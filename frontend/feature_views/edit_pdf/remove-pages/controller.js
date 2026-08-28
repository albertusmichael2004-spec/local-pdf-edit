import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";
import { $ } from "/frontend/assets/js/core/dom.js";
import { bindPageSelection } from "/frontend/assets/js/core/page_selection.js";

export function init() {
  bindPageSelection({
    inputId: "removeFile",
    workspaceId: "removePageWorkspace",
    wrapperId: "removeWorkspaceWrap",
    countId: "removeSelectionCount",
    pagesInputId: "removePagesInput",
    statusId: "removePagesStatus",
  });
  bindSimpleDownload({
    buttonId: "removePagesBtn",
    inputId: "removeFile",
    endpoint: "/api/edit/remove-pages",
    statusId: "removePagesStatus",
    fallback: "pages_removed.pdf",
    fields: () => ({ pages: $("#removePagesInput").value }),
  });
}
