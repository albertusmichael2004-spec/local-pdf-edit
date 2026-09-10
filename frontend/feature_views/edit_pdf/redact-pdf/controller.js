import { apiFetch, downloadResponse, parseError } from "/frontend/assets/js/core/api.js";
import { bindAnimatedReorder } from "/frontend/assets/js/core/drag_reorder.js";
import { $, escapeHtml, formatBytes, setStatus } from "/frontend/assets/js/core/dom.js";
import { clearFiles, getFiles, onFilesChanged, replaceFiles } from "/frontend/assets/js/core/file_store.js";
import { PageWorkspace } from "/frontend/assets/js/core/page_workspace.js?v=7.5";
import { openPdfPreview } from "/frontend/assets/js/core/pdf_preview_modal.js?v=7.5";
import { populateThumb, previewPdf } from "/frontend/assets/js/core/previews.js?v=7.5";
import { RedactCanvas } from "/frontend/assets/js/core/redact_canvas.js";
import {
  bindWorkflowInput,
  stageWorkflowTransfer,
  workflowReferenceForFile,
} from "/frontend/assets/js/core/workflow_transfer.js";

const SOURCE_COLORS = [
  "#df3b35", "#2878b8", "#2d936c", "#9b51b5", "#df7f19", "#197f89",
  "#c43870", "#6775c9", "#6f8b25", "#a85a35", "#0086c9", "#7c5ab8",
];

function artifactFromReference(reference) {
  return {
    artifact_id: reference.artifactId,
    file_name: reference.fileName,
    media_type: reference.mediaType || "application/pdf",
    bytes: Number(reference.bytes || 0),
    page_count: Number(reference.pageCount || reference.pageIds?.length || 0),
    page_ids: reference.pageIds || [],
    page_sources: reference.pageSources || [],
    source_operation: reference.sourceOperation || "transfer",
  };
}

function referenceFor(workflowId, artifact, destination = null, comparisonArtifactId = null) {
  return {
    workflowId,
    artifactId: artifact.artifact_id,
    fileName: artifact.file_name,
    mediaType: artifact.media_type,
    bytes: artifact.bytes,
    pageCount: artifact.page_count,
    pageIds: artifact.page_ids,
    pageSources: artifact.page_sources,
    sourceOperation: artifact.source_operation,
    destination,
    sourceFeature: "redact",
    comparisonArtifactId,
  };
}

function temporaryFile(workflowId, artifact) {
  const reference = referenceFor(workflowId, artifact);
  const file = new File([], reference.fileName, {
    type: reference.mediaType,
    lastModified: Date.now(),
  });
  Object.defineProperty(file, "workflowBytes", { value: Number(reference.bytes || 0) });
  bindWorkflowInput("redactFile", file, reference);
  return file;
}

async function jsonResponse(response) {
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function init() {
  const status = $("#redactStatus");
  const fileIds = new WeakMap();
  const fileColors = new WeakMap();
  let fileSequence = 0;
  let colorSequence = 0;
  const state = {
    workflowId: null,
    sourceEntries: [],
    currentSource: null,
    previewFile: null,
    result: null,
    comparisonArtifact: null,
    marks: [],
    selectedMarkId: null,
    undo: [],
    redo: [],
    previews: new Map(),
    canvasPreviews: new Map(),
    activePage: 1,
    pageDirty: false,
    generation: 0,
    suppressFileChange: false,
    addonExpanded: { ocr: false, compress: false, protect: false },
    zoom: 100,
    thumbnailObserver: null,
  };

  function stableFileId(file) {
    if (!fileIds.has(file)) fileIds.set(file, `redact-file-${++fileSequence}`);
    return fileIds.get(file);
  }

  function sourceColor(file) {
    if (!fileColors.has(file)) {
      const color = SOURCE_COLORS[colorSequence]
        || `hsl(${Math.round((colorSequence * 137.508 + 7) % 360)} 62% 43%)`;
      fileColors.set(file, color);
      colorSequence += 1;
    }
    return fileColors.get(file);
  }

  const canvas = new RedactCanvas({
    paper: $("#redactPaper"),
    image: $("#redactCanvasImage"),
    overlay: $("#redactOverlay"),
    onCreate: (mark) => commitMarks([...state.marks, mark], { selectedMarkId: mark.mark_id }),
    onTextSelect: (selection) => selectTextByDrag(selection),
    onFocus: (mark) => selectMark(mark, { navigate: false, scrollList: true }),
  });

  const pageWorkspace = new PageWorkspace({
    inputId: "redactFile",
    container: "#redactPageWorkspace",
    reorderable: true,
    organizeActions: true,
    onChange: (items) => {
      $("#redactPageCount").textContent = `${items.length} output pages`;
      setPageDirty(true);
    },
  });

  function selectedAppearance() {
    return $("#redactAppearance").value || "black";
  }

  function appearancePayload() {
    return { mode: selectedAppearance(), color: $("#redactColor").value || "#000000" };
  }

  function withAppearance(mark) {
    return { ...mark, appearance: appearancePayload() };
  }

  function marksForPage(pageNumber) {
    return state.marks.filter((mark) => mark.page_number === pageNumber);
  }

  function updateHistoryControls() {
    $("#redactUndo").disabled = !state.undo.length;
    $("#redactRedo").disabled = !state.redo.length;
    $("#redactClearMarks").disabled = !state.marks.length;
  }

  function renderMarkList() {
    const list = $("#redactMarkList");
    $("#redactMarkCount").textContent = String(state.marks.length);
    if (!state.marks.length) {
      list.innerHTML = "<p>No marks yet.</p>";
      updateHistoryControls();
      return;
    }
    list.innerHTML = state.marks.map((mark, index) => {
      const label = ["search", "text_selection"].includes(mark.source)
        ? `“${escapeHtml(mark.search_text || "Search match")}”`
        : "Manual area";
      const selected = mark.mark_id === state.selectedMarkId;
      return `<div class="redact-mark-item${selected ? " selected" : ""}" data-mark-id="${escapeHtml(mark.mark_id)}"><button class="redact-mark-focus" aria-current="${selected ? "true" : "false"}" type="button"><span>${label}</span><small>Page ${mark.page_number}${selected ? " · selected on preview" : ""}</small></button><button class="redact-mark-remove" aria-label="Remove ${escapeHtml(mark.search_text || `mark ${index + 1}`)}" title="Remove this redaction" type="button">×</button></div>`;
    }).join("");
    list.querySelectorAll(".redact-mark-item").forEach((item) => {
      const mark = state.marks.find((candidate) => candidate.mark_id === item.dataset.markId);
      item.querySelector(".redact-mark-focus").addEventListener("click", () => selectMark(mark, { navigate: true, scrollList: false }));
      item.querySelector(".redact-mark-remove").addEventListener("click", () => {
        commitMarks(state.marks.filter((candidate) => candidate !== mark));
      });
    });
    updateHistoryControls();
  }

  function refreshCanvasMarks() {
    canvas.setMarks(marksForPage(state.activePage));
    canvas.setSelectedMark(state.selectedMarkId);
    document.querySelectorAll("#redactThumbnails .redact-thumbnail").forEach((button) => {
      const pageNumber = Number(button.dataset.page);
      const count = marksForPage(pageNumber).length;
      button.classList.toggle("has-marks", count > 0);
      button.querySelector(".redact-thumbnail-mark-count").textContent = count ? String(count) : "";
    });
  }

  function commitMarks(next, { preserveRedo = false, selectedMarkId = state.selectedMarkId } = {}) {
    state.undo.push(state.marks.map((mark) => ({ ...mark, rect: { ...mark.rect } })));
    if (!preserveRedo) state.redo = [];
    state.marks = next.map(withAppearance);
    state.selectedMarkId = state.marks.some((mark) => mark.mark_id === selectedMarkId)
      ? selectedMarkId
      : null;
    renderMarkList();
    refreshCanvasMarks();
    executionOrder();
  }

  function resetMarks() {
    state.marks = [];
    state.selectedMarkId = null;
    state.undo = [];
    state.redo = [];
    renderMarkList();
    refreshCanvasMarks();
  }

  async function thumbnailPreviewFor(pageNumber) {
    if (state.previews.has(pageNumber)) return state.previews.get(pageNumber);
    const data = await previewPdf(state.previewFile, [pageNumber], { maxWidth: 320 });
    const preview = data.previews?.[0];
    if (!preview) throw new Error(`Could not render page ${pageNumber}.`);
    state.previews.set(pageNumber, preview);
    document.querySelectorAll(`#redactThumbnails [data-page="${pageNumber}"] img`).forEach((image) => {
      image.src = preview.image;
    });
    return preview;
  }

  function targetCanvasWidth() {
    const stageWidth = Math.max(700, $("#redactCanvasStage").clientWidth - 48);
    const pixelRatio = Math.max(1, window.devicePixelRatio || 1);
    return Math.min(3200, Math.max(1800, Math.ceil(stageWidth * pixelRatio * state.zoom / 100)));
  }

  async function canvasPreviewFor(pageNumber) {
    const targetWidth = targetCanvasWidth();
    const cached = state.canvasPreviews.get(pageNumber);
    if (cached && cached.width >= targetWidth) return cached.preview;
    const data = await previewPdf(state.previewFile, [pageNumber], { maxWidth: targetWidth });
    const preview = data.previews?.[0];
    if (!preview) throw new Error(`Could not render page ${pageNumber}.`);
    state.canvasPreviews.set(pageNumber, { width: targetWidth, preview });
    return preview;
  }

  async function showPage(pageNumber) {
    if (!state.currentSource || pageNumber < 1 || pageNumber > state.currentSource.page_count) return;
    state.activePage = pageNumber;
    document.querySelectorAll("#redactThumbnails .redact-thumbnail").forEach((button) => {
      button.classList.toggle("active", Number(button.dataset.page) === pageNumber);
    });
    $("#redactActivePageLabel").textContent = `Page ${pageNumber}`;
    try {
      const preview = await canvasPreviewFor(pageNumber);
      if (state.activePage !== pageNumber) return;
      canvas.showPage({
        pageId: state.currentSource.page_ids[pageNumber - 1],
        pageNumber,
        image: preview.image,
        marks: marksForPage(pageNumber),
      });
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  }

  function selectMark(mark, { navigate = true, scrollList = true } = {}) {
    if (!mark) return;
    state.selectedMarkId = mark.mark_id;
    renderMarkList();
    refreshCanvasMarks();
    if (navigate && state.activePage !== Number(mark.page_number)) showPage(Number(mark.page_number));
    window.setTimeout(() => {
      if (scrollList) {
        const item = [...document.querySelectorAll("#redactMarkList .redact-mark-item")]
          .find((candidate) => candidate.dataset.markId === mark.mark_id);
        item?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } else {
        $("#redactCanvasStage").scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }, 0);
  }

  function bindThumbnailObserver() {
    state.thumbnailObserver?.disconnect();
    state.thumbnailObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const image = entry.target;
        const pageNumber = Number(image.closest(".redact-thumbnail")?.dataset.page);
        if (pageNumber) thumbnailPreviewFor(pageNumber).catch(() => {});
        state.thumbnailObserver.unobserve(image);
      });
    }, { root: $("#redactThumbnails"), rootMargin: "100px" });
    document.querySelectorAll("#redactThumbnails .redact-thumbnail img").forEach((image) => {
      state.thumbnailObserver.observe(image);
    });
  }

  function renderThumbnails() {
    const container = $("#redactThumbnails");
    const pageCount = state.currentSource?.page_count || 0;
    $("#redactThumbCount").textContent = pageCount ? String(pageCount) : "";
    container.innerHTML = "";
    for (let page = 1; page <= pageCount; page += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `redact-thumbnail${page === state.activePage ? " active" : ""}`;
      button.dataset.page = String(page);
      button.innerHTML = `<span class="redact-thumbnail-image"><img alt="Page ${page}"/><i class="redact-thumbnail-mark-count"></i></span><span>Page ${page}</span>`;
      button.addEventListener("click", () => showPage(page));
      container.append(button);
    }
    refreshCanvasMarks();
    bindThumbnailObserver();
  }

  function renderSourceLegend() {
    const legend = $("#redactSourceLegend");
    const visible = state.sourceEntries.length > 1;
    legend.classList.toggle("hidden", !visible);
    if (!visible) {
      legend.innerHTML = "";
      return;
    }
    legend.innerHTML = `<strong>Source colors</strong>${state.sourceEntries.map((entry) => `<span class="workflow-source-legend-item" title="${escapeHtml(entry.file.name)}"><i style="--source-color:${sourceColor(entry.file)}"></i>${escapeHtml(entry.file.name)}</span>`).join("")}`;
  }

  function renderSourceList(files = getFiles("redactFile")) {
    const container = $("#redactSourceList");
    $("#redactSourceManager").classList.toggle("hidden", !files.length);
    container.innerHTML = "";
    const artifactByFile = new Map(state.sourceEntries.map((entry) => [entry.file, entry.artifact]));
    files.forEach((file, index) => {
      const artifact = artifactByFile.get(file);
      const item = document.createElement("div");
      item.className = "sortable-item workflow-source-item";
      item.dataset.reorderKey = stableFileId(file);
      item.style.setProperty("--source-color", sourceColor(file));
      const pages = artifact?.page_count ? `${artifact.page_count} page${artifact.page_count === 1 ? "" : "s"} · ` : "";
      item.innerHTML = `<span class="drag-handle" title="Drag to change PDF order">☷</span><div class="file-thumb workflow-source-thumb"><img alt="Preview"/><span>PDF</span></div><span class="workflow-source-copy"><button class="item-name file-name-preview" title="Preview ${escapeHtml(file.name)}" type="button">${escapeHtml(file.name)}</button><span class="item-size">${pages}${formatBytes(Number(file.workflowBytes ?? file.size))}</span></span><span class="workflow-source-position">${index + 1}</span><button class="remove-file" type="button">Remove</button>`;
      populateThumb(item.querySelector("img"), file);
      item.querySelector(".file-name-preview")?.addEventListener("click", (event) => {
        event.stopPropagation();
        openPdfPreview(file);
      });
      item.querySelector(".remove-file").addEventListener("click", (event) => {
        event.stopPropagation();
        replaceFiles("redactFile", getFiles("redactFile").filter((candidate) => candidate !== file));
      });
      container.append(item);
    });
    const byId = new Map(files.map((file) => [stableFileId(file), file]));
    bindAnimatedReorder({
      container,
      itemSelector: ".workflow-source-item",
      onCommit: (order) => replaceFiles("redactFile", order.map((id) => byId.get(id)).filter(Boolean)),
    });
  }

  function showWorkflow(visible) {
    for (const id of ["redactWorkflowNote", "redactPagePrep", "redactEditor", "redactWorkflowBuilder", "redactRunRow"]) {
      $(`#${id}`).classList.toggle("hidden", !visible);
    }
  }

  function lockEditor(locked) {
    $("#redactEditor").classList.toggle("redact-editor-complete", locked);
    document.querySelectorAll("#redactEditor button, #redactEditor input, #redactEditor select").forEach((control) => {
      control.disabled = Boolean(locked);
    });
    if (!locked) updateHistoryControls();
  }

  function clearEditor() {
    state.currentSource = null;
    state.previewFile = null;
    state.result = null;
    state.comparisonArtifact = null;
    state.previews.clear();
    state.canvasPreviews.clear();
    state.thumbnailObserver?.disconnect();
    pageWorkspace.clear();
    resetMarks();
    $("#redactThumbnails").innerHTML = "";
    $("#redactWorkflowResult").classList.add("hidden");
    lockEditor(false);
    showWorkflow(false);
  }

  function setPageDirty(dirty) {
    state.pageDirty = Boolean(dirty);
    $("#redactPrepWarning").classList.toggle("hidden", !dirty);
    $("#confirmRedactPages").disabled = !dirty;
    $("#redactEditor").classList.toggle("redact-editor-stale", dirty);
    $("#redactApplyBtn").disabled = dirty || Boolean(state.result);
  }

  async function loadSource(artifact, { clearExistingMarks = true } = {}) {
    state.currentSource = artifact;
    state.previewFile = temporaryFile(state.workflowId, artifact);
    state.previews.clear();
    state.canvasPreviews.clear();
    state.activePage = 1;
    state.result = null;
    $("#redactWorkflowResult").classList.add("hidden");
    lockEditor(false);
    if (clearExistingMarks) resetMarks();
    const sourceColors = new Map(state.sourceEntries.map((entry) => [entry.artifact.artifact_id, sourceColor(entry.file)]));
    const pageSources = (artifact.page_sources || []).map((source) => ({
      ...source,
      color: sourceColors.get(source.source_artifact_id) || null,
    }));
    await pageWorkspace.load(state.previewFile, { pageIds: artifact.page_ids, pageSources });
    $("#redactPageCount").textContent = `${artifact.page_count} output pages`;
    setPageDirty(false);
    showWorkflow(true);
    renderSourceLegend();
    renderThumbnails();
    await showPage(1);
  }

  async function deleteWorkflow(workflowId) {
    if (!workflowId) return;
    try {
      await apiFetch(`/api/workflows/${encodeURIComponent(workflowId)}`, { method: "DELETE" });
    } catch {
      // TTL cleanup remains the fallback.
    }
  }

  async function syncSources(files) {
    const generation = ++state.generation;
    const previousByFile = new Map(state.sourceEntries.map((entry) => [entry.file, entry]));
    const desiredEntries = files.map((file) => {
      if (previousByFile.has(file)) return previousByFile.get(file);
      const reference = workflowReferenceForFile(file, "redactFile");
      return { file, artifact: reference ? artifactFromReference(reference) : null, reference };
    });
    clearEditor();
    renderSourceList(files);
    if (!files.length) {
      const workflowId = state.workflowId;
      state.workflowId = null;
      state.sourceEntries = [];
      await deleteWorkflow(workflowId);
      setStatus(status, "Add one or more PDFs to start redacting.");
      return;
    }

    const referenced = desiredEntries.find((entry) => entry.reference);
    const knownEntries = desiredEntries.filter((entry) => entry.artifact);
    const canReuseWorkflow = Boolean(
      (state.workflowId && knownEntries.length)
      || (referenced && desiredEntries.every((entry) => !entry.reference || entry.reference.workflowId === referenced.reference.workflowId)),
    );
    const previousWorkflowId = state.workflowId;
    let endpoint;
    const form = new FormData();
    if (canReuseWorkflow) {
      state.workflowId = state.workflowId || referenced.reference.workflowId;
      endpoint = `/api/workflows/${encodeURIComponent(state.workflowId)}/redact/sources`;
      form.append("kept_artifact_ids_json", JSON.stringify(knownEntries.map((entry) => entry.artifact.artifact_id)));
      desiredEntries.filter((entry) => !entry.artifact).forEach((entry) => form.append("files", entry.file));
    } else {
      state.workflowId = null;
      await deleteWorkflow(previousWorkflowId);
      if (generation !== state.generation) return;
      endpoint = "/api/workflows/redact/start";
      desiredEntries.forEach((entry) => form.append("files", entry.file));
    }

    setStatus(status, files.length > 1 ? "Preparing PDF arrangement and merging locally…" : "Preparing secure redaction workspace…");
    const response = await apiFetch(endpoint, {
      method: "POST",
      body: form,
      progressElement: status,
      progressLabel: files.length > 1 ? "Merging PDFs for redaction…" : "Preparing Redact PDF…",
    });
    const data = await jsonResponse(response);
    if (generation !== state.generation) {
      if (!canReuseWorkflow) await deleteWorkflow(data.workflow.workflow_id);
      return;
    }
    state.workflowId = data.workflow.workflow_id;
    state.sourceEntries = desiredEntries.map((entry, index) => ({ file: entry.file, artifact: data.source_artifacts[index] }));
    renderSourceList(files);
    await loadSource(data.artifact);
    const expiry = new Date(data.workflow.expires_at);
    $("#redactWorkflowExpiry").textContent = `Temporary files expire after inactivity (currently ${expiry.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}).`;
    setStatus(status, `${data.artifact.page_count} pages are ready for secure redaction.`, "success");
    executionOrder();
  }

  onFilesChanged("redactFile", async (files) => {
    if (state.suppressFileChange) return;
    try {
      await syncSources([...files]);
    } catch (error) {
      clearEditor();
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#clearRedactFiles").addEventListener("click", () => clearFiles("redactFile"));

  $("#confirmRedactPages").addEventListener("click", async () => {
    try {
      if (!state.workflowId || !state.currentSource || !state.pageDirty) return;
      const form = new FormData();
      form.append("artifact_id", state.currentSource.artifact_id);
      form.append("plan_json", JSON.stringify(pageWorkspace.getPlan()));
      setStatus(status, "Materializing the page arrangement before marking…");
      const response = await apiFetch(
        `/api/workflows/${encodeURIComponent(state.workflowId)}/redact/prepare`,
        { method: "POST", body: form, progressElement: status, progressLabel: "Preparing pages…" },
      );
      const data = await jsonResponse(response);
      await loadSource(data.artifact);
      $("#redactPagePrep").open = false;
      setStatus(status, "Page arrangement confirmed. Draw redaction marks on the prepared PDF.", "success");
      executionOrder();
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#resetRedactPages").addEventListener("click", async () => {
    if (!state.currentSource || !state.previewFile) return;
    try {
      await pageWorkspace.load(state.previewFile, {
        pageIds: state.currentSource.page_ids,
        pageSources: state.currentSource.page_sources,
      });
      setPageDirty(false);
      setStatus(status, "Staged page changes were reset.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  document.querySelectorAll("[data-redact-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-redact-tool]").forEach((candidate) => candidate.classList.toggle("active", candidate === button));
      const tool = button.dataset.redactTool;
      canvas.setTool(tool);
      $("#redactCanvasStage").classList.toggle("pan-mode", tool === "pan");
      $("#redactTextPanel").classList.toggle("active", tool === "text");
      $("#redactPageInstruction").textContent = tool === "text"
        ? "Drag across text to mark the underlying PDF characters for redaction."
        : tool === "pan"
          ? "Pan and inspect the page without creating marks."
          : "Drag a box over every area that must be permanently removed.";
      if (tool === "text") $("#redactSearchText").focus();
    });
  });
  canvas.setTool("redact");

  async function selectTextByDrag(selection) {
    try {
      if (!state.workflowId || !state.currentSource) throw new Error("Upload a PDF first.");
      if (state.pageDirty) throw new Error("Confirm or reset the staged page arrangement first.");
      const form = new FormData();
      form.append("artifact_id", state.currentSource.artifact_id);
      form.append("page_number", String(selection.page_number));
      form.append("page_instance_id", selection.page_instance_id);
      form.append("rect_json", JSON.stringify(selection.rect));
      setStatus(status, `Resolving selected text on page ${selection.page_number}…`);
      const response = await apiFetch(
        `/api/workflows/${encodeURIComponent(state.workflowId)}/redact/select-text`,
        { method: "POST", body: form },
      );
      const data = await jsonResponse(response);
      if (!data.matches.length) {
        setStatus(status, "No selectable text was found in that area. Scanned PDFs may need OCR first.", "warning");
        return;
      }
      const existing = new Set(state.marks.map((mark) => `${mark.page_instance_id}:${mark.rect.x0.toFixed(5)}:${mark.rect.y0.toFixed(5)}:${mark.rect.x1.toFixed(5)}:${mark.rect.y1.toFixed(5)}`));
      const additions = data.matches.filter((mark) => {
        const key = `${mark.page_instance_id}:${mark.rect.x0.toFixed(5)}:${mark.rect.y0.toFixed(5)}:${mark.rect.x1.toFixed(5)}:${mark.rect.y1.toFixed(5)}`;
        return !existing.has(key);
      });
      if (additions.length) {
        commitMarks([...state.marks, ...additions], { selectedMarkId: additions[0].mark_id });
        selectMark(additions[0], { navigate: false, scrollList: true });
      }
      setStatus(status, `${data.match_count} dragged text selection${data.match_count === 1 ? "" : "s"} marked for redaction.`, "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  }

  $("#previewRedactPages").addEventListener("click", () => {
    if (state.previewFile) openPdfPreview(state.previewFile, { title: "Redact PDF page arrangement" });
  });

  $("#redactUndo").addEventListener("click", () => {
    if (!state.undo.length) return;
    state.redo.push(state.marks);
    state.marks = state.undo.pop();
    if (!state.marks.some((mark) => mark.mark_id === state.selectedMarkId)) state.selectedMarkId = null;
    renderMarkList();
    refreshCanvasMarks();
  });
  $("#redactRedo").addEventListener("click", () => {
    if (!state.redo.length) return;
    state.undo.push(state.marks);
    state.marks = state.redo.pop();
    if (!state.marks.some((mark) => mark.mark_id === state.selectedMarkId)) state.selectedMarkId = null;
    renderMarkList();
    refreshCanvasMarks();
  });
  $("#redactClearMarks").addEventListener("click", () => {
    if (state.marks.length) commitMarks([]);
  });

  function setZoom(next) {
    state.zoom = Math.max(60, Math.min(180, next));
    $("#redactPaper").style.width = `${state.zoom}%`;
    $("#redactZoomLabel").textContent = `${state.zoom}%`;
    if (state.currentSource) showPage(state.activePage);
  }
  $("#redactZoomOut").addEventListener("click", () => setZoom(state.zoom - 10));
  $("#redactZoomIn").addEventListener("click", () => setZoom(state.zoom + 10));
  setZoom(100);

  $("#redactAppearance").addEventListener("change", () => {
    $("#redactColorField").classList.toggle("hidden", selectedAppearance() !== "black");
    state.marks = state.marks.map(withAppearance);
    renderMarkList();
  });
  $("#redactColor").addEventListener("input", () => {
    state.marks = state.marks.map(withAppearance);
  });

  $("#redactSearchBtn").addEventListener("click", async () => {
    try {
      if (!state.workflowId || !state.currentSource) throw new Error("Upload a PDF first.");
      if (state.pageDirty) throw new Error("Confirm or reset the staged page arrangement first.");
      const query = $("#redactSearchText").value.trim();
      if (!query) throw new Error("Enter text to find and redact.");
      const form = new FormData();
      form.append("artifact_id", state.currentSource.artifact_id);
      form.append("query", query);
      form.append("exact", $("#redactSearchExact").checked ? "true" : "false");
      setStatus(status, `Searching all pages for “${query}”…`);
      const response = await apiFetch(
        `/api/workflows/${encodeURIComponent(state.workflowId)}/redact/search`,
        { method: "POST", body: form },
      );
      const data = await jsonResponse(response);
      if (!data.matches.length) {
        setStatus(status, "No matches found in the current text layer. Scanned PDFs may need OCR first.", "warning");
        return;
      }
      const existing = new Set(state.marks.map((mark) => `${mark.page_instance_id}:${mark.rect.x0.toFixed(5)}:${mark.rect.y0.toFixed(5)}:${mark.rect.x1.toFixed(5)}:${mark.rect.y1.toFixed(5)}`));
      const additions = data.matches.filter((mark) => {
        const key = `${mark.page_instance_id}:${mark.rect.x0.toFixed(5)}:${mark.rect.y0.toFixed(5)}:${mark.rect.x1.toFixed(5)}:${mark.rect.y1.toFixed(5)}`;
        return !existing.has(key);
      });
      if (additions.length) commitMarks([...state.marks, ...additions], { selectedMarkId: additions[0].mark_id });
      selectMark(additions[0] || data.matches[0], { navigate: true, scrollList: true });
      const matchMode = data.exact ? " exact" : "";
      setStatus(status, `${data.match_count}${matchMode} text match${data.match_count === 1 ? "" : "es"} marked for redaction.`, "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });
  $("#redactSearchText").addEventListener("keydown", (event) => {
    if (event.key === "Enter") $("#redactSearchBtn").click();
  });

  function toggleAddon(addon, checkboxId, bodyId) {
    const checkbox = $(`#${checkboxId}`);
    const body = $(`#${bodyId}`);
    const toggle = body?.closest(".workflow-addon")?.querySelector(".workflow-addon-toggle");
    const render = () => {
      const visible = checkbox.checked && state.addonExpanded[addon];
      body.classList.toggle("hidden", !visible);
      toggle?.setAttribute("aria-expanded", visible ? "true" : "false");
    };
    checkbox.addEventListener("change", () => {
      if (checkbox.checked && !state.addonExpanded[addon]) state.addonExpanded[addon] = true;
      render();
      executionOrder();
    });
    toggle?.addEventListener("click", (event) => {
      if (event.target.closest?.("input")) return;
      event.preventDefault();
      state.addonExpanded[addon] = !state.addonExpanded[addon];
      render();
    });
    toggle?.addEventListener("keydown", (event) => {
      if (event.target !== toggle || !["Enter", " "].includes(event.key)) return;
      event.preventDefault();
      state.addonExpanded[addon] = !state.addonExpanded[addon];
      render();
    });
    render();
  }

  function selectedCompressionMode() {
    return $("input[name='redactCompressionMode']:checked")?.value || "recommended";
  }

  function renderCompressionProfiles() {
    document.querySelectorAll("#redactCompressionProfiles .profile").forEach((profile) => {
      profile.classList.toggle("selected", Boolean(profile.querySelector("input[type='radio']:checked")));
    });
  }

  function executionOrder() {
    const steps = getFiles("redactFile").length > 1 ? ["Merge"] : [];
    if (state.currentSource?.source_operation === "prepare-pages") steps.push("Prepare pages");
    if ($("#redactOcrEnabled").checked) steps.push("OCR");
    steps.push("Redact");
    if ($("#redactCompressEnabled").checked) steps.push("Compress");
    if ($("#redactProtectEnabled").checked) steps.push("Protect");
    if ($("#redactHashEnabled").checked) steps.push("SHA-256");
    $("#redactExecutionOrder").querySelector("span").textContent = steps.join(" → ");
  }

  toggleAddon("ocr", "redactOcrEnabled", "redactOcrBody");
  toggleAddon("compress", "redactCompressEnabled", "redactCompressBody");
  toggleAddon("protect", "redactProtectEnabled", "redactProtectBody");
  $("#redactHashEnabled").addEventListener("change", executionOrder);
  document.querySelectorAll("input[name='redactCompressionMode']").forEach((radio) => radio.addEventListener("change", renderCompressionProfiles));
  for (const id of ["redactTargetMinMb", "redactTargetMaxMb"]) {
    $(`#${id}`).addEventListener("focus", () => {
      $("input[name='redactCompressionMode'][value='custom']").checked = true;
      renderCompressionProfiles();
    });
  }

  function renderResult(data) {
    state.result = data.artifact;
    state.comparisonArtifact = data.comparison_artifact;
    $("#redactResultMeta").textContent = `${data.artifact.file_name} • ${data.artifact.page_count} pages • ${formatBytes(data.artifact.bytes)}`;
    $("#redactVerification").innerHTML = `<strong>Content-layer verification passed</strong><span>${data.redaction.marks_applied} marks across ${data.redaction.pages_redacted} pages; ${data.redaction.text_regions_clear}/${data.redaction.marks_applied} marked regions contain no extractable text.</span>`;
    const hash = $("#redactResultHash");
    hash.classList.toggle("hidden", !data.sha256);
    hash.textContent = data.sha256 ? `SHA-256  ${data.sha256}` : "";
    const allowed = new Set(data.transfer_destinations || []);
    document.querySelectorAll("#redactContinueGrid [data-destination]").forEach((button) => {
      button.classList.toggle("hidden", !allowed.has(button.dataset.destination));
    });
    const canContinue = allowed.size > 0;
    $("#redactContinueHeading").classList.toggle("hidden", !canContinue);
    $("#redactContinueGrid").classList.toggle("hidden", !canContinue);
    $("#redactProtectedTerminal").classList.toggle("hidden", canContinue);
    $("#redactWorkflowResult").classList.remove("hidden");
    $("#redactApplyBtn").disabled = true;
    lockEditor(true);
    $("#redactWorkflowResult").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  $("#redactApplyBtn").addEventListener("click", async () => {
    try {
      if (!state.workflowId || !state.currentSource) throw new Error("Choose or drop a PDF first.");
      if (state.pageDirty) throw new Error("Confirm or reset the staged page arrangement first.");
      if (!state.marks.length) throw new Error("Draw or search for at least one redaction mark.");
      const password = $("#redactProtectPassword").value;
      if ($("#redactProtectEnabled").checked) {
        if (!password) throw new Error("Enter a password for the protected PDF.");
        if (password !== $("#redactProtectConfirm").value) throw new Error("The protection passwords do not match.");
      }
      const form = new FormData();
      form.append("artifact_id", state.currentSource.artifact_id);
      form.append("redactions_json", JSON.stringify(state.marks));
      form.append("appearance", selectedAppearance());
      form.append("color", $("#redactColor").value || "#000000");
      form.append("ocr_enabled", $("#redactOcrEnabled").checked ? "true" : "false");
      form.append("ocr_language", $("#redactOcrLanguage").value || "eng");
      form.append("ocr_dpi", $("#redactOcrDpi").value || "200");
      if ($("#redactCompressEnabled").checked) {
        const mode = selectedCompressionMode();
        form.append("compress_mode", mode);
        if (mode === "custom") {
          form.append("target_min_mb", $("#redactTargetMinMb").value);
          form.append("target_max_mb", $("#redactTargetMaxMb").value);
        }
      }
      if ($("#redactProtectEnabled").checked) form.append("protect_password", password);
      form.append("generate_sha256", $("#redactHashEnabled").checked ? "true" : "false");
      setStatus(status, `Running ${$("#redactExecutionOrder").querySelector("span").textContent}…`);
      const response = await apiFetch(
        `/api/workflows/${encodeURIComponent(state.workflowId)}/redact/execute`,
        { method: "POST", body: form, progressElement: status, progressLabel: "Securely removing marked PDF content…" },
      );
      const data = await jsonResponse(response);
      renderResult(data);
      if (data.failures?.length) {
        const failed = data.failures.map((failure) => `${failure.step}: ${failure.message}`).join("\n");
        setStatus(status, `Redaction complete and preserved. Optional step failed:\n${failed}`, "warning");
      } else {
        setStatus(status, `Done. ${data.execution_order.join(" → ")} completed and redaction was verified.`, "success");
      }
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#redactDownload").addEventListener("click", async () => {
    if (!state.result) return;
    try {
      const response = await apiFetch(state.result.download_url);
      await downloadResponse(response, state.result.file_name || "redacted.pdf");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#redactFinish").addEventListener("click", async () => {
    const workflowId = state.workflowId;
    state.workflowId = null;
    await deleteWorkflow(workflowId);
    state.sourceEntries = [];
    state.suppressFileChange = true;
    clearFiles("redactFile");
    state.suppressFileChange = false;
    clearEditor();
    renderSourceList([]);
    setStatus(status, "Workflow finished. Temporary files were cleared; downloaded files are unchanged.", "success");
  });

  document.querySelectorAll("#redactContinueGrid [data-destination]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!state.workflowId || !state.result || button.disabled) return;
      const destination = button.dataset.destination;
      try {
        const form = new FormData();
        form.append("artifact_id", state.result.artifact_id);
        form.append("destination", destination);
        form.append("source_feature", "redact");
        if (destination === "compare-pdf") {
          if (!state.comparisonArtifact) throw new Error("The original comparison artifact is unavailable.");
          form.append("comparison_artifact_id", state.comparisonArtifact.artifact_id);
        }
        const response = await apiFetch(
          `/api/workflows/${encodeURIComponent(state.workflowId)}/transfer`,
          { method: "POST", body: form },
        );
        await jsonResponse(response);
        stageWorkflowTransfer(referenceFor(
          state.workflowId,
          state.result,
          destination,
          state.comparisonArtifact?.artifact_id || null,
        ));
        const navigation = document.querySelector(`.nav-tool[data-tool="${destination}"]`);
        if (!navigation) throw new Error("The destination tool is unavailable in this build.");
        navigation.click();
      } catch (error) {
        setStatus(status, error.message || String(error), "error");
      }
    });
  });

  try {
    const response = await apiFetch("/api/health");
    if (response.ok) {
      const health = await response.json();
      if (!health.ghostscript) {
        $("#redactCompressEnabled").disabled = true;
        $("#redactCompressCapability").textContent = "Ghostscript is unavailable, so integrated compression is disabled.";
      }
      if (!health.tesseract) {
        $("#redactOcrEnabled").disabled = true;
        $("#redactOcrEnabled").closest("label").querySelector("small").textContent = "Tesseract is unavailable on this computer.";
      }
    }
  } catch {
    // Backend validation remains authoritative.
  }

  renderCompressionProfiles();
  renderSourceList([]);
  renderMarkList();
  showWorkflow(false);
  executionOrder();
}
