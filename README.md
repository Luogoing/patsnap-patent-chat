# 智慧芽 MCP 专利情报一期工具

本项目把早期 `Patsnap Patent Chat` 原型升级为智慧芽 MCP 专利情报工作台。一期主通道是智慧芽 marketplace 的「智慧芽专利搜索」MCP 服务，目标是让非专业用户用自然语言完成：

需求澄清 → 专利检索 → 相关性排序 → 风险/机会摘要 → 可复核报告。

工具只做专利情报初筛和服务记录沉淀，不输出正式法律意见，也不替代专利代理人判断。

## 当前能力

- `POST /api/intelligence`：主接口，输入自然语言问题、模式、返回条数和上下文，输出任务卡、Top 专利、排序依据、风险摘要、证据、追问和 `trace_id`。
- `POST /api/chat`：兼容旧聊天入口，内部转调 `/api/intelligence`。
- `GET /api/health`：检查本地 MCP 配置、远程连通性和工具数量，不返回密钥。
- 本地前端：技术方案输入、检索模式、结果报告、风险摘要和证据展示。
- 文档产出：一期路线图、服务记录模板、贡献规则和 GitHub Issue 模板。

## 本地运行

创建虚拟环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

配置智慧芽 MCP 密钥：

```powershell
.\scripts\set_zhihuiya_mcp_key.ps1
```

这会写入本地 `.env.local`：

```text
ZHIHUIYA_MCP_URL=https://connect.zhihuiya.com/2b0355/logic-mcp
ZHIHUIYA_MCP_API_KEY=your_local_key_here
```

启动服务：

```powershell
.\scripts\run.ps1
```

浏览器打开：

```text
http://127.0.0.1:8787
```

## API 示例

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8787/api/intelligence `
  -ContentType 'application/json' `
  -Body (@{
    question = '查询清华大学蔡临宁作为前三发明人的专利'
    mode = 'balanced'
    limit = 10
    context = ''
  } | ConvertTo-Json)
```

可用模式：

- `balanced`：综合检索与排序。
- `novelty`：新颖性/查新初筛。
- `infringement`：侵权或 FTO 风险初筛。
- `landscape`：技术布局观察。
- `raw`：直接把输入作为智慧芽检索式发送。

## 密钥安全

- 不要在 README、Issue、日志、截图或示例中写完整的带 `apikey` URL。
- 不要上传真实密钥、`.env`、`.env.local` 或任何包含密钥的配置文件。
- `.env.example` 只保留占位符。
- 如果密钥曾经出现在聊天、截图、提交历史、Issue 或日志中，应在智慧芽平台轮换密钥。
- 发布前运行安全扫描，确认没有真实密钥进入 Git。

## 验收场景

- “查询清华大学蔡临宁作为前三发明人的专利”返回候选、排序依据和证据。
- “氢气瓶复合材料缠绕和泄压阀技术方案”生成简版查新/风险报告。
- 至少 3 个课题组完成一次真实服务记录，并把反馈沉淀到 Issue 或服务记录模板。

## 文档产出

- [一期路线图与开源协作草案](02_outputs/Patsnap_MCP_一期路线图与开源协作草案.md)
- [专利检索对话接口说明](02_outputs/Patsnap_专利检索对话接口说明.md)

## 贡献方式

优先通过 GitHub Issue 提交：

- 用户需求/服务案例：说明真实场景、输入材料、期望输出和保密边界。
- Bug：提供复现步骤、期望结果、实际结果和环境信息。
- 贡献建议：描述希望新增的 MCP tool、文档模板、测试样例或安全规则。

提交 PR 前请确认：

- 不包含真实密钥、完整带密钥 URL、未脱敏客户材料。
- 不把临时日志、`.env.local`、本地缓存或大文件加入提交。
- 文档命令可以在 Windows PowerShell 下执行。
- 修改范围尽量小，避免把无关格式化和功能变更混在一起。
