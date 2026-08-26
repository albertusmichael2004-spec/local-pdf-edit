export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML;
}

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = units[0];
  for (let i = 0; i < units.length - 1 && value >= 1024; i += 1) {
    value /= 1024;
    unit = units[i + 1];
  }
  return `${value.toFixed(value >= 10 || unit === "B" ? 1 : 2)} ${unit}`;
}

export function setStatus(element, message, type = "") {
  if (!element) return;
  element.className = `status ${type}`.trim();
  element.textContent = message;
}

export function hideStatus(element) {
  if (!element) return;
  element.className = "status hidden";
  element.textContent = "";
}
