#!/usr/bin/env python3
"""Download e-newspaperarchives.ch article pages to Markdown.

This script is intentionally separated from result-list extraction.
It consumes article URLs either from a previous JSON export or from direct
CLI arguments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.e-newspaperarchives.ch/?a=q"
DEFAULT_OUTPUT_DIR = Path("sources/enewspaper/articles")
_ROOT = Path(__file__).resolve().parents[4]
_DB_SCRIPTS_DIR = _ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
_DB_MODULE_PATH = _DB_SCRIPTS_DIR / "db.py"
get_db_connection = None
register_source_document = None
try:
    spec = importlib.util.spec_from_file_location("named_entities_db_for_enewspaper", _DB_MODULE_PATH)
    if spec and spec.loader:
        _db_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = _db_module
        spec.loader.exec_module(_db_module)
        get_db_connection = _db_module.get_connection
        register_source_document = _db_module.register_source_document
        _DB_AVAILABLE = True
    else:
        _DB_AVAILABLE = False
except Exception:
    _DB_AVAILABLE = False

_DETECT_LANG_PATH = _ROOT / ".agents" / "skills" / "translate-markdown" / "scripts" / "detect_markdown_language.py"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_CDP_CANDIDATES = (
    "http://127.0.0.1:9222",
    "http://127.0.0.1:9223",
    "http://127.0.0.1:9333",
)
DEFAULT_CDP_PORT = 9222
DEFAULT_CDP_STARTUP_TIMEOUT_SECONDS = 15.0
DEFAULT_CDP_STARTUP_POLL_SECONDS = 0.5
DEFAULT_CDP_PROFILE_DIRNAME = "playwright-fetch-articles-cdp-profile"

INITIAL_CHALLENGE_WAIT_SECONDS = 12.0
CHALLENGE_POLL_SECONDS = 5.0
CHALLENGE_MAX_WAIT_SECONDS = 600.0
CHALLENGE_CLEAR_STABLE_CHECKS = 2

# Marqueurs vérifiés uniquement dans le TITRE de la page.
# Les pages de challenge Cloudflare affichent toujours leur statut dans le titre
# ("Just a moment...", "Un instant...", "Cloudflare - Checking your browser...").
# Vérifier ces mots dans le corps de la page génère des faux positifs pour du
# contenu textuel normal (ex. "un instant" dans un journal français de 1919).
BLOCK_MARKERS_TITLE = (
    "just a moment",
    "un instant",
    "verification de securite",
    "verificacion de seguridad",
    "security verification",
    "are you human",
    "cloudflare",
)

# Sélecteurs DOM spécifiques aux pages de challenge Cloudflare/Turnstile.
# Utilisés comme signal supplémentaire indépendant du texte.
BLOCK_DOM_SELECTORS = (
    "#challenge-form",
    "#challenge-running",
    ".cf-challenge-running",
    ".cf-browser-verification",
    "input[name='cf_captcha_kind']",
)

# Marqueurs de contenu temporaire observés quand l'article n'est pas encore prêt.
LOADING_TEXT_MARKERS = (
    "texte en chargement",
    "en chargement",
)

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


def _load_language_detection_functions():
    if not _DETECT_LANG_PATH.exists():
        return None, None

    module_name = "detect_markdown_language_shared_for_enewspaper"
    spec = importlib.util.spec_from_file_location(module_name, _DETECT_LANG_PATH)
    if spec is None or spec.loader is None:
        return None, None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, "detect_language_distribution", None), getattr(module, "format_distribution", None)


_detect_language_distribution, _format_distribution = _load_language_detection_functions()


@dataclass
class DownloadedArticle:
    article_url: str
    file_path: Optional[str] = None
    blocked: bool = False
    error: Optional[str] = None


@dataclass
class BrowserSession:
    browser: Any
    context: Any
    cdp_endpoint: str
    owns_browser: bool = False
    owns_context: bool = False
    launched_process: Optional[subprocess.Popen] = None


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _clean_extracted_text(text: str) -> str:
    """Supprime les blocs d'interface non pertinents du texte OCR extrait."""
    cleaned = html.unescape(text or "")

    junk_patterns = (
        r"\bTutoriel\b",
        r"https?://www\.e-newspaperarchives\.ch/\?a=d&d=\S+",
        r"\bEdition\s+PDF\s*\([^)]*\)",
        r"\bEdition\s+Article\b",
        r"\bURL\b\s*:?\s*https?://\S+",
        r"\bU\s*R\s*L\s*[:：]\s*",
        r"\[\s*Citer\s+l[’']article\s*\]",
        r"\bCommentaires\s*\(\s*\d+\s*\)",
        r"\bTags\s*\(\s*\d+\s*\)",
        r"\bTexte\b",
        r"Pourquoi\s+ce(?:\s+texte)?\s+contient-il\s+des\s+erreurs\??\s*Corriger\s+ce(?:\s+texte)?",
        r"Pourquoi\s+ce\s+texte\s+contient-il\s+des\s+erreurs\?",
        r"Corriger\s+ce\s+texte",
        r"Annoncer\s+une\s+correction\s+suspecte",
        r"\bContributeurs\s*:\s*[A-Za-zÀ-ÿ'’\- ]{2,100}",
        r"\bCopier\s+le\s+permalien\s+pour\s+cet\s+article\.?(?=\s|$)",
        (
            r"\[\s*Citer\s+l[’']article\s*\]\s*"
            #r"Commentaires\s*\(\s*0\s*\)\s*"
            #r"Tags\s*\(\s*0\s*\)\s*"
            r"Texte\s*"
            r"Pourquoi\s+ce\s+texte\s+contient-il\s+des\s+erreurs\?\s*"
            r"Corriger\s+ce\s+texte\s*"
            r"Annoncer\s+une\s+correction\s+suspecte"
        ),
    )

    for pattern in junk_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    cleaned = _dehyphenate_text(cleaned)
    cleaned = _join_soft_wrapped_lines(cleaned)
    cleaned = _fix_intra_word_spaces(cleaned)

    return _norm_ws(cleaned)


def _dehyphenate_text(text: str) -> str:
    """Supprime les césures de fin de ligne et conserve les traits lexicaux utiles."""
    if not text:
        return text

    text = re.sub(r"--\n(?=\s*[A-Za-zÀ-ÿ])", "--", text)
    pattern = re.compile(r"([A-Za-zÀ-ÿ']+)-\n\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-]*)")

    def repl(match):
        left = match.group(1)
        right = match.group(2)
        left_lower = left.lower()
        right_lower = right.lower()

        left_last_token = left_lower.split("-")[-1]
        if left_last_token in _FRENCH_NUMBER_TOKENS and right_lower in _FRENCH_NUMBER_TOKENS:
            return f"{left}-{right}"

        if f"{left_lower}-{right_lower}" in _HYPHEN_EXCEPTIONS:
            return f"{left}-{right}"

        return f"{left}{right}"

    return pattern.sub(repl, text)


def _join_soft_wrapped_lines(text: str) -> str:
    """Recolle les fragments de phrase coupés en fin de ligne."""
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

        if current_stripped.startswith("|") or nxt_stripped.startswith("|"):
            out.append(current)
            current = nxt_raw.rstrip()
            continue

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

        if current_stripped:
            current = f"{current} {nxt_stripped}"
        else:
            current = nxt_stripped

    out.append(current)
    return "\n".join(out)


def _fix_intra_word_spaces(text: str) -> str:
    """Recoller des mots OCR parfois scindés en deux tokens."""
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


def _looks_like_loading_placeholder(text: str) -> bool:
    lowered = _norm_ws(text).lower()
    return any(marker in lowered for marker in LOADING_TEXT_MARKERS)


def _yaml_escape(text: Optional[str]) -> str:
    return _norm_ws(text or "").replace('"', "'")


def _compute_language_distribution(text: str) -> str:
    if callable(_detect_language_distribution) and callable(_format_distribution):
        detected = _detect_language_distribution(text)
        return _format_distribution(detected)
    return "unknown:100"


def _ner_status_from_language_distribution(language_distribution: str) -> int:
    """Retourne 1 si le français dépasse 90%, sinon 0."""
    dist = _norm_ws(language_distribution).lower()
    if not dist:
        return 0

    for part in re.split(r"[,;]", dist):
        chunk = _norm_ws(part)
        if not chunk or ":" not in chunk:
            continue
        lang, value = chunk.split(":", 1)
        if _norm_ws(lang) != "fr":
            continue

        try:
            fr_pct = float(_norm_ws(value).replace("%", "").replace(",", "."))
        except ValueError:
            return 0

        return 1 if fr_pct > 90.0 else 0

    return 0


def _extract_publication_date_from_url(article_url: str) -> str:
    """Extrait la date de publication depuis le paramètre d=... de l'URL.

    Exemple: d=LNS19160309-01.2.12.1.6 -> "9 mars 1916"
    """
    parsed = urlparse(article_url or "")
    raw = ""
    for key in ("d", "docid", "id"):
        values = parse_qs(parsed.query).get(key)
        if values:
            raw = _norm_ws(values[0])
            if raw:
                break

    m = re.search(r"(\d{8})", raw)
    if not m:
        return ""

    yyyymmdd = m.group(1)
    year = int(yyyymmdd[0:4])
    month = int(yyyymmdd[4:6])
    day = int(yyyymmdd[6:8])

    months = {
        1: "janvier",
        2: "février",
        3: "mars",
        4: "avril",
        5: "mai",
        6: "juin",
        7: "juillet",
        8: "août",
        9: "septembre",
        10: "octobre",
        11: "novembre",
        12: "décembre",
    }
    month_label = months.get(month)
    if not month_label:
        return ""

    return f"{day} {month_label} {year}"


def _extract_publication_date_iso_from_url(article_url: str) -> str:
    """Extrait la date de publication au format ISO yyyy-MM-dd depuis l'URL."""
    parsed = urlparse(article_url or "")
    raw = ""
    for key in ("d", "docid", "id"):
        values = parse_qs(parsed.query).get(key)
        if values:
            raw = _norm_ws(values[0])
            if raw:
                break

    m = re.search(r"(\d{8})", raw)
    if not m:
        return ""

    yyyymmdd = m.group(1)
    return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _extract_journal_from_page_title(page_title: str, extracted_text: str) -> str:
    title = _norm_ws(page_title or "")
    if title:
        m = re.match(r"^(.*?)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}\s+[—-]", title)
        if m:
            return _norm_ws(m.group(1))

    # Fallback: début du texte OCR avant la première virgule.
    first_chunk = _norm_ws((extracted_text or "")[:220])
    if "," in first_chunk:
        return _norm_ws(first_chunk.split(",", 1)[0])
    return ""


def _extract_article_title_from_text(extracted_text: str, journal: str, date_publication: str) -> str:
    text = _norm_ws(extracted_text or "")
    if not text:
        return ""

    # Nettoie le préfixe journal/date classique.
    prefix_pattern = (
        rf"^{re.escape(journal)}\s*,?\s*"
        rf"(?:Volume\s*\d+\s*,?\s*)?"
        rf"(?:Num[ée]ro\s*\d+\s*,?\s*)?"
        rf"{re.escape(date_publication)}\s*"
    )
    text = re.sub(prefix_pattern, "", text, flags=re.IGNORECASE)

    # OCR parfois redondant: retire un éventuel préfixe journal restant.
    text = re.sub(rf"^{re.escape(journal)}\s*,?\s*", "", text, flags=re.IGNORECASE)

    # Coupe avant les marqueurs de corps d'article.
    split_markers = (
        "(Service spécial)",
        "Séance du",
        "Présidence de",
        "Page 1",
        "Page 2",
        "Page 3",
    )
    for marker in split_markers:
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
            break

    # Coupe au premier signe de phrase fort.
    for sep in (". ", "! ", "? "):
        idx = text.find(sep)
        if idx > 0:
            text = text[:idx]
            break

    candidate = _norm_ws(text).strip('"«»')
    if not candidate:
        return ""

    # Limite de sécurité pour éviter de prendre un trop long segment OCR.
    words = candidate.split()
    if len(words) > 18:
        candidate = " ".join(words[:18])

    return _norm_ws(candidate)


def _build_citation(title_article: str, journal: str, date_publication: str, article_url: str) -> str:
    title = _norm_ws(title_article or "Article")
    journal_norm = _norm_ws(journal or "Journal inconnu")
    date_pub = _norm_ws(date_publication or "date inconnue")
    url = _norm_ws(article_url or "")
    if url and not url.endswith("."):
        url = url + "."
    return f"{title}, {journal_norm} ({date_pub}), {url}".strip()


def _slugify(value: str) -> str:
    value = _norm_ws(value).lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "article"


def _article_id_from_url(url: str, fallback_index: int) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    raw_id = ""
    for key in ("d", "docid", "id"):
        values = qs.get(key)
        if values and _norm_ws(values[0]):
            raw_id = _norm_ws(values[0])
            break
    if not raw_id:
        raw_id = f"article_{fallback_index:04d}"
    return _slugify(raw_id)


def _register_article_in_db(
    *,
    article_url: str,
    article_path: Path,
    page_title: str,
    article_title: str,
    article_text: str,
    article_id: str,
) -> None:
    if not _DB_AVAILABLE:
        return

    date_publication = _extract_publication_date_iso_from_url(article_url) or "0000-00-00"
    journal = _extract_journal_from_page_title(page_title, article_text)
    title_article = _norm_ws(article_title) or _extract_article_title_from_text(
        article_text,
        journal,
        _extract_publication_date_from_url(article_url),
    )
    display_title = title_article or journal or f"Article e-newspaper {article_id}"
    language_distribution = _compute_language_distribution(article_text)
    ner_status = _ner_status_from_language_distribution(language_distribution)

    try:
        con = get_db_connection()
    except Exception as exc:
        print(f"[WARN] SQLite indisponible pour {article_path.name}: {exc}")
        return

    try:
        result = register_source_document(
            con,
            origin_path=article_path,
            identifiant_source=f"SRC-ENEWSPAPER-{article_id.upper()}",
            titre=display_title,
            url=article_url,
            auteurs=[journal] if journal else [],
            langues=language_distribution,
            type_source="primaire",
            nombre_pages=1,
            categorie="presse",
            extrait_brut=_norm_ws(article_text)[:500],
            date_publication=date_publication,
            ner_status=ner_status,
        )
        if result.get("action") == "error":
            print(f"[WARN] Insertion SQLite ignorée pour {article_path.name}: {result.get('reason', 'erreur inconnue')}")
    finally:
        con.close()


def _is_blocked(title: str, body_text: str) -> bool:
    """Détecte une page de challenge Cloudflare/Turnstile.

    On vérifie uniquement le TITRE de la page avec les marqueurs textuels.
    Le corps de la page n'est pas utilisé pour cette détection afin d'éviter
    les faux positifs sur du contenu textuel normal (ex. "un instant" dans un
    journal français).
    """
    title_lower = _norm_ws(title).lower()
    return any(marker in title_lower for marker in BLOCK_MARKERS_TITLE)


def _has_challenge_dom(page) -> bool:
    """Vérifie la présence d'éléments DOM propres aux challenges Cloudflare."""
    try:
        for selector in BLOCK_DOM_SELECTORS:
            if page.query_selector(selector):
                return True
    except Exception:
        pass
    return False


def _probe_cdp_endpoint(base_url: str) -> str | None:
    candidate = base_url.rstrip("/")
    try:
        with urlopen(f"{candidate}/json/version", timeout=1.5) as response:
            data = json.load(response)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None

    websocket_url = data.get("webSocketDebuggerUrl")
    return websocket_url or candidate


def _discover_cdp_endpoint(explicit: str | None) -> str | None:
    candidates: list[str] = []

    for raw in (
        explicit,
        os.environ.get("PLAYWRIGHT_MCP_CDP_URL"),
        os.environ.get("PLAYWRIGHT_CDP_URL"),
    ):
        if raw and raw not in candidates:
            candidates.append(raw)

    for candidate in DEFAULT_CDP_CANDIDATES:
        if candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        resolved = _probe_cdp_endpoint(candidate)
        if resolved:
            return resolved

    return None


def _extract_cdp_port(explicit_cdp_url: str | None) -> int:
    if explicit_cdp_url:
        parsed = urlparse(explicit_cdp_url)
        if parsed.port:
            return parsed.port
    return DEFAULT_CDP_PORT


def _can_launch_local_browser_for_cdp(explicit_cdp_url: str | None) -> bool:
    if not explicit_cdp_url:
        return True
    parsed = urlparse(explicit_cdp_url)
    host = (parsed.hostname or "").lower()
    return host in ("", "127.0.0.1", "localhost")


def _chromium_revision_key(path: Path) -> int:
    match = re.search(r"chromium-(\d+)", path.name)
    return int(match.group(1)) if match else -1


def _candidate_chromium_executables() -> list[Path]:
    candidates: list[Path] = []

    for env_var in ("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "PLAYWRIGHT_CHROME_EXECUTABLE", "CHROME_PATH"):
        raw = os.environ.get(env_var)
        if raw:
            candidates.append(Path(raw))

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        ms_playwright_dir = Path(local_app_data) / "ms-playwright"
        if ms_playwright_dir.exists():
            chromium_dirs = sorted(ms_playwright_dir.glob("chromium-*"), key=_chromium_revision_key, reverse=True)
            for chromium_dir in chromium_dirs:
                candidates.append(chromium_dir / "chrome-win64" / "chrome.exe")
                candidates.append(chromium_dir / "chrome-win" / "chrome.exe")

    for raw in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Chromium\Application\chrome.exe",
        r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
    ):
        candidates.append(Path(raw))

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)

    return unique_candidates


def _find_chromium_executable() -> Path | None:
    for candidate in _candidate_chromium_executables():
        if candidate.exists():
            return candidate
    return None


def _wait_for_cdp_endpoint(base_url: str, timeout_seconds: float = DEFAULT_CDP_STARTUP_TIMEOUT_SECONDS) -> str | None:
    deadline = time.monotonic() + max(0.5, timeout_seconds)
    while time.monotonic() < deadline:
        resolved = _probe_cdp_endpoint(base_url)
        if resolved:
            return resolved
        time.sleep(DEFAULT_CDP_STARTUP_POLL_SECONDS)
    return None


def _launch_local_chromium_for_cdp(explicit_cdp_url: str | None) -> tuple[subprocess.Popen, str]:
    if not _can_launch_local_browser_for_cdp(explicit_cdp_url):
        raise RuntimeError(
            "L'endpoint CDP fourni est distant et n'est pas joignable; "
            "le script ne peut pas lancer automatiquement un navigateur sur cet hote."
        )

    executable = _find_chromium_executable()
    if not executable:
        raise RuntimeError("Impossible de trouver un executable Chromium/Chrome local pour lancer le mode CDP.")

    cdp_port = _extract_cdp_port(explicit_cdp_url)
    base_url = f"http://127.0.0.1:{cdp_port}"
    user_data_dir = Path(os.environ.get("TEMP", ".")) / DEFAULT_CDP_PROFILE_DIRNAME
    user_data_dir.mkdir(parents=True, exist_ok=True)

    process = subprocess.Popen(
        [
            str(executable),
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    resolved_endpoint = _wait_for_cdp_endpoint(base_url)
    if resolved_endpoint:
        return process, resolved_endpoint

    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass

    raise RuntimeError(f"Le navigateur a ete lance, mais l'endpoint CDP {base_url} n'est pas devenu joignable.")


def _terminate_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return

    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
            process.wait(timeout=5)
        except Exception:
            pass


def _connect_browser_context_over_cdp(playwright, explicit_cdp_url: str | None):
    resolved_endpoint = _discover_cdp_endpoint(explicit_cdp_url)
    launched_process: subprocess.Popen | None = None
    owns_browser = False

    if not resolved_endpoint:
        launched_process, resolved_endpoint = _launch_local_chromium_for_cdp(explicit_cdp_url)
        owns_browser = True

    try:
        browser = playwright.chromium.connect_over_cdp(resolved_endpoint)
    except Exception:
        _terminate_process(launched_process)
        raise

    owns_context = False
    context = browser.contexts[0] if browser.contexts else None
    if context is None:
        context = browser.new_context(user_agent=DEFAULT_USER_AGENT)
        owns_context = True

    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return BrowserSession(
        browser=browser,
        context=context,
        cdp_endpoint=resolved_endpoint,
        owns_browser=owns_browser,
        owns_context=owns_context,
        launched_process=launched_process,
    )


def _cleanup_browser_session(session: BrowserSession, page=None) -> None:
    if page is not None:
        try:
            page.close()
        except Exception:
            pass

    if session.owns_context:
        try:
            session.context.close()
        except Exception:
            pass

    if session.owns_browser:
        try:
            session.browser.close()
        except Exception:
            pass
        finally:
            _terminate_process(session.launched_process)


def _wait_for_ready_or_block(page, timeout_ms: int = 20000) -> None:
    try:
        page.wait_for_function(
            """
            () => {
              const title = (document.title || '').toLowerCase();
              const blocked = title.includes('just a moment') ||
                              title.includes('un instant') ||
                              title.includes('security verification') ||
                              title.includes('cloudflare') ||
                              !!document.querySelector('#challenge-form, #challenge-running, .cf-challenge-running');
              const hasMainContent = !!document.querySelector('main, article, #content, .articleText, .ocrText');
              return blocked || hasMainContent;
            }
            """,
            timeout=timeout_ms,
        )
    except Exception:
        pass


def _wait_passively_for_challenge_clear(
    page,
    *,
    poll_seconds: float = CHALLENGE_POLL_SECONDS,
    max_wait_seconds: float = CHALLENGE_MAX_WAIT_SECONDS,
    stable_checks: int = CHALLENGE_CLEAR_STABLE_CHECKS,
) -> bool:
    elapsed = 0.0
    poll_ms = int(max(1.0, poll_seconds) * 1000)
    clear_streak = 0

    while elapsed <= max_wait_seconds:
        try:
            title = page.title()
        except Exception as exc:
            msg = str(exc).lower()
            if "execution context was destroyed" in msg or "most likely because of a navigation" in msg:
                clear_streak = 0
                page.wait_for_timeout(poll_ms)
                elapsed += poll_seconds
                continue
            print(f"[WARN] Navigation interrompue pendant l'attente du challenge: {exc}")
            return False

        if not (_is_blocked(title, "") or _has_challenge_dom(page)):
            clear_streak += 1
            if clear_streak >= max(1, stable_checks):
                return True
        else:
            clear_streak = 0

        page.wait_for_timeout(poll_ms)
        elapsed += poll_seconds

    return False


def _render_article_markdown(article_url: str, page_title: str, extracted_text: str, article_title: str = "") -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = dt.datetime.now().strftime("%Y-%m-%d")
    clean_title = _norm_ws(page_title)
    title = clean_title or "Article e-newspaperarchives.ch"
    date_publication = _extract_publication_date_iso_from_url(article_url)
    date_publication_display = _extract_publication_date_from_url(article_url)
    journal = _extract_journal_from_page_title(page_title, extracted_text)
    title_article = _norm_ws(article_title) or _extract_article_title_from_text(extracted_text, journal, date_publication_display)
    citation = _build_citation(title_article, journal, date_publication_display, article_url)
    article_author = journal or "Journal inconnu"
    language_distribution = _compute_language_distribution(extracted_text)
    lines = [
        "---",
        f'title: "{_yaml_escape(title_article)}"',
        f'author: "{_yaml_escape(article_author)}"',
        f'date_publication: "{_yaml_escape(date_publication)}"',
        f'citation: "{_yaml_escape(citation)}"',
        f'language_distribution: "{_yaml_escape(language_distribution)}"',
        'transformation_by: "skill fetch-enewspaper-article-content"',
        f'date_consultation: "{today}"',
        "sources:",
        f'  - "{_yaml_escape(article_url)}"',
        "---",
        "",
        "# Article e-newspaperarchives.ch",
        "",
        f"- URL de l'article: [Lien]({article_url})",
        f"- Date de collecte: `{now}`",
        f"- Titre de page: `{clean_title}`",
        "",
        "## Texte extrait",
        "",
        extracted_text or "(Aucun texte exploitable extrait automatiquement)",
        "",
    ]
    return "\n".join(lines)


def _extract_article_text_once(page) -> str:
    return page.evaluate(
        r"""
        () => {
          const keepLines = (s) => (s || '').replace(/\r/g, '').trim();
          const selectors = [
            '#articleText',
            '.articleText',
            '.ocrText',
            '.article-body',
            '#content',
            'main',
            'article'
          ];

          let best = '';
          for (const selector of selectors) {
            const nodes = Array.from(document.querySelectorAll(selector));
            for (const node of nodes) {
              const txt = keepLines(node.innerText || node.textContent || '');
              if (txt.length > best.length) {
                best = txt;
              }
            }
          }

          if (!best) {
            best = keepLines(document.body?.innerText || '');
          }

          return best;
        }
        """
    )


def _extract_article_title_once(page) -> str:
    """Extrait le titre d'article depuis le bloc dédié de la page e-newspaper."""
    try:
        title = page.evaluate(
            r"""
            () => {
              const node = document.querySelector('#sectionleveltabtitlearea');
              if (!node) return '';
              return (node.innerText || node.textContent || '').replace(/\r/g, '').trim();
            }
            """
        )
    except Exception:
        return ""
    return _norm_ws(title or "")


def _extract_article_text(page) -> str:
    # Certains articles restent brièvement sur "Texte En chargement…" alors que
    # le DOM principal est déjà présent. On réessaie quelques fois avant de figer.
    last_cleaned = ""
    for attempt in range(6):
        extracted = _extract_article_text_once(page)
        cleaned = _clean_extracted_text(extracted or "")
        last_cleaned = cleaned

        if cleaned and not _looks_like_loading_placeholder(cleaned):
            return cleaned

        if attempt < 5:
            page.wait_for_timeout(1500)

    return last_cleaned


def _load_article_urls_from_json(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[str] = []

    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    candidate = _norm_ws(str(item.get("article_url") or ""))
                    if candidate:
                        out.append(candidate)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                candidate = _norm_ws(item)
            elif isinstance(item, dict):
                candidate = _norm_ws(str(item.get("article_url") or ""))
            else:
                candidate = ""
            if candidate:
                out.append(candidate)

    return out


def _dedupe_urls(urls: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for url in urls:
        key = _norm_ws(url)
        if not key:
            continue
        key_l = key.lower()
        if key_l in seen:
            continue
        seen.add(key_l)
        out.append(key)
    return out


def _download_articles(
    article_urls: list[str],
    output_dir: Path,
    wait_time: float,
    pause_on_challenge: bool,
    max_articles: Optional[int],
    cdp_url: Optional[str],
) -> list[DownloadedArticle]:
    if not article_urls:
        return []

    limit = len(article_urls)
    if max_articles is not None:
        limit = max(0, min(limit, max_articles))

    selected_urls = article_urls[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[DownloadedArticle] = []

    with sync_playwright() as p:
        session = _connect_browser_context_over_cdp(p, cdp_url)
        print(f"[INFO] CDP endpoint utilise: {session.cdp_endpoint}")
        page = session.context.new_page()
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=90000)
            initial_wait = max(float(wait_time) * 3.0, INITIAL_CHALLENGE_WAIT_SECONDS)
            page.wait_for_timeout(int(initial_wait * 1000))
            _wait_for_ready_or_block(page)

            warmup_blocked = _is_blocked(page.title(), "") or _has_challenge_dom(page)
            if warmup_blocked and pause_on_challenge:
                print("[INFO] Challenge detecte avant telechargement des articles. Attente passive en cours...")
                warmup_blocked = not _wait_passively_for_challenge_clear(page)

            if warmup_blocked:
                return [
                    DownloadedArticle(
                        article_url=url,
                        blocked=True,
                        error="Challenge Cloudflare detecte avant telechargement des articles.",
                    )
                    for url in selected_urls
                ]

            for idx, article_url in enumerate(selected_urls, start=1):
                blocked = False
                error: Optional[str] = None
                file_path: Optional[str] = None

                try:
                    page.goto(article_url, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(int(wait_time * 1000))
                    _wait_for_ready_or_block(page)

                    blocked = _is_blocked(page.title(), "") or _has_challenge_dom(page)
                    if blocked and pause_on_challenge:
                        print(f"[INFO] Challenge detecte sur article {idx}/{len(selected_urls)}. Attente passive en cours...")
                        blocked = not _wait_passively_for_challenge_clear(page)

                    if blocked:
                        error = "Challenge Cloudflare detecte pendant le telechargement de l'article."
                    else:
                        article_text = _extract_article_text(page)
                        article_title = _extract_article_title_once(page)
                        article_id = _article_id_from_url(article_url, idx)
                        article_path = output_dir / f"{idx:04d}_{article_id}.md"
                        article_md = _render_article_markdown(
                            article_url,
                            page.title(),
                            article_text,
                            article_title=article_title,
                        )
                        article_path.write_text(article_md, encoding="utf-8")
                        _register_article_in_db(
                            article_url=article_url,
                            article_path=article_path,
                            page_title=page.title(),
                            article_title=article_title,
                            article_text=article_text,
                            article_id=article_id,
                        )
                        file_path = str(article_path)
                except Exception as exc:
                    error = str(exc)

                downloaded.append(
                    DownloadedArticle(
                        article_url=article_url,
                        file_path=file_path,
                        blocked=blocked,
                        error=error,
                    )
                )
        finally:
            _cleanup_browser_session(session, page)

    return downloaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download e-newspaperarchives article pages")
    parser.add_argument("--input-json", type=Path, help="JSON file from enewspaper_fetch_results.py")
    parser.add_argument("--article-url", action="append", default=[], help="Single article URL (repeatable)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--wait-time", type=float, default=3.5, help="Wait time after each page load")
    parser.add_argument("--pause-on-challenge", action="store_true", help="Pause for manual Turnstile solve")
    parser.add_argument("--cdp-url", help="CDP endpoint URL (ex: http://127.0.0.1:9222)")
    parser.add_argument("--max-articles", type=int, help="Maximum number of article pages to download")
    parser.add_argument("--dry-run", action="store_true", help="Show planned run without downloading")
    parser.add_argument("--verbose", action="store_true", help="Affiche le détail complet des articles téléchargés")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    urls: list[str] = []
    if args.input_json:
        try:
            urls.extend(_load_article_urls_from_json(args.input_json))
        except Exception as exc:
            print(f"[ERROR] Impossible de lire {args.input_json}: {exc}")
            return 2

    urls.extend(_norm_ws(url) for url in args.article_url)
    urls = _dedupe_urls(urls)

    if not urls:
        print("[ERROR] Aucune URL d'article fournie. Utilisez --input-json ou --article-url.")
        return 2

    planned_total = len(urls) if args.max_articles is None else max(0, min(len(urls), args.max_articles))

    if args.dry_run:
        print(f"[DRY-RUN] Input JSON: {args.input_json or '(none)'}")
        print(f"[DRY-RUN] URLs uniques detectees: {len(urls)}")
        print(f"[DRY-RUN] URLs prevues: {planned_total}")
        print(f"[DRY-RUN] Output directory: {args.output_dir}")
        print(f"[DRY-RUN] CDP URL: {args.cdp_url or '(auto)'}")
        print(f"[DRY-RUN] Pause on challenge: {args.pause_on_challenge}")
        return 0

    downloaded = _download_articles(
        article_urls=urls,
        output_dir=args.output_dir,
        wait_time=args.wait_time,
        pause_on_challenge=args.pause_on_challenge,
        max_articles=args.max_articles,
        cdp_url=args.cdp_url,
    )

    total_downloaded = sum(1 for item in downloaded if item.file_path)
    total_blocked = sum(1 for item in downloaded if item.blocked)

    if args.verbose:
        summary_output: Optional[str] = None
        if planned_total > 1:
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_path = args.output_dir / f"download_articles_summary_{timestamp}.json"
            args.output_dir.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(
                    {
                        "downloaded_articles": [asdict(item) for item in downloaded],
                        "total_requested": planned_total,
                        "total_downloaded": total_downloaded,
                        "total_blocked": total_blocked,
                        "generated_at": dt.datetime.now().isoformat(),
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary_output = str(summary_path)

        print(
            json.dumps(
                {
                    "total_requested": planned_total,
                    "total_downloaded": total_downloaded,
                    "total_blocked": total_blocked,
                    "summary_output": summary_output,
                    "timestamp": dt.datetime.now().isoformat(),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"[INFO] {total_downloaded}/{planned_total} article(s) téléchargé(s), {total_blocked} bloqué(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

