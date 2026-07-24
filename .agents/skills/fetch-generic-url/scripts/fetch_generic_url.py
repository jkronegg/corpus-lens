#!/usr/bin/env python3
"""Télécharge des documents depuis des URLs génériques."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import pdfplumber

DEFAULT_OUT_DIR = Path("sources")
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_MAX_DOWNLOAD_ATTEMPTS = 4
REPO_ROOT = Path(__file__).resolve().parents[4]
DB_SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
DB_MODULE_PATH = DB_SCRIPTS_DIR / "db.py"

get_db_connection = None
upsert_source = None
source_exists_by_url = None
DB_AVAILABLE = False

try:
    spec = importlib.util.spec_from_file_location("named_entities_db_for_download", DB_MODULE_PATH)
    if spec and spec.loader:
        _db_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = _db_module
        spec.loader.exec_module(_db_module)
        get_db_connection = _db_module.get_connection
        upsert_source = _db_module.upsert_source
        source_exists_by_url = _db_module.source_exists_by_url
        DB_AVAILABLE = True
except Exception as e:
    print(f"[WARN] DB module not available: {e}")
    DB_AVAILABLE = False

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Document types and their common extensions
DOCUMENT_TYPES = {
    "pdf": [".pdf"],
    "html": [".html", ".htm"],
    "docx": [".docx"],
    "doc": [".doc"],
    "xlsx": [".xlsx"],
    "xls": [".xls"],
    "pptx": [".pptx"],
    "ppt": [".ppt"],
    "txt": [".txt"],
    "rtf": [".rtf"],
    "odt": [".odt"],
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".svg"}
WEBPAGE_DISCOVERY_HINTS = ("seance", "séance", "archive", "conseil", "communal", "asp", "page")


def _default_worklist_path(out_dir: Path, document_type: Optional[str], source_url: str = "") -> Path:
    """Return deterministic worklist path for resumable background downloads.

    Le nom inclut un hash court de l'URL source afin que deux instances
    lancées en parallèle pour des pages différentes n'écrivent pas dans
    le même fichier.
    """
    suffix = slugify(document_type or "document")
    url_tag = hashlib.md5((source_url or "").encode()).hexdigest()[:8]
    return out_dir / f"worklist_{suffix}_{url_tag}.json"


def _default_head_cache_path(out_dir: Path) -> Path:
    """Return shared persistent HEAD cache path for all worklists in out_dir."""
    return out_dir / "head_cache_shared.json"


def _load_head_cache(cache_path: Path, document_type: str) -> dict[str, bool]:
    """Load shared HEAD cache from disk and return section for document_type."""
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                section = data.get(str(document_type).lower(), {})
                if isinstance(section, dict):
                    return {str(k): bool(v) for k, v in section.items()}
        except Exception as e:
            print(f"[WARN] HEAD cache illisible ({cache_path}): {e}")
    return {}


def _save_head_cache(cache_path: Path, document_type: str, cache: dict[str, bool]) -> None:
    """Save shared HEAD cache section for document_type to disk."""
    full_cache: dict[str, dict[str, bool]] = {}
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                for k, v in existing.items():
                    if isinstance(v, dict):
                        full_cache[str(k)] = {str(url): bool(val) for url, val in v.items()}
        except Exception as e:
            print(f"[WARN] HEAD cache existant illisible ({cache_path}): {e}")

    full_cache[str(document_type).lower()] = {str(k): bool(v) for k, v in cache.items()}

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(full_cache, f, ensure_ascii=False, indent=2)


def slugify(value: str) -> str:
    """Convert text to URL-friendly slug."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "document"


def _clean_last_url_segment(segment: str) -> str:
    """Remove a technical extension from the last URL segment only."""
    value = unquote(segment or "").strip()
    if re.search(r"\.[a-z]{1,8}$", value, flags=re.IGNORECASE):
        cleaned = value.rsplit(".", 1)[0].strip()
        if cleaned:
            return cleaned
    return value


def url_storage_subdir(url: str) -> Path:
    """Build a stable relative storage directory from a source URL."""
    parsed = urlparse(url)
    raw_segments = [unquote(segment).strip() for segment in parsed.path.split("/") if segment.strip()]

    if len(raw_segments) > 1 and slugify(raw_segments[0]) in {"f", "fr", "de", "it", "en"}:
        raw_segments = raw_segments[1:]

    slug_segments: list[str] = []
    for index, segment in enumerate(raw_segments):
        normalized = _clean_last_url_segment(segment) if index == len(raw_segments) - 1 else segment
        slug_segment = slugify(normalized)
        if slug_segment:
            slug_segments.append(slug_segment)

    if slug_segments:
        return Path(*slug_segments)

    hostname = slugify(parsed.hostname or parsed.netloc or "document")
    return Path(hostname)


def page_storage_slug(url: str, title: str) -> str:
    """Build a stable page-specific slug for storing page assets.

    The URL hash avoids collisions when multiple pages share the same title.
    """
    base = slugify(title or "webpage")
    url_tag = hashlib.md5((url or "").encode()).hexdigest()[:8]
    return f"{base}_{url_tag}"


def yaml_escape(value: str) -> str:
    """Escape quotes for YAML."""
    return (value or "").replace('"', "'")


def normalize_whitespace(value: str) -> str:
    """Collapse all whitespace (including line breaks) into single spaces."""
    return re.sub(r"\s+", " ", value or "").strip()


def today_utc() -> str:
    """Return current UTC date as YYYY-MM-DD."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def publication_date_for_downloaded_file(path: Path) -> Optional[str]:
    """Return unknown publication date for PDFs; keep current default for other files."""
    if path.suffix.lower() == ".pdf":
        return None
    return today_utc()


def _to_iso_date(value: str) -> Optional[str]:
    """Try to parse a date value and return YYYY-MM-DD."""
    if not value:
        return None

    candidate = normalize_whitespace(value).replace("/", "-")
    candidate = re.sub(r"(\d{2})\.(\d{2})\.(\d{4})", r"\3-\2-\1", candidate)

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(candidate[:19], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", candidate)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def extract_document_publication_date(soup: BeautifulSoup) -> Optional[str]:
    """Extract publication date from common meta/time fields in HTML."""
    meta_names = {
        "article:published_time",
        "publishdate",
        "pubdate",
        "date",
        "dc.date",
        "dcterms.created",
        "dcterms.issued",
    }

    for meta in soup.find_all("meta"):
        key_raw = str(meta.get("property") or meta.get("name") or "")
        key = normalize_whitespace(key_raw.lower())
        content = str(meta.get("content") or "")
        if key in meta_names:
            parsed = _to_iso_date(content)
            if parsed:
                return parsed

    for time_tag in soup.find_all("time"):
        parsed = _to_iso_date(str(time_tag.get("datetime") or time_tag.get_text(" ", True)))
        if parsed:
            return parsed

    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Télécharge des documents depuis des URLs génériques.")
    parser.add_argument("--url", required=True, help="URL cible (document ou webpage)")
    parser.add_argument("--document-type", help="Type de document (pdf, html, docx, etc.)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Dossier de sortie")
    parser.add_argument("--dry-run", action="store_true", help="Valide l'URL sans télécharger")
    parser.add_argument("--max-redirects", type=int, default=DEFAULT_MAX_REDIRECTS, help="Max redirects à suivre")
    parser.add_argument("--follow-links", action="store_true", help="Télécharge les ressources liées (images)")
    parser.add_argument("--background-download", action=argparse.BooleanOptionalAction, default=True, help="Crée/alimente la file de travail puis lance le téléchargement en tâche de fond (actif par défaut; --no-background-download pour désactiver)")
    parser.add_argument("--worklist-file", type=Path, help="Fichier JSON de suivi des téléchargements (reprenable)")
    parser.add_argument("--max-download-attempts", type=int, default=DEFAULT_MAX_DOWNLOAD_ATTEMPTS, help="Nombre maximal d'essais par URL dans la file de travail")
    parser.add_argument("--run-worklist-worker", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _load_worklist(worklist_path: Path, document_type: str) -> dict:
    if worklist_path.exists():
        try:
            with open(worklist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                data.setdefault("document_type", document_type)
                data.setdefault("updated_at", _utc_timestamp())
                data.setdefault("run_status", "finished")
                data.setdefault("worker_pid", None)
                return data
        except Exception as e:
            print(f"[WARN] Worklist illisible ({worklist_path}): {e}")

    return {
        "document_type": document_type,
        "created_at": _utc_timestamp(),
        "updated_at": _utc_timestamp(),
        "run_status": "finished",
        "worker_pid": None,
        "items": [],
    }


def _worklist_run_status(worklist: dict) -> str:
    """Return normalized worklist run status."""
    status = str(worklist.get("run_status") or "").strip().lower()
    if status in {"running", "finished"}:
        return status

    active_statuses = {"pending", "probing", "downloading"}
    items = worklist.get("items", []) if isinstance(worklist.get("items"), list) else []
    if any(str(item.get("status") or "").lower() in active_statuses for item in items if isinstance(item, dict)):
        return "running"
    return "finished"


def _reset_worklist_and_log(worklist_path: Path, document_type: str) -> None:
    """Reset worklist JSON and matching log file to empty state."""
    fresh = {
        "document_type": document_type,
        "created_at": _utc_timestamp(),
        "updated_at": _utc_timestamp(),
        "run_status": "finished",
        "worker_pid": None,
        "items": [],
    }
    _save_worklist(worklist_path, fresh)

    log_path = worklist_path.with_suffix(".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write("")


def _prepare_worklist_for_new_run(worklist_path: Path, document_type: str) -> dict:
    """Check existing worklist state before starting a new run.

    - running  => refuse and suggest killing process
    - finished => reset JSON+LOG and allow restart
    """
    if not worklist_path.exists():
        return {"success": True, "action": "new"}

    worklist = _load_worklist(worklist_path, document_type)
    status = _worklist_run_status(worklist)
    pid = worklist.get("worker_pid")

    if status == "running":
        return {
            "success": False,
            "error": "Worklist déjà en cours d'exécution.",
            "worklist_file": str(worklist_path),
            "worker_pid": pid,
            "suggestion": f"Le processus semble encore actif. Tuez-le puis relancez (ex: Stop-Process -Id {pid} -Force)." if pid else "Le processus semble encore actif. Tuez-le puis relancez.",
        }

    _reset_worklist_and_log(worklist_path, document_type)
    return {"success": True, "action": "reset"}


def _save_worklist(worklist_path: Path, worklist: dict) -> None:
    worklist_path.parent.mkdir(parents=True, exist_ok=True)
    worklist["updated_at"] = _utc_timestamp()
    with open(worklist_path, "w", encoding="utf-8") as f:
        json.dump(worklist, f, ensure_ascii=False, indent=2)


def _queue_urls_in_worklist(
    worklist_path: Path,
    urls: list[str],
    document_type: str,
    requires_head_check: bool = False,
) -> dict:
    worklist = _load_worklist(worklist_path, document_type)
    index = {item.get("url"): item for item in worklist.get("items", []) if isinstance(item, dict) and item.get("url")}

    added = 0
    for url in urls:
        if url in index:
            continue
        worklist["items"].append(
            {
                "url": url,
                "status": "pending",
                "attempts": 0,
                "last_error": "",
                "output_file": "",
                "requires_head_check": requires_head_check,
                "updated_at": _utc_timestamp(),
            }
        )
        added += 1

    _save_worklist(worklist_path, worklist)
    return {"added": added, "total": len(worklist.get("items", []))}


def _process_worklist(
    worklist_path: Path,
    output_dir: Path,
    session: requests.Session,
    max_redirects: int,
    max_download_attempts: int,
    db_con,
) -> dict:
    worklist = _load_worklist(worklist_path, "document")
    downloaded_files: list[str] = []
    document_type = str(worklist.get("document_type") or "document")
    head_cache_path = _default_head_cache_path(output_dir)
    head_cache = _load_head_cache(head_cache_path, document_type)
    worklist["run_status"] = "running"
    worklist.setdefault("worker_pid", None)
    _save_worklist(worklist_path, worklist)

    for item in worklist.get("items", []):
        status = str(item.get("status") or "pending")
        attempts = int(item.get("attempts") or 0)
        if status in {"done", "skipped"}:
            continue
        if attempts >= max_download_attempts:
            continue

        doc_url = str(item.get("url") or "").strip()
        if not doc_url:
            continue

        if DB_AVAILABLE and db_con and callable(source_exists_by_url) and source_exists_by_url(db_con, doc_url):
            item["status"] = "skipped"
            item["last_error"] = "already_in_database"
            item["requires_head_check"] = False
            item["updated_at"] = _utc_timestamp()
            _save_worklist(worklist_path, worklist)
            continue

        needs_head_check = bool(item.get("requires_head_check"))
        item["status"] = "probing" if needs_head_check else "downloading"
        item["attempts"] = attempts + 1
        item["updated_at"] = _utc_timestamp()
        _save_worklist(worklist_path, worklist)

        if needs_head_check:
            if doc_url in head_cache:
                is_valid = head_cache[doc_url]
                print(f"[CACHE] HEAD check cached for {doc_url}: {is_valid}")
            else:
                is_valid = _looks_like_document_by_head(doc_url, [document_type], session, max_redirects)
                head_cache[doc_url] = is_valid
                _save_head_cache(head_cache_path, document_type, head_cache)
                print(f"[HEAD] Checked {doc_url}: {is_valid}")
            
            if not is_valid:
                item["status"] = "skipped"
                item["last_error"] = "head_not_matching_document_type"
                item["requires_head_check"] = False
                item["updated_at"] = _utc_timestamp()
                _save_worklist(worklist_path, worklist)
                continue

            item["requires_head_check"] = False
            item["status"] = "downloading"
            item["last_error"] = ""
            item["updated_at"] = _utc_timestamp()
            _save_worklist(worklist_path, worklist)

        preferred_name = Path(urlparse(doc_url).path).name or f"document_{attempts + 1}"
        temp_download_dir = output_dir / ".tmp_fetch_generic_url"
        temp_output_path = _download_file_with_metadata(
            doc_url,
            temp_download_dir,
            session,
            max_redirects,
            preferred_filename=preferred_name,
        )

        if temp_output_path:
            source_signature = generate_signature(str(temp_output_path))
            existing_sources: list[dict] = []
            if DB_AVAILABLE and db_con:
                existing_sources = _find_sources_by_signature(db_con, source_signature)

            if existing_sources:
                _warn_if_signature_url_mismatch(existing_sources, doc_url)
                try:
                    temp_output_path.unlink(missing_ok=True)
                except Exception as e:
                    print(f"[WARN] Impossible de supprimer le fichier temporaire {temp_output_path}: {e}")

                item["status"] = "skipped"
                item["last_error"] = "duplicate_signature_already_in_source"
                item["requires_head_check"] = False
                item["updated_at"] = _utc_timestamp()
                _save_worklist(worklist_path, worklist)
                continue

            output_path = _persist_temp_download(temp_output_path, output_dir)
            pdf_page_count = get_pdf_page_count(output_path)
            item["status"] = "done"
            item["last_error"] = ""
            item["output_file"] = str(output_path)
            downloaded_files.append(str(output_path))

            if DB_AVAILABLE and db_con and callable(upsert_source):
                source_entry = {
                    "signature": source_signature,
                    "identifiant_source": slugify(Path(output_path).stem),
                    "titre": Path(output_path).stem,
                    "date_publication": publication_date_for_downloaded_file(output_path),
                    "date_consultation": today_utc(),
                    "origine": doc_url,
                    "url": doc_url,
                    "auteurs": [],
                    "author": "",
                    "periodes": [],
                    "path": str(output_path),
                    "file_name": output_path.name,
                    "relative_path": output_path.relative_to(REPO_ROOT / "sources").as_posix() if (REPO_ROOT / "sources") in output_path.parents else output_path.name,
                    "ner_status": 0,
                    "nombre_pages": pdf_page_count,
                }
                result = upsert_source(db_con, source_entry)
                print(f"[DB] {result.get('action', 'unknown')}: {result.get('source_id')}")
        else:
            item["status"] = "failed"
            item["last_error"] = "download_failed"

        item["updated_at"] = _utc_timestamp()
        _save_worklist(worklist_path, worklist)

    items = worklist.get("items", [])
    done = sum(1 for i in items if i.get("status") == "done")
    failed = sum(1 for i in items if i.get("status") == "failed")
    pending = sum(1 for i in items if i.get("status") == "pending")
    probing = sum(1 for i in items if i.get("status") == "probing")
    skipped = sum(1 for i in items if i.get("status") == "skipped")
    exhausted = sum(1 for i in items if int(i.get("attempts") or 0) >= max_download_attempts and i.get("status") not in {"done", "skipped"})

    worklist["run_status"] = "finished"
    worklist["worker_pid"] = None
    worklist["finished_at"] = _utc_timestamp()
    _save_worklist(worklist_path, worklist)

    return {
        "success": True,
        "worklist_file": str(worklist_path),
        "downloaded_now": len(downloaded_files),
        "count": len(downloaded_files),
        "failed_count": failed,
        "failed_urls": [str(i.get("url")) for i in items if i.get("status") == "failed" and i.get("url")],
        "skipped_urls": [str(i.get("url")) for i in items if i.get("status") == "skipped" and i.get("url")],
        "already_indexed_urls": [str(i.get("url")) for i in items if i.get("last_error") == "already_in_database" and i.get("url")],
        "done": done,
        "failed": failed,
        "pending": pending,
        "probing": probing,
        "skipped": skipped,
        "exhausted": exhausted,
        "files": downloaded_files,
    }


def _start_background_worker(args: argparse.Namespace, worklist_path: Path) -> dict:
    """Start a detached worker process that consumes the worklist file."""
    script_path = Path(__file__).resolve()
    log_path = worklist_path.with_suffix(".log")

    command = [
        sys.executable,
        "-u",
        str(script_path),
        "--url",
        args.url,
        "--document-type",
        str(args.document_type),
        "--out-dir",
        str(args.out_dir),
        "--max-redirects",
        str(args.max_redirects),
        "--worklist-file",
        str(worklist_path),
        "--max-download-attempts",
        str(args.max_download_attempts),
        "--run-worklist-worker",
    ]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log_file:
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )

    worklist = _load_worklist(worklist_path, str(args.document_type))
    worklist["run_status"] = "running"
    worklist["worker_pid"] = process.pid
    _save_worklist(worklist_path, worklist)

    return {
        "started": True,
        "pid": process.pid,
        "worklist_file": str(worklist_path),
        "log_file": str(log_path),
    }


def get_content_type(url: str, session: requests.Session, max_redirects: int) -> tuple[str, Optional[str], bool]:
    """
    Determine content type by following redirects and checking headers.
    Returns (mime_type, extension, is_webpage).
    """
    try:
        response = session.head(url, timeout=10, allow_redirects=True, headers={"User-Agent": USER_AGENT})
        
        # Limite les redirects
        if len(response.history) > max_redirects:
            raise ValueError(f"Too many redirects ({len(response.history)} > {max_redirects})")
        
        # Obtenir le MIME type
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        
        # Extraire l'extension du chemin URL
        parsed = urlparse(response.url)
        path = parsed.path
        _, ext = Path(path).suffix or "", None
        if path:
            _, ext = path.rsplit(".", 1) if "." in path else (path, None)
            ext = f".{ext}" if ext else None
        
        # Déterminer si c'est une webpage
        is_webpage = content_type.startswith("text/html") or content_type.startswith("application/xhtml")
        
        return content_type, ext, is_webpage
    except Exception as e:
        print(f"[WARN] Error checking content type: {e}")
        return "", None, False


def download_file(url: str, output_path: Path, session: requests.Session, max_redirects: int) -> bool:
    """Download file from URL and save to output_path."""
    try:
        response = session.get(url, timeout=30, allow_redirects=True, headers={"User-Agent": USER_AGENT}, stream=True)
        
        if len(response.history) > max_redirects:
            print(f"[ERROR] Too many redirects ({len(response.history)} > {max_redirects})")
            return False
        
        if response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code} for {url}")
            return False
        
        # Limiter à 100MB
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > 100 * 1024 * 1024:
            print(f"[ERROR] File too large ({int(content_length) / 1024 / 1024:.1f}MB > 100MB)")
            return False
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"[OK] Downloaded {output_path.name}")
        return True
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        return False


def _filename_from_content_disposition(content_disposition: str) -> Optional[str]:
    """Extract filename from Content-Disposition header.
    
    Handles:
    - RFC 5987 style: filename*=UTF-8''... (possibly percent-encoded)
    - Standard form: filename="..." or filename=...
    - Embedded quotes in filenames: filename="name-"with"embedded"-quotes.pdf"
    """
    if not content_disposition:
        return None

    def _repair_mojibake(value: str) -> str:
        """Fix common UTF-8 decoded as Latin-1 artifacts (e.g. nÂ° -> n°)."""
        if not value or not any(token in value for token in ("Â", "Ã", "â")):
            return value
        try:
            repaired = value.encode("latin-1").decode("utf-8")
            if repaired:
                return repaired
        except UnicodeError:
            pass
        return value

    # RFC 5987 style: filename*=UTF-8''... (possibly percent-encoded)
    match = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", content_disposition, flags=re.IGNORECASE)
    if match:
        value = unquote(match.group(1).strip().strip('"'))
        value = _repair_mojibake(value)
        value = value.replace('"', "")
        return Path(value).name

    # Generic form: filename=... 
    # Handle both: filename="value" and filename=value
    # For embedded quotes, we extract everything between the first = and the first unescaped semicolon
    match = re.search(r'filename\s*=\s*(.+?)(?:;|$)', content_disposition, flags=re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        
        # Only strip outer quotes if they wrap the ENTIRE value
        # This preserves embedded quotes like: name-"embedded".pdf
        if value.startswith('"') and value.endswith('"'):
            # Check if removing outer quotes leaves a valid path
            inner = value[1:-1]
            # Only remove quotes if the inner value doesn't start/end with special chars
            # that would indicate malformed parsing
            if not (inner.count('"') == 0 or (inner.count('"') > 0 and inner.find('"') > 0)):
                # Has unmatched internal quotes, try to extract intelligently
                # Look for .pdf at the end and work backwards
                pdf_idx = inner.rfind('.pdf')
                if pdf_idx != -1:
                    value = inner[:pdf_idx + 4]
                else:
                    value = inner
            else:
                value = inner

        value = unquote(value)
        value = _repair_mojibake(value)
        value = value.replace('"', "")
        
        # Fallback: if value still has issues, extract the last quoted/unquoted segment ending with .pdf
        if '.pdf' in value.lower():
            # Extract from first letter/quote to last occurrence of .pdf
            parts = re.split(r'["\s;]+', value)
            for part in parts:
                if '.pdf' in part.lower():
                    return Path(part).name
            # If nothing worked, just try the whole value
            return Path(value).name
        
        return Path(value).name

    return None


def _guess_extension_from_content_type(content_type: str) -> Optional[str]:
    """Guess file extension from MIME type."""
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if not mime:
        return None
    return mimetypes.guess_extension(mime)


def _sanitize_filename(filename: str) -> str:
    """Make filename safe for local filesystem (especially Windows)."""
    # Remove control chars and Windows-forbidden characters.
    safe = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', "-", filename or "")
    safe = re.sub(r"\s+", " ", safe).strip(" .")
    safe = re.sub(r"-+", "-", safe)
    return safe or "document"


def _ensure_unique_path(path: Path) -> Path:
    """Avoid overwriting existing files by appending a numeric suffix."""
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _normalize_url_for_compare(url: str) -> str:
    """Normalize URL for stable comparison in dedup checks."""
    candidate = str(url or "").strip()
    if not candidate:
        return ""
    return candidate[:-1] if candidate.endswith("/") else candidate


def _source_url_for_comparison(row: dict) -> str:
    """Return the best URL-like value from a source row for comparisons."""
    url = str(row.get("url") or "").strip()
    if url:
        return url
    origin = str(row.get("origine") or "").strip()
    if origin.lower().startswith(("http://", "https://")):
        return origin
    return ""


def _find_sources_by_signature(db_con, signature: str) -> list[dict]:
    """Return existing source rows for a given source signature."""
    if not db_con or not signature:
        return []
    rows = db_con.execute(
        """
        SELECT id, signature, url, origine, identifiant_source, titre
        FROM source
        WHERE signature = ?
        ORDER BY id
        """,
        (signature,),
    ).fetchall()
    return [dict(row) for row in rows]


def _warn_if_signature_url_mismatch(existing_sources: list[dict], new_url: str) -> None:
    """Warn when same content signature is already indexed under another URL."""
    normalized_new = _normalize_url_for_compare(new_url)
    for source_row in existing_sources:
        existing_url = _source_url_for_comparison(source_row)
        normalized_existing = _normalize_url_for_compare(existing_url)
        if normalized_existing and normalized_existing != normalized_new:
            print(
                "[WARN] Signature déjà présente avec une URL différente "
                f"(source_id={source_row.get('id')}, existing_url={existing_url}, new_url={new_url}). "
                "Deux URLs différentes pointent probablement vers le même document réel."
            )


def _persist_temp_download(temp_path: Path, output_dir: Path) -> Path:
    """Move a temporary download into final output_dir with collision-safe naming."""
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = _ensure_unique_path(output_dir / temp_path.name)
    shutil.move(str(temp_path), str(final_path))
    return final_path


def _download_file_with_metadata(
    url: str,
    output_dir: Path,
    session: requests.Session,
    max_redirects: int,
    preferred_filename: Optional[str] = None,
) -> Optional[Path]:
    """Download a file and derive a stable filename from headers/final URL."""
    try:
        response = session.get(url, timeout=30, allow_redirects=True, headers={"User-Agent": USER_AGENT}, stream=True)

        if len(response.history) > max_redirects:
            print(f"[ERROR] Too many redirects ({len(response.history)} > {max_redirects})")
            return None

        if response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code} for {url}")
            return None

        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > 100 * 1024 * 1024:
            print(f"[ERROR] File too large ({int(content_length) / 1024 / 1024:.1f}MB > 100MB)")
            return None

        filename = _filename_from_content_disposition(response.headers.get("content-disposition", ""))
        if not filename:
            final_name = Path(urlparse(response.url).path).name
            filename = final_name or preferred_filename or "document"

        if "." not in filename:
            guessed_ext = _guess_extension_from_content_type(response.headers.get("content-type", ""))
            if guessed_ext:
                filename = f"{filename}{guessed_ext}"

        filename = _sanitize_filename(filename)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = _ensure_unique_path(output_dir / filename)

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"[OK] Downloaded {output_path.name}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        return None


def is_document_url(url: str, document_types: list[str]) -> bool:
    """Check if URL likely points to a document of specified type."""
    parsed = urlparse(url)
    path = parsed.path.lower()

    extensions = []
    for doc_type in document_types:
        extensions.extend(DOCUMENT_TYPES.get(doc_type.lower(), []))

    return any(path.endswith(ext) for ext in extensions)


def _response_matches_document_type(response: requests.Response, document_types: list[str]) -> bool:
    """Return True when the final response looks like one of the requested document types."""
    content_type = (response.headers.get("content-type", "") or "").split(";")[0].strip().lower()
    final_url = getattr(response, "url", "") or ""
    final_path = urlparse(final_url).path.lower()
    content_disposition = response.headers.get("content-disposition", "") or ""
    disposition_filename = _filename_from_content_disposition(content_disposition)
    disposition_path = disposition_filename.lower() if disposition_filename else ""

    extensions = []
    for doc_type in document_types:
        extensions.extend(DOCUMENT_TYPES.get(doc_type.lower(), []))

    # 1. Check final URL path extension
    if any(final_path.endswith(ext) for ext in extensions):
        return True

    # 2. Check content-disposition filename extension (PDF with embedded quotes)
    if disposition_path and any(disposition_path.endswith(ext) for ext in extensions):
        return True

    # 3. Check content-type MIME first (most reliable)
    if content_type == "application/pdf" and "pdf" in [d.lower() for d in document_types]:
        return True

    # 4. Check for "attachment" with .pdf in disposition (covers embedded quotes case)
    if "pdf" in [d.lower() for d in document_types]:
        if "attachment" in content_disposition.lower() and ".pdf" in content_disposition.lower():
            return True
        if content_type == "application/octet-stream" and ".pdf" in content_disposition.lower():
            # Sometimes servers return octet-stream for PDFs but have .pdf in disposition
            return True

    # 5. Generic MIME type matching
    if not content_type:
        return False


    if "html" in document_types and (content_type.startswith("text/html") or content_type.startswith("application/xhtml")):
        return True

    for doc_type in document_types:
        doc_type = doc_type.lower()
        if doc_type in content_type:
            return True

    return False


def _looks_like_document_by_head(url: str, document_types: list[str], session: requests.Session, max_redirects: int) -> bool:
    """Resolve proxy links by probing their content-type with HEAD."""
    try:
        response = session.head(url, timeout=10, allow_redirects=True, headers={"User-Agent": USER_AGENT})
        if len(response.history) > max_redirects:
            return False
        return _response_matches_document_type(response, document_types)
    except Exception:
        return False


def extract_candidate_links_for_background(html: str, base_url: str, document_types: list[str]) -> list[str]:
    """Collect candidate links quickly so HEAD validation can run later in the background worker."""
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()
    base_netloc = urlparse(base_url).netloc.lower()

    for link in soup.find_all("a", href=True):
        href = (link.get("href") or "").strip()
        if not href:
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in {"http", "https"}:
            continue

        normalized_url = parsed._replace(fragment="").geturl()
        if not normalized_url:
            continue

        same_site = parsed.netloc.lower() == base_netloc
        if same_site or is_document_url(normalized_url, document_types):
            links.add(normalized_url)

    return sorted(links)


def find_document_links(
    html: str,
    base_url: str,
    document_types: list[str],
    session: Optional[requests.Session] = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> list[str]:
    """Find all links pointing to documents of specified type."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    head_cache: dict[str, bool] = {}
    
    extensions = []
    for doc_type in document_types:
        extensions.extend(DOCUMENT_TYPES.get(doc_type.lower(), []))
    
    for link in soup.find_all("a", href=True):
        href = link.get("href", "").strip()
        if not href:
            continue
        
        full_url = urljoin(base_url, href)

        # Requested behavior: decide document eligibility from HTTP HEAD headers.
        if session is not None:
            if full_url not in head_cache:
                head_cache[full_url] = _looks_like_document_by_head(full_url, document_types, session, max_redirects)
            if head_cache[full_url]:
                links.append(full_url)
            continue

        # Fallback when no session is provided (e.g., isolated unit tests).
        if any(full_url.lower().endswith(ext) for ext in extensions):
            links.append(full_url)
    
    return list(set(links))  # Remove duplicates


def _is_candidate_subpage_url(base_url: str, candidate_url: str) -> bool:
    """Restrict crawling to same-site, likely-related pages."""
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)

    if not candidate.scheme.startswith("http"):
        return False
    if candidate.netloc != base.netloc:
        return False

    path = (candidate.path or "").lower()
    query = (candidate.query or "").lower()
    full = f"{path}?{query}"
    if any(token in full for token in ("mailto:", "javascript:")):
        return False

    # Keep pages in the same section or clearly related to council archives/sessions.
    base_dir = (base.path.rsplit("/", 1)[0] + "/").lower()
    in_same_section = path.startswith(base_dir)
    has_hint = any(hint in full for hint in WEBPAGE_DISCOVERY_HINTS)
    return in_same_section or has_hint


def collect_document_links_from_webpages(
    start_url: str,
    document_types: list[str],
    session: requests.Session,
    max_redirects: int,
) -> tuple[list[str], list[str]]:
    """Analyze only the provided page URL and collect matching document links from it."""
    try:
        response = session.get(start_url, timeout=30, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except Exception as e:
        print(f"[WARN] Failed to fetch page {start_url}: {e}")
        return [], []

    page_doc_links = find_document_links(
        response.text,
        start_url,
        document_types,
        session=session,
        max_redirects=max_redirects,
    )
    return sorted(set(page_doc_links)), [start_url]


def collect_candidate_links_from_webpages_for_background(
    start_url: str,
    document_types: list[str],
    session: requests.Session,
) -> tuple[list[str], list[str]]:
    """Fetch the page and queue candidate links; HEAD validation will happen in the worker."""
    try:
        response = session.get(start_url, timeout=30, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except Exception as e:
        print(f"[WARN] Failed to fetch page {start_url}: {e}")
        return [], []

    page_candidate_links = extract_candidate_links_for_background(
        response.text,
        start_url,
        document_types,
    )
    return page_candidate_links, [start_url]


def extract_images_from_html(html: str, base_url: str) -> list[str]:
    """Extract all image URLs from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    images = []
    
    for img in soup.find_all("img", src=True):
        src = img.get("src", "").strip()
        if src:
            full_url = urljoin(base_url, src)
            images.append(full_url)
    
    return list(set(images))  # Remove duplicates


def download_image(url: str, images_dir: Path, session: requests.Session) -> Optional[Path]:
    """Download image and return relative path."""
    try:
        response = session.get(url, timeout=20, headers={"User-Agent": USER_AGENT}, stream=True)
        
        if response.status_code != 200:
            return None
        
        # Generate filename from URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        parsed = urlparse(url)
        filename = Path(parsed.path).name or f"image_{url_hash}.jpg"
        
        images_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = images_dir / filename
        
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return filepath
    except Exception as e:
        print(f"[WARN] Failed to download image {url}: {e}")
        return None


def generate_signature(path: str) -> str:
    """Generate signature from file content when possible.

    If ``path`` points to an existing file, hash the file bytes so renames
    keep the same technical identifier. Otherwise, fall back to hashing the
    provided string (useful for URLs/front matter before file creation).
    """
    file_path = Path(path)
    if file_path.exists() and file_path.is_file():
        digest = hashlib.md5()
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    return hashlib.md5(path.encode()).hexdigest()


def get_pdf_page_count(path: Path) -> int:
    """Return number of pages for a PDF file, or -1 when unavailable."""
    try:
        if path.suffix.lower() != ".pdf":
            return -1
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception as e:
        print(f"[WARN] Impossible de compter les pages PDF ({path}): {e}")
        return -1


def html_to_markdown(html: str, base_url: str, output_dir: Path, session: requests.Session,
                     follow_links: bool = False, page_assets_dir: Optional[Path] = None) -> tuple[str, Optional[Path], list[Path]]:
    """Convert HTML to Markdown with front matter and download images."""
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract title and metadata
    title = soup.find("title")
    page_title = normalize_whitespace(title.get_text(" ", True)) if title else "Untitled"

    # Extract main content
    content_parts = []
    content_parts.append("## Page 1\n")
    
    # Extract text from body
    body = soup.find("body") or soup
    for element in body.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"]):
        text = normalize_whitespace(element.get_text(" ", True))
        if text:
            if element.name and element.name.startswith("h"):
                level = int(element.name[1])
                content_parts.append(f"{'#' * (level + 1)} {text}\n")
            elif element.name == "li":
                content_parts.append(f"- {text}\n")
            else:
                content_parts.append(f"{text}\n\n")
    
    markdown_content = "\n".join(content_parts)
    
    # Download images if requested
    image_paths = []
    if follow_links:
        image_urls = extract_images_from_html(html, base_url)
        images_dir = (page_assets_dir or (output_dir / slugify(page_title))) / "images"
        for img_url in image_urls[:10]:  # Limit to 10 images
            img_path = download_image(img_url, images_dir, session)
            if img_path:
                image_paths.append(img_path)
    
    return markdown_content, None, image_paths


def generate_front_matter(
    title: str,
    url: str,
    document_type: str = "webpage",
    date_publication: Optional[str] = None,
) -> str:
    """Generate YAML front matter."""
    date_consultation = today_utc()
    publication = date_publication or date_consultation
    
    return f"""---
title: "{yaml_escape(title)}"
url: "{yaml_escape(url)}"
date_publication: {publication}
date_consultation: {date_consultation}
transformation_by: "skill fetch-generic-url"
sources: ["{yaml_escape(url)}"]
document_type: {document_type}
signature: "{generate_signature(url)}"
---

"""


def handle_direct_document(url: str, output_dir: Path, session: requests.Session, 
                           max_redirects: int, db_con) -> dict:
    """Handle direct document download."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if DB_AVAILABLE and db_con and callable(source_exists_by_url) and source_exists_by_url(db_con, url):
        return {
            "success": True,
            "skipped": True,
            "reason": "already_in_database",
            "url": url,
        }
    
    # Get filename from URL
    parsed = urlparse(url)
    filename = Path(parsed.path).name or "document"
    if not "." in filename:
        _, ext = mimetypes.guess_extension(url) or ("", "")
        filename = f"{filename}{ext}"
    
    output_path = _download_file_with_metadata(
        url,
        output_dir,
        session,
        max_redirects,
        preferred_filename=filename,
    )

    if not output_path:
        return {"success": False, "error": "Download failed"}
    
    # Register in database if available
    if DB_AVAILABLE and db_con and callable(upsert_source):
        signature = generate_signature(str(output_path))
        pdf_page_count = get_pdf_page_count(output_path)
        source_entry = {
            "signature": signature,
            "identifiant_source": slugify(parsed.path),
            "titre": output_path.stem,
            "date_publication": publication_date_for_downloaded_file(output_path),
            "date_consultation": today_utc(),
            "origine": url,
            "url": url,
            "auteurs": [],
            "author": "",
            # TODO pourquoi avoir deux champs pour les auteurs ? conserver uniquement "auteurs"
            "periodes": [],
            "path": str(output_path),
            "file_name": output_path.name,
            "relative_path": output_path.relative_to(REPO_ROOT / "sources").as_posix() if (REPO_ROOT / "sources") in output_path.parents else output_path.name,
            "ner_status": 0,
            "nombre_pages": pdf_page_count,
        }

        result = upsert_source(db_con, source_entry)
        print(f"[DB] {result.get('action', 'unknown')}: {result.get('source_id')}")
    
    return {"success": True, "file": str(output_path)}


def handle_webpage_with_document_type(url: str, output_dir: Path, document_type: str, 
                                     session: requests.Session, max_redirects: int, db_con,
                                     worklist_file: Optional[Path] = None, max_download_attempts: int = DEFAULT_MAX_DOWNLOAD_ATTEMPTS,
                                     background_download: bool = False) -> dict:
    """Handle webpage with document_type specified - find and download documents."""
    try:
        if background_download:
            doc_links, crawled_pages = collect_candidate_links_from_webpages_for_background(
                url,
                [document_type],
                session,
            )
        else:
            # Collect links from the page and relevant subpages (archives/paginated sections).
            doc_links, crawled_pages = collect_document_links_from_webpages(
                url,
                [document_type],
                session,
                max_redirects,
            )
        print(f"[INFO] Crawled pages: {len(crawled_pages)}")
        print(f"[INFO] Candidate {document_type} links: {len(doc_links)}")
        
        if not doc_links:
            return {"success": False, "error": f"No {document_type} documents found"}
        
        resolved_worklist = (worklist_file or _default_worklist_path(output_dir, document_type, url)).resolve()
        preparation = _prepare_worklist_for_new_run(resolved_worklist, document_type)
        if not preparation.get("success"):
            return preparation

        if preparation.get("action") == "reset":
            print(f"[INFO] Worklist terminée détectée, reset de {resolved_worklist.name} et du log associé.")

        queue_info = _queue_urls_in_worklist(
            resolved_worklist,
            doc_links,
            document_type,
            requires_head_check=background_download,
        )

        if background_download:
            worker_info = _start_background_worker(
                argparse.Namespace(
                    url=url,
                    document_type=document_type,
                    out_dir=output_dir,
                    max_redirects=max_redirects,
                    max_download_attempts=max_download_attempts,
                ),
                resolved_worklist,
            )
            return {
                "success": True,
                "mode": "background",
                "worklist_file": str(resolved_worklist),
                "queued_added": queue_info["added"],
                "queued_total": queue_info["total"],
                "crawled_pages": crawled_pages,
                "worker": worker_info,
            }

        worklist_result = _process_worklist(
            resolved_worklist,
            output_dir,
            session,
            max_redirects,
            max_download_attempts,
            db_con,
        )
        worklist_result["crawled_pages"] = crawled_pages
        worklist_result["queued_added"] = queue_info["added"]
        worklist_result["queued_total"] = queue_info["total"]
        return worklist_result
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_webpage_without_document_type(url: str, output_dir: Path, follow_links: bool,
                                         session: requests.Session, db_con) -> dict:
    """Handle webpage without document_type - convert to Markdown."""
    try:
        response = session.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        parsed = urlparse(url)
        page_title = normalize_whitespace((soup.title.get_text(" ", True) if soup.title else "")) or (parsed.path.split("/")[-1] or "webpage")
        date_publication = extract_document_publication_date(soup)
        page_assets_dir = output_dir / page_storage_slug(url, page_title)
        
        # Convert to Markdown
        markdown_content, _, image_paths = html_to_markdown(html, url, output_dir, session, follow_links, page_assets_dir=page_assets_dir)
        
        # Generate filename
        output_dir.mkdir(parents=True, exist_ok=True)
        md_filename = f"{slugify(page_title)}.md"
        md_path = output_dir / md_filename
        
        # Add front matter
        front_matter = generate_front_matter(page_title, url, "webpage", date_publication=date_publication)
        full_content = front_matter + markdown_content
        
        # Write Markdown
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(full_content)
        
        print(f"[OK] Saved webpage to {md_path}")
        
        # Register in database if available
        files_registered = []
        if DB_AVAILABLE and db_con and callable(upsert_source):
            signature = generate_signature(str(md_path))
            source_entry = {
                "signature": signature,
                "identifiant_source": slugify(md_filename),
                "titre": page_title,
                "date_publication": today_utc(),
                "date_consultation": today_utc(),
                "origine": url,
                "auteurs": ["generic-url-downloader"],
                "periodes": [],
                "path": str(md_path),
                "file_name": md_path.name,
                "relative_path": md_path.relative_to(REPO_ROOT / "sources").as_posix() if (REPO_ROOT / "sources") in md_path.parents else md_path.name,
                "author": "generic-url-downloader",
                "ner_status": 1,
            }
            
            result = upsert_source(db_con, source_entry)
            print(f"[DB] {result.get('action', 'unknown')}: {result.get('source_id')}")
            files_registered.append(str(md_path))
            
            # Register images with parent relationship
            for img_path in image_paths:
                img_entry = {
                    "signature": generate_signature(str(img_path)),
                    "identifiant_source": slugify(img_path.name),
                    "titre": img_path.name,
                    "date_publication": today_utc(),
                    "date_consultation": today_utc(),
                    "origine": url,
                    "auteurs": ["generic-url-downloader"],
                    "periodes": [],
                    "path": str(img_path),
                    "file_name": img_path.name,
                    "relative_path": img_path.relative_to(REPO_ROOT / "sources").as_posix() if (REPO_ROOT / "sources") in img_path.parents else img_path.name,
                    "author": "generic-url-downloader",
                    "parent_path": str(md_path),
                    "ner_status": 0,
                }
                
                result = upsert_source(db_con, img_entry)
                print(f"[DB] Image registered: {result.get('source_id')}")
                files_registered.append(str(img_path))
        
        return {
            "success": True,
            "files": [str(md_path)] + [str(p) for p in image_paths],
            "markdown": str(md_path),
            "images": [str(p) for p in image_paths],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    args = parse_args()
    
    # Normalize output directory
    out_dir = args.out_dir.resolve()
    
    # Create session
    session = requests.Session()
    
    # Get database connection if available
    db_con = None
    if DB_AVAILABLE and callable(get_db_connection):
        try:
            db_con = get_db_connection()
        except Exception as e:
            print(f"[WARN] Database connection failed: {e}")
    
    # Detect content type
    content_type, ext, is_webpage = get_content_type(args.url, session, args.max_redirects)

    if is_webpage and args.document_type:
        out_dir = out_dir / url_storage_subdir(args.url)
    
    if args.dry_run:
        result = {
            "url": args.url,
            "content_type": content_type,
            "is_webpage": is_webpage,
            "extension": ext,
            "document_type": args.document_type,
        }
        print(json.dumps(result, indent=2))
        return
    
    if args.run_worklist_worker:
        if not args.worklist_file:
            print(json.dumps({"success": False, "error": "--worklist-file is required with --run-worklist-worker"}, indent=2))
            return
        result = _process_worklist(
            args.worklist_file.resolve(),
            out_dir,
            session,
            args.max_redirects,
            args.max_download_attempts,
            db_con,
        )
        print(json.dumps(result, indent=2))
        return

    # Handle based on type
    if is_webpage and args.document_type:
        result = handle_webpage_with_document_type(
            args.url,
            out_dir,
            args.document_type,
            session,
            args.max_redirects,
            db_con,
            args.worklist_file.resolve() if args.worklist_file else None,
            args.max_download_attempts,
            background_download=args.background_download,
        )
    elif is_webpage:
        result = handle_webpage_without_document_type(
            args.url, out_dir, args.follow_links, session, db_con
        )
    else:
        if args.document_type:
            print("[WARN] --document-type ignoré car URL directe ne permettant pas d'avoir des listes de documents.")
        result = handle_direct_document(args.url, out_dir, session, args.max_redirects, db_con)
    
    # Output result
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
