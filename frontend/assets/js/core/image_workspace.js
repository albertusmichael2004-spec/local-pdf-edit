import { getFiles, onFilesChanged, replaceFiles } from "./file_store.js";
import { localImageUrl } from "./previews.js";

function createButton(label, title, className = "page-card-action") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.title = title;
  return button;
}

export class ImageWorkspace {
  constructor({ inputId, container, wrapper, count }) {
    this.inputId = inputId;
    this.container = container;
    this.wrapper = wrapper;
    this.count = count;
    this.dragIndex = null;
    onFilesChanged(inputId, () => this.render());
    this.render();
  }

  render() {
    const files = getFiles(this.inputId);
    this.container.replaceChildren();
    this.wrapper.classList.toggle("hidden", !files.length);
    this.count.textContent = `${files.length} ${files.length === 1 ? "page" : "pages"}`;
    files.forEach((file, index) => this.container.appendChild(this._card(file, index)));
  }

  _card(file, index) {
    const card = document.createElement("div");
    card.className = "page-editor-card";
    const page = document.createElement("div");
    page.className = "page-editor-page";
    page.draggable = true;
    const preview = document.createElement("div");
    preview.className = "page-editor-preview";
    const image = document.createElement("img");
    image.src = localImageUrl(file);
    image.alt = `Preview ${file.name}`;
    preview.appendChild(image);
    const actions = document.createElement("div");
    actions.className = "page-card-actions";
    const remove = createButton("×", "Delete image", "page-card-action danger");
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      const next = [...getFiles(this.inputId)];
      next.splice(index, 1);
      replaceFiles(this.inputId, next);
    });
    actions.appendChild(remove);
    const label = document.createElement("div");
    label.className = "page-editor-label";
    label.textContent = `Page ${index + 1} · ${file.name}`;
    label.title = file.name;
    page.append(preview, actions, label);
    this._bindDrag(page, index);
    card.appendChild(page);
    return card;
  }

  _bindDrag(page, index) {
    page.addEventListener("dragstart", (event) => {
      this.dragIndex = index;
      page.closest(".page-editor-card")?.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
    });
    page.addEventListener("dragend", () => {
      this.dragIndex = null;
      this.container.querySelectorAll(".page-editor-card").forEach((card) => card.classList.remove("dragging", "drop-target"));
    });
    page.addEventListener("dragover", (event) => {
      if (this.dragIndex === null || this.dragIndex === index) return;
      event.preventDefault();
      page.closest(".page-editor-card")?.classList.add("drop-target");
    });
    page.addEventListener("dragleave", () => page.closest(".page-editor-card")?.classList.remove("drop-target"));
    page.addEventListener("drop", (event) => {
      event.preventDefault();
      if (this.dragIndex === null || this.dragIndex === index) return;
      const files = [...getFiles(this.inputId)];
      const [moved] = files.splice(this.dragIndex, 1);
      files.splice(index, 0, moved);
      replaceFiles(this.inputId, files);
    });
  }
}
