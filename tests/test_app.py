from patent_chat.app import _build_mcp_query, _make_response
from patent_chat.intelligence import build_risk_summary, build_task_card


def test_build_mcp_query_keeps_raw_query_direct():
    card = build_task_card("raw: TACD: hydrogen storage tank", mode="raw")

    assert _build_mcp_query(card) == "TACD: hydrogen storage tank"


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
