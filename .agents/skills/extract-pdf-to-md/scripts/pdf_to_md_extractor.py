import bisect
import math
import re
import importlib.util
import sys
import subprocess
from datetime import datetime
from pathlib import Path

import pdfplumber
from pdfplumber.utils import extract_text, get_bbox_overlap, obj_to_bbox

try:
    import fitz  # PyMuPDF
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    fitz = None

try:
    from rapidocr_onnxruntime import RapidOCR
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    RapidOCR = None

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None


SKILL_NAME = "extract-pdf-to-md"

_ROOT = Path(__file__).resolve().parents[4]
_DETECT_LANG_PATH = _ROOT / ".agents" / "skills" / "translate-markdown" / "scripts" / "detect_markdown_language.py"
_TRANSLATE_MD_PATH = _ROOT / ".agents" / "skills" / "translate-markdown" / "scripts" / "translate_markdown.py"
_DB_MODULE_PATH = _ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts" / "db.py"
_FR_TRANSLATION_THRESHOLD = 80
_OCR_ENGINE = None
_OCR_ENABLED = fitz is not None and RapidOCR is not None
_OCR_RENDER_DPI = 288
_OCR_RENDER_COLORSPACE = fitz.csGRAY if fitz is not None else None
_OCR_RENDER_FORMAT = "png"
_OCR_RENDER_ANNOTS = False

_DB_AVAILABLE = False
_GET_DB_CONNECTION = None
_UPSERT_SOURCE = None

_OCR_PRODUCER_HINTS = (
    "adobe psl",
    "canon",
    "abbyy",
    "tesseract",
    "ocr",
    "omnipage",
    "finereader",
    "image capture",
    "scan",
)

try:
    _db_spec = importlib.util.spec_from_file_location("named_entities_db_extract_pdf", _DB_MODULE_PATH)
    if _db_spec is not None and _db_spec.loader is not None:
        _db_module = importlib.util.module_from_spec(_db_spec)
        sys.modules[_db_spec.name] = _db_module
        _db_spec.loader.exec_module(_db_module)
        _GET_DB_CONNECTION = getattr(_db_module, "get_connection", None)
        _UPSERT_SOURCE = getattr(_db_module, "upsert_source", None)
        _DB_AVAILABLE = callable(_GET_DB_CONNECTION) and callable(_UPSERT_SOURCE)
except Exception:
    _DB_AVAILABLE = False


def _get_ocr_engine():
    global _OCR_ENGINE
    if not _OCR_ENABLED:
        return None
    if _OCR_ENGINE is None:
        _OCR_ENGINE = RapidOCR(
            params={
                "Global.lang_det": "multi_server",
                "Global.lang_rec": "multi_server",
                "Global.use_angle_cls": True,
                "Global.use_text_det": True,
                "Global.print_verbose": True
            },
        )
    return _OCR_ENGINE


def _pdf_metadata_blob(pdf_metadata: dict | None) -> str:
    if not pdf_metadata:
        return ""
    parts = []
    for key in ("Producer", "Creator", "Title", "Subject", "Keywords", "producer", "creator"):
        val = pdf_metadata.get(key)
        if val:
            parts.append(str(val))
    return " ".join(parts).lower()


def _is_pdf_likely_ocr_origin(pdf_metadata: dict | None) -> bool:
    blob = _pdf_metadata_blob(pdf_metadata)
    if not blob:
        return False
    return any(hint in blob for hint in _OCR_PRODUCER_HINTS)


def _tokenize_for_quality(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r"[A-Za-zÀ-ÿ0-9'’\-]+", text)


def _ocr_suspicion_ratio(text: str) -> float:
    """Retourne un ratio de tokens suspects (plus bas = meilleur)."""
    tokens = _tokenize_for_quality(text)
    if not tokens:
        return 1.0

    suspicious = 0
    for tok in tokens:
        low = tok.lower()
        has_letter = bool(re.search(r"[A-Za-zÀ-ÿ]", tok))
        has_digit = bool(re.search(r"\d", tok))

        # Cas OCR fréquents: mélange lettres/chiffres, ponctuation cassée, mots collés absurdes.
        if has_letter and has_digit:
            suspicious += 1
            continue
        if re.search(r"[A-Za-zÀ-ÿ]{8,}\d{2,}", tok) or re.search(r"\d{2,}[A-Za-zÀ-ÿ]{8,}", tok):
            suspicious += 1
            continue
        if re.search(r"[A-Za-zÀ-ÿ]{1}\s", tok):
            suspicious += 1
            continue
        if re.search(r"['’]{2,}", tok):
            suspicious += 1
            continue
        # Casse OCR anormale à l'intérieur d'un mot: éPurotion, lmpôts, MuNiciPalité
        if re.search(r"[a-zà-ÿ][A-ZÀ-Ý][a-zà-ÿ]{2,}", tok):
            suspicious += 1
            continue
        if re.search(r"[A-ZÀ-Ý]{2,}[a-zà-ÿ]{2,}[A-ZÀ-Ý]{1,}", tok):
            suspicious += 1
            continue
        if len(low) >= 9 and re.search(r"[a-zà-ÿ]{3}[A-Z]{2}", tok):
            suspicious += 1
            continue

    return suspicious / max(1, len(tokens))


def _text_quality_score(text: str) -> float:
    """Score [0..1], plus élevé = meilleure qualité estimée."""
    tokens = _tokenize_for_quality(text)
    if not tokens:
        return 0.0

    suspicious = _ocr_suspicion_ratio(text)
    alpha_ratio = min(1.0, len(re.findall(r"[A-Za-zÀ-ÿ]", text)) / max(1, len(text)))
    long_word_ratio = sum(1 for t in tokens if re.fullmatch(r"[A-Za-zÀ-ÿ]{4,}", t)) / max(1, len(tokens))

    score = (1.0 - suspicious) * 0.55 + alpha_ratio * 0.20 + long_word_ratio * 0.25
    return max(0.0, min(1.0, score))


def _sample_page_indexes(total_pages: int) -> list[int]:
    if total_pages <= 0:
        return []
    if total_pages == 1:
        return [0]
    mids = {0, total_pages - 1, total_pages // 2}
    return sorted(mids)


def _assess_ocr_replacement(
    pdf_path: Path,
    pages_with_idx: list[tuple[int, object]],
    pdf_metadata: dict | None,
) -> tuple[bool, str, float, float]:
    """Décide si une OCR complète devrait remplacer le texte embarqué du PDF."""
    if not _OCR_ENABLED:
        return False, "ocr_engine_unavailable", 0.0, 0.0

    is_ocr_origin = _is_pdf_likely_ocr_origin(pdf_metadata)
    if not is_ocr_origin:
        return False, "pdf_not_likely_ocr_origin", 0.0, 0.0

    if not pages_with_idx:
        return False, "no_pages", 0.0, 0.0

    total = len(pages_with_idx)
    idxs = _sample_page_indexes(total)
    if not idxs:
        return False, "no_sample_pages", 0.0, 0.0

    embedded_scores: list[float] = []
    new_ocr_scores: list[float] = []

    for sample_idx in idxs:
        page_num, page = pages_with_idx[sample_idx]

        chars = _extract_tables_and_chars(page)
        chars_no_md = [ch for ch in chars if not ch.get("is_markdown_block")]
        header_text, body_text, footer_text = _extract_text_with_header_footer(chars_no_md, page.width, page.height)
        embedded_text = "\n\n".join([p for p in [header_text, body_text, footer_text] if p])
        embedded_text = _fix_intra_word_spaces(_join_soft_wrapped_lines(_dehyphenate_text(embedded_text or "")))

        ocr_text = _ocr_text_from_page(pdf_path, page_num - 1)

        if embedded_text.strip():
            embedded_scores.append(_text_quality_score(embedded_text))
        if ocr_text.strip():
            new_ocr_scores.append(_text_quality_score(ocr_text))

    if not new_ocr_scores:
        return False, "new_ocr_empty", 0.0, 0.0

    old_avg = sum(embedded_scores) / len(embedded_scores) if embedded_scores else 0.0
    new_avg = sum(new_ocr_scores) / len(new_ocr_scores)

    # Déclenchement très conservateur: on force l'OCR complète seulement si le gain est très significatif.
    # Favorise le préservation du texte embedé (qui contient les accents) sur la prise en charge
    # d'une très légère amélioration d'OCR (qui perd les accents/ petits caractères).
    # Seuil augmenté à 0.10 (au lieu de 0.03) pour éviter le remplacement du texte valide.
    #delta = new_avg - old_avg
    #rel_gain = (delta / old_avg) if old_avg > 0 else (1.0 if new_avg > 0 else 0.0)
    #improve = delta >= 0.10 or (delta >= 0.08 and rel_gain >= 0.10)

    # Déclenchement conservateur mais praticable: on force l'OCR complète si le gain est net.
    # - soit gain absolu >= 0.03
    # - soit gain >= 0.02 et amélioration relative >= 5%
    delta = new_avg - old_avg
    rel_gain = (delta / old_avg) if old_avg > 0 else (1.0 if new_avg > 0 else 0.0)
    improve = delta >= 0.03 or (delta >= 0.02 and rel_gain >= 0.05)
    reason = "new_ocr_better" if improve else "embedded_ocr_good_enough"
    return improve, reason, old_avg, new_avg


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _bbox_from_ocr_polygon(polygon) -> tuple[float, float, float, float] | None:
    if not polygon:
        return None

    points = []
    try:
        for point in polygon:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            x = float(point[0])
            y = float(point[1])
            points.append((x, y))
    except Exception:
        return None

    if not points:
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _rows_to_simple_markdown_table(rows: list[list[str]]) -> str | None:
    cleaned = []
    for row in rows:
        if row is None:
            continue
        normalized = []
        for value in row:
            text = str(value or "").strip()
            text = re.sub(r"\s+", " ", text)
            text = text.replace("|", r"\|")
            normalized.append(text)
        if any(cell for cell in normalized):
            cleaned.append(normalized)

    if len(cleaned) < 2:
        return None

    width = max(len(row) for row in cleaned)
    if width < 2:
        return None

    padded_rows = [row + [""] * (width - len(row)) for row in cleaned]
    header = padded_rows[0]
    body = padded_rows[1:]

    sep = ["---"] * width
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _ocr_result_to_text_or_markdown(ocr_result) -> str:
    raw_fragments = []
    tokens = []

    for item in ocr_result or []:
        if not item:
            continue
        text = str(item[1] if len(item) > 1 else "").strip()
        if not text:
            continue
        raw_fragments.append(text)

        polygon = item[0] if len(item) > 0 else None
        bbox = _bbox_from_ocr_polygon(polygon)
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        tokens.append(
            {
                "text": text,
                "x0": x0,
                "x1": x1,
                "y0": y0,
                "y1": y1,
                "xc": (x0 + x1) / 2.0,
                "yc": (y0 + y1) / 2.0,
                "h": max(1.0, y1 - y0),
            }
        )

    if not tokens:
        return "\n".join(raw_fragments).strip()

    row_tolerance = max(6.0, _median([token["h"] for token in tokens]) * 0.75)
    sorted_tokens = sorted(tokens, key=lambda token: (token["yc"], token["x0"]))

    rows: list[dict] = []
    current = []
    current_y = None
    for token in sorted_tokens:
        if current_y is None or abs(token["yc"] - current_y) <= row_tolerance:
            current.append(token)
            current_y = token["yc"] if current_y is None else ((current_y * (len(current) - 1) + token["yc"]) / len(current))
            continue
        rows.append({"tokens": sorted(current, key=lambda row_token: row_token["x0"])})
        current = [token]
        current_y = token["yc"]
    if current:
        rows.append({"tokens": sorted(current, key=lambda row_token: row_token["x0"])})

    for row in rows:
        row_tokens = row["tokens"]
        row_heights = [max(1.0, token["y1"] - token["y0"]) for token in row_tokens]
        row_gap_threshold = max(10.0, _median(row_heights) * 0.9)
        cells = []
        cell_tokens = []
        for token in row_tokens:
            if not cell_tokens:
                cell_tokens = [token]
                continue
            previous = cell_tokens[-1]
            gap = token["x0"] - previous["x1"]
            if gap > row_gap_threshold:
                cell_text = " ".join(tok["text"] for tok in cell_tokens).strip()
                if cell_text:
                    cells.append(cell_text)
                cell_tokens = [token]
            else:
                cell_tokens.append(token)
        if cell_tokens:
            cell_text = " ".join(tok["text"] for tok in cell_tokens).strip()
            if cell_text:
                cells.append(cell_text)
        row["cells"] = cells
        row["line"] = " ".join(cells).strip()

    output_blocks = []
    idx = 0
    while idx < len(rows):
        cell_count = len(rows[idx].get("cells", []))
        if cell_count >= 3:
            end = idx
            while end < len(rows) and len(rows[end].get("cells", [])) >= 2:
                end += 1

            candidate = rows[idx:end]
            if len(candidate) >= 3 and max(len(r.get("cells", [])) for r in candidate) >= 3:
                counts: dict[int, int] = {}
                for row in candidate:
                    c = len(row.get("cells", []))
                    if c >= 2:
                        counts[c] = counts.get(c, 0) + 1
                target_cols = max(counts.items(), key=lambda item: (item[1], item[0]))[0] if counts else 0

                if target_cols >= 2:
                    table_rows = []
                    for row in candidate:
                        cells = list(row.get("cells", []))
                        if not cells:
                            continue
                        if len(cells) < target_cols:
                            cells += [""] * (target_cols - len(cells))
                        elif len(cells) > target_cols:
                            cells = cells[: target_cols - 1] + [" ".join(cells[target_cols - 1 :])]
                        table_rows.append(cells)

                    markdown_table = _rows_to_simple_markdown_table(table_rows)
                    if markdown_table:
                        output_blocks.append(markdown_table)
                        idx = end
                        continue

        line = rows[idx].get("line", "")
        if line:
            output_blocks.append(line)
        idx += 1

    return "\n\n".join(block for block in output_blocks if block).strip()


def _ocr_text_from_page(pdf_path: Path, page_index_0based: int) -> str:
    if not _OCR_ENABLED or fitz is None:
        return ""

    engine = _get_ocr_engine()
    if engine is None:
        return ""

    try:
        with fitz.open(pdf_path) as doc:
            page = doc[page_index_0based]
            pix = page.get_pixmap(
                dpi=_OCR_RENDER_DPI,
                colorspace=_OCR_RENDER_COLORSPACE,
                alpha=False,
                annots=_OCR_RENDER_ANNOTS,
            )
            img_bytes = pix.tobytes(_OCR_RENDER_FORMAT)
    except Exception:
        return ""

    try:
        ocr_result, _ = engine(img_bytes, unclip_ratio=4) # increase unclip_ratio if the whitespaces between words are hung
    except Exception:
        return ""

    return _ocr_result_to_text_or_markdown(ocr_result)


def _load_language_detection_functions():
    if not _DETECT_LANG_PATH.exists():
        return None, None

    module_name = "detect_markdown_language_shared"
    spec = importlib.util.spec_from_file_location(module_name, _DETECT_LANG_PATH)
    if spec is None or spec.loader is None:
        return None, None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, "detect_language_distribution", None), getattr(module, "format_distribution", None)


_detect_language_distribution, _format_distribution = _load_language_detection_functions()

# number of bins for the histogram used to detect the columns or header/footer
NUM_BINS = 1000
# Maximum header or footer height (0.10=10% of the page height)
MAX_HEADER_FOOTER_RATIO = 0.10
# X coordinate tolerance on character overlap (increase this value if spaces between characters are missing)
TEXT_X_TOLERANCE = 1.0

# Special cases for which the hyphen must not be removed
_HYPHEN_EXCEPTIONS = {
    "contre-projet",
    "à-dire",
    "elle-même",
}

_FRENCH_NUMBER_TOKENS = {
    "zero", "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
    "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize", "vingt", "trente",
    "quarante", "cinquante", "soixante", "cent", "mille", "million", "milliard", "et",
}

_MONTHS_MAP = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
    "januar": 1,
    "februar": 2,
    "marz": 3,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

# Détection de colonnes qui fonctionne sur le
# principe suivant:
# - un histogramme h(i) à N=1000 bins correspondant
#   à la largeur de la page est défini.
# - pour chaque caractère, on incrémente les h(i)
#   pour i correspondant aux bins de la plage
#   "x0" - "x1" du de chaque caractère de la page.
# - les minimums locaux de l'histogramme indiquent
#   bandes verticales dans lesquelles les caractères
#   sont les moins présents, donc les séparations
#   entre les colonnes.
#
# Le header et le footer sont détectés avec le même
# principe d'histogramme, mais sur les coordonnées
# y0 et y1 des caractères.

def _percentile(values, q):
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(round((len(sorted_vals) - 1) * q))
    index = max(0, min(len(sorted_vals) - 1, idx))
    return float(sorted_vals[index])


def _smooth_histogram(hist, window=9):
    if not hist:
        return []
    if window <= 1:
        return [float(v) for v in hist]

    radius = window // 2
    smoothed: list[float] = []
    for i in range(len(hist)):
        left = max(0, i - radius)
        right = min(len(hist), i + radius + 1)
        chunk = hist[left:right]
        smoothed.append(float(sum(chunk)) / float(len(chunk)))
    return smoothed


def _build_char_coverage_histogram(chars, page_width, bins=NUM_BINS):
    hist = [0] * bins
    if page_width <= 0:
        return hist

    for ch in chars:
        x0 = float(ch.get("x0", 0.0))
        x1 = float(ch.get("x1", x0))
        if x1 < x0:
            x0, x1 = x1, x0

        x0 = max(0.0, min(page_width, x0))
        x1 = max(0.0, min(page_width, x1))
        if x1 <= x0:
            continue

        start = int((x0 / page_width) * bins)
        end = int(math.ceil((x1 / page_width) * bins) - 1)
        start = max(0, min(bins - 1, start))
        end = max(0, min(bins - 1, end))

        for i in range(start, end + 1):
            hist[i] += 1
    return hist


def _build_char_coverage_histogram_vertical(chars, page_height, bins=NUM_BINS):
    """Histogramme vertical (top->bottom) basé sur les plages y0/y1 des caractères."""
    hist = [0] * bins
    if page_height <= 0:
        return hist

    for ch in chars:
        # Priorité à y0/y1 (demandé), avec fallback top/bottom.
        if "y0" in ch and "y1" in ch:
            y0 = float(ch.get("y0", 0.0))
            y1 = float(ch.get("y1", y0))
            y_low = min(y0, y1)
            y_high = max(y0, y1)
            top = max(0.0, min(page_height, page_height - y_high))
            bottom = max(0.0, min(page_height, page_height - y_low))
        else:
            top = float(ch.get("top", 0.0))
            bottom = float(ch.get("bottom", top))
            if bottom < top:
                top, bottom = bottom, top
            top = max(0.0, min(page_height, top))
            bottom = max(0.0, min(page_height, bottom))

        if bottom <= top:
            continue

        start = int((top / page_height) * bins)
        end = int(math.ceil((bottom / page_height) * bins) - 1)
        start = max(0, min(bins - 1, start))
        end = max(0, min(bins - 1, end))

        for i in range(start, end + 1):
            hist[i] += 1
    return hist


def _char_center_top(ch, page_height):
    if "y0" in ch and "y1" in ch:
        y0 = float(ch.get("y0", 0.0))
        y1 = float(ch.get("y1", y0))
        center_pdf = (y0 + y1) / 2.0
        return page_height - center_pdf
    top = float(ch.get("top", 0.0))
    bottom = float(ch.get("bottom", top))
    return (top + bottom) / 2.0


def detect_column_separators(chars, page_width, bins=NUM_BINS):
    """
    Detecte des separateurs verticaux via minima locaux
    de l'histogramme.

    Retourne une liste de positions x (en points: 0..page_width)
    des séparateurs détectés, triée par ordre croissant.
    """
    if not chars or page_width <= 0:
        return []

    hist = _build_char_coverage_histogram(chars, page_width, bins=bins)
    smooth = _smooth_histogram(hist, window=11)
    if len(smooth) < 3:
        return []

    margin = int(bins * 0.08)
    threshold = _percentile(smooth, 0.20)
    max_level = max(smooth) if smooth else 0.0

    # find the local minimas candidates
    candidates = []
    for i in range(max(1, margin), min(bins - 1, bins - margin)):
        current = smooth[i]
        if current > threshold:
            continue
        if not (current <= smooth[i - 1] and current <= smooth[i + 1]):
            continue

        local_span = int(bins * 0.03)
        left = max(margin, i - local_span)
        right = min(bins - margin - 1, i + local_span)
        left_peak = max(smooth[left:i] or [current])
        right_peak = max(smooth[i + 1:right + 1] or [current])
        depth = min(left_peak, right_peak) - current

        if depth >= max(0.5, 0.05 * max_level):
            candidates.append(i)

    if not candidates:
        return []

    # Fusion des minima voisins: conserve le minimum le plus profond par groupe.
    min_distance = int(bins * 0.04)
    groups = []
    current_group = [candidates[0]]
    for idx in candidates[1:]:
        if idx - current_group[-1] <= min_distance:
            current_group.append(idx)
        else:
            groups.append(current_group)
            current_group = [idx]
    groups.append(current_group)

    chosen_bins = [min(group, key=lambda k: smooth[k]) for group in groups]
    chosen_bins.sort()

    return [float(((float(b) + 0.5) / float(bins)) * float(page_width)) for b in chosen_bins]


def detect_header_footer_boundaries(chars, page_height, bins=NUM_BINS):
    """Détecte les limites header/body/footer via minima locaux sur l'axe Y.

    Retour:
      (header_bottom_y, footer_top_y) en coordonnées top->bottom.
      Valeurs None si header/footer non détecté.
    """
    if not chars or page_height <= 0:
        return None, None

    hist = _build_char_coverage_histogram_vertical(chars, page_height, bins=bins)
    smooth = _smooth_histogram(hist, window=11)
    if len(smooth) < 3:
        return None, None

    threshold = _percentile(smooth, 0.20)
    max_level = max(smooth) if smooth else 0.0
    max_block_height = page_height * MAX_HEADER_FOOTER_RATIO

    candidates = []
    for i in range(1, bins - 1):
        current = smooth[i]
        if current > threshold:
            continue
        if not (current <= smooth[i - 1] and current <= smooth[i + 1]):
            continue

        local_span = int(bins * 0.03)
        left = max(0, i - local_span)
        right = min(bins - 1, i + local_span)
        left_peak = max(smooth[left:i] or [current])
        right_peak = max(smooth[i + 1:right + 1] or [current])
        depth = min(left_peak, right_peak) - current
        if depth >= max(0.5, 0.05 * max_level):
            y = ((i + 0.5) / bins) * page_height
            candidates.append((i, y))

    if not candidates:
        return None, None

    char_centers = [_char_center_top(ch, page_height) for ch in chars]

    header_bottom = None
    header_candidates = [y for _, y in candidates if 0.0 < y <= max_block_height]
    for y in sorted(header_candidates):
        top_count = sum(1 for c in char_centers if c <= y)
        body_count = sum(1 for c in char_centers if c > y)
        if top_count > 0 and body_count > 0:
            header_bottom = y
            break

    footer_top = None
    footer_candidates = [y for _, y in candidates if (page_height - max_block_height) <= y < page_height]
    for y in sorted(footer_candidates, reverse=True):
        bottom_count = sum(1 for c in char_centers if c >= y)
        body_count = sum(1 for c in char_centers if c < y)
        if bottom_count > 0 and body_count > 0:
            footer_top = y
            break

    if header_bottom is not None and footer_top is not None and header_bottom >= footer_top:
        return None, None

    return header_bottom, footer_top


def _extract_tables_and_chars(page):
    def _cell_text(value) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() == "nan":
            return ""
        return text

    def _md_cell(value: str) -> str:
        text = _cell_text(value)
        if not text:
            return ""
        # Préserve les retours utiles dans les cellules multi-lignes.
        text = re.sub(r"\n(?=\d\s)", "<br><br>", text, count=1)
        text = text.replace("\n", "<br>")
        return text

    def _looks_numeric(value: str) -> bool:
        text = _cell_text(value)
        if not text:
            return False
        return bool(re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", text))

    def _markdown_table_from_rows(rows: list[list]) -> str | None:
        if not rows:
            return None

        def _cell_lines(value) -> list[str]:
            text = _cell_text(value)
            if not text:
                return [""]
            lines = [re.sub(r"\s+", " ", part).strip() for part in text.splitlines()]
            lines = [line for line in lines if line or len(lines) == 1]
            return lines or [""]

        normalized_rows = [[_cell_lines(cell) for cell in row] for row in rows]
        width = max(len(row) for row in normalized_rows)
        if width == 0:
            return None

        padded_rows = [row + [[""]] * (width - len(row)) for row in normalized_rows]
        if len(padded_rows) < 2:
            return None

        header = padded_rows[0]
        data_rows = padded_rows[1:]

        align_right = []
        for col_idx in range(width):
            values = []
            for row in data_rows:
                for line in row[col_idx]:
                    if line:
                        values.append(line)
            align_right.append(bool(values) and all(_looks_numeric(value) for value in values))

        col_widths = [0] * width
        for row in padded_rows:
            for idx, cell in enumerate(row):
                for line in cell:
                    col_widths[idx] = max(col_widths[idx], len(line))
        col_widths = [max(3, col_widths[0])] + [max(3, w + 2) for w in col_widths[1:]]

        def _format_cell(cell: str, idx: int) -> str:
            if align_right[idx]:
                return cell.rjust(col_widths[idx])
            return cell.ljust(col_widths[idx])

        def _format_header_cell(cell: str, idx: int) -> str:
            return cell.ljust(col_widths[idx])

        separator = []
        for idx in range(width):
            dash_count = max(3, col_widths[idx])
            if align_right[idx]:
                separator.append("-" * (dash_count - 1) + ":")
            else:
                separator.append(":" + "-" * (dash_count - 1))

        lines = [
            # Header rows may span multiple physical lines per cell; render them first.
        ]
        header_height = max(len(cell) for cell in header)
        for line_idx in range(header_height):
            lines.append(
                "| "
                + " | ".join(
                    _format_header_cell(cell[line_idx] if line_idx < len(cell) else "", idx)
                    for idx, cell in enumerate(header)
                )
                + " |"
            )

        lines.append("| " + " | ".join(separator) + " |")

        for row in data_rows:
            row_height = max(len(cell) for cell in row)
            for line_idx in range(row_height):
                lines.append(
                    "| "
                    + " | ".join(
                        _format_cell(cell[line_idx] if line_idx < len(cell) else "", idx)
                        for idx, cell in enumerate(row)
                    )
                    + " |"
                )

        return "\n".join(lines)

    def _render_codebook_table(rows: list[list]) -> str | None:
        # Heuristique ciblée: le tableau CODEBOOK est extrait sur 8 colonnes,
        # dont 4 colonnes fantômes (vides/nan) qui cassent la structure attendue.
        if len(rows) < 4:
            return None
        first = rows[0] if rows and rows[0] else []
        if len(first) < 8:
            return None

        first_joined = " ".join(_cell_text(c) for c in first)
        if "BEZEICHNUNG" not in first_joined or "VARIABLE IM" not in first_joined:
            return None

        header_col1_parts = [_cell_text(rows[i][1]) for i in range(min(3, len(rows))) if len(rows[i]) > 1]
        header_col2_parts = [_cell_text(rows[i][4]) for i in range(min(3, len(rows))) if len(rows[i]) > 4]
        header_col3 = _cell_text(rows[0][6]) if len(rows[0]) > 6 else ""
        header_col4 = _cell_text(rows[0][7]) if len(rows[0]) > 7 else ""

        header_col1 = "<br>".join(part for part in header_col1_parts if part)
        header_col2 = " <br> ".join(part for part in header_col2_parts if part)
        if not (header_col1 and header_col2 and header_col3 and header_col4):
            return None

        lines = [
            f"| {header_col1} | {header_col2} | {header_col3} | {header_col4} |",
            "|-------|----------------|------------------|----------------------|",
        ]

        for row in rows[3:]:
            if not row or len(row) < 8:
                continue
            c1 = _md_cell(row[0])
            c2 = _md_cell(row[3])
            c3 = _md_cell(row[6])
            c4 = _md_cell(row[7])
            if not (c1 or c2 or c3 or c4):
                continue
            lines.append(f"| {c1} | {c2} | {c3} | {c4} |")

        return "\n".join(lines) if len(lines) > 1 else None

    filtered_page = page
    chars = list(filtered_page.chars)

    for table in page.find_tables():
        table_chars = page.crop(table.bbox).chars
        if not table_chars:
            continue

        first_table_char = table_chars[0]
        filtered_page = filtered_page.filter(
            lambda obj: get_bbox_overlap(obj_to_bbox(obj), table.bbox) is None
        )
        chars = list(filtered_page.chars)

        raw_rows = table.extract() or []
        custom_md = _render_codebook_table(raw_rows)
        if custom_md:
            chars.append(first_table_char | {"text": custom_md})
            continue

        if pd is not None:
            df = pd.DataFrame(raw_rows)
            if df.empty:
                continue
            df.columns = df.iloc[0]
            markdown = df.drop(0).to_markdown(index=False)
        else:
            markdown = _markdown_table_from_rows(raw_rows)
            if not markdown:
                continue
        chars.append(
            first_table_char
            | {
                "text": markdown,
                "is_markdown_block": True,
            }
        )

    return chars


def _extract_text_by_columns(chars, page_width):
    separators = detect_column_separators(chars, page_width, bins=NUM_BINS)
    if not separators:
        return extract_text(chars, layout=True, x_tolerance=TEXT_X_TOLERANCE)
    if len(separators) > 1 and min((b - a) for a, b in zip(separators, separators[1:])) < (page_width * 0.08):
        return extract_text(chars, layout=True, x_tolerance=TEXT_X_TOLERANCE)

    columns = [[] for _ in range(len(separators) + 1)]
    for ch in chars:
        center_x = (float(ch.get("x0", 0.0)) + float(ch.get("x1", 0.0))) / 2.0
        col_idx = bisect.bisect_right(separators, center_x)
        columns[col_idx].append(ch)

    texts = []
    for col_chars in columns:
        if not col_chars:
            continue
        ordered = sorted(col_chars, key=lambda c: (float(c.get("top", 0.0)), float(c.get("x0", 0.0))))
        col_text = extract_text(ordered, layout=True, x_tolerance=TEXT_X_TOLERANCE)
        if col_text and col_text.strip():
            texts.append(col_text)

    return "\n\n".join(texts)


def _extract_text_with_header_footer(chars, page_width, page_height):
    header_bottom, footer_top = detect_header_footer_boundaries(chars, page_height, bins=NUM_BINS)

    header_chars = []
    body_chars = []
    footer_chars = []

    for ch in chars:
        center_y = _char_center_top(ch, page_height)
        if header_bottom is not None and center_y <= header_bottom:
            header_chars.append(ch)
            continue
        if footer_top is not None and center_y >= footer_top:
            footer_chars.append(ch)
            continue
        body_chars.append(ch)

    header_text = ""
    if header_chars:
        header_sorted = sorted(header_chars, key=lambda c: (float(c.get("top", 0.0)), float(c.get("x0", 0.0))))
        header_text = extract_text(header_sorted, layout=True, x_tolerance=TEXT_X_TOLERANCE)
        if header_text:
            header_text = header_text.strip()

    body_text = _extract_text_by_columns(body_chars, page_width) if body_chars else ""
    if body_text:
        body_text = body_text.strip()

    footer_text = ""
    if footer_chars:
        footer_sorted = sorted(footer_chars, key=lambda c: (float(c.get("top", 0.0)), float(c.get("x0", 0.0))))
        footer_text = extract_text(footer_sorted, layout=True, x_tolerance=TEXT_X_TOLERANCE)
        if footer_text:
            footer_text = footer_text.strip()

    return header_text, body_text, footer_text


def _page_has_extracted_text(page_text: str) -> bool:
    if not page_text:
        return False
    stripped = re.sub(r"\s+", "", page_text)
    return len(stripped) >= 8


def _dehyphenate_text(text):
    """Supprime les césures de fin de ligne et conserve les traits lexicaux utiles."""
    if not text:
        return text

    # Cas OCR fréquent: "c'est--\ndire" ou "c'est--\n dire" -> "c'est--dire"
    text = re.sub(r"--\n(?=\s*[A-Za-zÀ-ÿ])", "--", text)

    # Gère aussi les retours avec indentation OCR: "mili-\n taire".
    pattern = re.compile(r"([A-Za-zÀ-ÿ']+)-\n\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-]*)")

    def repl(match):
        left = match.group(1)
        right = match.group(2)
        left_lower = left.lower()
        right_lower = right.lower()

        # Cas des nombres français composés : vingt-cinq, quarante-et-un...
        # On conserve le trait d'union quand les deux segments sont des tokens numériques.
        left_last_token = left_lower.split("-")[-1]
        if left_last_token in _FRENCH_NUMBER_TOKENS and right_lower in _FRENCH_NUMBER_TOKENS:
            return f"{left}-{right}"

        # Conserve le trait pour les composés attendus (contre-projet).
        if f"{left_lower}-{right_lower}" in _HYPHEN_EXCEPTIONS:
            return f"{left}-{right}"

        # Césure typographique standard: on retire le trait + saut de ligne.
        return f"{left}{right}"

    return pattern.sub(repl, text)


def _join_soft_wrapped_lines(text):
    """Recolle les fragments de phrase coupés en fin de ligne.

    Règle: si la ligne suivante est vide ou commence par des espaces,
    on ne recolle pas (nouveau paragraphe / bloc).

    Le recollement est effectué page par page, afin de conserver la numérotation des pages.
    """
    if not text:
        return text

    lines = text.split("\n")
    if not lines:
        return text

    out = []
    current = lines[0].rstrip()
    for nxt in lines[1:]:
        nxt_raw = nxt
        nxt_stripped = nxt_raw.strip()
        current_raw = current
        current_stripped = current_raw.strip()

        # Lignes appartenant à un tableau Markdown: jamais fusionner.
        if current_stripped.startswith("|") or nxt_stripped.startswith("|"):
            out.append(current)
            current = nxt_raw.rstrip()
            continue

        # Nouveau paragraphe/bloc: ligne vide, fin de phrase ou forte indentation.
        indent_len = len(nxt_raw) - len(nxt_raw.lstrip(" \t"))
        is_block_indent = indent_len >= 4
        if (
            not nxt_stripped
            or is_block_indent
            or current_raw.endswith((".", "!", "?", ":", ";"))
        ):
            out.append(current)
            current = nxt_raw.rstrip()
            continue

        # Recollement doux des lignes de phrase.
        if current_stripped:
            current = f"{current} {nxt_stripped}"
        else:
            current = nxt_stripped

    out.append(current)
    return "\n".join(out)


def _fix_intra_word_spaces(text):
    """Recoller des mots OCR parfois scindés en deux tokens (ex: "finance ment")."""
    if not text:
        return text

    suffixes = (
        "ment", "ments", "tion", "tions", "sion", "sions", "aire", "aires",
        "isme", "ismes", "able", "ables", "ique", "iques", "ance", "ances",
        "ence", "ences", "eur", "eurs", "euse", "euses", "if", "ifs", "ive", "ives",
    )
    suffix_pattern = "|".join(suffixes)
    return re.sub(
        rf"\b([A-Za-zÀ-ÿ]{{3,}})\s+({suffix_pattern})\b",
        r"\1\2",
        text,
    )


# ---------------------------------------------------------------------------
# Détection du numéro de page depuis le texte (header/footer)
# Copié et adapté depuis pdf_to_md_extractor.py
# ---------------------------------------------------------------------------

def _normalize_page_label(label: str) -> str:
    """Normalise un label de page: supprime les espaces et uniformise les tirets."""
    value = (label or "").strip()
    value = value.replace("–", "-")
    value = re.sub(r"\s*-\s*", "-", value)
    return value


def _next_page_label(prev_label: str, fallback: str) -> str:
    """Retourne le prochain label de page en incrémentant le dernier numéro du label précédent."""
    prev_nums = [int(x) for x in re.findall(r"\d+", prev_label or "")]
    if prev_nums:
        return str(prev_nums[-1] + 1)
    return _normalize_page_label(fallback)


def _detect_page_label_from_text(text: str, fallback: str) -> str:
    """Extrait le numéro de page depuis le texte d'une page (header/footer prioritaires).

    Cherche en priorité:
    1. Un nombre à 3-4 chiffres seul sur une ligne (parmi les 6 premières lignes non vides).
    2. Le motif «— 485 —» ou «PAGE 485» fréquent dans les headers/footers.
    Retourne *fallback* normalisé si rien n'est trouvé.
    """
    snippet_lines = [ln.strip() for ln in (text or "").splitlines()[:25] if ln.strip()]
    snippet = " ".join(snippet_lines)

    # Nombre seul sur une ligne (ex. numéro de folio centré)
    for ln in snippet_lines[:6]:
        m = re.match(r"^(\d{3,4})$", ln)
        if m:
            return _normalize_page_label(m.group(1))

    candidates = [
        (r"[—-]\s*(\d{1,4}(?:\s*[-–]\s*\d{1,4})?)\s*[—-]", True),
        (r"\b(\d{3,4})\s*[—-]\s*\d{1,2}\.?\s*[A-Za-zÀ-ÿ]+", True),
        (r"\b(?:Page|Seite|Pagina)\s*(\d{1,4}(?:\s*[-–]\s*\d{1,4})?)\b", False),
    ]
    for pattern, require_high_numbers in candidates:
        match = re.search(pattern, snippet, flags=re.IGNORECASE)
        if match:
            candidate = _normalize_page_label(match.group(1))
            nums = [int(x) for x in re.findall(r"\d+", candidate)]
            if len(nums) > 1:
                continue
            if require_high_numbers and nums and any(n < 100 for n in nums):
                continue
            return candidate
    return _normalize_page_label(fallback)


def _detect_page_label_from_header_footer(header_text: str, body_text: str, footer_text: str, prev_label: str) -> str:
    """Détecte le numéro de page depuis le header/footer d'une page.

    Utilise le même algorithme que _detect_page_label_from_text, en cherchant d'abord
    dans le header, puis dans le footer. Pour le body, on ne consulte que les 200 premiers
    et 200 derniers caractères pour éviter les faux positifs type "N°5-2022" au milieu
    du texte.

    Args:
        header_text: Texte du header extrait
        body_text: Texte du body extrait (sera tronqué aux extrêmités)
        footer_text: Texte du footer extraité
        prev_label: Numéro de page précédent (ou fallback initial)

    Returns:
        Le numéro de page détecté ou calculé.
    """
    # Prépare une version tronquée du body: cible les zones extrêmes
    # (début et fin), où les numéros de page sont plus plausibles.
    body_edges = ""
    if body_text:
        first_200 = body_text[:200]
        last_200 = body_text[-200:] if len(body_text) > 200 else ""
        body_edges = first_200 + (" " + last_200 if last_200 and last_200 != first_200 else "")

    # Cherche en priorité: header, puis footer, puis body (extrêmités seulement)
    for text in [header_text, footer_text, body_edges]:
        if not text:
            continue
            
        # Chercher rapidement sur les premières lignes
        snippet_lines = [ln.strip() for ln in text.splitlines()[:15] if ln.strip()]

        # Nombre seul sur une ligne
        for ln in snippet_lines[:6]:
            m = re.match(r"^(\d{1,4})$", ln)
            if m:
                return _normalize_page_label(m.group(1))

        # Motifs typiques de numéros de page
        snippet = " ".join(snippet_lines)
        candidates = [
            (r"[—-]\s*(\d{1,4})\s*[—-]", True),
            (r"\b(\d{3,4})\s*[—-]", True),
            (r"[—-]\s*(\d{3,4})\b", True),
            (r"\b(?:Page|Seite|Pagina)\s+(\d{1,4})\b", False),
        ]
        for pattern, require_high_numbers in candidates:
            match = re.search(pattern, snippet, flags=re.IGNORECASE)
            if match:
                candidate = _normalize_page_label(match.group(1))
                nums = [int(x) for x in re.findall(r"\d+", candidate)]
                if len(nums) == 1:
                    if require_high_numbers and nums[0] < 50:
                        continue
                    return candidate

    # Fallback: page précédente + 1
    if prev_label:
        return _next_page_label(prev_label, prev_label)
    return "1"


def _normalize_detected_page_label(prev_label: str, detected_label: str) -> str:
    """Normalise le label détecté et écarte les sauts numériques aberrants.

    Heuristique: si prev/candidate sont numériques et que l'écart est > 2,
    on considère la détection suspecte et on revient à prev+1.
    """
    prev = _normalize_page_label(prev_label)
    current = _normalize_page_label(detected_label)

    if re.fullmatch(r"\d+", prev) and re.fullmatch(r"\d+", current):
        prev_num = int(prev)
        current_num = int(current)
        if current_num - prev_num > 2:
            return str(prev_num + 1)

    return current


# ---------------------------------------------------------------------------
# Front matter YAML
# ---------------------------------------------------------------------------

def _norm_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _group_page_labels(page_labels: list[str]) -> str:
    """Regroupe les pages numériques consécutives (ex. 1-4, 10-12).

    Les labels non numériques sont conservés tels quels, dans l'ordre.
    """
    if not page_labels:
        return ""

    tokens: list[str] = []
    current_start: int | None = None
    current_end: int | None = None

    def _flush_current_range() -> None:
        nonlocal current_start, current_end
        if current_start is None or current_end is None:
            return
        if current_start == current_end:
            tokens.append(str(current_start))
        else:
            tokens.append(f"{current_start}-{current_end}")
        current_start = None
        current_end = None

    for raw in page_labels:
        label = _norm_ws(raw)
        if not re.fullmatch(r"\d+", label):
            _flush_current_range()
            if label:
                tokens.append(label)
            continue

        value = int(label)
        if current_start is None:
            current_start = value
            current_end = value
            continue

        if value == current_end + 1:
            current_end = value
        else:
            _flush_current_range()
            current_start = value
            current_end = value

    _flush_current_range()
    return ", ".join(tokens)


class FrontMatter:
    """Gère la génération du front matter YAML pour les extractions PDF."""

    FIELD_ORDER = [
        "titre",
        "source",
        "date_publication",
        "date_event",
        "date_extraction",
        "pages",
        "ocr_pages",
        "ocr_quality",
        "transformation_by",
        "language_distribution",
        "author",
    ]

    def __init__(self, meta: dict) -> None:
        self.meta = meta

    @staticmethod
    def _escape_yaml_value(value: str) -> str:
        if not value:
            return '""'
        escaped = value.replace('"', "'")
        return f'"{escaped}"'

    def build(self) -> str:
        lines = ["---"]
        for field in self.FIELD_ORDER:
            value = self.meta.get(field, "")
            if value is None:
                continue
            text_value = str(value)
            if not text_value.strip():
                continue
            lines.append(f"{field}: {self._escape_yaml_value(text_value)}")
        lines.append("---\n")
        return "\n".join(lines)


def _compute_language_distribution(text: str) -> str:
    if callable(_detect_language_distribution) and callable(_format_distribution):
        detected = _detect_language_distribution(text)
        return _format_distribution(detected)
    return "unknown:100"


def _format_ddmmyyyy(date_obj: datetime) -> str:
    return date_obj.strftime("%d.%m.%Y")


def _parse_ddmmyyyy(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%d.%m.%Y")
    except ValueError:
        return None


def _parse_pdf_creation_date(raw_value: object) -> str:
    """Parse PDF metadata creation date and return dd.MM.yyyy or empty string.

    Typical format: D:20160923092046+02'00'
    """
    if raw_value is None:
        return ""

    text = str(raw_value).strip()
    if not text:
        return ""

    # PDF spec style: D:YYYYMMDDHHmmSSOHH'mm'
    if text.startswith("D:"):
        text = text[2:]
    match = re.match(r"^(\d{4})(\d{2})(\d{2})", text)
    if match:
        year, month, day = map(int, match.groups())
        try:
            return _format_ddmmyyyy(datetime(year, month, day))
        except ValueError:
            return ""

    # ISO-like fallback.
    iso_candidate = text.replace("Z", "+00:00")
    try:
        return _format_ddmmyyyy(datetime.fromisoformat(iso_candidate))
    except ValueError:
        pass

    # Already formatted fallback.
    for pattern in (
        r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b",
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
    ):
        m = re.search(pattern, text)
        if not m:
            continue
        try:
            if pattern.startswith("\\b(\\d{1,2})"):
                day, month, year = map(int, m.groups())
            else:
                year, month, day = map(int, m.groups())
            return _format_ddmmyyyy(datetime(year, month, day))
        except ValueError:
            continue

    return ""


def _detect_content_date(text: str) -> str:
    """Detect a date mentioned in the document text (prefer beginning/end zones)."""
    if not text:
        return ""

    normalized = re.sub(r"\s+", " ", text)
    zone = (normalized[:4000] + " " + normalized[-4000:]).strip()
    if not zone:
        return ""

    # Numeric formats.
    for m in re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", zone):
        day, month, year = map(int, m.groups())
        try:
            return _format_ddmmyyyy(datetime(year, month, day))
        except ValueError:
            continue

    for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", zone):
        year, month, day = map(int, m.groups())
        try:
            return _format_ddmmyyyy(datetime(year, month, day))
        except ValueError:
            continue

    # Named month format (FR/DE).
    for m in re.finditer(r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\b", zone, flags=re.IGNORECASE):
        day = int(m.group(1))
        month_name = m.group(2).strip(" .").lower()
        year = int(m.group(3))
        month = _MONTHS_MAP.get(month_name)
        if month is None:
            continue
        try:
            return _format_ddmmyyyy(datetime(year, month, day))
        except ValueError:
            continue

    return ""


def _classify_document_kind(title: str, text: str) -> str:
    """Return one of: annonce, compte-rendu, autre."""
    haystack = (f"{title} {text[:2000]}").lower()
    if any(token in haystack for token in ("ordre du jour", "annonce", "convocation", "avis")):
        return "annonce"
    if any(token in haystack for token in ("procès-verbal", "proces-verbal", "pv", "compte-rendu", "séance")):
        return "compte-rendu"
    return "autre"


def _resolve_publication_and_date_events(pdf_metadata: dict | None, title: str, markdown_body: str) -> tuple[str, str]:
    """Resolve publication and event dates.

    - `date_publication`: metadata PDF prioritaire, sinon date détectée dans le contenu.
    - `date_event`: date détectée dans le contenu (si disponible).
    """
    pdf_metadata = pdf_metadata or {}
    metadata_raw = (
        pdf_metadata.get("CreationDate")
        or pdf_metadata.get("creationdate")
        or pdf_metadata.get("creation_date")
    )
    metadata_date = _parse_pdf_creation_date(metadata_raw)
    content_date = _detect_content_date(markdown_body)

    publication_date = metadata_date or content_date or ""
    date_event = content_date or ""
    return publication_date, date_event


def _extract_language_percentage(distribution: str, language: str) -> int:
    if not distribution:
        return 0

    for chunk in distribution.split(","):
        part = chunk.strip()
        if ":" not in part:
            continue
        lang, value = [x.strip().lower() for x in part.split(":", 1)]
        if lang != language.lower():
            continue
        match = re.search(r"\d+", value)
        if match:
            return int(match.group(0))
    return 0


def _to_repo_rel(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _register_markdown_source_document(md_path: Path, pdf_path: Path, language_distribution: str) -> None:
    if not _DB_AVAILABLE:
        return

    ner_status = 0 if _extract_language_percentage(language_distribution, "fr") < _FR_TRANSLATION_THRESHOLD else 1
    con = None
    try:
        con = _GET_DB_CONNECTION()
        result = _UPSERT_SOURCE(
            con,
            {
                "parent_path": _to_repo_rel(pdf_path),
                "path": _to_repo_rel(md_path),
                "file_name": md_path.name,
                "relative_path": md_path.name,
                "author": "skill " + SKILL_NAME,
                "ner_status": ner_status,
            },
        )
        if result.get("action") == "error":
            print(
                f"warn: echec enregistrement source_document pour {md_path}: {result.get('reason', 'inconnu')}",
                flush=True,
            )
    except Exception as exc:
        print(f"warn: echec enregistrement source_document pour {md_path}: {exc}", flush=True)
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


def _maybe_trigger_translation(md_path: Path, language_distribution: str) -> None:
    fr_pct = _extract_language_percentage(language_distribution, "fr")
    if fr_pct >= _FR_TRANSLATION_THRESHOLD:
        return

    if not _TRANSLATE_MD_PATH.exists():
        print(
            f"warn: traduction auto ignoree (script introuvable): {_TRANSLATE_MD_PATH}",
            flush=True,
        )
        return

    cmd = [
        sys.executable,
        "-u",
        str(_TRANSLATE_MD_PATH),
        "--input",
        str(md_path),
    ]
    try:
        subprocess.run(cmd, check=False)
        print(
            f"info: traduction auto lancee (fr:{fr_pct} < {_FR_TRANSLATION_THRESHOLD}) -> {md_path}",
            flush=True,
        )
    except Exception as exc:
        print(f"warn: echec lancement traduction auto: {exc}", flush=True)


def _build_pdf_frontmatter(
    pdf_path: Path,
    page_count: int,
    language_distribution: str,
    ocr_pages: int = 0,
    ocr_quality: float | None = None,
    date_publication: str = "",
    date_event: str = "",
) -> str:
    title = _norm_ws(pdf_path.stem.replace("_", " "))
    meta = {
        "titre": title,
        "source": str(pdf_path),
        "date_publication": date_publication,
        "date_event": date_event,
        "date_extraction": datetime.now().isoformat(),
        "pages": str(page_count),
        "ocr_pages": str(ocr_pages) if ocr_pages > 0 else "",
        "ocr_quality": f"{ocr_quality:.3f}" if ocr_quality is not None else "",
        "author": "skill " + SKILL_NAME,
        "transformation_by": "skill " + SKILL_NAME,
        "language_distribution": language_distribution or "unknown:100",
    }
    return FrontMatter(meta).build()


def extract_pdf_to_md(pdf_path: Path, md_path: Path | None = None, *, no_translate: bool = False) -> int:
    """Point d'entree public du skill: extrait un PDF en Markdown pagine.

    Retourne le nombre de sections `## Page ...` produites.
    """
    pdf_path = Path(pdf_path)
    md_path = Path(md_path) if md_path else pdf_path.with_suffix(".md")
    content = process_pdf(pdf_path, md_path=md_path, no_translate=no_translate)
    return len(re.findall(r"^## Page\s+", content, flags=re.MULTILINE))


def process_pdf(pdf_path, page_numbers=None, md_path=None, *, no_translate: bool = False, write_files:bool = True):
    all_text = []
    page_labels = []  # Liste pour conserver les numéros de pages détectés
    ocr_pages = 0
    md_path = Path(md_path) if md_path else Path(pdf_path).with_suffix(".md")

    with pdfplumber.open(pdf_path) as pdf:
        pdf_metadata = dict(pdf.metadata or {})

        # Sélection des pages physiques à extraire du PDF (API 1-based).
        if page_numbers is not None:
            if isinstance(page_numbers, (str, bytes)):
                raise TypeError("page_numbers doit être une liste/itérable d'entiers (pages physiques 1-based).")

            pages_with_idx = []
            for raw_page_num in page_numbers:
                page_num = int(raw_page_num)
                page_index = page_num - 1
                if page_index < 0 or page_index >= len(pdf.pages):
                    raise ValueError(f"page_numbers contient une page hors limites: {page_num} (1..{len(pdf.pages)})")
                pages_with_idx.append((page_num, pdf.pages[page_index]))
        else:
            pages_with_idx = list(enumerate(pdf.pages, 1))

        force_full_ocr = False
        force_reason = ""
        old_quality = 0.0
        new_quality = 0.0
        try:
            force_full_ocr, force_reason, old_quality, new_quality = _assess_ocr_replacement(
                Path(pdf_path),
                pages_with_idx,
                pdf_metadata,
            )
        except Exception as exc:
            force_full_ocr = False
            force_reason = f"ocr_assessment_error:{exc}"

        # if force_full_ocr:
        #     print(
        #         "info: remplacement OCR activé "
        #         f"(raison={force_reason}, old_quality={old_quality:.3f}, new_quality={new_quality:.3f})",
        #         flush=True,
        #     )

        prev_label = ""
        for _page_num, page in pages_with_idx:
            if force_full_ocr:
                label = _next_page_label(prev_label, str(_page_num)) if prev_label else str(_page_num)
                label = _normalize_page_label(label)
                prev_label = label
                page_labels.append(label)

                page_text = _ocr_text_from_page(Path(pdf_path), _page_num - 1)
                if page_text:
                    ocr_pages += 1
                else:
                    page_text = ""
            else:
                chars = _extract_tables_and_chars(page)
                table_blocks = [ch["text"] for ch in chars if ch.get("is_markdown_block")]
                chars = [ch for ch in chars if not ch.get("is_markdown_block")]

                # Extraction séparée des header, body, footer
                header_text, body_text, footer_text = _extract_text_with_header_footer(chars, page.width, page.height)

                # Détection du numéro de page à partir du header/footer
                label = _detect_page_label_from_header_footer(header_text, body_text, footer_text, prev_label)
                label = _normalize_detected_page_label(prev_label, label)
                prev_label = label
                page_labels.append(label)

                # Recomposer le texte de la page avec dehyphenation et recollement
                if len(header_text)>0:
                    header_text = f"\n[header]: # ({header_text})\n"
                if len(footer_text)>0:
                    footer_text = f"\n[footer]: # ({footer_text})\n"
                page_text_raw = "\n\n".join([p for p in [header_text, body_text, footer_text] if p])
                page_text_raw = _dehyphenate_text(page_text_raw)
                page_text = _join_soft_wrapped_lines(page_text_raw)
                page_text = _fix_intra_word_spaces(page_text)
                if table_blocks:
                    table_text = "\n\n".join(table_blocks)
                    page_text = "\n\n".join([p for p in [page_text, table_text] if p])

                if not _page_has_extracted_text(page_text):
                    ocr_text = _ocr_text_from_page(Path(pdf_path), _page_num - 1)
                    if ocr_text:
                        ocr_pages += 1
                        page_text = ocr_text

            all_text.append(f"## Page {label}\n\n{page_text or ''}")

    # Écrire la liste des numéros de pages en haut du contenu (format regroupé).
    pages_summary = "Pages détectées: " + _group_page_labels(page_labels)
    markdown_body = pages_summary + "\n\n" + "\n\n".join(all_text)
    language_distribution = _compute_language_distribution(markdown_body)
    date_publication, date_event = _resolve_publication_and_date_events(
        pdf_metadata,
        Path(pdf_path).stem,
        markdown_body,
    )
    selected_ocr_quality = new_quality if force_full_ocr else old_quality
    frontmatter = _build_pdf_frontmatter(
        Path(pdf_path),
        len(page_labels),
        language_distribution,
        ocr_pages=ocr_pages,
        ocr_quality=selected_ocr_quality,
        date_publication=date_publication,
        date_event=date_event,
    )
    content = frontmatter + markdown_body

    if write_files:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(content, encoding="utf-8")
        _register_markdown_source_document(md_path, Path(pdf_path), language_distribution)
        if not no_translate:
            _maybe_trigger_translation(md_path, language_distribution)

    return content


if __name__ == "__main__":
    # Path to your PDF file
    pdf_path = r"test/extrait-de-proces-verbal-1.pdf"
    #pdf_path = r"test/entree_en_vigueur_ro_43_375_1928-01-01.pdf"
    #pdf_path = r"test/Wikipédia_Réarmement_Allemagne_sous_le_Troisième_Reich.pdf"
    #pdf_path = r"test/message_conseil_federal_ff1918v349_20181201_10081845.pdf"
    extracted_text = process_pdf(pdf_path, [1], md_path=Path(pdf_path).with_suffix(".md"))
    print(extracted_text)
