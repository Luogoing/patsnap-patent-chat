from patent_chat.app import _build_mcp_query, _client_for_mode, _make_response, _should_fallback_to_novelty
from patent_chat.config import Settings
from patent_chat.intelligence import build_risk_summary, build_task_card


def test_build_mcp_query_keeps_raw_query_direct():
    card = build_task_card("raw: TACD: hydrogen storage tank", mode="raw")

    assert _build_mcp_query(card) == "TACD: hydrogen storage tank"


def test_build_mcp_query_simplifies_identity_lookup():
    card = build_task_card(
        "查询清华大学蔡临宁作为前三发明人的专利",
        "关注公开号、申请人、发明人、公开日、法律状态和证据链接。",
        "balanced",
    )

    assert _build_mcp_query(card) == "清华大学 蔡临宁"


def test_intelligence_error_response_has_required_schema_and_redacts_secret():
    card = build_task_card("查询清华大学蔡临宁作为前三发明人的专利", mode="balanced")
    risk = build_risk_summary(card, [])
    response = _make_response(
        ok=False,
        trace_id="trace-test",
        task_card=card,
        query="清华大学 蔡临宁 发明人",
        patents=[],
        risk_summary=risk,
        error={
            "code": "auth_failed",
            "message": "智慧芽 MCP 认证失败",
            "detail": "https://example.test/mcp?apikey=test_key_placeholder",
        },
    )

    assert response["ok"] is False
    assert response["trace_id"] == "trace-test"
    assert response["task_card"]["question"] == "查询清华大学蔡临宁作为前三发明人的专利"
    assert response["patents"] == []
    assert response["ranking"] == []
    assert response["risk_summary"]["level"] == "unknown"
    assert response["error_code"] == "auth_failed"
    assert "test_key_placeholder" not in str(response)


def test_novelty_mode_selects_novelty_mcp_channel():
    settings = Settings(
        ZHIHUIYA_MCP_URL="https://example.test/search",
        ZHIHUIYA_MCP_API_KEY="main_key",
        ZHIHUIYA_NOVELTY_MCP_URL="https://example.test/novelty",
        ZHIHUIYA_NOVELTY_MCP_API_KEY="novelty_key",
    )

    client = _client_for_mode(settings, "novelty")

    assert client.channel == "novelty_search"
    assert client.base_url == "https://example.test/novelty"
    assert client.api_key == "novelty_key"


def test_permission_denied_can_fallback_to_novelty_channel():
    settings = Settings(
        ZHIHUIYA_MCP_URL="https://example.test/search",
        ZHIHUIYA_MCP_API_KEY="main_key",
        ZHIHUIYA_NOVELTY_MCP_URL="https://example.test/novelty",
    )
    response = {"ok": False, "error": {"code": "permission_denied"}}

    assert _should_fallback_to_novelty(response, settings, "balanced") is True
    assert _should_fallback_to_novelty(response, settings, "novelty") is False
