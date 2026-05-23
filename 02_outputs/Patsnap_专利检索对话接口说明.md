# 智慧芽 MCP 专利情报接口说明

日期：2026-05-24

## 当前完成状态

已在本项目中建立一期本地 Web 专利情报接口：

```text
http://127.0.0.1:8787
```

核心文件：

```text
patent_chat/app.py              FastAPI 后端和 API 路由
patent_chat/zhihuiya_mcp.py     智慧芽 MCP Streamable HTTP 客户端
patent_chat/intelligence.py     任务卡、命中归一化、排序和风险摘要规则链
static/                         本地前端页面
scripts/run.ps1                 本地启动脚本
scripts/set_zhihuiya_mcp_key.ps1 本地密钥写入脚本
```

## 密钥处理

真实智慧芽 API key 不写入仓库。

本地运行前执行：

```powershell
.\scripts\set_zhihuiya_mcp_key.ps1
```

脚本会提示粘贴 API key，并写入被 Git 忽略的 `.env.local`：

```text
ZHIHUIYA_MCP_URL=https://connect.zhihuiya.com/2b0355/logic-mcp
ZHIHUIYA_MCP_API_KEY=your_local_key_here
```

代码会在内存中把 API key 作为 MCP 连接参数使用，但不会把完整带密钥 URL 写入代码、README、Git 或日志。

## 后端接口

### `GET /api/health`

返回 MCP 配置和连通性状态，不返回密钥。

主要字段：

- `mcp.configured`
- `mcp.has_url`
- `mcp.has_api_key`
- `mcp.connectable`
- `mcp.tool_count`
- `mcp.error`

### `POST /api/intelligence`

请求：

```json
{
  "question": "查询清华大学蔡临宁作为前三发明人的专利",
  "mode": "balanced",
  "limit": 10,
  "context": ""
}
```

响应：

```text
task_card
patents / top_patents
ranking
risk_summary
evidence
next_questions
report_markdown
trace_id
```

### `POST /api/chat`

兼容旧聊天入口，内部转调 `/api/intelligence`。

## 支持的输入

自然语言：

```text
查询清华大学蔡临宁作为前三发明人的专利
```

技术方案：

```text
氢气瓶复合材料缠绕和泄压阀技术方案
```

专家检索式：

```text
raw: TACD: hydrogen storage tank AND TA: composite
```

## 错误映射

MCP 错误会统一映射为：

- 密钥缺失
- 认证失败
- 权限不足
- 工具不存在
- 请求超时
- 返回结构异常
- SDK 缺失或连接失败

所有错误响应都会包含 `trace_id`，用于本地排查。

## 当前边界

- 一期报告仅做创新情报和风险初筛，不构成法律意见。
- 排序链是规则最小版，依赖 MCP 返回字段完整度；缺少权利要求、法律状态、同族信息时会明确标注不确定性。
- 飞书/Hermes 接入作为下一阶段，当前先保证本地网页和 MCP 后端跑通。
