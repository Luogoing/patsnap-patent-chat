const form = document.querySelector("#intelligence-form");
const questionInput = document.querySelector("#question");
const modeInput = document.querySelector("#mode");
const limitInput = document.querySelector("#limit");
const contextInput = document.querySelector("#context");
const submitButton = document.querySelector("#submit-button");
const emptyState = document.querySelector("#empty-state");
const report = document.querySelector("#report");
const requestStatus = document.querySelector("#request-status");
const modeDescription = document.querySelector("#mode-description");
const modeHelp = document.querySelector("#mode-help");
const configSummary = document.querySelector("#config-summary");
const configMainUrl = document.querySelector("#config-main-url");
const configMainKey = document.querySelector("#config-main-key");
const configNoveltyUrl = document.querySelector("#config-novelty-url");
const configNoveltyKey = document.querySelector("#config-novelty-key");
const saveConfigButton = document.querySelector("#save-config-button");
const selfTestButton = document.querySelector("#self-test-button");
const configStatus = document.querySelector("#config-status");

const MODE_META = {
  balanced: {
    label: "综合检索",
    description: "适合第一次摸底，兼顾相关专利、证据和风险。",
  },
  novelty: {
    label: "新颖性初筛",
    description: "适合判断方案是否容易被现有公开文献覆盖，重点看相似技术特征。",
  },
  infringement: {
    label: "侵权风险",
    description: "适合围绕产品边界识别潜在权利要求风险和规避方向。",
  },
  landscape: {
    label: "技术布局",
    description: "适合梳理申请人、技术分支、热门方向和空白点。",
  },
  raw: {
    label: "专家检索式",
    description: "适合直接提交智慧芽/布尔检索式，由接口按原始检索意图执行。",
  },
};

const EXAMPLES = {
  tsinghua: {
    question: "查询清华大学蔡临宁作为前三发明人的专利",
    mode: "balanced",
    limit: 5,
    context: "关注公开号、申请人、发明人、公开日、法律状态和证据链接。",
  },
  hydrogen: {
    question: "一种面向无人机或航空装备的高压氢气瓶方案：复合材料缠绕层、金属或塑料内胆、端部过渡区、泄压阀/安全阀一体化布置，要求评估相似专利和潜在风险。",
    mode: "infringement",
    limit: 10,
    context: "重点关注碳纤维缠绕、储氢气瓶、泄压阀、压力容器、端部密封结构。希望区分材料层结构与安全阀结构的相似点。",
  },
  raw: {
    question: '((hydrogen OR H2 OR 储氢) AND (cylinder OR vessel OR tank OR 气瓶 OR 压力容器) AND ("carbon fiber" OR composite OR 缠绕 OR 复合材料) AND (relief valve OR safety valve OR 泄压阀 OR 安全阀))',
    mode: "raw",
    limit: 20,
    context: "raw 模式：尽量保留原始布尔逻辑。可优先返回公开号、申请人、发明人、法律状态和证据链接。",
  },
};

const ERROR_HINTS = [
  { pattern: /config|配置|env|environment|api key|key/i, label: "配置错误", advice: "请检查服务端环境变量、Patsnap/MCP 配置和 API key 是否可用。" },
  { pattern: /auth|认证|unauthorized|401|token|bearer/i, label: "认证错误", advice: "请确认接口鉴权、token 或连接器登录状态是否有效。" },
  { pattern: /permission|权限|forbidden|403|scope/i, label: "权限错误", advice: "账号可能缺少数据源或工具权限，请检查授权范围。" },
  { pattern: /tool|工具|mcp|client|connector|timeout|timed out/i, label: "工具调用错误", advice: "上游 MCP/连接器可能超时或不可用，可以稍后重试并保留 trace_id 排查。" },
];

function asArray(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function firstValue(source, keys, fallback = "") {
  for (const key of keys) {
    if (source && source[key] !== undefined && source[key] !== null && source[key] !== "") {
      return source[key];
    }
  }
  return fallback;
}

function textValue(value) {
  if (Array.isArray(value)) return value.filter(Boolean).map(textValue).join("，");
  if (value && typeof value === "object") return JSON.stringify(value);
  return value === undefined || value === null ? "" : String(value);
}

function formatDate(value) {
  const text = textValue(value);
  if (!text) return "";
  if (/^\d{8}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
  return text;
}

function formatScore(value) {
  if (value === undefined || value === null || value === "") return "";
  const number = Number(value);
  if (Number.isFinite(number)) {
    if (number > 0 && number <= 1) return `${Math.round(number * 100)}%`;
    return String(Math.round(number * 100) / 100);
  }
  return String(value);
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function setStatus(message, tone = "neutral") {
  requestStatus.textContent = message || "";
  requestStatus.dataset.tone = tone;
}

function setConfigStatus(message, tone = "neutral") {
  configStatus.textContent = message || "";
  configStatus.dataset.tone = tone;
}

function renderKeyValueList(items) {
  const list = el("dl", "kv-list");
  items
    .filter((item) => item.value !== undefined && item.value !== null && item.value !== "")
    .forEach((item) => {
      list.appendChild(el("dt", "", item.label));
      list.appendChild(el("dd", "", String(item.value)));
    });
  return list;
}

function renderSection(title, body, options = {}) {
  const section = el("section", `report-section${options.compact ? " compact" : ""}`);
  section.appendChild(el("h3", "", title));
  if (body instanceof Node) {
    section.appendChild(body);
  } else {
    section.appendChild(el("p", "muted", body || "暂无返回内容"));
  }
  return section;
}

function renderTextList(items, emptyText = "暂无返回内容") {
  const values = asArray(items).filter(Boolean);
  if (!values.length) return el("p", "muted", emptyText);

  const list = el("ul", "text-list");
  values.forEach((item) => {
    const listItem = el("li");
    if (typeof item === "string") {
      listItem.textContent = item;
    } else {
      listItem.textContent = firstValue(item, ["text", "summary", "point", "content"], JSON.stringify(item));
    }
    list.appendChild(listItem);
  });
  return list;
}

function getPatents(data) {
  const top = firstValue(data, ["top_patents"], null);
  const patents = firstValue(data, ["patents"], null);
  const results = firstValue(data, ["results"], null);
  if (Array.isArray(top)) return top;
  if (Array.isArray(patents)) return patents;
  if (patents && Array.isArray(patents.items)) return patents.items;
  if (Array.isArray(results)) return results;
  return [];
}

function appendPatentLink(container, patent) {
  const url = firstValue(patent, ["url", "link", "evidence_url", "patent_url", "google_patents_url", "patsnap_url"], "");
  if (!url) return;
  const link = el("a", "inline-link", "打开证据链接");
  link.href = url;
  link.target = "_blank";
  link.rel = "noreferrer";
  container.appendChild(link);
}

function renderPatents(data) {
  const patents = getPatents(data);
  if (!patents.length) return el("p", "muted", "暂无 Top 专利返回");

  const list = el("ol", "patent-list");
  patents.forEach((patent, index) => {
    const item = el("li", "patent-card");
    const title = firstValue(patent, ["title", "name", "publication_title", "invention_title"], "未命名专利");
    const number = firstValue(patent, ["publication_number", "publicationNumber", "pub_no", "patent_number", "number", "pn"], "");
    const applicant = textValue(firstValue(patent, ["applicant", "applicants", "assignee", "assignees", "owner"], ""));
    const inventor = textValue(firstValue(patent, ["inventor", "inventors", "inventor_names"], ""));
    const legalStatus = firstValue(patent, ["legal_status", "legalStatus", "status", "simple_legal_status"], "");
    const publicationDate = formatDate(firstValue(patent, ["publication_date", "publicationDate", "pub_date", "published_at"], ""));
    const applicationDate = formatDate(firstValue(patent, ["application_date", "applicationDate", "app_date", "filed_at"], ""));
    const score = formatScore(firstValue(patent, ["score", "similarity", "relevance", "relevance_score", "rank_score"], ""));
    const abstract = firstValue(patent, ["abstract", "summary", "snippet", "claim_snippet"], "");
    const evidence = firstValue(patent, ["evidence", "evidence_text", "match_reason", "reason"], "");

    const head = el("div", "patent-head");
    const titleWrap = el("div", "patent-title");
    titleWrap.appendChild(el("span", "patent-rank", `#${index + 1}`));
    titleWrap.appendChild(el("strong", "", title));
    head.appendChild(titleWrap);
    if (score !== "") head.appendChild(el("span", "badge", `相关度 ${score}`));
    item.appendChild(head);

    item.appendChild(
      renderKeyValueList([
        { label: "公开号", value: number },
        { label: "申请人", value: applicant },
        { label: "发明人", value: inventor },
        { label: "法律状态", value: legalStatus },
        { label: "公开日", value: publicationDate },
        { label: "申请日", value: applicationDate },
      ]),
    );

    const evidenceText = evidenceSummary(evidence);
    if (abstract) item.appendChild(el("p", "patent-abstract", abstract));
    if (evidenceText) item.appendChild(el("p", "patent-evidence", `证据：${evidenceText}`));
    appendPatentLink(item, patent);
    list.appendChild(item);
  });
  return list;
}

function evidenceSummary(value) {
  const items = asArray(value).filter(Boolean);
  if (!items.length) return "";
  return items
    .slice(0, 3)
    .map((item) => {
      if (typeof item === "string") return item;
      const reason = firstValue(item, ["reason"], "");
      const field = firstValue(item, ["field", "source"], "");
      const text = firstValue(item, ["text", "snippet", "summary"], "");
      return [reason, field, text].filter(Boolean).join(" | ");
    })
    .filter(Boolean)
    .join("；");
}

function renderRiskSummary(data) {
  const risk = firstValue(data, ["risk_summary", "risk", "summary"], "");
  if (!risk || typeof risk === "string") return el("p", "muted", risk || "暂无风险摘要");

  const wrap = el("div", "risk_summary");
  wrap.appendChild(
    renderKeyValueList([
      { label: "等级", value: firstValue(risk, ["level", "risk_level"], "") },
      { label: "摘要", value: firstValue(risk, ["summary", "overview"], "") },
      { label: "不确定性", value: firstValue(risk, ["uncertainty"], "") },
      { label: "边界", value: firstValue(risk, ["disclaimer", "boundary"], "") },
    ]),
  );
  const points = firstValue(risk, ["risk_points", "points", "items"], []);
  if (asArray(points).length) wrap.appendChild(renderTextList(points));
  return wrap;
}

function renderEvidence(data) {
  const evidence = asArray(firstValue(data, ["evidence", "citations", "sources"], []));
  if (!evidence.length) return el("p", "muted", "暂无证据返回");

  const list = el("ul", "evidence-list");
  evidence.forEach((item) => {
    const listItem = el("li");
    if (typeof item === "string") {
      listItem.textContent = item;
    } else {
      const text = firstValue(item, ["text", "claim", "snippet", "summary"], "");
      const source = firstValue(item, ["source", "patent", "publication_number", "url"], "");
      const url = firstValue(item, ["url", "link"], "");
      listItem.textContent = [text, source].filter(Boolean).join(" | ") || JSON.stringify(item);
      if (url) {
        const link = el("a", "inline-link evidence-link", "打开");
        link.href = url;
        link.target = "_blank";
        link.rel = "noreferrer";
        listItem.appendChild(link);
      }
    }
    list.appendChild(listItem);
  });
  return list;
}

function countEvidence(data) {
  return asArray(firstValue(data, ["evidence", "citations", "sources"], [])).length;
}

function getRanking(data) {
  return asArray(firstValue(data, ["ranking"], [])).filter(Boolean);
}

function rankingSummary(data) {
  const ranking = getRanking(data);
  if (!ranking.length) return "";
  const head = ranking
    .slice(0, 3)
    .map((item) => {
      const rank = firstValue(item, ["rank"], "");
      const number = firstValue(item, ["number", "patent_number"], "");
      const title = firstValue(item, ["title"], "");
      const score = formatScore(firstValue(item, ["score"], ""));
      return [`#${rank || ""}`, number, title, score ? `相关度 ${score}` : ""].filter(Boolean).join(" · ");
    })
    .join("；");
  return `已生成 ${ranking.length} 条排序记录${head ? `：${head}` : ""}`;
}

function renderRanking(data) {
  const ranking = getRanking(data);
  if (!ranking.length) return el("p", "muted", "暂无排序依据");
  const list = el("ol", "ranking-list");
  ranking.slice(0, 10).forEach((item) => {
    const listItem = el("li", "ranking-item");
    const title = firstValue(item, ["title"], "未命名专利");
    const number = firstValue(item, ["number", "patent_number"], "");
    const score = formatScore(firstValue(item, ["score"], ""));
    listItem.appendChild(el("strong", "", [number, title].filter(Boolean).join(" | ")));
    if (score) listItem.appendChild(el("span", "badge", `相关度 ${score}`));
    const basis = asArray(firstValue(item, ["basis", "reasons"], []));
    if (basis.length) listItem.appendChild(renderTextList(basis.slice(0, 3)));
    list.appendChild(listItem);
  });
  return list;
}

function renderStatusSummary(data, requestPayload) {
  const traceId = firstValue(data, ["trace_id", "traceId", "request_id"], "");
  const status = firstValue(data, ["status"], data.ok === false ? "失败" : "完成");
  const patents = getPatents(data);
  const summary = el("section", "status-summary");
  summary.appendChild(el("h2", "", "结果状态"));
  summary.appendChild(
    renderKeyValueList([
      { label: "状态", value: status },
      { label: "模式", value: MODE_META[requestPayload.mode]?.label || requestPayload.mode },
      { label: "专利数", value: patents.length },
      { label: "证据数", value: countEvidence(data) },
      { label: "排序", value: rankingSummary(data) },
      { label: "通道", value: firstValue(data, ["channel", "tool"], "") },
      { label: "trace_id", value: traceId },
    ]),
  );
  return summary;
}

function renderTaskCard(data, requestPayload) {
  const task = firstValue(data, ["task", "task_card"], {});
  const card = el("section", "task_card");
  card.appendChild(el("h2", "", firstValue(task, ["title", "name"], "任务卡")));
  card.appendChild(
    renderKeyValueList([
      { label: "检索模式", value: firstValue(task, ["mode"], MODE_META[requestPayload.mode]?.label || requestPayload.mode) },
      { label: "返回条数", value: firstValue(task, ["limit"], requestPayload.limit) },
      { label: "检索式", value: firstValue(data, ["query_text", "query", "search_query"], "") },
      { label: "意图", value: textValue(firstValue(task, ["intents", "intent"], "")) },
      { label: "关键词", value: textValue(firstValue(task, ["key_terms", "keywords"], "")) },
    ]),
  );
  const question = firstValue(task, ["question"], requestPayload.question);
  if (question) card.appendChild(el("p", "task_question", question));
  return card;
}

function classifyError(message, status) {
  const combined = `${status || ""} ${message || ""}`;
  const matched = ERROR_HINTS.find((hint) => hint.pattern.test(combined));
  if (matched) return matched;
  if (status >= 500) return { label: "工具调用错误", advice: "服务端或上游工具返回异常，请稍后重试并保留 trace_id。" };
  if (status === 401) return ERROR_HINTS[1];
  if (status === 403) return ERROR_HINTS[2];
  return { label: "请求错误", advice: "请检查输入是否为空、检索式是否过长，或稍后重试。" };
}

function renderError(error, details = {}) {
  emptyState.classList.add("hidden");
  report.classList.remove("hidden");
  clearNode(report);

  const category = classifyError(error.message, details.status);
  const panel = el("section", "error-panel");
  panel.appendChild(el("h2", "", category.label));
  panel.appendChild(el("p", "", error.message || "请求失败，请检查服务状态。"));
  panel.appendChild(el("p", "muted", category.advice));
  if (details.traceId) panel.appendChild(el("p", "trace", `trace_id: ${details.traceId}`));
  if (details.status) panel.appendChild(el("p", "muted", `HTTP 状态：${details.status}`));
  report.appendChild(panel);
}

function renderReport(data, requestPayload) {
  emptyState.classList.add("hidden");
  report.classList.remove("hidden");
  clearNode(report);

  report.appendChild(renderStatusSummary(data, requestPayload));
  report.appendChild(renderTaskCard(data, requestPayload));
  report.appendChild(renderSection("Top 专利", renderPatents(data)));
  report.appendChild(renderSection("排序依据", renderRanking(data)));
  report.appendChild(renderSection("相似点", renderTextList(firstValue(data, ["similarities", "similar_points"], []))));
  report.appendChild(renderSection("差异点", renderTextList(firstValue(data, ["differences", "different_points"], []))));
  report.appendChild(renderSection("风险摘要", renderRiskSummary(data)));
  report.appendChild(renderSection("证据", renderEvidence(data)));
  report.appendChild(renderSection("下一步追问", renderTextList(firstValue(data, ["next_questions", "follow_up_questions", "questions"], []))));
}

function updateModeHelp() {
  const current = MODE_META[modeInput.value] || MODE_META.balanced;
  modeDescription.textContent = current.description;
  clearNode(modeHelp);
  Object.entries(MODE_META).forEach(([, meta]) => {
    modeHelp.appendChild(el("dt", "", meta.label));
    modeHelp.appendChild(el("dd", "", meta.description));
  });
}

function fillExample(name) {
  const example = EXAMPLES[name];
  if (!example) return;
  questionInput.value = example.question;
  modeInput.value = example.mode;
  limitInput.value = example.limit;
  contextInput.value = example.context;
  updateModeHelp();
  questionInput.focus();
  setStatus("已填入示例，可以直接生成或继续修改。", "success");
}

function renderConfig(config) {
  const patent = config.patent_search || {};
  const novelty = config.novelty_search || {};
  configMainUrl.value = patent.base_url || "https://connect.zhihuiya.com/2b0355/logic-mcp";
  configNoveltyUrl.value = novelty.base_url || "https://connect.zhihuiya.com/bec69d/mcp";
  configMainKey.value = "";
  configNoveltyKey.value = "";
  const patentReady = Boolean(patent.key_configured || patent.has_api_key);
  const noveltyReady = Boolean(novelty.key_configured || novelty.has_api_key);
  const patentText = patentReady ? "专利搜索已配置" : "专利搜索未配置 key";
  const noveltyText = noveltyReady ? "查新通道已配置" : "查新通道未配置 key";
  configSummary.textContent = `${patentText}；${noveltyText}。已保存的 key 不会在页面回显。`;
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    const config = await response.json();
    renderConfig(config);
    setConfigStatus("本地配置已读取。", "success");
  } catch (error) {
    setConfigStatus("读取配置失败，服务可能未启动。", "error");
  }
}

async function saveConfig() {
  saveConfigButton.disabled = true;
  setConfigStatus("正在保存到本地 .env.local 并检测连接...", "loading");
  try {
    const payload = {
      zhihuiya_mcp_url: configMainUrl.value.trim(),
      zhihuiya_mcp_api_key: configMainKey.value.trim(),
      zhihuiya_novelty_mcp_url: configNoveltyUrl.value.trim(),
      zhihuiya_novelty_mcp_api_key: configNoveltyKey.value.trim(),
    };
    const response = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(firstValue(data, ["error", "detail"], "保存失败"));
    renderConfig(data.config || {});
    const channels = data.health?.channels || {};
    const connected = Object.values(channels).filter((item) => item.connectable).length;
    setConfigStatus(`已保存，${connected} 个 MCP 通道可连接。`, connected ? "success" : "error");
  } catch (error) {
    setConfigStatus(error.message || "保存失败。", "error");
  } finally {
    saveConfigButton.disabled = false;
  }
}

async function runSelfTest() {
  selfTestButton.disabled = true;
  setConfigStatus("正在跑内置自检：健康检查、人物检索、专家检索式...", "loading");
  try {
    const response = await fetch("/api/self-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cases: ["tsinghua", "raw", "hydrogen"], limit: 3 }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(`自检接口失败：${response.status}`);
    const passed = asArray(data.results).filter((item) => item.ok).length;
    const total = asArray(data.results).length;
    setConfigStatus(`自检完成：${passed}/${total} 通过。${data.trace_id ? `trace_id ${data.trace_id}` : ""}`, data.ok ? "success" : "error");
  } catch (error) {
    setConfigStatus(error.message || "自检失败。", "error");
  } finally {
    selfTestButton.disabled = false;
  }
}

document.querySelectorAll(".example-button").forEach((button) => {
  button.addEventListener("click", () => fillExample(button.dataset.example));
});

saveConfigButton.addEventListener("click", saveConfig);
selfTestButton.addEventListener("click", runSelfTest);
modeInput.addEventListener("change", updateModeHelp);
updateModeHelp();
loadConfig();

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    question: questionInput.value.trim(),
    mode: modeInput.value,
    limit: Number(limitInput.value || 10),
    context: contextInput.value.trim(),
  };
  if (!payload.question) {
    setStatus("请先输入技术方案、申请人或检索式。", "error");
    questionInput.focus();
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = "生成中...";
  setStatus("正在调用 /api/intelligence，请稍候。", "loading");

  try {
    const response = await fetch("/api/intelligence", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json()
      : { error: await response.text() };

    if (!response.ok || data.ok === false) {
      const message = firstValue(data, ["error", "detail", "message"], `接口返回失败：${response.status}`);
      throw Object.assign(new Error(message), {
        status: response.status,
        traceId: firstValue(data, ["trace_id", "traceId", "request_id"], ""),
      });
    }

    renderReport(data, payload);
    setStatus("结果已生成。", "success");
  } catch (error) {
    renderError(error, { status: error.status, traceId: error.traceId });
    setStatus("请求失败，详情见右侧错误提示。", "error");
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "生成结果报告";
  }
});
