# 支付宝沙箱接入步骤

个人开发者不需要企业资质即可使用支付宝沙箱。沙箱的 APPID、密钥和买家账号
都是独立的一套，**不能**用正式环境的参数。

## 1. 创建沙箱应用

1. 登录 [支付宝开放平台](https://open.alipay.com/)，进入「控制台 → 沙箱」。
2. 在「沙箱应用」里找到默认应用，记下 **APPID**。
3. 同一个页面下方有「沙箱账号」，里面有**买家账号**和登录密码，
   付款时用这个账号登录，不要用自己的支付宝。

## 2. 生成并上传密钥

1. 下载支付宝的「密钥工具」（开放平台文档里的 AlipayDevelopmentAssistant），
   选择 **RSA2**、密钥长度 **2048**，生成一对应用密钥。
2. 把**应用公钥**复制到沙箱应用的「接口加签方式 → 自定义密钥」里并保存。
3. 保存后页面会显示**支付宝公钥**，复制它。
4. 应用私钥只留在本地，不要上传到任何仓库或聊天工具。

本项目支持三种填法：PEM 文件路径、PEM 文本、密钥工具导出的裸 base64。
推荐用文件：

```text
backend/secrets/
├── alipay_app_private.pem   # 应用私钥
└── alipay_public.pem        # 支付宝公钥
```

`backend/secrets/` 和 `*.pem` 已在 `.gitignore` 中，不会被提交。
Docker Compose 会把该目录**只读**挂载到容器的 `/app/secrets`。

## 3. 本地配置

编辑 `backend/.env`：

```dotenv
PAYMENT_PROVIDER=alipay
PAYMENT_MOCK_BASE_URL=http://localhost:5173
PUBLIC_BASE_URL=http://localhost:8000

ALIPAY_APP_ID=2021xxxxxxxxxxxx
ALIPAY_PRIVATE_KEY=secrets/alipay_app_private.pem
ALIPAY_PUBLIC_KEY=secrets/alipay_public.pem
ALIPAY_GATEWAY=https://openapi-sandbox.dl.alipaydev.com/gateway.do
ALIPAY_NOTIFY_URL=
ALIPAY_SELLER_ID=
```

改完重启后端（Docker 用 `docker compose up -d backend`，本地直接重启 uvicorn）。

## 4. 异步通知与主动查单

支付宝的异步通知必须能**从公网访问**后端。本地开发有两种方式：

- **内网穿透**：把 `PUBLIC_BASE_URL` 改成穿透地址（如 cpolar / ngrok 分配的
  HTTPS 域名），支付宝才能回调 `/api/payments/alipay/notify`。
- **不配回调**：保持 `PUBLIC_BASE_URL` 为本地地址。付款完成后支付宝仍会跳回
  `/pay/<支付单号>`，页面上的「我已完成支付」会调用 `alipay.trade.query`
  主动查单并核销。功能完整，只是少了实时通知。

服务器部署时把 `PUBLIC_BASE_URL` 设为公网地址（例如
`http://121.196.150.159`），确认安全组放行对应端口，并保证
`ALIPAY_NOTIFY_URL` 为空或指向公网可达的地址。

## 5. 验证一笔支付

1. 用宠物主账号登录，对一笔「待支付」订单点「去支付」。
2. 收银台点「前往支付宝支付」，在新窗口用**沙箱买家账号**登录付款。
3. 付款成功后回到 PawCare，页面应显示「已支付」，订单的 `payment_status`
   变为 `paid`，并收到一条站内通知。
4. 管理端审计日志里能看到 `payment.paid`，支付单号与支付宝交易号对应。

## 常见问题

| 现象 | 原因 |
|---|---|
| 创建支付单返回 503「支付宝参数未配置完整」 | APPID / 两个密钥有空的 |
| 收银台报「验签失败」 | 应用公钥传错、用了正式环境密钥，或 APPID 与密钥不匹配 |
| 网关返回 `isv.invalid-signature`，但公钥和 APPID 都对 | 请求待签名串漏了 `sign_type`。项目已在 `sign_content` 中保留它；只有异步通知验签才剔除 `sign_type`（见 `notify_content`） |
| 收银台报「订单已失效」 | 支付单超过 15 分钟；点「重新生成支付单」 |
| 付款后页面一直「等待支付」 | 没有公网回调且没有点「我已完成支付」；点一次即可主动查单 |
| 通知一直失败 | `PUBLIC_BASE_URL` 是 localhost，或服务器防火墙没放行 |

## 安全注意

- 应用私钥等同于收款能力，泄露后必须立刻在开放平台重置密钥。
- 仓库里只有 `.env.example` 和 `secrets/.gitkeep`，不要提交真实 `.env`、`.pem`。
- 沙箱和正式环境共用代码，但网关、APPID、密钥、买家账号都不同，切换时成套替换。
