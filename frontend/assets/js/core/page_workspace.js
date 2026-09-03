import { inspectPdf, previewPdf } from "./previews.js";
import { bindAnimatedReorder } from "./drag_reorder.js";

let sequence = 0;

function uid(prefix = "page") {
  sequence += 1;
  return `${prefix}-${Date.now()}-${sequence}`;
}

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function parsePageOrderExpression(expression, totalPages) {
  const output = [];
  for (const rawToken of String(expression || "").split(",")) {
    const token = rawToken.trim();
    if (!token) continue;
    const range = token.match(/^(\d+)\s*-\s*(\d+)$/);
    if (range) {
      const start = Number(range[1]);
      const end = Number(range[2]);
      const step = start <= end ? 1 : -1;
      for (let page = start; page !== end + step; page += step) {
        if (page < 1 || page > totalPages) throw new Error(`Page ${page} is outside 1-${totalPages}.`);
        output.push(page);
      }
      continue;
    }
    if (!/^\d+$/.test(token)) throw new Error(`Invalid page-order token: ${token}`);
    const page = Number(token);
    if (page < 1 || page > totalPages) throw new Error(`Page ${page} is outside 1-${totalPages}.`);
    output.push(page);
  }
  if (!output.length) throw new Error("Enter at least one page in the new order.");
  return output;
}

export class PageWorkspace {
  constructor({
    inputId,
    container,
    selectable = false,
    checkboxSelection = false,
    reorderable = false,
    organizeActions = false,
    maxPreviewBatch = 12,
    onChange = null,
    onSelectionChange = null,
    onCardClick = null,
  }) {
    this.inputId = inputId;
    this.container = typeof container === "string" ? document.querySelector(container) : container;
    this.selectable = selectable;
    this.checkboxSelection = checkboxSelection;
    this.reorderable = reorderable;
    this.organizeActions = organizeActions;
    this.maxPreviewBatch = maxPreviewBatch;
    this.onChange = onChange;
    this.onSelectionChange = onSelectionChange;
    this.onCardClick = onCardClick;
    this.file = null;
    this.info = null;
    this.items = [];
    this.previewCache = new Map();
    this.pendingPages = new Set();
    this.previewTimer = null;
    this.observer = null;
    if (this.reorderable) {
      bindAnimatedReorder({
        container: this.container,
        itemSelector: ".page-editor-card",
        onCommit: (order) => {
          const byId = new Map(this.items.map((item) => [item.id, item]));
          this.items = order.map((id) => byId.get(id)).filter(Boolean);
          this._notifyChanged();
          this.render();
        },
      });
    }
  }

  async load(file) {
    this.file = file;
    this.info = await inspectPdf(file);
    this.items = Array.from({ length: this.info.pages }, (_, index) => ({
      id: uid("source"),
      sourcePage: index + 1,
      rotation: 0,
      widthPt: null,
      heightPt: null,
      selected: false,
      blank: false,
    }));
    this.previewCache.clear();
    this.render();
    return this.info;
  }

  clear() {
    this.file = null;
    this.info = null;
    this.items = [];
    this.previewCache.clear();
    this._disconnectObserver();
    if (this.container) this.container.innerHTML = "";
  }

  render() {
    if (!this.container) return;
    this._disconnectObserver();
    this.container.innerHTML = "";
    const fragment = document.createDocumentFragment();
    this.items.forEach((item, index) => fragment.appendChild(this._createCard(item, index)));
    this.container.appendChild(fragment);
    this._bindLazyPreviews();
  }

  _createCard(item, index) {
    const card = document.createElement("div");
    card.className = `page-editor-card${item.selected ? " selected" : ""}${item.blank ? " blank" : ""}${item.edited ? " edited" : ""}${item.active ? " active-page" : ""}`;
    card.dataset.itemId = item.id;
    card.dataset.reorderKey = item.id;
    if (item.sourcePage) card.dataset.sourcePage = String(item.sourcePage);

    if (this.organizeActions) {
      const left = document.createElement("button");
      left.type = "button";
      left.className = "page-side-add left";
      left.title = "Add blank page before";
      left.textContent = "+";
      left.addEventListener("click", (event) => {
        event.stopPropagation();
        this.insertBlank(index, "before");
      });
      card.appendChild(left);
    }

    const pageShell = document.createElement("div");
    pageShell.className = "page-editor-page";
    pageShell.draggable = false;

    if (this.checkboxSelection) {
      const check = document.createElement("input");
      check.type = "checkbox";
      check.className = "page-select-check";
      check.checked = item.selected;
      check.title = "Select this page";
      check.addEventListener("click", (event) => event.stopPropagation());
      check.addEventListener("change", () => this.setSelected(item.id, check.checked));
      pageShell.appendChild(check);
    }

    const preview = document.createElement("div");
    preview.className = "page-editor-preview";
    if (item.blank) {
      preview.innerHTML = `<div class="blank-page-visual"><span>Blank</span></div>`;
    } else {
      const img = document.createElement("img");
      img.alt = `Preview page ${item.sourcePage}`;
      img.draggable = false;
      img.dataset.lazyPage = String(item.sourcePage);
      const cached = this.previewCache.get(item.sourcePage);
      if (item.previewImage) {
        img.src = item.previewImage;
        img.dataset.customPreview = "true";
      } else if (cached?.image) {
        img.src = cached.image;
        this._applyPreviewMetadata(item, cached);
      }
      preview.appendChild(img);
    }
    preview.style.transform = item.rotation ? `rotate(${item.rotation}deg)` : "";
    pageShell.appendChild(preview);

    if (this.organizeActions) {
      const actions = document.createElement("div");
      actions.className = "page-card-actions";
      const rotate = document.createElement("button");
      rotate.type = "button";
      rotate.className = "page-card-action";
      rotate.title = "Rotate page clockwise";
      rotate.textContent = "↻";
      rotate.addEventListener("click", (event) => {
        event.stopPropagation();
        item.rotation = (item.rotation + 90) % 360;
        this._notifyChanged();
        this.render();
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "page-card-action danger";
      remove.title = "Delete page";
      remove.textContent = "×";
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        this.remove(item.id);
      });
      actions.append(rotate, remove);
      pageShell.appendChild(actions);
    }

    if (this.onCardClick) {
      pageShell.addEventListener("click", (event) => this.onCardClick(item, this, event));
    } else if (this.selectable) {
      pageShell.addEventListener("click", () => this.setSelected(item.id, !item.selected));
    }

    const label = document.createElement("div");
    label.className = "page-editor-label";
    label.textContent = item.blank ? "Blank page" : `Page ${item.sourcePage}`;
    pageShell.appendChild(label);
    card.appendChild(pageShell);

    if (this.organizeActions) {
      const right = document.createElement("button");
      right.type = "button";
      right.className = "page-side-add right";
      right.title = "Add blank page after";
      right.textContent = "+";
      right.addEventListener("click", (event) => {
        event.stopPropagation();
        this.insertBlank(index, "after");
      });
      card.appendChild(right);
    }
    return card;
  }

  insertBlank(index, side = "after") {
    const neighbor = this.items[index];
    const blank = {
      id: uid("blank"),
      sourcePage: null,
      rotation: 0,
      widthPt: neighbor?.widthPt || 595,
      heightPt: neighbor?.heightPt || 842,
      selected: false,
      blank: true,
    };
    this.items.splice(side === "before" ? index : index + 1, 0, blank);
    this._notifyChanged();
    this.render();
  }

  remove(itemId) {
    if (this.items.length <= 1) return;
    this.items = this.items.filter((item) => item.id !== itemId);
    this._notifyChanged();
    this.render();
  }

  setSelected(itemId, selected) {
    const item = this.items.find((entry) => entry.id === itemId);
    if (!item) return;
    item.selected = Boolean(selected);
    const card = this.container.querySelector(`[data-item-id="${itemId}"]`);
    card?.classList.toggle("selected", item.selected);
    const checkbox = card?.querySelector(".page-select-check");
    if (checkbox) checkbox.checked = item.selected;
    this.onSelectionChange?.(this.getSelectedPages(), this);
  }

  clearSelection() {
    this.items.forEach((item) => { item.selected = false; });
    this.render();
    this.onSelectionChange?.([], this);
  }

  getSelectedPages() {
    return [...new Set(this.items.filter((item) => item.selected && item.sourcePage).map((item) => item.sourcePage))].sort((a, b) => a - b);
  }

  getPlan() {
    return this.items.map((item) => ({
      source_page: item.sourcePage,
      rotation: item.rotation || 0,
      width_pt: item.widthPt || 595,
      height_pt: item.heightPt || 842,
    }));
  }

  applyOrder(pageNumbers) {
    const dimensions = new Map(this.items.filter((item) => item.sourcePage).map((item) => [item.sourcePage, item]));
    this.items = pageNumbers.map((pageNumber) => {
      const source = dimensions.get(pageNumber);
      return {
        id: uid("source"),
        sourcePage: pageNumber,
        rotation: 0,
        widthPt: source?.widthPt || null,
        heightPt: source?.heightPt || null,
        selected: false,
        blank: false,
      };
    });
    this._notifyChanged();
    this.render();
  }

  setPreviewRotationForSelected(degrees) {
    const normalized = ((degrees % 360) + 360) % 360;
    this.container.querySelectorAll(".page-editor-card.selected .page-editor-preview").forEach((preview) => {
      preview.style.transform = normalized ? `rotate(${normalized}deg)` : "";
    });
  }

  _notifyChanged() {
    this.onChange?.(this.items, this);
  }

  _applyPreviewMetadata(item, preview) {
    item.widthPt = preview.width_pt || item.widthPt;
    item.heightPt = preview.height_pt || item.heightPt;
  }

  _disconnectObserver() {
    if (this.observer) this.observer.disconnect();
    this.observer = null;
  }

  _bindLazyPreviews() {
    if (!this.file) return;
    this.observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const img = entry.target;
        if (img.src) {
          this.observer.unobserve(img);
          return;
        }
        const page = Number(img.dataset.lazyPage);
        if (page) this._queuePreview(page);
        this.observer.unobserve(img);
      });
    }, { root: this.container, rootMargin: "180px" });
    this.container.querySelectorAll("img[data-lazy-page]").forEach((img) => {
      if (!img.src) this.observer.observe(img);
    });
  }

  _queuePreview(pageNumber) {
    if (this.previewCache.has(pageNumber)) return;
    this.pendingPages.add(pageNumber);
    window.clearTimeout(this.previewTimer);
    this.previewTimer = window.setTimeout(() => this._flushPreviewQueue(), 35);
  }

  async _flushPreviewQueue() {
    if (!this.file || !this.pendingPages.size) return;
    const pages = [...this.pendingPages].slice(0, this.maxPreviewBatch);
    pages.forEach((page) => this.pendingPages.delete(page));
    try {
      const data = await previewPdf(this.file, pages);
      for (const preview of data.previews || []) {
        this.previewCache.set(preview.page, preview);
        this.items.filter((item) => item.sourcePage === preview.page).forEach((item) => this._applyPreviewMetadata(item, preview));
        this.container.querySelectorAll(`img[data-lazy-page="${preview.page}"]`).forEach((img) => {
          if (!img.dataset.customPreview) img.src = preview.image;
        });
      }
    } catch (error) {
      console.warn("Could not load page thumbnails", error);
    }
    if (this.pendingPages.size) this.previewTimer = window.setTimeout(() => this._flushPreviewQueue(), 35);
  }
}
