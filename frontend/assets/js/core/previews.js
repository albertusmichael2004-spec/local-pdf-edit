import { apiFetch, parseError } from "./api.js";

const previewCache = new Map();
const imageObjectUrls = new WeakMap();

function fileKey(file) {
  return `${file.name}|${file.size}|${file.lastModified}`;
}

export function localImageUrl(file) {
  if (!imageObjectUrls.has(file)) imageObjectUrls.set(file, URL.createObjectURL(file));
  return imageObjectUrls.get(file);
}

export async function inspectPdf(file) {
  const form = new FormData();
  form.append("file", file);
  const response = await apiFetch("/api/pdf/info", { method: "POST", body: form });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function previewPdf(file, pages) {
  const form = new FormData();
  form.append("file", file);
  form.append("pages", pages.join(","));
  const response = await apiFetch("/api/pdf/previews", { method: "POST", body: form });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export function previewKind(file) {
  const name = file.name.toLowerCase();
  if ((file.type || "").startsWith("image/") || /\.(png|jpe?g)$/i.test(name)) return "image";
  if (name.endsWith(".pdf") || file.type === "application/pdf") return "pdf";
  return "file";
}

export async function pdfFirstPageImage(file) {
  const key = fileKey(file);
  if (previewCache.has(key)) return previewCache.get(key);
  const promise = previewPdf(file, [1]).then((data) => data.previews?.[0]?.image || "");
  previewCache.set(key, promise);
  try {
    return await promise;
  } catch (error) {
    previewCache.delete(key);
    throw error;
  }
}

export async function populateThumb(img, file) {
  const kind = previewKind(file);
  if (kind === "image") {
    img.src = localImageUrl(file);
    return;
  }
  if (kind === "pdf") {
    try {
      img.src = await pdfFirstPageImage(file);
    } catch {
      img.closest(".file-thumb")?.classList.add("thumb-failed");
    }
  }
}
