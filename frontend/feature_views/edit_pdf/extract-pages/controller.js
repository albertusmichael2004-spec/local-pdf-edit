import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";
import { $ } from "/frontend/assets/js/core/dom.js";
import { bindPageSelection } from "/frontend/assets/js/core/page_selection.js";

export function init() {
  bindPageSelection({
    inputId: "extractFile",
    workspaceId: "extractPageWorkspace",
    wrapperId: "extractWorkspaceWrap",
    countId: "extractSelectionCount",
    pagesInputId: "extractPagesInput",
    statusId: "extractPagesStatus",
  });
  bindSimpleDownload({
    buttonId: "extractPagesBtn",
    inputId: "extractFile",
    endpoint: "/api/edit/extract-pages",
    statusId: "extractPagesStatus",
    fallback: "extracted.pdf",
    fields: () => ({ pages: $("#extractPagesInput").value }),
  });
}
