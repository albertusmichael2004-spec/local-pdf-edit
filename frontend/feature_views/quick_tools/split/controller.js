import { $, $$, escapeHtml, formatBytes, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js";
import { inspectPdf, previewPdf } from "/frontend/assets/js/core/previews.js";

let splitTotalPages = 0;
let splitMode = "range";
let splitRanges = [{ from: 1, to: 1 }];
let activeRangeIndex = 0;
let previewTimer = null;

function clampPage(value) {
  const numeric = Math.max(1, Number(value) || 1);
  return splitTotalPages ? Math.min(splitTotalPages, numeric) : numeric;
}

function renderRangeRows() {
  const container = $("#rangeRows");
  container.innerHTML = "";
  splitRanges.forEach((range, index) => {
    const row = document.createElement("div");
    row.className = `range-row-card ${index === activeRangeIndex ? "active" : ""}`;
    row.innerHTML = `
      <div class="range-row-top">
        <strong>Range ${index + 1}</strong>
        ${splitRanges.length > 1 ? '<button type="button">Remove</button>' : ""}
      </div>
      <div class="range-inputs">
        <label>from <input type="number" min="1" ${splitTotalPages ? `max="${splitTotalPages}"` : ""} value="${range.from}" data-side="from" /></label>
        <label>to <input type="number" min="1" ${splitTotalPages ? `max="${splitTotalPages}"` : ""} value="${range.to}" data-side="to" /></label>
      </div>`;
    row.addEventListener("click", () => {
      activeRangeIndex = index;
      renderRangeRows();
      scheduleSplitPreview();
    });
    row.querySelectorAll("input").forEach((input) => {
      input.addEventListener("click", (event) => event.stopPropagation());
      input.addEventListener("input", (event) => {
        splitRanges[index][event.target.dataset.side] = clampPage(event.target.value);
        activeRangeIndex = index;
        $("#splitPreviewLabel").textContent = `Range ${index + 1}`;
        scheduleSplitPreview();
      });
    });
    const remove = row.querySelector("button");
    if (remove) {
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        splitRanges.splice(index, 1);
        activeRangeIndex = Math.min(activeRangeIndex, splitRanges.length - 1);
        renderRangeRows();
        scheduleSplitPreview();
      });
    }
    container.appendChild(row);
  });
}

async function updateSplitPreview() {
  const file = firstFile("splitFile");
  if (!file || !splitTotalPages || !splitRanges.length) return;
  const range = splitRanges[activeRangeIndex];
  const from = clampPage(range.from);
  const to = clampPage(range.to);
  $("#splitFromLabel").textContent = `Page ${from}`;
  $("#splitToLabel").textContent = `Page ${to}`;
  try {
    const data = await previewPdf(file, [from, to]);
    const map = new Map(data.previews.map((item) => [item.page, item.image]));
    $("#splitFromPreview").src = map.get(from) || "";
    $("#splitToPreview").src = map.get(to) || map.get(from) || "";
  } catch (error) {
    setStatus($("#splitStatus"), error.message || String(error), "error");
  }
}

function scheduleSplitPreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(updateSplitPreview, 280);
}

export function init() {
  renderRangeRows();
  onFilesChanged("splitFile", async (files) => {
    if (!files.length) return;
    try {
      const info = await inspectPdf(files[0]);
      splitTotalPages = info.pages;
      splitRanges = [{ from: 1, to: info.pages }];
      activeRangeIndex = 0;
      $("#splitPageCount").textContent = `${info.pages} pages • ${formatBytes(info.bytes)}`;
      $("#splitFileMeta").classList.remove("hidden");
      $("#splitFileMeta").innerHTML = `<strong>${escapeHtml(info.name)}</strong> • ${info.pages} pages • ${formatBytes(info.bytes)}`;
      renderRangeRows();
      updateSplitPreview();
    } catch (error) {
      setStatus($("#splitStatus"), error.message || String(error), "error");
    }
  });

  $("#addRangeBtn").addEventListener("click", () => {
    splitRanges.push({ from: 1, to: splitTotalPages || 1 });
    activeRangeIndex = splitRanges.length - 1;
    renderRangeRows();
    scheduleSplitPreview();
  });

  $$(".mode-tab").forEach((button) => {
    button.addEventListener("click", () => {
      splitMode = button.dataset.splitMode;
      $$(".mode-tab").forEach((item) => item.classList.toggle("active", item === button));
      $$(".split-mode-body").forEach((item) => item.classList.remove("active"));
      $(`#split${splitMode[0].toUpperCase() + splitMode.slice(1)}Mode`).classList.add("active");
    });
  });

  $("#splitBtn").addEventListener("click", async () => {
    const status = $("#splitStatus");
    try {
      const form = formWithSingleFile("splitFile");
      form.append("mode", splitMode);
      if (splitMode === "range") {
        for (const range of splitRanges) {
          if (Number(range.from) > Number(range.to)) {
            throw new Error("Each range must have from page <= to page.");
          }
        }
        form.append(
          "ranges",
          splitRanges.map((range) => `${clampPage(range.from)}-${clampPage(range.to)}`).join(";"),
        );
        form.append("merge_ranges", $("#mergeRanges").checked ? "true" : "false");
      } else if (splitMode === "pages") {
        form.append("every_n", $("#splitEveryN").value);
      } else {
        form.append("max_size_mb", $("#splitMaxSize").value);
      }
      await postDownload("/api/split", form, status, "split-pdf.zip", "Splitting PDF locally…");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
