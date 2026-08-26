import { bindSimpleDownload } from "/frontend/assets/js/core/downloads.js";
import { $ } from "/frontend/assets/js/core/dom.js";

export function init() {
  bindSimpleDownload({
    buttonId: "unlockBtn",
    inputId: "unlockFile",
    endpoint: "/api/security/unlock",
    statusId: "unlockStatus",
    fallback: "unlocked.pdf",
    fields: () => ({ password: $("#unlockPassword").value }),
  });
}
