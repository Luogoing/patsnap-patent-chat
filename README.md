# Patsnap Patent Chat

一个本地运行的基础专利检索对话接口，后端代理调用智慧芽 / Patsnap Eureka Open Platform API，前端只负责对话，不暴露 API Key。

## 功能

- 对话式输入检索需求
- 自动生成基础 Patsnap 检索式
- 调用 Patsnap 专利检索结果接口和计数接口
- 返回命中数量、检索式、原始结果摘要和 Google Patents 辅助链接
- 支持 `raw:` 前缀直接输入 Patsnap 专家检索式

## 安全

真实密钥只放在本地 `.env.local`，仓库只提交 `.env.example`。

`.gitignore` 已忽略：

```text
.env
.env.*
```

## 初始化

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

创建本地密钥文件：

```powershell
.\scripts\set_patsnap_key.ps1
```

运行中的服务会自动重新读取 `.env.local`，通常不需要重启。

运行：

```powershell
.\scripts\run.ps1
```

浏览器打开：

```text
http://127.0.0.1:8787
```

## 查询示例

普通自然语言：

```text
检索氢气瓶复合材料缠绕和泄压阀相关专利
```

专利号：

```text
US8674530 CN111922118A
```

直接输入 Patsnap 检索式：

```text
raw: TACD: hydrogen storage tank AND TA: composite
```

## 依据

- Eureka REST API Base URL: `https://connect.patsnap.com`
- 推荐认证方式：`Authorization: Bearer <API Key>`
- 计数接口：`/search/patent/query-search-count`
- 嵌套检索接口：`/search/patent/nested-search-patent`
