import { apiFetch } from "./api.js";
import { $, $$ } from "./dom.js";
import { bindDropzones, initializeSingleFileControls } from "./dropzones.js";
import { FEATURES } from "./features.js";

const loaded = new Set();

async function ensureLoaded(featureId) {
  if (loaded.has(featureId)) return;
  const feature = FEATURES[featureId];
  if (!feature) throw new Error(`Unknown feature: ${featureId}`);

  const response = await apiFetch(feature.view);
  if (!response.ok) throw new Error(`Could not load ${feature.title} UI.`);
  const html = await response.text();
  $("#featureHost").insertAdjacentHTML("beforeend", html);
  const panel = $(`#${featureId}`);
  if (!panel) throw new Error(`Feature panel ${featureId} is missing.`);
  panel.classList.remove("active");
  bindDropzones(panel);
  initializeSingleFileControls(panel);

  const controller = await import(feature.controller);
  if (typeof controller.init === "function") await controller.init(panel);
  loaded.add(featureId);
}

export async function showFeature(featureId) {
  await ensureLoaded(featureId);
  $$("#featureHost .tool-panel").forEach((panel) => panel.classList.remove("active"));
  const panel = $(`#${featureId}`);
  panel.classList.add("active");
  $("#toolTitle").textContent = FEATURES[featureId]?.title || featureId;
  $$(".nav-tool").forEach((button) => {
    button.classList.toggle("active", button.dataset.tool === featureId);
  });
}

export function bindNavigation() {
  $$(".category-toggle").forEach((button) => {
    button.addEventListener("click", () => button.closest(".category").classList.toggle("open"));
  });
  $$(".nav-tool").forEach((button) => {
    button.addEventListener("click", () => {
      showFeature(button.dataset.tool).catch((error) => {
        console.error(error);
        $("#toolTitle").textContent = "Feature failed to load";
      });
    });
  });
}
