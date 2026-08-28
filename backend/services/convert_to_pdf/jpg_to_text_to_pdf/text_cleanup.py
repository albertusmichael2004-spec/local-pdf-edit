from __future__ import annotations

import re

_CORRECTIONS = (
    (r"\bJang\b", "Yang"),
    (r"\bjang\b", "yang"),
    (r"\bkatakata\b", "kata-kata"),
    (r"\baneki\b", "aneka"),
    (r"\bASSIST\b", "ASSISI"),
    (r"\bMahatinggig\b", "Mahatinggi"),
    (r"\b(?:kiea|klea)\b", "kita"),
    (r"\bmengump\b", "mengumpulkan"),
    (r"\byesus\b", "Yesus"),
    (r"\bSesudah la(?=\s+mengatakan\b)", "Sesudah Ia"),
    (r"\bla\b", "Ia"),
    (r"\bdoadoa\b", "doa-doa"),
    (r"\bYubilum\b", "Yubileum"),
    (r"\btidakan\b", "tindakan"),
    (r"\bdanrumput\b", "dan rumput"),
    (r"\bbanyakorang\b", "banyak orang"),
    (r"\bMarilahkita\b", "Marilah kita"),
    (r"\bRohKudusitu\b", "Roh Kudus itu"),
    (r"\bmMmUrNI\b", "murni"),
    (r"\bkiniakan\b", "kini akan"),
    (r"\bSemogala\b", "Semoga Ia"),
    (r"\blesai\b", "selesai"),
    (r"\btobatyang\b", "tobat yang"),
    (r"\bberkat Tahan\b", "berkat Tuhan"),
    (r"\bsalah:\s+satu\b", "salah satu"),
    (r"^TAHUN ILEUM(?= SANTO FRANSISKUS ASSISI$)", "ZIARAH TAHUN YUBILEUM"),
    (r"^PrP:\s*", "P: "),
    (r"\bkepada Mu\b", "kepada-Mu"),
    (r"^.*?(?=ZIARAH TAHUN YUBILEUM SANTO FRANSISKUS ASSISI)", ""),
)
_IA_CONTEXT = re.compile(
    r'^["“]?la(?=\s+(?:masuk|tidak|telah|mengatakan|yakin|memanggil|menerima)\b)'
)
_TSV_ROW = re.compile(r"^[1-5]\t(?:-?\d+(?:\.\d+)?\t){9,}")


def clean_ocr_line(text: str) -> str:
    """Apply conservative fixes for common Indonesian OCR artifacts."""
    clean = " ".join(part for part in text.replace("�", '"').splitlines() if not _TSV_ROW.match(part))
    clean = _IA_CONTEXT.sub(lambda match: match.group(0)[:-2] + "Ia", clean.strip())
    for pattern, replacement in _CORRECTIONS:
        clean = re.sub(pattern, replacement, clean)
    clean = re.sub(r"(?<=\w)\.(?=[A-Z])", ". ", clean)
    clean = re.sub(r"^i (?=LINGKUNGAN\b)", "", clean)
    clean = re.sub(r"\s+([,.;:!?])", r"\1", clean)
    clean = re.sub(r"([,;:!?])(?=\w)", r"\1 ", clean)
    return re.sub(r"[ \t]{2,}", " ", clean).strip()
