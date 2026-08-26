import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";
import { $ } from "/frontend/assets/js/core/dom.js";

export function init() {
  bindSimpleDownload({
    buttonId: "extractPagesBtn",
    inputId: "extractFile",
    endpoint: "/api/edit/extract-pages",
    statusId: "extractPagesStatus",
    fallback: "extracted.pdf",
    fields: () => ({ pages: $("#extractPagesInput").value }),
  });
}
