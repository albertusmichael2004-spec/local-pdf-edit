import { $, hideStatus, setStatus } from "/frontend/assets/js/core/dom.js";
import { clearFiles, getFiles, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { postDownload } from "/frontend/assets/js/core/downloads.js";
import { renderSortable } from "/frontend/assets/js/core/sortable.js";

export function init() {
  onFilesChanged("jpgFiles", () => renderSortable("jpgFiles", "jpgList"));
  renderSortable("jpgFiles", "jpgList");

  $("#clearJpgBtn").addEventListener("click", () => {
    clearFiles("jpgFiles");
    renderSortable("jpgFiles", "jpgList");
    hideStatus($("#jpgToPdfStatus"));
  });
  $("#jpgToPdfBtn").addEventListener("click", async () => {
    const status = $("#jpgToPdfStatus");
    const files = getFiles("jpgFiles");
    if (!files.length) return setStatus(status, "Add at least one image.", "error");
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    await postDownload(
      "/api/convert/jpg-to-pdf",
      form,
      status,
      "images.pdf",
      "Converting images locally…",
    );
  });
}
