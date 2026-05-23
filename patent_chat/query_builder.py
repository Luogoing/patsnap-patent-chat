import re
from dataclasses import dataclass


PATENT_NUMBER_RE = re.compile(r"\b[A-Z]{2}\s?\d{4,}[A-Z]?\d?\b", re.IGNORECASE)


@dataclass(frozen=True)
class BuiltQuery:
    query_text: str
    mode: str
    note: str


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def build_query(message: str) -> BuiltQuery:
    text = _clean_text(message)
    if not text:
        return BuiltQuery("TACD: patent", "keyword", "空输入已替换为默认关键词。")

    lower = text.lower()
    if lower.startswith("raw:"):
        raw = text[4:].strip()
        return BuiltQuery(raw, "raw", "已按原始 Patsnap 检索式发送。")

    patent_numbers = [m.group(0).replace(" ", "").upper() for m in PATENT_NUMBER_RE.finditer(text)]
    if patent_numbers and len(" ".join(patent_numbers)) >= max(6, len(text) // 2):
        joined = " OR ".join(dict.fromkeys(patent_numbers))
        return BuiltQuery(f"PN:({joined})", "patent_number", "检测到专利号，已使用 PN 字段检索。")

    stripped = re.sub(r"^(帮我|请|检索|搜索|查找|查询|找一下|帮忙)\s*", "", text)
    stripped = stripped.replace("相关专利", "").replace("专利", "").strip(" ，。；;")
    if not stripped:
        stripped = text

    return BuiltQuery(f"TACD: {stripped}", "keyword", "已使用 TACD 字段检索题名、摘要、权利要求和说明书。")
