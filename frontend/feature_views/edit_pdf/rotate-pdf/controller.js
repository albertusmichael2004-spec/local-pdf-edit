import { $, $$, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js";
import { PageWorkspace } from "/frontend/assets/js/core/page_workspace.js";

export function init() {
  const status = $("#rotateStatus");
  let angle = 270;
  const workspace = new PageWorkspace({
    inputId: "rotateFile",
    container: "#rotatePageWorkspace",
    selectable: true,
    onSelectionChange: (pages) => {
      $("#rotateSelectionCount").textContent = `${pages.length} selected`;
      workspace.setPreviewRotationForSelected(angle);
    },
  });

  onFilesChanged("rotateFile", async (files) => {
    if (!files.length) {
      workspace.clear();
      $("#rotateControls").classList.add("hidden");
      $("#rotateWorkspaceWrap").classList.add("hidden");
      return;
    }
    try {
      await workspace.load(files[0]);
      $("#rotateControls").classList.remove("hidden");
      $("#rotateWorkspaceWrap").classList.toggle("hidden", $("#rotatePageMode").value !== "custom");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#rotatePageMode").addEventListener("change", () => {
    const custom = $("#rotatePageMode").value === "custom";
    $("#rotateWorkspaceWrap").classList.toggle("hidden", !custom);
    if (!custom) workspace.clearSelection();
  });

  $$("#rotateDirection .segment").forEach((button) => {
    button.addEventListener("click", () => {
      angle = Number(button.dataset.angle);
      $$("#rotateDirection .segment").forEach((item) => item.classList.toggle("active", item === button));
      workspace.setPreviewRotationForSelected(angle);
    });
  });

  $("#rotateBtn").addEventListener("click", async () => {
    try {
      if (!firstFile("rotateFile")) throw new Error("Choose or drop a file first.");
      const custom = $("#rotatePageMode").value === "custom";
      const selected = workspace.getSelectedPages();
      if (custom && !selected.length) throw new Error("Select at least one page to rotate.");
      const form = formWithSingleFile("rotateFile");
      form.append("pages", custom ? selected.join(",") : "all");
      form.append("angle", String(angle));
      await postDownload("/api/edit/rotate", form, status, "rotated.pdf", "Rotating selected pages locally…");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
