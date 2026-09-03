import { getFiles, onFilesChanged, replaceFiles } from "./file_store.js";
import { localImageUrl } from "./previews.js";
import { bindAnimatedReorder } from "./drag_reorder.js";

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
    bindAnimatedReorder({
      container: this.container,
      itemSelector: ".page-editor-card",
      onCommit: (order) => {
        const files = getFiles(this.inputId);
        replaceFiles(this.inputId, order.map((value) => files[Number(value)]).filter(Boolean));
      },
    });
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
    card.dataset.reorderKey = String(index);
    const page = document.createElement("div");
    page.className = "page-editor-page";
    page.draggable = false;
    const preview = document.createElement("div");
    preview.className = "page-editor-preview";
    const image = document.createElement("img");
    image.src = localImageUrl(file);
    image.alt = `Preview ${file.name}`;
    image.draggable = false;
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
    card.appendChild(page);
    return card;
  }
}
