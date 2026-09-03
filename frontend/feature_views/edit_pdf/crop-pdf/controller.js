import { $, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js";
import { PageWorkspace } from "/frontend/assets/js/core/page_workspace.js";
import { previewPdf } from "/frontend/assets/js/core/previews.js";
import { CropBoxEditor } from "/frontend/assets/js/core/crop_box.js";

export function init() {
  const status = $("#cropStatus");
  let file = null;
  let activePage = 1;
  const previews = new Map();
  const cropBox = new CropBoxEditor({
    wrapper: $("#cropPaper"),
    image: $("#cropPreviewImage"),
    box: $("#cropBox"),
    inputs: { left: $("#cropLeft"), top: $("#cropTop"), right: $("#cropRight"), bottom: $("#cropBottom") },
  });

  function currentMargins() {
    return {
      left_mm: Math.max(0, Number($("#cropLeft").value || 0)),
      top_mm: Math.max(0, Number($("#cropTop").value || 0)),
      right_mm: Math.max(0, Number($("#cropRight").value || 0)),
      bottom_mm: Math.max(0, Number($("#cropBottom").value || 0)),
    };
  }

  function setMargins(margins = {}) {
    $("#cropLeft").value = margins.left_mm ?? 0;
    $("#cropTop").value = margins.top_mm ?? 0;
    $("#cropRight").value = margins.right_mm ?? 0;
    $("#cropBottom").value = margins.bottom_mm ?? 0;
  }

  async function getPreview(pageNumber) {
    if (previews.has(pageNumber)) return previews.get(pageNumber);
    const data = await previewPdf(file, [pageNumber]);
    const preview = data.previews?.[0];
    if (preview) previews.set(pageNumber, preview);
    return preview;
  }

  async function showSample(pageNumber, margins = null) {
    if (!file) return;
    const preview = await getPreview(pageNumber);
    if (!preview) return;
    setMargins(margins || {});
    cropBox.setPreview(preview);
    activePage = pageNumber;
    $("#cropPreviewLabel").textContent = `Page ${pageNumber}${margins ? " · crop applied" : ""}`;
  }

  function croppedThumbnail(preview, margins) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        const widthMm = (Number(preview.width_pt) || 595) * 25.4 / 72;
        const heightMm = (Number(preview.height_pt) || 842) * 25.4 / 72;
        const left = Math.round(image.naturalWidth * margins.left_mm / widthMm);
        const right = Math.round(image.naturalWidth * margins.right_mm / widthMm);
        const top = Math.round(image.naturalHeight * margins.top_mm / heightMm);
        const bottom = Math.round(image.naturalHeight * margins.bottom_mm / heightMm);
        const width = Math.max(1, image.naturalWidth - left - right);
        const height = Math.max(1, image.naturalHeight - top - bottom);
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        canvas.getContext("2d").drawImage(image, left, top, width, height, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", 0.86));
      };
      image.onerror = reject;
      image.src = preview.image;
    });
  }

  const workspace = new PageWorkspace({
    inputId: "cropFile",
    container: "#cropPageWorkspace",
    selectable: true,
    checkboxSelection: true,
    onSelectionChange: async (pages) => {
      $("#cropSelectionCount").textContent = `${pages.length} selected`;
    },
    onCardClick: async (item) => {
      workspace.items.forEach((entry) => { entry.active = entry === item; });
      workspace.render();
      await showSample(item.sourcePage, item.cropMargins);
    },
  });

  onFilesChanged("cropFile", async (files) => {
    file = files[0] || null;
    workspace.clear();
    previews.clear();
    if (!file) {
      $("#cropEditor").classList.add("hidden");
      return;
    }
    try {
      $("#cropEditor").classList.remove("hidden");
      $("#cropPageMode").value = "all";
      $("#cropWorkspaceWrap").classList.add("hidden");
      await workspace.load(file);
      workspace.items[0].active = true;
      workspace.render();
      await showSample(1, null);
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#cropPageMode").addEventListener("change", async () => {
    const custom = $("#cropPageMode").value === "custom";
    $("#cropWorkspaceWrap").classList.toggle("hidden", !custom);
    if (!custom) {
      workspace.clearSelection();
      const item = workspace.items.find((entry) => entry.sourcePage === activePage) || workspace.items[0];
      await showSample(item?.sourcePage || 1, item?.cropMargins);
    }
  });

  $("#unselectCropPages").addEventListener("click", () => workspace.clearSelection());

  $("#applyCrop").addEventListener("click", async () => {
    try {
      if (!file || !workspace.items.length) throw new Error("Upload a PDF first.");
      const margins = currentMargins();
      const custom = $("#cropPageMode").value === "custom";
      let targets;
      if (!custom) {
        targets = workspace.items;
      } else {
        targets = workspace.items.filter((item) => item.selected);
        if (!targets.length) {
          const active = workspace.items.find((item) => item.sourcePage === activePage);
          targets = active ? [active] : [];
        }
      }
      if (!targets.length) throw new Error("Choose a page to crop.");
      for (const item of targets) {
        const preview = await getPreview(item.sourcePage);
        item.cropMargins = { ...margins };
        item.previewImage = await croppedThumbnail(preview, margins);
        item.edited = true;
      }
      workspace.render();
      const active = workspace.items.find((item) => item.sourcePage === activePage);
      await showSample(activePage, active?.cropMargins);
      setStatus(status, `Crop applied to ${targets.length} page${targets.length === 1 ? "" : "s"}.`, "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#cropBtn").addEventListener("click", async () => {
    try {
      if (!firstFile("cropFile")) throw new Error("Choose or drop a file first.");
      const plan = Object.fromEntries(
        workspace.items
          .filter((item) => item.edited && item.cropMargins)
          .map((item) => [item.sourcePage, item.cropMargins]),
      );
      if (!Object.keys(plan).length) throw new Error("Click Apply crop before exporting.");
      const form = formWithSingleFile("cropFile");
      form.append("crop_plan_json", JSON.stringify(plan));
      await postDownload("/api/edit/crop", form, status, "cropped.pdf", "Cropping selected pages locally…");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
