import { $, escapeHtml, formatBytes } from "./dom.js";
import { getFiles, replaceFiles } from "./file_store.js";
import { populateThumb } from "./previews.js";

export function renderSortable(inputId, containerId) {
  const container = $(`#${containerId}`);
  if (!container) return;
  const files = getFiles(inputId);
  container.innerHTML = "";
  files.forEach((file, index) => {
    const item = document.createElement("div");
    item.className = "sortable-item";
    item.draggable = true;
    item.dataset.index = index;
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
    item.addEventListener("dragstart", (event) => {
      item.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", String(index));
    });
    item.addEventListener("dragend", () => {
      item.classList.remove("dragging");
      container.querySelectorAll(".drop-target").forEach((node) => node.classList.remove("drop-target"));
    });
    item.addEventListener("dragover", (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      item.classList.add("drop-target");
    });
    item.addEventListener("dragleave", () => item.classList.remove("drop-target"));
    item.addEventListener("drop", (event) => {
      event.preventDefault();
      event.stopPropagation();
      item.classList.remove("drop-target");
      const from = Number(event.dataTransfer.getData("text/plain"));
      const to = Number(item.dataset.index);
      if (!Number.isInteger(from) || from === to) return;
      const reordered = [...getFiles(inputId)];
      if (from < 0 || from >= reordered.length || to < 0 || to >= reordered.length) return;
      const [moved] = reordered.splice(from, 1);
      reordered.splice(to, 0, moved);
      replaceFiles(inputId, reordered);
    });
    container.appendChild(item);
  });
}
