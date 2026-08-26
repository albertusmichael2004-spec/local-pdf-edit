import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";

export function init() {
  bindSimpleDownload({
    buttonId: "pdfToWordBtn",
    inputId: "pdfToWordFile",
    endpoint: "/api/convert/pdf-to-word",
    statusId: "pdfToWordStatus",
    fallback: "document.docx",
    workingMessage: "Reconstructing Word document locally…",
  });
}
