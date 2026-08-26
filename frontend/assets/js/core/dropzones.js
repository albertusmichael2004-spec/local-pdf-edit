import { $ } from "./dom.js";
import { clearFiles, firstFile, onFilesChanged, setFiles, updateFileMeta } from "./file_store.js";
import { localImageUrl, pdfFirstPageImage, previewKind } from "./previews.js";

let globalDropGuardBound = false;

export function bindGlobalDropGuard() {
  if (globalDropGuardBound) return;
  globalDropGuardBound = true;
  document.addEventListener("dragover", (event) => event.preventDefault());
  document.addEventListener("drop", (event) => event.preventDefault());
}

export function bindDropzones(root = document) {
  root.querySelectorAll(".dropzone[data-input]").forEach((zone) => {
    if (zone.dataset.bound === "true") return;
    zone.dataset.bound = "true";
    const inputId = zone.dataset.input;
    const input = $(`#${inputId}`);
    if (!input) return;
    const append = zone.dataset.append === "true";

    zone.addEventListener("click", () => input.click());
    input.addEventListener("change", () => setFiles(inputId, input.files, append));
    for (const eventName of ["dragenter", "dragover"]) {
      zone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        zone.classList.add("dragover");
      });
    }
    for (const eventName of ["dragleave", "dragend"]) {
      zone.addEventListener(eventName, () => zone.classList.remove("dragover"));
    }
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      event.stopPropagation();
      zone.classList.remove("dragover");
      if (event.dataTransfer?.files?.length) {
        setFiles(inputId, event.dataTransfer.files, append);
      }
    });
    updateFileMeta(inputId);
    if (!input.multiple) {
      onFilesChanged(inputId, () => refreshSingleFileControls(inputId));
    }
  });
}

export function ensureSingleFileControls(inputId) {
  const input = $(`#${inputId}`);
  const zone = document.querySelector(`.dropzone[data-input="${inputId}"]`);
  if (!input || !zone || input.multiple) return null;
  let shell = document.querySelector(`[data-single-controls-for="${inputId}"]`);
  if (shell) return shell;

  shell = document.createElement("div");
  shell.dataset.singleControlsFor = inputId;
  shell.className = "single-file-controls hidden";
  shell.innerHTML = `
    <div class="single-preview"><img alt="First page / file preview"/><div class="single-file-icon">FILE</div></div>
    <div class="single-file-actions">
      <button type="button" class="btn secondary small remove-current">Remove current file</button>
      <button type="button" class="btn secondary small upload-new">Upload new file</button>
    </div>`;
  const meta = document.querySelector(`[data-filemeta-for="${inputId}"]`)
    || (inputId.endsWith("File") ? $(`#${inputId.replace(/File$/, "FileMeta")}`) : null);
  (meta || zone).insertAdjacentElement("afterend", shell);
  shell.querySelector(".remove-current").addEventListener("click", (event) => {
    event.stopPropagation();
    clearFiles(inputId);
    refreshSingleFileControls(inputId);
  });
  shell.querySelector(".upload-new").addEventListener("click", (event) => {
    event.stopPropagation();
    input.click();
  });
  return shell;
}

export async function refreshSingleFileControls(inputId) {
  const input = $(`#${inputId}`);
  if (!input || input.multiple) return;
  const shell = ensureSingleFileControls(inputId);
  if (!shell) return;
  const file = firstFile(inputId);
  if (!file) {
    shell.classList.add("hidden");
    return;
  }

  shell.classList.remove("hidden");
  const img = shell.querySelector("img");
  const icon = shell.querySelector(".single-file-icon");
  img.removeAttribute("src");
  img.classList.add("hidden");
  icon.classList.remove("hidden");
  icon.textContent = (file.name.split(".").pop() || "FILE").toUpperCase();
  try {
    const kind = previewKind(file);
    if (kind === "image") {
      img.src = localImageUrl(file);
      img.classList.remove("hidden");
      icon.classList.add("hidden");
    } else if (kind === "pdf") {
      img.src = await pdfFirstPageImage(file);
      img.classList.remove("hidden");
      icon.classList.add("hidden");
    }
  } catch {
    // Keep the file-type tile when preview rendering fails.
  }
}

export function initializeSingleFileControls(root = document) {
  root.querySelectorAll(".dropzone[data-input]").forEach((zone) => {
    const input = $(`#${zone.dataset.input}`);
    if (!input || input.multiple) return;
    ensureSingleFileControls(zone.dataset.input);
    refreshSingleFileControls(zone.dataset.input);
  });
}
