import { $, setStatus } from "/frontend/assets/js/core/dom.js?v=4.5";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js?v=4.5";
import { firstFile } from "/frontend/assets/js/core/file_store.js?v=4.5";

export function bindArchiveDownload({
  buttonId,
  inputId,
  endpoint,
  statusId,
  fallback,
  passwordId = null,
  confirmId = null,
  minPasswordLength = 8,
  workingMessage = "Securing your file locally…",
}) {
  $(`#${buttonId}`).addEventListener("click", async () => {
    const status = $(`#${statusId}`);
    try {
      const file = firstFile(inputId);
      if (!file) throw new Error("Choose or drop a file first.");
      let password = null;
      if (passwordId) {
        password = $(`#${passwordId}`).value;
        if (password.length < minPasswordLength) {
          const requirement = minPasswordLength === 1
            ? "Enter the archive password."
            : `Use a password with at least ${minPasswordLength} characters.`;
          throw new Error(requirement);
        }
        if (confirmId && password !== $(`#${confirmId}`).value) {
          throw new Error("Password confirmation does not match.");
        }
      }
      const form = formWithSingleFile(inputId);
      if (password !== null) form.append("password", password);
      await postDownload(endpoint, form, status, fallback, workingMessage);
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
