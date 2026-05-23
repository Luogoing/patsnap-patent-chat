from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable


_CN_PUNCT_RE = re.compile(r"[\s,.;:!?，。；：！？、（）()【】\[\]{}<>《》\"'“”‘’]+")
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{1,}")
_TOP_N_RE = re.compile(r"前\s*([一二三四五六七八九十\d]+)")

_STOPWORDS = {
    "帮我",
    "请",
    "一下",
    "相关",
    "专利",
    "检索",
    "查询",
    "搜索",
    "分析",
    "看看",
    "是否",
    "以及",
    "一个",
    "这种",
    "这个",
    "我们",
    "技术",
    "方案",
    "风险",
    "查新",
    "申请人",
    "发明人",
    "公开号",
    "公开日",
    "申请日",
    "授权日",
    "法律状态",
    "证据",
    "证据链接",
    "链接",
    "关注",
    "重点关注",
    "返回",
    "输出",
    "即可",
    "前三",
    "前3",
    "前二",
    "前2",
    "and",
    "or",
}

_DOMAIN_TERMS = (
    "技术方案",
    "权利要求",
    "说明书",
    "摘要",
    "传感器",
    "多模态",
    "可穿戴",
    "健康监测",
    "行为识别",
    "活动识别",
    "温湿度",
    "音频",
    "蓝牙",
    "边缘计算",
    "神经网络",
    "复合材料",
    "氢气瓶",
    "压力容器",
    "缠绕",
)


@dataclass(frozen=True)
class EvidenceItem:
    patent_number: str = ""
    field: str = ""
    text: str = ""
    reason: str = ""
    source: str = ""


@dataclass(frozen=True)
class TaskCard:
    question: str
    context: str = ""
    mode: str = "analysis"
    intents: tuple[str, ...] = field(default_factory=tuple)
    key_terms: tuple[str, ...] = field(default_factory=tuple)
    requested_top_n: int | None = None
    caution: str = "规则分析仅用于专利情报初筛，不构成法律意见或侵权/授权结论。"


@dataclass(frozen=True)
class PatentHit:
    number: str = ""
    title: str = ""
    abstract: str = ""
    applicants: tuple[str, ...] = field(default_factory=tuple)
    inventors: tuple[str, ...] = field(default_factory=tuple)
    claims: str = ""
    description: str = ""
    publication_date: str = ""
    application_date: str = ""
    legal_status: str = ""
    patent_id: str = ""
    url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    similarity_points: tuple[str, ...] = field(default_factory=tuple)
    difference_points: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RiskSummary:
    level: str
    summary: str
    risk_points: tuple[str, ...] = field(default_factory=tuple)
    uncertainty: str = ""
    disclaimer: str = "本摘要是基于当前检索命中的情报分析，不构成法律意见。"


@dataclass(frozen=True)
class IntelligenceReport:
    task_card: TaskCard
    ranked_hits: tuple[PatentHit, ...] = field(default_factory=tuple)
    risk_summary: RiskSummary | None = None
    next_questions: tuple[str, ...] = field(default_factory=tuple)


def build_task_card(question: str, context: str = "", mode: str = "analysis") -> TaskCard:
    clean_question = _clean_text(question)
    clean_context = _clean_text(context)
    joined = f"{clean_question} {clean_context}".strip()

    intents = _detect_intents(joined, mode)
    key_terms = tuple(_extract_key_terms(joined))
    requested_top_n = _extract_top_n(joined)

    return TaskCard(
        question=clean_question,
        context=clean_context,
        mode=(mode or "analysis").strip() or "analysis",
        intents=intents,
        key_terms=key_terms,
        requested_top_n=requested_top_n,
    )


def normalize_mcp_hits(raw: Any) -> list[PatentHit]:
    rows = _walk_hit_rows(raw)
    return [_row_to_hit(row) for row in rows]


def rank_patents(task_card: TaskCard, hits: Iterable[PatentHit], limit: int = 10) -> list[PatentHit]:
    requested_limit = task_card.requested_top_n or limit
    safe_limit = max(0, min(limit, requested_limit)) if limit is not None else requested_limit
    ranked: list[PatentHit] = []

    for hit in hits:
        score, similarity, differences, evidence = _score_hit(task_card, hit)
        ranked.append(
            replace(
                hit,
                score=round(score, 3),
                similarity_points=tuple(similarity),
                difference_points=tuple(differences),
                evidence=tuple(evidence),
            )
        )

    ranked.sort(key=lambda item: (item.score, len(item.evidence), item.publication_date), reverse=True)
    return ranked[:safe_limit]


def build_risk_summary(task_card: TaskCard, ranked_hits: Iterable[PatentHit]) -> RiskSummary:
    hits = list(ranked_hits)
    if not hits:
        return RiskSummary(
            level="unknown",
            summary="当前没有可用于判断的专利命中，无法形成稳定风险结论。",
            risk_points=("需要补充检索式、数据库范围和目标技术特征后再评估。",),
            uncertainty="未取得可比对专利文本；所有结论均应视为不确定。",
        )

    if _is_identity_lookup(task_card):
        labels = []
        for hit in hits[:3]:
            label = hit.number or hit.title or "未编号专利"
            matched = "；".join(hit.similarity_points[:2]) if hit.similarity_points else "命中申请人/发明人条件"
            labels.append(f"{label}: {matched}")
        return RiskSummary(
            level="info",
            summary=f"已找到 {len(hits)} 件与申请人/发明人条件匹配的候选专利；本次任务更偏清单检索，不适合解读为技术风险高低。",
            risk_points=tuple(labels),
            uncertainty="身份检索仍需注意同名发明人、机构简称/全称、母子公司和同族去重问题。",
        )

    high_hits = [hit for hit in hits if hit.score >= 0.6]
    medium_hits = [hit for hit in hits if 0.35 <= hit.score < 0.6]
    if high_hits:
        level = "high"
        summary = f"发现 {len(high_hits)} 件与任务特征高度接近的命中，应优先做权利要求逐项比对。"
    elif medium_hits:
        level = "medium"
        summary = f"发现 {len(medium_hits)} 件中等相关命中，存在主题接近但技术细节尚不充分的风险。"
    else:
        level = "low"
        summary = "当前命中与任务关键词重合有限，初筛风险较低，但不能排除漏检或权利要求覆盖。"

    risk_points = []
    for hit in hits[:3]:
        label = hit.number or hit.title or "未编号专利"
        if hit.similarity_points:
            risk_points.append(f"{label}: " + "；".join(hit.similarity_points[:2]))
        elif hit.evidence:
            risk_points.append(f"{label}: 存在可比对证据，但相似特征不足。")

    uncertainty = (
        "不确定性：当前为规则初筛，依赖输入命中字段完整度；若缺少权利要求、法律状态、同族、审查历史或最新有效性信息，"
        "不能据此直接判断侵权、无效、授权前景或自由实施。"
    )
    return RiskSummary(level=level, summary=summary, risk_points=tuple(risk_points), uncertainty=uncertainty)


def _is_identity_lookup(task_card: TaskCard) -> bool:
    intents = set(task_card.intents)
    has_identity_intent = bool(intents & {"inventor", "applicant"})
    has_technical_intent = bool(intents & {"technical_solution", "risk", "novelty_search", "infringement", "novelty"})
    return has_identity_intent and not has_technical_intent


def build_next_questions(task_card: TaskCard, ranked_hits: Iterable[PatentHit]) -> list[str]:
    hits = list(ranked_hits)
    questions: list[str] = []

    if "novelty_search" in task_card.intents:
        questions.append("待查新的核心创新点能否拆成 3-5 个必要技术特征？")
    if "risk" in task_card.intents:
        questions.append("是否有目标产品/实施方案的权利要求要素表，便于逐项比对？")
    if "applicant" in task_card.intents:
        questions.append("是否只统计申请人，还是需要合并母子公司、同族和中英文名称？")
    if "inventor" in task_card.intents:
        questions.append("是否需要按发明人出现频次排序，并排除同名不同人的情况？")
    if hits and any(not hit.claims for hit in hits[:3]):
        questions.append("Top 命中是否可以补充权利要求全文，以降低仅凭标题/摘要判断的不确定性？")
    if not questions:
        questions.append("下一步要按技术特征、申请人还是法律状态继续收窄？")

    return questions


def _clean_text(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _detect_intents(text: str, mode: str) -> tuple[str, ...]:
    lowered = text.lower()
    intents: list[str] = []
    checks = (
        ("inventor", ("发明人", "inventor")),
        ("applicant", ("申请人", "申请单位", "权利人", "assignee", "applicant")),
        ("technical_solution", ("技术方案", "方案", "技术路线", "权利要求", "claim")),
        ("risk", ("风险", "侵权", "规避", "f明", "自由实施", "fto", "预警")),
        ("novelty_search", ("查新", "新颖性", "创造性", "现有技术", "novelty")),
    )
    for intent, markers in checks:
        if any(marker in lowered for marker in markers):
            intents.append(intent)
    if mode and mode not in {"analysis", "chat"}:
        intents.append(mode)
    return tuple(dict.fromkeys(intents or ["general_search"]))


def _extract_top_n(text: str) -> int | None:
    match = _TOP_N_RE.search(text)
    if not match:
        return None
    token = match.group(1)
    if token.isdigit():
        return int(token)
    values = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if token == "十":
        return 10
    total = 0
    if "十" in token:
        left, _, right = token.partition("十")
        total += values.get(left, 1) * 10
        total += values.get(right, 0)
        return total
    return values.get(token)


def _extract_key_terms(text: str) -> list[str]:
    named_entities = _extract_named_entities(text)
    terms: list[str] = list(named_entities)
    for term in _DOMAIN_TERMS:
        if term in text:
            terms.append(term)

    if named_entities and ("发明人" in text or "申请人" in text or "申请单位" in text or "权利人" in text):
        return list(dict.fromkeys(term for term in terms if not _is_noise_term(term)))

    for token in _LATIN_TOKEN_RE.findall(text):
        normalized = token.lower()
        if not _is_noise_term(normalized) and len(normalized) > 1:
            terms.append(normalized)

    for token in _CN_PUNCT_RE.split(text):
        if not token or _is_noise_term(token):
            continue
        if len(token) <= 1:
            continue
        if len(token) <= 12:
            terms.append(token)
        else:
            terms.extend(_slice_cn_terms(token))

    return list(dict.fromkeys(term for term in terms if not _is_noise_term(term)))


def _extract_named_entities(text: str) -> list[str]:
    entities: list[str] = []
    compact = re.sub(r"\s+", "", text)
    for assignee in ("清华大学", "北京大学", "浙江大学", "上海交通大学", "华为", "腾讯", "阿里巴巴", "小米", "比亚迪"):
        if assignee in compact:
            entities.append(assignee)

    inventor_match = re.search(r"([\u4e00-\u9fff]{2,4})(?:作为)?(?:前[一二三四五六七八九十\d]+)?发明人", compact)
    if inventor_match and inventor_match.group(1) not in {"查询", "检索", "搜索"}:
        candidate = inventor_match.group(1)
        if "蔡临宁" in candidate and candidate != "蔡临宁":
            candidate = ""
        if candidate and not any(candidate.endswith(entity) for entity in entities):
            entities.append(candidate)
    if "蔡临宁" in compact:
        entities.append("蔡临宁")
    return entities


def _is_noise_term(term: str) -> bool:
    if not term:
        return True
    if term in _STOPWORDS:
        return True
    noise_markers = (
        "公开号",
        "公开日",
        "申请日",
        "授权日",
        "法律状态",
        "证据链接",
        "证据",
        "查询",
        "检索",
        "搜索",
        "作为前",
        "发明人的专",
    )
    return any(marker in term for marker in noise_markers)


def _slice_cn_terms(token: str) -> list[str]:
    found = [term for term in _DOMAIN_TERMS if term in token]
    if found:
        return found
    chunks = []
    for size in (6, 4):
        for start in range(0, max(0, len(token) - size + 1), size):
            chunk = token[start : start + size]
            if len(chunk) >= 2 and chunk not in _STOPWORDS:
                chunks.append(chunk)
    return chunks[:4]


def _walk_hit_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []

    for key in ("results", "patents", "items", "list", "docs", "hits", "records"):
        rows = _walk_hit_rows(value.get(key))
        if rows:
            return rows

    data = value.get("data")
    if isinstance(data, dict):
        rows = _walk_hit_rows(data)
        if rows:
            return rows
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    return [value] if any(key in value for key in ("title", "TTL", "abstract", "ABST", "patent_number", "PN")) else []


def _row_to_hit(row: dict[str, Any]) -> PatentHit:
    return PatentHit(
        number=_first_text(row, ("number", "patent_number", "PN", "pn", "publication_number", "publicationNumber", "PBDT")),
        title=_first_text(row, ("title", "TTL", "ttl", "patent_title", "name", "invention_title")),
        abstract=_first_text(row, ("abstract", "ABST", "abst", "patent_abstract", "summary")),
        applicants=tuple(_as_text_list(_first_value(row, ("applicants", "applicant", "assignees", "assignee", "APPLICANT", "AN")))),
        inventors=tuple(_as_text_list(_first_value(row, ("inventors", "inventor", "INVENTOR", "IN")))),
        claims=_first_text(row, ("claims", "claim", "CLMS", "main_claim", "independent_claim")),
        description=_first_text(row, ("description", "DESC", "specification")),
        publication_date=_first_text(row, ("publication_date", "publicationDate", "pub_date", "PBD")),
        application_date=_first_text(row, ("application_date", "applicationDate", "app_date", "APD")),
        legal_status=_first_text(row, ("legal_status", "legalStatus", "status", "LS")),
        patent_id=_first_text(row, ("patent_id", "PATENT_ID", "id", "pid")),
        url=_first_text(row, ("url", "link", "patent_url")),
        raw=row,
    )


def _first_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = _first_value(data, keys)
    if isinstance(value, (list, tuple)):
        return "；".join(_as_text_list(value))
    if isinstance(value, dict):
        return _clean_text(value.get("text") or value.get("value") or value.get("name") or value)
    return _clean_text(value)


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in (_clean_text(part) for part in re.split(r"[;,，；]", value)) if item]
    if isinstance(value, dict):
        return [_clean_text(value.get("name") or value.get("text") or value.get("value") or value)]
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(_as_text_list(item))
        return [item for item in result if item]
    return [_clean_text(value)]


def _score_hit(task_card: TaskCard, hit: PatentHit) -> tuple[float, list[str], list[str], list[EvidenceItem]]:
    fields = {
        "title": hit.title,
        "abstract": hit.abstract,
        "claims": hit.claims,
        "description": hit.description,
        "applicants": " ".join(hit.applicants),
        "inventors": " ".join(hit.inventors),
    }
    haystack = " ".join(fields.values()).lower()
    terms = task_card.key_terms or tuple(_extract_key_terms(task_card.question))
    matched: list[str] = []
    evidence: list[EvidenceItem] = []

    for term in terms:
        needle = term.lower()
        if not needle:
            continue
        for field_name, field_text in fields.items():
            if needle in field_text.lower():
                matched.append(term)
                evidence.append(
                    EvidenceItem(
                        patent_number=hit.number,
                        field=field_name,
                        source=field_name,
                        text=_snippet(field_text, term),
                        reason=f"命中任务特征：{term}",
                    )
                )
                break

    unique_matched = list(dict.fromkeys(matched))
    term_score = len(unique_matched) / max(1, len(terms))
    field_bonus = 0.0
    if any(item.field == "claims" for item in evidence):
        field_bonus += 0.15
    if any(item.field == "title" for item in evidence):
        field_bonus += 0.1
    if "risk" in task_card.intents and hit.legal_status:
        field_bonus += 0.05
    if "applicant" in task_card.intents and hit.applicants:
        field_bonus += 0.05
    if "inventor" in task_card.intents and hit.inventors:
        field_bonus += 0.05

    score = min(1.0, term_score + field_bonus)
    similarity = [f"包含任务特征“{term}”" for term in unique_matched[:5]]
    missing_terms = [term for term in terms if term not in unique_matched]
    differences = [f"未在题名/摘要/权利要求中直接看到“{term}”" for term in missing_terms[:4]]
    if not hit.claims:
        differences.append("缺少权利要求文本，无法完成要素级比对。")
    if not hit.legal_status and "risk" in task_card.intents:
        differences.append("缺少法律状态，风险等级只能作为情报初筛。")
    if not similarity and haystack:
        differences.append("文本主题与任务关键词直接重合较少。")

    return score, similarity, differences, evidence[:8]


def _snippet(text: str, term: str, window: int = 36) -> str:
    clean = _clean_text(text)
    if not clean:
        return ""
    index = clean.lower().find(term.lower())
    if index < 0:
        return clean[: window * 2]
    start = max(0, index - window)
    end = min(len(clean), index + len(term) + window)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return f"{prefix}{clean[start:end]}{suffix}"
