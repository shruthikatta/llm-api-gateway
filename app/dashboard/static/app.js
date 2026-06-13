const state = {
  apiKey: localStorage.getItem("gateway_api_key") || "",
  days: 7,
  teams: [],
};

const views = {
  overview: { title: "Overview", subtitle: "Platform usage, cost, and latency" },
  teams: { title: "Teams & Budget", subtitle: "Spend, limits, and per-team usage" },
  providers: { title: "Providers", subtitle: "Health, latency, and circuit breakers" },
  audit: { title: "Audit Log", subtitle: "Administrative changes" },
  alerts: { title: "Alerts", subtitle: "Slack webhook and threshold configuration" },
};

function $(id) {
  return document.getElementById(id);
}

function showError(message) {
  const banner = $("error-banner");
  banner.textContent = message;
  banner.classList.remove("hidden");
}

function clearError() {
  $("error-banner").classList.add("hidden");
}

async function api(path, options = {}) {
  if (!state.apiKey) {
    throw new Error("Connect with an admin API key first.");
  }
  const response = await fetch(path, {
    ...options,
    headers: {
      Authorization: `Bearer ${state.apiKey}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = body?.error?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response.json();
}

function formatUsd(value) {
  return `$${Number(value || 0).toFixed(4)}`;
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function renderStatCards(container, cards) {
  container.innerHTML = cards
    .map(
      (card) => `
      <div class="stat-card">
        <div class="label">${card.label}</div>
        <div class="value">${card.value}</div>
      </div>`
    )
    .join("");
}

function renderTable(container, columns, rows) {
  container.innerHTML = `
    <table>
      <thead><tr>${columns.map((c) => `<th>${c.label}</th>`).join("")}</tr></thead>
      <tbody>
        ${rows
          .map(
            (row) =>
              `<tr>${columns.map((c) => `<td>${c.render(row)}</td>`).join("")}</tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

function drawTimeseries(canvas, points) {
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 640;
  const height = canvas.height;
  canvas.width = width;
  ctx.clearRect(0, 0, width, height);

  if (!points.length) {
    ctx.fillStyle = "#93a4c7";
    ctx.fillText("No usage data for this period.", 16, 32);
    return;
  }

  const padding = 36;
  const maxRequests = Math.max(...points.map((p) => p.request_count), 1);
  const maxCost = Math.max(...points.map((p) => p.total_cost_usd), 0.0001);
  const step = (width - padding * 2) / Math.max(points.length - 1, 1);

  ctx.strokeStyle = "#5b8cff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = padding + index * step;
    const y = height - padding - (point.request_count / maxRequests) * (height - padding * 2);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.strokeStyle = "#3dd68c";
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = padding + index * step;
    const y = height - padding - (point.total_cost_usd / maxCost) * (height - padding * 2);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#93a4c7";
  ctx.font = "12px sans-serif";
  ctx.fillText("Blue: requests", padding, 18);
  ctx.fillText("Green: cost (USD)", padding + 120, 18);
}

async function loadOverview() {
  const [overview, timeseries, latency] = await Promise.all([
    api(`/v1/admin/analytics/overview?days=${state.days}`),
    api(`/v1/admin/analytics/timeseries?days=${state.days}`),
    api(`/v1/admin/analytics/latency?days=${state.days}`),
  ]);

  renderStatCards($("overview-stats"), [
    { label: "Requests", value: formatNumber(overview.request_count) },
    { label: "Success rate", value: overview.request_count ? `${((overview.success_count / overview.request_count) * 100).toFixed(1)}%` : "—" },
    { label: "Total tokens", value: formatNumber(overview.total_tokens) },
    { label: "Total cost", value: formatUsd(overview.total_cost_usd) },
    { label: "Avg latency", value: `${overview.avg_latency_ms.toFixed(1)} ms` },
    { label: "Active teams", value: `${overview.active_teams}/${overview.team_count}` },
  ]);

  drawTimeseries($("timeseries-chart"), timeseries.points);
  renderTable(
    $("top-models"),
    [
      { label: "Model", render: (row) => row.model },
      { label: "Requests", render: (row) => formatNumber(row.requests) },
      { label: "Cost", render: (row) => formatUsd(row.cost_usd) },
    ],
    overview.top_models
  );

  renderStatCards($("latency-stats"), [
    { label: "p50", value: `${latency.p50_ms.toFixed(1)} ms` },
    { label: "p95", value: `${latency.p95_ms.toFixed(1)} ms` },
    { label: "p99", value: `${latency.p99_ms.toFixed(1)} ms` },
  ]);
}

async function loadTeams() {
  const [teams, analytics] = await Promise.all([
    api("/v1/admin/teams"),
    api(`/v1/admin/analytics/teams?days=${state.days}`),
  ]);
  state.teams = teams;
  const analyticsById = Object.fromEntries(analytics.teams.map((t) => [t.team_id, t]));
  const container = $("team-list");
  container.innerHTML = "";

  for (const team of teams) {
    const budget = await api(`/v1/admin/teams/${team.id}/budget/dashboard`);
    const usage = analyticsById[team.id];
    const dailyPct = budget.daily_budget_usd
      ? Math.min(100, (budget.daily_spent_usd / budget.daily_budget_usd) * 100)
      : 0;

    const card = document.createElement("article");
    card.className = "panel";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
        <div>
          <h3 style="margin:0;">${team.name}</h3>
          <p class="muted" style="margin:4px 0 0;">${team.slug}</p>
        </div>
        <span class="status-pill ${budget.daily_warning || budget.monthly_warning ? "warn" : "ok"}">
          ${budget.daily_warning || budget.monthly_warning ? "Budget warning" : "Healthy"}
        </span>
      </div>
      <div class="budget-bar"><span style="width:${dailyPct}%"></span></div>
      <p class="muted">Daily spend ${formatUsd(budget.daily_spent_usd)} / ${formatUsd(budget.daily_budget_usd)}</p>
      <p class="muted">Monthly spend ${formatUsd(budget.monthly_spent_usd)} / ${formatUsd(budget.monthly_budget_usd)}</p>
      <p>Requests: ${formatNumber(usage?.request_count || 0)} · Tokens: ${formatNumber(usage?.total_tokens || 0)} · Cost: ${formatUsd(usage?.total_cost_usd || 0)}</p>
    `;
    container.appendChild(card);
  }
}

async function loadProviders() {
  const data = await api("/v1/admin/analytics/providers");
  const container = $("provider-cards");
  container.innerHTML = data.providers
    .map((provider) => {
      const healthy = provider.healthy && provider.circuit_state !== "open";
      const pill = healthy ? "ok" : provider.circuit_state === "open" ? "bad" : "warn";
      return `
        <article class="provider-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <h3 style="margin:0;">${provider.provider}</h3>
            <span class="status-pill ${pill}">${healthy ? "Healthy" : provider.circuit_state}</span>
          </div>
          <p class="muted" style="margin-top:12px;">Latency EMA: ${provider.latency_ms_ema.toFixed(1)} ms</p>
          <p class="muted">Error rate: ${(provider.error_rate * 100).toFixed(1)}%</p>
          <p class="muted">Circuit: ${provider.circuit_state}</p>
        </article>`;
    })
    .join("");
}

async function loadAudit() {
  const logs = await api("/v1/admin/audit-logs?limit=50");
  renderTable(
    $("audit-table"),
    [
      { label: "Time", render: (row) => new Date(row.created_at).toLocaleString() },
      { label: "Action", render: (row) => row.action },
      { label: "Resource", render: (row) => `${row.resource_type}:${row.resource_id}` },
      { label: "Details", render: (row) => JSON.stringify(row.details || {}) },
    ],
    logs
  );
}

async function loadAlerts() {
  const config = await api("/v1/admin/analytics/alerts/config");
  $("alert-config").innerHTML = `
    <p>Enabled: <strong>${config.enabled ? "Yes" : "No"}</strong></p>
    <p>Slack configured: <strong>${config.slack_configured ? "Yes" : "No"}</strong></p>
    <p>Budget warnings: <strong>${config.budget_warnings ? "On" : "Off"}</strong></p>
    <p>Circuit open alerts: <strong>${config.circuit_open_alerts ? "On" : "Off"}</strong></p>
    <p>Error rate threshold: <strong>${(config.error_rate_threshold * 100).toFixed(0)}%</strong></p>
  `;
}

async function refreshActiveView() {
  clearError();
  const active = document.querySelector(".nav-item.active")?.dataset.view || "overview";
  try {
    if (active === "overview") await loadOverview();
    if (active === "teams") await loadTeams();
    if (active === "providers") await loadProviders();
    if (active === "audit") await loadAudit();
    if (active === "alerts") await loadAlerts();
    $("connection-status").textContent = "Connected";
    $("connection-status").className = "muted";
  } catch (error) {
    showError(error.message);
    $("connection-status").textContent = "Connection failed";
  }
}

function switchView(viewName) {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewName);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${viewName}`);
  });
  const meta = views[viewName];
  $("view-title").textContent = meta.title;
  $("view-subtitle").textContent = meta.subtitle;
  refreshActiveView();
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

$("connect-btn").addEventListener("click", () => {
  state.apiKey = $("api-key").value.trim();
  localStorage.setItem("gateway_api_key", state.apiKey);
  refreshActiveView();
});

$("refresh-btn").addEventListener("click", refreshActiveView);
$("period-days").addEventListener("change", (event) => {
  state.days = Number(event.target.value);
  refreshActiveView();
});

$("test-alert-btn").addEventListener("click", async () => {
  try {
    const result = await api("/v1/admin/analytics/alerts/test", { method: "POST" });
    $("alert-result").textContent = result.message;
  } catch (error) {
    $("alert-result").textContent = error.message;
  }
});

if (state.apiKey) {
  $("api-key").value = state.apiKey;
  refreshActiveView();
}
