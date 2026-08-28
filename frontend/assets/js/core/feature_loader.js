import { apiFetch } from "./api.js";
import { $, $$ } from "./dom.js";
import {
  bindDropzones,
  initializeSingleFileControls,
} from "./dropzones.js";
import { FEATURES } from "./features.js";


async function loadFeature(featureId) {
  const feature = FEATURES[featureId];

  if (!feature) {
    throw new Error(
      `Unknown feature: ${featureId}`
    );
  }

  const response = await apiFetch(
    feature.view
  );

  if (!response.ok) {
    throw new Error(
      `Could not load ${feature.title} UI.`
    );
  }

  const html = await response.text();

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

  const controller = await import(
    feature.controller
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


export async function showFeature(
  featureId
) {
  const panel = await loadFeature(
    featureId
  );

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
