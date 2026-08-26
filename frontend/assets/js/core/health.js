import { apiFetch } from "./api.js";
import { $ } from "./dom.js";

export async function loadHealth() {
  try {
    const response = await apiFetch("/api/health");
    const data = await response.json();
    const gs = data.ghostscript ? "GS ✓" : "GS ✕";
    const tess = data.tesseract ? "OCR ✓" : "OCR ✕";
    const office = data.libreoffice ? "LibreOffice ✓" : "Office fallback ✓";
    $("#systemBadge").textContent = `${gs}  •  ${tess}  •  ${office}  •  max ${data.max_file_mb} MB/file`;
  } catch {
    $("#systemBadge").textContent = "Local engine unavailable";
  }
}
