import { bindArchiveDownload } from "/frontend/feature_views/document_security/shared.js";

export function init() {
  bindArchiveDownload({
    buttonId: "aes256Btn",
    inputId: "aes256File",
    endpoint: "/api/document-security/aes256",
    statusId: "aes256Status",
    fallback: "document_aes256.7z",
    passwordId: "aes256Password",
    confirmId: "aes256Confirm",
    workingMessage: "Encrypting the file with AES-256 locally…",
  });
}
