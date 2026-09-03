import { apiFetch } from "./api.js";
import { $ } from "./dom.js";

export async function loadHealth() {
  try {
    const response = await apiFetch("/api/health");
    const data = await response.json();
    const gs = data.ghostscript ? "GS ✓" : "GS ✕";
    const tess = data.tesseract ? "OCR ✓" : "OCR ✕";
    const office = data.libreoffice ? "LibreOffice ✓" : "Office fallback ✓";
    const media = data.ffmpeg && data.ffprobe ? "Media ✓" : "Media ✕";
    const ebook = data.calibre ? "Ebook ✓" : "Ebook ✕";
    $("#systemBadge").textContent = `${gs}  •  ${tess}  •  ${office}  •  ${media}  •  ${ebook}  •  Uploads uncapped`;
  } catch {
    $("#systemBadge").textContent = "Local engine unavailable";
  }
}
