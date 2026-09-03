const POLL_INTERVAL_MS = 500;

function makeId() {
  return globalThis.crypto?.randomUUID?.() || `job-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function duration(seconds) {
  const value = Math.max(0, Math.round(seconds || 0));
  if (value < 60) return `${value}s`;
  return `${Math.floor(value / 60)}m ${value % 60}s`;
}

export function renderProgress(element, state, fallback = "Processing locally…") {
  if (!element) return;
  const percent = Number.isFinite(state.percent) ? Math.max(0, Math.min(100, state.percent)) : null;
  const stage = state.stage || fallback;
  const elapsed = state.elapsed_seconds || 0;
  const eta = percent > 2 && percent < 100 ? (elapsed / percent) * (100 - percent) : null;
  element.className = "status progress-status";
  element.replaceChildren();

  const heading = document.createElement("div");
  heading.className = "progress-heading";
  const spinner = document.createElement("span");
  spinner.className = state.status === "complete" ? "progress-check" : "progress-spinner";
  spinner.textContent = state.status === "complete" ? "✓" : "";
  const label = document.createElement("strong");
  label.textContent = state.operation || fallback;
  const value = document.createElement("span");
  value.textContent = percent === null ? "Working" : `${Math.round(percent)}%`;
  heading.append(spinner, label, value);

  const track = document.createElement("div");
  track.className = `progress-track${percent === null ? " indeterminate" : ""}`;
  const bar = document.createElement("span");
  if (percent !== null) bar.style.width = `${percent}%`;
  track.append(bar);

  const detail = document.createElement("div");
  detail.className = "progress-detail";
  detail.textContent = state.detail ? `${stage} — ${state.detail}` : stage;
  const metrics = document.createElement("div");
  metrics.className = "progress-metrics";
  metrics.textContent = `Elapsed ${duration(elapsed)}${eta ? ` • ETA ~${duration(eta)}` : " • Engine is responding"}`;
  element.append(heading, track, detail, metrics);
}

export function startProgressTracking(endpoint, element, fallback, onComplete = null) {
  const id = makeId();
  let stopped = false;
  const localStarted = Date.now();
  renderProgress(element, { stage: fallback, elapsed_seconds: 0, status: "running" }, fallback);

  const stop = () => {
    stopped = true;
    window.clearInterval(timer);
  };
  const poll = async () => {
    if (stopped) return;
    try {
      const response = await fetch(`/api/progress/${encodeURIComponent(id)}`, { cache: "no-store" });
      const state = await response.json();
      if (state.status !== "pending") renderProgress(element, state, fallback);
      if (state.status === "complete") {
        stop();
        onComplete?.();
      }
    } catch {
      renderProgress(element, {
        stage: fallback,
        detail: "Waiting for the local engine",
        elapsed_seconds: (Date.now() - localStarted) / 1000,
        status: "running",
      }, fallback);
    }
  };
  const timer = window.setInterval(poll, POLL_INTERVAL_MS);
  poll();
  return {
    id,
    headers: { "X-Progress-ID": id },
    endpoint: `${endpoint}${endpoint.includes("?") ? "&" : "?"}progress_id=${encodeURIComponent(id)}`,
    stop,
  };
}
