import { bindArchiveDownload } from "/frontend/feature_views/document_security/shared.js";

export function init() {
  bindArchiveDownload({
    buttonId: "decryptArchiveBtn",
    inputId: "decryptArchiveFile",
    endpoint: "/api/document-security/decrypt",
    statusId: "decryptArchiveStatus",
    fallback: "decrypted_file",
    passwordId: "decryptArchivePassword",
    minPasswordLength: 1,
    workingMessage: "Decrypting the archive locally…",
  });
}
