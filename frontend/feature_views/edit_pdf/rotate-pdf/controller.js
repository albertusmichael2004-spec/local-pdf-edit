import { $, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js";
import { PageWorkspace } from "/frontend/assets/js/core/page_workspace.js";
import { previewPdf } from "/frontend/assets/js/core/previews.js";

export function init() {
  const status = $("#rotateStatus");
  let file = null;
  let allAngle = 0;

  function updateCustomCount() {
    const count = workspace.items.filter((item) => item.rotation).length;
    $("#rotateSelectionCount").textContent = `${count} page${count === 1 ? "" : "s"} rotated`;
  }

  const workspace = new PageWorkspace({
    inputId: "rotateFile",
    container: "#rotatePageWorkspace",
    onCardClick: (item) => {
      item.rotation = (item.rotation + 90) % 360;
      item.edited = Boolean(item.rotation);
      workspace.render();
      updateCustomCount();
    },
  });

  function updateAllPreview() {
    $("#rotatePreviewImage").style.transform = allAngle ? `rotate(${allAngle}deg)` : "";
    $("#rotateAngleLabel").textContent = `Current rotation: ${allAngle}°`;
  }

  onFilesChanged("rotateFile", async (files) => {
    file = files[0] || null;
    if (!files.length) {
      workspace.clear();
      $("#rotateControls").classList.add("hidden");
      $("#rotateWorkspaceWrap").classList.add("hidden");
      $("#rotateAllPreview").classList.add("hidden");
      return;
    }
    try {
      allAngle = 0;
      updateAllPreview();
      const [preview] = await Promise.all([
        previewPdf(file, [1]),
        workspace.load(file),
      ]);
      $("#rotatePreviewImage").src = preview.previews?.[0]?.image || "";
      $("#rotateControls").classList.remove("hidden");
      $("#rotateAllPreview").classList.remove("hidden");
      $("#rotateWorkspaceWrap").classList.add("hidden");
      updateCustomCount();
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#rotatePageMode").addEventListener("change", () => {
    const custom = $("#rotatePageMode").value === "custom";
    $("#rotateWorkspaceWrap").classList.toggle("hidden", !custom);
    $("#rotateAllPreview").classList.toggle("hidden", custom);
    $("#rotateAllAction").classList.toggle("hidden", custom);
  });

  $("#rotateClockwise").addEventListener("click", () => {
    allAngle = (allAngle + 90) % 360;
    updateAllPreview();
  });

  $("#rotateBtn").addEventListener("click", async () => {
    try {
      if (!firstFile("rotateFile")) throw new Error("Choose or drop a file first.");
      const custom = $("#rotatePageMode").value === "custom";
      const form = formWithSingleFile("rotateFile");
      if (custom) {
        const plan = Object.fromEntries(
          workspace.items.filter((item) => item.rotation).map((item) => [item.sourcePage, item.rotation]),
        );
        if (!Object.keys(plan).length) throw new Error("Click at least one page to rotate it.");
        form.append("rotation_plan_json", JSON.stringify(plan));
      } else {
        if (!allAngle) throw new Error("Click Rotate 90° clockwise before exporting.");
        form.append("pages", "all");
        form.append("angle", String(allAngle));
      }
      await postDownload("/api/edit/rotate", form, status, "rotated.pdf", "Rotating selected pages locally…");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
