import { $, hideStatus, setStatus } from "/frontend/assets/js/core/dom.js";
import { clearFiles, getFiles, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { postDownload } from "/frontend/assets/js/core/downloads.js";
import { renderSortable } from "/frontend/assets/js/core/sortable.js";

export function init() {
  onFilesChanged("mergeFiles", () => renderSortable("mergeFiles", "mergeList"));
  renderSortable("mergeFiles", "mergeList");

  $("#clearMergeBtn").addEventListener("click", () => {
    clearFiles("mergeFiles");
    renderSortable("mergeFiles", "mergeList");
    hideStatus($("#mergeStatus"));
  });
  $("#mergeBtn").addEventListener("click", async () => {
    const status = $("#mergeStatus");
    const files = getFiles("mergeFiles");
    if (files.length < 2) return setStatus(status, "Add at least two PDFs.", "error");
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    await postDownload("/api/merge", form, status, "merged.pdf", "Merging PDFs locally…");
  });
}
