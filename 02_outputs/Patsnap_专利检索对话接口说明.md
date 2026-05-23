# Patsnap 专利检索对话接口说明

日期：2026-05-23

## 当前完成状态

已在本项目中建立一个基础本地 Web 对话接口：

```text
http://127.0.0.1:8787
```

核心文件：

```text
patent_chat/app.py              FastAPI 后端
patent_chat/patsnap_client.py   智慧芽 API 客户端
patent_chat/query_builder.py    自然语言到 Patsnap 检索式的基础转换
patent_chat/normalizer.py       API 返回结果标准化
static/                         本地前端页面
scripts/run.ps1                 本地启动脚本
scripts/set_patsnap_key.ps1     本地密钥写入脚本
```

## 密钥处理

真实智慧芽 API key 不写入仓库。

本地运行前执行：

```powershell
.\scripts\set_patsnap_key.ps1
```

脚本会提示粘贴 API key，并写入：

```text
.env.local
```

`.env.local` 已被 `.gitignore` 忽略，不会上传 GitHub。

## 调用的智慧芽接口

依据官方文档，默认配置为：

```text
Base URL: https://connect.patsnap.com
Authorization: Bearer <API Key>
Count endpoint: /search/patent/query-search-count
Search endpoint: /search/patent/nested-search-patent
```

默认请求头：

```text
Authorization: Bearer <PATSNAP_API_KEY>
Content-Type: application/json
Accept: application/json
```

## 支持的输入

普通关键词：

```text
氢气瓶 复合材料 缠绕 泄压阀
```

会转换为：

```text
TACD: 氢气瓶 复合材料 缠绕 泄压阀
```

专利号：

```text
US8674530 CN111922118A
```

会转换为：

```text
PN:(US8674530 OR CN111922118A)
```

原始 Patsnap 检索式：

```text
raw: TACD: virtual reality AND AN: Meta
```

会直接发送：

```text
TACD: virtual reality AND AN: Meta
```

## 本次验证

已完成：

- Python 语法编译通过。
- 依赖安装通过。
- 查询式生成基础检查通过。
- FastAPI `/health` 检查通过。
- `.gitignore` 已保护 `.env*`、虚拟环境、日志和误克隆大目录。

未完成：

- 未使用真实 API key 做在线检索，因为真实密钥不应出现在命令日志或 Git 记录中。
- GitHub 上传还需要本机 GitHub CLI 登录，或提供一个已有 GitHub 仓库远端。

## 后续可增强

1. 根据智慧芽实际返回字段，细化 `patent_chat/normalizer.py`。
2. 增加申请人、IPC/CPC、日期、国家/地区过滤控件。
3. 增加导出 Excel/Markdown 报告。
4. 增加 Hermes skill 或 MCP server，让飞书里的 Hermes 直接调用该检索接口。
5. 增加查新模板：技术点、关键词、近似专利、风险等级、规避建议。
