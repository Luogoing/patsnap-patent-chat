from patent_chat.intelligence import (
    build_next_questions,
    build_risk_summary,
    build_task_card,
    normalize_mcp_hits,
    rank_patents,
)


def test_chinese_question_builds_task_card():
    card = build_task_card(
        "请分析可穿戴多模态健康监测技术方案的查新风险，并列出前三发明人和申请人",
        "重点关注温湿度、音频和活动识别",
        "risk",
    )

    assert "technical_solution" in card.intents
    assert "novelty_search" in card.intents
    assert "risk" in card.intents
    assert "inventor" in card.intents
    assert "applicant" in card.intents
    assert card.requested_top_n == 3
    assert "可穿戴" in card.key_terms
    assert "多模态" in card.key_terms
    assert "法律意见" in card.caution


def test_person_lookup_keeps_output_fields_out_of_key_terms():
    card = build_task_card(
        "查询清华大学蔡临宁作为前三发明人的专利",
        "关注公开号、申请人、发明人、公开日、法律状态和证据链接。",
        "balanced",
    )

    assert "清华大学" in card.key_terms
    assert "蔡临宁" in card.key_terms
    assert "公开号" not in card.key_terms
    assert "证据链接" not in card.key_terms
    assert "申请人" not in card.key_terms


def test_mock_mcp_hits_normalize_to_patent_hits():
    raw = {
        "data": {
            "results": [
                {
                    "PN": "CN123456789A",
                    "TTL": "一种可穿戴多模态健康监测系统",
                    "ABST": "融合温湿度传感器、音频和活动识别模型。",
                    "AN": [{"name": "北京智能科技有限公司"}],
                    "IN": "张三; 李四",
                    "CLMS": "一种系统，包括可穿戴传感器和多模态融合模块。",
                    "legalStatus": "公开",
                }
            ]
        }
    }

    hits = normalize_mcp_hits(raw)

    assert len(hits) == 1
    assert hits[0].number == "CN123456789A"
    assert hits[0].title == "一种可穿戴多模态健康监测系统"
    assert hits[0].applicants == ("北京智能科技有限公司",)
    assert hits[0].inventors == ("张三", "李四")
    assert "融合模块" in hits[0].claims


def test_risk_summary_contains_uncertainty_and_no_legal_overpromise():
    card = build_task_card("可穿戴多模态健康监测方案有没有查新和侵权风险", mode="risk")
    hits = normalize_mcp_hits(
        [
            {
                "publication_number": "CN111111111A",
                "title": "可穿戴健康监测装置",
                "abstract": "通过多模态传感器采集活动识别和环境温湿度。",
                "claims": "包括可穿戴传感器、多模态融合处理器和健康监测输出。",
            }
        ]
    )
    ranked = rank_patents(card, hits, limit=5)

    summary = build_risk_summary(card, ranked)

    assert summary.level in {"medium", "high"}
    assert "不确定性" in summary.uncertainty
    assert "不构成法律意见" in summary.disclaimer
    assert summary.risk_points


def test_top_n_ranking_includes_comparison_and_evidence():
    card = build_task_card("查新 可穿戴 多模态 活动识别 温湿度 前2", mode="novelty")
    hits = normalize_mcp_hits(
        [
            {
                "PN": "CN-A",
                "TTL": "可穿戴多模态活动识别系统",
                "ABST": "系统用于活动识别。",
                "CLMS": "包括可穿戴设备、多模态融合模块和活动识别模型。",
            },
            {
                "PN": "CN-B",
                "TTL": "厨房设备控制方法",
                "ABST": "用于家电控制。",
            },
            {
                "PN": "CN-C",
                "TTL": "可穿戴传感器",
                "ABST": "采集体征数据。",
            },
        ]
    )

    ranked = rank_patents(card, hits, limit=2)

    assert [hit.number for hit in ranked] == ["CN-A", "CN-C"]
    assert len(ranked) == 2
    assert ranked[0].score > ranked[1].score
    assert ranked[0].similarity_points
    assert ranked[0].difference_points
    assert ranked[0].evidence
    assert ranked[0].evidence[0].field in {"title", "abstract", "claims"}


def test_next_questions_follow_detected_intents():
    card = build_task_card("前三申请人和发明人，顺便看风险", mode="analysis")

    questions = build_next_questions(card, [])

    assert any("申请人" in question for question in questions)
    assert any("发明人" in question for question in questions)
    assert any("权利要求" in question for question in questions)
