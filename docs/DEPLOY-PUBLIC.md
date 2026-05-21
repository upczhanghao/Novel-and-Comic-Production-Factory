# 公网部署安全手册（Debian 12）

本手册针对 **Debian 12 (bookworm)** 服务器自用部署。Storia 当前是单进程 uvicorn 架构，限流状态在内存里，不支持多副本/多用户。商业化部署不在本文范围内。

> 本文所有命令默认你是普通用户，已配置 `sudo`。把 `you` 替换成你的用户名，`yourdomain.com` 替换成你自己的域名。

---

## 一、核心问题：陌生人发现你的域名后，怎样才进不来？

把域名挂到公网那一刻，你就要假设它**一定会被发现**：

- TLS 证书签发会进入 [crt.sh](https://crt.sh/) 等证书透明日志，全网可查。
- DNS 历史记录（SecurityTrails、DNSDumpster）也会留痕。
- 哪怕没人主动找，公网 IP 段的扫描器每天都在挨个敲门。

**"靠没人知道"不是防御**。本手册的核心，是在"陌生人已经知道 `storia.yourdomain.com` 存在"的前提下，让他依然无法：

1. 打开 UI；
2. 调用任何 `/api/*` 接口；
3. 间接消耗你的 LLM / 图片 / Embedding 配额。

为达成这点，Storia 的部署采用**四层串联**的纵深防御。任何一层失守，下一层仍能兜住——但**不要**只靠一层。

| 层 | 作用 | 拦截对象 | 推荐方案 A 实现 | 备用方案 B 实现 |
|---|---|---|---|---|
| L1 边界接入 | 让陌生人的 TCP 包根本到不了你的机器 | 端口扫描、直连 IP | Cloudflare Tunnel（机器不开 80/443） | nginx + 防火墙 + IP 白名单 |
| L2 身份验证 | 让没有授权身份的人进不到反向代理之后 | 拿到域名的陌生人 | Cloudflare Access（邮箱/OAuth/TOTP） | API Token（`NOVELWRITER_API_TOKEN`）|
| L3 应用限流 | 即使前两层被绕过，也限制单位时间调用次数 | 拿到 Token 的人滥用 | 应用内限流（默认开启） | 同左 |
| L4 厂商硬限额 | 即使应用层被打穿，也保住钱包 | 失控的扣费 | LLM 厂商后台预算上限 | 同左 |

下文先做**一次性基础准备**，再分层讲每一层的目的与配置。读完一遍你就知道：每条命令在防什么，省哪条会留下哪个口子。

---

## 二、一次性基础准备

这部分与防护方案无关，A、B 方案都需要。

### 2.1 系统与运行时

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip git curl ca-certificates ufw

# Node.js 20（用于前端构建）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
```

> Debian 12 默认 Python 是 3.11，满足 Storia 要求（≥ 3.11）。

### 2.2 SSH 加固（防"另一条路被攻破"）

域名再怎么防，SSH 端口被爆破一样完蛋：

```bash
# 仅密钥登录，禁用密码
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh
```

### 2.3 部署 Storia 主体

```bash
cd /opt
sudo mkdir storia && sudo chown $USER:$USER storia
cd storia
git clone <你的仓库地址> .

chmod +x start_api.sh
./start_api.sh --skip-build  # 冒烟测试后端能起来；Ctrl-C 停掉
```

### 2.4 用 systemd 托管（关键：只监听 127.0.0.1）

新建 `/etc/systemd/system/storia.service`：

```ini
[Unit]
Description=Storia — Novel and Comic Production Factory
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=you
Group=you
WorkingDirectory=/opt/storia
EnvironmentFile=/opt/storia/.env
# 关键：进程只听本地，公网必须经过 L1 反向代理才能到这里
ExecStart=/opt/storia/.venv/bin/python -m uvicorn api_server:app --host 127.0.0.1 --port 7860
Restart=always
RestartSec=10
ProtectSystem=strict
ReadWritePaths=/opt/storia
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

`/opt/storia/.env`（chmod 600）：

```bash
NOVELWRITER_HOST=127.0.0.1
NOVELWRITER_PORT=7860
# 仅方案 B 启用 Token；方案 A 由 Cloudflare Access 承担身份验证
# NOVELWRITER_API_TOKEN=<openssl rand -hex 32 的输出>
# NOVELWRITER_CORS_ORIGINS=https://storia.yourdomain.com
```

```bash
sudo chmod 600 /opt/storia/.env
sudo systemctl daemon-reload
sudo systemctl enable --now storia
journalctl -u storia -f
```

> **为什么死活要 `--host 127.0.0.1`？**
> 这是 L1 的最后一道保险。即使你今后误关了防火墙、误绑了公网 IP，进程依然只接受本机回环连接，陌生人 `curl http://你的公网IP:7860` 直接 connection refused。

---

## 三、防护方案 A：Cloudflare Tunnel + Access（首选）

A 方案的特点：**机器永远不暴露 80/443**，Tunnel 由你的服务器主动出站连到 Cloudflare 边缘；陌生人哪怕扫到你的 IP，也敲不出任何 HTTP 响应。身份验证由 Cloudflare Access 在边缘完成，未授权流量根本走不到你的机器。

### L1：让陌生人的包到不了机器 — Cloudflare Tunnel

**1. 域名托管到 Cloudflare**（免费版即可）。把域名 NS 改到 Cloudflare 给的两个地址，等生效。

**2. 装 cloudflared**：

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
  sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main" | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install -y cloudflared
```

**3. 创建 Tunnel**：

```bash
cloudflared tunnel login              # 浏览器选你要绑的域名
cloudflared tunnel create storia      # 记下输出的 UUID
```

凭据文件落在 `~/.cloudflared/<UUID>.json`。

**4. 配置** `~/.cloudflared/config.yml`：

```yaml
tunnel: <UUID>
credentials-file: /home/you/.cloudflared/<UUID>.json
ingress:
  - hostname: storia.yourdomain.com
    service: http://127.0.0.1:7860
  - service: http_status:404
```

```bash
cloudflared tunnel route dns storia storia.yourdomain.com
sudo cloudflared --config /home/you/.cloudflared/config.yml service install
sudo systemctl enable --now cloudflared
```

> `cloudflared service install` 默认读 root 的 `~/.cloudflared`。把 config 与 credentials 拷到 `/etc/cloudflared/`，或在安装后修改 systemd 单元的 `ExecStart` 指向你的 config 路径。

**5. 防火墙：拒绝一切入站**

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw enable
# 注意：80/443 不要放行。所有 Web 流量走 Tunnel 出站。
```

**这一步做完，从公网视角你的机器除了 SSH 没有任何 TCP 端口可见。** 陌生人扫到你的 IP 也只能止步于此。

### L2：阻止陌生人通过 Cloudflare 边缘 — Access 策略

Cloudflare 控制台 → Zero Trust → Access → Applications：

- 类型：**Self-hosted**
- 应用域名：`storia.yourdomain.com`
- 策略：`Action: Allow`，规则 `Emails` = 你的邮箱（或 GitHub OAuth、TOTP、Google Workspace 等）

**做完这步，没通过 Access 验证的请求在边缘就被拦掉**，根本不会进入 Tunnel，更不会到你的进程。

> **为什么 A 方案不用 Token？** 身份验证已经被 Cloudflare Access 全权接管，再加 Token 反而让浏览器要多管理一份凭据。如果你想要"双保险"也不是不行，但收益很小，复杂度更高。

---

## 四、防护方案 B：nginx + Token + IP 白名单（备用）

适合不愿走 Cloudflare 的人，但配置项多更易出错，也无法避免你的 IP 被扫描器看到。

### L1：让陌生人到不了进程 — 防火墙 + nginx 反代

**装 nginx + 自动签证书**：

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'                                  # 仅放行 80 + 443
sudo ufw enable
sudo certbot --nginx -d storia.yourdomain.com                # 自动签 + 改 nginx 配置
```

`/etc/nginx/sites-available/storia`（在 certbot 自动生成基础上微调）：

```nginx
server {
    listen 443 ssl http2;
    server_name storia.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/storia.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/storia.yourdomain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;

    # ★ L1 加强：固定 IP 白名单（强烈建议，能配就配）
    # allow 1.2.3.4;        # 你家宽带固定 IP / 公司出口
    # deny all;

    # SSE / 长连接所必须
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;
    proxy_read_timeout 3600s;

    client_max_body_size 64m;

    location / { proxy_pass http://127.0.0.1:7860; }
}

server {
    listen 80;
    server_name storia.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/storia /etc/nginx/sites-enabled/storia
sudo nginx -t && sudo systemctl reload nginx
```

certbot 已经写好自动续期 timer，`systemctl list-timers | grep certbot` 可以看到。

> **没有 IP 白名单的 B 方案有多脆？** 任何人输入 `https://storia.yourdomain.com` 就能打开登录界面。Token 是你唯一的身份验证。如果浏览器 localStorage 在公共电脑被复制、或前端有个未发现的 XSS，Token 就裸奔。所以**强烈建议至少配一条 `allow` 规则**。

### L2：阻止陌生人调用接口 — API Token

编辑 `/opt/storia/.env`，取消注释：

```bash
NOVELWRITER_API_TOKEN=$(openssl rand -hex 32)         # 在 shell 里跑，把输出粘进去
NOVELWRITER_CORS_ORIGINS=https://storia.yourdomain.com
```

```bash
sudo systemctl restart storia
```

浏览器首次打开 `https://storia.yourdomain.com`，DevTools console 执行：

```js
localStorage.setItem('novelwriter_api_token', '<你的 token>')
```

刷新即可。

> ⚠️ `NOVELWRITER_API_TOKEN` 与 `NOVELWRITER_CORS_ORIGINS=*` 同时设置时，进程会拒绝启动 —— 既要鉴权又要任意 Origin 是矛盾配置。

---

## 五、L3 — 应用层限流（A、B 方案共用，默认开启）

前两层防陌生人，这一层防"已经进来的人滥用"——比如你共享给朋友的账号、Token 偶然泄露、自家脚本写错了死循环。

- 配置落 `/opt/storia/rate_limits.json`，可在 UI **「安全与限流」** 页热更，无需重启。
- 默认两个桶：
  - `generate`：10 次 / 分钟，覆盖所有调用 LLM / 图片 / Embedding / 知识库导入的端点。
  - `default`：60 次 / 分钟，覆盖其它 `/api/*`。
- 客户端识别：优先取 `X-Forwarded-For` 首跳 IP（Cloudflare/nginx 自动传过来）。
- 命中限流返回 `429` + `Retry-After: 60`。
- 「安全与限流」页面每 3 秒轮询一次，给出每桶 60s 命中/拒绝、累计、Top 客户端，便于实时调阈值。

---

## 六、L4 — 厂商账户硬限额（最后一道止损）

**即使前三层全部失守**，只要你在厂商后台设了硬限额，损失也就到此为止。这是最重要、最便宜、最容易被忽视的一层：

- OpenAI：Settings → Limits → 每月预算上限（hard limit）+ 每分钟 RPM/TPM。
- DeepSeek / Gemini / Claude：均有类似预算或速率配额，按厂商文档设。
- 给 Storia 用的 API Key **单独开一个专用 Key**，不要复用主账户 Key —— 出问题立刻 revoke 不影响其它项目。

> 应用层限流只能拦自己进程里的请求，**不能撤回已经发到 LLM 厂商账户的扣费**。L4 是唯一能在最坏情况下保住钱包的机制。

---

## 七、紧急处置：每一层失守的应对

| 症状 | 失守的层 | 处置 |
|---|---|---|
| 限流 UI 看到某 IP 拒绝数飙升 | L2 被绕过 | 把 `generate` 桶 per_min 临时调到 1 或 0；`sudo ufw insert 1 deny from <ip>` 拉黑（A 方案在 Cloudflare WAF 加 IP block 规则）。 |
| LLM 厂商邮件提示用量异常 | L1~L3 全失守 | 立刻去厂商后台 revoke API Key（L4 兜底）；UI 限流 `enabled: false` 一键熔断本进程（已发出请求不可撤回）。 |
| 怀疑 Token 泄露（仅 B） | L2 失守 | `openssl rand -hex 32` 重新生成，写回 `.env`，`sudo systemctl restart storia`。旧 Token 立即失效。 |
| 怀疑 Cloudflare 账号被入侵（仅 A） | L1+L2 同时失守 | Cloudflare 控制台改密码 + 启用硬件 key MFA；Access 策略全部改成只允许新邮箱；轮换 Tunnel 凭据 (`cloudflared tunnel rotate`)。 |
| 服务器进程异常 / 内存暴涨 | — | `journalctl -u storia -n 200`、`ps aux \| grep uvicorn`、`sudo systemctl restart storia`。限流计数器只占内存，最坏情况也只是 IP 数量 × 数百字节。 |
| Cloudflare Tunnel 掉线（仅 A） | L1 故障，整站不可达 | `sudo systemctl status cloudflared`、`journalctl -u cloudflared -n 100`，常见原因是凭据过期或网络抖动。 |

---

## 八、升级流程

```bash
cd /opt/storia
sudo systemctl stop storia
git pull
./start_api.sh --skip-build  # hashed-deps 自动应用 requirements.txt 增量；Ctrl-C 立刻退
# 或强制重建前端：
NOVELWRITER_FORCE_BUILD=1 ./start_api.sh --skip-build
sudo systemctl start storia
journalctl -u storia -n 50
```

---

## 九、备份建议

把这些目录纳入定期备份（推荐用 `restic` 或 `borgbackup` 加密增量备份到对象存储）：

```text
/opt/storia/config.json          # 模型配置（含 API Key，敏感）
/opt/storia/projects.json        # 项目索引
/opt/storia/xp_presets.json      # XP 预设
/opt/storia/rate_limits.json     # 限流配置
/opt/storia/.env                 # Token 与环境变量（敏感）
/opt/storia/output/              # 项目输出
/opt/storia/styles/              # 文风模板与 DNA
/opt/storia/prompts/             # 提示词方案
/opt/storia/vectorstore/         # 知识库向量数据
```

含敏感数据的文件（`config.json`、`.env`、tunnel 凭据）务必加密备份，不要明文上传到任何对象存储。

---

## 十、不在本手册范围内的事

- **多副本 / 多进程部署**：限流计数在内存，需要先改造成 Redis backend。
- **多用户隔离**：当前所有 API 共用一份 config / projects 状态，没有 per-user 数据隔离——这也意味着方案 A 的 Access 策略哪怕区分了多个邮箱，进入应用后看到的也是同一份数据。
- **审计日志**：`app.log` 只记请求与异常，没有可信审计链。
- **彻底隐藏域名存在**：TLS 证书透明日志一签就公开，DNS 记录也会被被动收集。本手册的策略是"被发现也进不来"，而不是"不被发现"。

如果你的部署超出单机自用范围，建议把这些放在重做架构时一起处理，而不是给当前版本打补丁。
