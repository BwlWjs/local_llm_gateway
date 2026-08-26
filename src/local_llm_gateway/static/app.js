const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function api(path, opts = {}) {
  return fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  }).then(async (r) => {
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const d = data && data.detail;
      throw new Error(typeof d === "string" ? d : JSON.stringify(d || data));
    }
    return data;
  });
}

// 兼容非 secure context（http://192.168.x.x 下 navigator.clipboard 不可用）
function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    document.execCommand("copy");
    return Promise.resolve();
  } catch (e) {
    return Promise.reject(e);
  } finally {
    document.body.removeChild(ta);
  }
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((el) => el.classList.add("hidden"));
  const el = $(`#tab-${name}`);
  if (el) el.classList.remove("hidden");
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
}

async function loadKeys() {
  const keys = await api("/api/v1/keys");
  $("#key-list").innerHTML = keys
    .map((k) => `<tr>
      <td>${esc(k.name)}</td>
      <td><code>${esc(k.prefix)}</code></td>
      <td>${esc((k.scopes || []).join(", "))}</td>
      <td>${esc(k.status)}</td>
      <td>${esc(k.created_at)}</td>
      <td><button data-revoke="${esc(k.id)}">吊销</button></td>
    </tr>`)
    .join("");
  document.querySelectorAll("[data-revoke]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api(`/api/v1/keys/${btn.dataset.revoke}`, { method: "DELETE" });
        loadKeys();
      } catch (err) {
        alert(err.message);
      }
    });
  });
}

async function loadModels() {
  const models = await api("/api/v1/models");
  $("#model-list").innerHTML = models
    .map((m) => `<tr><td><code>${esc(m.id)}</code></td><td>${esc(m.display_name)}</td><td>${esc(m.provider)}</td></tr>`)
    .join("");
}

async function loadStatus() {
  const s = await api("/api/v1/status");
  $("#status-box").textContent = JSON.stringify(s, null, 2);
}

async function loadConnect() {
  const origin = window.location.origin;
  const openaiBase = `${origin}/v1`;
  let models = [];
  try {
    models = await api("/api/v1/models");
  } catch (_) {
    models = [];
  }

  const rows = [
    ["API 地址", origin],
    ["OpenAI base (/v1)", openaiBase],
    ["协议（推荐）", "anthropic-message"],
    ["鉴权方式", "x-api-key: <key> 或 Authorization: Bearer <key>"],
  ];
  if (models.length) rows.push(["模型 ID", models.map((m) => m.id).join(", ")]);

  $("#connect-info").innerHTML = rows
    .map(
      ([label, value], i) => `
      <div class="info-row">
        <div class="info-label">${esc(label)}</div>
        <code class="info-value" id="cv-${i}">${esc(value)}</code>
        <button class="copy-btn" data-copy="cv-${i}">复制</button>
      </div>`
    )
    .join("");

  const md = [
    "# ModelRelay 接入配置",
    "",
    `- **API 地址**: \`${origin}\``,
    `- **OpenAI base**: \`${openaiBase}\``,
    "- **协议**: `anthropic-message`（推荐，流式完整）",
    "- **鉴权**: `x-api-key: <key>` 或 `Authorization: Bearer <key>`",
    ...(models.length ? [`- **模型 ID**: \`${models.map((m) => m.id).join("`, `")}\``] : []),
    "",
    "## 发 key",
    "",
    "```bash",
    `curl -X POST ${origin}/api/v1/keys \\`,
    "  -H 'Content-Type: application/json' \\",
    "  -d '{\"name\":\"agent\"}'",
    "```",
  ].join("\n");
  $("#conn-markdown").textContent = md;
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".copy-btn");
  if (!btn) return;
  const target = document.getElementById(btn.dataset.copy);
  if (!target) return;
  copyText(target.textContent)
    .then(() => {
      const old = btn.textContent;
      btn.textContent = "已复制";
      setTimeout(() => {
        btn.textContent = old;
      }, 1200);
    })
    .catch(() => alert("复制失败，请手动复制"));
});

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  $("#key-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("#key-name").value.trim() || "default";
    try {
      const resp = await api("/api/v1/keys", { method: "POST", body: JSON.stringify({ name }) });
      const box = $("#key-created");
      box.classList.remove("hidden");
      box.textContent = `Key 已创建（只显示这一次）：${resp.key}`;
      $("#key-name").value = "";
      loadKeys();
    } catch (err) {
      alert(err.message);
    }
  });
  switchTab("keys");
  loadKeys().catch((e) => alert(e.message));
  loadModels().catch((e) => alert(e.message));
  loadStatus().catch((e) => alert(e.message));
  loadConnect().catch((e) => alert(e.message));
});
