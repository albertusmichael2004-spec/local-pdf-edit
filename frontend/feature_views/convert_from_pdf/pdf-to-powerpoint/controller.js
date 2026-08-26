import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";

export function init() {
  bindSimpleDownload({
    buttonId: "pdfToPptBtn",
    inputId: "pdfToPptFile",
    endpoint: "/api/convert/pdf-to-powerpoint",
    statusId: "pdfToPptStatus",
    fallback: "presentation.pptx",
    workingMessage: "Rendering PDF pages into PowerPoint slides…",
  });
}
