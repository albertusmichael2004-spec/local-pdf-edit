import { apiFetch, downloadResponse } from "./api.js?v=4.5";
import { $, setStatus } from "./dom.js?v=4.5";
import { firstFile } from "./file_store.js?v=4.5";
import { startProgressTracking } from "./progress.js?v=4.5";

const STREAM_DOWNLOAD_THRESHOLD = 512 * 1024 * 1024;

function appendNativeField(form, name, value) {
  const input = document.createElement("input");
  input.name = name;
  if (value instanceof File) {
    input.type = "file";
    const transfer = new DataTransfer();
    transfer.items.add(value);
    input.files = transfer.files;
  } else {
    input.type = "hidden";
    input.value = String(value);
  }
  form.append(input);
}

function startLargeDownload(endpoint, payload, statusEl, workingMessage) {
  const entries = [...payload.entries()];
  const bytes = entries.reduce((sum, [, value]) => sum + (value instanceof File ? value.size : 0), 0);
  if (bytes < STREAM_DOWNLOAD_THRESHOLD || typeof DataTransfer === "undefined") return false;
  const tracker = startProgressTracking(endpoint, statusEl, workingMessage, () => {
    setStatus(statusEl, "Done. Output is ready.", "success");
  });
  const target = document.createElement("iframe");
  target.name = `stream-download-${Date.now()}`;
  target.hidden = true;
  const form = document.createElement("form");
  form.hidden = true;
  form.method = "post";
  form.enctype = "multipart/form-data";
  form.action = tracker.endpoint;
  form.target = target.name;
  entries.forEach(([name, value]) => appendNativeField(form, name, value));
  let submitted = false;
  target.addEventListener("load", () => {
    if (!submitted) return;
    const message = target.contentDocument?.body?.textContent?.trim();
    if (!message) return;
    tracker.stop();
    setStatus(statusEl, message, "error");
  });
  document.body.append(target, form);
  submitted = true;
  form.submit();
  window.setTimeout(() => form.remove(), 0);
  return true;
}

export function formWithSingleFile(inputId) {
  const file = firstFile(inputId);
  if (!file) throw new Error("Choose or drop a file first.");
  const form = new FormData();
  form.append("file", file);
  return form;
}

export async function postDownload(
  endpoint,
  form,
  statusEl,
  fallbackName,
  workingMessage = "Processing locally…",
) {
  try {
    setStatus(statusEl, workingMessage);
    if (startLargeDownload(endpoint, form, statusEl, workingMessage)) return;
    const response = await apiFetch(endpoint, {
      method: "POST",
      body: form,
      progressElement: statusEl,
      progressLabel: workingMessage,
    });
    await downloadResponse(response, fallbackName);
    const note = response.headers.get("x-compression-note");
    const reduction = response.headers.get("x-reduction-percent");
    const oversized = response.headers.get("x-oversized-parts");
    const engine = response.headers.get("x-conversion-engine");
    const mediaWarning = response.headers.get("x-media-warning");
    const archiveNote = response.headers.get("x-archive-note");
    let message = "Done. Output is ready.";
    if (engine) message += ` Engine: ${engine}.`;
    if (reduction) message += ` Size reduction: ${Number(reduction).toFixed(1)}%.`;
    if (note) message += ` ${note}`;
    if (mediaWarning) message += ` ${mediaWarning}`;
    if (archiveNote) message += ` ${archiveNote}`;
    if (oversized) {
      message += ` Parts ${oversized} exceed the requested size because a single page is already larger than the target.`;
    }
    setStatus(statusEl, message, oversized || mediaWarning ? "warning" : "success");
  } catch (error) {
    setStatus(statusEl, error.message || String(error), "error");
  }
}

export function bindSimpleDownload({
  buttonId,
  inputId,
  endpoint,
  statusId,
  fallback,
  fields = () => ({}),
  workingMessage,
}) {
  $(`#${buttonId}`).addEventListener("click", async () => {
    const status = $(`#${statusId}`);
    try {
      const form = formWithSingleFile(inputId);
      Object.entries(fields()).forEach(([key, value]) => form.append(key, value));
      await postDownload(endpoint, form, status, fallback, workingMessage);
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
