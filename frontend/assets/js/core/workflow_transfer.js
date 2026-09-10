import { apiFetch, parseError } from "/frontend/assets/js/core/api.js";
import { setFiles } from "/frontend/assets/js/core/file_store.js";

const STORAGE_KEY = "local-pdf-workbench.workflow-transfer";
const bindingsByInput = new Map();
const bindingsByFile = new WeakMap();
const WORKFLOW_REFERENCE = Symbol.for("local-pdf-workbench.workflow-reference");

const DESTINATION_INPUTS = {
  split: "splitFile",
  "extract-pages": "extractFile",
  watermark: "watermarkFile",
  crop: "cropFile",
  ocr: "ocrFile",
  redact: "redactFile",
};

function readPendingTransfer() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function bindWorkflowInput(inputId, file, reference) {
  const binding = { ...reference, inputId, file };
  bindingsByInput.set(inputId, binding);
  bindingsByFile.set(file, binding);
  Object.defineProperty(file, WORKFLOW_REFERENCE, {
    configurable: true,
    enumerable: false,
    value: { ...reference, inputId },
  });
  return binding;
}

export function workflowReferenceForFile(file, inputId = null) {
  if (!file) return null;
  const direct = bindingsByFile.get(file) || file[WORKFLOW_REFERENCE] || null;
  if (direct) return direct;
  const inputBinding = inputId ? bindingsByInput.get(inputId) : null;
  return inputBinding?.file === file ? inputBinding : null;
}

export function appendWorkflowReference(form, file, inputId = null, { prefix = "" } = {}) {
  const binding = workflowReferenceForFile(file, inputId);
  if (!binding) return false;
  form.append(`${prefix}workflow_id`, binding.workflowId);
  form.append(`${prefix}artifact_id`, binding.artifactId);
  return true;
}

export function stageWorkflowTransfer(reference) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(reference));
}

export function clearPendingWorkflowTransfer() {
  sessionStorage.removeItem(STORAGE_KEY);
}

function transferBanner(reference) {
  const banner = document.createElement("div");
  banner.className = "workflow-transfer-banner";
  const title = document.createElement("strong");
  title.textContent = "Temporary workflow PDF loaded";
  const detail = document.createElement("span");
  const source = reference.sourceFeature === "redact" ? "Redact PDF" : "Organize PDF";
  detail.textContent = `${reference.fileName} is coming from ${source}. The original stays untouched.`;
  banner.append(title, detail);
  return banner;
}

async function verifiedArtifact(reference, artifactId = reference.artifactId) {
  const response = await apiFetch(
    `/api/workflows/${encodeURIComponent(reference.workflowId)}/artifacts/${encodeURIComponent(artifactId)}`,
  );
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

function transferredFile(inputId, reference, artifact) {
  const file = new File([], artifact.file_name, {
    type: artifact.media_type || "application/pdf",
    lastModified: Date.now(),
  });
  Object.defineProperty(file, "workflowBytes", {
    configurable: false,
    enumerable: false,
    value: Number(artifact.bytes || 0),
  });
  const enriched = {
    ...reference,
    artifactId: artifact.artifact_id,
    fileName: artifact.file_name,
    mediaType: artifact.media_type,
    bytes: artifact.bytes,
    pageCount: artifact.page_count,
    pageIds: artifact.page_ids,
    pageSources: artifact.page_sources,
    sourceOperation: artifact.source_operation,
  };
  bindWorkflowInput(inputId, file, enriched);
  return file;
}

export async function hydratePendingWorkflowTransfer(featureId, panel) {
  const reference = readPendingTransfer();
  if (!reference || reference.destination !== featureId) return false;
  if (featureId === "compare-pdf") {
    if (!reference.comparisonArtifactId) {
      throw new Error("The original workflow PDF is unavailable for comparison.");
    }
    const [leftArtifact, rightArtifact] = await Promise.all([
      verifiedArtifact(reference, reference.comparisonArtifactId),
      verifiedArtifact(reference),
    ]);
    const left = transferredFile("compareLeft", reference, leftArtifact);
    const right = transferredFile("compareRight", reference, rightArtifact);
    setFiles("compareLeft", [left]);
    setFiles("compareRight", [right]);
    panel.prepend(transferBanner({ ...reference, fileName: `${left.name} + ${right.name}` }));
    sessionStorage.removeItem(STORAGE_KEY);
    return true;
  }
  const inputId = DESTINATION_INPUTS[featureId];
  if (!inputId || !panel.querySelector(`#${inputId}`)) return false;
  const artifact = await verifiedArtifact(reference);
  const file = transferredFile(inputId, reference, artifact);
  setFiles(inputId, [file]);
  panel.prepend(transferBanner({ ...reference, fileName: artifact.file_name }));
  sessionStorage.removeItem(STORAGE_KEY);
  return true;
}
