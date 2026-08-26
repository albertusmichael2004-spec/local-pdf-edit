import { $, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js";
import { PageWorkspace } from "/frontend/assets/js/core/page_workspace.js";
import { previewPdf } from "/frontend/assets/js/core/previews.js";
import { CropBoxEditor } from "/frontend/assets/js/core/crop_box.js";

export function init() {
  const status = $("#cropStatus");
  let file = null;
  const cropBox = new CropBoxEditor({
    wrapper: $("#cropPaper"),
    image: $("#cropPreviewImage"),
    box: $("#cropBox"),
    inputs: { left: $("#cropLeft"), top: $("#cropTop"), right: $("#cropRight"), bottom: $("#cropBottom") },
  });

  async function showSample(pageNumber) {
    if (!file) return;
    const data = await previewPdf(file, [pageNumber]);
    const preview = data.previews?.[0];
    if (!preview) return;
    cropBox.setPreview(preview);
    $("#cropPreviewLabel").textContent = `Page ${pageNumber} sample`;
  }

  const workspace = new PageWorkspace({
    inputId: "cropFile",
    container: "#cropPageWorkspace",
    selectable: true,
    checkboxSelection: true,
    onSelectionChange: async (pages) => {
      $("#cropSelectionCount").textContent = `${pages.length} selected`;
      if (pages.length) await showSample(pages[0]);
    },
  });

  onFilesChanged("cropFile", async (files) => {
    file = files[0] || null;
    workspace.clear();
    if (!file) {
      $("#cropEditor").classList.add("hidden");
      return;
    }
    try {
      $("#cropEditor").classList.remove("hidden");
      $("#cropPageMode").value = "all";
      $("#cropWorkspaceWrap").classList.add("hidden");
      await showSample(1);
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#cropPageMode").addEventListener("change", async () => {
    const custom = $("#cropPageMode").value === "custom";
    $("#cropWorkspaceWrap").classList.toggle("hidden", !custom);
    if (custom && file && !workspace.file) await workspace.load(file);
    if (!custom) {
      workspace.clearSelection();
      await showSample(1);
    }
  });

  $("#cropBtn").addEventListener("click", async () => {
    try {
      if (!firstFile("cropFile")) throw new Error("Choose or drop a file first.");
      const custom = $("#cropPageMode").value === "custom";
      const selected = workspace.getSelectedPages();
      if (custom && !selected.length) throw new Error("Select at least one page to crop.");
      const form = formWithSingleFile("cropFile");
      form.append("pages", custom ? selected.join(",") : "all");
      form.append("left_mm", $("#cropLeft").value);
      form.append("top_mm", $("#cropTop").value);
      form.append("right_mm", $("#cropRight").value);
      form.append("bottom_mm", $("#cropBottom").value);
      await postDownload("/api/edit/crop", form, status, "cropped.pdf", "Cropping selected pages locally…");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
