import { apiFetch, parseError } from "/frontend/assets/js/core/api.js";
import { $, escapeHtml, formatBytes, setStatus } from "/frontend/assets/js/core/dom.js?v=4.5";
import { formWithSingleFile } from "/frontend/assets/js/core/downloads.js";
import { clearFiles, onFilesChanged } from "/frontend/assets/js/core/file_store.js?v=4.5";
import { getNativeApi } from "/frontend/assets/js/core/native_api.js?v=6.0";
import { renderProgress } from "/frontend/assets/js/core/progress.js?v=5.4";

export function init() {
  let nativeSource = null;
  const status = $("#documentShaStatus");
  const nativeMeta = $("#documentShaNativeMeta");
  const dropzone = document.querySelector('.dropzone[data-input="documentShaFile"]');

  const clearNativeSource = () => {
    nativeSource = null;
    nativeMeta.classList.add("hidden");
    nativeMeta.textContent = "";
  };

  onFilesChanged("documentShaFile", (files) => {
    if (files.length) clearNativeSource();
  });

  const selectNativeSource = (result, kind) => {
    if (!result) return;
    clearFiles("documentShaFile");
    nativeSource = { ...result, kind };
    nativeMeta.classList.remove("hidden");
    const size = Number.isFinite(result.bytes) ? ` • ${formatBytes(result.bytes)}` : "";
    nativeMeta.innerHTML = `<strong>${escapeHtml(result.name)}</strong>${size}<br><code>${escapeHtml(result.path)}</code>`;
    setStatus(status, `${kind === "folder" ? "Folder" : "File"} selected for local hashing.`, "success");
  };

  $("#chooseDocumentShaNative").addEventListener("click", async () => {
    try {
      const api = getNativeApi();
      if (!api?.choose_hash_file) throw new Error("Native file selection is available in the desktop app.");
      selectNativeSource(await api.choose_hash_file(), "file");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#chooseDocumentShaFolder").addEventListener("click", async () => {
    try {
      const api = getNativeApi();
      if (!api?.choose_hash_folder) throw new Error("Native folder selection is available in the desktop app.");
      selectNativeSource(await api.choose_hash_folder(), "folder");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  dropzone?.addEventListener("directorydrop", () => {
    setStatus(status, "Windows does not expose a dropped folder path to the app. Use “Choose local folder” instead.", "error");
  });

  if (window.__documentShaProgressHandler) {
    window.removeEventListener("message", window.__documentShaProgressHandler);
  }
  window.__documentShaProgressHandler = (event) => {
    if (event.origin !== window.location.origin) return;
    if (event.data?.type !== "pdf-workbench-native-hash-progress") return;
    renderProgress(status, event.data.payload, "Hashing local source…");
  };
  window.addEventListener("message", window.__documentShaProgressHandler);

  $("#documentShaBtn").addEventListener("click", async () => {
    try {
      if (nativeSource) {
        const api = getNativeApi();
        if (!api?.hash_security_path) throw new Error("Native hashing requires the desktop app.");
        renderProgress(status, {
          operation: "Calculating SHA-256",
          stage: `Preparing local ${nativeSource.kind}`,
          percent: 1,
          elapsed_seconds: 0,
          status: "running",
        });
        const data = await api.hash_security_path(nativeSource.path);
        const scope = data.kind === "folder" ? `${data.files} files • ${formatBytes(data.bytes)}` : formatBytes(data.bytes);
        setStatus(status, `${data.name} • ${scope}\nSHA-256\n${data.sha256}`, "success");
        return;
      }

      const form = formWithSingleFile("documentShaFile");
      const response = await apiFetch("/api/document-security/sha256", {
        method: "POST",
        body: form,
        progressElement: status,
        progressLabel: "Hashing file locally…",
      });
      if (!response.ok) throw new Error(await parseError(response));
      const data = await response.json();
      setStatus(status, `${data.name} • ${formatBytes(data.bytes)}\nSHA-256\n${data.sha256}`, "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
