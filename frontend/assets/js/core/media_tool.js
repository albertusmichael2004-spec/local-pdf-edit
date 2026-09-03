import { apiFetch, parseError } from "./api.js";
import { $, hideStatus, setStatus } from "./dom.js";
import { clearFiles, getFiles, onFilesChanged } from "./file_store.js";
import { postDownload } from "./downloads.js";
import { renderSortable } from "./sortable.js";

function commonTargets(items) {
  if (!items.length) return [];
  const counts = new Map();
  for (const item of items) {
    for (const target of item.targets || []) {
      const current = counts.get(target.format) || { ...target, count: 0 };
      current.count += 1;
      current.recommended ||= target.recommended;
      counts.set(target.format, current);
    }
  }
  return [...counts.values()].filter((item) => item.count === items.length);
}

function endpointFor(operation, kind) {
  if (operation === "compress") return kind === "image" ? "/api/compress/images" : "/api/compress/media";
  if (kind === "image") return "/api/convert/images";
  if (kind === "video") return "/api/convert/video";
  if (kind === "audio") return "/api/convert/audio";
  if (kind === "ebook" || kind === "pdf") return "/api/convert/ebook";
  return null;
}

async function inspect(files) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const response = await apiFetch("/api/media/probe", { method: "POST", body: form });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

function fillTargets(select, targets, operation) {
  select.replaceChildren();
  if (operation === "compress") select.add(new Option("Keep original type", "keep", true, true));
  for (const target of targets) {
    const label = `${target.format.toUpperCase()}${target.recommended ? " · Recommended" : ""}`;
    const selected = target.recommended && operation !== "compress";
    select.add(new Option(label, target.format, selected, selected));
  }
  select.disabled = !select.options.length;
}

export function initMediaTool({ operation, ids }) {
  const state = { kind: null, token: 0 };
  const target = $(`#${ids.target}`);
  const summary = $(`#${ids.summary}`);
  const status = $(`#${ids.status}`);
  const button = $(`#${ids.button}`);

  const refresh = async () => {
    const files = getFiles(ids.input);
    renderSortable(ids.input, ids.list);
    const token = ++state.token;
    state.kind = null;
    button.disabled = true;
    target.disabled = true;
    if (!files.length) {
      summary.className = "media-detection hidden";
      hideStatus(status);
      return;
    }
    setStatus(status, `Inspecting ${files.length} file${files.length === 1 ? "" : "s"} locally…`);
    try {
      const data = await inspect(files);
      if (token !== state.token) return;
      const kinds = [...new Set(data.files.map((file) => file.kind))];
      if (kinds.length !== 1) throw new Error(`Use one detected file type per batch. Found: ${kinds.join(", ")}.`);
      state.kind = kinds[0];
      fillTargets(target, commonTargets(data.files), operation);
      const formats = [...new Set(data.files.map((file) => file.format.toUpperCase()))].join(", ");
      summary.className = "media-detection";
      summary.innerHTML = `<strong>Detected ${state.kind}</strong><span>${formats} · ${data.files.length} file${data.files.length === 1 ? "" : "s"}</span>`;
      if (!endpointFor(operation, state.kind)) throw new Error(`No ${operation} route is available for ${state.kind}.`);
      if (!target.options.length) throw new Error("No compatible target is available. Check the local engine status.");
      button.disabled = false;
      setStatus(status, "Ready. Target formats reflect the engines available on this computer.", "success");
    } catch (error) {
      if (token !== state.token) return;
      setStatus(status, error.message || String(error), "error");
    }
  };

  onFilesChanged(ids.input, refresh);
  refresh();
  $(`#${ids.clear}`).addEventListener("click", () => clearFiles(ids.input));
  button.addEventListener("click", async () => {
    const endpoint = endpointFor(operation, state.kind);
    if (!endpoint) return setStatus(status, "Upload and inspect supported files first.", "error");
    const form = new FormData();
    getFiles(ids.input).forEach((file) => form.append("files", file));
    form.append("target_format", target.value);
    const selectedQuality = ids.qualityName
      ? document.querySelector(`input[name="${ids.qualityName}"]:checked`)?.value
      : $(`#${ids.quality}`)?.value;
    form.append("quality", selectedQuality || "recommended");
    form.append("keep_metadata", String($(`#${ids.metadata}`).checked));
    const fallback = operation === "compress" ? "media_compressed.zip" : "media_converted.zip";
    await postDownload(endpoint, form, status, fallback, `${operation === "compress" ? "Compressing" : "Converting"} locally…`);
  });
}
