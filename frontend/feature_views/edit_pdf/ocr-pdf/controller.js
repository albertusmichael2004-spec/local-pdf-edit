import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";
import { $ } from "/frontend/assets/js/core/dom.js";

export function init() {
  bindSimpleDownload({
    buttonId: "ocrBtn",
    inputId: "ocrFile",
    endpoint: "/api/edit/ocr",
    statusId: "ocrStatus",
    fallback: "ocr.pdf",
    fields: () => ({ language: $("#ocrLanguage").value, dpi: $("#ocrDpi").value }),
    workingMessage: "Running OCR locally. This can take time for large scans…",
  });
}
