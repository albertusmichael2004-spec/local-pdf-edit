import { inspectPdf, previewPdf } from "/frontend/assets/js/core/previews.js?v=7.5";

let modal = null;
let activeRequest = 0;
let activeLoader = null;
let activeFocus = null;
let closeTimer = 0;

function buildModal() {
  if (modal) return modal;
  modal = document.createElement("div");
  modal.className = "pdf-preview-modal hidden";
  modal.setAttribute("aria-hidden", "true");
  modal.innerHTML = `
    <div aria-labelledby="pdfPreviewTitle" aria-modal="true" class="pdf-preview-dialog" role="dialog" tabindex="-1">
      <header class="pdf-preview-header">
        <div class="pdf-preview-heading">
          <strong id="pdfPreviewTitle">PDF preview</strong>
          <span id="pdfPreviewMeta">Loading document…</span>
        </div>
        <button aria-label="Close PDF preview" class="pdf-preview-close" data-pdf-preview-close type="button">×</button>
      </header>
      <div class="pdf-preview-status" id="pdfPreviewStatus" role="status">Preparing preview…</div>
      <div class="pdf-preview-scroll" id="pdfPreviewScroll">
        <div class="pdf-preview-pages" id="pdfPreviewPages"></div>
      </div>
    </div>`;
  document.body.appendChild(modal);

  const close = () => closePdfPreview();
  modal.querySelector("[data-pdf-preview-close]").addEventListener("click", close);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) close();
  });
  return modal;
}

function setStatus(message, type = "") {
  const status = modal?.querySelector("#pdfPreviewStatus");
  if (!status) return;
  status.textContent = message;
  status.className = `pdf-preview-status${type ? ` ${type}` : ""}`;
}

function closePdfPreview() {
  if (!modal || modal.classList.contains("hidden")) return;
  window.clearTimeout(closeTimer);
  closeTimer = 0;
  activeRequest += 1;
  activeLoader?.disconnect();
  activeLoader = null;
  modal.classList.remove("is-visible");
  modal.classList.add("is-closing");
  modal.setAttribute("aria-hidden", "true");
  closeTimer = window.setTimeout(() => {
    modal.classList.add("hidden");
    modal.classList.remove("is-closing");
    document.body.classList.remove("pdf-preview-open");
    modal.querySelector("#pdfPreviewPages").replaceChildren();
    const focusTarget = activeFocus;
    activeFocus = null;
    focusTarget?.focus?.();
    closeTimer = 0;
  }, 240);
}

function pageFigure(page, total) {
  const figure = document.createElement("figure");
  figure.className = "pdf-preview-page";
  figure.dataset.pdfPage = String(page);
  figure.innerHTML = `<div class="pdf-preview-page-loading">Loading page ${page}…</div><figcaption>Page ${page} of ${total}</figcaption>`;
  return figure;
}

function renderPage(figure, preview) {
  const loading = figure.querySelector(".pdf-preview-page-loading");
  loading?.remove();
  const image = document.createElement("img");
  image.alt = `PDF page ${preview.page}`;
  image.draggable = false;
  const reveal = () => window.requestAnimationFrame(() => image.classList.add("is-visible"));
  image.addEventListener("load", reveal, { once: true });
  image.addEventListener("error", reveal, { once: true });
  figure.insertBefore(image, figure.querySelector("figcaption"));
  image.src = preview.image;
  figure.dataset.loaded = "true";
  if (image.complete) reveal();
}

function loadPages(file, pageFigures, token) {
  const pending = new Set();
  let timer = 0;

  const flush = async () => {
    timer = 0;
    if (!pending.size || token !== activeRequest) return;
    const pages = [...pending].slice(0, 4);
    pages.forEach((page) => pending.delete(page));
    try {
      const data = await previewPdf(file, pages, { maxWidth: 1200 });
      if (token !== activeRequest) return;
      for (const preview of data.previews || []) {
        const figure = pageFigures.get(preview.page);
        if (figure) renderPage(figure, preview);
      }
      setStatus("Scroll to review every page.");
    } catch (error) {
      if (token !== activeRequest) return;
      pages.forEach((page) => {
        const figure = pageFigures.get(page);
        const loading = figure?.querySelector(".pdf-preview-page-loading");
        if (loading) loading.textContent = "Could not render this page.";
      });
      setStatus(error.message || String(error), "error");
    }
    if (pending.size) timer = window.setTimeout(flush, 30);
  };

  const queue = (page) => {
    if (!pageFigures.has(page) || pageFigures.get(page).dataset.loaded === "true") return;
    pending.add(page);
    if (!timer) timer = window.setTimeout(flush, 20);
  };

  const scroll = modal.querySelector("#pdfPreviewScroll");
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      queue(Number(entry.target.dataset.pdfPage));
    });
  }, { root: scroll, rootMargin: "520px 0px" });
  pageFigures.forEach((figure) => observer.observe(figure));
  return { queue, disconnect: () => { observer.disconnect(); window.clearTimeout(timer); } };
}

export function openPdfPreview(
  file,
  { pageNumber = 1, title = file?.name || "PDF document", singlePage = false } = {},
) {
  if (!file) return;
  const shell = buildModal();
  window.clearTimeout(closeTimer);
  closeTimer = 0;
  activeLoader?.disconnect();
  activeLoader = null;
  const token = ++activeRequest;
  activeFocus = document.activeElement;
  shell.classList.remove("hidden", "is-closing", "is-visible");
  shell.setAttribute("aria-hidden", "false");
  document.body.classList.add("pdf-preview-open");
  shell.querySelector("#pdfPreviewTitle").textContent = title;
  shell.querySelector("#pdfPreviewMeta").textContent = "Reading document structure…";
  shell.querySelector("#pdfPreviewPages").replaceChildren();
  shell.querySelector("#pdfPreviewScroll").scrollTop = 0;
  setStatus("Preparing preview…");
  shell.querySelector(".pdf-preview-dialog").focus();
  window.requestAnimationFrame(() => {
    if (token === activeRequest && !shell.classList.contains("hidden")) {
      shell.classList.add("is-visible");
    }
  });

  inspectPdf(file).then((info) => {
    if (token !== activeRequest) return;
    const total = Number(info.pages || 0);
    const targetPage = Math.min(Math.max(1, Number(pageNumber) || 1), total || 1);
    const pageFigures = new Map();
    const pages = shell.querySelector("#pdfPreviewPages");
    const pagesToRender = singlePage ? [targetPage] : Array.from(
      { length: total },
      (_value, index) => index + 1,
    );
    for (const page of pagesToRender) {
      const figure = pageFigure(page, total);
      pageFigures.set(page, figure);
      pages.appendChild(figure);
    }
    shell.querySelector("#pdfPreviewMeta").textContent = singlePage
      ? `Page ${targetPage} of ${total} · ${info.name || title}`
      : `${total} page${total === 1 ? "" : "s"} · ${info.name || title}`;
    setStatus(singlePage ? "Single-page preview." : "Preview ready. Scroll to inspect the document.");
    activeLoader = loadPages(file, pageFigures, token);
    activeLoader.queue(targetPage);
    const target = pageFigures.get(targetPage);
    target?.scrollIntoView({ block: "start" });
    shell.querySelectorAll(".pdf-preview-page.is-focus-page").forEach((figure) => figure.classList.remove("is-focus-page"));
    target?.classList.add("is-focus-page");
  }).catch((error) => {
    if (token !== activeRequest) return;
    shell.querySelector("#pdfPreviewMeta").textContent = "Preview unavailable";
    setStatus(error.message || String(error), "error");
  });

}
