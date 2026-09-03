import { $, escapeHtml, formatBytes, setStatus } from "/frontend/assets/js/core/dom.js?v=4.5";
import { apiFetch, parseError } from "/frontend/assets/js/core/api.js";
import { clearFiles, firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js?v=4.5";
import { getNativeApi } from "/frontend/assets/js/core/native_api.js?v=6.0";

export function init() {
  let selected = null;
  const nativeMeta = $("#extractArchiveNativeMeta");
  const status = $("#extractArchiveStatus");

  onFilesChanged("extractArchiveFile", (files) => {
    if (!files.length) return;
    selected = null;
    nativeMeta.classList.add("hidden");
    nativeMeta.textContent = "";
    setStatus(status, "Compressed file ready. Click Extract files to continue.", "success");
  });

  $("#chooseArchiveFile").addEventListener("click", async () => {
    try {
      const api = getNativeApi();
      if (!api?.choose_archive) {
        $("#extractArchiveFile").click();
        setStatus(status, "Windows picker is still loading; using the upload picker instead.", "warning");
        return;
      }
      const result = await api.choose_archive();
      if (!result) return;
      clearFiles("extractArchiveFile");
      selected = result;
      nativeMeta.classList.remove("hidden");
      nativeMeta.innerHTML = `<strong>${escapeHtml(result.name)}</strong> • ${formatBytes(result.bytes)}<br><code>${escapeHtml(result.path)}</code>`;
      setStatus(status, "Archive selected. Choose the destination behavior and extract.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#extractArchiveBtn").addEventListener("click", async () => {
    try {
      const sameFolder = $("#extractBesideArchive").checked;
      const password = $("#extractArchivePassword").value;
      if (selected) {
        const api = getNativeApi();
        if (!api?.extract_archive) throw new Error("The native extraction bridge is not ready. Retry in a moment.");
        setStatus(status, "Extracting locally…");
        const result = await api.extract_archive(selected.path, sameFolder, password);
        if (!result) {
          setStatus(status, "Extraction cancelled.", "warning");
          return;
        }
        setStatus(
          status,
          `Done. Extracted ${result.files} file(s), ${formatBytes(result.bytes)}.\n${result.path}`,
          "success",
        );
        return;
      }

      const uploaded = firstFile("extractArchiveFile");
      if (!uploaded) throw new Error("Choose or drop a compressed file first.");
      const form = new FormData();
      form.append("file", uploaded, uploaded.name);
      form.append("password", password);
      setStatus(status, "Uploading and extracting locally…");
      const response = await apiFetch("/api/document-security/extract-upload", {
        method: "POST",
        body: form,
        progressElement: status,
        progressLabel: "Extracting compressed file locally…",
      });
      if (!response.ok) throw new Error(await parseError(response));
      const result = await response.json();
      setStatus(
        status,
        `Done. Extracted ${result.files} file(s), ${formatBytes(result.bytes)}.\n${result.path}${result.explorer_opened ? "\nWindows Explorer opened the folder." : ""}`,
        "success",
      );
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
