// Telegram WebApp setup
const tg = window.Telegram?.WebApp;
tg?.ready?.();
tg?.expand?.();

const INIT_DATA = tg?.initData || "";

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": INIT_DATA,
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

document.querySelectorAll("nav#tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    loadTab(btn.dataset.tab);
  });
});

let channelsCache = [];

async function loadChannels() {
  channelsCache = await api("/api/channels");
  for (const id of ["create-channel", "settings-channel"]) {
    const sel = document.getElementById(id);
    if (!sel) continue;
    sel.innerHTML = channelsCache
      .map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
      .join("");
  }
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

const STATUS_LABEL = {
  draft: "черновик",
  pending_approval: "на модерации",
  approved: "одобрено",
  published: "опубликовано",
  rejected: "отклонено",
  deleted: "удалено",
};

function postStatusBadge(p) {
  return `<span class="badge ${p.status}">${STATUS_LABEL[p.status] || p.status}</span>`;
}

function renderPost(p) {
  const channel = channelsCache.find((c) => c.id === p.channel_id);
  return `
    <div class="list-item" data-post-id="${p.id}">
      <div class="meta">#${p.id} · ${escapeHtml(channel?.name || "")} · ${postStatusBadge(p)}
        ${p.scheduled_at ? `· запланировано ${new Date(p.scheduled_at).toLocaleString()}` : ""}
        ${p.published_at ? `· опубликовано ${new Date(p.published_at).toLocaleString()}` : ""}
      </div>
      <div>${escapeHtml((p.text || "").slice(0, 240))}${(p.text || "").length > 240 ? "…" : ""}</div>
      <div class="actions"></div>
    </div>`;
}

async function loadDashboard() {
  const d = await api("/api/dashboard");
  document.getElementById("stat-channels").textContent = d.channels;
  document.getElementById("stat-today").textContent = d.posts_today;
  document.getElementById("stat-queue").textContent = d.queue;
  document.getElementById("stat-pending").textContent = d.pending_approval;
  document.getElementById("recent-list").innerHTML = d.recent.map(renderPost).join("");
}

async function loadScheduledList() {
  const posts = await api("/api/posts?status_filter=approved&limit=50");
  const scheduled = posts.filter((p) => p.scheduled_at && !p.published_at);
  const node = document.getElementById("scheduled-list");
  node.innerHTML = scheduled.map((p) => renderPost(p)).join("");
  scheduled.forEach((p) => {
    const item = node.querySelector(`[data-post-id="${p.id}"] .actions`);
    if (!item) return;
    item.innerHTML = `<button class="del">Удалить</button>`;
    item.querySelector(".del").addEventListener("click", async () => {
      if (!confirm("Удалить этот пост?")) return;
      await api(`/api/posts/${p.id}`, { method: "DELETE" });
      loadScheduledList();
    });
  });
}

async function loadModeration() {
  const pending = await api("/api/posts?status_filter=pending_approval&limit=50");
  const queue = document.getElementById("moderation-queue");
  queue.innerHTML = pending.map(renderPost).join("") || "<em>Пусто</em>";
  pending.forEach((p) => {
    const actions = queue.querySelector(`[data-post-id="${p.id}"] .actions`);
    if (!actions) return;
    actions.innerHTML = `<button class="ok primary">Одобрить</button><button class="no">Отклонить</button>`;
    actions.querySelector(".ok").addEventListener("click", async () => {
      await api(`/api/posts/${p.id}/approve`, { method: "POST" });
      loadModeration();
    });
    actions.querySelector(".no").addEventListener("click", async () => {
      await api(`/api/posts/${p.id}/reject`, { method: "POST" });
      loadModeration();
    });
  });

  const log = await api("/api/moderation/log?limit=50");
  document.getElementById("moderation-log").innerHTML =
    log
      .map(
        (m) => `
      <div class="list-item">
        <div class="meta">#${m.id} · ${m.action} · ${m.triggered_by} · ${new Date(m.created_at).toLocaleString()}</div>
        <div>${escapeHtml(m.reason || "—")}${m.post_id ? ` · пост #${m.post_id}` : ""}</div>
      </div>`
      )
      .join("") || "<em>Пусто</em>";
}

async function loadSettings() {
  const sel = document.getElementById("settings-channel");
  if (!sel.value && channelsCache[0]) sel.value = channelsCache[0].id;
  const channelId = parseInt(sel.value);
  if (!channelId) return;
  const ch = await api(`/api/channels/${channelId}`);
  document.getElementById("settings-prompt").value = ch.system_prompt || "";
  document.getElementById("set-approval").checked = !!ch.settings.approval_required;
  document.getElementById("set-autopost").checked = !!ch.settings.auto_post;
  document.getElementById("set-autodelete").checked = !!ch.settings.auto_delete;
  document.getElementById("set-stopwords").value = (ch.settings.stopwords || []).join("\n");
  document.getElementById("set-model").value = ch.settings.ai_model || "";

  const slots = await api(`/api/channels/${channelId}/slots`);
  const list = document.getElementById("slots-list");
  list.innerHTML =
    slots
      .map(
        (s) => `
      <div class="list-item">
        <div class="meta">${s.enabled ? "вкл" : "выкл"} · ${s.time_of_day} · дни [${s.days_of_week.join(",") || "все"}]</div>
        <div class="actions"><button class="del" data-id="${s.id}">Удалить</button></div>
      </div>`
      )
      .join("") || "<em>Слотов нет</em>";
  list.querySelectorAll(".del").forEach((b) => {
    b.addEventListener("click", async () => {
      await api(`/api/slots/${b.dataset.id}`, { method: "DELETE" });
      loadSettings();
    });
  });
}

async function loadTab(name) {
  try {
    if (name === "dashboard") return loadDashboard();
    if (name === "create") {
      await loadScheduledList();
    }
    if (name === "moderation") return loadModeration();
    if (name === "settings") return loadSettings();
  } catch (e) {
    console.error(e);
    alert(e.message);
  }
}

document.getElementById("btn-ai").addEventListener("click", async () => {
  const channelId = parseInt(document.getElementById("create-channel").value);
  const topic = document.getElementById("create-topic").value.trim();
  if (!channelId || !topic) {
    alert("Выберите канал и укажите тему.");
    return;
  }
  try {
    const r = await api("/api/ai/generate", {
      method: "POST",
      body: JSON.stringify({ channel_id: channelId, topic }),
    });
    document.getElementById("create-text").value = r.text;
  } catch (e) {
    alert(e.message);
  }
});

document.getElementById("btn-improve").addEventListener("click", async () => {
  const channelId = parseInt(document.getElementById("create-channel").value);
  const text = document.getElementById("create-text").value;
  if (!text) return;
  try {
    const r = await api("/api/ai/generate", {
      method: "POST",
      body: JSON.stringify({ channel_id: channelId, topic: "", improve_text: text }),
    });
    document.getElementById("create-text").value = r.text;
  } catch (e) {
    alert(e.message);
  }
});

document.getElementById("btn-publish").addEventListener("click", async () => {
  const channelId = parseInt(document.getElementById("create-channel").value);
  const text = document.getElementById("create-text").value;
  const media_url = document.getElementById("create-media").value.trim() || null;
  const media_type = document.getElementById("create-media-type").value;
  const sched = document.getElementById("create-schedule").value;
  const scheduled_at = sched ? new Date(sched).toISOString() : null;
  try {
    await api("/api/posts", {
      method: "POST",
      body: JSON.stringify({
        channel_id: channelId,
        text,
        media_url,
        media_type,
        scheduled_at,
        publish_now: !scheduled_at,
        source: "manual",
      }),
    });
    document.getElementById("create-text").value = "";
    document.getElementById("create-media").value = "";
    document.getElementById("create-schedule").value = "";
    document.getElementById("create-topic").value = "";
    alert("Отправлено.");
    loadScheduledList();
  } catch (e) {
    alert(e.message);
  }
});

document.getElementById("settings-channel").addEventListener("change", loadSettings);

document.getElementById("btn-save-settings").addEventListener("click", async () => {
  const channelId = parseInt(document.getElementById("settings-channel").value);
  if (!channelId) return;
  const payload = {
    system_prompt: document.getElementById("settings-prompt").value,
    approval_required: document.getElementById("set-approval").checked,
    auto_post: document.getElementById("set-autopost").checked,
    auto_delete: document.getElementById("set-autodelete").checked,
    stopwords: document.getElementById("set-stopwords").value.split("\n").map((s) => s.trim()).filter(Boolean),
    ai_model: document.getElementById("set-model").value.trim() || null,
  };
  try {
    await api(`/api/channels/${channelId}`, { method: "PATCH", body: JSON.stringify(payload) });
    alert("Сохранено.");
  } catch (e) {
    alert(e.message);
  }
});

document.getElementById("btn-add-slot").addEventListener("click", async () => {
  const channelId = parseInt(document.getElementById("settings-channel").value);
  const t = document.getElementById("slot-time").value;
  const daysRaw = document.getElementById("slot-days").value.trim();
  if (!channelId || !t) {
    alert("Выберите канал и время.");
    return;
  }
  const days = daysRaw ? daysRaw.split(",").map((s) => parseInt(s.trim())).filter((n) => !Number.isNaN(n)) : [];
  try {
    await api(`/api/channels/${channelId}/slots`, {
      method: "POST",
      body: JSON.stringify({ time_of_day: t, days_of_week: days, enabled: true }),
    });
    document.getElementById("slot-time").value = "";
    document.getElementById("slot-days").value = "";
    loadSettings();
  } catch (e) {
    alert(e.message);
  }
});

(async () => {
  try {
    await loadChannels();
    await loadDashboard();
  } catch (e) {
    document.body.innerHTML = `<pre style="padding:16px">Ошибка инициализации: ${escapeHtml(e.message)}</pre>`;
  }
})();
