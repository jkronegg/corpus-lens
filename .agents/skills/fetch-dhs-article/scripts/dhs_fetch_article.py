#!/usr/bin/env python3
"""Recherche un article DHS depuis les catalogues CSV locaux, puis l'exporte en Markdown.

Usage principal :
- cherche un ou plusieurs termes dans les catalogues CSV DHS locaux ;
- récupère l'URL correspondante pour les meilleurs résultats ;
- télécharge l'article HTML ;
- convertit le HTML en Markdown via `dhs_html_to_md.py` ;
- télécharge les images en local ;
- enregistre le Markdown et les images dans `sources/DHS` (ou un dossier configuré).

Ce script remplace le précédent flux multi-modes : il est désormais centré sur
une seule tâche explicite, l'export ciblé d'articles DHS.
"""

from __future__ import annotations

import argparse
import base64
import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dhs_html_to_md import convert_dhs_html_to_md, download_and_rewrite_images
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

SKILL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[4]
DB_SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
_DB_MODULE_PATH = DB_SCRIPTS_DIR / "db.py"
get_db_connection = None
register_source_document = None
try:
    spec = importlib.util.spec_from_file_location("named_entities_db_for_dhs", _DB_MODULE_PATH)
    if spec and spec.loader:
        _db_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = _db_module
        spec.loader.exec_module(_db_module)
        get_db_connection = _db_module.get_connection
        register_source_document = _db_module.register_source_document
        DB_AVAILABLE = True
    else:
        DB_AVAILABLE = False
except Exception:
    DB_AVAILABLE = False

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
DHS_BASE = "https://hls-dhs-dss.ch"
DEFAULT_CSV_GLOB = "liste_*_f_utf8.csv"
DEFAULT_CSV_DIR = SKILL_ROOT / "assets"
DEFAULT_OUT_DIR = Path("sources/DHS")
MD_IMAGE_RE = re.compile(r"!\[[^]]*]\(([^)]+)\)")
DEFAULT_CDP_CANDIDATES = (
    "http://127.0.0.1:9222",
    "http://127.0.0.1:9223",
    "http://127.0.0.1:9333",
)
DEFAULT_CDP_PORT = 9222
DEFAULT_CDP_STARTUP_TIMEOUT_SECONDS = 15.0
DEFAULT_CDP_STARTUP_POLL_SECONDS = 0.5
DEFAULT_CDP_PROFILE_DIRNAME = "playwright-dhs-cdp-profile"
CHALLENGE_POLL_SECONDS = 5.0
CHALLENGE_MAX_WAIT_SECONDS = 180.0
CHALLENGE_CLEAR_STABLE_CHECKS = 2
BLOCK_MARKERS = (
    "just a moment",
    "un instant",
    "security verification",
    "verification de securite",
    "vérification de sécurité",
    "cloudflare",
    "are you human",
    "cf-ray",
)


@dataclass(slots=True)
class Config:
    timeout: int
    sleep_s: float
    user_agent: str
    dry_run: bool
    cdp_url: str | None
    pause_on_challenge: bool


@dataclass(slots=True)
class BrowserSession:
    browser: Any
    context: Any
    cdp_endpoint: str
    reused_existing_browser: bool = False
    owns_browser: bool = False
    owns_context: bool = False
    launched_process: Optional[subprocess.Popen] = None


@dataclass(slots=True)
class CatalogHit:
    term: str
    score: int
    csv_file: Path
    article_id: str
    lemma: str
    url: str
    row: Dict[str, str]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cherche des articles DHS dans les catalogues CSV et les exporte en Markdown"
    )
    parser.add_argument(
        "--term",
        "--hybrid-term",
        action="append",
        dest="terms",
        default=[],
        help="Terme DHS à chercher dans les CSV locaux (répétable)",
    )
    parser.add_argument(
        "--csv-dir",
        "--hybrid-csv-dir",
        type=Path,
        default=DEFAULT_CSV_DIR,
        dest="csv_dir",
        help=f"Dossier contenant les CSV DHS ({DEFAULT_CSV_GLOB})",
    )
    parser.add_argument(
        "--csv-glob",
        "--hybrid-csv-glob",
        default=DEFAULT_CSV_GLOB,
        dest="csv_glob",
        help="Glob des CSV DHS à analyser",
    )
    parser.add_argument(
        "--out-dir",
        "--hybrid-out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        dest="out_dir",
        help="Dossier de sortie des .md et images",
    )
    parser.add_argument(
        "--max-hits",
        "--hybrid-max-hits",
        type=int,
        default=1,
        dest="max_hits",
        help="Nombre max de lignes CSV retenues par terme (défaut: 1)",
    )
    parser.add_argument(
        "--overwrite",
        "--hybrid-overwrite",
        action="store_true",
        dest="overwrite",
        help="Écrase les fichiers .md existants",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP en secondes")
    parser.add_argument("--sleep", type=float, default=0.5, help="Pause entre requêtes (secondes)")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent HTTP")
    parser.add_argument("--cdp-url", default=None, help="Endpoint CDP (ex: http://127.0.0.1:9222)")
    parser.add_argument(
        "--no-pause-on-challenge",
        action="store_true",
        help="Ne pas attendre passivement la resolution du challenge Cloudflare",
    )
    parser.add_argument("--dry-run", action="store_true", help="N'effectue pas les requêtes HTTP")
    return parser.parse_args(list(argv))


def warn_legacy_flags(argv: Sequence[str]) -> None:
    legacy_flags = [arg for arg in argv if arg.startswith("--hybrid-")]
    if legacy_flags:
        unique_flags = ", ".join(sorted(set(legacy_flags)))
        print(
            f"[info] Alias hérités détectés ({unique_flags}). Préfère `--term`, `--csv-dir`, `--out-dir`, `--max-hits`, `--overwrite`.",
            file=sys.stderr,
        )


def slugify(value: str) -> str:
    """Produit un slug stable et lisible, sans accents."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "theme"


def normalize_search_text(value: str) -> str:
    return slugify(value).replace("_", " ")


def normalize_numeric_id(value: str) -> str:
    """Normalise un identifiant numerique pour comparaison (ignore les zeros de tete)."""
    digits = re.sub(r"\D+", "", value or "")
    if not digits:
        return ""
    return digits.lstrip("0") or "0"


def is_numeric_term(value: str) -> bool:
    return bool(re.fullmatch(r"\d+", (value or "").strip()))


def normalize_url(url: str) -> str:
    normalized = (url or "").strip()
    if not normalized:
        return ""
    if normalized.startswith(("http://", "https://")):
        return normalized
    if normalized.startswith("/"):
        return DHS_BASE + normalized
    return DHS_BASE + "/" + normalized


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _is_blocked(title: str, body_text: str) -> bool:
    blob = _norm_ws(f"{title}\n{body_text}").lower()
    return any(marker in blob for marker in BLOCK_MARKERS)


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


def _connect_browser_context_over_cdp(playwright, explicit_cdp_url: str | None, user_agent: str) -> BrowserSession:
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
        context = browser.new_context(user_agent=user_agent)
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


def _find_reusable_blank_page(context: Any) -> Any | None:
    blank_urls = {
        "about:blank",
        "about:newtab",
        "chrome://newtab/",
        "edge://newtab/",
    }

    blank_page = None
    dhs_page = None

    for page in context.pages:
        try:
            current_url = _norm_ws(page.url).lower()
            if current_url in blank_urls:
                blank_page = page
            elif current_url.startswith("https://hls-dhs-dss.ch"):
                dhs_page = page
        except Exception:
            continue

    # Préfère réutiliser une blank page, sinon réutilise une page DHS existante
    return blank_page or dhs_page


def _wait_for_ready_or_block(page: Any, timeout_ms: int = 20000) -> None:
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
              const hasArticle = !!document.querySelector('article, .entry-content, .article, main');
              const hasTitle = !!document.querySelector('h1');
              return blocked || hasArticle || hasTitle;
            }
            """,
            timeout=timeout_ms,
        )
    except Exception:
        pass


def _wait_passively_for_challenge_clear(
    page: Any,
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
            body_text = _norm_ws(page.inner_text("body"))
        except Exception as exc:
            msg = str(exc).lower()
            if "execution context was destroyed" in msg or "most likely because of a navigation" in msg:
                clear_streak = 0
                page.wait_for_timeout(poll_ms)
                elapsed += poll_seconds
                continue
            return False

        if not _is_blocked(title, body_text):
            clear_streak += 1
            if clear_streak >= max(1, stable_checks):
                return True
        else:
            clear_streak = 0

        page.wait_for_timeout(poll_ms)
        elapsed += poll_seconds

    return False


def _start_browser_session(cfg: Config):
    playwright = sync_playwright().start()
    try:
        session = _connect_browser_context_over_cdp(playwright, cfg.cdp_url, cfg.user_agent)
    except Exception:
        playwright.stop()
        raise
    return playwright, session


def _finish_browser_session(playwright, session: BrowserSession, page) -> None:
    """Finit la session du navigateur CDP en le laissant ouvert."""
    print("  [info] Navigateur CDP laisse ouvert pour verification manuelle.")


def _get_or_create_work_page(session: BrowserSession) -> Any:
    page = _find_reusable_blank_page(session.context)
    if page is None:
        page = session.context.new_page()
    return page


def _load_article_html(page: Any, url: str, cfg: Config) -> Tuple[str, int | None, str]:
    response = page.goto(url, wait_until="domcontentloaded", timeout=cfg.timeout * 1000)
    _wait_for_ready_or_block(page, timeout_ms=cfg.timeout * 1000)

    title = page.title()
    body_text = _norm_ws(page.inner_text("body"))
    blocked = _is_blocked(title, body_text)
    if blocked and cfg.pause_on_challenge:
        print("  [info] Challenge Cloudflare detecte. Attente passive en cours...")
        blocked = not _wait_passively_for_challenge_clear(page)

    body = page.content()
    status = response.status if response else None
    final_url = page.url
    if blocked:
        raise RuntimeError("Cloudflare challenge")
    return body, status, final_url


def _download_image_via_cdp_page(page: Any, image_url: str, out_img: Path, timeout_ms: int) -> bool:
    page.set_default_timeout(timeout_ms)
    result = page.evaluate(
        """
        async ({ imageUrl }) => {
          try {
            const response = await fetch(imageUrl, {
              credentials: 'include',
              cache: 'force-cache',
            });
            const status = response.status;
            const contentType = response.headers.get('content-type') || '';
            if (!response.ok) {
              return { ok: false, status, contentType, error: `HTTP ${status}` };
            }

            const buffer = await response.arrayBuffer();
            const bytes = new Uint8Array(buffer);
            let binary = '';
            const chunkSize = 0x8000;
            for (let i = 0; i < bytes.length; i += chunkSize) {
              const chunk = bytes.subarray(i, i + chunkSize);
              binary += String.fromCharCode(...chunk);
            }

            return {
              ok: true,
              status,
              contentType,
              bodyBase64: btoa(binary),
            };
          } catch (error) {
            return { ok: false, error: String(error) };
          }
        }
        """,
        {"imageUrl": image_url},
    )

    if not result or not result.get("ok"):
        return False

    payload = base64.b64decode(result.get("bodyBase64") or "")
    if not payload:
        return False

    out_img.write_bytes(payload)
    return True


def fetch_html(url: str, cfg: Config) -> Tuple[str, int | None, str]:
    playwright, session = _start_browser_session(cfg)
    page = _get_or_create_work_page(session)
    assert page is not None
    try:
        print(f"  [info] CDP endpoint utilise: {session.cdp_endpoint}")
        return _load_article_html(page, url, cfg)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(f"Timeout Playwright: {exc}") from exc
    finally:
        _finish_browser_session(playwright, session, page)


def is_cloudflare_challenge(page_html: str) -> bool:
    low = page_html.lower()
    return "cloudflare" in low and (
        "just a moment" in low or "__cf_chl" in low or "cf-ray" in low or "cf-mitigated" in low
    )


def discover_catalog_csv_files(csv_dir: Path, csv_glob: str) -> List[Path]:
    if not csv_dir.exists():
        return []
    return sorted(path for path in csv_dir.glob(csv_glob) if path.is_file())


def row_match_score(row: Dict[str, str], term: str) -> int:
    """Score simple: exact lemma > exact autres champs > contient."""
    if is_numeric_term(term):
        target_id = normalize_numeric_id(term)
        row_id = normalize_numeric_id(row.get("ID", ""))
        if target_id and row_id and target_id == row_id:
            return 1000

    target = normalize_search_text(term)
    lemma = normalize_search_text(row.get("Lemma", ""))
    complement = normalize_search_text(row.get("Complement", ""))
    precision = normalize_search_text(row.get("Precision", ""))
    full_name = " ".join(part for part in (lemma, complement) if part).strip()
    inverted_full_name = " ".join(part for part in (complement, lemma) if part).strip()

    if lemma and lemma == target:
        return 300
    if target and target in {full_name, inverted_full_name}:
        return 280
    if complement and complement == target:
        return 250
    if precision and precision == target:
        return 220

    haystack = " ".join(part for part in (lemma, complement, precision) if part)
    if target and target in haystack:
        return 100

    return 0


def find_hits_in_catalogs(term: str, csv_files: Sequence[Path], max_hits: int) -> List[CatalogHit]:
    hits: List[CatalogHit] = []
    for csv_file in csv_files:
        with csv_file.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                score = row_match_score(row, term)
                if score <= 0:
                    continue

                url = normalize_url(row.get("URL", ""))
                if not url:
                    continue

                article_id = ((row.get("ID", "") or "").strip() or "000000").zfill(6)
                lemma = (row.get("Lemma", "") or "").strip() or "sans_titre"
                hits.append(
                    CatalogHit(
                        term=term,
                        score=score,
                        csv_file=csv_file,
                        article_id=article_id,
                        lemma=lemma,
                        url=url,
                        row=dict(row),
                    )
                )

    hits.sort(key=lambda hit: (-hit.score, hit.article_id, hit.lemma.casefold()))

    deduped: List[CatalogHit] = []
    seen_urls = set()
    for hit in hits:
        if hit.url in seen_urls:
            continue
        seen_urls.add(hit.url)
        deduped.append(hit)

    target = normalize_search_text(term)
    exact_lemma_hits = [hit for hit in deduped if normalize_search_text(hit.lemma) == target]

    # Un même terme peut référencer plusieurs notices DHS distinctes (ex. homonymes/familles).
    # Dans ce cas on retourne toutes les correspondances exactes du lemme.
    if len(exact_lemma_hits) > 1:
        return exact_lemma_hits

    return deduped[: max(1, max_hits)]


def prefix_downloaded_images(md_text: str, md_out_path: Path, images_root: Path, prefix: str) -> str:
    """Préfixe les noms d'images locales avec le thème de recherche."""
    target_dir = images_root / md_out_path.stem
    if not target_dir.exists():
        return md_text

    rel_dir = str(target_dir.relative_to(md_out_path.parent)).replace("\\", "/")
    for image_file in sorted(target_dir.glob("*")):
        if not image_file.is_file():
            continue

        old_name = image_file.name
        new_name = old_name if old_name.startswith(prefix + "_") else f"{prefix}_{old_name}"
        if new_name == old_name:
            continue

        new_path = image_file.with_name(new_name)
        if new_path.exists():
            continue

        image_file.rename(new_path)
        old_rel = f"{rel_dir}/{old_name}" if rel_dir else old_name
        new_rel = f"{rel_dir}/{new_name}" if rel_dir else new_name
        md_text = md_text.replace(f"]({old_rel})", f"]({new_rel})")

    return md_text


def build_md_filename(term: str, article_id: str, lemma: str) -> str:
    """Construit un nom .md stable en evitant le doublon term/lemma."""
    term_prefix = slugify(term)
    lemma_slug = slugify(lemma)
    safe_article_id = (article_id or "000000").zfill(6)

    if lemma_slug == term_prefix:
        return f"{term_prefix}_dhs_{safe_article_id}.md"

    return f"{term_prefix}_dhs_{safe_article_id}_{lemma_slug}.md"


def verify_export_outputs(md_out: Path) -> Tuple[int, int]:
    """Valide le markdown exporte et ses images locales referencees.

    Retourne (images_referencees, images_manquantes).
    """
    if not md_out.exists() or md_out.stat().st_size == 0:
        raise RuntimeError(f"Fichier Markdown absent ou vide: {md_out}")

    content = md_out.read_text(encoding="utf-8", errors="replace")
    image_links = [m.group(1).strip() for m in MD_IMAGE_RE.finditer(content)]

    local_refs = []
    for ref in image_links:
        lower = ref.lower()
        if lower.startswith(("http://", "https://", "data:")):
            continue
        local_refs.append(ref)

    missing = 0
    for ref in local_refs:
        target = (md_out.parent / ref).resolve()
        if not target.exists() or not target.is_file():
            missing += 1

    if missing > 0:
        raise RuntimeError(
            f"Verification export echouee pour {md_out.name}: {missing} image(s) locale(s) manquante(s)"
        )

    return len(local_refs), 0


def _register_dhs_export_in_db(hit: CatalogHit, md_out: Path, images_root: Path) -> None:
    if not DB_AVAILABLE:
        return

    images: list[Path] = []
    image_dir = images_root / md_out.stem
    if image_dir.exists():
        images.extend(sorted(path for path in image_dir.glob("*") if path.is_file()))

    identifiant_source = f"SRC-DHS-{hit.article_id}-{slugify(hit.lemma).upper()}"
    try:
        con = get_db_connection()
    except Exception as exc:
        print(f"  [warn] SQLite indisponible pour {md_out.name}: {exc}")
        return

    try:
        result = register_source_document(
            con,
            origin_path=md_out,
            identifiant_source=identifiant_source,
            titre=f"DHS: {hit.lemma}",
            url=hit.url,
            auteurs=["Dictionnaire historique de la Suisse"],
            langues="fr:100",
            type_source="secondaire",
            nombre_pages=1,
            categorie="autre",
            ner_status=1,
        )
        if result.get("action") == "error":
            print(f"  [warn] Insertion SQLite ignorée pour {md_out.name}: {result.get('reason', 'erreur inconnue')}")
            return

        for image_path in images:
            storage_status = register_source_document(
                con,
                origin_path=image_path,
                parent_path=md_out,
                ner_status=0,
            )
            if storage_status.get("action") == "error":
                print(
                    f"  [warn] Insertion SQLite ignorée pour {image_path.name}: "
                    f"{storage_status.get('reason', 'erreur inconnue')}"
                )
    finally:
        con.close()


def export_catalog_hit(hit: CatalogHit, out_dir: Path, images_root: Path, overwrite: bool, cfg: Config) -> bool:
    term_prefix = slugify(hit.term)
    md_name = build_md_filename(hit.term, hit.article_id, hit.lemma)
    md_out = out_dir / md_name

    if md_out.exists() and not overwrite:
        print(f"  [skip] Déjà présent: {md_out.name}")
        return False

    if cfg.dry_run:
        print(f"  [dry-run] {hit.lemma} -> {hit.url}")
        return False

    playwright, session = _start_browser_session(cfg)
    page = _get_or_create_work_page(session)
    assert page is not None
    try:
        print(f"  [info] CDP endpoint utilise: {session.cdp_endpoint}")
        page_html, status_code, _final_url = _load_article_html(page, hit.url, cfg)
        if is_cloudflare_challenge(page_html):
            raise RuntimeError("Cloudflare challenge")

        md_text, _meta = convert_dhs_html_to_md(page_html)

        def _browser_image_downloader(image_url: str, out_img: Path) -> bool:
            return _download_image_via_cdp_page(page, image_url, out_img, cfg.timeout * 1000)

        md_text, img_ok, img_fail = download_and_rewrite_images(
            md_text,
            md_out,
            images_root,
            browser_image_downloader=_browser_image_downloader,
        )
        md_text = prefix_downloaded_images(md_text, md_out, images_root, term_prefix)
        md_out.write_text(md_text, encoding="utf-8")

        verified_refs, _missing = verify_export_outputs(md_out)
        _register_dhs_export_in_db(hit, md_out, images_root)

        print(
            f"  [ok] {hit.lemma} ({status_code}) -> {md_out.name} "
            f"[images +{img_ok}/-{img_fail}, verify local_refs={verified_refs}]"
        )
        return True
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(f"Timeout Playwright: {exc}") from exc
    finally:
        _finish_browser_session(playwright, session, page)


def fetch_articles(args: argparse.Namespace, cfg: Config) -> Dict[str, int]:
    terms = [term.strip() for term in args.terms if term.strip()]
    if not terms:
        print("Aucun terme fourni. Utilise `--term`.", file=sys.stderr)
        return {"terms": 0, "hits": 0, "saved": 0, "errors": 0}

    csv_files = discover_catalog_csv_files(args.csv_dir, args.csv_glob)
    if not csv_files:
        print(
            f"Aucun CSV trouvé dans {args.csv_dir} avec le glob '{args.csv_glob}'.",
            file=sys.stderr,
        )
        return {"terms": len(terms), "hits": 0, "saved": 0, "errors": len(terms)}

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    images_root = out_dir / "images"
    images_root.mkdir(parents=True, exist_ok=True)

    stats = {"terms": len(terms), "hits": 0, "saved": 0, "errors": 0}
    for index, term in enumerate(terms, start=1):
        print(f"[fetch {index}/{len(terms)}] Recherche locale: {term}")
        hits = find_hits_in_catalogs(term, csv_files, args.max_hits)
        if not hits:
            print(f"  [miss] Aucun résultat CSV pour '{term}'")
            stats["errors"] += 1
            continue

        for hit in hits:
            stats["hits"] += 1
            try:
                if export_catalog_hit(hit, out_dir, images_root, args.overwrite, cfg):
                    stats["saved"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                print(f"  [error] {hit.lemma}: {type(exc).__name__}: {exc}")

            if cfg.sleep_s > 0:
                time.sleep(cfg.sleep_s)

    return stats


def build_config(args: argparse.Namespace) -> Config:
    return Config(
        timeout=args.timeout,
        sleep_s=max(0.0, args.sleep),
        user_agent=args.user_agent,
        dry_run=args.dry_run,
        cdp_url=args.cdp_url,
        pause_on_challenge=not args.no_pause_on_challenge,
    )


def main(argv: Sequence[str]) -> int:
    warn_legacy_flags(argv)
    args = parse_args(argv)
    cfg = build_config(args)

    stats = fetch_articles(args, cfg)
    print("Terminé.")
    print(json.dumps(stats, ensure_ascii=False))
    return 0 if args.terms else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

