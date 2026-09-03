import { bindArchiveDownload } from "/frontend/feature_views/document_security/shared.js";

export function init() {
  bindArchiveDownload({
    buttonId: "create7zBtn",
    inputId: "create7zFile",
    endpoint: "/api/document-security/create-7z",
    statusId: "create7zStatus",
    fallback: "document_archive.7z",
    workingMessage: "Creating a 7z archive locally…",
  });
}
