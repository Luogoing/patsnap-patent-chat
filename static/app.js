const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const limitInput = document.querySelector("#limit");
const messages = document.querySelector("#messages");

function addMessage(role, text, extra = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}${extra.error ? " error" : ""}`;
  const body = document.createElement("p");
  body.textContent = text;
  article.appendChild(body);

  if (extra.queryText) {
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = `检索式：${extra.queryText}`;
    article.appendChild(meta);
  }

  if (extra.googleUrl) {
    const link = document.createElement("a");
    link.href = extra.googleUrl;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.className = "link";
    link.textContent = "在 Google Patents 中辅助查看";
    article.appendChild(link);
  }

  if (Array.isArray(extra.patents) && extra.patents.length > 0) {
    const list = document.createElement("ol");
    list.className = "result-list";
    extra.patents.forEach((patent) => {
      const item = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = patent.title || patent.number || "未命名专利结果";
      const desc = document.createElement("span");
      desc.textContent = [patent.number, patent.abstract].filter(Boolean).join(" - ");
      item.appendChild(title);
      item.appendChild(desc);
      list.appendChild(item);
    });
    article.appendChild(list);
  }

  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  addMessage("user", message);
  input.value = "";
  const button = form.querySelector("button");
  button.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        limit: Number(limitInput.value || 10),
      }),
    });
    const data = await response.json();
    addMessage("assistant", data.answer, {
      error: !data.ok,
      queryText: data.query_text,
      googleUrl: data.google_patents_url,
      patents: data.patents,
    });
  } catch (error) {
    addMessage("assistant", `请求失败：${error.message}`, { error: true });
  } finally {
    button.disabled = false;
    input.focus();
  }
});
