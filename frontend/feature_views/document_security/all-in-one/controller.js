import { $, escapeHtml, formatBytes, setStatus } from "/frontend/assets/js/core/dom.js?v=4.5";
import { clearFiles, firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js?v=4.5";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js?v=4.5";
import { getNativeApi } from "/frontend/assets/js/core/native_api.js?v=6.0";

export function init() {
  let nativeSource = null;
  const nativeMeta = $("#allSecurityNativeMeta");
  const status = $("#allSecurityStatus");

  onFilesChanged("allSecurityFile", (files) => {
    if (!files.length) return;
    nativeSource = null;
    nativeMeta.classList.add("hidden");
    nativeMeta.textContent = "";
  });

  $("#chooseAllSecurityNative").addEventListener("click", async () => {
    try {
      const api = getNativeApi();
      if (!api) throw new Error("Native file selection is available in the desktop app.");
      const result = await api.choose_security_file();
      if (!result) return;
      clearFiles("allSecurityFile");
      nativeSource = { ...result, kind: "file" };
      nativeMeta.classList.remove("hidden");
      nativeMeta.innerHTML = `<strong>${escapeHtml(result.name)}</strong> • ${formatBytes(result.bytes)}<br><code>${escapeHtml(result.path)}</code>`;
      setStatus(status, "Local source selected.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#chooseAllSecurityFolder").addEventListener("click", async () => {
    try {
      const api = getNativeApi();
      if (!api?.choose_security_folder) throw new Error("Native folder selection is available in the desktop app.");
      const result = await api.choose_security_folder();
      if (!result) return;
      clearFiles("allSecurityFile");
      nativeSource = { ...result, kind: "folder" };
      nativeMeta.classList.remove("hidden");
      nativeMeta.innerHTML = `<strong>${escapeHtml(result.name)}</strong> • Complete folder<br><code>${escapeHtml(result.path)}</code>`;
      setStatus(status, "Local folder selected. Its complete structure will be encrypted.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  document.querySelector('.dropzone[data-input="allSecurityFile"]')?.addEventListener("directorydrop", () => {
    setStatus(status, "Use “Choose local folder” so the desktop app can read the complete folder path.", "error");
  });

  $("#allSecurityBtn").addEventListener("click", async () => {
    try {
      const password = $("#allSecurityPassword").value;
      if (password.length < 8) throw new Error("Use a password with at least 8 characters.");
      if (password !== $("#allSecurityConfirm").value) throw new Error("Password confirmation does not match.");
      const deleteOriginal = $("#deleteAllSecurityOriginal").checked;
      const reduceSize = $("#reduceAllSecuritySize").checked;

      if (nativeSource) {
        const api = getNativeApi();
        if (!api) throw new Error("Native encryption requires the desktop app.");
        setStatus(status, nativeSource.kind === "folder"
          ? "Compressing and encrypting the complete folder locally…"
          : "Creating and validating the encrypted archive locally…");
        const result = await api.secure_all_in_one(nativeSource.path, password, deleteOriginal, reduceSize);
        const removed = result.original_trashed ? " Original moved to Recycle Bin." : "";
        setStatus(status, `Done. Encrypted archive:\n${result.path}.${removed}\n${result.note || ""}`, "success");
        return;
      }

      if (!firstFile("allSecurityFile")) throw new Error("Choose or drop a file first.");
      if (deleteOriginal) {
        throw new Error("To remove the original safely, use the local file or folder picker first.");
      }
      const form = formWithSingleFile("allSecurityFile");
      form.append("password", password);
      form.append("reduce_size", reduceSize ? "true" : "false");
      await postDownload(
        "/api/document-security/all-in-one",
        form,
        status,
        "document_secured.7z",
        "Creating an AES-256 encrypted 7z locally…",
      );
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
