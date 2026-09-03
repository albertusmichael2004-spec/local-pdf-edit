import { bindArchiveDownload } from "/frontend/feature_views/document_security/shared.js";

export function init() {
  bindArchiveDownload({
    buttonId: "passwordProtectBtn",
    inputId: "passwordProtectFile",
    endpoint: "/api/document-security/password-protect",
    statusId: "passwordProtectStatus",
    fallback: "document_protected.zip",
    passwordId: "passwordProtectPassword",
    confirmId: "passwordProtectConfirm",
    workingMessage: "Creating a password-protected ZIP locally…",
  });
}
