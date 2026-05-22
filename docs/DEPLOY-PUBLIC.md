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

> **术语对齐**：本节出现的 "Cloudflare 控制台" 指 `https://dash.cloudflare.com`；"Zero Trust 控制台" 指从前者左侧 **Zero Trust** 菜单点进去后跳转到的 `https://one.dash.cloudflare.com`，两者账号同一个但侧栏不同。Tunnel 和 Access 的入口都在 **Zero Trust 控制台**。

### 准备清单（在开始之前确认你有）

- 一个已在域名注册商（阿里云/腾讯云/Namecheap/GoDaddy/Cloudflare Registrar 等）注册成功的域名，**且能登录到 NS 修改页面**。
- 一个 Cloudflare 账号（免费版即可）。**强烈建议给该账号启用 TOTP 或硬件 key 二次验证**——这个账号一旦被入侵，L1 + L2 同时失守。
- 你已经在服务器上跑起 Storia 并能通过 `curl http://127.0.0.1:7860/api/health` 拿到 `{"status":"ok"}`。

### L1：让陌生人的包到不了机器 — Cloudflare Tunnel

#### 步骤 1. 把域名托管到 Cloudflare（免费版）

1. 浏览器打开 `https://dash.cloudflare.com`，登录或注册。
2. 主页右上点 **Add a site** → 输入你的根域名 `yourdomain.com`（**不要**带子域、不要带 `https://`）→ Continue。
3. 选择 **Free** 方案 → Continue。Cloudflare 会自动扫描你现有 DNS 记录，**先确认列表里你原有的 A/MX/TXT 记录都在**——如果有缺，手动 Add record 补上，否则托管后邮件、其他子域会失联。
4. 页面顶部会显示两个 Cloudflare 指派给你的 NS 地址，形如 `xxx.ns.cloudflare.com` / `yyy.ns.cloudflare.com`。记下它们。
5. 登录你的**域名注册商**控制台（不是 Cloudflare），找到域名的 **Nameserver / DNS 服务器** 设置页：
   - 阿里云：域名控制台 → 管理 → DNS 修改
   - 腾讯云：域名注册 → 我的域名 → 管理 → 修改 DNS 服务器
   - Namecheap：Domain List → Manage → Nameservers → Custom DNS
   - GoDaddy：My Products → Domain → DNS → Nameservers → Change
6. 把 NS 改成 Cloudflare 给你的两个地址，**只填这两个，删掉原有的全部 NS**。保存。
7. 回到 Cloudflare 那个站点页面，点 **Done, check nameservers**。生效时间通常 5 分钟 ~ 24 小时，Cloudflare 检测到后会发邮件通知，站点状态变为 **Active**。

> **等待 Active 之后再继续后面步骤**。NS 没生效就跑下面的 `tunnel login` / `route dns` 会失败或落到错误的 zone。

#### 步骤 2. 在服务器上安装 cloudflared

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
  sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main" | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install -y cloudflared
cloudflared --version   # 验证安装成功，应输出形如 "cloudflared version 2024.x.x"
```

#### 步骤 3. 把 cloudflared 与你的 Cloudflare 账号绑定

```bash
cloudflared tunnel login
```

执行后终端会打印一个 `https://dash.cloudflare.com/argotunnel?...` 链接。

- **如果服务器有图形界面**：直接打开。
- **如果服务器是纯 SSH（更常见）**：把那个 URL **完整复制**到你**本地电脑**的浏览器里打开。

浏览器页面会让你：
1. 登录 Cloudflare（如果未登录）。
2. **Select a zone** 下拉选你刚托管的域名 `yourdomain.com` → **Authorize**。

授权成功后服务器终端会自动收到回调并打印类似：
```
You have successfully logged in.
If you wish to copy your credentials to a server, they have been saved to:
/home/you/.cloudflared/cert.pem
```

> 这个 `cert.pem` 是你账号级别的凭据，只用于"创建 Tunnel"这一步，**不要外传**。

#### 步骤 4. 创建 Tunnel 并记下 UUID

```bash
cloudflared tunnel create storia
```

输出形如：
```
Tunnel credentials written to /home/you/.cloudflared/3f1e0b2c-...-abcdef.json.
Created tunnel storia with id 3f1e0b2c-aaaa-bbbb-cccc-abcdef012345
```

把那个 **UUID**（`3f1e0b2c-...`）记下来，后面的 config 文件要用。凭据 JSON 文件落在 `~/.cloudflared/<UUID>.json`，这是 Tunnel **运行时**的凭据，丢了或泄露要 `cloudflared tunnel rotate` 轮换。

#### 步骤 5. 写 Tunnel 配置

新建 `~/.cloudflared/config.yml`（把 `<UUID>` 替换成步骤 4 的 UUID，把 `you` 换成你的用户名，`storia.yourdomain.com` 换成你想用的子域）：

```yaml
tunnel: <UUID>
credentials-file: /home/you/.cloudflared/<UUID>.json

ingress:
  # 主入口：Storia
  - hostname: storia.yourdomain.com
    service: http://127.0.0.1:7860
    originRequest:
      # Storia 用 SSE 推流，这两个超时必须给足
      connectTimeout: 30s
      noTLSVerify: true
  # 必须有的 catch-all，未匹配的 hostname 一律 404
  - service: http_status:404
```

#### 步骤 6. 给 Tunnel 绑定公网域名

```bash
cloudflared tunnel route dns storia storia.yourdomain.com
```

这条命令会在 Cloudflare 上自动创建一条 **CNAME** 记录：`storia` → `<UUID>.cfargotunnel.com`，并打开"Proxied"（橙色云）。回 Cloudflare 控制台 → 你的域名 → **DNS → Records** 应能看到这条记录。

> 如果报 `failed to add route: code: 1003`，通常是 NS 还没生效，或者 zone 选错了。等 `dig NS yourdomain.com` 返回 Cloudflare 的 NS 后再试。

#### 步骤 7. 前台冒烟测试

先**别**装 systemd 服务，先前台跑一次确认能通：

```bash
cloudflared tunnel --config ~/.cloudflared/config.yml run storia
```

正常输出会有 `Registered tunnel connection`，且至少能看到 2 ~ 4 条 `connIndex=...` 表示和 Cloudflare 多个边缘节点都建好了连接。

**此时换到本地电脑浏览器**，打开 `https://storia.yourdomain.com`——应该能直接看到 Storia 的 UI（**还没配 Access，所以现在全世界都能进**，这就是为什么下一节 L2 必须立刻做）。

确认 OK 后，Ctrl+C 停掉前台进程。

#### 步骤 8. 把 cloudflared 装成 systemd 服务

`cloudflared service install` 默认会找 root 的 `~/.cloudflared/`，但你的 config 和 credentials 在 `/home/you/.cloudflared/` 下。最稳妥的做法是先把它们拷到系统目录：

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/config.yml          /etc/cloudflared/config.yml
sudo cp ~/.cloudflared/<UUID>.json         /etc/cloudflared/<UUID>.json
# 同步修改 config.yml 里的 credentials-file 路径
sudo sed -i 's|/home/you/.cloudflared/|/etc/cloudflared/|' /etc/cloudflared/config.yml
sudo chmod 600 /etc/cloudflared/<UUID>.json

sudo cloudflared --config /etc/cloudflared/config.yml service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared          # 应看到 active (running) + 4 个边缘连接
journalctl -u cloudflared -f               # 实时日志，Ctrl+C 退出
```

#### 步骤 9. 关掉服务器的 80/443，仅留 SSH

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status verbose                    # 确认 80/443 不在放行列表里
```

**这一步做完，从公网视角你的机器除了 SSH 没有任何 TCP 端口可见。** 用 `https://www.shodan.io/host/<你的IP>` 或者本地另一台机器 `nmap -Pn -p 80,443,7860 <你的IP>` 验证——应该全是 `filtered` 或 `closed`。

### L2：阻止陌生人通过 Cloudflare 边缘 — Access 策略

L1 完成后，**任何人输入 `https://storia.yourdomain.com` 都能直接看到 UI**。现在用 Access 在边缘加一道身份验证。

#### 步骤 10. 首次进入 Zero Trust 并选 Team 名

1. Cloudflare 控制台左侧菜单点 **Zero Trust**（蓝色盾牌图标）。首次进入会让你选一个 **Team name**，这个名字会变成 `<team>.cloudflareaccess.com`——以后所有 Access 登录页都从这里弹。**随便填一个你能记住的英文短词**（不可改）。
2. 计划选 **Free**（最多 50 个用户，自用够用）。补一张信用卡或 PayPal——Free plan 不会扣费，但卡片是 Cloudflare 的反滥用要求。

#### 步骤 11. 配置登录身份源（One-Time PIN 最省事）

默认 **One-time PIN**（邮箱验证码）已开启，不需要额外配置。如果你想用 GitHub、Google、Microsoft 等 SSO，走：

- **Zero Trust 控制台 → Settings → Authentication → Login methods → Add new**，按页面提示填 OAuth Client ID / Secret。

本手册以最简的 One-time PIN 为例。

#### 步骤 12. 创建 Access Application

1. **Zero Trust 控制台 → Access → Applications → Add an application**。
2. 选 **Self-hosted**。
3. 配置如下字段（其余保持默认）：

   | 字段 | 填什么 |
   |---|---|
   | Application name | `Storia` |
   | Session Duration | `24 hours`（按需调） |
   | Application domain | Subdomain = `storia`，Domain 下拉选 `yourdomain.com`，Path 留空 |
   | Identity providers | 勾上 **One-time PIN**（默认已勾） |

   点 **Next**。

4. **Add policy** 页：

   | 字段 | 填什么 |
   |---|---|
   | Policy name | `me-only` |
   | Action | **Allow** |
   | Session duration | Same as application |
   | Configure rules → Include → Selector | **Emails** |
   | Value | 你的邮箱（可点 `+` 加多个） |

   点 **Next** → **Next** → **Add application**。

#### 步骤 13. 验证 Access 已生效

1. 用**无痕窗口**打开 `https://storia.yourdomain.com`。
2. 应该立刻被重定向到 `<team>.cloudflareaccess.com` 的登录页，要求输入邮箱。
3. 输入步骤 12 配置的邮箱 → 收到 6 位验证码 → 输入 → 进入 Storia UI。
4. **再换一个不在白名单里的邮箱试一次**——应停在登录页提示 `That account does not have access`，并且**永远进不到 Storia**。

**做完这一步，没通过 Access 验证的请求在 Cloudflare 边缘就被拦掉，根本不会进入 Tunnel，更不会到你的进程。**

> **为什么 A 方案不用 Token？** 身份验证已经被 Cloudflare Access 全权接管，再加 Token 反而让浏览器要多管理一份凭据。如果你想要"双保险"也不是不行，但收益很小、复杂度更高。

#### 步骤 14（可选，强烈推荐）. 加一条 WAF 规则只允许 Access 流量

L2 已经够用，但如果有人拿到 Cloudflare 内部 Tunnel CNAME（`<UUID>.cfargotunnel.com`）直接打你的 hostname，理论上仍要绕一道 Access。再加一道 WAF Custom Rule 兜底：

1. Cloudflare 控制台（不是 Zero Trust）→ 你的域名 → **Security → WAF → Custom rules → Create rule**。
2. Rule name：`block-non-access-storia`
3. Field = `Hostname`，Operator = `equals`，Value = `storia.yourdomain.com`
4. **AND** → Field = `cf.access.authenticated`，Operator = `equals`，Value = `false`
5. Action = **Block**
6. Deploy.

这样即使有人绕过 Access 直连边缘也会被 WAF 拦。

#### Cloudflare 部分常见坑速查

| 现象 | 原因 | 处置 |
|---|---|---|
| `cloudflared tunnel login` 浏览器打开后选不到域名 | NS 还没切到 Cloudflare / zone 状态不是 Active | 等 NS 生效，`dig NS yourdomain.com` 应返回 Cloudflare 的 NS |
| `route dns` 报错 `An A, AAAA, or CNAME record with that host already exists` | DNS 已有同名记录 | Cloudflare DNS 页面删掉旧的 `storia` 记录，再跑 `route dns` |
| 浏览器访问报 `Error 1033 Argo Tunnel error` | 服务器上 cloudflared 没跑 / 没连上 | `sudo systemctl status cloudflared`、`journalctl -u cloudflared -n 100` |
| 浏览器访问报 `Error 502 Bad Gateway` | cloudflared 连上了边缘，但回源 `127.0.0.1:7860` 失败 | 检查 storia 服务：`sudo systemctl status storia`、`curl http://127.0.0.1:7860/api/health` |
| SSE 流式输出几秒就断 | `originRequest` 超时太短 | config.yml 里加 `connectTimeout: 30s` 并把 Cloudflare 仪表 → 你的域名 → **Network → WebSockets** 打开 |
| Access 登录死循环 | 浏览器 cookie 异常 / 第三方 cookie 被拦 | 清 `<team>.cloudflareaccess.com` 与你的域名的 cookie，重试 |

---

## 四、防护方案 B：nginx + Token + IP 白名单（备用）

适合不愿走 Cloudflare 的人，但配置项多更易出错，也**无法避免你的 IP 被扫描器看到**——证书签发会进 CT 日志，你的子域和 IP 一定会被发现。这条路线的核心思想是「让陌生人看得到但进不去」，靠两道闸：**网络层 IP 白名单 + 应用层 Token**。

### 准备清单（在开始之前确认你有）

- 一个解析到你服务器公网 IP 的子域 `storia.yourdomain.com`：登录你的 DNS 服务商，加一条 **A 记录**，Name = `storia`，Value = `<你的服务器公网 IP>`，TTL 5 分钟。`dig +short storia.yourdomain.com` 能返回该 IP 后再继续。
- 服务器已能跑 Storia，`curl http://127.0.0.1:7860/api/health` 返回 `{"status":"ok"}`。
- **强烈建议但非必须**：一个固定的家庭/办公网络出口 IP（用来做 nginx `allow` 白名单）。`curl ifconfig.me` 在你常用的网络下测一下；如果是动态 IP，可改用 [DDNS + nginx geo 模块] 或退回纯 Token 模式，但**风险显著上升**。

### L1：让陌生人到不了进程 — nginx 反代 + 防火墙 + IP 白名单

#### 步骤 1. 安装 nginx 与 certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
nginx -v && certbot --version       # 确认安装成功
```

#### 步骤 2. 防火墙：只放行 SSH 与 80/443

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'                # 自动放行 80 + 443
sudo ufw enable
sudo ufw status verbose                    # 确认 7860 不在放行列表里
```

> Storia 自身只听 `127.0.0.1:7860`（systemd 单元里 `--host 127.0.0.1`），所以即使你没装 ufw，公网也连不到 7860。但**仍然要装 ufw**——它是兜底，且能拦掉其他你可能临时起的端口（debug 服务、容器映射等）。

#### 步骤 3. 写一份**最小** nginx 站点（先不要 SSL，让 certbot 自动加）

新建 `/etc/nginx/sites-available/storia`：

```nginx
server {
    listen 80;
    server_name storia.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:7860;
    }
}
```

启用并 reload：

```bash
sudo ln -sf /etc/nginx/sites-available/storia /etc/nginx/sites-enabled/storia
sudo rm -f /etc/nginx/sites-enabled/default      # 防止默认站点抢 80 端口
sudo nginx -t && sudo systemctl reload nginx
```

**冒烟测试**：在**本地电脑**浏览器打开 `http://storia.yourdomain.com`，应该能看到 Storia UI（**此时还没 SSL，也还没鉴权，全公网都能进**，下面立刻补）。

> 如果浏览器报 `502 Bad Gateway`：检查 Storia 在跑 (`sudo systemctl status storia`) 且监听 `127.0.0.1:7860`。
> 如果报 `404 nginx` 或连不上：检查 DNS 是否生效 (`dig +short storia.yourdomain.com`) 与 ufw 是否放行了 80。

#### 步骤 4. 用 certbot 自动签 Let's Encrypt 证书

```bash
sudo certbot --nginx -d storia.yourdomain.com
```

按提示输入邮箱（用于到期通知）、同意条款。最后一项选 **2: Redirect**——certbot 会自动加一段 `listen 443 ssl` server 块并把 80 → 443 强跳。

完成后再次访问 `https://storia.yourdomain.com` 应能看到 UI 且地址栏挂着锁。证书有效期 90 天，certbot 装了 systemd timer 自动续期：

```bash
systemctl list-timers | grep certbot       # 应看到 certbot.timer
sudo certbot renew --dry-run               # 模拟续期，确认能跑通
```

#### 步骤 5. 强化 nginx：SSE 长连接 + 上传上限 + IP 白名单

certbot 改完之后，重新打开 `/etc/nginx/sites-available/storia`，把 443 server 块替换成下面这版（**保留 certbot 已经写好的 `ssl_certificate` 两行**）：

```nginx
server {
    listen 443 ssl http2;
    server_name storia.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/storia.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/storia.yourdomain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # ★ L1 关键：固定 IP 白名单（强烈建议，能配就配）
    # 取消下面三行的注释，并把 1.2.3.4 换成你 curl ifconfig.me 拿到的 IP
    # allow 1.2.3.4;        # 你家宽带固定 IP / 公司出口
    # allow 5.6.7.8;        # 可多写几条
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

    # 知识库导入有大文件
    client_max_body_size 64m;

    location / {
        proxy_pass http://127.0.0.1:7860;
    }
}

server {
    listen 80;
    server_name storia.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

**验证 IP 白名单**：
- 在白名单 IP 上访问 `https://storia.yourdomain.com` → 应正常打开。
- 拿手机切到 **4G/5G**（出口 IP 不在白名单）访问同一 URL → 应返回 `403 Forbidden`。

> **没有 IP 白名单的 B 方案有多脆？** 任何人输入 `https://storia.yourdomain.com` 就能打开登录界面。Token 是你**唯一**的身份验证。如果浏览器 localStorage 在公共电脑被复制、或前端有个未发现的 XSS，Token 就裸奔。**所以这一步几乎不可省。** 真的没固定 IP，至少考虑 DDNS + nginx 动态白名单脚本。

### L2：阻止陌生人调用接口 — API Token

L1 阻断了陌生 IP 的网络流量；L2 是给"通过 IP 白名单但没你授权"的人再加一道（比如你公司其他同事和你共用出口 IP）。

#### 步骤 6. 生成强随机 Token

```bash
openssl rand -hex 32
# 输出 64 个十六进制字符的字符串，全选复制
```

#### 步骤 7. 写到 `.env` 并重启

编辑 `/opt/storia/.env`，把方案 A 时注释掉的两行取消注释并填好：

```bash
NOVELWRITER_HOST=127.0.0.1
NOVELWRITER_PORT=7860
NOVELWRITER_API_TOKEN=<步骤 6 拿到的 64 位字符串>
NOVELWRITER_CORS_ORIGINS=https://storia.yourdomain.com
```

```bash
sudo chmod 600 /opt/storia/.env
sudo systemctl restart storia
journalctl -u storia -n 20                 # 确认没 ERROR、监听 127.0.0.1:7860
```

> ⚠️ **`NOVELWRITER_API_TOKEN` 与 `NOVELWRITER_CORS_ORIGINS=*` 同时设置时，进程会拒绝启动** —— 既要鉴权又要任意 Origin 是矛盾配置。报错信息会在 `journalctl -u storia` 里指出。

#### 步骤 8. 验证 Token 已生效

未带 Token 直接 curl：

```bash
curl -i https://storia.yourdomain.com/api/health
# 期望 401 Unauthorized（如果你在白名单 IP 上跑；否则会先被 nginx 403）
```

带 Token：

```bash
curl -i -H "X-NovelWriter-Token: <你的 token>" https://storia.yourdomain.com/api/health
# 期望 200 OK + {"status":"ok"}
```

#### 步骤 9. 让浏览器 UI 带上 Token

浏览器打开 `https://storia.yourdomain.com`（此时 UI 会报 401，正常）。F12 打开 DevTools → Console，粘贴执行：

```js
localStorage.setItem('novelwriter_api_token', '<你的 token>')
```

刷新页面，UI 应正常加载。Token 落在浏览器 localStorage，下次直接访问无需再设。

> **Token 泄露怎么办？** `openssl rand -hex 32` 重新生成 → 改 `.env` → `sudo systemctl restart storia`。旧 Token 立刻失效，所有浏览器需要重新 `localStorage.setItem`。

#### 步骤 10（可选，强烈推荐）. fail2ban 拦暴力扫描

即使有 IP 白名单 + Token，扫描器仍会消耗 nginx 资源。装 fail2ban 对 403/401 频繁的 IP 自动封 IP：

```bash
sudo apt install -y fail2ban
sudo tee /etc/fail2ban/jail.d/nginx-storia.conf > /dev/null <<'EOF'
[nginx-storia]
enabled  = true
filter   = nginx-http-auth
port     = http,https
logpath  = /var/log/nginx/error.log
maxretry = 5
findtime = 600
bantime  = 3600
EOF
sudo systemctl restart fail2ban
sudo fail2ban-client status nginx-storia
```

#### nginx + Token 部分常见坑速查

| 现象 | 原因 | 处置 |
|---|---|---|
| `certbot --nginx` 报 `Connection refused` 或 `DNS problem` | DNS 未生效 / 80 端口未放行 | `dig +short storia.yourdomain.com` 确认指向服务器；`sudo ufw status` 确认放行 'Nginx Full' |
| `502 Bad Gateway` | Storia 没跑或没监听 127.0.0.1:7860 | `sudo systemctl status storia`、`ss -tlnp \| grep 7860` |
| 在白名单 IP 上也返回 `403` | nginx 没 reload，或 `allow` 写的 IP 不对 | `curl ifconfig.me` 再核对一次出口 IP；`sudo nginx -t && sudo systemctl reload nginx` |
| API 全返回 `401` 但 Token 是对的 | header 名写错（应是 `X-NovelWriter-Token`，区分横杠），或 localStorage key 拼错（应是 `novelwriter_api_token`） | 在 DevTools → Network 看实际请求头；清掉 localStorage 重设 |
| 进程启动失败，journal 里报 `CORS_ORIGINS=\* with API_TOKEN` | `.env` 里 CORS 配了 `*` 又开了 Token | 把 `NOVELWRITER_CORS_ORIGINS` 改成你的具体域名 |
| SSE 流式输出几秒就断 | nginx `proxy_read_timeout` 太短 / `proxy_buffering` 没关 | 检查 443 server 块里 `proxy_read_timeout 3600s;` 与 `proxy_buffering off;` 都在 |
| Let's Encrypt 证书续期失败 | 80 端口被关 / DNS 改过指向 | `sudo certbot renew --dry-run` 重现；保持 80 在 ufw 放行（80 用于 HTTP-01 challenge） |

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
