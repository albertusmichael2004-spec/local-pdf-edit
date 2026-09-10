import { $, setStatus } from "/frontend/assets/js/core/dom.js?v=4.5";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js?v=4.5";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js?v=4.5";
import { getNativeApi } from "/frontend/assets/js/core/native_api.js?v=6.0";

function filePathHint(file) {
  if (!file) return "";
  for (const key of ["pywebviewFullPath", "path", "fullPath"]) {
    const candidate = file[key];
    if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
  }
  return "";
}

function sameUpload(source, file) {
  return Boolean(
    source
      && source.kind === "file"
      && String(source.name || "").toLowerCase() === String(file.name || "").toLowerCase()
      && Number(source.bytes) === Number(file.size),
  );
}

export function init() {
  let nativeSource = null;
  const status = $("#allSecurityStatus");

  onFilesChanged("allSecurityFile", (files) => {
    nativeSource = null;
    const hintedPath = filePathHint(files[0]);
    if (hintedPath) {
      nativeSource = {
        path: hintedPath,
        name: files[0].name,
        bytes: files[0].size,
        kind: "file",
      };
    }
  });

  document.querySelector('.dropzone[data-input="allSecurityFile"]')?.addEventListener("directorydrop", () => {
    setStatus(status, "Upload a ZIP file when you need to protect a complete folder.", "error");
  });

  async function resolveNativeSource(file) {
    // Browser uploads intentionally do not expose an absolute source path.
    // The desktop bridge is only needed when the user explicitly enables the
    // destructive Recycle Bin option.
    if (sameUpload(nativeSource, file)) return nativeSource;
    const api = getNativeApi();
    if (!api?.choose_security_file) {
      throw new Error("Moving the original requires the desktop app's local file access.");
    }
    setStatus(status, "Confirm the original file in the desktop file dialog…");
    const result = await api.choose_security_file();
    if (!result) throw new Error("No original file was selected; the original was not changed.");
    const source = { ...result, kind: "file" };
    if (!sameUpload(source, file)) {
      throw new Error("The selected original does not match the uploaded file name and size. Nothing was changed.");
    }
    nativeSource = source;
    return source;
  }

  $("#allSecurityBtn").addEventListener("click", async () => {
    try {
      const password = $("#allSecurityPassword").value;
      if (password.length < 8) throw new Error("Use a password with at least 8 characters.");
      if (password !== $("#allSecurityConfirm").value) throw new Error("Password confirmation does not match.");
      const deleteOriginal = $("#deleteAllSecurityOriginal").checked;
      const reduceSize = $("#reduceAllSecuritySize").checked;

      const file = firstFile("allSecurityFile");
      if (!file) throw new Error("Choose or drop a file first.");

      if (deleteOriginal) {
        const source = await resolveNativeSource(file);
        const api = getNativeApi();
        if (!api?.secure_all_in_one) throw new Error("Moving the original requires the desktop app's local file access.");
        setStatus(status, "Creating and validating the encrypted archive beside the original…");
        const result = await api.secure_all_in_one(source.path, password, true, reduceSize);
        const removed = result.original_trashed ? " Original moved to Recycle Bin." : "";
        setStatus(status, `Done. Encrypted archive:\n${result.path}.${removed}\n${result.note || ""}`, "success");
        return;
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
