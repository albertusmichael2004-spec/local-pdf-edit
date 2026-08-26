import { $, setStatus } from "/frontend/assets/js/core/dom.js";
import { firstFile, onFilesChanged } from "/frontend/assets/js/core/file_store.js";
import { formWithSingleFile, postDownload } from "/frontend/assets/js/core/downloads.js";
import { PageWorkspace, parsePageOrderExpression } from "/frontend/assets/js/core/page_workspace.js";

export function init() {
  const status = $("#organizeStatus");
  const workspace = new PageWorkspace({
    inputId: "organizeFile",
    container: "#organizePageWorkspace",
    reorderable: true,
    organizeActions: true,
    onChange: (items) => {
      $("#organizePageCount").textContent = `${items.length} output pages`;
    },
  });

  onFilesChanged("organizeFile", async (files) => {
    if (!files.length) {
      workspace.clear();
      $("#organizeToolbar").classList.add("hidden");
      $("#organizeWorkspaceWrap").classList.add("hidden");
      return;
    }
    try {
      setStatus(status, "Rendering page thumbnails locally…");
      const info = await workspace.load(files[0]);
      $("#organizeOrder").value = `1-${info.pages}`;
      $("#organizePageCount").textContent = `${info.pages} output pages`;
      $("#organizeToolbar").classList.remove("hidden");
      $("#organizeWorkspaceWrap").classList.remove("hidden");
      status.classList.add("hidden");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#applyOrganizeOrder").addEventListener("click", () => {
    try {
      if (!workspace.info) throw new Error("Upload a PDF first.");
      workspace.applyOrder(parsePageOrderExpression($("#organizeOrder").value, workspace.info.pages));
      setStatus(status, "Typed page order applied to the visual arrangement.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#resetOrganizeOrder").addEventListener("click", async () => {
    try {
      const file = firstFile("organizeFile");
      if (!file) throw new Error("Upload a PDF first.");
      const info = await workspace.load(file);
      $("#organizeOrder").value = `1-${info.pages}`;
      $("#organizePageCount").textContent = `${info.pages} output pages`;
      setStatus(status, "Page arrangement reset to the original PDF.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#organizeBtn").addEventListener("click", async () => {
    try {
      if (!firstFile("organizeFile")) throw new Error("Choose or drop a file first.");
      if (!workspace.items.length) throw new Error("Load the page arrangement first.");
      const form = formWithSingleFile("organizeFile");
      form.append("plan_json", JSON.stringify(workspace.getPlan()));
      form.append("order", $("#organizeOrder").value || "");
      await postDownload("/api/edit/organize", form, status, "organized.pdf", "Building the organized PDF locally…");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
}
