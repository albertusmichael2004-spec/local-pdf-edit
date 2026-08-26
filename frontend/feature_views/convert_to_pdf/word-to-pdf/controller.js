import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";

export function init() {
  bindSimpleDownload({
    buttonId: "wordToPdfBtn",
    inputId: "wordToPdfFile",
    endpoint: "/api/convert/word-to-pdf",
    statusId: "wordToPdfStatus",
    fallback: "document.pdf",
  });
}
