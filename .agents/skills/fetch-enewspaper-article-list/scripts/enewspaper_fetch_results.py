#!/usr/bin/env python3
"""Search e-newspaperarchives.ch and export results to JSON and Markdown.

This script uses Playwright in headful mode when needed to pass Cloudflare
Turnstile manually, then extracts paginated search results.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.e-newspaperarchives.ch/?a=q"
DEFAULT_OUTPUT_DIR = Path("sources/enewspaper")
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
DEFAULT_CDP_PROFILE_DIRNAME = "playwright-fetch-results-cdp-profile"

# Turnstile on the first page often takes longer than normal page loads.
INITIAL_CHALLENGE_WAIT_SECONDS = 12.0
CHALLENGE_POLL_SECONDS = 5.0
CHALLENGE_MAX_WAIT_SECONDS = 600.0
CHALLENGE_CLEAR_STABLE_CHECKS = 2

BLOCK_MARKERS = (
    "just a moment",
    "un instant",
    "verification de securite",
    "vérification de sécurité",
    "security verification",
    "cloudflare",
    "are you human",
)

COMMON_LINK_WORDS = {
    "de",
    "le",
    "la",
    "les",
    "du",
    "des",
    "d'",
    "l'",
}

MONTH_NAME_TO_NUMBER = {
    # Francais
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
    # Allemand
    "januar": 1,
    "februar": 2,
    "marz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
    # Italien
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
    # Anglais
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass
class SearchResult:
    article_type: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    newspaper: Optional[str] = None
    snippet: Optional[str] = None
    article_url: Optional[str] = None
    srpos: Optional[int] = None


@dataclass
class PageResults:
    page_index: int
    page_url: str
    blocked: bool
    items: list[SearchResult] = field(default_factory=list)
    year_histogram: Optional[dict[int, int]] = None
    error: Optional[str] = None


@dataclass
class BrowserSession:
    browser: Any
    context: Any
    cdp_endpoint: str
    reused_existing_browser: bool = False
    owns_browser: bool = False
    owns_context: bool = False
    launched_process: Optional[subprocess.Popen] = None


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _clean_newspaper_name(value: Optional[str]) -> Optional[str]:
    """Remove leading result index prefix from newspaper name."""
    cleaned = _norm_ws(value or "")
    # Example: "16. Le Franc-Montagnard" -> "Le Franc-Montagnard"
    cleaned = re.sub(r"^\d+\.\s*", "", cleaned)
    return cleaned or None


def _split_article_type_from_title(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Extract trailing [TYPE] from title and return (type, cleaned_title)."""
    cleaned = _norm_ws(value or "")
    if not cleaned:
        return None, None

    match = re.search(r"\s*\[([^\[\]]+)\]\s*$", cleaned)
    if not match:
        return None, cleaned

    article_type = _norm_ws(match.group(1)) or None
    title = _norm_ws(cleaned[: match.start()]) or None
    return article_type, title


def _filter_common_link_words(query: str) -> str:
    """Remove frequent French connector words from a query."""
    cleaned = _norm_ws(query)
    if not cleaned:
        return ""

    elision_prefixes = tuple(word for word in COMMON_LINK_WORDS if word.endswith("'"))
    kept: list[str] = []
    for token in cleaned.split(" "):
        core = token.strip(".,;:!?()[]{}\"`")
        core_lower = core.lower().replace("’", "'")

        if core_lower in COMMON_LINK_WORDS:
            continue

        # Handle French elisions when attached to the next word.
        # Example: "l'instruction" -> "instruction".
        for prefix in elision_prefixes:
            if core_lower.startswith(prefix) and len(core_lower) > len(prefix):
                core = core[len(prefix):]
                core_lower = core_lower[len(prefix):]
                break

        if core:
            kept.append(core)

    return _norm_ws(" ".join(kept))


def _sanitize_query_for_search(raw_query: str) -> str:
    """Normalize query and remove common link words; fail if no useful terms remain."""
    normalized = _norm_ws(raw_query)
    filtered = _filter_common_link_words(normalized)
    if normalized and not filtered:
        raise ValueError("La requete ne contient que des mots de liaison communs.")
    return filtered


def _apply_txq_to_url(url: str, query: str) -> str:
    """Ensure URL carries txq with the sanitized query.

    Some result pages do not render the search form field, so relying on UI input
    can fail. Setting txq directly keeps behavior deterministic.
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["txq"] = [query]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _slugify(value: str) -> str:
    value = _norm_ws(value).lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "search"


def _article_id_from_url(url: str, fallback_index: int) -> str:
    """Build a stable article identifier from URL query params."""
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


def _ensure_lang_on_url(url: str, lang: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    if "l" not in qs:
        qs["l"] = [lang]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _ensure_results_flag_on_url(url: str) -> str:
    """Ensure the site renders actual result rows instead of the bare search form view."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["results"] = ["1"]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _resolve_partial_date_inputs(
    day: Optional[int],
    month: Optional[int],
    year: Optional[int],
    *,
    year_required_error: str,
    day_requires_month_error: str,
) -> Optional[tuple[int, int, int]]:
    """Resolve optional date using partial input rules shared by start/end."""
    if day is None and month is None and year is None:
        return None

    if year is None:
        raise ValueError(year_required_error)

    if month is None and day is not None:
        raise ValueError(day_requires_month_error)

    resolved_month = 1 if month is None else month
    resolved_day = 1 if day is None else day
    dt.date(year, resolved_month, resolved_day)
    return resolved_day, resolved_month, year


def _apply_date_to_url(url: str, date_value: Optional[tuple[int, int, int]], param_keys: tuple[str, str, str]) -> str:
    """Apply a date tuple to a set of URL query parameters."""
    if not date_value:
        return url

    day, month, year = date_value
    day_key, month_key, year_key = param_keys
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs[day_key] = [str(day)]
    qs[month_key] = [str(month)]
    qs[year_key] = [str(year)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _sync_date_selects_if_present(page, date_value: Optional[tuple[int, int, int]], selectors: tuple[str, str, str]) -> None:
    """Best-effort sync of day/month/year select fields by explicit selectors."""
    if not date_value:
        return

    day, month, year = date_value
    for selector, value in zip(selectors, (day, month, year)):
        try:
            select = page.locator(selector).first
            if select.count() == 0:
                continue
            select.select_option(str(value))
        except Exception:
            # Keep scraping resilient if a select is absent/readonly or value not present.
            continue


def _resolve_start_date_inputs(
    start_day: Optional[int],
    start_month: Optional[int],
    start_year: Optional[int],
) -> Optional[tuple[int, int, int]]:
    """Resolve optional start date using partial input rules.

    Rules:
    - no field => no start date
    - year only => 01/01/year
    - year+month => 01/month/year
    - year+month+day => exact date
    """
    return _resolve_partial_date_inputs(
        start_day,
        start_month,
        start_year,
        year_required_error="`--start-year` est requis si `--start-month` ou `--start-day` est fourni.",
        day_requires_month_error="`--start-day` ne peut pas etre utilise sans `--start-month`.",
    )


def _resolve_end_date_inputs(
    end_day: Optional[int],
    end_month: Optional[int],
    end_year: Optional[int],
) -> Optional[tuple[int, int, int]]:
    """Resolve optional end date using the same partial-input logic as start date."""
    return _resolve_partial_date_inputs(
        end_day,
        end_month,
        end_year,
        year_required_error="`--end-year` est requis si `--end-month` ou `--end-day` est fourni.",
        day_requires_month_error="`--end-day` ne peut pas etre utilise sans `--end-month`.",
    )


def _apply_start_date_to_url(url: str, start_date: Optional[tuple[int, int, int]]) -> str:
    """Apply start date to e-newspaper query params (dafdq/dafmq/dafyq)."""
    return _apply_date_to_url(url, start_date, ("dafdq", "dafmq", "dafyq"))


def _apply_end_date_to_url(url: str, end_date: Optional[tuple[int, int, int]]) -> str:
    """Apply end date to e-newspaper query params (datdq/datmq/datyq)."""
    return _apply_date_to_url(url, end_date, ("datdq", "datmq", "datyq"))


def _apply_newspaper_codes_to_url(url: str, newspaper_codes: list[str]) -> str:
    """Apply newspaper codes to URL query params (selectpuq parameter).
    
    If newspaper_codes is empty, no filter is applied.
    If newspaper_codes is provided, they will be URL-encoded and applied to selectpuq.
    """
    if not newspaper_codes:
        return url
    
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["selectpuq"] = newspaper_codes
    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _sync_start_date_selects_if_present(page, start_date: Optional[tuple[int, int, int]]) -> None:
    """Best-effort sync of start-date UI selects by explicit HTML IDs.

    Required IDs from the site:
    - selectdafdq (day)
    - selectdafmq (month)
    - selectdafyq (year)
    """
    _sync_date_selects_if_present(page, start_date, ("#selectdafdq", "#selectdafmq", "#selectdafyq"))


def _sync_end_date_selects_if_present(page, end_date: Optional[tuple[int, int, int]]) -> None:
    """Best-effort sync of end-date UI selects by explicit HTML IDs.

    Required IDs from the site:
    - selectdatdq (day)
    - selectdatmq (month)
    - selectdatyq (year)
    """
    _sync_date_selects_if_present(page, end_date, ("#selectdatdq", "#selectdatmq", "#selectdatyq"))


def _sync_newspaper_codes_select_if_present(page, newspaper_codes: list[str]) -> bool:
    """Best-effort sync of newspaper filter using the page HTML select element.

    This intentionally avoids URL-based `selectpuq` injection because that mode is
    not reliably applied by e-newspaperarchives.
    """
    if not newspaper_codes:
        return False

    normalized_codes = [code.strip() for code in newspaper_codes if _norm_ws(code)]
    if not normalized_codes:
        return False

    selectors = (
        "#selectpuq",
        "select[name='selectpuq']",
        "select[id*='puq']",
        "select[name*='puq']",
    )

    for selector in selectors:
        try:
            select = page.locator(selector).first
            if select.count() == 0:
                continue
            select.select_option(normalized_codes)
            return True
        except Exception:
            continue

    return False


def _is_blocked(title: str, body_text: str) -> bool:
    blob = _norm_ws(f"{title}\n{body_text}").lower()
    return any(marker in blob for marker in BLOCK_MARKERS)


def _extract_query_from_url(url: str) -> str:
    qs = parse_qs(urlparse(url).query)
    for key in ("txq", "q"):
        values = qs.get(key)
        if values and _norm_ws(values[0]):
            return _norm_ws(values[0])
    return "search"


def _extract_date_range_from_url(url: str) -> tuple[str, str]:
    """Extract start/end date labels from e-newspaper URL params."""
    qs = parse_qs(urlparse(url).query)

    def _fmt(day_key: str, month_key: str, year_key: str) -> str:
        day_values = qs.get(day_key)
        month_values = qs.get(month_key)
        year_values = qs.get(year_key)
        if not (day_values and month_values and year_values):
            return "non specifiee"

        day = _norm_ws(day_values[0])
        month = _norm_ws(month_values[0])
        year = _norm_ws(year_values[0])
        if not (day.isdigit() and month.isdigit() and year.isdigit()):
            return "non specifiee"

        return f"{int(day):02d}/{int(month):02d}/{int(year):04d}"

    start_label = _fmt("dafdq", "dafmq", "dafyq")
    end_label = _fmt("datdq", "datmq", "datyq")
    return start_label, end_label


def _probe_cdp_endpoint(base_url: str) -> str | None:
    """Return a CDP endpoint URL when the candidate is reachable, else None."""
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

    if os.name != "nt":
        home = Path.home()
        ms_playwright_cache_roots = [
            home / ".cache" / "ms-playwright",
            home / "Library" / "Caches" / "ms-playwright",
        ]
        for cache_root in ms_playwright_cache_roots:
            if not cache_root.exists():
                continue
            chromium_dirs = sorted(cache_root.glob("chromium-*"), key=_chromium_revision_key, reverse=True)
            for chromium_dir in chromium_dirs:
                candidates.append(chromium_dir / "chrome-linux" / "chrome")
                candidates.append(chromium_dir / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium")

        for raw in (
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
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
        raise RuntimeError(
            "Impossible de trouver un executable Chromium/Chrome local pour lancer le mode CDP."
        )

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

    raise RuntimeError(
        f"Le navigateur a ete lance, mais l'endpoint CDP {base_url} n'est pas devenu joignable."
    )


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
    reused_existing_browser = resolved_endpoint is not None

    if not resolved_endpoint:
        launched_process, resolved_endpoint = _launch_local_chromium_for_cdp(explicit_cdp_url)
        owns_browser = True
        reused_existing_browser = False

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
        reused_existing_browser=reused_existing_browser,
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


def _find_reusable_blank_page(context) -> Any | None:
    """Return an existing blank/new-tab page when available."""
    blank_urls = {
        "about:blank",
        "about:newtab",
        "chrome://newtab/",
        "edge://newtab/",
    }

    for page in context.pages:
        try:
            current_url = _norm_ws(page.url).lower()
            if current_url in blank_urls:
                return page
        except Exception:
            continue

    return None


def _wait_for_ready_or_block(page, timeout_ms: int = 20000) -> None:
    try:
        page.wait_for_function(
            """
            () => {
              const body = (document.body?.innerText || '').toLowerCase();
              const blocked = body.includes('just a moment') ||
                              body.includes('un instant') ||
                              body.includes('security verification') ||
                              body.includes('vérification de sécurité') ||
                              body.includes('cloudflare');
              const hasSearchInput = !!document.querySelector('input[name="txq"], #txq, input[type="search"]');
              const hasResults = document.querySelectorAll('a[href*="?a=d&d="]').length > 0;
              const noResults = body.includes('0 pour') || body.includes('no results');
              return blocked || hasSearchInput || hasResults || noResults;
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
    """Passively wait for challenge resolution by polling page text every 5s."""
    elapsed = 0.0
    poll_ms = int(max(1.0, poll_seconds) * 1000)
    clear_streak = 0

    while elapsed <= max_wait_seconds:
        try:
            title = page.title()
            body_text = _norm_ws(page.inner_text("body"))
        except Exception as exc:
            msg = str(exc).lower()
            if "execution context was destroyed" in msg or "most likely because of a navigation" in msg:
                clear_streak = 0
                remaining = max_wait_seconds - elapsed
                print(
                    f"[INFO] Navigation detectee pendant Turnstile. Nouvelle verification dans {int(poll_seconds)}s "
                    f"(reste ~{int(max(0.0, remaining))}s)."
                )
                try:
                    page.wait_for_timeout(poll_ms)
                except Exception as wait_exc:
                    print(f"[WARN] Timeout interrompu pendant l'attente du challenge: {wait_exc}")
                    return False
                elapsed += poll_seconds
                continue

            print(f"[WARN] Navigation interrompue pendant l'attente du challenge: {exc}")
            return False

        if not _is_blocked(title, body_text):
            clear_streak += 1
            if clear_streak >= max(1, stable_checks):
                return True
            print(
                f"[INFO] Challenge semble passe. Verification de stabilite "
                f"{clear_streak}/{max(1, stable_checks)}..."
            )
        else:
            clear_streak = 0

        remaining = max_wait_seconds - elapsed
        print(f"[INFO] Challenge actif. Nouvelle verification dans {int(poll_seconds)}s (reste ~{int(max(0.0, remaining))}s).")
        try:
            page.wait_for_timeout(poll_ms)
        except Exception as exc:
            print(f"[WARN] Timeout interrompu pendant l'attente du challenge: {exc}")
            return False
        elapsed += poll_seconds

    return False


def _run_search_if_needed(page, query: Optional[str], wait_time: float, force_submit: bool = False) -> None:
    if not query and not force_submit:
        return

    txq = parse_qs(urlparse(page.url).query).get("txq", [""])[0]
    if _norm_ws(txq) and not force_submit:
        return

    # Prefer explicit selectors and fallback to role-based selectors.
    search_box = page.locator('input[name="txq"], #txq').first
    if search_box.count() == 0:
        search_box = page.get_by_role("textbox", name=re.compile("Chercher|Search|Cercare", re.I)).first

    if search_box.count() == 0:
        # Some search-result URLs already render results without a visible search form.
        has_results = page.locator('a[href*="?a=d&d="]').count() > 0
        if has_results and not force_submit:
            return
        raise RuntimeError("Impossible de trouver le champ de recherche (txq).")

    if query:
        search_box.fill(query)

    button = page.locator('button[type="submit"], input[type="submit"]').first
    if button.count() == 0:
        button = page.get_by_role("button", name=re.compile("Chercher|Search|Cercare", re.I)).first

    if button.count() == 0:
        search_box.press("Enter")
    else:
        button.click()

    page.wait_for_load_state("domcontentloaded", timeout=90000)
    page.wait_for_timeout(int(wait_time * 1000))
    _wait_for_ready_or_block(page)


def _extract_results_on_page(page) -> list[SearchResult]:
    rows = page.evaluate(
        r"""
        () => {
          const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
          const links = Array.from(document.querySelectorAll('a[href*="?a=d&d="]'));
          const datePattern = /\b\d{1,2}[\.\/-]\d{1,2}[\.\/-]\d{2,4}\b|\b\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}\b/;
          const out = [];

          for (const link of links) {
            const li = link.closest('li') || link.closest('article') || link.parentElement;
            if (!li) continue;

            const href = (link.getAttribute('href') || '').trim();
            const title = norm(link.textContent || '');
            const fullTextRaw = (li.innerText || li.textContent || '');
            const fullText = norm(fullTextRaw);
            const lines = fullTextRaw
              .replace(/\r/g, '\n')
              .split('\n')
              .map((line) => norm(line))
              .filter(Boolean);

            // Prefer publication metadata lines (typically near the end),
            // not dates that appear in long article titles.
            const titleLower = title.toLowerCase();
            let date = '';
            let newspaper = '';
            let bestScore = Number.NEGATIVE_INFINITY;

            for (let i = lines.length - 1; i >= 0; i--) {
              const line = lines[i];
              const lineLower = line.toLowerCase();
              const matches = Array.from(line.matchAll(new RegExp(datePattern.source, 'g')));
              if (!matches.length) continue;

              for (let j = matches.length - 1; j >= 0; j--) {
                const match = matches[j];
                const matchText = norm(match[0] || '');
                const matchIndex = typeof match.index === 'number' ? match.index : line.indexOf(matchText);
                if (!matchText || matchIndex < 0) continue;

                const before = norm(line.slice(0, matchIndex));
                const after = norm(line.slice(matchIndex + matchText.length));

                let score = 0;
                if (i === lines.length - 1) score += 4;
                if (before) score += 3;
                if (!after) score += 1;
                if (lineLower === titleLower) score -= 8;
                if (titleLower && lineLower.includes(titleLower)) score -= 3;
                if (before && titleLower && before.toLowerCase().includes(titleLower)) score -= 2;

                if (score > bestScore) {
                  bestScore = score;
                  date = matchText;
                  newspaper = before;
                }
              }
            }

            // Fallback: keep the last date found in the full text.
            if (!date) {
              const allDateMatches = Array.from(fullText.matchAll(new RegExp(datePattern.source, 'g')));
              if (allDateMatches.length) {
                const lastMatch = allDateMatches[allDateMatches.length - 1];
                date = norm(lastMatch[0] || '');
              }
            }

            if (!newspaper && date) {
              const dateIndex = fullText.lastIndexOf(date);
              if (dateIndex > 0) {
                const before = fullText.slice(0, dateIndex);
                newspaper = norm(before.replace(title, ''));
              }
            }

            // Guess snippet from dedicated node first.
            const snippetNode = li.querySelector('p, .snippet, .searchResultSnippet');
            let snippet = snippetNode ? norm(snippetNode.textContent || '') : '';
            if (!snippet) {
              snippet = fullText.replace(title, '').trim();
            }

            const urlObj = new URL(href, window.location.href);
            const srposRaw = urlObj.searchParams.get('srpos');
            const srpos = srposRaw && /^\d+$/.test(srposRaw) ? parseInt(srposRaw, 10) : null;

            out.push({
              title,
              date,
              newspaper,
              snippet,
              article_url: urlObj.toString(),
              srpos,
            });
          }

          return out;
        }
        """
    )

    results: list[SearchResult] = []
    for row in rows:
        raw_date = _norm_ws(row.get("date") or "")
        article_type, clean_title = _split_article_type_from_title(row.get("title"))
        results.append(
            SearchResult(
                article_type=article_type,
                title=clean_title,
                date_publication=_format_result_date(raw_date),
                newspaper=_clean_newspaper_name(row.get("newspaper")),
                snippet=_norm_ws(row.get("snippet") or "") or None,
                article_url=_norm_ws(row.get("article_url") or "") or None,
                srpos=row.get("srpos"),
            )
        )
    return results


def _extract_year_histogram(page) -> dict[int, int]:
    """Extract year-count histogram from search page HTML metadata."""
    raw = page.evaluate(
        r"""
        () => {
          const node = document.querySelector('#searchresultyeargraph');
          if (!node) return '';
          return (node.getAttribute('data-year-count-mapping-json') || '').trim();
        }
        """
    )

    raw_mapping = _norm_ws(raw or "")
    if not raw_mapping:
        return {}

    payload = None
    for candidate in (raw_mapping, html.unescape(raw_mapping)):
        try:
            payload = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue

    if not isinstance(payload, dict):
        return {}

    histogram: dict[int, int] = {}
    for year_raw, count_raw in payload.items():
        try:
            year = int(str(year_raw).strip())
            count = int(str(count_raw).strip())
        except (ValueError, TypeError):
            continue
        if count >= 0:
            histogram[year] = count

    return dict(sorted(histogram.items(), key=lambda kv: kv[0]))


def _next_page_href(page) -> Optional[str]:
    links = page.evaluate(
        r"""
        () => Array.from(document.querySelectorAll('nav a[href]')).map((a) => ({
          text: (a.textContent || '').replace(/\s+/g, ' ').trim(),
          href: (a.getAttribute('href') || '').trim(),
        }))
        """
    )

    current_r = parse_qs(urlparse(page.url).query).get("r", ["1"])[0]
    try:
        current_r_int = int(current_r)
    except ValueError:
        current_r_int = 1

    candidates: list[tuple[int, str]] = []
    for link in links:
        href = link.get("href") or ""
        text = (link.get("text") or "").lower()
        if not href:
            continue
        if "a=q" not in href:
            continue
        parsed = urlparse(urljoin(page.url, href))
        r_values = parse_qs(parsed.query).get("r")
        if not r_values:
            continue
        try:
            r_value = int(r_values[0])
        except ValueError:
            continue
        if r_value <= current_r_int:
            continue
        score = 0
        if "suiv" in text or "next" in text or "»" in text:
            score = -1000
        candidates.append((score + r_value, urljoin(page.url, href)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _collect(
    warmup_url: str,
    url: str,
    query: Optional[str],
    start_date: Optional[tuple[int, int, int]],
    end_date: Optional[tuple[int, int, int]],
    newspaper_codes: list[str],
    max_pages: int,
    pause_on_challenge: bool,
    wait_time: float,
    cdp_url: Optional[str],
    keep_browser_open: bool,
) -> list[PageResults]:
    collected: list[PageResults] = []


    with sync_playwright() as p:
        session = _connect_browser_context_over_cdp(p, cdp_url)
        print(f"[INFO] CDP endpoint utilise: {session.cdp_endpoint}")
        if session.reused_existing_browser:
            print("[INFO] Navigateur existant detecte et reutilise.")
        else:
            print("[INFO] Aucun navigateur CDP existant detecte; un nouveau navigateur a ete lance.")

        page = _find_reusable_blank_page(session.context)
        if page is not None:
            print("[INFO] Onglet vide existant reutilise.")
        else:
            page = session.context.new_page()
            print("[INFO] Aucun onglet vide detecte; creation d'un nouvel onglet.")
        try:
            # Warm up on the raw BASE_URL first to pass Cloudflare before loading
            # the fully-parameterized search URL.
            page.goto(warmup_url, wait_until="domcontentloaded", timeout=90000)
            initial_wait = max(float(wait_time) * 3.0, INITIAL_CHALLENGE_WAIT_SECONDS)
            page.wait_for_timeout(int(initial_wait * 1000))
            _wait_for_ready_or_block(page)

            title = page.title()
            body_text = _norm_ws(page.inner_text("body"))
            initial_blocked = _is_blocked(title, body_text)
            if initial_blocked and pause_on_challenge:
                print("[INFO] Challenge Cloudflare detecte au chargement initial. Attente passive en cours...")
                initial_blocked = not _wait_passively_for_challenge_clear(page)

            if initial_blocked:
                # Do not interact with the page while challenge is active: this can
                # trigger additional reloads on Turnstile screens.
                collected.append(
                    PageResults(
                        page_index=1,
                        page_url=page.url,
                        blocked=True,
                        items=[],
                        error="Challenge Cloudflare detecte avant extraction.",
                    )
                )
                return collected

            # Challenge passed on warmup page, now open the actual search URL.
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(int(wait_time * 1000))
            _wait_for_ready_or_block(page)

            title = page.title()
            body_text = _norm_ws(page.inner_text("body"))
            blocked_after_search_nav = _is_blocked(title, body_text)
            if blocked_after_search_nav and pause_on_challenge:
                print("[INFO] Challenge detecte apres ouverture de la page de recherche. Attente passive en cours...")
                blocked_after_search_nav = not _wait_passively_for_challenge_clear(page)

            if blocked_after_search_nav:
                collected.append(
                    PageResults(
                        page_index=1,
                        page_url=page.url,
                        blocked=True,
                        items=[],
                        error="Challenge Cloudflare detecte apres ouverture de la page de recherche.",
                    )
                )
                return collected

            # Date filters are already encoded in URL query params; touching the
            # date selectors can trigger form-driven reload loops on this site.
            newspaper_filter_applied = _sync_newspaper_codes_select_if_present(page, newspaper_codes)
            if newspaper_codes and not newspaper_filter_applied:
                print("[WARN] Filtre journaux non applique: selecteur HTML `selectpuq` introuvable ou incompatible.")

            # Force submit when journal filters are requested so UI-selected values
            # are actually applied by the remote search form.
            _run_search_if_needed(
                page,
                query=query,
                wait_time=wait_time,
                force_submit=bool(newspaper_codes),
            )

            visited_urls: set[str] = set()

            for page_index in range(1, max_pages + 1):
                blocked = False
                items: list[SearchResult] = []
                year_histogram: Optional[dict[int, int]] = None
                error = None
                title = ""
                body_text = ""

                try:
                    title = page.title()
                    body_text = _norm_ws(page.inner_text("body"))
                    blocked = _is_blocked(title, body_text)

                    if blocked and pause_on_challenge:
                        print("[INFO] Challenge Cloudflare detecte. Attente passive en cours...")
                        blocked = not _wait_passively_for_challenge_clear(page)

                    if not blocked:
                        items = _extract_results_on_page(page)
                        year_histogram = _extract_year_histogram(page)
                except Exception as exc:
                    error = str(exc)

                collected.append(
                    PageResults(
                        page_index=page_index,
                        page_url=page.url,
                        blocked=blocked,
                        items=items,
                        year_histogram=year_histogram,
                        error=error,
                    )
                )

                if blocked:
                    break
                if page.url in visited_urls:
                    break
                visited_urls.add(page.url)

                next_href = _next_page_href(page)
                if not next_href:
                    break

                page.goto(next_href, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(int(wait_time * 1000))
                _wait_for_ready_or_block(page)
        finally:
            if keep_browser_open:
                print("[INFO] Navigateur laisse ouvert pour verification manuelle.")
            else:
                _cleanup_browser_session(session, page)

    return collected


def _dedupe(items: Iterable[SearchResult]) -> list[SearchResult]:
    out: list[SearchResult] = []
    seen: set[str] = set()
    for item in items:
        key = (item.article_url or "").strip().lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(item)
    return out


def _normalize_alpha_for_date(value: str) -> str:
    """Normalize alpha date text to ASCII-ish lowercase for month matching."""
    normalized = unicodedata.normalize("NFKD", _norm_ws(value).lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _parse_result_date(value: Optional[str]) -> Optional[dt.date]:
    """Best-effort parse of publication date for sorting."""
    if not value:
        return None

    text = _norm_ws(value)

    # Numeric variants: dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd.
    m = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", text)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3))
        if year < 100:
            year += 2000 if year < 50 else 1900
        try:
            return dt.date(year, month, day)
        except ValueError:
            pass

    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        try:
            return dt.date(year, month, day)
        except ValueError:
            pass

    # Alpha month variants: "12 mars 1934", "12 March 1934", etc.
    normalized = _normalize_alpha_for_date(text)
    m = re.search(r"\b(\d{1,2})\s+([a-z]+)\s+(\d{4})\b", normalized)
    if m:
        day = int(m.group(1))
        month_name = m.group(2)
        year = int(m.group(3))
        month = MONTH_NAME_TO_NUMBER.get(month_name)
        if month:
            try:
                return dt.date(year, month, day)
            except ValueError:
                pass

    return None


def _format_result_date(value: Optional[str]) -> Optional[str]:
    """Format a parsed result date as dd.MM.yyyy when possible."""
    if not value:
        return None

    parsed = _parse_result_date(value)
    if parsed is None:
        return _norm_ws(value) or None

    return parsed.strftime("%d.%m.%Y")


def _sort_results_by_publication_date(items: list[SearchResult]) -> list[SearchResult]:
    """Sort results by publication date ascending; keep undated items last."""
    indexed = list(enumerate(items))

    def _key(pair: tuple[int, SearchResult]) -> tuple[bool, dt.date, int, int]:
        idx, item = pair
        parsed = _parse_result_date(item.date)
        if parsed is None:
            return (True, dt.date.max, item.srpos if item.srpos is not None else 10**9, idx)
        return (False, parsed, item.srpos if item.srpos is not None else 10**9, idx)

    return [item for _, item in sorted(indexed, key=_key)]


def _md_cell(text: Optional[str]) -> str:
    return _norm_ws(text or "").replace("|", "\\|")


def _yaml_escape(text: Optional[str]) -> str:
    return _norm_ws(text or "").replace('"', "'")


def _render_markdown(search_url: str, pages: list[PageResults]) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = dt.datetime.now().strftime("%Y-%m-%d")
    all_items = _sort_results_by_publication_date(_dedupe(item for page in pages for item in page.items))
    query = _extract_query_from_url(search_url)
    start_label, end_label = _extract_date_range_from_url(search_url)
    title = f"Recherche e-newspaperarchives.ch — {query}"
    year_histogram = next((page.year_histogram for page in pages if page.year_histogram), {})

    lines = [
        "---",
        f'title: "{_yaml_escape(title)}"',
        f'date_consultation: "{today}"',
        'transformation_by: "skill fetch-enewspaper-article-list"',
        "sources:",
        f'  - "{_yaml_escape(search_url)}"',
        "---",
        "",
        "# Recherche e-newspaperarchives.ch",
        "",
        f"- Requete: `{query}`",
        f"- Date de debut (filtre): `{start_label}`",
        f"- Date de fin (filtre): `{end_label}`",
        f"- Date de consultation: `{now}`",
        f"- Pages visitees: `{len(pages)}`",
        f"- Resultats uniques collectes: `{len(all_items)}`",
        f"- URL de recherche: [Lien]({search_url})",
        "",
        "## Resume global",
        "",
    ]

    if not all_items:
        lines.append("Aucun resultat exploitable n'a ete extrait automatiquement.")
    else:
        lines.append(f"Total: **{len(all_items)}** resultats")
        lines.append("")
        lines.append("| Position | Type d'article | Titre | Date | Journal | URL |")
        lines.append("|---|---|---|---|---|---|")
        for item in all_items:
            pos = str(item.srpos) if item.srpos is not None else ""
            url = f"[Lien]({item.article_url})" if item.article_url else ""
            lines.append(
                f"| {pos} | {_md_cell(item.article_type)} | {_md_cell(item.title)} | {_md_cell(item.date)} | {_md_cell(item.newspaper)} | {url} |"
            )

    lines.append("")
    lines.append("## Histogramme du nombre d'articles au cours du temps")
    lines.append("")

    if not year_histogram:
        lines.append("Histogramme indisponible (`#searchresultyeargraph[data-year-count-mapping-json]` absent ou illisible).")
    else:
        max_count = max(year_histogram.values()) if year_histogram else 0
        lines.append("```text")
        lines.append(f"{'Annee':<8} {'N':>6}  {'Histogramme'}")
        for year, count in sorted(year_histogram.items()):
            bar_len = round((count / max_count) * 40) if max_count > 0 else 0
            lines.append(f"{year:<8} {count:>6}  {'#' * bar_len}")
        lines.append("```")

        lines.append("")
        lines.append("| Annee | Nombre d'articles |")
        lines.append("|---:|---:|")
        for year, count in sorted(year_histogram.items()):
            lines.append(f"| {year} | {count} |")

    lines.append("")
    lines.append("## Details par page")
    lines.append("")

    for page in pages:
        lines.append(f"### Page {page.page_index}")
        lines.append("")
        lines.append(f"- URL: `{page.page_url}`")
        lines.append(f"- Statut anti-bot: `{'bloque' if page.blocked else 'ok'}`")
        if page.error:
            lines.append(f"- Erreur: `{page.error}`")
        lines.append(f"- Nombre de resultats extraits: `{len(page.items)}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract e-newspaperarchives search results")
    parser.add_argument("--query", help="Search query text")
    parser.add_argument("--lang", default="fr", help="Language code used if URL has no l= parameter")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum pages to process")
    parser.add_argument("--wait-time", type=float, default=3.5, help="Wait time after each page load")
    parser.add_argument("--start-day", type=int, choices=range(1, 32), metavar="1-31", help="Start date day")
    parser.add_argument("--start-month", type=int, choices=range(1, 13), metavar="1-12", help="Start date month")
    parser.add_argument("--start-year", type=int, help="Start date year")
    parser.add_argument("--end-day", type=int, choices=range(1, 32), metavar="1-31", help="End date day")
    parser.add_argument("--end-month", type=int, choices=range(1, 13), metavar="1-12", help="End date month")
    parser.add_argument("--end-year", type=int, help="End date year")
    parser.add_argument(
        "--newspaper-codes",
        nargs="*",
        default=[],
        help="List of newspaper codes to filter by (e.g., NZZ BEZ). If empty, search all newspapers.",
    )
    parser.add_argument(
        "--no-pause-on-challenge",
        action="store_true",
        help="Disable passive waiting when Turnstile challenge is detected",
    )
    parser.add_argument("--cdp-url", help="CDP endpoint URL (ex: http://127.0.0.1:9222)")
    parser.add_argument("--close-browser-at-end", action="store_true", help="Close browser when scraping completes")
    parser.add_argument("--dry-run", action="store_true", help="Show planned run without scraping")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pause_on_challenge = not args.no_pause_on_challenge

    try:
        start_date = _resolve_start_date_inputs(args.start_day, args.start_month, args.start_year)
        end_date = _resolve_end_date_inputs(args.end_day, args.end_month, args.end_year)
        if start_date and end_date:
            start_dt = dt.date(start_date[2], start_date[1], start_date[0])
            end_dt = dt.date(end_date[2], end_date[1], end_date[0])
            if end_dt < start_dt:
                raise ValueError("La date de fin ne peut pas etre anterieure a la date de debut.")
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    url = _ensure_lang_on_url(BASE_URL, args.lang)
    url = _ensure_results_flag_on_url(url)
    raw_query = args.query or _extract_query_from_url(url)
    try:
        query = _sanitize_query_for_search(raw_query)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    url = _apply_txq_to_url(url, query)
    url = _apply_start_date_to_url(url, start_date)
    url = _apply_end_date_to_url(url, end_date)

    if args.dry_run:
        print(f"[DRY-RUN] Would open: {url}")
        print(f"[DRY-RUN] Query: {query}")
        print(f"[DRY-RUN] Output directory: {args.output_dir}")
        print(f"[DRY-RUN] Max pages: {args.max_pages}")
        if start_date:
            day, month, year = start_date
            print(f"[DRY-RUN] Start date: {day:02d}/{month:02d}/{year}")
        else:
            print("[DRY-RUN] Start date: (not used)")
        if end_date:
            day, month, year = end_date
            print(f"[DRY-RUN] End date: {day:02d}/{month:02d}/{year}")
        else:
            print("[DRY-RUN] End date: (not used)")
        if args.newspaper_codes:
            print(f"[DRY-RUN] Newspaper codes: {', '.join(args.newspaper_codes)}")
        else:
            print("[DRY-RUN] Newspaper codes: (not filtered, all newspapers)")
        print("[DRY-RUN] Browser mode: headful (fixed)")
        print(f"[DRY-RUN] CDP URL: {args.cdp_url or '(auto)'}")
        print(f"[DRY-RUN] Pause on challenge: {pause_on_challenge}")
        print(f"[DRY-RUN] Keep browser open: {not args.close_browser_at_end}")
        return 0

    pages = _collect(
        warmup_url=BASE_URL,
        url=url,
        query=query,
        start_date=start_date,
        end_date=end_date,
        newspaper_codes=args.newspaper_codes,
        max_pages=args.max_pages,
        pause_on_challenge=pause_on_challenge,
        wait_time=args.wait_time,
        cdp_url=args.cdp_url,
        keep_browser_open=not args.close_browser_at_end,
    )

    all_results = _sort_results_by_publication_date(_dedupe(item for page in pages for item in page.items))

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    query_slug = _slugify(query)
    json_path = args.output_dir / f"enewspaper_{query_slug}_{timestamp}.json"
    md_path = args.output_dir / f"enewspaper_{query_slug}_{timestamp}.md"

    payload = {
        "search_url": url,
        "query": query,
        "search_start_date": _extract_date_range_from_url(url)[0],
        "search_end_date": _extract_date_range_from_url(url)[1],
        "date_consultation": dt.datetime.now().isoformat(),
        "pages_processed": len(pages),
        "total_results": len(all_results),
        "year_histogram": next((page.year_histogram for page in pages if page.year_histogram), {}),
        "results": [asdict(item) for item in all_results],
        "downloaded_articles": [],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_render_markdown(url, pages), encoding="utf-8")

    anti_bot = any(page.blocked for page in pages)
    print(
        json.dumps(
            {
                "pages_processed": len(pages),
                "total_results": len(all_results),
                "json_output": str(json_path),
                "markdown_output": str(md_path),
                "anti_bot_detected": anti_bot,
                "timestamp": dt.datetime.now().isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


