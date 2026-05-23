const form = document.querySelector("#intelligence-form");
const questionInput = document.querySelector("#question");
const modeInput = document.querySelector("#mode");
const limitInput = document.querySelector("#limit");
const contextInput = document.querySelector("#context");
const submitButton = document.querySelector("#submit-button");
const emptyState = document.querySelector("#empty-state");
const report = document.querySelector("#report");

const ERROR_HINTS = [
  { pattern: /config|配置|env|environment|api key|key/i, label: "配置错误" },
  { pattern: /auth|认证|unauthorized|401|token|bearer/i, label: "认证错误" },
  { pattern: /permission|权限|forbidden|403|scope/i, label: "权限错误" },
  { pattern: /tool|工具|mcp|client|connector|timeout/i, label: "工具错误" },
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
  if (Array.isArray(value)) return value.filter(Boolean).join("；");
  if (value && typeof value === "object") return JSON.stringify(value);
  return value === undefined || value === null ? "" : String(value);
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

function renderPatents(data) {
  const patents = asArray(firstValue(data, ["top_patents", "patents", "results"], []));
  if (!patents.length) return el("p", "muted", "暂无 Top 专利返回");

  const list = el("ol", "patent-list");
  patents.forEach((patent) => {
    const item = el("li", "patent-card");
    const title = firstValue(patent, ["title", "name", "publication_title"], "未命名专利");
    const number = firstValue(patent, ["publication_number", "patent_number", "number", "pn"], "");
    const applicant = textValue(firstValue(patent, ["applicant", "applicants", "assignee", "owner"], ""));
    const score = firstValue(patent, ["score", "similarity", "relevance"], "");
    const abstract = firstValue(patent, ["abstract", "summary", "snippet"], "");
    const url = firstValue(patent, ["url", "link", "google_patents_url"], "");

    const head = el("div", "patent-head");
    head.appendChild(el("strong", "", title));
    if (score !== "") head.appendChild(el("span", "badge", `相关度 ${score}`));
    item.appendChild(head);
    item.appendChild(
      renderKeyValueList([
        { label: "公开号", value: number },
        { label: "申请人", value: applicant },
      ]),
    );
    if (abstract) item.appendChild(el("p", "patent-abstract", abstract));
    if (url) {
      const link = el("a", "inline-link", "打开证据链接");
      link.href = url;
      link.target = "_blank";
      link.rel = "noreferrer";
      item.appendChild(link);
    }
    list.appendChild(item);
  });
  return list;
}

function renderRiskSummary(data) {
  const risk = firstValue(data, ["risk_summary", "risk", "summary"], "");
  if (!risk || typeof risk === "string") return el("p", "muted", risk || "暂无风险摘要");

  const wrap = el("div", "risk_summary");
  wrap.appendChild(
    renderKeyValueList([
      { label: "等级", value: firstValue(risk, ["level"], "") },
      { label: "摘要", value: firstValue(risk, ["summary"], "") },
      { label: "不确定性", value: firstValue(risk, ["uncertainty"], "") },
      { label: "边界", value: firstValue(risk, ["disclaimer"], "") },
    ]),
  );
  const points = firstValue(risk, ["risk_points", "points"], []);
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
      listItem.textContent = [text, source].filter(Boolean).join(" | ") || JSON.stringify(item);
    }
    list.appendChild(listItem);
  });
  return list;
}

function renderTaskCard(data, requestPayload) {
  const task = firstValue(data, ["task", "task_card"], {});
  const card = el("section", "task_card");
  card.appendChild(el("h2", "", firstValue(task, ["title", "name"], "任务卡")));
  card.appendChild(
    renderKeyValueList([
      { label: "检索模式", value: firstValue(task, ["mode"], requestPayload.mode) },
      { label: "返回条数", value: firstValue(task, ["limit"], requestPayload.limit) },
      { label: "检索式", value: firstValue(data, ["query_text", "query", "search_query"], "") },
      { label: "意图", value: textValue(firstValue(task, ["intents"], "")) },
      { label: "关键词", value: textValue(firstValue(task, ["key_terms"], "")) },
      { label: "状态", value: firstValue(data, ["status"], data.ok === false ? "失败" : "完成") },
    ]),
  );
  const question = firstValue(task, ["question"], requestPayload.question);
  if (question) card.appendChild(el("p", "task_question", question));
  return card;
}

function classifyError(message, status) {
  const combined = `${status || ""} ${message || ""}`;
  const matched = ERROR_HINTS.find((hint) => hint.pattern.test(combined));
  if (matched) return matched.label;
  if (status >= 500) return "工具错误";
  if (status === 401) return "认证错误";
  if (status === 403) return "权限错误";
  return "请求错误";
}

function renderError(error, details = {}) {
  emptyState.classList.add("hidden");
  report.classList.remove("hidden");
  clearNode(report);

  const category = classifyError(error.message, details.status);
  const panel = el("section", "error-panel");
  panel.appendChild(el("h2", "", category));
  panel.appendChild(el("p", "", error.message || "请求失败，请检查服务状态。"));
  if (details.traceId) panel.appendChild(el("p", "trace", `trace_id: ${details.traceId}`));
  if (details.status) panel.appendChild(el("p", "muted", `HTTP 状态：${details.status}`));
  report.appendChild(panel);
}

function renderReport(data, requestPayload) {
  emptyState.classList.add("hidden");
  report.classList.remove("hidden");
  clearNode(report);

  report.appendChild(renderTaskCard(data, requestPayload));
  report.appendChild(renderSection("Top 专利", renderPatents(data)));
  report.appendChild(renderSection("相似点", renderTextList(firstValue(data, ["similarities", "similar_points"], []))));
  report.appendChild(renderSection("差异点", renderTextList(firstValue(data, ["differences", "different_points"], []))));
  report.appendChild(renderSection("风险摘要", renderRiskSummary(data)));
  report.appendChild(renderSection("证据", renderEvidence(data)));
  report.appendChild(renderSection("下一步追问", renderTextList(firstValue(data, ["next_questions", "follow_up_questions", "questions"], []))));

  const traceId = firstValue(data, ["trace_id", "traceId", "request_id"], "");
  if (traceId) report.appendChild(renderSection("trace_id", traceId, { compact: true }));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    question: questionInput.value.trim(),
    mode: modeInput.value,
    limit: Number(limitInput.value || 10),
    context: contextInput.value.trim(),
  };
  if (!payload.question) return;

  submitButton.disabled = true;
  submitButton.textContent = "生成中...";

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
  } catch (error) {
    renderError(error, { status: error.status, traceId: error.traceId });
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "生成结果报告";
  }
});
