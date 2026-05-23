# Hermes Agent 进阶使用教程

日期：2026-05-23

适用环境：

```text
Hermes Agent v0.14.0
安装目录：C:\Users\zhang\AppData\Local\hermes
项目目录：D:\codex-new\02_projects\_documents_new_projects__20260430\New project 55
```

## 1. 先记住三种入口

Hermes 有三种常用入口：

1. 消息平台入口：飞书、微信里直接和机器人聊天。
2. 终端入口：在 PowerShell 里运行 `hermes` 或 `hermes --tui`。
3. 后台入口：`gateway` 常驻运行，负责接收飞书/微信消息。

你当前主线是消息平台入口。只要 Gateway 没跑，飞书/微信发消息就不会进 Hermes。

## 2. Windows 上推荐的命令写法

如果新终端已经刷新 PATH，可以直接用 `hermes`。为了减少路径问题，稳妥写法是先定义一个变量：

```powershell
$env:HERMES_HOME = "$env:LOCALAPPDATA\hermes"
$H = "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\hermes.exe"
```

之后本窗口里都用：

```powershell
& $H gateway status
& $H doctor
& $H model
```

## 3. 日常启动和停止

前台启动，适合测试和排错：

```powershell
$env:HERMES_HOME = "$env:LOCALAPPDATA\hermes"
$H = "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\hermes.exe"
& $H gateway run
```

这个窗口不能关。关掉后，机器人就离线。

查看状态：

```powershell
& $H gateway status
```

测试稳定后，可以安装为 Windows 登录后自启动：

```powershell
& $H gateway install
```

如果以后改了配置或升级了 Hermes，再重启 Gateway：

```powershell
& $H gateway restart
```

## 4. 飞书/微信里最常用的命令

在飞书或微信聊天里发送：

```text
/help
```

查看当前可用命令。

查看自己是谁、权限状态：

```text
/whoami
```

把当前聊天设为默认通知位置：

```text
/sethome
```

它也支持别名：

```text
/set-home
```

查看消息平台可用命令：

```text
/commands
```

当 Hermes 要执行危险命令时，会让你批准。常用回复：

```text
/approve
/approve session
/approve always
/deny
```

建议：

- 临时命令用 `/approve`。
- 同一会话内反复需要的命令用 `/approve session`。
- 不要轻易用 `/approve always`，除非你确定这条命令长期安全。

## 5. 飞书群聊怎么用

你配置的是推荐模式：群聊里只有被 @ 时才响应。

示例：

```text
@张岩松的智能助手 帮我把今天这个项目的配置步骤整理成待办清单。
```

更好的提问方式：

```text
@张岩松的智能助手 你现在作为项目助手，只基于本聊天上下文，列出 Hermes 飞书联动还缺哪些验证项。
```

群聊里尽量不要直接发 App Secret、Token、API Key。

## 6. 私聊授权和 pairing

你选择了 DM pairing approval。含义是：不是所有人私聊机器人都能直接使用。

如果新用户私聊机器人，Hermes 可能会给出一个 pairing code。管理员在本机 PowerShell 里可以查看和批准：

```powershell
& $H pairing list
& $H pairing approve feishu 配对码
```

微信则一般用：

```powershell
& $H pairing approve weixin 配对码
```

如果平台名报错，先运行：

```powershell
& $H pairing list
```

看待批准记录里显示的平台名，再按那个平台名批准。

## 7. 模型配置

如果机器人能收到消息但不回复，或者报模型/API 错，先跑：

```powershell
& $H model
```

这个命令用于选择默认模型 Provider 和模型。

检查配置状态：

```powershell
& $H config check
& $H doctor
```

如果只是临时在终端问一句：

```powershell
& $H -z "用中文一句话说明你当前能调用哪些工具"
```

## 8. 定时任务 cron

Hermes 可以定时执行任务，然后把结果发回飞书/微信 Home Chat。

先在飞书或微信目标聊天里发：

```text
/sethome
```

然后创建任务：

```powershell
& $H cron create "0 9 * * *" "每天早上九点，用中文给我一份今日待办提醒，重点关注 Hermes 项目和未完成配置。" --name "每日待办" --deliver feishu
```

常用时间表达式：

```text
30m          30 分钟后执行一次
every 2h    每 2 小时执行一次
0 9 * * *   每天 09:00
0 9 * * 1   每周一 09:00
```

管理定时任务：

```powershell
& $H cron list
& $H cron status
& $H cron run 任务ID
& $H cron pause 任务ID
& $H cron resume 任务ID
& $H cron remove 任务ID
```

如果不确定 `--deliver feishu` 是否识别，先用：

```powershell
& $H send --list
```

看当前可投递目标。

## 9. 直接发通知 send

`send` 是不经过大模型的直接推送。

列出可发送目标：

```powershell
& $H send --list
```

向默认飞书 Home Chat 发消息：

```powershell
& $H send --to feishu "Hermes 网关测试消息"
```

从文件发送：

```powershell
& $H send --to feishu --subject "日报" --file "D:\path\report.md"
```

用途：脚本运行完、仿真完成、磁盘告警、每日摘要，都可以直接推送。

## 10. Skills 进阶

查看已安装 Skills：

```powershell
& $H skills list
```

搜索 Skills：

```powershell
& $H skills search keyword
```

安装 Skill：

```powershell
& $H skills install skill-name
```

在聊天里，很多 Skill 会变成斜杠命令。可以先发：

```text
/help
```

看当前有哪些可用命令。

适合你的使用方式：

- 写材料：让 Hermes 按模板整理、改写、提纲化。
- 项目管理：让 Hermes 持续维护待办、风险点、下一步动作。
- 文件处理：给出路径，让它读取、总结、生成草稿。
- 自动提醒：结合 cron，把例行检查推送到飞书。

## 11. 会话管理

查看历史会话：

```powershell
& $H sessions list
```

交互式浏览会话：

```powershell
& $H sessions browse
```

导出会话：

```powershell
& $H sessions export
```

适合场景：某个项目聊了很多轮，后面要恢复上下文或归档证据。

## 12. Dashboard 网页管理

启动本地 Web 管理界面：

```powershell
& $H dashboard
```

默认地址一般是：

```text
http://127.0.0.1:9119
```

查看 Dashboard 状态：

```powershell
& $H dashboard --status
```

停止 Dashboard：

```powershell
& $H dashboard --stop
```

不要加 `--insecure` 暴露到局域网，里面可能涉及 API Key 和配置。

## 13. 更新和备份

升级前建议先备份：

```powershell
& $H backup --quick --label before-update
```

检查更新：

```powershell
& $H update --check
```

执行更新：

```powershell
& $H update --backup
```

更新后重跑：

```powershell
& $H doctor
& $H gateway status
```

## 14. 故障排查顺序

机器人不回消息时，按这个顺序排查：

1. Gateway 是否在跑：

```powershell
& $H gateway status
```

2. 配置是否正常：

```powershell
& $H doctor
```

3. 模型是否配置：

```powershell
& $H model
```

4. 飞书/微信登录是否过期：

```powershell
& $H gateway setup
```

微信扫码登录类配置可能会过期，过期后重新 setup 扫码。

5. 看日志：

```powershell
& $H logs
& $H logs errors
```

## 15. 推荐的下一步练习

按这个顺序练：

1. 在飞书私聊发 `/help`。
2. 在飞书私聊发 `/whoami`。
3. 在飞书私聊发 `/sethome`。
4. 问一句普通问题，确认模型回复。
5. 在群聊 @ 机器人，确认群聊触发正常。
6. 用 `send` 给飞书发一条测试消息。
7. 创建一个 30 分钟后执行的一次性 cron 测试。

一次性 cron 测试：

```powershell
& $H cron create "30m" "提醒我检查 Hermes 飞书/微信联动是否稳定。" --name "Hermes联动检查" --deliver feishu
```

如果这 7 步跑通，Hermes 就从“能聊”进入“能当工作台”的状态了。
