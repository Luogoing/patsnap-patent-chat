from patent_chat.query_builder import build_query


def test_raw_query_passthrough():
    built = build_query("raw: TACD: virtual reality")
    assert built.query_text == "TACD: virtual reality"
    assert built.mode == "raw"


def test_patent_number_query():
    built = build_query("US8674530 CN111922118A")
    assert built.query_text == "PN:(US8674530 OR CN111922118A)"
    assert built.mode == "patent_number"


def test_keyword_query():
    built = build_query("检索 氢气瓶 复合材料 缠绕 相关专利")
    assert built.query_text.startswith("TACD:")
    assert "氢气瓶" in built.query_text
