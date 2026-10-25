"""支付宝渠道：RSA2 签名、异步通知验签、金额校验与主动查单。"""

import base64
import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.config import settings
from app.models.audit import AuditLog
from app.models.payment import PaymentOrder
from app.payments import alipay
from tests.test_payments import make_order

APP_ID = "2021000000000001"
SELLER_ID = "2088000000000001"
GATEWAY = "https://sandbox.example.com/gateway.do"


def _keypair(tmp_path, name: str):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    private_path = tmp_path / f"{name}_private.pem"
    public_path = tmp_path / f"{name}_public.pem"
    private_path.write_text(private_pem, encoding="utf-8")
    public_path.write_text(public_pem, encoding="utf-8")
    return {
        "private_pem": private_pem,
        "public_pem": public_pem,
        "private_path": str(private_path),
        "public_path": str(public_path),
    }


def _sign_bytes(data: bytes, private_pem: str) -> str:
    key = serialization.load_pem_private_key(
        private_pem.encode("utf-8"), password=None
    )
    signature = key.sign(data, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def _sign_text(text: str, private_pem: str) -> str:
    return _sign_bytes(text.encode("utf-8"), private_pem)


@pytest.fixture()
def alipay_env(tmp_path, monkeypatch):
    app_keys = _keypair(tmp_path, "app")
    alipay_keys = _keypair(tmp_path, "alipay")
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "alipay")
    monkeypatch.setattr(settings, "ALIPAY_APP_ID", APP_ID)
    monkeypatch.setattr(settings, "ALIPAY_PRIVATE_KEY", app_keys["private_path"])
    monkeypatch.setattr(settings, "ALIPAY_PUBLIC_KEY", alipay_keys["public_path"])
    monkeypatch.setattr(settings, "ALIPAY_GATEWAY", GATEWAY)
    monkeypatch.setattr(settings, "ALIPAY_SELLER_ID", SELLER_ID)
    monkeypatch.setattr(settings, "ALIPAY_NOTIFY_URL", "")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://pawcare.test")
    monkeypatch.setattr(
        settings, "PAYMENT_MOCK_BASE_URL", "https://pawcare.test"
    )
    return {"app": app_keys, "alipay": alipay_keys}


def _payments(client, headers, order_id: int) -> dict:
    body = client.post(
        "/api/payments", headers=headers, json={"order_id": order_id}
    ).json()
    assert body["code"] == 200, body
    return body["data"]


def _token_of(payment: dict) -> str:
    pay_url = payment.get("pay_url") or ""
    params = parse_qs(urlparse(pay_url).query)
    return_url = params["return_url"][0]
    return parse_qs(urlparse(return_url).query)["token"][0]


def _notify_form(payment: dict, alipay_private_pem: str, **overrides) -> dict:
    form = {
        "app_id": APP_ID,
        "seller_id": SELLER_ID,
        "out_trade_no": payment["payment_no"],
        "trade_no": "2026102422001400000000000001",
        "trade_status": "TRADE_SUCCESS",
        "total_amount": f"{payment['amount']:.2f}",
        "receipt_amount": f"{payment['amount']:.2f}",
        "gmt_payment": "2026-10-24 10:05:00",
        "notify_time": "2026-10-24 10:05:01",
        "notify_type": "trade_status_sync",
        "notify_id": "notify-0001",
        "charset": "utf-8",
        "version": "1.0",
        "sign_type": "RSA2",
    }
    form.update(overrides)
    # 支付宝异步通知的待验签串不含 sign / sign_type。
    form["sign"] = _sign_text(alipay.notify_content(form), alipay_private_pem)
    return form


def test_create_alipay_payment_signs_page_pay_url(
    client, owner_headers, admin_headers, alipay_env
):
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])

    assert payment["channel"] == "alipay"
    assert payment["qr_content"] == ""
    assert payment["pay_url"].startswith(GATEWAY + "?")

    params = {key: values[0] for key, values in parse_qs(
        urlparse(payment["pay_url"]).query
    ).items()}
    assert params["method"] == "alipay.trade.page.pay"
    assert params["app_id"] == APP_ID
    assert params["notify_url"] == "https://pawcare.test/api/payments/alipay/notify"
    assert payment["payment_no"] in params["return_url"]
    # 请求签名必须把 sign_type 也算进去，否则网关会报 isv.invalid-signature。
    assert "sign_type=RSA2" in alipay.sign_content(params)
    assert alipay.verify_params(params, alipay_env["app"]["public_pem"])

    content = json.loads(params["biz_content"])
    assert content["out_trade_no"] == payment["payment_no"]
    assert content["total_amount"] == f"{order['total_amount']:.2f}"
    assert content["timeout_express"] == "15m"
    assert len(_token_of(payment)) >= 20


def test_alipay_notify_marks_order_paid(
    client, owner_headers, admin_headers, db, alipay_env
):
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])
    form = _notify_form(payment, alipay_env["alipay"]["private_pem"])

    resp = client.post("/api/payments/alipay/notify", data=form)
    assert resp.status_code == 200
    assert resp.text == "success"

    row = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment["payment_no"])
        .first()
    )
    assert row.status == "paid"
    assert row.transaction_id == form["trade_no"]
    detail = client.get(
        f"/api/boarding/orders/{order['id']}", headers=owner_headers
    ).json()["data"]
    assert detail["payment_status"] == "paid"
    assert detail["paid_amount"] == order["total_amount"]

    paid_audits = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "payment.paid",
            AuditLog.target_id == row.id,
        )
        .count()
    )
    assert paid_audits == 1

    # 支付宝会重复通知，必须幂等。
    replay = client.post("/api/payments/alipay/notify", data=form)
    assert replay.text == "success"
    db.expire_all()
    assert (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "payment.paid",
            AuditLog.target_id == row.id,
        )
        .count()
        == 1
    )


def test_alipay_notify_rejects_tampered_amount(
    client, owner_headers, admin_headers, db, alipay_env
):
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])
    form = _notify_form(
        payment,
        alipay_env["alipay"]["private_pem"],
        total_amount="0.01",
    )

    resp = client.post("/api/payments/alipay/notify", data=form)
    assert resp.text == "failure"

    db.expire_all()
    row = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment["payment_no"])
        .first()
    )
    assert row.status == "created"
    assert row.notify_payload is None


def test_alipay_notify_rejects_bad_signature_and_app_id(
    client, owner_headers, admin_headers, alipay_env
):
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])

    form = _notify_form(payment, alipay_env["alipay"]["private_pem"])
    form["sign"] = "not-a-signature"
    assert client.post("/api/payments/alipay/notify", data=form).text == "failure"

    # 换用应用私钥签名：支付网关不可能持有这把钥匙，验签必须失败。
    forged = _notify_form(payment, alipay_env["app"]["private_pem"])
    assert client.post("/api/payments/alipay/notify", data=forged).text == "failure"

    # 签名正确但 app_id 不属于本项目。
    other_app = _notify_form(
        payment,
        alipay_env["alipay"]["private_pem"],
        app_id="2021999999999999",
    )
    assert client.post("/api/payments/alipay/notify", data=other_app).text == "failure"

    # 通知验签的待签串不含 sign_type；按请求签名规则签出来的必须被拒绝。
    request_style = _notify_form(payment, alipay_env["alipay"]["private_pem"])
    request_style["sign"] = _sign_text(
        alipay.sign_content(request_style),
        alipay_env["alipay"]["private_pem"],
    )
    assert (
        client.post("/api/payments/alipay/notify", data=request_style).text
        == "failure"
    )


def test_mock_notify_is_disabled_for_alipay(
    client, owner_headers, admin_headers, alipay_env
):
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])
    token = _token_of(payment)

    resp = client.post(
        "/api/payments/mock/notify",
        json={"payment_no": payment["payment_no"], "token": token},
    )
    assert resp.json()["code"] == 403
    assert resp.json()["message"] == "模拟支付已关闭"


def test_raw_base64_key_files_are_supported(tmp_path):
    """支付宝密钥工具导出的文件常常只有一行 base64，没有 PEM 头尾。"""
    keys = _keypair(tmp_path, "raw")
    private_path = tmp_path / "raw_private.pem"
    public_path = tmp_path / "raw_public.pem"
    private_path.write_text(
        "".join(keys["private_pem"].splitlines()[1:-1]), encoding="utf-8"
    )
    public_path.write_text(
        "".join(keys["public_pem"].splitlines()[1:-1]), encoding="utf-8"
    )

    private_key = alipay.load_private_key(str(private_path))
    public_key = alipay.load_public_key(str(public_path))
    assert private_key.key_size == 2048
    assert (
        private_key.public_key().public_numbers().n
        == public_key.public_numbers().n
    )


class FakeResponse:
    def __init__(
        self,
        text: str,
        content: bytes | None = None,
        encoding: str = "utf-8",
    ):
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.encoding = encoding

    def raise_for_status(self) -> None:
        return None


def _query_response(payment_no: str, amount: float, private_pem: str) -> FakeResponse:
    node = {
        "code": "10000",
        "msg": "Success",
        "out_trade_no": payment_no,
        "trade_no": "2026102422001400000000000002",
        "trade_status": "TRADE_SUCCESS",
        "total_amount": f"{amount:.2f}",
    }
    raw = json.dumps(node, ensure_ascii=False, separators=(",", ":"))
    signature = _sign_text(raw, private_pem)
    return FakeResponse(
        '{"alipay_trade_query_response":' + raw + ',"sign":"' + signature + '"}'
    )


def test_refresh_queries_alipay_and_settles(
    client, owner_headers, admin_headers, monkeypatch, alipay_env
):
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])

    def fake_post(url, data=None, timeout=None):
        assert url == GATEWAY
        return _query_response(
            payment["payment_no"],
            payment["amount"],
            alipay_env["alipay"]["private_pem"],
        )

    monkeypatch.setattr(alipay.httpx, "post", fake_post)

    body = client.post(
        f"/api/payments/{payment['payment_no']}/refresh", headers=owner_headers
    ).json()
    assert body["code"] == 200, body
    assert body["data"]["status"] == "paid"

    detail = client.get(
        f"/api/boarding/orders/{order['id']}", headers=owner_headers
    ).json()["data"]
    assert detail["payment_status"] == "paid"


def test_refresh_settles_payment_closed_by_expiry(
    client, owner_headers, admin_headers, db, monkeypatch, alipay_env
):
    """支付单过期关单后用户才付完款，主动查单仍要能核销。"""
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])
    row = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment["payment_no"])
        .one()
    )
    row.status = "closed"
    row.expires_at = datetime.now() - timedelta(minutes=1)
    db.commit()

    monkeypatch.setattr(
        alipay.httpx,
        "post",
        lambda url, data=None, timeout=None: _query_response(
            payment["payment_no"],
            payment["amount"],
            alipay_env["alipay"]["private_pem"],
        ),
    )

    body = client.post(
        f"/api/payments/{payment['payment_no']}/refresh", headers=owner_headers
    ).json()
    assert body["code"] == 200, body
    assert body["data"]["status"] == "paid"

    detail = client.get(
        f"/api/boarding/orders/{order['id']}", headers=owner_headers
    ).json()["data"]
    assert detail["payment_status"] == "paid"


def test_refresh_skips_long_closed_payment(
    client, owner_headers, admin_headers, db, monkeypatch, alipay_env
):
    """过期超过一天的关单不再查，避免每次回到页面都打网关。"""
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])
    row = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment["payment_no"])
        .one()
    )
    row.status = "closed"
    row.expires_at = datetime.now() - timedelta(hours=25)
    db.commit()

    calls: list[int] = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        raise AssertionError("不应发起查单")

    monkeypatch.setattr(alipay.httpx, "post", fake_post)
    body = client.post(
        f"/api/payments/{payment['payment_no']}/refresh", headers=owner_headers
    ).json()
    assert body["code"] == 200, body
    assert body["data"]["status"] == "closed"
    assert calls == []


def test_query_verifies_gbk_response_bytes(
    client, owner_headers, admin_headers, monkeypatch, alipay_env
):
    """沙箱 POST 查单响应是 GBK，签名针对原始字节而不是 UTF-8 重编码。"""
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])

    node = json.dumps(
        {
            "code": "10000",
            "msg": "Success",
            "out_trade_no": payment["payment_no"],
            "trade_no": "2026102422001400000000000003",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": f"{payment['amount']:.2f}",
            "subject": "宠物寄养",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("gbk")
    signature = _sign_bytes(node, alipay_env["alipay"]["private_pem"]).encode()
    body = (
        b'{"alipay_trade_query_response":'
        + node
        + b',"sign":"'
        + signature
        + b'"}'
    )

    monkeypatch.setattr(
        alipay.httpx,
        "post",
        lambda url, data=None, timeout=None: FakeResponse(
            body.decode("gbk"), body, encoding="gbk"
        ),
    )

    result = client.post(
        f"/api/payments/{payment['payment_no']}/refresh", headers=owner_headers
    ).json()
    assert result["code"] == 200, result
    assert result["data"]["status"] == "paid"


def test_public_refresh_requires_token_and_settles(
    client, owner_headers, admin_headers, monkeypatch, alipay_env
):
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])
    token = _token_of(payment)

    monkeypatch.setattr(
        alipay.httpx,
        "post",
        lambda url, data=None, timeout=None: _query_response(
            payment["payment_no"],
            payment["amount"],
            alipay_env["alipay"]["private_pem"],
        ),
    )

    wrong = client.post(
        f"/api/payments/public/{payment['payment_no']}/refresh",
        params={"token": "z" * 24},
    ).json()
    assert wrong["code"] == 403

    body = client.post(
        f"/api/payments/public/{payment['payment_no']}/refresh",
        params={"token": token},
    ).json()
    assert body["code"] == 200, body
    assert body["data"]["status"] == "paid"


def test_public_payment_exposes_pay_url(
    client, owner_headers, admin_headers, alipay_env
):
    order = make_order(client, owner_headers, admin_headers)
    payment = _payments(client, owner_headers, order["id"])
    token = _token_of(payment)

    body = client.get(
        f"/api/payments/public/{payment['payment_no']}", params={"token": token}
    ).json()
    assert body["code"] == 200
    assert body["data"]["channel"] == "alipay"
    assert body["data"]["pay_url"] == payment["pay_url"]
    assert "owner_id" not in body["data"]


def test_reused_payment_gets_fresh_signature(
    client, owner_headers, admin_headers, alipay_env
):
    """复用未过期支付单时重新签名，避免旧时间戳被网关拒绝。"""
    order = make_order(client, owner_headers, admin_headers)
    first = _payments(client, owner_headers, order["id"])
    second = _payments(client, owner_headers, order["id"])

    assert second["payment_no"] == first["payment_no"]
    params = {
        key: values[0]
        for key, values in parse_qs(urlparse(second["pay_url"]).query).items()
    }
    assert alipay.verify_params(params, alipay_env["app"]["public_pem"])
    assert json.loads(params["biz_content"])["out_trade_no"] == first["payment_no"]
