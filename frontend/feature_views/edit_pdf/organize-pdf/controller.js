import { apiFetch, downloadResponse, parseError } from "/frontend/assets/js/core/api.js";
import { $, escapeHtml, formatBytes, setStatus } from "/frontend/assets/js/core/dom.js";
import { clearFiles, getFiles, onFilesChanged, replaceFiles } from "/frontend/assets/js/core/file_store.js";
import { populateThumb } from "/frontend/assets/js/core/previews.js?v=7.5";
import { openPdfPreview } from "/frontend/assets/js/core/pdf_preview_modal.js?v=7.5";
import { bindAnimatedReorder } from "/frontend/assets/js/core/drag_reorder.js";
import { PageWorkspace, parsePageOrderExpression } from "/frontend/assets/js/core/page_workspace.js?v=7.5";
import { bindWorkflowInput, stageWorkflowTransfer } from "/frontend/assets/js/core/workflow_transfer.js";

const SOURCE_COLORS = [
  "#df3b35", "#2878b8", "#2d936c", "#9b51b5", "#df7f19", "#197f89",
  "#c43870", "#6775c9", "#6f8b25", "#a85a35", "#0086c9", "#7c5ab8",
  "#c55d08", "#238b45", "#b23a48", "#4c78a8", "#8f6b00", "#5e7d87",
];

function referenceFor(workflowId, artifact, destination = null) {
  return {
    workflowId,
    artifactId: artifact.artifact_id,
    fileName: artifact.file_name,
    mediaType: artifact.media_type,
    bytes: artifact.bytes,
    destination,
    sourceFeature: "organize",
  };
}

function temporaryFile(reference) {
  const file = new File([], reference.fileName, {
    type: reference.mediaType || "application/pdf",
    lastModified: Date.now(),
  });
  Object.defineProperty(file, "workflowBytes", { value: Number(reference.bytes || 0) });
  bindWorkflowInput("organizeFile", file, reference);
  return file;
}

async function jsonResponse(response) {
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function init() {
  const status = $("#organizeStatus");
  const fileIds = new WeakMap();
  const fileColors = new WeakMap();
  let nextFileId = 0;
  let nextColor = 0;
  const state = {
    workflowId: null,
    currentSource: null,
    sourceEntries: [],
    result: null,
    dirty: false,
    generation: 0,
    suppressFileChange: false,
    addonExpanded: { compress: false, protect: false },
  };

  function stableFileId(file) {
    if (!fileIds.has(file)) fileIds.set(file, `organize-file-${++nextFileId}`);
    return fileIds.get(file);
  }

  function sourceColor(file) {
    if (!fileColors.has(file)) {
      const paletteColor = SOURCE_COLORS[nextColor];
      const generatedColor = `hsl(${Math.round((nextColor * 137.508 + 7) % 360)} 62% 43%)`;
      fileColors.set(file, paletteColor || generatedColor);
      nextColor += 1;
    }
    return fileColors.get(file);
  }

  const workspace = new PageWorkspace({
    inputId: "organizeFile",
    container: "#organizePageWorkspace",
    reorderable: true,
    organizeActions: true,
    onChange: (items) => {
      state.dirty = true;
      $("#organizePageCount").textContent = `${items.length} output pages`;
    },
  });

  function toggleBody(addon, checkboxId, bodyId) {
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
    return $("input[name='organizeCompressionMode']:checked")?.value || "recommended";
  }

  function renderCompressionProfiles() {
    document.querySelectorAll("#organizeCompressionProfiles .profile").forEach((profile) => {
      profile.classList.toggle("selected", Boolean(profile.querySelector("input[type='radio']:checked")));
    });
  }

  function confirmAddonDiscard(checkboxId, hasEdits, clearEdits, message) {
    $(`#${checkboxId}`).addEventListener("change", (event) => {
      if (event.target.checked || !hasEdits()) return;
      if (!window.confirm(message)) {
        event.target.checked = true;
        event.stopImmediatePropagation();
        return;
      }
      clearEdits();
    });
  }

  function executionOrder() {
    const hasMerge = getFiles("organizeFile").length > 1;
    const order = hasMerge ? ["Merge", "Organize"] : ["Organize"];
    // These badges are the order of the optional actions themselves. Keep them
    // at 1–2–3 even when the base workflow also includes merge or organize.
    $("#organizeCompressOrderIndex").textContent = "1";
    $("#organizeProtectOrderIndex").textContent = "2";
    $("#organizeHashOrderIndex").textContent = "3";
    if ($("#organizeCompressEnabled").checked) order.push("Compress");
    if ($("#organizeProtectEnabled").checked) order.push("Protect");
    if ($("#organizeHashEnabled").checked) order.push("SHA-256");
    $("#organizeExecutionOrder").querySelector("span").textContent = order.join(" → ");
  }

  async function deleteWorkflow(workflowId) {
    if (!workflowId) return;
    try {
      await apiFetch(`/api/workflows/${encodeURIComponent(workflowId)}`, { method: "DELETE" });
    } catch {
      // TTL cleanup remains the fallback if the local engine is closing.
    }
  }

  async function deleteCurrentWorkflow() {
    const workflowId = state.workflowId;
    state.workflowId = null;
    await deleteWorkflow(workflowId);
  }

  function showEditor(visible) {
    for (const id of ["organizeToolbar", "organizeWorkspaceWrap", "organizeWorkflowBuilder", "organizeWorkflowNote"]) {
      $(`#${id}`).classList.toggle("hidden", !visible);
    }
    $("#organizeBtn").disabled = !visible;
  }

  function clearArrangement() {
    workspace.clear();
    state.currentSource = null;
    state.result = null;
    state.dirty = false;
    $("#organizeWorkflowResult").classList.add("hidden");
    $("#organizeSourceLegend").classList.add("hidden");
    showEditor(false);
  }

  function renderSourceList(files = getFiles("organizeFile")) {
    const container = $("#organizeSourceList");
    $("#organizeSourceManager").classList.toggle("hidden", !files.length);
    container.innerHTML = "";
    const artifactByFile = new Map(state.sourceEntries.map((entry) => [entry.file, entry.artifact]));
    files.forEach((file, index) => {
      const artifact = artifactByFile.get(file);
      const item = document.createElement("div");
      item.className = "sortable-item workflow-source-item";
      item.dataset.reorderKey = stableFileId(file);
      item.style.setProperty("--source-color", sourceColor(file));
      const pageMeta = artifact ? `${artifact.page_count} page${artifact.page_count === 1 ? "" : "s"} · ` : "";
      item.innerHTML = `
        <span class="drag-handle" title="Drag to change merge order">☷</span>
        <div class="file-thumb workflow-source-thumb"><img alt="Preview"/><span>${escapeHtml(file.name.split(".").pop()?.toUpperCase() || "PDF")}</span></div>
        <span class="workflow-source-copy"><button class="item-name file-name-preview" title="Preview ${escapeHtml(file.name)}" type="button">${escapeHtml(file.name)}</button><span class="item-size">${pageMeta}${formatBytes(file.size)}</span></span>
        <span class="workflow-source-position">${index + 1}</span>
        <button class="remove-file" type="button">Remove</button>`;
      populateThumb(item.querySelector(".file-thumb img"), file);
      item.querySelector(".file-name-preview")?.addEventListener("click", (event) => {
        event.stopPropagation();
        openPdfPreview(file);
      });
      item.querySelector(".remove-file").addEventListener("click", (event) => {
        event.stopPropagation();
        replaceFiles("organizeFile", getFiles("organizeFile").filter((candidate) => candidate !== file));
      });
      container.appendChild(item);
    });
    const byId = new Map(files.map((file) => [stableFileId(file), file]));
    bindAnimatedReorder({
      container,
      itemSelector: ".workflow-source-item",
      onCommit: (order) => replaceFiles("organizeFile", order.map((id) => byId.get(id)).filter(Boolean)),
    });
  }

  function renderSourceLegend() {
    const legend = $("#organizeSourceLegend");
    const visible = state.sourceEntries.length > 1;
    legend.classList.toggle("hidden", !visible);
    if (!visible) {
      legend.innerHTML = "";
      return;
    }
    legend.innerHTML = `<strong>Source colors</strong>${state.sourceEntries.map((entry) => `
      <span class="workflow-source-legend-item" title="${escapeHtml(entry.file.name)}">
        <i style="--source-color:${sourceColor(entry.file)}"></i>${escapeHtml(entry.file.name)}
      </span>`).join("")}`;
  }

  async function loadSource(file, artifact, { animate = false } = {}) {
    const sourceColors = new Map(state.sourceEntries.map((entry) => [entry.artifact.artifact_id, sourceColor(entry.file)]));
    const pageSources = (artifact.page_sources || []).map((source) => ({
      ...source,
      color: sourceColors.get(source.source_artifact_id) || null,
    }));
    const info = await workspace.load(file, {
      pageIds: artifact.page_ids || [],
      pageSources,
      animate,
    });
    $("#organizeOrder").value = `1-${info.pages}`;
    $("#organizePageCount").textContent = `${info.pages} output pages`;
    state.currentSource = artifact;
    state.dirty = false;
    showEditor(true);
    renderSourceLegend();
  }

  function sourcesNeedFreshWorkflow(entries) {
    let sawNew = false;
    for (const entry of entries) {
      if (!entry.artifact) sawNew = true;
      else if (sawNew) return true;
    }
    return !state.workflowId || !entries.some((entry) => entry.artifact);
  }

  function isPureSourceReorder(files) {
    const previous = state.sourceEntries;
    if (files.length < 2 || files.length !== previous.length || !previous.every((entry) => entry.artifact)) return false;
    const previousFiles = previous.map((entry) => entry.file);
    return files.every((file) => previousFiles.includes(file))
      && files.some((file, index) => file !== previousFiles[index]);
  }

  async function syncSources(files) {
    const generation = ++state.generation;
    const reorderOnly = isPureSourceReorder(files);
    if (!reorderOnly) clearArrangement();
    else {
      state.result = null;
      $("#organizeWorkflowResult").classList.add("hidden");
    }
    renderSourceList(files);
    executionOrder();
    if (!files.length) {
      state.sourceEntries = [];
      await deleteCurrentWorkflow();
      setStatus(status, "Add one or more PDFs to start organizing.");
      return;
    }

    const previousByFile = new Map(state.sourceEntries.map((entry) => [entry.file, entry]));
    const desiredEntries = files.map((file) => previousByFile.get(file) || { file, artifact: null });
    const freshWorkflow = sourcesNeedFreshWorkflow(desiredEntries);
    const previousWorkflowId = state.workflowId;
    if (freshWorkflow) {
      state.workflowId = null;
      await deleteWorkflow(previousWorkflowId);
      if (generation !== state.generation) return;
    }

    const form = new FormData();
    let endpoint = "/api/workflows/organize/start";
    if (freshWorkflow) {
      desiredEntries.forEach((entry) => form.append("files", entry.file));
    } else {
      endpoint = `/api/workflows/${encodeURIComponent(state.workflowId)}/organize/sources`;
      form.append("kept_artifact_ids_json", JSON.stringify(
        desiredEntries.filter((entry) => entry.artifact).map((entry) => entry.artifact.artifact_id),
      ));
      desiredEntries.filter((entry) => !entry.artifact).forEach((entry) => form.append("files", entry.file));
    }

    setStatus(status, files.length > 1 ? "Preparing the merged page arrangement…" : "Preparing the page arrangement…");
    const response = await apiFetch(endpoint, {
      method: "POST",
      body: form,
      progressElement: status,
      progressLabel: files.length > 1 ? "Merging PDFs locally…" : "Preparing Organize PDF…",
    });
    const data = await jsonResponse(response);
    if (generation !== state.generation) {
      if (freshWorkflow) await deleteWorkflow(data.workflow.workflow_id);
      return;
    }

    state.workflowId = data.workflow.workflow_id;
    state.sourceEntries = desiredEntries.map((entry, index) => ({
      file: entry.file,
      artifact: data.source_artifacts[index],
    }));
    renderSourceList(files);
    const sourceFile = files.length === 1
      ? files[0]
      : temporaryFile(referenceFor(state.workflowId, data.artifact));
    await loadSource(sourceFile, data.artifact, { animate: reorderOnly });
    const expiry = new Date(data.workflow.expires_at);
    $("#organizeWorkflowExpiry").textContent = `Temporary files expire after inactivity (currently ${expiry.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}).`;
    const message = files.length > 1
      ? `${files.length} PDFs merged into ${data.artifact.page_count} pages. Arrangement is ready.`
      : `${data.artifact.page_count} pages are ready to arrange.`;
    setStatus(status, message, "success");
  }

  onFilesChanged("organizeFile", async (files) => {
    if (state.suppressFileChange) return;
    try {
      await syncSources([...files]);
    } catch (error) {
      clearArrangement();
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#clearOrganizeFiles").addEventListener("click", () => clearFiles("organizeFile"));

  document.querySelectorAll("input[name='organizeCompressionMode']").forEach((radio) => {
    radio.addEventListener("change", renderCompressionProfiles);
  });
  for (const id of ["organizeTargetMinMb", "organizeTargetMaxMb"]) {
    $(`#${id}`).addEventListener("focus", () => {
      $("input[name='organizeCompressionMode'][value='custom']").checked = true;
      renderCompressionProfiles();
    });
  }

  confirmAddonDiscard(
    "organizeCompressEnabled",
    () => selectedCompressionMode() !== "recommended" || Boolean($("#organizeTargetMinMb").value || $("#organizeTargetMaxMb").value),
    () => {
      $("input[name='organizeCompressionMode'][value='recommended']").checked = true;
      $("#organizeTargetMinMb").value = "";
      $("#organizeTargetMaxMb").value = "";
      renderCompressionProfiles();
    },
    "Discard the compression settings?",
  );
  confirmAddonDiscard(
    "organizeProtectEnabled",
    () => Boolean($("#organizeProtectPassword").value || $("#organizeProtectConfirm").value),
    () => {
      $("#organizeProtectPassword").value = "";
      $("#organizeProtectConfirm").value = "";
    },
    "Discard the password protection settings?",
  );
  toggleBody("compress", "organizeCompressEnabled", "organizeCompressBody");
  toggleBody("protect", "organizeProtectEnabled", "organizeProtectBody");
  for (const id of ["organizeCompressEnabled", "organizeProtectEnabled", "organizeHashEnabled"]) {
    $(`#${id}`).addEventListener("change", executionOrder);
  }

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
      if (!state.currentSource) throw new Error("Upload a PDF first.");
      const files = getFiles("organizeFile");
      const file = files.length === 1
        ? files[0]
        : temporaryFile(referenceFor(state.workflowId, state.currentSource));
      await loadSource(file, state.currentSource);
      setStatus(status, "Page arrangement reset to the current PDF list.", "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  function renderResult(data) {
    state.result = data.artifact;
    $("#organizeResultMeta").textContent = `${data.artifact.file_name} • ${data.artifact.page_count} pages • ${formatBytes(data.artifact.bytes)}`;
    const hash = $("#organizeResultHash");
    hash.classList.toggle("hidden", !data.sha256);
    hash.textContent = data.sha256 ? `SHA-256  ${data.sha256}` : "";
    const canContinue = Boolean(data.transfer_destinations?.length);
    $("#organizeContinueHeading").classList.toggle("hidden", !canContinue);
    $("#organizeContinueGrid").classList.toggle("hidden", !canContinue);
    $("#organizeProtectedTerminal").classList.toggle("hidden", canContinue);
    $("#organizeWorkflowResult").classList.remove("hidden");
    $("#organizeWorkflowResult").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  $("#organizeBtn").addEventListener("click", async () => {
    try {
      if (!state.workflowId || !state.currentSource) throw new Error("Choose or drop a file first.");
      if (!workspace.items.length) throw new Error("Load the page arrangement first.");
      const password = $("#organizeProtectPassword").value;
      if ($("#organizeProtectEnabled").checked) {
        if (!password) throw new Error("Enter a password for the protected PDF.");
        if (password !== $("#organizeProtectConfirm").value) throw new Error("The protection passwords do not match.");
      }
      const form = new FormData();
      form.append("artifact_id", state.currentSource.artifact_id);
      form.append("plan_json", JSON.stringify(workspace.getPlan()));
      if ($("#organizeCompressEnabled").checked) {
        const mode = selectedCompressionMode();
        form.append("compress_mode", mode);
        if (mode === "custom") {
          form.append("target_min_mb", $("#organizeTargetMinMb").value);
          form.append("target_max_mb", $("#organizeTargetMaxMb").value);
        }
      }
      if ($("#organizeProtectEnabled").checked) form.append("protect_password", password);
      form.append("generate_sha256", $("#organizeHashEnabled").checked ? "true" : "false");
      setStatus(status, `Running ${$("#organizeExecutionOrder").querySelector("span").textContent}…`);
      const response = await apiFetch(
        `/api/workflows/${encodeURIComponent(state.workflowId)}/organize/execute`,
        { method: "POST", body: form, progressElement: status, progressLabel: "Running organize workflow…" },
      );
      const data = await jsonResponse(response);
      renderResult(data);
      const compressionNote = data.compression?.note ? ` ${data.compression.note}` : "";
      setStatus(status, `Done. ${data.execution_order.join(" → ")} completed.${compressionNote}`, "success");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#organizeDownload").addEventListener("click", async () => {
    if (!state.workflowId || !state.result) return;
    try {
      const response = await apiFetch(state.result.download_url);
      await downloadResponse(response, state.result.file_name || "organized.pdf");
    } catch (error) {
      setStatus(status, error.message || String(error), "error");
    }
  });

  $("#organizeFinish").addEventListener("click", async () => {
    await deleteCurrentWorkflow();
    state.result = null;
    state.sourceEntries = [];
    state.suppressFileChange = true;
    clearFiles("organizeFile");
    state.suppressFileChange = false;
    clearArrangement();
    renderSourceList([]);
    $("#organizeWorkflowResult").classList.add("hidden");
    setStatus(status, "Workflow finished. Temporary files were cleared; downloaded files are unchanged.", "success");
  });

  document.querySelectorAll("#organizeWorkflowResult [data-destination]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!state.workflowId || !state.result || button.disabled) return;
      const destination = button.dataset.destination;
      try {
        const form = new FormData();
        form.append("artifact_id", state.result.artifact_id);
        form.append("destination", destination);
        form.append("source_feature", "organize");
        const response = await apiFetch(
          `/api/workflows/${encodeURIComponent(state.workflowId)}/transfer`,
          { method: "POST", body: form },
        );
        await jsonResponse(response);
        stageWorkflowTransfer(referenceFor(state.workflowId, state.result, destination));
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
        $("#organizeCompressEnabled").disabled = true;
        $("#organizeCompressCapability").textContent = "Ghostscript is unavailable, so integrated compression is disabled.";
      }
      if (!health.tesseract) {
        const ocr = $("#organizeOcrDestination");
        ocr.disabled = true;
        ocr.querySelector("span").textContent = "Tesseract is unavailable";
      }
    }
  } catch {
    // Backend validation still provides a precise dependency error if needed.
  }

  renderCompressionProfiles();
  renderSourceList([]);
  showEditor(false);
  executionOrder();
}
