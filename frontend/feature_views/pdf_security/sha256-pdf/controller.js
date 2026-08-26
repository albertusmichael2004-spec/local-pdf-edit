import { apiFetch, parseError } from "/frontend/assets/js/core/api.js";
import { $, setStatus } from "/frontend/assets/js/core/dom.js";
import { formWithSingleFile } from "/frontend/assets/js/core/downloads.js";

export function init() {
  $("#shaBtn").addEventListener("click", async () => {
    const status = $("#shaStatus");
    try {
      const form = formWithSingleFile("shaFile");
      setStatus(status, "Hashing locally…");
      const response = await apiFetch("/api/security/sha256", { method: "POST", body: form });
      if (!response.ok) throw new Error(await parseError(response));
      const data = await response.json();
      setStatus(status, `${data.name}\nSHA-256\n${data.sha256}`, "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
