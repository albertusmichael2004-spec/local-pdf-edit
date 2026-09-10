const STORAGE_KEY = "local-pdf-workbench.locale";
const SUPPORTED = new Set(["en", "id"]);
const sourceByNode = new WeakMap();
let locale = "en";
let applying = false;

const translations = {
  id: {
    "brand.name": "Local PDF Workbench",
    "language.label": "Bahasa",
    "language.english": "English",
    "language.indonesian": "Bahasa Indonesia",
    "nav.mediaTools": "Media Tools",
    "nav.editPdf": "Edit PDF",
    "nav.convertToPdf": "Konversi ke PDF",
    "nav.convertFromPdf": "Konversi dari PDF",
    "nav.pdfSecurity": "Keamanan PDF",
    "nav.documentSecurity": "Keamanan Dokumen",
    "nav.merge": "Gabungkan PDF",
    "nav.split": "Pisahkan PDF",
    "nav.organize": "Atur PDF",
    "nav.redact": "Redaksi PDF",
    "nav.compress": "Kompres PDF",
    "nav.removePages": "Hapus halaman",
    "nav.extractPages": "Ekstrak halaman",
    "nav.ocr": "OCR PDF",
    "nav.rotate": "Putar PDF",
    "nav.watermark": "Tambah watermark",
    "nav.crop": "Potong PDF",
    "nav.mediaConverter": "Konverter Media",
    "nav.mediaCompressor": "Kompresor Media",
    "nav.recommended": "Direkomendasikan",
    "nav.jpgToPdf": "JPG ke PDF",
    "nav.imageOcr": "OCR Gambar ke PDF / Word",
    "nav.wordToPdf": "Word ke PDF",
    "nav.powerPointToPdf": "PowerPoint ke PDF",
    "nav.excelToPdf": "Excel ke PDF",
    "nav.htmlToPdf": "HTML ke PDF",
    "nav.pdfToJpg": "PDF ke JPG",
    "nav.pdfToWord": "PDF ke Word",
    "nav.pdfToPowerPoint": "PDF ke PowerPoint",
    "nav.pdfToExcel": "PDF ke Excel",
    "nav.unlock": "Buka kunci PDF",
    "nav.protect": "Lindungi PDF",
    "nav.sha256Pdf": "SHA-256 PDF",
    "nav.comparePdf": "Bandingkan PDF",
    "nav.allInOne": "Semua dalam Satu",
    "nav.sha256File": "SHA-256 File",
    "nav.compareSha256": "Bandingkan SHA-256",
    "nav.decrypt": "Dekripsi File / Arsip",
    "nav.extractArchive": "Ekstrak Arsip",
    "nav.passwordProtect": "Lindungi File dengan Password",
    "nav.create7z": "Buat Arsip 7z",
    "nav.aes256": "Enkripsi AES-256",
    "update.available": "Pembaruan tersedia",
    "update.download": "Unduh pembaruan",
    "update.history": "Perubahan sejak versi Anda",
    "shell.localProcessing": "Pemrosesan lokal",
    "shell.privacy": "File tetap berada di komputer ini. Artifact workflow dibersihkan saat selesai, direset, atau kedaluwarsa.",
    "shell.engineReady": "Engine lokal siap",
    "shell.engineLoading": "Engine lokal sedang dimuat…",
    "shell.engineFailed": "Engine lokal gagal — mulai ulang aplikasi",
    "startup.loading": "Memuat fitur aplikasi…",
    "feature.merge": "Gabungkan PDF",
    "feature.split": "Pisahkan PDF",
    "feature.media-converter": "Konverter Media",
    "feature.media-compressor": "Kompresor Media",
    "feature.remove-pages": "Hapus halaman",
    "feature.extract-pages": "Ekstrak halaman",
    "feature.organize": "Atur PDF",
    "feature.redact": "Redaksi PDF",
    "feature.compress": "Kompres PDF",
    "feature.ocr": "OCR PDF",
    "feature.rotate": "Putar PDF",
    "feature.watermark": "Tambah watermark",
    "feature.crop": "Potong PDF",
    "feature.jpg-to-pdf": "JPG ke PDF",
    "feature.jpg-to-text-to-pdf": "OCR Gambar ke PDF / Word",
    "feature.word-to-pdf": "Word ke PDF",
    "feature.ppt-to-pdf": "PowerPoint ke PDF",
    "feature.excel-to-pdf": "Excel ke PDF",
    "feature.html-to-pdf": "HTML ke PDF",
    "feature.pdf-to-jpg": "PDF ke JPG",
    "feature.pdf-to-word": "PDF ke Word",
    "feature.pdf-to-ppt": "PDF ke PowerPoint",
    "feature.pdf-to-excel": "PDF ke Excel",
    "feature.unlock": "Buka kunci PDF",
    "feature.protect": "Lindungi PDF",
    "feature.sha256": "SHA-256 PDF",
    "feature.compare-pdf": "Bandingkan PDF",
    "feature.document-security-all": "Keamanan Dokumen — Semua dalam Satu",
    "feature.document-sha256": "SHA-256 File",
    "feature.sha256-compare": "Bandingkan SHA-256",
    "feature.document-decrypt": "Dekripsi File / Arsip",
    "feature.extract-archive": "Ekstrak Arsip",
    "feature.document-password-protect": "Lindungi File dengan Password",
    "feature.create-7z": "Buat Arsip 7z",
    "feature.aes256-encrypt": "Enkripsi AES-256",
    "createAnother": "Buat yang lain",
    "createAnotherTitle": "Bersihkan tugas ini dan mulai lagi",
    "resetting": "Mengatur ulang…",
    "resetError": "Tidak dapat mengatur ulang tugas ini.",
    "resetEngineError": "Engine lokal tidak dapat mengatur ulang tugas.",
    "retryFeature": "Coba buka fitur lagi",
    "featureLoadFailed": "Fitur gagal dimuat",
    "dropPdf": "Jatuhkan PDF di sini atau klik untuk memilih",
    "dropPdfs": "Jatuhkan PDF di sini atau klik untuk memilih",
    "dropAgain": "Jatuhkan lagi untuk menambahkan file lainnya.",
    "clear": "Bersihkan",
    "remove": "Hapus",
    "password": "Password",
    "confirmPassword": "Konfirmasi password",
    "recommended": "Direkomendasikan",
    "extremeCompression": "Kompresi ekstrem",
    "lessCompression": "Kompresi ringan",
    "customTargetRange": "Rentang target khusus",
    "minMb": "Min MB",
    "maxMb": "Maks MB",
    "localOnly": "Semua pemrosesan dan preview tetap lokal.",
    "organize.kicker": "WORKFLOW TERINTEGRASI",
    "organize.description": "Atur sekali, lalu kompres, lindungi, hash, atau lanjutkan ke alat PDF lain tanpa mengunggah ulang hasilnya.",
    "organize.drop": "Jatuhkan satu atau beberapa PDF",
    "organize.dropHint": "Beberapa PDF akan otomatis digabung sesuai urutan di bawah.",
    "organize.uploaded": "PDF yang diunggah",
    "organize.uploadedHint": "Geser untuk mengubah urutan merge, tambahkan file, atau hapus sumber.",
    "organize.removeAll": "Hapus semua",
    "organize.localWorkflow": "Workflow sementara lokal",
    "organize.pageArrangement": "Susunan halaman",
    "organize.pageHint": "Geser untuk mengatur ulang. Arahkan ke halaman untuk menambah halaman kosong, memutar, atau menghapusnya.",
    "organize.newOrder": "Urutan halaman baru",
    "organize.applyOrder": "Terapkan urutan",
    "organize.resetPages": "Reset halaman",
    "organize.additional": "Aksi tambahan",
    "organize.additionalHint": "Pilih hanya kebutuhan output ini. Pengaturan tetap tersimpan saat panel dibuka atau ditutup.",
    "organize.safeOrder": "Urutan aman",
    "organize.compress": "Kompres hasil",
    "organize.protect": "Lindungi hasil",
    "organize.hash": "Buat SHA-256",
    "organize.execution": "Urutan eksekusi",
    "organize.run": "Jalankan workflow pengaturan",
    "organize.ready": "PDF sementara siap",
    "organize.download": "Unduh PDF",
    "organize.finish": "Selesai & bersihkan file sementara",
    "organize.continue": "Lanjutkan pengeditan",
    "organize.continueHint": "Alat berikut akan dibuka dengan PDF sementara yang sudah dimuat.",
    "organize.splitHint": "Buat beberapa output",
    "organize.extractHint": "Pilih halaman yang dipertahankan",
    "organize.watermarkHint": "Buka editor watermark",
    "organize.cropHint": "Buka editor crop visual",
    "organize.ocrHint": "Jadikan hasil scan dapat dicari",
  },
};

const textTranslations = {
  "Language": "Bahasa",
  "English": "English",
  "Bahasa Indonesia": "Bahasa Indonesia",
  "Windows desktop-ready": "Siap untuk desktop Windows",
  "Local processing": "Pemrosesan lokal",
  "Files stay on this computer. Workflow artifacts are cleared on Finish, reset, or timeout.": "File tetap berada di komputer ini. Artifact workflow dibersihkan saat selesai, direset, atau kedaluwarsa.",
  "Local engine ready": "Engine lokal siap",
  "Local engine loading…": "Engine lokal sedang dimuat…",
  "Local engine failed — restart the app": "Engine lokal gagal — mulai ulang aplikasi",
  "Clear this task and start again": "Bersihkan tugas ini dan mulai lagi",
  "Loading application features…": "Memuat fitur aplikasi…",
  "Merging PDFs locally…": "Menggabungkan PDF secara lokal…",
  "Preparing the merged page arrangement…": "Menyiapkan susunan halaman gabungan…",
  "Preparing the page arrangement…": "Menyiapkan susunan halaman…",
  "Add one or more PDFs to start organizing.": "Tambahkan satu atau beberapa PDF untuk mulai mengatur.",
  "Add at least two PDFs.": "Tambahkan setidaknya dua PDF.",
  "Merge PDF": "Gabungkan PDF",
  "Split PDF": "Pisahkan PDF",
  "Media Converter": "Konverter Media",
  "Media Compressor": "Kompresor Media",
  "Remove pages": "Hapus halaman",
  "Extract pages": "Ekstrak halaman",
  "Organize PDF": "Atur PDF",
  "Redact PDF": "Redaksi PDF",
  "Compress PDF": "Kompres PDF",
  "OCR PDF": "OCR PDF",
  "Rotate PDF": "Putar PDF",
  "Add watermark": "Tambah watermark",
  "Crop PDF": "Potong PDF",
  "Convert to PDF": "Konversi ke PDF",
  "Convert from PDF": "Konversi dari PDF",
  "PDF Security": "Keamanan PDF",
  "Document Security": "Keamanan Dokumen",
  "JPG to PDF": "JPG ke PDF",
  "Word to PDF": "Word ke PDF",
  "PowerPoint to PDF": "PowerPoint ke PDF",
  "Excel to PDF": "Excel ke PDF",
  "HTML to PDF": "HTML ke PDF",
  "PDF to JPG": "PDF ke JPG",
  "PDF to Word": "PDF ke Word",
  "PDF to PowerPoint": "PDF ke PowerPoint",
  "PDF to Excel": "PDF ke Excel",
  "Unlock PDF": "Buka kunci PDF",
  "Protect PDF": "Lindungi PDF",
  "All in One": "Semua dalam Satu",
  "SHA-256 File": "SHA-256 File",
  "Compare SHA-256": "Bandingkan SHA-256",
  "Decrypt File / Archive": "Dekripsi File / Arsip",
  "Extract Archive": "Ekstrak Arsip",
  "Password Protect File": "Lindungi File dengan Password",
  "Create 7z Archive": "Buat Arsip 7z",
  "AES-256 Encrypt": "Enkripsi AES-256",
  "Drop PDF": "Jatuhkan PDF",
  "Drop PDFs here or click to browse": "Jatuhkan PDF di sini atau klik untuk memilih",
  "Drop a PDF here or click to browse": "Jatuhkan PDF di sini atau klik untuk memilih",
  "Drop one or more PDFs": "Jatuhkan satu atau beberapa PDF",
  "Drop scanned PDF": "Jatuhkan PDF hasil scan",
  "Drop images": "Jatuhkan gambar",
  "Drop any file": "Jatuhkan file apa pun",
  "Drop first file": "Jatuhkan file pertama",
  "Drop second file": "Jatuhkan file kedua",
  "Clear": "Bersihkan",
  "Create another one": "Buat yang lain",
  "Download PDF": "Unduh PDF",
  "Password": "Password",
  "Confirm password": "Konfirmasi password",
  "Recommended": "Direkomendasikan",
  "Extreme compression": "Kompresi ekstrem",
  "Less compression": "Kompresi ringan",
  "Custom target range": "Rentang target khusus",
  "Min MB": "Min MB",
  "Max MB": "Maks MB",
  "Page arrangement": "Susunan halaman",
  "Apply order": "Terapkan urutan",
  "Reset pages": "Reset halaman",
  "Uploaded PDFs": "PDF yang diunggah",
  "Remove all": "Hapus semua",
  "Additional actions": "Aksi tambahan",
  "Execution order": "Urutan eksekusi",
  "Protect result": "Lindungi hasil",
  "Compress result": "Kompres hasil",
  "Generate SHA-256": "Buat SHA-256",
  "Local temporary workflow": "Workflow sementara lokal",
  "Temporary PDF is ready": "PDF sementara siap",
  "Continue editing": "Lanjutkan pengeditan",
  "Extract selected pages": "Ekstrak halaman yang dipilih",
  "Remove selected pages": "Hapus halaman yang dipilih",
  "Run OCR": "Jalankan OCR",
  "Convert to PDF": "Konversi ke PDF",
  "Convert to Word": "Konversi ke Word",
  "Convert to JPG": "Konversi ke JPG",
  "Convert to PowerPoint": "Konversi ke PowerPoint",
  "Convert to Excel": "Konversi ke Excel",
  "Choose local file": "Pilih file lokal",
  "Choose local folder": "Pilih folder lokal",
  "Generate SHA-256": "Buat SHA-256",
  "Encrypt with AES-256": "Enkripsi dengan AES-256",
  "Create protected ZIP": "Buat ZIP terlindungi",
  "Create 7z archive": "Buat arsip 7z",
  "Decrypt and download": "Dekripsi dan unduh",
  "Extract files": "Ekstrak file",
  "Add multiple PDF files and drag them into the exact output order.": "Tambahkan beberapa file PDF lalu geser ke urutan output yang tepat.",
  "Drop again to add more files.": "Jatuhkan lagi untuk menambahkan file lainnya.",
  "Choose a quality profile or aim for a target file-size range.": "Pilih profil kualitas atau tentukan rentang ukuran file target.",
  "Ghostscript runs locally.": "Ghostscript berjalan secara lokal.",
  "Smallest practical output while keeping scans and images readable instead of heavily blurred.": "Output sekecil mungkin sambil menjaga scan dan gambar tetap terbaca.",
  "Good quality and meaningful compression.": "Kualitas baik dengan kompresi yang tetap terasa.",
  "High quality with lighter size reduction.": "Kualitas tinggi dengan pengurangan ukuran yang lebih ringan.",
  "Aim for a size window rather than an exact byte count.": "Tentukan rentang ukuran, bukan jumlah byte yang harus persis.",
  "Combine JPG, JPEG, or PNG images into one PDF in the selected order.": "Gabungkan gambar JPG, JPEG, atau PNG menjadi satu PDF sesuai urutan pilihan.",
  "Drop again to append more images.": "Jatuhkan lagi untuk menambahkan gambar.",
  "Arrange once, then optionally compress, protect, hash, or continue in another PDF tool without uploading the result again.": "Atur sekali, lalu kompres, lindungi, hash, atau lanjutkan ke alat PDF lain tanpa mengunggah ulang hasilnya.",
  "Multiple PDFs are merged automatically in the order shown below.": "Beberapa PDF akan otomatis digabung sesuai urutan di bawah.",
  "Drag to change merge order, add more above, or remove any source.": "Geser untuk mengubah urutan merge, tambahkan file, atau hapus sumber.",
  "Drag to reorder. Hover a page to insert a blank page, rotate it, or remove it.": "Geser untuk mengatur urutan. Arahkan ke halaman untuk menambah halaman kosong, memutar, atau menghapusnya.",
  "Choose only what this output needs. Settings survive collapse and expand.": "Pilih hanya kebutuhan output ini. Pengaturan tetap tersimpan saat panel dibuka atau ditutup.",
  "Runs once, after page changes and before protection.": "Dijalankan sekali, setelah perubahan halaman dan sebelum perlindungan.",
  "Apply AES-256 password protection after all editing.": "Terapkan perlindungan password AES-256 setelah semua pengeditan.",
  "Calculated from the exact final artifact, after every modification.": "Dihitung dari artifact final yang tepat setelah semua perubahan.",
  "Choose pages, then drag the blue crop frame or enter exact margins in millimeters.": "Pilih halaman, lalu geser bingkai crop biru atau masukkan margin dalam milimeter.",
  "The original file is not modified.": "File asli tidak diubah.",
  "Select page thumbnails to create a new PDF in the original page order.": "Pilih thumbnail halaman untuk membuat PDF baru dalam urutan halaman asli.",
  "Upload once, then select pages below.": "Unggah sekali, lalu pilih halaman di bawah.",
  "Click thumbnails or check boxes to select pages.": "Klik thumbnail atau checkbox untuk memilih halaman.",
  "Turn scanned pages into a searchable PDF using local Tesseract OCR.": "Ubah halaman hasil scan menjadi PDF yang dapat dicari dengan Tesseract OCR lokal.",
  "OCR rasterizes pages and adds a searchable text layer.": "OCR merasterisasi halaman dan menambahkan lapisan teks yang dapat dicari.",
  "Stage one or more text watermarks, apply them to all pages or selected pages, preview the result, then export once.": "Siapkan satu atau beberapa watermark teks, terapkan ke semua atau halaman pilihan, lihat preview, lalu ekspor sekali.",
  "All processing and previews remain local.": "Semua pemrosesan dan preview tetap lokal.",
  "Watermark text": "Teks watermark",
  "All pages": "Semua halaman",
  "Custom pages": "Halaman khusus",
  "Font size": "Ukuran font",
  "Opacity": "Opasitas",
  "Rotation": "Rotasi",
  "Save custom font": "Simpan font khusus",
  "Clear staged watermarks": "Bersihkan watermark yang disiapkan",
  "Add watermark to selection": "Tambahkan watermark ke pilihan",
  "Watermark preview": "Preview watermark",
  "Export PDF": "Ekspor PDF",
  "Tesseract language code": "Kode bahasa Tesseract",
  "Render DPI": "DPI render",
  "Protect any document, image, ZIP, or other file with one action.": "Lindungi dokumen, gambar, ZIP, atau file lain dengan satu aksi.",
  "Drop a file or ZIP": "Jatuhkan file atau ZIP",
  "Click this area to choose a file from your computer.": "Klik area ini untuk memilih file dari komputer.",
  "Original": "Asli",
  "Comparison": "Perbandingan",
  "Compare hashes": "Bandingkan hash",
  "Archive password": "Password arsip",
  "Archive password (optional)": "Password arsip (opsional)",
  "No application file-size limit.": "Tidak ada batas ukuran file dari aplikasi.",
  "Extract to a new folder beside the compressed file": "Ekstrak ke folder baru di sebelah file terkompresi",
  "PDF to Excel": "PDF ke Excel",
  "PDF to JPG": "PDF ke JPG",
  "PDF to PowerPoint": "PDF ke PowerPoint",
  "PDF to Word": "PDF ke Word",
  "Excel to PDF": "Excel ke PDF",
  "PowerPoint to PDF": "PowerPoint ke PDF",
  "Word to PDF": "Word ke PDF",
  "HTML to PDF": "HTML ke PDF",
  "Image OCR to PDF / Word": "OCR Gambar ke PDF / Word",
  "Best-effort table extraction with one worksheet per PDF page.": "Ekstraksi tabel terbaik dengan satu worksheet untuk setiap halaman PDF.",
  "Render each page into a high-quality JPG and download a ZIP.": "Render setiap halaman menjadi JPG berkualitas tinggi lalu unduh ZIP.",
  "Create one visually faithful image slide per PDF page.": "Buat satu slide gambar yang mempertahankan tampilan setiap halaman PDF.",
  "Reconstruct a digital PDF as an editable DOCX.": "Susun ulang PDF digital menjadi DOCX yang dapat diedit.",
  "Output format": "Format output",
  "OCR language": "Bahasa OCR",
  "OCR quality": "Kualitas OCR",
  "Fast": "Cepat",
  "Accurate": "Akurat",
  "Maximum accuracy": "Akurasi maksimum",
  "PDF layout": "Tata letak PDF",
  "Preserve original layout": "Pertahankan tata letak asli",
  "Editable text": "Teks yang dapat diedit",
};

const reverseTextTranslations = new Map(Object.entries(textTranslations).map(([en, id]) => [id, en]));

export function getLocale() {
  return locale;
}

export function t(key, fallback = key) {
  if (locale === "en") return fallback;
  return translations[locale]?.[key] || textTranslations[fallback] || fallback;
}

function normalized(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function translatedText(source) {
  if (!source) return source;
  if (locale === "en") return reverseTextTranslations.get(source) || source;
  const merged = source.match(/^(\d+) PDFs merged into (\d+) pages\. Arrangement is ready\.$/);
  if (merged) return `${merged[1]} PDF berhasil digabung menjadi ${merged[2]} halaman. Susunan siap.`;
  const ready = source.match(/^(\d+) pages are ready to arrange\.$/);
  if (ready) return `${ready[1]} halaman siap diatur.`;
  const selected = source.match(/^(\d+) selected$/);
  if (selected) return `${selected[1]} dipilih`;
  const pages = source.match(/^(\d+) pages?$/);
  if (pages) return `${pages[1]} halaman`;
  const page = source.match(/^Page (\d+)$/);
  if (page) return `Halaman ${page[1]}`;
  return textTranslations[source] || source;
}

function replaceTextNode(node) {
  const raw = node.nodeValue || "";
  const current = normalized(raw);
  if (!current) return;
  const canonical = sourceByNode.get(node) || reverseTextTranslations.get(current) || current;
  sourceByNode.set(node, canonical);
  const next = translatedText(canonical);
  if (next === current) return;
  const leading = raw.match(/^\s*/)?.[0] || "";
  const trailing = raw.match(/\s*$/)?.[0] || "";
  node.nodeValue = `${leading}${next}${trailing}`;
}

export function translateTree(root = document) {
  if (!root || applying) return;
  applying = true;
  try {
    const scope = root.nodeType === Node.TEXT_NODE ? root.parentElement : root;
    scope?.querySelectorAll?.("[data-i18n]").forEach((element) => {
      const key = element.dataset.i18n;
      const fallback = element.dataset.i18nFallback || element.textContent || key;
      element.textContent = t(key, fallback);
    });
    scope?.querySelectorAll?.("[data-i18n-title]").forEach((element) => {
      element.title = t(element.dataset.i18nTitle, element.dataset.i18nTitleFallback || element.title);
    });
    scope?.querySelectorAll?.("[data-i18n-placeholder]").forEach((element) => {
      element.placeholder = t(element.dataset.i18nPlaceholder, element.dataset.i18nPlaceholderFallback || element.placeholder);
    });
    scope?.querySelectorAll?.("[data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel, element.dataset.i18nAriaLabelFallback || element.getAttribute("aria-label") || ""));
    });
    scope?.querySelectorAll?.("[data-i18n-badge]").forEach((element) => {
      element.dataset.badge = t(element.dataset.i18nBadge, element.dataset.i18nBadgeFallback || "Recommended");
    });
    const walker = document.createTreeWalker(scope || document, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      if (node.parentElement?.closest("[data-i18n]")) return;
      replaceTextNode(node);
    });
  } finally {
    applying = false;
  }
}

function persistLocaleRemotely(next) {
  fetch("/api/preferences/language", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ language: next }),
  }).catch(() => {});
}

export function setLocale(nextLocale, { persist = true } = {}) {
  const next = SUPPORTED.has(nextLocale) ? nextLocale : "en";
  locale = next;
  try { localStorage.setItem(STORAGE_KEY, next); } catch { /* localStorage may be unavailable */ }
  if (persist) persistLocaleRemotely(next);
  document.documentElement.lang = next === "id" ? "id" : "en";
  translateTree(document);
  document.dispatchEvent(new CustomEvent("pdf-workbench:locale-change", { detail: { locale: next } }));
}

export async function initI18n() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (SUPPORTED.has(saved)) locale = saved;
  } catch { /* use English when storage is unavailable */ }
  const select = document.querySelector("#languageSelect");
  if (select) {
    select.value = locale;
    select.addEventListener("change", () => setLocale(select.value));
  }
  document.documentElement.lang = locale === "id" ? "id" : "en";
  translateTree(document);
  const observer = new MutationObserver((records) => {
    if (applying) return;
    records.forEach((record) => {
      if (record.type === "characterData") replaceTextNode(record.target);
      else translateTree(record.target);
    });
  });
  observer.observe(document.body, { subtree: true, childList: true, characterData: true });

  // The desktop shell uses a disposable Chromium profile, so localStorage is
  // only a fast fallback. The API preference survives closing and reopening
  // the installed app through the user's persistent application data folder.
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 1200);
  try {
    const response = await fetch("/api/preferences/language", {
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
    });
    if (response.ok) {
      const payload = await response.json();
      if (SUPPORTED.has(payload?.language) && payload.language !== locale) {
        setLocale(payload.language, { persist: false });
      }
    }
  } catch {
    // Keep the localStorage/default locale when the local API is unavailable.
  } finally {
    window.clearTimeout(timeout);
  }
  return locale;
}
