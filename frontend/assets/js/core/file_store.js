import { $, escapeHtml, formatBytes } from "./dom.js";

const fileState = new Map();
const callbacks = new Map();

export function getFiles(inputId) {
  return fileState.get(inputId) || [];
}

export function firstFile(inputId) {
  return getFiles(inputId)[0] || null;
}

export function replaceFiles(inputId, files) {
  fileState.set(inputId, [...files]);
  updateFileMeta(inputId);
  notify(inputId);
}

function matchesAccept(file, input) {
  const accept = (input.accept || "")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  if (!accept.length) return true;
  const name = file.name.toLowerCase();
  const type = (file.type || "").toLowerCase();
  return accept.some((rule) => {
    if (rule.startsWith(".")) return name.endsWith(rule);
    if (rule.endsWith("/*")) return type.startsWith(rule.slice(0, -1));
    return type === rule;
  });
}

export function setFiles(inputId, incoming, append = false) {
  const input = $(`#${inputId}`);
  if (!input) return;
  const accepted = [...incoming].filter((file) => matchesAccept(file, input));
  const existing = append && input.multiple ? getFiles(inputId) : [];
  const next = input.multiple ? [...existing, ...accepted] : accepted.slice(0, 1);
  fileState.set(inputId, next);
  input.value = "";
  updateFileMeta(inputId);
  notify(inputId);
}

export function clearFiles(inputId) {
  const input = $(`#${inputId}`);
  fileState.set(inputId, []);
  if (input) input.value = "";
  updateFileMeta(inputId);
  notify(inputId);
}

export function onFilesChanged(inputId, callback) {
  const list = callbacks.get(inputId) || [];
  list.push(callback);
  callbacks.set(inputId, list);
}

function notify(inputId) {
  for (const callback of callbacks.get(inputId) || []) {
    callback(getFiles(inputId));
  }
}

export function updateFileMeta(inputId) {
  const files = getFiles(inputId);
  const explicit = document.querySelector(`[data-filemeta-for="${inputId}"]`);
  const special = inputId.endsWith("File") ? $(`#${inputId.replace(/File$/, "FileMeta")}`) : null;
  const meta = explicit || special;
  if (!meta) return;
  if (!files.length) {
    meta.classList.add("hidden");
    meta.textContent = "";
    return;
  }
  meta.classList.remove("hidden");
  if (files.length === 1) {
    const file = files[0];
    meta.innerHTML = `<strong>${escapeHtml(file.name)}</strong> • ${formatBytes(file.size)}`;
    return;
  }
  const total = files.reduce((sum, file) => sum + file.size, 0);
  meta.innerHTML = `<strong>${files.length} files selected</strong> • ${formatBytes(total)}`;
}
