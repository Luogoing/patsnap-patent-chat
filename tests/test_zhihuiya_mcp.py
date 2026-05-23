import asyncio
from types import SimpleNamespace

from patent_chat.config import Settings
from patent_chat.zhihuiya_mcp import (
    MISSING_API_KEY,
    ZhihuiyaMCPClient,
    _build_search_arguments,
    clean_mcp_url_and_key,
    normalize_search_result,
    platform_error_from_payload,
    redact_secret,
)


def test_redact_secret_removes_keys_from_text_and_nested_data():
    secret = "test_key_placeholder"
    data = {
        "url": f"https://example.test/mcp?apikey={secret}&safe=1",
        "headers": {"Authorization": f"Bearer {secret}"},
    }

    redacted = redact_secret(data, secret)

    assert secret not in str(redacted)
    assert "[redacted]" in str(redacted)
    assert "safe=1" in redacted["url"]


def test_clean_mcp_url_extracts_key_and_strips_query():
    base_url, api_key = clean_mcp_url_and_key(
        "https://mcp.example.test/stream?apikey=test_key_placeholder&foo=bar"
    )

    assert base_url == "https://mcp.example.test/stream"
    assert api_key == "test_key_placeholder"
    assert "apikey" not in base_url
    assert "test_key_placeholder" not in base_url


def test_clean_mcp_url_prefers_explicit_key():
    base_url, api_key = clean_mcp_url_and_key(
        "https://mcp.example.test/stream?apikey=url_key_placeholder",
        "explicit_key_placeholder",
    )

    assert base_url == "https://mcp.example.test/stream"
    assert api_key == "explicit_key_placeholder"


def test_client_keeps_only_safe_base_url():
    settings = Settings(
        ZHIHUIYA_MCP_URL="https://mcp.example.test/stream?apikey=test_key_placeholder&foo=bar",
        ZHIHUIYA_MCP_API_KEY="",
    )
    client = ZhihuiyaMCPClient(settings)

    assert client.base_url == "https://mcp.example.test/stream"
    assert "test_key_placeholder" not in client.base_url
    assert "apikey" not in client.base_url
    assert not hasattr(client, "settings")


def test_transport_url_adds_apikey_only_at_call_boundary():
    settings = Settings(
        ZHIHUIYA_MCP_URL="https://mcp.example.test/stream",
        ZHIHUIYA_MCP_API_KEY="test_key_placeholder",
    )
    client = ZhihuiyaMCPClient(settings)

    transport_url = client._transport_url()

    assert client.base_url == "https://mcp.example.test/stream"
    assert "test_key_placeholder" not in client.base_url
    assert "apikey=test_key_placeholder" in transport_url


def test_missing_key_error_is_structured():
    settings = Settings(
        ZHIHUIYA_MCP_URL="https://mcp.example.test/stream",
        ZHIHUIYA_MCP_API_KEY="",
    )
    client = ZhihuiyaMCPClient(settings)

    result = asyncio.run(client.health())

    assert result["ok"] is False
    assert result["error"]["code"] == MISSING_API_KEY
    assert "ZHIHUIYA_MCP_API_KEY" in result["error"]["message"]


def test_patsnap_search_schema_uses_topk_filters_and_strategy():
    tool = {
        "name": "patsnap_search",
        "input_schema": {
            "properties": {
                "topk": {},
                "filters": {},
                "sources": {},
                "keywords": {},
                "semantic_query": {},
                "search_strategy": {},
            }
        },
    }

    args = _build_search_arguments(tool, "查询清华大学蔡临宁作为前三发明人的专利", 5)

    assert args["topk"] == 5
    assert args["sources"] == ["patent"]
    assert args["search_strategy"] == ["filter"]
    assert "keywords" not in args
    assert args["filters"]["assignees"] == ["清华大学"]
    assert args["filters"]["inventors"] == ["蔡临宁"]


def test_normalize_search_result_parses_mcp_text_json():
    mcp_result = SimpleNamespace(
        content=[
            SimpleNamespace(
                text="""
                {
                  "results": [
                    {
                      "publication_number": "CN123456789A",
                      "title": "复合材料氢气瓶",
                      "abstract": "一种复合材料压力容器。",
                      "patent_id": "pid-1"
                    }
                  ]
                }
                """
            )
        ]
    )

    normalized = normalize_search_result(mcp_result, "氢气瓶", 10, "test_key_placeholder")

    assert normalized["query"] == "氢气瓶"
    assert normalized["items"] == [
        {
            "number": "CN123456789A",
            "title": "复合材料氢气瓶",
            "abstract": "一种复合材料压力容器。",
            "patent_id": "pid-1",
            "raw": {
                "publication_number": "CN123456789A",
                "title": "复合材料氢气瓶",
                "abstract": "一种复合材料压力容器。",
                "patent_id": "pid-1",
            },
        }
    ]


def test_platform_error_maps_quota_or_permission_without_secret():
    result = platform_error_from_payload(
        {
            "error_code": 67200004,
            "error_msg": "No permission or API package quota has exceeded the limit!",
            "status": False,
            "debug": "apikey=test_key_placeholder",
        },
        "test_key_placeholder",
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "permission_denied"
    assert "test_key_placeholder" not in str(result)
