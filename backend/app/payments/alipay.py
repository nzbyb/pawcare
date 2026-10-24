"""支付宝开放平台 RSA2 签名与电脑网站支付。

只依赖 cryptography + httpx，不引入官方 SDK：
- 生成 alipay.trade.page.pay 收银台地址；
- 校验异步通知签名；
- 主动查单（alipay.trade.query），并校验支付宝响应签名。

密钥既可以是 PEM 内容，也可以是文件路径；支付宝后台复制出来的
裸 base64 公钥也会自动补上 PEM 头尾。
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)

BEIJING = ZoneInfo("Asia/Shanghai")
TRADE_SUCCESS = {"TRADE_SUCCESS", "TRADE_FINISHED"}


class AlipayError(Exception):
    """支付宝配置、签名或通信失败。"""


def _ensure_pem(value: str, kind: str, header: str | None = None) -> str:
    """把 PEM、路径和裸 base64 统一成 PEM 文本。

    文件里也可能只有一行 base64（支付宝密钥工具默认导出格式），
    读出来之后要继续走补头尾的逻辑。
    """
    text = (value or "").strip()
    if not text:
        raise AlipayError(f"未配置{kind}")
    if "BEGIN" in text:
        # .env 里常用 \n 表示换行。
        return text.replace("\\n", "\n").strip()

    path = Path(text)
    if path.is_file():
        content = path.read_text(encoding="utf-8-sig").strip()
        if not content:
            raise AlipayError(f"{kind}文件为空")
        if "BEGIN" in content:
            return content.replace("\\n", "\n").strip()
        text = content

    body = "\n".join(text[i : i + 64] for i in range(0, len(text), 64))
    header = header or ("PRIVATE KEY" if kind == "应用私钥" else "PUBLIC KEY")
    return f"-----BEGIN {header}-----\n{body}\n-----END {header}-----\n"


def load_private_key(value: str) -> rsa.RSAPrivateKey:
    """支持 PKCS8 与 PKCS1 两种私钥；裸 base64 两种头都试一次。"""
    pem = _ensure_pem(value, "应用私钥").encode("utf-8")
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (ValueError, TypeError):
        try:
            fallback = _ensure_pem(
                value, "应用私钥", header="RSA PRIVATE KEY"
            ).encode("utf-8")
            key = serialization.load_pem_private_key(fallback, password=None)
        except (ValueError, TypeError) as exc:
            raise AlipayError("支付宝应用私钥格式不正确") from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise AlipayError("支付宝应用私钥必须是 RSA 私钥")
    return key


def load_public_key(value: str) -> rsa.RSAPublicKey:
    """支持 SPKI 与 PKCS1 两种公钥；裸 base64 两种头都试一次。"""
    pem = _ensure_pem(value, "支付宝公钥").encode("utf-8")
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError):
        try:
            fallback = _ensure_pem(
                value, "支付宝公钥", header="RSA PUBLIC KEY"
            ).encode("utf-8")
            key = serialization.load_pem_public_key(fallback)
        except (ValueError, TypeError) as exc:
            raise AlipayError("支付宝公钥格式不正确") from exc
    if not isinstance(key, rsa.RSAPublicKey):
        raise AlipayError("支付宝公钥必须是 RSA 公钥")
    return key


def sign_content(params: dict[str, Any]) -> str:
    """请求待签名串：剔除 sign 和空值，按 key 升序拼接。

    请求签名必须保留 sign_type——网关生成的验签串里也带着
    sign_type=RSA2，漏掉它会一律返回 isv.invalid-signature。
    """
    items = [
        (key, str(value))
        for key, value in params.items()
        if key != "sign" and value not in (None, "")
    ]
    return "&".join(f"{key}={value}" for key, value in sorted(items))


def notify_content(params: dict[str, Any]) -> str:
    """异步通知待验签串：支付宝的通知验签要剔除 sign 和 sign_type。"""
    items = [
        (key, str(value))
        for key, value in params.items()
        if key not in ("sign", "sign_type") and value not in (None, "")
    ]
    return "&".join(f"{key}={value}" for key, value in sorted(items))


def sign_params(params: dict[str, Any], private_key: str) -> str:
    return _sign_text(sign_content(params), private_key)


def _sign_text(content: str, private_key: str) -> str:
    key = load_private_key(private_key)
    signature = key.sign(
        content.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


def _verify_text(content: str, signature: str, public_key: str) -> bool:
    try:
        decoded = base64.b64decode(signature, validate=True)
    except (ValueError, TypeError):
        return False
    key = load_public_key(public_key)
    try:
        key.verify(
            decoded,
            content.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature:
        return False
    return True


def verify_params(params: dict[str, Any], public_key: str) -> bool:
    """校验我们自己生成的请求签名（含 sign_type）。"""
    signature = params.get("sign")
    if not signature:
        return False
    return _verify_text(sign_content(params), signature, public_key)


def timestamp() -> str:
    return datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def _base_params(app_id: str, method: str) -> dict[str, Any]:
    return {
        "app_id": app_id,
        "method": method,
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": timestamp(),
        "version": "1.0",
    }


def page_pay_url(
    *,
    app_id: str,
    private_key: str,
    gateway: str,
    notify_url: str,
    return_url: str,
    out_trade_no: str,
    amount: str,
    subject: str,
    timeout_express: str,
) -> str:
    """生成电脑网站支付收银台地址（用户浏览器跳转）。"""
    params = _base_params(app_id, "alipay.trade.page.pay")
    params["notify_url"] = notify_url
    params["return_url"] = return_url
    params["biz_content"] = json.dumps(
        {
            "out_trade_no": out_trade_no,
            "product_code": "FAST_INSTANT_TRADE_PAY",
            "total_amount": amount,
            "subject": subject,
            "timeout_express": timeout_express,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    params["sign"] = sign_params(params, private_key)
    return f"{gateway}?{urlencode(params)}"


def verify_notify(form: dict[str, Any], public_key: str) -> bool:
    """异步通知验签。sign_type 只接受 RSA2。"""
    if form.get("sign_type") not in (None, "", "RSA2"):
        return False
    sign = form.get("sign")
    if not isinstance(sign, str) or not sign:
        return False
    if " " in sign:
        # 表单解码会把 base64 里的 "+" 变成空格，验签前还原。
        sign = sign.replace(" ", "+")
    return _verify_text(notify_content(form), sign, public_key)


def _extract_node(content: bytes, key: str) -> bytes:
    """从响应原始字节里截出业务节点的 JSON，用于验签。

    支付宝响应签名针对的是响应节点的原始字节；重新 json.dumps、
    或按 UTF-8 重新编码都会改变字节（沙箱的 POST 查单响应是 GBK）。
    """
    marker = f'"{key}"'.encode("utf-8")
    index = content.find(marker)
    if index < 0:
        return b""
    colon = content.find(b":", index + len(marker))
    if colon < 0:
        return b""
    start = colon + 1
    while start < len(content) and content[start] in b" \t\r\n":
        start += 1
    if start >= len(content) or content[start : start + 1] != b"{":
        return b""

    depth = 0
    in_string = False
    escaped = False
    for position in range(start, len(content)):
        char = content[position]
        if in_string:
            if escaped:
                escaped = False
            elif char == 0x5C:  # 反斜杠
                escaped = True
            elif char == 0x22:  # 双引号
                in_string = False
            continue
        if char == 0x22:
            in_string = True
        elif char == 0x7B:  # {
            depth += 1
        elif char == 0x7D:  # }
            depth -= 1
            if depth == 0:
                return content[start : position + 1]
    return b""


def _verify_response(
    content: bytes, node_key: str, public_key: str, charset: str = "utf-8"
) -> dict[str, Any]:
    try:
        payload = json.loads(content.decode(charset))
    except (UnicodeDecodeError, LookupError) as exc:
        raise AlipayError("支付宝响应编码不合法") from exc
    except json.JSONDecodeError as exc:
        raise AlipayError("支付宝响应不是合法 JSON") from exc

    node = payload.get(node_key)
    if not isinstance(node, dict):
        raise AlipayError("支付宝响应缺少业务节点")

    signature = payload.get("sign")
    raw_node = _extract_node(content, node_key)
    if not signature or not raw_node:
        raise AlipayError("支付宝响应缺少签名")
    try:
        decoded = base64.b64decode(signature, validate=True)
    except (ValueError, TypeError) as exc:
        raise AlipayError("支付宝响应签名格式错误") from exc
    key = load_public_key(public_key)
    try:
        key.verify(
            decoded,
            raw_node,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise AlipayError("支付宝响应验签失败") from exc
    return node


def query_trade(
    *,
    app_id: str,
    private_key: str,
    public_key: str,
    gateway: str,
    out_trade_no: str,
    timeout: float = 5.0,
) -> dict[str, Any] | None:
    """主动查单。交易不存在时返回 None。"""
    params = _base_params(app_id, "alipay.trade.query")
    params["biz_content"] = json.dumps(
        {"out_trade_no": out_trade_no}, ensure_ascii=False, separators=(",", ":")
    )
    params["sign"] = sign_params(params, private_key)

    try:
        response = httpx.post(gateway, data=params, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AlipayError(f"支付宝查单失败：{exc}") from exc

    node = _verify_response(
        response.content,
        "alipay_trade_query_response",
        public_key,
        getattr(response, "encoding", None) or "utf-8",
    )
    code = str(node.get("code", ""))
    if code == "10000":
        return node
    sub_code = str(node.get("sub_code", ""))
    if sub_code == "ACQ.TRADE_NOT_EXIST":
        return None
    logger.warning(
        "支付宝查单返回失败 code=%s sub_code=%s msg=%s",
        code,
        sub_code,
        node.get("sub_msg") or node.get("msg"),
    )
    raise AlipayError(str(node.get("sub_msg") or node.get("msg") or "支付宝查单失败"))
