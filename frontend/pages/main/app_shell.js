import { bindGlobalDropGuard } from "/frontend/assets/js/core/dropzones.js?v=4.5";
import {
  bindNavigation,
  showFeature,
} from "/frontend/assets/js/core/feature_loader.js?v=6.0";

const startupParams = new URLSearchParams(window.location.search);
const warmStart = startupParams.get("startup_cache") === "1";
const assetVersion = startupParams.get("asset_version") || "6.0";

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

async function initializeApplication() {
  bindGlobalDropGuard();
  bindNavigation();
  await showFeature("merge");

  document.querySelector("#appStartup")?.remove();
  document.querySelector("#windowTabs")?.remove();
  document.querySelector("#windowWorkspaceHost")?.remove();
  document.body.classList.remove("shell-loading", "tab-shell");
  document.querySelector(".app-frame")?.removeAttribute("hidden");

  notifyDesktopReadyWhenBridgeExists(false);

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
