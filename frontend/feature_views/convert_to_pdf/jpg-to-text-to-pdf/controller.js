import { $, hideStatus, setStatus } from "/frontend/assets/js/core/dom.js";
import { postDownload } from "/frontend/assets/js/core/downloads.js";
import { clearFiles, getFiles } from "/frontend/assets/js/core/file_store.js";
import { ImageWorkspace } from "/frontend/assets/js/core/image_workspace.js";

export function init(panel) {
  const inputId = "imageOcrFiles";
  const status = $("#imageOcrStatus");
  const outputFormat = $("#imageOcrOutputFormat");
  const layoutMode = $("#imageOcrLayoutMode");
  const layoutHint = $("#imageOcrLayoutHint");
  new ImageWorkspace({
    inputId,
    container: panel.querySelector("#imageOcrWorkspace"),
    wrapper: panel.querySelector("#imageOcrWorkspaceWrap"),
    count: panel.querySelector("#imageOcrPageCount"),
  });

  function syncLayout() {
    const isPdf = outputFormat.value === "pdf";
    layoutMode.disabled = !isPdf;
    if (!isPdf) layoutMode.value = "editable";
    layoutHint.textContent = !isPdf
      ? "Word output is fully editable and keeps the selected page order."
      : layoutMode.value === "preserve"
        ? "Preserve keeps each source image and adds aligned searchable text."
        : "Editable rebuilds recognized text into a clean text-based PDF.";
  }

  outputFormat.addEventListener("change", syncLayout);
  layoutMode.addEventListener("change", syncLayout);
  $("#imageOcrClearButton").addEventListener("click", () => {
    clearFiles(inputId);
    hideStatus(status);
  });
  $("#imageOcrExportButton").addEventListener("click", async () => {
    const files = getFiles(inputId);
    if (!files.length) {
      setStatus(status, "Add at least one image.", "error");
      return;
    }
    const format = outputFormat.value || "pdf";
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("output_format", format);
    form.append("language", $("#imageOcrLanguage").value || "auto");
    form.append("quality", $("#imageOcrQuality").value || "maximum");
    form.append("layout_mode", format === "pdf" ? layoutMode.value : "editable");
    await postDownload(
      "/api/convert/image-ocr-export",
      form,
      status,
      format === "docx" ? "image_ocr_text.docx" : "image_ocr_text.pdf",
      "Correcting page geometry and extracting text locally…",
    );
  });
  syncLayout();
  hideStatus(status);
}
