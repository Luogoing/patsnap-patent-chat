from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, get_settings
from .normalizer import extract_total, google_patents_url, normalize_patents
from .patsnap_client import PatsnapAPIError, PatsnapClient, PatsnapConfigError
from .query_builder import build_query


STATIC_DIR = ROOT / "static"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    limit: int = 10
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


app = FastAPI(title="Patsnap Patent Chat", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "ok": True,
        "has_patsnap_api_key": bool(settings.patsnap_api_key),
        "base_url": settings.patsnap_base_url,
        "search_path": settings.patsnap_search_path,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()
    built = build_query(request.message)
    client = PatsnapClient(settings)
    try:
        count_response = await client.count(built.query_text)
        search_response = await client.search(
            built.query_text,
            limit=request.limit or settings.patsnap_default_limit,
            offset=request.offset,
        )
        total = extract_total(count_response, search_response)
        patents = normalize_patents(search_response, built.query_text, request.limit)
        answer = make_answer(built.query_text, built.note, total, patents)
        return ChatResponse(
            ok=True,
            answer=answer,
            query_text=built.query_text,
            query_mode=built.mode,
            total=total,
            google_patents_url=google_patents_url(built.query_text),
            patents=patents,
            raw={"count": count_response, "search": search_response},
        )
    except (PatsnapConfigError, PatsnapAPIError) as exc:
        return ChatResponse(
            ok=False,
            answer=f"检索失败：{exc}",
            query_text=built.query_text,
            query_mode=built.mode,
            google_patents_url=google_patents_url(built.query_text),
            error=str(exc),
        )


def make_answer(query_text: str, note: str, total: int | None, patents: list[dict[str, Any]]) -> str:
    total_text = f"命中约 {total} 件" if total is not None else "已完成检索，但未解析到总数"
    lines = [
        note,
        f"检索式：{query_text}",
        total_text,
    ]
    if patents:
        lines.append("前几条结果已列在下方。建议下一步根据最接近的申请人、CPC/IPC、权利要求关键词继续收窄。")
    return "\n".join(lines)


def main() -> None:
    import uvicorn

    uvicorn.run("patent_chat.app:app", host="127.0.0.1", port=8787, reload=True)


if __name__ == "__main__":
    main()
