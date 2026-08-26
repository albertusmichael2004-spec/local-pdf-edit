import { apiFetch, parseError } from "/frontend/assets/js/core/api.js";
import { $, escapeHtml, setStatus } from "/frontend/assets/js/core/dom.js";
import { postDownload } from "/frontend/assets/js/core/downloads.js";
import { firstFile } from "/frontend/assets/js/core/file_store.js";

function renderCompareResults(data) {
  const container = $("#compareResults");
  container.classList.remove("hidden");
  const overallClass = data.byte_identical ? "same" : (data.different_pages === 0 ? "same" : "changed");
  const cards = `
    <div class="compare-summary-grid">
      <div class="compare-card ${overallClass}"><span>Byte-identical</span><strong>${data.byte_identical ? "YES" : "NO"}</strong></div>
      <div class="compare-card"><span>Pages</span><strong>${data.left_pages} vs ${data.right_pages}</strong></div>
      <div class="compare-card"><span>Changed pages</span><strong>${data.different_pages}</strong></div>
      <div class="compare-card"><span>Exact characters</span><strong>${data.exact_character_pages}/${data.total_compared_pages}</strong></div>
      <div class="compare-card"><span>Exact word sequence</span><strong>${data.exact_word_pages}/${data.total_compared_pages}</strong></div>
      <div class="compare-card"><span>Visually identical</span><strong>${data.visually_identical_pages}/${data.total_compared_pages}</strong></div>
    </div>`;

  const rows = data.page_results.map((page) => {
    const changed = !(page.character_exact && page.word_sequence_exact && page.visually_identical && page.exists_left && page.exists_right);
    const wordDetails = (page.word_changes_preview || []).map((change) =>
      `<li><b>${escapeHtml(change.type)}</b>: <code>${escapeHtml(change.left || "∅")}</code> → <code>${escapeHtml(change.right || "∅")}</code></li>`,
    ).join("") || "<li>No word differences.</li>";
    const charDetails = (page.character_changes_preview || []).slice(0, 8).map((change) =>
      `<li><b>${escapeHtml(change.type)}</b> @ L${change.left_index}/R${change.right_index}: <code>${escapeHtml(change.left || "∅")}</code> → <code>${escapeHtml(change.right || "∅")}</code></li>`,
    ).join("") || "<li>No character differences.</li>";
    return `
      <details class="compare-page ${changed ? "changed" : "same"}">
        <summary><span>Page ${page.page}</span><span>${changed ? "Changed" : "Exact match"}</span><span>Words ${(page.word_similarity * 100).toFixed(2)}%</span><span>Chars ${(page.character_similarity * 100).toFixed(2)}%</span><span>Pixels ${(page.pixel_difference * 100).toFixed(3)}%</span></summary>
        <div class="compare-detail-grid">
          <div><b>Exact checks</b><p>Text: ${page.text_exact ? "Yes" : "No"}<br>Word sequence: ${page.word_sequence_exact ? "Yes" : "No"}<br>Character-for-character: ${page.character_exact ? "Yes" : "No"}<br>Visual: ${page.visually_identical ? "Yes" : "No"}</p></div>
          <div><b>Characters</b><p>${page.left_characters} vs ${page.right_characters}<br>+${page.chars_inserted} / −${page.chars_deleted} / replaced ${page.chars_replaced}</p></div>
          <div><b>Words</b><p>${page.left_words} vs ${page.right_words}<br>+${page.words_inserted} / −${page.words_deleted} / replaced ${page.words_replaced}</p></div>
        </div>
        <div class="compare-diff-columns"><div><b>Word-level changes</b><ul>${wordDetails}</ul></div><div><b>Character-level changes</b><ul>${charDetails}</ul></div></div>
      </details>`;
  }).join("");

  container.innerHTML = `${cards}<div class="compare-hashes"><b>SHA-256</b><code>${escapeHtml(data.sha256_left)}</code><code>${escapeHtml(data.sha256_right)}</code></div><p class="helper">${escapeHtml(data.comparison_note || "")}</p><div class="compare-pages">${rows}</div>`;
}

export function init() {
  $("#comparePdfBtn").addEventListener("click", async () => {
    const status = $("#comparePdfStatus");
    try {
      const left = firstFile("compareLeft");
      const right = firstFile("compareRight");
      if (!left || !right) throw new Error("Choose both PDFs first.");
      const form = new FormData();
      form.append("left", left);
      form.append("right", right);
      setStatus(status, "Comparing SHA-256, pages, exact words, exact characters and rendered pixels locally…");
      const response = await apiFetch("/api/security/compare-pdf-summary", { method: "POST", body: form });
      if (!response.ok) throw new Error(await parseError(response));
      const data = await response.json();
      renderCompareResults(data);
      $("#downloadCompareBtn").disabled = false;
      setStatus(
        status,
        data.different_pages === 0
          ? "Comparison complete. No page-level content or visual differences detected."
          : `Comparison complete. ${data.different_pages} page(s) contain differences.`,
        data.different_pages === 0 ? "success" : "warning",
      );
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#downloadCompareBtn").addEventListener("click", async () => {
    const status = $("#comparePdfStatus");
    try {
      const left = firstFile("compareLeft");
      const right = firstFile("compareRight");
      if (!left || !right) throw new Error("Choose both PDFs first.");
      const form = new FormData();
      form.append("left", left);
      form.append("right", right);
      await postDownload(
        "/api/security/compare-pdf",
        form,
        status,
        "pdf_comparison_report.zip",
        "Building downloadable comparison report and visual diff images…",
      );
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
