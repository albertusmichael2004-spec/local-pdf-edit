import { apiFetch, parseError } from "/frontend/assets/js/core/api.js";
import { $, escapeHtml, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js";
import { PageWorkspace } from "/frontend/assets/js/core/page_workspace.js";
import { previewPdf } from "/frontend/assets/js/core/previews.js";

function fontCss(fontKey, select) {
  const option = [...select.options].find((item) => item.value === fontKey);
  return option?.textContent || "Arial";
}

function overlayElement(rule, fontSelect) {
  const overlay = document.createElement("div");
  overlay.className = "watermark-overlay";
  overlay.textContent = rule.text;
  overlay.style.opacity = String(rule.opacity);
  overlay.style.fontSize = `${Math.max(11, Math.min(34, rule.font_size * 0.38))}px`;
  overlay.style.transform = `translate(-50%, -50%) rotate(${rule.rotation}deg)`;
  overlay.style.fontFamily = `"${fontCss(rule.font_key, fontSelect)}", Arial, sans-serif`;
  return overlay;
}

export async function init() {
  const status = $("#watermarkStatus");
  const fontSelect = $("#watermarkFont");
  const rules = [];
  let sampleImage = "";

  const workspace = new PageWorkspace({
    inputId: "watermarkFile",
    container: "#watermarkPageWorkspace",
    selectable: true,
    checkboxSelection: true,
    onSelectionChange: (pages) => {
      $("#watermarkSelectionCount").textContent = `${pages.length} selected`;
    },
  });

  async function loadFonts() {
    try {
      const response = await apiFetch("/api/edit/watermark/fonts");
      if (!response.ok) return;
      const data = await response.json();
      for (const font of data.custom || []) {
        if ([...fontSelect.options].some((option) => option.value === font.key)) continue;
        const option = document.createElement("option");
        option.value = font.key;
        option.textContent = `${font.label} (custom)`;
        fontSelect.appendChild(option);
      }
    } catch {
      // Built-in font options remain usable.
    }
  }

  function renderRuleList() {
    const shell = $("#stagedWatermarks");
    if (!rules.length) {
      shell.classList.add("hidden");
      shell.innerHTML = "";
      return;
    }
    shell.classList.remove("hidden");
    shell.innerHTML = `<strong>Staged watermarks</strong>${rules.map((rule, index) => {
      const pages = rule.pages === "all" ? "All pages" : `Pages ${rule.pages.join(", ")}`;
      return `<div class="staged-rule"><span>${escapeHtml(rule.text)} • ${escapeHtml(pages)} • ${escapeHtml(fontCss(rule.font_key, fontSelect))}</span><button type="button" data-rule-index="${index}">Remove</button></div>`;
    }).join("")}`;
    shell.querySelectorAll("button[data-rule-index]").forEach((button) => button.addEventListener("click", () => {
      rules.splice(Number(button.dataset.ruleIndex), 1);
      renderAllOverlays();
      renderRuleList();
    }));
  }

  function renderAllOverlays() {
    const sample = $("#watermarkSampleOverlays");
    sample.innerHTML = "";
    rules.filter((rule) => rule.pages === "all" || rule.pages.includes(1)).forEach((rule) => sample.appendChild(overlayElement(rule, fontSelect)));

    $("#watermarkPageWorkspace").querySelectorAll(".page-editor-card").forEach((card) => {
      const preview = card.querySelector(".page-editor-preview");
      preview.querySelectorAll(".watermark-overlay").forEach((node) => node.remove());
      const page = Number(card.dataset.sourcePage);
      rules.filter((rule) => rule.pages === "all" || rule.pages.includes(page)).forEach((rule) => preview.appendChild(overlayElement(rule, fontSelect)));
    });
  }

  async function ensureCustomWorkspace() {
    const file = firstFile("watermarkFile");
    if (!file) return;
    if (!workspace.file || workspace.file !== file) await workspace.load(file);
    renderAllOverlays();
  }

  onFilesChanged("watermarkFile", async (files) => {
    rules.splice(0, rules.length);
    workspace.clear();
    if (!files.length) {
      $("#watermarkControls").classList.add("hidden");
      $("#watermarkPreviewArea").classList.add("hidden");
      return;
    }
    try {
      const preview = await previewPdf(files[0], [1]);
      sampleImage = preview.previews?.[0]?.image || "";
      $("#watermarkSampleImage").src = sampleImage;
      $("#watermarkControls").classList.remove("hidden");
      $("#watermarkPreviewArea").classList.remove("hidden");
      $("#watermarkAllSample").classList.remove("hidden");
      $("#watermarkPageWorkspace").classList.add("hidden");
      $("#watermarkPageMode").value = "all";
      renderRuleList();
      renderAllOverlays();
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#watermarkPageMode").addEventListener("change", async () => {
    const custom = $("#watermarkPageMode").value === "custom";
    $("#watermarkAllSample").classList.toggle("hidden", custom);
    $("#watermarkPageWorkspace").classList.toggle("hidden", !custom);
    $("#watermarkPreviewHint").textContent = custom ? "Check the pages that should receive the next watermark." : "Showing page 1 as an example for All pages.";
    $("#watermarkSelectionCount").textContent = custom ? `${workspace.getSelectedPages().length} selected` : "All pages";
    if (custom) await ensureCustomWorkspace();
  });

  $("#stageWatermark").addEventListener("click", async () => {
    try {
      const text = $("#watermarkText").value.trim();
      if (!text) throw new Error("Enter watermark text first.");
      const custom = $("#watermarkPageMode").value === "custom";
      if (custom) await ensureCustomWorkspace();
      const selected = workspace.getSelectedPages();
      if (custom && !selected.length) throw new Error("Check at least one page for this watermark.");
      rules.push({
        text,
        pages: custom ? selected : "all",
        opacity: Number($("#watermarkOpacity").value || 0.22),
        font_size: Number($("#watermarkFontSize").value || 42),
        rotation: Number($("#watermarkRotation").value || 45),
        font_key: fontSelect.value,
      });
      if (custom) workspace.clearSelection();
      renderAllOverlays();
      renderRuleList();
      setStatus(status, "Watermark staged. You can select another set of pages and add a different watermark before exporting.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#clearWatermarks").addEventListener("click", () => {
    rules.splice(0, rules.length);
    renderAllOverlays();
    renderRuleList();
    setStatus(status, "All staged watermarks were cleared.", "success");
  });

  $("#uploadWatermarkFont").addEventListener("click", async () => {
    const file = $("#watermarkFontFile").files?.[0];
    if (!file) return setStatus(status, "Choose a .ttf or .otf font first.", "error");
    const form = new FormData();
    form.append("file", file);
    try {
      setStatus(status, "Saving the custom font locally…");
      const response = await apiFetch("/api/edit/watermark/font", { method: "POST", body: form });
      if (!response.ok) throw new Error(await parseError(response));
      const data = await response.json();
      const option = document.createElement("option");
      option.value = data.key;
      option.textContent = `${data.label} (custom)`;
      fontSelect.appendChild(option);
      fontSelect.value = data.key;
      $("#watermarkFontFile").value = "";
      setStatus(status, "Custom font saved in the local data/fonts folder.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#watermarkExportBtn").addEventListener("click", async () => {
    try {
      if (!rules.length) throw new Error("Add at least one watermark before exporting.");
      const form = formWithSingleFile("watermarkFile");
      form.append("rules_json", JSON.stringify(rules));
      await postDownload("/api/edit/watermark", form, status, "watermarked.pdf", "Applying all staged watermarks locally…");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  await loadFonts();
}
