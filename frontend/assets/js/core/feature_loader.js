import { apiFetch } from "/frontend/assets/js/core/api.js";
import { $, $$ } from "/frontend/assets/js/core/dom.js";
import {
  bindDropzones,
  initializeSingleFileControls,
} from "/frontend/assets/js/core/dropzones.js";
import { FEATURES } from "./features.js?v=7.5";
import { clearPendingWorkflowTransfer, hydratePendingWorkflowTransfer } from "/frontend/assets/js/core/workflow_transfer.js";
import { resetAllFiles } from "/frontend/assets/js/core/file_store.js";
import { t, translateTree } from "/frontend/assets/js/core/i18n.js";

const featureResources = new Map();
const assetVersion = new URLSearchParams(window.location.search).get("asset_version") || "7.9";
let navigationGeneration = 0;

function bindCreateAnotherButton(panel, featureId) {
  if (panel.querySelector(".task-reset-button")) return;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn secondary task-reset-button";
  button.dataset.i18n = "createAnother";
  button.dataset.i18nFallback = "Create another one";
  button.dataset.i18nTitle = "createAnotherTitle";
  button.dataset.i18nTitleFallback = "Clear this task and start again";
  button.textContent = t("createAnother", "Create another one");
  button.title = t("createAnotherTitle", "Clear this task and start again");

  const primaryButtons = [...panel.querySelectorAll(".btn.primary")];
  const primary = primaryButtons.at(-1);
  const primaryIsHidden = primary?.closest(".hidden");
  let row = primaryIsHidden ? null : primary?.closest(".action-row");
  if (!row && primary?.parentElement && !primaryIsHidden) {
    row = document.createElement("div");
    row.className = "action-row task-action-row";
    primary.parentElement.insertBefore(row, primary);
    row.appendChild(primary);
  }
  if (!row) {
    row = document.createElement("div");
    row.className = "action-row task-action-row";
    panel.appendChild(row);
  }
  row.classList.add("task-action-row");
  row.appendChild(button);

  button.addEventListener("click", async () => {
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = t("resetting", "Resetting…");
    try {
      const response = await apiFetch("/api/workspace/reset", { method: "POST" });
      if (!response.ok) throw new Error(t("resetEngineError", "The local engine could not reset the task."));
      resetAllFiles();
      clearPendingWorkflowTransfer();
      await showFeature(featureId);
    } catch (error) {
      button.disabled = false;
      button.textContent = t("createAnother", "Create another one");
      button.title = t("createAnotherTitle", "Clear this task and start again");
      const status = panel.querySelector(".status") || panel.appendChild(document.createElement("div"));
      status.className = "status error";
      status.textContent = error?.message || t("resetError", "Could not reset this task.");
    }
  });
}

function versionedUrl(path) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("v", assetVersion);
  return url;
}

async function prepareFeature(featureId) {
  const feature = FEATURES[featureId];

  if (!feature) {
    throw new Error(
      `Unknown feature: ${featureId}`
    );
  }

  if (featureResources.has(featureId)) {
    return featureResources.get(featureId);
  }

  const response = await apiFetch(versionedUrl(feature.view), { cache: "force-cache" });

  if (!response.ok) {
    throw new Error(
      `Could not load ${feature.title} UI.`
    );
  }

  const html = await response.text();

  const controllerUrl = versionedUrl(feature.controller);

  const controller = await import(
    controllerUrl.href
  );

  const resources = { html, controller };
  featureResources.set(featureId, resources);
  return resources;
}


async function loadFeature(featureId, generation) {
  const feature = FEATURES[featureId];
  const { html, controller } = await prepareFeature(featureId);

  if (generation !== navigationGeneration) return null;

  const host = $("#featureHost");

  if (!host) {
    throw new Error(
      "Feature host #featureHost is missing."
    );
  }

  /*
   * IMPORTANT:
   * Only one feature panel may exist at a time.
   *
   * Do not append the new panel to old panels.
   * This prevents UI stacking when switching tools.
   */
  host.replaceChildren();

  host.insertAdjacentHTML(
    "afterbegin",
    html
  );

  /*
   * Preferred:
   * panel.html has id matching featureId.
   *
   * Fallback:
   * use the first .tool-panel and assign its ID.
   * This also protects older/newer panels whose ID
   * was accidentally omitted.
   */
  let panel = $(
    `#featureHost #${featureId}`
  );

  if (!panel) {
    panel = $(
      "#featureHost .tool-panel"
    );
  }

  if (!panel) {
    throw new Error(
      `Feature panel ${featureId} is missing.`
    );
  }

  if (!panel.id) {
    panel.id = featureId;
  }

  panel.classList.add("active");

  bindDropzones(panel);

  initializeSingleFileControls(
    panel
  );

  if (
    typeof controller.init === "function"
  ) {
    await controller.init(
      panel
    );
  }

  try {
    await hydratePendingWorkflowTransfer(featureId, panel);
  } catch (error) {
    const notice = document.createElement("div");
    notice.className = "status error workflow-transfer-error";
    notice.textContent = error?.message || "The temporary workflow PDF could not be loaded.";
    panel.prepend(notice);
  }

  translateTree(panel);
  bindCreateAnotherButton(panel, featureId);

  return panel;
}

function renderFeatureFailure(featureId, error) {
  const host = $("#featureHost");
  if (!host) return;
  const panel = document.createElement("section");
  panel.className = "tool-panel active feature-load-failure";
  const heading = document.createElement("h2");
  heading.textContent = `${t(`feature.${featureId}`, FEATURES[featureId]?.title || featureId)} ${t("featureLoadFailed", "could not open")}`;
  const detail = document.createElement("p");
  detail.textContent = error?.message || String(error);
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "btn primary";
  retry.textContent = t("retryFeature", "Retry feature");
  retry.addEventListener("click", () => showFeature(featureId));
  panel.append(heading, detail, retry);
  host.replaceChildren(panel);
}


export async function showFeature(
  featureId
) {
  const generation = ++navigationGeneration;
  const selectedButton = $(`.nav-tool[data-tool="${featureId}"]`);
  selectedButton?.classList.add("loading");
  let panel;
  try {
    panel = await loadFeature(featureId, generation);
  } catch (error) {
    if (generation !== navigationGeneration) return null;
    renderFeatureFailure(featureId, error);
    const title = $("#toolTitle");
    if (title) title.textContent = "Feature failed to load";
    throw error;
  } finally {
    selectedButton?.classList.remove("loading");
  }

  if (!panel || generation !== navigationGeneration) return null;

  /*
   * Defensive:
   * although only one panel should exist,
   * make sure no stale panel can stay active.
   */
  $$("#featureHost .tool-panel")
    .forEach((candidate) => {
      candidate.classList.toggle(
        "active",
        candidate === panel
      );
    });

  const title = $("#toolTitle");

  if (title) {
    title.textContent =
      t(`feature.${featureId}`, FEATURES[featureId]?.title)
      || featureId;
  }

  $$(".nav-tool").forEach(
    (button) => {
      button.classList.toggle(
        "active",
        button.dataset.tool === featureId
      );
    }
  );

  return panel;
}


export function bindNavigation() {
  $$(".category-toggle").forEach(
    (button) => {
      button.addEventListener(
        "click",
        () => {
          button
            .closest(".category")
            ?.classList
            .toggle("open");
        }
      );
    }
  );

  $$(".nav-tool").forEach(
    (button) => {
      button.addEventListener(
        "click",
        () => {
          const featureId =
            button.dataset.tool;

          if (!featureId) {
            return;
          }

          showFeature(
            featureId
          ).catch((error) => {
            console.error(error);

            const title =
              $("#toolTitle");

            if (title) {
              title.textContent =
                "Feature failed to load";
            }
          });
        }
      );
    }
  );
}

document.addEventListener("pdf-workbench:locale-change", () => {
  translateTree(document);
  const active = document.querySelector(".nav-tool.active")?.dataset.tool;
  const title = document.querySelector("#toolTitle");
  if (title && active) title.textContent = t(`feature.${active}`, FEATURES[active]?.title || active);
});
