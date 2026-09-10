import { $, escapeHtml, formatBytes } from "./dom.js";
import { getFiles, replaceFiles } from "./file_store.js";
import { populateThumb } from "./previews.js?v=7.5";
import { openPdfPreview } from "/frontend/assets/js/core/pdf_preview_modal.js?v=7.5";
import { bindAnimatedReorder, stableReorderKey } from "/frontend/assets/js/core/drag_reorder.js";

export function renderSortable(inputId, containerId) {
  const container = $(`#${containerId}`);
  if (!container) return;
  const files = getFiles(inputId);
  container.innerHTML = "";
  files.forEach((file, index) => {
    const item = document.createElement("div");
    item.className = "sortable-item";
    item.draggable = false;
    item.dataset.index = index;
    item.dataset.reorderKey = stableReorderKey(file);
    item.innerHTML = `
      <span class="drag-handle">☷</span>
      <div class="file-thumb"><img alt="Preview"/><span>${escapeHtml(file.name.split(".").pop()?.toUpperCase() || "FILE")}</span></div>
      <span class="item-name">${escapeHtml(file.name)}</span>
      <span class="item-size">${formatBytes(file.size)}</span>
      <button class="remove-file" type="button">Remove</button>`;
    populateThumb(item.querySelector(".file-thumb img"), file);
    if (file.name.toLowerCase().endsWith(".pdf") || file.type === "application/pdf") {
      const name = item.querySelector(".item-name");
      const previewButton = document.createElement("button");
      previewButton.className = "item-name file-name-preview";
      previewButton.title = `Preview ${file.name}`;
      previewButton.type = "button";
      previewButton.textContent = file.name;
      previewButton.addEventListener("click", (event) => {
        event.stopPropagation();
        openPdfPreview(file);
      });
      name?.replaceWith(previewButton);
    }
    item.querySelector(".remove-file").addEventListener("click", (event) => {
      event.stopPropagation();
      const next = [...getFiles(inputId)];
      next.splice(index, 1);
      replaceFiles(inputId, next);
    });
    container.appendChild(item);
  });
  bindAnimatedReorder({
    container,
    itemSelector: ".sortable-item",
    onCommit: (order) => {
      const byKey = new Map(files.map((file) => [stableReorderKey(file), file]));
      replaceFiles(inputId, order.map((value) => byKey.get(value)).filter(Boolean));
    },
  });
}
