import { bindGlobalDropGuard } from "/frontend/assets/js/core/dropzones.js?v=4.5";
import {
  bindNavigation,
  showFeature,
} from "/frontend/assets/js/core/feature_loader.js?v=7.9";
import { getLocale, initI18n } from "/frontend/assets/js/core/i18n.js";

const startupParams = new URLSearchParams(window.location.search);
const warmStart = startupParams.get("startup_cache") === "1";
const assetVersion = startupParams.get("asset_version") || "7.9";
const initialTool = startupParams.get("tool") || "organize";
const SIDEBAR_STATE_KEY = "pdf-workbench.sidebar-collapsed";

const sleep = (milliseconds) => new Promise((resolve) => {
  window.setTimeout(resolve, milliseconds);
});

async function waitForEngine() {
  const label = document.querySelector("#appStartupLabel");
  let attempts = 0;
  let connectionFailures = 0;
  while (true) {
    try {
      const response = await fetch("/api/desktop-startup", {
        cache: "no-store",
        credentials: "same-origin",
      });
      // The regular FastAPI server does not need the desktop-only readiness
      // endpoint. A missing endpoint means the server already accepted the
      // page request, so it is ready for normal API calls.
      if (response.status === 404) return;
      if (response.ok) {
        connectionFailures = 0;
        const payload = await response.json();
        if (payload.status === "ready") return;
        if (payload.status === "error") {
          const error = new Error(payload.detail || "Application features failed to load.");
          error.startupFatal = true;
          throw error;
        }
      } else {
        connectionFailures += 1;
      }
    } catch (error) {
      if (error?.startupFatal) throw error;
      connectionFailures += 1;
      // The page itself is served by the engine, so repeated connection
      // failures after it painted mean the child process has exited.
      if (connectionFailures >= 3) {
        const failure = new Error("The local engine stopped during startup. Restart the app.");
        failure.startupFatal = true;
        throw failure;
      }
    }
    attempts += 1;
    if (label && attempts >= 8) {
      label.textContent = "Loading application features… still working locally.";
    }
    await sleep(Math.min(250 + attempts * 25, 750));
  }
}

async function notifyDesktopReady(markCache = false) {
  try {
    if (!window.pywebview?.api?.ui_ready) return false;
    if (markCache && window.pywebview.api.mark_startup_cache) {
      await window.pywebview.api.mark_startup_cache(assetVersion);
    }
    await window.pywebview.api.ui_ready();
    return true;
  } catch {
    return false;
  }
}

function notifyDesktopReadyWhenBridgeExists(markCache = false, attempt = 0) {
  notifyDesktopReady(markCache).then((sent) => {
    if (!sent && attempt < 40) {
      window.setTimeout(() => notifyDesktopReadyWhenBridgeExists(markCache, attempt + 1), 100);
    }
  });
}

function reportStartupErrorWhenBridgeExists(message, attempt = 0) {
  if (window.pywebview?.api?.report_startup_error) {
    window.pywebview.api.report_startup_error(message).catch(() => {});
  } else if (attempt < 40) {
    window.setTimeout(() => reportStartupErrorWhenBridgeExists(message, attempt + 1), 100);
  }
}

function showStartupFailure(error) {
  document.body.classList.remove("shell-loading");
  document.body.innerHTML = `<main class="startup-failure"><h1>Application startup failed</h1><p></p></main>`;
  const message = error?.message || String(error);
  document.querySelector(".startup-failure p").textContent = message;
  reportStartupErrorWhenBridgeExists(message);
}

let latestUpdatePayload = null;

function renderUpdateHistory(history, container) {
  if (!container || !Array.isArray(history) || !history.length) return;
  container.replaceChildren();
  const locale = getLocale();
  for (const release of history) {
    if (!release || typeof release !== "object") continue;
    const version = String(release.version || "").trim();
    if (!version) continue;
    const section = document.createElement("section");
    section.className = "update-release";
    const title = document.createElement("div");
    title.className = "update-release-title";
    title.textContent = `Version ${version}${release.date ? ` · ${release.date}` : ""}`;
    section.append(title);
    const list = document.createElement("ul");
    const localized = release.changes_i18n?.[locale]
      || release.changes_i18n?.en
      || release.changes;
    const changes = Array.isArray(localized) ? localized : [];
    for (const change of changes) {
      const item = document.createElement("li");
      item.textContent = String(change);
      list.append(item);
    }
    if (list.children.length) section.append(list);
    container.append(section);
  }
  container.hidden = !container.children.length;
}

function renderUpdateNoticeText(payload) {
  const text = document.querySelector("#updateNoticeText");
  const history = document.querySelector("#updateNoticeHistory");
  if (!text || !payload) return;
  if (getLocale() === "id") {
    text.textContent = `Versi ${payload.latest_version} tersedia (saat ini ${payload.current_version}).`;
  } else {
    text.textContent = `Version ${payload.latest_version} is available (current ${payload.current_version}).`;
  }
  renderUpdateHistory(payload.release_history, history);
}

async function checkForUpdates() {
  try {
    const response = await fetch("/api/update/check", {
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!response.ok) return;
    const payload = await response.json();

    const notice = document.querySelector("#updateNotice");
    const text = document.querySelector("#updateNoticeText");
    const link = document.querySelector("#updateNoticeLink");
    const dismiss = document.querySelector("#dismissUpdateNotice");
    if (!notice || !text) return;
    if (["disabled", "misconfigured"].includes(payload.status)) {
      const history = document.querySelector("#updateNoticeHistory");
      latestUpdatePayload = null;
      history?.replaceChildren();
      if (history) history.hidden = true;
      if (link) {
        link.hidden = true;
        link.removeAttribute("href");
      }
      text.textContent = getLocale() === "id"
        ? "Pemeriksaan update belum dikonfigurasi dengan benar pada build ini."
        : "Update checking is not configured correctly in this build.";
      dismiss?.addEventListener("click", () => {
        notice.hidden = true;
      }, { once: true });
      notice.hidden = false;
      return;
    }
    if (payload.status !== "available") return;

    dismiss?.addEventListener("click", () => {
      notice.hidden = true;
    }, { once: true });
    latestUpdatePayload = payload;
    renderUpdateNoticeText(payload);
    if (link && payload.installer_url) {
      link.href = payload.installer_url;
      link.hidden = false;
    }
    notice.hidden = false;
  } catch {
    // Update checks are optional and must never interrupt local startup.
  }
}

function bindSidebarToggle() {
  const frame = document.querySelector(".app-frame");
  const sidebarContent = document.querySelector(".sidebar-content");
  const toggle = document.querySelector("#sidebarToggle");
  const logo = document.querySelector("#sidebarLogo");
  const sidebarScroll = document.querySelector("#sidebarScroll");
  if (!frame || !toggle || !logo) return;

  let preservedScrollTop = sidebarScroll?.scrollTop || 0;
  let releaseWidthTimer = 0;
  const freezeContentLayer = () => {
    if (!sidebarContent) return;
    const width = sidebarContent.getBoundingClientRect().width;
    if (width <= 0) return;
    sidebarContent.style.width = `${width}px`;
    sidebarContent.style.minWidth = `${width}px`;
  };
  const releaseContentLayer = () => {
    window.clearTimeout(releaseWidthTimer);
    releaseWidthTimer = window.setTimeout(() => {
      if (frame.classList.contains("sidebar-collapsed") || !sidebarContent) return;
      sidebarContent.style.width = "";
      sidebarContent.style.minWidth = "";
    }, 340);
  };
  const setCollapsed = (collapsed) => {
    window.clearTimeout(releaseWidthTimer);
    if (collapsed) freezeContentLayer();
    if (collapsed && sidebarScroll) preservedScrollTop = sidebarScroll.scrollTop;
    frame.classList.toggle("sidebar-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Open sidebar" : "Close sidebar");
    toggle.title = collapsed ? "Open sidebar" : "Close sidebar";
    logo.setAttribute("aria-label", collapsed ? "Open sidebar" : "PDF Workbench");
    logo.title = collapsed ? "Open sidebar" : "PDF Workbench";
    try {
      window.localStorage.setItem(SIDEBAR_STATE_KEY, collapsed ? "1" : "0");
    } catch {
      // The layout still works when local storage is unavailable.
    }
    if (!collapsed && sidebarScroll) {
      window.requestAnimationFrame(() => {
        sidebarScroll.scrollTop = preservedScrollTop;
      });
      releaseContentLayer();
    }
  };

  let collapsed = false;
  try {
    collapsed = window.localStorage.getItem(SIDEBAR_STATE_KEY) === "1";
  } catch {
    // Use the expanded layout by default.
  }
  sidebarScroll?.addEventListener("scroll", () => {
    if (!frame.classList.contains("sidebar-collapsed")) {
      preservedScrollTop = sidebarScroll.scrollTop;
    }
  }, { passive: true });
  setCollapsed(collapsed);
  toggle.addEventListener("click", () => setCollapsed(!frame.classList.contains("sidebar-collapsed")));
  logo.addEventListener("click", () => {
    if (frame.classList.contains("sidebar-collapsed")) setCollapsed(false);
  });
}

async function initializeApplication() {
  await initI18n();
  document.addEventListener("pdf-workbench:locale-change", () => {
    if (latestUpdatePayload) renderUpdateNoticeText(latestUpdatePayload);
  });
  bindGlobalDropGuard();
  bindNavigation();
  bindSidebarToggle();
  await showFeature(initialTool);

  document.querySelector("#appStartup")?.remove();
  document.querySelector("#windowTabs")?.remove();
  document.querySelector("#windowWorkspaceHost")?.remove();
  document.body.classList.remove("shell-loading", "tab-shell");
  document.querySelector(".app-frame")?.removeAttribute("hidden");

  notifyDesktopReadyWhenBridgeExists(false);
  checkForUpdates();

  const engineBadge = document.querySelector(".header-pill");
  if (engineBadge) engineBadge.textContent = "Local engine loading…";
  window.__engineReadyPromise = waitForEngine()
    .then(() => {
      if (engineBadge) engineBadge.textContent = "Local engine ready";
      notifyDesktopReadyWhenBridgeExists(!warmStart);
      return true;
    })
    .catch((error) => {
      if (engineBadge) {
        engineBadge.textContent = "Local engine failed — restart the app";
        engineBadge.title = error?.message || String(error);
      }
      reportStartupErrorWhenBridgeExists(error?.message || String(error));
      console.error(error);
      return false;
    });
}

window.updateNativeHashProgress = (payload) => {
  window.postMessage(
    { type: "pdf-workbench-native-hash-progress", payload },
    window.location.origin,
  );
};

window.addEventListener("pywebviewready", () => notifyDesktopReadyWhenBridgeExists(false), { once: true });
initializeApplication().catch((error) => {
  console.error(error);
  showStartupFailure(error);
});
