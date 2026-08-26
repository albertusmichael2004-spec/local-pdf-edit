import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";

export function init() {
  bindSimpleDownload({
    buttonId: "htmlToPdfBtn",
    inputId: "htmlToPdfFile",
    endpoint: "/api/convert/html-to-pdf",
    statusId: "htmlToPdfStatus",
    fallback: "page.pdf",
  });
}
