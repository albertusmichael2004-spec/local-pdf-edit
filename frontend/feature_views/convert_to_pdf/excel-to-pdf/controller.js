import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";

export function init() {
  bindSimpleDownload({
    buttonId: "excelToPdfBtn",
    inputId: "excelToPdfFile",
    endpoint: "/api/convert/excel-to-pdf",
    statusId: "excelToPdfStatus",
    fallback: "workbook.pdf",
  });
}
