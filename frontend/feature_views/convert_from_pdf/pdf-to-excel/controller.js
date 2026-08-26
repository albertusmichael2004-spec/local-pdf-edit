import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";

export function init() {
  bindSimpleDownload({
    buttonId: "pdfToExcelBtn",
    inputId: "pdfToExcelFile",
    endpoint: "/api/convert/pdf-to-excel",
    statusId: "pdfToExcelStatus",
    fallback: "tables.xlsx",
    workingMessage: "Extracting tables locally…",
  });
}
