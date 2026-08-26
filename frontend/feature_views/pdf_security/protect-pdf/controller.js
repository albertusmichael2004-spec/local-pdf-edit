import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";
import { $ } from "/frontend/assets/js/core/dom.js";

export function init() {
  bindSimpleDownload({
    buttonId: "protectBtn",
    inputId: "protectFile",
    endpoint: "/api/security/protect",
    statusId: "protectStatus",
    fallback: "protected.pdf",
    fields: () => ({ password: $("#protectPassword").value }),
  });
}
