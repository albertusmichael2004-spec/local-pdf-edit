import { apiFetch, parseError } from "/frontend/assets/js/core/api.js";
import { $, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile } from "/frontend/assets/js/core/file_store.js";

export function init() {
  $("#shaCompareBtn").addEventListener("click", async () => {
    const status = $("#shaCompareStatus");
    try {
      const left = firstFile("shaLeft");
      const right = firstFile("shaRight");
      if (!left || !right) throw new Error("Choose both PDFs first.");
      const form = new FormData();
      form.append("left", left);
      form.append("right", right);
      setStatus(status, "Hashing both files locally…");
      const response = await apiFetch("/api/security/sha256-compare", { method: "POST", body: form });
      if (!response.ok) throw new Error(await parseError(response));
      const data = await response.json();
      const message = data.identical
        ? `IDENTICAL — both PDFs have the same SHA-256.\n${data.left.sha256}`
        : `DIFFERENT — the files are not byte-for-byte identical.\n\n${data.left.name}:\n${data.left.sha256}\n\n${data.right.name}:\n${data.right.sha256}`;
      setStatus(status, message, data.identical ? "success" : "warning");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
