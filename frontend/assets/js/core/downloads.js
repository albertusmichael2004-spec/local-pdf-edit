import { apiFetch, downloadResponse } from "./api.js";
import { $, setStatus } from "./dom.js";
import { firstFile } from "./file_store.js";

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
    const response = await apiFetch(endpoint, { method: "POST", body: form });
    await downloadResponse(response, fallbackName);
    const note = response.headers.get("x-compression-note");
    const reduction = response.headers.get("x-reduction-percent");
    const oversized = response.headers.get("x-oversized-parts");
    const engine = response.headers.get("x-conversion-engine");
    let message = "Done. Output is ready.";
    if (engine) message += ` Engine: ${engine}.`;
    if (reduction) message += ` Size reduction: ${Number(reduction).toFixed(1)}%.`;
    if (note) message += ` ${note}`;
    if (oversized) {
      message += ` Parts ${oversized} exceed the requested size because a single page is already larger than the target.`;
    }
    setStatus(statusEl, message, oversized ? "warning" : "success");
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
