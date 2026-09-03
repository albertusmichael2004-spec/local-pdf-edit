import { apiFetch } from "./api.js";
import { $, $$ } from "./dom.js?v=4.5";
import {
  bindDropzones,
  initializeSingleFileControls,
} from "./dropzones.js?v=4.5";
import { FEATURES } from "./features.js?v=6.0";

const featureResources = new Map();
const assetVersion = new URLSearchParams(window.location.search).get("asset_version") || "6.0";
let navigationGeneration = 0;

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

  return panel;
}

function renderFeatureFailure(featureId, error) {
  const host = $("#featureHost");
  if (!host) return;
  const panel = document.createElement("section");
  panel.className = "tool-panel active feature-load-failure";
  const heading = document.createElement("h2");
  heading.textContent = `${FEATURES[featureId]?.title || featureId} could not open`;
  const detail = document.createElement("p");
  detail.textContent = error?.message || String(error);
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "btn primary";
  retry.textContent = "Retry feature";
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
      FEATURES[featureId]?.title
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
