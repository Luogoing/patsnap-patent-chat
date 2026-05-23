from __future__ import annotations

import asyncio
import inspect
import json
import re
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncIterator, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from .config import Settings


MISSING_API_KEY = "missing_api_key"
AUTH_FAILED = "auth_failed"
PERMISSION_DENIED = "permission_denied"
TOOL_NOT_FOUND = "tool_not_found"
TIMEOUT = "timeout"
INVALID_RESPONSE = "invalid_response"
SDK_UNAVAILABLE = "sdk_unavailable"
CONNECTION_FAILED = "connection_failed"

SECRET_QUERY_KEYS = {
    "apikey",
    "api_key",
    "key",
    "token",
    "access_token",
    "authorization",
}
SECRET_RE = re.compile(r"\bsk[-_][A-Za-z0-9._-]+")


def _result_ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def _result_error(code: str, message: str, detail: Any = None, api_key: str = "") -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        if isinstance(detail, BaseException):
            detail = str(detail)
        error["detail"] = redact_secret(detail, api_key)
    return {"ok": False, "data": None, "error": error}


def redact_secret(value: Any, api_key: str = "") -> Any:
    if isinstance(value, dict):
        return {key: redact_secret(item, api_key) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secret(item, api_key) for item in value]
    if not isinstance(value, str):
        return value

    redacted = SECRET_RE.sub("[redacted]", value)
    if api_key:
        redacted = redacted.replace(api_key, "[redacted]")
    return _redact_url_query(redacted)


def _redact_url_query(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme or not parts.netloc:
        return value

    query = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SECRET_QUERY_KEYS:
            query.append((key, "[redacted]"))
        else:
            query.append((key, item))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def clean_mcp_url_and_key(url: str, explicit_api_key: str = "") -> tuple[str, str]:
    raw_url = (url or "").strip()
    api_key = (explicit_api_key or "").strip()
    if not raw_url:
        return "", api_key

    parts = urlsplit(raw_url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if not api_key:
        for key, value in query:
            if key.lower() in SECRET_QUERY_KEYS and value:
                api_key = value
                break

    safe_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", parts.fragment))
    return safe_url.rstrip("/"), api_key


def _clamp_limit(limit: int | None, default_limit: int) -> int:
    selected = default_limit if limit is None else limit
    return max(1, min(int(selected), 100))


def _load_mcp_sdk() -> tuple[Any, Any]:
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as exc:
        raise RuntimeError(str(exc)) from exc
    return ClientSession, streamablehttp_client


def _maybe_get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _normalize_tools(response: Any) -> list[dict[str, Any]] | None:
    tools = _maybe_get(response, "tools", response)
    if not isinstance(tools, list):
        return None

    normalized: list[dict[str, Any]] = []
    for tool in tools:
        name = _maybe_get(tool, "name")
        if not isinstance(name, str) or not name:
            continue
        normalized.append(
            {
                "name": name,
                "description": _maybe_get(tool, "description", "") or "",
                "input_schema": _maybe_get(tool, "inputSchema", _maybe_get(tool, "input_schema", {})) or {},
            }
        )
    return normalized


def _choose_search_tool(tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    exact_names = {"search", "patent_search", "search_patents", "zhihuiya_search", "patsnap_search"}
    for tool in tools:
        if tool["name"] in exact_names:
            return tool
    for tool in tools:
        name = tool["name"].lower()
        if "search" in name and ("patent" in name or "zhihuiya" in name or "patsnap" in name):
            return tool
    for tool in tools:
        if "search" in tool["name"].lower():
            return tool
    return None


def _build_search_arguments(tool: dict[str, Any], query: str, limit: int) -> dict[str, Any]:
    schema = tool.get("input_schema")
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}

    args: dict[str, Any] = {}
    query_name = "query"
    for candidate in ("query", "q", "keyword", "keywords", "query_text"):
        if candidate in properties:
            query_name = candidate
            break
    args[query_name] = query

    limit_name = "limit"
    for candidate in ("limit", "size", "page_size", "count", "top_k"):
        if candidate in properties:
            limit_name = candidate
            break
    args[limit_name] = limit
    return args


def _json_from_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _extract_tool_payload(result: Any) -> Any:
    structured = _maybe_get(result, "structuredContent", _maybe_get(result, "structured_content"))
    if structured is not None:
        return structured

    if isinstance(result, dict):
        for key in ("data", "result", "results", "items", "patents"):
            if key in result:
                return result

    content = _maybe_get(result, "content")
    if isinstance(content, list):
        for item in content:
            text = _maybe_get(item, "text")
            if isinstance(text, str):
                parsed = _json_from_text(text)
                if parsed is not None:
                    return parsed
    return result


def _walk_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("items", "results", "patents", "list", "docs", "data"):
            found = _walk_items(value.get(key))
            if found:
                return found
    return []


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return ""


def normalize_search_result(result: Any, query: str, limit: int, api_key: str = "") -> dict[str, Any]:
    payload = _extract_tool_payload(result)
    items = _walk_items(payload)[:limit]
    if not isinstance(payload, (dict, list)) or not items:
        raise ValueError("MCP tool returned no recognizable patent list")

    normalized = []
    for row in items:
        normalized.append(
            {
                "number": _first_present(row, ("publication_number", "patent_number", "PN", "pn", "number")),
                "title": _first_present(row, ("title", "TTL", "ttl", "patent_title", "name")),
                "abstract": _first_present(row, ("abstract", "ABST", "abst", "patent_abstract")),
                "patent_id": _first_present(row, ("patent_id", "PATENT_ID", "id", "pid")),
                "raw": redact_secret(row, api_key),
            }
        )

    return {
        "query": query,
        "limit": limit,
        "items": normalized,
        "raw": redact_secret(payload, api_key),
    }


def _classify_exception(exc: BaseException) -> str:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)):
        return TIMEOUT

    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", status_code)
    if status_code in (401, 407):
        return AUTH_FAILED
    if status_code == 403:
        return PERMISSION_DENIED

    text = str(exc).lower()
    if "401" in text or "unauthorized" in text or "authentication" in text or "auth failed" in text:
        return AUTH_FAILED
    if "403" in text or "forbidden" in text or "permission" in text:
        return PERMISSION_DENIED
    if "not found" in text and "tool" in text:
        return TOOL_NOT_FOUND
    return CONNECTION_FAILED


def _message_for_code(code: str) -> str:
    return {
        MISSING_API_KEY: "缺少 ZHIHUIYA_MCP_API_KEY，或 ZHIHUIYA_MCP_URL 中没有可提取的 apikey。",
        AUTH_FAILED: "智慧芽 MCP 认证失败，请确认 API Key 有效。",
        PERMISSION_DENIED: "智慧芽 MCP 权限不足，请确认账号已开通对应工具权限。",
        TOOL_NOT_FOUND: "智慧芽 MCP 未提供可用的专利检索工具。",
        TIMEOUT: "智慧芽 MCP 请求超时。",
        INVALID_RESPONSE: "智慧芽 MCP 返回结构异常，无法标准化为专利结果。",
        SDK_UNAVAILABLE: "缺少 Python MCP SDK，无法使用 streamable HTTP transport。",
        CONNECTION_FAILED: "智慧芽 MCP 连接失败。",
    }[code]


def platform_error_from_payload(payload: Any, api_key: str = "") -> dict[str, Any] | None:
    if not isinstance(payload, dict) or payload.get("status") is not False:
        return None

    message = str(payload.get("error_msg") or payload.get("message") or payload.get("error") or "")
    lowered = message.lower()
    if "permission" in lowered or "quota" in lowered or "exceeded" in lowered:
        code = PERMISSION_DENIED
    elif "auth" in lowered or "key" in lowered or "token" in lowered:
        code = AUTH_FAILED
    else:
        code = CONNECTION_FAILED
    return _result_error(code, _message_for_code(code), payload, api_key)


SessionFactory = Callable[[], Any]


class ZhihuiyaMCPClient:
    def __init__(
        self,
        settings: Settings,
        session_factory: SessionFactory | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        channel: str = "patent_search",
    ):
        self.base_url, self.api_key = clean_mcp_url_and_key(
            settings.zhihuiya_mcp_url if base_url is None else base_url,
            settings.zhihuiya_mcp_api_key if api_key is None else api_key,
        )
        self.channel = channel
        self.timeout = max(1.0, float(settings.zhihuiya_mcp_timeout))
        self.default_limit = _clamp_limit(None, settings.zhihuiya_mcp_default_limit)
        self._session_factory = session_factory

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }

    def _transport_url(self) -> str:
        separator = "&" if urlsplit(self.base_url).query else "?"
        return f"{self.base_url}{separator}{urlencode({'apikey': self.api_key})}"

    def _missing_key_error(self) -> dict[str, Any] | None:
        if not self.api_key:
            return _result_error(MISSING_API_KEY, _message_for_code(MISSING_API_KEY))
        if not self.base_url:
            return _result_error(CONNECTION_FAILED, "缺少 ZHIHUIYA_MCP_URL，无法连接智慧芽 MCP。")
        return None

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[Any]:
        if self._session_factory is not None:
            async with self._session_factory() as session:
                yield session
            return

        try:
            ClientSession, streamablehttp_client = _load_mcp_sdk()
        except RuntimeError as exc:
            raise ZhihuiyaMCPRuntimeError(SDK_UNAVAILABLE, exc) from exc

        timeout = timedelta(seconds=self.timeout)
        try:
            transport_context = streamablehttp_client(
                self._transport_url(),
                headers=self._headers(),
                timeout=timeout,
                sse_read_timeout=timeout,
            )
        except TypeError:
            transport_context = streamablehttp_client(self._transport_url(), headers=self._headers())

        async with transport_context as transport:
            read_stream, write_stream = transport[0], transport[1]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    async def health(self) -> dict[str, Any]:
        missing = self._missing_key_error()
        if missing:
            return missing
        tools = await self.list_tools()
        if not tools.get("ok"):
            return tools
        tool_list = tools["data"]["tools"]
        return _result_ok(
            {
                "status": "ok",
                "tool_count": len(tool_list),
                "base_url": self.base_url,
                "channel": self.channel,
            }
        )

    async def list_tools(self) -> dict[str, Any]:
        missing = self._missing_key_error()
        if missing:
            return missing
        try:
            return await asyncio.wait_for(self._list_tools_once(), timeout=self.timeout + 1)
        except (asyncio.TimeoutError, TimeoutError) as exc:
            return _result_error(TIMEOUT, _message_for_code(TIMEOUT), exc, self.api_key)
        except ZhihuiyaMCPRuntimeError as exc:
            return _result_error(exc.code, _message_for_code(exc.code), exc.__cause__ or exc, self.api_key)
        except Exception as exc:
            code = _classify_exception(exc)
            return _result_error(code, _message_for_code(code), exc, self.api_key)

    async def search(self, query: str, limit: int | None = None) -> dict[str, Any]:
        missing = self._missing_key_error()
        if missing:
            return missing
        safe_limit = _clamp_limit(limit, self.default_limit)
        try:
            return await asyncio.wait_for(self._search_once(query, safe_limit), timeout=self.timeout + 1)
        except (asyncio.TimeoutError, TimeoutError) as exc:
            return _result_error(TIMEOUT, _message_for_code(TIMEOUT), exc, self.api_key)
        except ValueError as exc:
            return _result_error(INVALID_RESPONSE, _message_for_code(INVALID_RESPONSE), exc, self.api_key)
        except ZhihuiyaMCPRuntimeError as exc:
            return _result_error(exc.code, _message_for_code(exc.code), exc.__cause__ or exc, self.api_key)
        except Exception as exc:
            code = _classify_exception(exc)
            return _result_error(code, _message_for_code(code), exc, self.api_key)

    async def _list_tools_once(self) -> dict[str, Any]:
        platform_error = await self._preflight_platform_error()
        if platform_error:
            return platform_error
        async with self._session() as session:
            response = await _maybe_await(session.list_tools())
        tools = _normalize_tools(response)
        if tools is None:
            return _result_error(INVALID_RESPONSE, _message_for_code(INVALID_RESPONSE), response, self.api_key)
        return _result_ok({"tools": tools})

    async def _search_once(self, query: str, safe_limit: int) -> dict[str, Any]:
        platform_error = await self._preflight_platform_error()
        if platform_error:
            return platform_error
        async with self._session() as session:
            tools_response = await _maybe_await(session.list_tools())
            tools = _normalize_tools(tools_response)
            if tools is None:
                return _result_error(INVALID_RESPONSE, _message_for_code(INVALID_RESPONSE), tools_response, self.api_key)
            search_tool = _choose_search_tool(tools)
            if search_tool is None:
                return _result_error(TOOL_NOT_FOUND, _message_for_code(TOOL_NOT_FOUND))

            args = _build_search_arguments(search_tool, query, safe_limit)
            response = await _maybe_await(session.call_tool(search_tool["name"], args))

            data = normalize_search_result(response, query, safe_limit, self.api_key)
            data["tool"] = search_tool["name"]
            data["channel"] = self.channel
            return _result_ok(data)

    async def _preflight_platform_error(self) -> dict[str, Any] | None:
        timeout = min(self.timeout, 10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(self._transport_url(), headers=self._headers())
        except (httpx.HTTPError, asyncio.TimeoutError, TimeoutError):
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        return platform_error_from_payload(payload, self.api_key)


class ZhihuiyaMCPRuntimeError(RuntimeError):
    def __init__(self, code: str, cause: BaseException):
        self.code = code
        super().__init__(str(cause))
