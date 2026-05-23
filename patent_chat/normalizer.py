from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _walk_lists(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("results", "patents", "items", "list", "docs", "data"):
            found = _walk_lists(value.get(key))
            if found:
                return found
    return []


def extract_total(count_response: dict[str, Any], search_response: dict[str, Any]) -> int | None:
    candidates = [
        count_response.get("data", {}).get("total_search_result_count") if isinstance(count_response.get("data"), dict) else None,
        search_response.get("data", {}).get("num_found") if isinstance(search_response.get("data"), dict) else None,
        search_response.get("num_found"),
        count_response.get("total_search_result_count"),
    ]
    for value in candidates:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def normalize_patents(search_response: dict[str, Any], query_text: str, limit: int) -> list[dict[str, Any]]:
    rows = _walk_lists(search_response.get("data", search_response))[:limit]
    normalized: list[dict[str, Any]] = []
    for row in rows:
        number = _first_present(row, ("patent_number", "PN", "pn", "publication_number", "PBDT"))
        title = _first_present(row, ("title", "TTL", "ttl", "patent_title", "name"))
        abstract = _first_present(row, ("abstract", "ABST", "abst", "patent_abstract"))
        patent_id = _first_present(row, ("patent_id", "PATENT_ID", "id", "pid"))
        normalized.append(
            {
                "number": number or "",
                "title": title or "",
                "abstract": abstract or "",
                "patent_id": patent_id or "",
                "raw": row,
            }
        )

    if normalized:
        return normalized

    return [
        {
            "number": "",
            "title": "已获得 API 响应，但当前版本无法从返回结构中自动抽取专利列表。",
            "abstract": "请展开原始 JSON，或根据贵司 API 包实际字段调整 patent_chat/normalizer.py。",
            "patent_id": "",
            "raw": search_response,
        }
    ]


def google_patents_url(query_text: str) -> str:
    return f"https://patents.google.com/?q={quote_plus(query_text)}"
