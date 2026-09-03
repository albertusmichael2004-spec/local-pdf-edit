import { $, escapeHtml, formatBytes } from "./dom.js";
import { getFiles, replaceFiles } from "./file_store.js";
import { populateThumb } from "./previews.js";
import { bindAnimatedReorder } from "./drag_reorder.js";

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
    item.dataset.reorderKey = String(index);
    item.innerHTML = `
      <span class="drag-handle">☷</span>
      <div class="file-thumb"><img alt="Preview"/><span>${escapeHtml(file.name.split(".").pop()?.toUpperCase() || "FILE")}</span></div>
      <span class="item-name">${escapeHtml(file.name)}</span>
      <span class="item-size">${formatBytes(file.size)}</span>
      <button class="remove-file" type="button">Remove</button>`;
    populateThumb(item.querySelector(".file-thumb img"), file);
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
    onCommit: (order) => replaceFiles(inputId, order.map((value) => files[Number(value)]).filter(Boolean)),
  });
}
