import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";

export function init() {
  bindSimpleDownload({
    buttonId: "pptToPdfBtn",
    inputId: "pptToPdfFile",
    endpoint: "/api/convert/powerpoint-to-pdf",
    statusId: "pptToPdfStatus",
    fallback: "presentation.pdf",
  });
}
