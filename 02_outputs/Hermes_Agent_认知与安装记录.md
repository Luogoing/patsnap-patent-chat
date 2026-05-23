# Hermes Agent 认知与安装记录

日期：2026-05-23

## 1. 本项目中的 Hermes 是什么

这里的 Hermes 指 `NousResearch/hermes-agent`，不是 HARMES 数据集。

Hermes Agent 是一个可自托管的 AI Agent，核心特点是：

- 支持 CLI、本地工具调用、浏览器工具、文件工具、记忆、Skills、定时任务和消息网关。
- 支持多种模型 Provider，可通过 `hermes model` 或 `hermes setup` 配置。
- 支持消息平台 Gateway，飞书/Lark 是其中一个官方支持平台。
- 飞书联动后，可以在飞书私聊或群聊中与 Hermes 对话；群聊默认需要 @ 机器人。

主要官方来源：

- GitHub: https://github.com/NousResearch/hermes-agent
- 飞书集成文档: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/messaging/feishu.md
- 飞书集成概览: https://hermes-agent.ai/integrations/feishu

## 2. 本机安装结果

安装方式：官方 Windows PowerShell 安装脚本。

安装命令：

```powershell
iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
```

安装位置：

```text
C:\Users\zhang\AppData\Local\hermes
```

核心文件：

```text
C:\Users\zhang\AppData\Local\hermes\hermes-agent\
C:\Users\zhang\AppData\Local\hermes\config.yaml
C:\Users\zhang\AppData\Local\hermes\.env
C:\Users\zhang\AppData\Local\hermes\skills\
C:\Users\zhang\AppData\Local\hermes\logs\
```

Hermes 命令路径：

```text
C:\Users\zhang\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe
```

安装器已把下面路径加入用户 PATH，但需要重启终端后普通 `hermes` 命令才会直接生效：

```text
C:\Users\zhang\AppData\Local\hermes\hermes-agent\venv\Scripts
```

版本验证：

```text
Hermes Agent v0.14.0 (2026.5.16)
Python: 3.11.15
OpenAI SDK: 2.24.0
```

## 3. 已补装的飞书依赖

Hermes 的基础安装没有自动带上飞书可选依赖，因此已补装：

```text
lark-oapi==1.5.3
qrcode==7.4.2
pycryptodome==3.23.0
requests-toolbelt==1.0.0
```

验证结果：

```text
feishu extras ok
```

`hermes doctor` 中飞书相关工具已经可用：

```text
feishu_doc
feishu_drive
```

## 4. 当前健康检查结论

已通过：

- Python 3.11.15 venv 正常。
- Hermes 主程序可启动。
- 配置文件和 `.env` 存在。
- Git、ripgrep、Node.js、Playwright Chromium、浏览器工具依赖正常。
- 飞书文档和飞书云盘工具可用。
- 未发现 active security advisories。

仍未配置/未启动：

- Gateway 尚未运行。
- 尚未完成飞书 App 凭据配置。
- 尚未在 Hermes 中完成模型 Provider 登录或 API Key 配置。
- 可选的 Telegram、Discord、Docker、外部 Web 搜索、图像/视频等工具未配置，不影响飞书主线。

Gateway 状态：

```text
Gateway is not running
```

## 5. 飞书联动最短路径

推荐使用 WebSocket 模式，因为本机不需要公网回调地址。

### 方案 A：扫码创建飞书应用

运行：

```powershell
$env:HERMES_HOME="$env:LOCALAPPDATA\hermes"
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\hermes.exe" gateway setup
```

在交互菜单里选择 Feishu / Lark，用飞书手机端扫码。Hermes 会尝试自动创建应用并保存凭据。

### 方案 B：手动创建飞书应用

1. 打开飞书开放平台：

```text
https://open.feishu.cn/
```

2. 创建企业自建应用。
3. 在「凭证与基础信息」复制：

```text
App ID
App Secret
```

4. 启用 Bot 能力。
5. 运行：

```powershell
$env:HERMES_HOME="$env:LOCALAPPDATA\hermes"
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\hermes.exe" gateway setup
```

6. 选择 Feishu / Lark，按提示填入 App ID / App Secret。

## 6. 手动配置项参考

这些变量写入：

```text
C:\Users\zhang\AppData\Local\hermes\.env
```

最小配置：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=secret_xxx
FEISHU_DOMAIN=feishu
FEISHU_CONNECTION_MODE=websocket
```

推荐再加访问控制：

```bash
FEISHU_ALLOWED_USERS=ou_xxx,ou_yyy
FEISHU_GROUP_POLICY=allowlist
```

如果要把某个飞书群作为定时任务/通知的默认投递位置：

```bash
FEISHU_HOME_CHANNEL=oc_xxx
FEISHU_HOME_CHANNEL_NAME=Home
```

Webhook 模式才需要重点配置：

```bash
FEISHU_CONNECTION_MODE=webhook
FEISHU_ENCRYPT_KEY=your-encrypt-key
FEISHU_VERIFICATION_TOKEN=your-verification-token
```

## 7. 启动 Gateway

前台启动，便于首次排错：

```powershell
$env:HERMES_HOME="$env:LOCALAPPDATA\hermes"
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\hermes.exe" gateway run
```

状态检查：

```powershell
$env:HERMES_HOME="$env:LOCALAPPDATA\hermes"
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\hermes.exe" gateway status
```

后续如果确认稳定，可安装为 Windows 登录后自启动任务：

```powershell
$env:HERMES_HOME="$env:LOCALAPPDATA\hermes"
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\hermes.exe" gateway install
```

## 8. 使用行为要点

- 飞书私聊：默认每条消息都会回复。
- 飞书群聊：默认只有 @ 机器人时才回复。
- 群聊会话：默认 `group_sessions_per_user: true`，即同一个群里按用户隔离上下文。
- 生产使用建议配置 `FEISHU_ALLOWED_USERS`，避免任何能接触机器人者都能使用 Hermes。
- App Secret 不能发在群里，也不要写进项目公开文件。

## 9. 下一步待办

1. 运行 `hermes setup` 或 `hermes model` 配置模型 Provider。
2. 运行 `hermes gateway setup` 配置飞书应用。
3. 启动 `hermes gateway run`，在飞书里私聊机器人验证。
4. 在目标飞书群中 @ 机器人验证群聊响应。
5. 用 `/set-home` 将某个飞书聊天设为 Home Channel，便于接收定时任务结果。

## 10. 备注

本次开始时曾误按 `HARMES` 数据集方向创建了：

```text
D:\codex-new\02_projects\_documents_new_projects__20260430\New project 55\00_source\HARMES
```

根据项目文件安全规则，未擅自删除。若确认无用，后续可再清理。
