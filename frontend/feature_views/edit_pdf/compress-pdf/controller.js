import { $, $$, escapeHtml, formatBytes, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js";
import { inspectPdf } from "/frontend/assets/js/core/previews.js";

export function init() {
  $$("input[name='compressionMode']").forEach((radio) => {
    radio.addEventListener("change", () => {
      $$("#compressionProfiles .profile").forEach((profile) => {
        profile.classList.toggle("selected", profile.contains(radio));
      });
    });
  });

  onFilesChanged("compressFile", async (files) => {
    if (!files.length) return;
    try {
      const info = await inspectPdf(files[0]);
      $("#compressFileMeta").classList.remove("hidden");
      $("#compressFileMeta").innerHTML = `<strong>${escapeHtml(info.name)}</strong> • ${info.pages} pages • ${formatBytes(info.bytes)}`;
    } catch {
      // The compression endpoint returns the final validation error.
    }
  });

  $("#compressBtn").addEventListener("click", async () => {
    const status = $("#compressStatus");
    try {
      if (!firstFile("compressFile")) throw new Error("Choose or drop a file first.");
      const form = formWithSingleFile("compressFile");
      const mode = $("input[name='compressionMode']:checked").value;
      form.append("mode", mode);
      if (mode === "custom") {
        form.append("target_min_mb", $("#targetMinMb").value);
        form.append("target_max_mb", $("#targetMaxMb").value);
      }
      await postDownload(
        "/api/edit/compress",
        form,
        status,
        "compressed.pdf",
        "Compressing locally. Custom mode may test several candidates…",
      );
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
