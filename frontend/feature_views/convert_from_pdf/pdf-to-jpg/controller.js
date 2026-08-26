import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";

export function init() {
  bindSimpleDownload({
    buttonId: "pdfToJpgBtn",
    inputId: "pdfToJpgFile",
    endpoint: "/api/convert/pdf-to-jpg",
    statusId: "pdfToJpgStatus",
    fallback: "pages_jpg.zip",
  });
}
