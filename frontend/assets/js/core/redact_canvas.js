let markSequence = 0;

function nextMarkId() {
  markSequence += 1;
  return `redact-${Date.now()}-${markSequence}`;
}

function clamp(value) {
  return Math.max(0, Math.min(1, value));
}

export class RedactCanvas {
  constructor({ paper, image, overlay, onCreate, onTextSelect, onFocus }) {
    this.paper = paper;
    this.image = image;
    this.overlay = overlay;
    this.onCreate = onCreate;
    this.onTextSelect = onTextSelect;
    this.onFocus = onFocus;
    this.pageId = null;
    this.pageNumber = 1;
    this.marks = [];
    this.selectedMarkId = null;
    this.tool = "redact";
    this.draft = null;
    this.activePointer = null;
    this._bind();
  }

  _bind() {
    this.overlay.addEventListener("pointerdown", (event) => {
      if (!["redact", "text"].includes(this.tool) || event.button !== 0) return;
      event.preventDefault();
      const point = this._point(event);
      this.activePointer = event.pointerId;
      this.overlay.setPointerCapture?.(event.pointerId);
      this.draft = { x0: point.x, y0: point.y, x1: point.x, y1: point.y };
      this.render();
    });
    this.overlay.addEventListener("pointermove", (event) => {
      if (event.pointerId !== this.activePointer || !this.draft) return;
      const point = this._point(event);
      this.draft.x1 = point.x;
      this.draft.y1 = point.y;
      this.render();
    });
    const finish = (event) => {
      if (event.pointerId !== this.activePointer || !this.draft) return;
      const bounds = this.overlay.getBoundingClientRect();
      const normalized = this._normalized(this.draft);
      this.activePointer = null;
      this.draft = null;
      if ((normalized.x1 - normalized.x0) * bounds.width < 5
          || (normalized.y1 - normalized.y0) * bounds.height < 5) {
        this.render();
        return;
      }
      const selection = {
        page_instance_id: this.pageId,
        page_number: this.pageNumber,
        rect: { space: "normalized_view", ...normalized },
      };
      if (this.tool === "text") {
        this.onTextSelect?.(selection);
      } else {
        this.onCreate?.({
          mark_id: nextMarkId(),
          ...selection,
          source: "manual",
          search_text: null,
        });
      }
    };
    this.overlay.addEventListener("pointerup", finish);
    this.overlay.addEventListener("pointercancel", finish);
  }

  _point(event) {
    const bounds = this.overlay.getBoundingClientRect();
    return {
      x: clamp((event.clientX - bounds.left) / Math.max(1, bounds.width)),
      y: clamp((event.clientY - bounds.top) / Math.max(1, bounds.height)),
    };
  }

  _normalized(rect) {
    return {
      x0: Math.min(rect.x0, rect.x1),
      y0: Math.min(rect.y0, rect.y1),
      x1: Math.max(rect.x0, rect.x1),
      y1: Math.max(rect.y0, rect.y1),
    };
  }

  setTool(tool) {
    this.tool = ["pan", "text"].includes(tool) ? tool : "redact";
    this.overlay.classList.toggle("drawing-enabled", this.tool === "redact");
    this.overlay.classList.toggle("text-selecting", this.tool === "text");
  }

  showPage({ pageId, pageNumber, image, marks }) {
    this.pageId = pageId;
    this.pageNumber = pageNumber;
    this.marks = marks || [];
    this.image.src = image || "";
    this.render();
  }

  setMarks(marks) {
    this.marks = marks || [];
    this.render();
  }

  setSelectedMark(markId) {
    this.selectedMarkId = markId || null;
    this.render();
  }

  render() {
    this.overlay.replaceChildren();
    const entries = this.marks.map((mark) => ({ mark, rect: mark.rect, draft: false }));
    if (this.draft) entries.push({ mark: null, rect: this._normalized(this.draft), draft: true, textSelection: this.tool === "text" });
    for (const entry of entries) {
      const box = document.createElement("button");
      box.type = "button";
      const selected = !entry.draft && entry.mark?.mark_id === this.selectedMarkId;
      box.className = `redact-mark-box${entry.draft ? " draft" : ""}${entry.textSelection ? " text-selection" : ""}${selected ? " selected" : ""}`;
      box.style.left = `${entry.rect.x0 * 100}%`;
      box.style.top = `${entry.rect.y0 * 100}%`;
      box.style.width = `${(entry.rect.x1 - entry.rect.x0) * 100}%`;
      box.style.height = `${(entry.rect.y1 - entry.rect.y0) * 100}%`;
      box.title = entry.draft ? (entry.textSelection ? "Select text to redact" : "New redaction area") : "Redaction area";
      if (!entry.draft) {
        box.setAttribute("aria-pressed", selected ? "true" : "false");
        box.setAttribute("aria-label", `Select redaction mark${entry.mark?.search_text ? ` for ${entry.mark.search_text}` : ""}`);
        box.addEventListener("pointerdown", (event) => event.stopPropagation());
        box.addEventListener("click", () => this.onFocus?.(entry.mark));
      }
      this.overlay.appendChild(box);
    }
  }
}
