import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";
import { $ } from "/frontend/assets/js/core/dom.js";

export function init() {
  bindSimpleDownload({
    buttonId: "removePagesBtn",
    inputId: "removeFile",
    endpoint: "/api/edit/remove-pages",
    statusId: "removePagesStatus",
    fallback: "pages_removed.pdf",
    fields: () => ({ pages: $("#removePagesInput").value }),
  });
}
