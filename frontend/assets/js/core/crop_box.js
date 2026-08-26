const MM_PER_PT = 25.4 / 72;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export class CropBoxEditor {
  constructor({ wrapper, image, box, inputs }) {
    this.wrapper = wrapper;
    this.image = image;
    this.box = box;
    this.inputs = inputs;
    this.pageWidthPt = 595;
    this.pageHeightPt = 842;
    this.rect = { left: 0, top: 0, right: 0, bottom: 0 };
    this._buildHandles();
    Object.values(inputs).forEach((input) => input.addEventListener("input", () => this.syncFromInputs()));
  }

  setPreview(preview) {
    this.pageWidthPt = Number(preview.width_pt) || 595;
    this.pageHeightPt = Number(preview.height_pt) || 842;
    this.image.src = preview.image || "";
    this.syncFromInputs();
  }

  syncFromInputs() {
    const widthMm = this.pageWidthPt * MM_PER_PT;
    const heightMm = this.pageHeightPt * MM_PER_PT;
    this.rect.left = clamp(Number(this.inputs.left.value || 0) / widthMm, 0, 0.92);
    this.rect.right = clamp(Number(this.inputs.right.value || 0) / widthMm, 0, 0.92);
    this.rect.top = clamp(Number(this.inputs.top.value || 0) / heightMm, 0, 0.92);
    this.rect.bottom = clamp(Number(this.inputs.bottom.value || 0) / heightMm, 0, 0.92);
    this._normalize();
    this._render();
  }

  _syncInputs() {
    const widthMm = this.pageWidthPt * MM_PER_PT;
    const heightMm = this.pageHeightPt * MM_PER_PT;
    this.inputs.left.value = (this.rect.left * widthMm).toFixed(1);
    this.inputs.right.value = (this.rect.right * widthMm).toFixed(1);
    this.inputs.top.value = (this.rect.top * heightMm).toFixed(1);
    this.inputs.bottom.value = (this.rect.bottom * heightMm).toFixed(1);
  }

  _normalize() {
    const minRemaining = 0.06;
    if (this.rect.left + this.rect.right > 1 - minRemaining) this.rect.right = 1 - minRemaining - this.rect.left;
    if (this.rect.top + this.rect.bottom > 1 - minRemaining) this.rect.bottom = 1 - minRemaining - this.rect.top;
    Object.keys(this.rect).forEach((key) => { this.rect[key] = clamp(this.rect[key], 0, 0.94); });
  }

  _render() {
    this.box.style.left = `${this.rect.left * 100}%`;
    this.box.style.top = `${this.rect.top * 100}%`;
    this.box.style.right = `${this.rect.right * 100}%`;
    this.box.style.bottom = `${this.rect.bottom * 100}%`;
  }

  _buildHandles() {
    this.box.innerHTML = "";
    ["nw", "n", "ne", "e", "se", "s", "sw", "w"].forEach((direction) => {
      const handle = document.createElement("span");
      handle.className = `crop-handle ${direction}`;
      handle.dataset.direction = direction;
      this.box.appendChild(handle);
      handle.addEventListener("pointerdown", (event) => this._startResize(event, direction));
    });
    this.box.addEventListener("pointerdown", (event) => {
      if (event.target !== this.box) return;
      this._startMove(event);
    });
  }

  _startResize(event, direction) {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startY = event.clientY;
    const initial = { ...this.rect };
    const bounds = this.wrapper.getBoundingClientRect();

    const move = (next) => {
      const dx = (next.clientX - startX) / Math.max(1, bounds.width);
      const dy = (next.clientY - startY) / Math.max(1, bounds.height);
      this.rect = { ...initial };
      if (direction.includes("w")) this.rect.left = clamp(initial.left + dx, 0, 0.94);
      if (direction.includes("e")) this.rect.right = clamp(initial.right - dx, 0, 0.94);
      if (direction.includes("n")) this.rect.top = clamp(initial.top + dy, 0, 0.94);
      if (direction.includes("s")) this.rect.bottom = clamp(initial.bottom - dy, 0, 0.94);
      this._normalize();
      this._render();
      this._syncInputs();
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  }

  _startMove(event) {
    event.preventDefault();
    const startX = event.clientX;
    const startY = event.clientY;
    const initial = { ...this.rect };
    const bounds = this.wrapper.getBoundingClientRect();
    const width = 1 - initial.left - initial.right;
    const height = 1 - initial.top - initial.bottom;

    const move = (next) => {
      const dx = (next.clientX - startX) / Math.max(1, bounds.width);
      const dy = (next.clientY - startY) / Math.max(1, bounds.height);
      const left = clamp(initial.left + dx, 0, 1 - width);
      const top = clamp(initial.top + dy, 0, 1 - height);
      this.rect.left = left;
      this.rect.right = 1 - width - left;
      this.rect.top = top;
      this.rect.bottom = 1 - height - top;
      this._render();
      this._syncInputs();
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  }
}
