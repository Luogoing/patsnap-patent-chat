from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, Settings, get_settings
from .intelligence import (
    PatentHit,
    RiskSummary,
    TaskCard,
    build_next_questions,
    build_risk_summary,
    build_task_card,
    normalize_mcp_hits,
    rank_patents,
)
from .normalizer import google_patents_url
from .zhihuiya_mcp import ZhihuiyaMCPClient, clean_mcp_url_and_key, redact_secret


STATIC_DIR = ROOT / "static"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = 0


class ChatResponse(BaseModel):
    ok: bool
    answer: str
    query_text: str
    query_mode: str
    total: int | None = None
    google_patents_url: str
    patents: list[dict[str, Any]] = []
    raw: dict[str, Any] = {}
    error: str | None = None


class IntelligenceRequest(BaseModel):
    question: str = Field(min_length=1)
    mode: str = "balanced"
    limit: int = Field(default=10, ge=1, le=50)
    context: str = ""


class LocalConfigRequest(BaseModel):
    zhihuiya_mcp_url: str = ""
    zhihuiya_mcp_api_key: str = ""
    zhihuiya_novelty_mcp_url: str = ""
    zhihuiya_novelty_mcp_api_key: str = ""


class SelfTestRequest(BaseModel):
    cases: list[str] = Field(default_factory=lambda: ["tsinghua", "raw"])
    limit: int = Field(default=3, ge=1, le=10)


app = FastAPI(title="Zhihuiya MCP Patent Intelligence", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    return await api_health()


@app.get("/api/health")
async def api_health() -> dict[str, Any]:
    settings = get_settings()
    channels = {}
    for channel in _configured_clients(settings):
        remote = await channel["client"].health()
        data = remote.get("data") or {}
        channels[channel["name"]] = {
            "configured": bool(channel["client"].base_url and channel["client"].api_key),
            "has_url": bool(channel["client"].base_url),
            "has_api_key": bool(channel["client"].api_key),
            "base_url": channel["client"].base_url,
            "connectable": bool(remote.get("ok")),
            "tool_count": data.get("tool_count", 0),
            "error": remote.get("error"),
        }

    primary = channels.get("patent_search", {})
    ok = any(item.get("connectable") for item in channels.values())

    return {
        "ok": ok,
        "service": "zhihuiya-mcp-patent-intelligence",
        "mcp": primary,
        "channels": channels,
        "legacy_rest_configured": bool(settings.patsnap_api_key),
    }


@app.get("/api/config")
async def api_config() -> dict[str, Any]:
    settings = get_settings()
    return _public_config(settings)


@app.post("/api/config")
async def save_local_config(request: LocalConfigRequest) -> dict[str, Any]:
    settings = get_settings()
    saved = _save_local_config(request, settings)
    health_payload = await api_health()
    return {
        "ok": True,
        "saved": saved,
        "config": _public_config(get_settings()),
        "health": health_payload,
    }


@app.post("/api/intelligence")
async def intelligence(request: IntelligenceRequest) -> dict[str, Any]:
    return await run_intelligence(
        question=request.question,
        mode=request.mode,
        limit=request.limit,
        context=request.context,
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    report = await run_intelligence(
        question=request.message,
        mode="balanced",
        limit=request.limit,
        context="",
    )
    query_text = str(report.get("query") or request.message)
    error = report.get("error") if not report.get("ok") else None
    return ChatResponse(
        ok=bool(report.get("ok")),
        answer=_legacy_answer(report),
        query_text=query_text,
        query_mode="zhihuiya_mcp",
        total=len(report.get("patents") or []),
        google_patents_url=google_patents_url(query_text),
        patents=report.get("patents") or [],
        raw={"trace_id": report.get("trace_id"), "tool": report.get("tool")},
        error=str(error) if error else None,
    )


@app.post("/api/self-test")
async def self_test(request: SelfTestRequest) -> dict[str, Any]:
    trace_id = uuid4().hex
    health_payload = await api_health()
    results = []
    for case in request.cases[:5]:
        payload = _self_test_case(case, request.limit)
        report = await run_intelligence(**payload)
        patents = report.get("patents") or []
        results.append(
            {
                "case": case,
                "ok": bool(report.get("ok")) and bool(patents),
                "patents": len(patents),
                "evidence": len(report.get("evidence") or []),
                "trace_id": report.get("trace_id", ""),
                "error": report.get("error", ""),
            }
        )

    return {
        "ok": bool(health_payload.get("ok")) and all(item["ok"] for item in results),
        "trace_id": trace_id,
        "health": health_payload,
        "results": results,
    }


async def run_intelligence(question: str, mode: str = "balanced", limit: int = 10, context: str = "") -> dict[str, Any]:
    trace_id = uuid4().hex
    safe_limit = _clamp_limit(limit)
    task_card = build_task_card(question=question, context=context, mode=mode)
    query = _build_mcp_query(task_card)

    settings = get_settings()
    primary = _client_for_mode(settings, task_card.mode)
    mcp_response = await primary.search(query=query, limit=safe_limit)
    selected_client = primary
    if _should_fallback_to_novelty(mcp_response, settings, task_card.mode):
        fallback = _novelty_client(settings)
        mcp_response = await fallback.search(query=query, limit=safe_limit)
        selected_client = fallback
    elif _should_fallback_to_patent_search(mcp_response, settings, selected_client.channel):
        fallback = _patent_search_client(settings)
        mcp_response = await fallback.search(query=query, limit=safe_limit)
        selected_client = fallback

    if not mcp_response.get("ok"):
        risk_summary = build_risk_summary(task_card, [])
        return _make_response(
            ok=False,
            trace_id=trace_id,
            task_card=task_card,
            query=query,
            patents=[],
            risk_summary=risk_summary,
            tool=selected_client.channel,
            error=mcp_response.get("error") or {"message": "智慧芽 MCP 调用失败。"},
        )

    data = mcp_response.get("data") or {}
    raw_payload = data.get("raw") or {"items": data.get("items") or []}
    hits = normalize_mcp_hits(raw_payload)
    if not hits and data.get("items"):
        hits = normalize_mcp_hits({"items": data["items"]})

    ranked = rank_patents(task_card, hits, limit=safe_limit)
    risk_summary = build_risk_summary(task_card, ranked)
    return _make_response(
        ok=True,
        trace_id=trace_id,
        task_card=task_card,
        query=query,
        patents=ranked,
        risk_summary=risk_summary,
        tool=data.get("tool", ""),
        mcp_count=len(hits),
        channel=data.get("channel", selected_client.channel),
    )


def _make_response(
    *,
    ok: bool,
    trace_id: str,
    task_card: TaskCard,
    query: str,
    patents: list[PatentHit],
    risk_summary: RiskSummary,
    tool: str = "",
    channel: str = "",
    mcp_count: int = 0,
    error: Any = None,
) -> dict[str, Any]:
    public_patents = [_patent_to_public_dict(hit) for hit in patents]
    evidence = [item for hit in patents for item in hit.evidence]
    similarities = _flatten_points(patents, "similarity_points")
    differences = _flatten_points(patents, "difference_points")
    next_questions = build_next_questions(task_card, patents)
    error_payload = redact_secret(error) if error else None

    response = {
        "ok": ok,
        "trace_id": trace_id,
        "task_card": _to_jsonable(task_card),
        "query": query,
        "search_query": query,
        "mode": task_card.mode,
        "channel": channel or tool,
        "tool": tool,
        "mcp_count": mcp_count,
        "patents": public_patents,
        "top_patents": public_patents,
        "ranking": _build_ranking(public_patents),
        "risk_summary": _to_jsonable(risk_summary),
        "evidence": [_to_jsonable(item) for item in evidence],
        "similarities": similarities,
        "differences": differences,
        "next_questions": next_questions,
        "report_markdown": _build_markdown_report(task_card, public_patents, risk_summary, next_questions),
    }
    if error_payload:
        message = _error_message(error_payload)
        response["error"] = message
        response["error_detail"] = error_payload
        if isinstance(error_payload, dict):
            response["error_code"] = error_payload.get("code", "")
    return response


def _configured_clients(settings: Settings) -> list[dict[str, Any]]:
    return [
        {"name": "patent_search", "client": _patent_search_client(settings)},
        {"name": "novelty_search", "client": _novelty_client(settings)},
    ]


def _patent_search_client(settings: Settings) -> ZhihuiyaMCPClient:
    return ZhihuiyaMCPClient(settings, channel="patent_search")


def _novelty_client(settings: Settings) -> ZhihuiyaMCPClient:
    api_key = settings.zhihuiya_novelty_mcp_api_key or settings.zhihuiya_mcp_api_key
    return ZhihuiyaMCPClient(
        settings,
        base_url=settings.zhihuiya_novelty_mcp_url,
        api_key=api_key,
        channel="novelty_search",
    )


def _client_for_mode(settings: Settings, mode: str) -> ZhihuiyaMCPClient:
    if (mode or "").lower() in {"novelty", "infringement", "risk"}:
        return _novelty_client(settings)
    return _patent_search_client(settings)


def _should_fallback_to_novelty(response: dict[str, Any], settings: Settings, mode: str) -> bool:
    if response.get("ok"):
        return False
    if (mode or "").lower() in {"novelty", "infringement", "risk"}:
        return False
    error = response.get("error") or {}
    if error.get("code") not in {"permission_denied", "tool_not_found", "timeout", "invalid_response", "connection_failed"}:
        return False
    novelty_key = settings.zhihuiya_novelty_mcp_api_key or settings.zhihuiya_mcp_api_key
    return bool(settings.zhihuiya_novelty_mcp_url and novelty_key)


def _should_fallback_to_patent_search(response: dict[str, Any], settings: Settings, channel: str) -> bool:
    if response.get("ok"):
        return False
    if channel == "patent_search":
        return False
    error = response.get("error") or {}
    if error.get("code") not in {"permission_denied", "tool_not_found", "timeout", "invalid_response", "connection_failed"}:
        return False
    return bool(settings.zhihuiya_mcp_url and settings.zhihuiya_mcp_api_key)


def _build_mcp_query(task_card: TaskCard) -> str:
    question = task_card.question.strip()
    if question.lower().startswith("raw:"):
        return question[4:].strip()
    if task_card.mode == "raw":
        return question
    if _is_identity_lookup_task(task_card) and task_card.key_terms:
        return " ".join(task_card.key_terms)

    parts = [question]
    if task_card.context:
        parts.append(f"补充上下文：{task_card.context}")
    if task_card.key_terms:
        parts.append("关键词：" + " ".join(task_card.key_terms[:12]))
    if task_card.intents:
        parts.append("任务意图：" + " ".join(task_card.intents))
    return "\n".join(part for part in parts if part)


def _is_identity_lookup_task(task_card: TaskCard) -> bool:
    intents = set(task_card.intents)
    has_identity_intent = bool(intents & {"inventor", "applicant"})
    has_technical_intent = bool(intents & {"technical_solution", "risk", "novelty_search", "infringement", "novelty"})
    return has_identity_intent and not has_technical_intent


def _patent_to_public_dict(hit: PatentHit) -> dict[str, Any]:
    return {
        "number": hit.number,
        "patent_number": hit.number,
        "publication_number": hit.number,
        "title": hit.title,
        "abstract": hit.abstract,
        "applicants": list(hit.applicants),
        "applicant": "；".join(hit.applicants),
        "inventors": list(hit.inventors),
        "inventor": "；".join(hit.inventors),
        "claims": hit.claims,
        "publication_date": hit.publication_date,
        "application_date": hit.application_date,
        "legal_status": hit.legal_status,
        "patent_id": hit.patent_id,
        "url": hit.url,
        "score": hit.score,
        "similarity_points": list(hit.similarity_points),
        "difference_points": list(hit.difference_points),
        "evidence": [_to_jsonable(item) for item in hit.evidence],
    }


def _build_ranking(public_patents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranking = []
    for index, patent in enumerate(public_patents, start=1):
        ranking.append(
            {
                "rank": index,
                "number": patent.get("number", ""),
                "title": patent.get("title", ""),
                "score": patent.get("score", 0),
                "basis": patent.get("similarity_points", [])[:3],
            }
        )
    return ranking


def _flatten_points(patents: list[PatentHit], attr: str) -> list[str]:
    points: list[str] = []
    for hit in patents[:5]:
        label = hit.number or hit.title or "未编号专利"
        for point in getattr(hit, attr):
            points.append(f"{label}: {point}")
    return points[:12]


def _build_markdown_report(
    task_card: TaskCard,
    patents: list[dict[str, Any]],
    risk_summary: RiskSummary,
    next_questions: list[str],
) -> str:
    lines = [
        "# 专利情报初筛报告",
        "",
        f"- 问题：{task_card.question}",
        f"- 模式：{task_card.mode}",
        f"- 风险等级：{risk_summary.level}",
        f"- 风险摘要：{risk_summary.summary}",
        f"- 不确定性：{risk_summary.uncertainty}",
        "",
        "## Top 专利",
    ]
    if patents:
        for item in patents[:10]:
            label = item.get("number") or "未编号"
            title = item.get("title") or "未命名"
            lines.append(f"- {label} | {title} | 相关度 {item.get('score', 0)}")
    else:
        lines.append("- 暂无可复核专利命中。")
    lines.extend(["", "## 下一步追问"])
    lines.extend(f"- {item}" for item in next_questions)
    lines.extend(["", risk_summary.disclaimer])
    return "\n".join(lines)


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _to_jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _error_message(error: Any) -> str:
    if isinstance(error, dict):
        return str(error.get("message") or error.get("detail") or "智慧芽 MCP 调用失败。")
    return str(error or "智慧芽 MCP 调用失败。")


def _legacy_answer(report: dict[str, Any]) -> str:
    if not report.get("ok"):
        return f"检索失败：{report.get('error') or '智慧芽 MCP 调用失败。'}"
    risk = report.get("risk_summary") or {}
    patents = report.get("patents") or []
    lines = [
        "已通过智慧芽 MCP 完成专利情报初筛。",
        f"检索式/问题：{report.get('query')}",
        f"返回 Top {len(patents)} 件候选。",
    ]
    if isinstance(risk, dict) and risk.get("summary"):
        lines.append(f"风险摘要：{risk['summary']}")
    return "\n".join(lines)


def _clamp_limit(limit: int) -> int:
    return max(1, min(int(limit or 10), 50))


def _public_config(settings: Settings) -> dict[str, Any]:
    return {
        "ok": True,
        "local_env_exists": (ROOT / ".env.local").exists(),
        "patent_search": {
            "base_url": clean_mcp_url_and_key(settings.zhihuiya_mcp_url, "")[0],
            "key_configured": bool(settings.zhihuiya_mcp_api_key),
        },
        "novelty_search": {
            "base_url": clean_mcp_url_and_key(settings.zhihuiya_novelty_mcp_url, "")[0],
            "key_configured": bool(settings.zhihuiya_novelty_mcp_api_key or settings.zhihuiya_mcp_api_key),
            "uses_main_key": not bool(settings.zhihuiya_novelty_mcp_api_key) and bool(settings.zhihuiya_mcp_api_key),
        },
        "timeout": settings.zhihuiya_mcp_timeout,
        "default_limit": settings.zhihuiya_mcp_default_limit,
    }


def _save_local_config(request: LocalConfigRequest, settings: Settings) -> dict[str, bool]:
    env_path = ROOT / ".env.local"
    current = _read_env_file(env_path)

    patent_url, patent_key = clean_mcp_url_and_key(
        request.zhihuiya_mcp_url or current.get("ZHIHUIYA_MCP_URL") or settings.zhihuiya_mcp_url,
        request.zhihuiya_mcp_api_key or current.get("ZHIHUIYA_MCP_API_KEY") or settings.zhihuiya_mcp_api_key,
    )
    novelty_url, novelty_key = clean_mcp_url_and_key(
        request.zhihuiya_novelty_mcp_url
        or current.get("ZHIHUIYA_NOVELTY_MCP_URL")
        or settings.zhihuiya_novelty_mcp_url,
        request.zhihuiya_novelty_mcp_api_key
        or current.get("ZHIHUIYA_NOVELTY_MCP_API_KEY")
        or settings.zhihuiya_novelty_mcp_api_key,
    )

    values = {
        "ZHIHUIYA_MCP_URL": patent_url,
        "ZHIHUIYA_MCP_API_KEY": patent_key,
        "ZHIHUIYA_MCP_TIMEOUT": str(current.get("ZHIHUIYA_MCP_TIMEOUT") or settings.zhihuiya_mcp_timeout),
        "ZHIHUIYA_MCP_DEFAULT_LIMIT": str(
            current.get("ZHIHUIYA_MCP_DEFAULT_LIMIT") or settings.zhihuiya_mcp_default_limit
        ),
        "ZHIHUIYA_NOVELTY_MCP_URL": novelty_url,
        "ZHIHUIYA_NOVELTY_MCP_API_KEY": novelty_key,
    }
    _write_env_file(env_path, values)
    return {
        "patent_search": bool(patent_url and patent_key),
        "novelty_search": bool(novelty_url and (novelty_key or patent_key)),
    }


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    lines = [
        "# Local-only Zhihuiya MCP configuration. This file is ignored by git.",
        f"ZHIHUIYA_MCP_URL={values['ZHIHUIYA_MCP_URL']}",
        f"ZHIHUIYA_MCP_API_KEY={values['ZHIHUIYA_MCP_API_KEY']}",
        f"ZHIHUIYA_MCP_TIMEOUT={values['ZHIHUIYA_MCP_TIMEOUT']}",
        f"ZHIHUIYA_MCP_DEFAULT_LIMIT={values['ZHIHUIYA_MCP_DEFAULT_LIMIT']}",
        f"ZHIHUIYA_NOVELTY_MCP_URL={values['ZHIHUIYA_NOVELTY_MCP_URL']}",
        f"ZHIHUIYA_NOVELTY_MCP_API_KEY={values['ZHIHUIYA_NOVELTY_MCP_API_KEY']}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _self_test_case(case: str, limit: int) -> dict[str, Any]:
    normalized = (case or "").lower()
    cases = {
        "tsinghua": {
            "question": "查询清华大学蔡临宁作为前三发明人的专利",
            "mode": "balanced",
            "limit": limit,
            "context": "返回公开号、申请人、发明人和公开日即可。",
        },
        "raw": {
            "question": '((hydrogen OR H2 OR 储氢) AND (cylinder OR vessel OR tank OR 气瓶 OR 压力容器) AND ("carbon fiber" OR composite OR 缠绕 OR 复合材料) AND (relief valve OR safety valve OR 泄压阀 OR 安全阀))',
            "mode": "raw",
            "limit": limit,
            "context": "保留原始布尔检索式。",
        },
        "hydrogen": {
            "question": "氢气瓶复合材料缠绕和泄压阀技术方案",
            "mode": "infringement",
            "limit": limit,
            "context": "关注压力容器、复合材料、缠绕层和安全阀。",
        },
    }
    return cases.get(normalized, cases["tsinghua"])


def main() -> None:
    import uvicorn

    uvicorn.run("patent_chat.app:app", host="127.0.0.1", port=8787, reload=True)


if __name__ == "__main__":
    main()
