import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import TextIO, Optional

ROOT = Path(__file__).resolve().parents[4]
SOURCES_DIR = ROOT / "sources"
AUTHORS_PATH = SOURCES_DIR / "auteurs.json"
NAMED_ENTITIES_DB_SCRIPTS_DIR = (
    ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
)
if str(NAMED_ENTITIES_DB_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(NAMED_ENTITIES_DB_SCRIPTS_DIR))

from db import (
    get_connection as get_named_entities_connection,
    list_source_documents as list_indexed_source_documents,
    list_sources as list_indexed_sources,
    replace_sources as replace_indexed_sources,
    upsert_source,
)

import importlib.util

NER_EXTRACT_SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "manage-named-entities-db"
    / "scripts"
    / "extract_entities_spacy.py"
)
_NER_MODULE = None

PAGE_LABEL_PATTERN = r"\d+(?:\s*[-–]\s*\d+)?"
PAGE_HEADER_RE = re.compile(rf"^##\s*Page\s+({PAGE_LABEL_PATTERN})\s*$", flags=re.MULTILINE)
ALT_PAGE_HEADER_RE = re.compile(
    rf"^\s{{0,3}}(?:#|##|###)?\s*Page\s+({PAGE_LABEL_PATTERN})\s*$",
    flags=re.MULTILINE | re.IGNORECASE,
)

MONTHS = {
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
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "dezember": 12,
}

PRIMARY_BINARY_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".xls",
    ".ods",
    ".csv",
    ".tsv",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".svg",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".odt",
    ".odp",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".svg"}
INDEX_META_FILES = {
    "auteurs.json"
}
LOCK_FILE_PREFIXES = ("~$",)
INDEX_LOCK_FILE = ROOT / ".indexer-sources.lock"
NER_GLOBAL_LOG_FILE = ROOT / "indexation_sources.log"


def _load_ner_module():
    """Charge le module NER une seule fois dans le processus courant."""
    global _NER_MODULE
    if _NER_MODULE is not None:
        return _NER_MODULE

    if not NER_EXTRACT_SCRIPT.exists():
        return None

    spec = importlib.util.spec_from_file_location("extract_entities_spacy_shared", NER_EXTRACT_SCRIPT)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _NER_MODULE = module
    return _NER_MODULE


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def slug_token(value: str) -> str:
    value = strip_accents(value)
    value = value.upper()
    value = re.sub(r"[^A-Z0-9]+", "-", value)
    return value.strip("-")


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def to_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def load_known_authors(path: Path) -> list[str]:
    payload = load_json_list(path)
    authors = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("nom")
        if isinstance(name, str) and name.strip():
            authors.append(name.strip())
    # Déterminisme + suppression doublons
    return sorted(set(authors), key=lambda x: slug_token(x))



def normalize_page_label(label: str) -> str:
    value = (label or "").strip()
    value = value.replace("–", "-")
    value = re.sub(r"\s*-\s*", "-", value)
    return value



def parse_md_page_sections(content: str) -> list[tuple[str, str]]:
    matches = list(PAGE_HEADER_RE.finditer(content))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        label = normalize_page_label(match.group(1))
        body = content[start:end]
        sections.append((label, body))
    return sections


def normalize_md_page_sections(md_path: Path) -> bool:
    """Normalise des variantes d'en-tête vers `## Page X` quand c'est non ambigu."""
    if not md_path.exists():
        return False
    content = md_path.read_text(encoding="utf-8", errors="replace")
    if PAGE_HEADER_RE.search(content):
        return False

    converted = ALT_PAGE_HEADER_RE.sub(lambda m: f"## Page {normalize_page_label(m.group(1))}", content)
    if converted != content and PAGE_HEADER_RE.search(converted):
        md_path.write_text(converted, encoding="utf-8")
        return True
    return False


def ensure_single_page_section(md_path: Path) -> bool:
    """Ajoute une section `## Page 1` pour les Markdown non paginés.

    Preserve un éventuel frontmatter YAML en tête de fichier.
    """
    if not md_path.exists():
        return False

    content = md_path.read_text(encoding="utf-8", errors="replace")
    if PAGE_HEADER_RE.search(content):
        return False

    stripped = content.strip()
    if not stripped:
        return False

    # Frontmatter YAML en tete: --- ... ---
    if stripped.startswith("---"):
        fm = re.match(r"(?s)^\s*---\n.*?\n---\s*\n?", content)
        if fm:
            head = fm.group(0).rstrip() + "\n\n"
            body = content[fm.end():].strip()
            if body:
                md_path.write_text(f"{head}## Page 1\n\n{body}\n", encoding="utf-8")
                return True
            return False

    md_path.write_text(f"## Page 1\n\n{stripped}\n", encoding="utf-8")
    return True


def has_valid_page_sections(md_path: Path) -> bool:
    if not md_path.exists():
        return False
    content = md_path.read_text(encoding="utf-8", errors="replace")
    headers = re.findall(rf"^##\s*Page\s+({PAGE_LABEL_PATTERN})\s*$", content, flags=re.MULTILINE)
    if not headers:
        return False
    return True


def _read_index_lock(lock_path: Path) -> dict:
    if not lock_path.exists():
        return {}
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _try_acquire_file_lock(lock_handle: TextIO) -> bool:
    """Le lock n’est plus basé sur “PID vivant + fichier lock” (fragile entre “mondes”), mais sur :
    • acquisition non bloquante d’un verrou de fichier partagé (msvcrt.locking sur Windows, fcntl.flock sur Unix),
    • conservation du descripteur ouvert pendant toute l’exécution,
    • libération explicite en finally.
    Résultat : si une instance tourne déjà, la seconde obtient Indexation déjà en cours. au lieu de passer à tort.
    """
    if os.name == "nt":
        import msvcrt

        try:
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    # Unix version
    import fcntl

    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _release_file_lock(lock_handle: TextIO) -> None:
    if os.name == "nt":
        import msvcrt

        lock_handle.seek(0)
        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _acquire_index_lock(lock_path: Path) -> tuple[TextIO | None, str]:
    """Acquire an inter-process lock shared by all runtimes on the same filesystem."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_path.open("a+", encoding="utf-8")

    if not _try_acquire_file_lock(lock_handle):
        payload = _read_index_lock(lock_path)
        try:
            existing_pid = int(payload.get("pid") or 0)
            details = f" (pid={existing_pid})" if existing_pid > 0 else ""
        except Exception:
            details = ""
        lock_handle.close()
        return None, f"Indexation déjà en cours{details}."

    new_payload = {
        "pid": os.getpid(),
        "started_at": datetime.now().isoformat(),
        "script": str(Path(__file__).resolve()),
    }
    lock_handle.seek(0)
    lock_handle.truncate()
    json.dump(new_payload, lock_handle, ensure_ascii=False, indent=2)
    lock_handle.write("\n")
    lock_handle.flush()
    return lock_handle, f"Lock acquis: {lock_path}"


def _release_index_lock(lock_handle: TextIO) -> None:
    try:
        _release_file_lock(lock_handle)
    except Exception:
        pass
    finally:
        lock_handle.close()


def md_stats(md_path: Path) -> tuple[int, str, bool]:
    if not md_path.exists():
        return -1, "", False
    content = md_path.read_text(encoding="utf-8", errors="replace")
    pages = len(re.findall(rf"^##\s*Page\s+({PAGE_LABEL_PATTERN})\s*$", content, flags=re.MULTILINE))
    text = re.sub(r"^## Page \d+\s*$", "", content, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return (pages if pages > 0 else -1, text[:500], len(text) > 0)


def _parse_front_matter_fields(md_path: Path) -> dict[str, str | list]:
    """Extrait tous les champs du front matter YAML, en préservant les listes."""
    if not md_path.exists():
        return {}
    content = md_path.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"(?s)^---\n(.*?)\n---\n?", content)
    if not match:
        return {}

    fields: dict[str, str | list] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        # Détecte les listes YAML (commence par [ ou -)
        if value.startswith("[") and value.endswith("]"):
            # Format [item1, item2, ...]
            items = value[1:-1].split(",")
            fields[key] = [_strip_yaml_quotes(item.strip()) for item in items]
        elif value.startswith("-"):
            # Format YAML list (rarement dans front matter simple)
            fields[key] = [_strip_yaml_quotes(value)]
        else:
            # Chaîne simple
            fields[key] = _strip_yaml_quotes(value)
    return fields


def _strip_yaml_quotes(value: str) -> str:
    """Supprime les guillemets YAML d'une valeur."""
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def load_source_json_metadata(source_path: Path) -> dict:
    """Charge les métadonnées depuis <document>.source.json."""
    if source_path.suffix.lower() not in PRIMARY_BINARY_EXTENSIONS:
        return {}

    source_json_path = source_path.with_stem(source_path.stem).with_suffix(".source.json")
    # Vérifier si le chemin contient des traits d'union multiples avant d'en ajouter un
    root_name = principal_root_name(source_path)
    source_json_path = source_path.parent / f"{root_name}.source.json"

    if not source_json_path.exists():
        return {}

    try:
        return json.loads(source_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def markdown_language_distribution(md_path: Path) -> str | None:
    fields = _parse_front_matter_fields(md_path)
    value = (fields.get("language_distribution") or "").strip()
    return value or None


def detect_languages(text: str) -> list[str]:
    t = text.lower()
    langs = []
    if any(w in t for w in [" le ", " la ", " les ", " des ", " suisse", "votation", "referendum"]):
        langs.append("fr")
    if any(w in t for w in [" der ", " die ", " das ", " und ", "bundes"]):
        langs.append("de")
    if any(w in t for w in [" il ", " della ", " degli ", " svizzera"]):
        langs.append("it")
    if any(w in t for w in [" the ", " and ", " switzerland"]):
        langs.append("en")
    if not langs:
        langs = ["fr"]
    return sorted(set(langs))


def normalize_numeric_date(day: str, month: str, year: str) -> str:
    try:
        return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return "0000-00-00"


def normalize_named_date(day: str, month_name: str, year: str) -> str:
    month_value = MONTHS.get(month_name.strip(" .").lower())
    if month_value is None:
        return "0000-00-00"
    return normalize_numeric_date(day, str(month_value), year)


def detect_date_publication_from_md(md_path: Path) -> str:
    if not md_path.exists():
        return "0000-00-00"
    content = md_path.read_text(encoding="utf-8", errors="replace")
    first_page = content.split("## Page 2", 1)[0]
    pages = re.split(r"(?m)^## Page \d+\s*$", content)
    page_bodies = [re.sub(r"\s+", " ", p).strip() for p in pages if p.strip()]
    last_page = page_bodies[-1] if page_bodies else ""

    # Priorité aux zones où la date est généralement indiquée (début / fin du document).
    prioritized_texts = [first_page, last_page]
    search_texts = prioritized_texts + [content]

    numeric_patterns = [
        r"date de publication\s*[:\-]?\s*(\d{1,2})[./](\d{1,2})[./](\d{4})",
        r"date de mise en ligne\s*[:\-]?\s*(\d{1,2})[./](\d{1,2})[./](\d{4})",
        r"version du\s*[:\-]?\s*(\d{1,2})[./](\d{1,2})[./](\d{4})",
        r"(?:redaction|rédaction)\s*[:\-]?\s*(\d{1,2})[./](\d{1,2})[./](\d{4})",
        r"publi[ée]\s+le\s*(\d{1,2})[./](\d{1,2})[./](\d{4})",
        r"r[ée]dig[ée]\s+le\s*(\d{1,2})[./](\d{1,2})[./](\d{4})",
    ]
    for text_block in search_texts:
        for pattern in numeric_patterns:
            match = re.search(pattern, text_block, flags=re.IGNORECASE)
            if match:
                value = normalize_numeric_date(*match.groups())
                if value != "0000-00-00":
                    return value

    named_patterns = [
        r"\((?:du|vom)\s+(\d{1,2})\.?\s+([A-Za-zÀ-ÿ]+)\.?\s+(\d{4})\.?\)",
        r"date de publication\s*[:\-]?\s*(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})",
        r"publi[ée]\s+le\s+(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})",
    ]
    for text_block in search_texts:
        for pattern in named_patterns:
            match = re.search(pattern, text_block, flags=re.IGNORECASE)
            if match:
                value = normalize_named_date(*match.groups())
                if value != "0000-00-00":
                    return value

    # Fenêtres proches des mentions d'auteur/rédaction (souvent en tête/pied du document).
    nearby_author_windows = re.findall(
        r"(?is)(?:autrice\/auteur|autrice|auteur|autor|rédaction|redaction|publié\s+le|version\s+du).{0,120}",
        first_page + "\n" + last_page,
    )
    for window in nearby_author_windows:
        for day, month, year in re.findall(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", window):
            value = normalize_numeric_date(day, month, year)
            if value != "0000-00-00":
                return value
        for day, month_name, year in re.findall(r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\b", window):
            value = normalize_named_date(day, month_name, year)
            if value != "0000-00-00":
                return value

    candidates = set()
    for zone in prioritized_texts:
        for day, month, year in re.findall(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", zone):
            value = normalize_numeric_date(day, month, year)
            if value != "0000-00-00":
                candidates.add(value)
        for day, month_name, year in re.findall(r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\b", zone):
            value = normalize_named_date(day, month_name, year)
            if value != "0000-00-00":
                candidates.add(value)
    if len(candidates) == 1:
        return next(iter(candidates))

    return "0000-00-00"


def md_first_page_text(md_path: Path) -> str:
    if not md_path.exists():
        return ""
    content = md_path.read_text(encoding="utf-8", errors="replace")
    first_page = content.split("## Page 2", 1)[0]
    return re.sub(r"\s+", " ", first_page).strip()


def md_last_page_text(md_path: Path) -> str:
    if not md_path.exists():
        return ""
    content = md_path.read_text(encoding="utf-8", errors="replace")
    pages = re.split(r"(?m)^## Page \d+\s*$", content)
    page_bodies = [re.sub(r"\s+", " ", p).strip() for p in pages if p.strip()]
    return page_bodies[-1] if page_bodies else ""


def detect_authors_from_md(md_path: Path, known_authors: list[str]) -> list[str]:
    first_page = md_first_page_text(md_path)
    last_page = md_last_page_text(md_path)
    search_zone = (first_page + "\n" + last_page).strip()
    if not search_zone:
        return []

    normalized_search_zone = slug_token(search_zone)
    found: list[str] = []

    # 1) Extraction directe via libellés usuels
    direct_patterns = [
        r"Autrice/Auteur\s*:\s*([^|\n]+)",
        r"Autrice\s*:\s*([^|\n]+)",
        r"Auteur\s*:\s*([^|\n]+)",
        r"Autor\s*:\s*([^|\n]+)",
        r"Auteurs?\s*:\s*([^|\n]+)",
        r"Publié\s+par\s*:?\s*([^|\n]+)",
    ]
    for pattern in direct_patterns:
        for match in re.findall(pattern, search_zone, flags=re.IGNORECASE):
            raw = re.split(r"\b(?:Traduction|Version du|DOI|ISSN|ISBN)\b", match, maxsplit=1, flags=re.IGNORECASE)[0]
            chunks = re.split(r";| et | and | und ", raw)
            for chunk in chunks:
                candidate = chunk.strip(" .:-\t\n\r")
                if is_probable_author_name(candidate):
                    found.append(candidate)

    # 2) Appui par registre d'auteurs connus
    for known in known_authors:
        if slug_token(known) and slug_token(known) in normalized_search_zone:
            found.append(known)

    # Nettoyage / dédoublonnage déterministe
    cleaned = []
    seen = set()
    for name in found:
        # Supprime les faux positifs de type rôle ou libellé générique
        if re.match(r"^(traduction|version du|conditions d'utilisation)$", name, flags=re.IGNORECASE):
            continue
        key = slug_token(name)
        if key and key not in seen:
            seen.add(key)
            cleaned.append(name)
    return cleaned


def is_probable_author_name(value: str) -> bool:
    candidate = re.sub(r"\s+", " ", (value or "")).strip(" .")
    if len(candidate) < 3 or len(candidate) > 80:
        return False
    if re.search(r"https?://|www\.|@", candidate, flags=re.IGNORECASE):
        return False
    if re.search(r"\b(archives|copyright|droits|contact|version|page|doi|issn|isbn|conf[ée]rence)\b", candidate, flags=re.IGNORECASE):
        return False
    # Évite les lignes OCR verbeuses: 5 mots max pour un nom de personne.
    tokens = [t for t in re.split(r"\s+", candidate) if t]
    if len(tokens) > 5:
        return False
    # Un nom doit contenir des lettres et aucun chiffre.
    if not re.search(r"[A-Za-zÀ-ÿ]", candidate):
        return False
    if re.search(r"\d", candidate):
        return False

    # Validation morphologique des tokens (nom propre + particules usuelles).
    particles = {"de", "du", "des", "d", "von", "van", "di", "da", "del", "della", "la", "le"}
    raw_tokens = [t.strip(" ,.;:()[]{}\"'") for t in candidate.split() if t.strip(" ,.;:()[]{}\"'")]
    if not raw_tokens:
        return False
    for token in raw_tokens:
        low = token.lower()
        if low in particles:
            continue
        if re.fullmatch(r"[A-ZÀ-Ý]\.?", token):
            continue
        if re.fullmatch(r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]+", token):
            continue
        # Autorise aussi les formes tout en majuscules (OCR / petites capitales)
        if re.fullmatch(r"[A-ZÀ-Ý'\-]{2,}", token):
            continue
        return False
    return True


def sanitize_author_candidates(authors: list[str], known_authors: list[str]) -> list[str]:
    known_keys = {slug_token(a) for a in known_authors}
    out = []
    seen = set()
    for raw in authors:
        candidate = re.sub(r"\s+", " ", (raw or "")).strip(" .")
        if not candidate:
            continue
        key = slug_token(candidate)
        if not key:
            continue
        if key in known_keys or is_probable_author_name(candidate):
            if key not in seen:
                seen.add(key)
                out.append(candidate)
    return out


def compact_author_list(authors: list[str]) -> list[str]:
    """Supprime les entrées d'auteur trop partielles lorsqu'une forme plus complète est présente."""
    cleaned = [a.strip() for a in authors if isinstance(a, str) and a.strip()]
    if not cleaned:
        return []

    to_drop = set()
    lowered = [a.lower() for a in cleaned]
    for i, ai in enumerate(cleaned):
        token_i = ai.strip().lower()
        # Un seul mot (souvent nom de famille seul) -> à supprimer si une forme plus complète existe.
        if len(token_i.split()) == 1:
            for j, aj in enumerate(cleaned):
                if i == j:
                    continue
                lj = lowered[j]
                if (
                    lj.startswith(token_i + ",")
                    or lj.startswith(token_i + " ")
                    or ("," in lj and re.search(rf"\b{re.escape(token_i)}\b", lj))
                    or (len(lj.split()) > 1 and re.search(rf"\b{re.escape(token_i)}\b", lj))
                ):
                    to_drop.add(i)
                    break

    out = []
    seen = set()
    for idx, name in enumerate(cleaned):
        if idx in to_drop:
            continue
        key = slug_token(name)
        if key and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def author_family_name(author: str) -> str:
    """Extrait un nom de famille canonique pour construire identifiant_source."""
    value = re.sub(r"\s+", " ", (author or "")).strip(" .")
    if not value:
        return "Inconnu"

    # Forme "Nom, Prénom"
    if "," in value:
        family = value.split(",", 1)[0].strip()
        return family or "Inconnu"

    # Retire les titres fréquents
    value = re.sub(r"^(dr|docteur|prof|professeur|mr|mme|m\.)\s+", "", value, flags=re.IGNORECASE)
    tokens = [t for t in value.split(" ") if t]
    if not tokens:
        return "Inconnu"

    return tokens[-1]


def source_creation_date(path: Path) -> str:
    try:
        ts = path.stat().st_ctime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except OSError:
        return "0000-00-00"


def source_key_from_path(path: Path) -> str:
    """Clé canonique d'une source indépendamment du suffixe .pdf/.md."""
    rel = to_rel(path)
    rel = re.sub(r"\.(pdf|md)$", "", rel, flags=re.IGNORECASE)
    return rel


def principal_root_name(path: Path) -> str:
    stem = path.stem
    return stem.split(".", 1)[0]


def derivation_depth(path: Path) -> int:
    stem = path.stem
    return stem.count(".")


def _is_local_markdown_asset(raw_ref: str) -> bool:
    ref = (raw_ref or "").strip().strip('"\'')
    if not ref:
        return False
    lowered = ref.lower()
    if lowered.startswith(("http://", "https://", "data:", "mailto:", "#")):
        return False
    return True


def _extract_markdown_asset_refs(content: str) -> list[str]:
    refs: list[str] = []

    # Markdown image syntax: ![alt](path "title")
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", content):
        raw = match.group(1).strip()
        if not raw:
            continue
        # Keep only URL/path segment before optional title.
        ref = raw.split()[0].strip()
        refs.append(ref)

    # HTML img tags in markdown.
    for match in re.finditer(r"<img[^>]*src=[\"']([^\"']+)[\"'][^>]*>", content, flags=re.IGNORECASE):
        refs.append(match.group(1).strip())

    return refs


def collect_embedded_markdown_images(md_paths: list[Path]) -> set[Path]:
    embedded: set[Path] = set()
    for md_path in md_paths:
        if not md_path.exists():
            continue
        content = md_path.read_text(encoding="utf-8", errors="replace")
        for raw_ref in _extract_markdown_asset_refs(content):
            if not _is_local_markdown_asset(raw_ref):
                continue

            ref = raw_ref.split("#", 1)[0].split("?", 1)[0].strip()
            if not ref:
                continue

            target = (md_path.parent / ref).resolve()
            if target.exists() and target.suffix.lower() in IMAGE_EXTENSIONS:
                embedded.add(target)
    return embedded


def _resolve_frontmatter_source_to_parent_path(md_path: Path, raw_source: str) -> str | None:
    """Résout la valeur `source` du front matter vers un `parent_path` repo-relatif."""
    value = (raw_source or "").strip().replace("\\", "/")
    if not value:
        return None
    if value.lower().startswith(("http://", "https://", "data:", "mailto:")):
        return None

    candidates: list[Path] = []

    # Cas 1: chemin repo-relatif explicite (souvent `sources/...`).
    if value.startswith("sources/"):
        candidates.append((ROOT / value).resolve())

    # Cas 2: chemin relatif au markdown courant.
    candidates.append((md_path.parent / value).resolve())

    # Cas 3: chemin relatif à la racine du repo.
    candidates.append((ROOT / value).resolve())

    for candidate in candidates:
        try:
            return to_rel(candidate)
        except ValueError:
            continue

    return None


def _collect_derived_documents_from_frontmatter(candidate_files: list[Path]) -> dict[str, list[dict]]:
    """Retourne un mapping `parent_path` -> liste de documents dérivés via front matter `source`."""
    by_parent: dict[str, list[dict]] = {}

    for file_path in sorted(candidate_files, key=lambda p: to_rel(p)):
        if file_path.suffix.lower() != ".md":
            continue

        fields = _parse_front_matter_fields(file_path)
        source_value = fields.get("source")
        if not isinstance(source_value, str) or not source_value.strip():
            continue

        parent_path = _resolve_frontmatter_source_to_parent_path(file_path, source_value)
        if not parent_path:
            continue

        file_rel = to_rel(file_path)
        parent_abs = ROOT / parent_path
        try:
            path_relatif = file_path.relative_to(parent_abs.parent).as_posix()
        except ValueError:
            path_relatif = file_path.name

        by_parent.setdefault(parent_path, []).append(
            {
                "fichier": file_path.name,
                "path_relatif": path_relatif,
                "path": file_rel,
                "author": resolve_derived_author(file_path),
                "ner_status": 1,
            }
        )

    for parent, items in by_parent.items():
        items.sort(key=lambda item: item["path"])

    return by_parent


def _normalize_author_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts)
    return ""


def _author_from_json_payload(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""

    for key in ("author", "auteur", "authors", "auteurs"):
        author = _normalize_author_value(payload.get(key))
        if author:
            return author

    # Fallback courant pour certains exports: auteur imbriqué dans metadata.
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("author", "auteur", "authors", "auteurs"):
            author = _normalize_author_value(metadata.get(key))
            if author:
                return author
    return ""


def resolve_derived_author(derived_path: Path) -> str:
    """Résout l'auteur d'un document dérivé (Markdown/JSON) avec fallback sidecar .source.json."""
    if not derived_path.exists():
        return ""

    suffix = derived_path.suffix.lower()

    if suffix == ".md":
        fields = _parse_front_matter_fields(derived_path)
        for key in ("author", "auteur", "authors", "auteurs"):
            author = _normalize_author_value(fields.get(key))
            if author:
                return author

    if suffix == ".json":
        try:
            payload = json.loads(derived_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = None
        author = _author_from_json_payload(payload)
        if author:
            return author

    # Fallback: cherche un sidecar .source.json pour les artefacts dérivés/binaire.
    sidecar = derived_path.parent / f"{principal_root_name(derived_path)}.source.json"
    if sidecar.exists() and sidecar.resolve() != derived_path.resolve():
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = None
        author = _author_from_json_payload(payload)
        if author:
            return author

    return ""


def normalize_periodes(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str) and re.match(r"^\d{4}-\d{4}$", item):
            out.append(item)
    out = sorted(set(out))
    return out[:3] if out else []


def detect_periodes_from_md(
    md_path: Path,
    fallback_value: object,
    interest_start_year: int = 1918,
    interest_end_year: int = 1939,
) -> list[str]:
    if not md_path.exists():
        return normalize_periodes(fallback_value)

    content = md_path.read_text(encoding="utf-8", errors="replace")
    content = re.sub(rf"^##\s*Page\s+({PAGE_LABEL_PATTERN})\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"https?://\S+", "", content)

    years_count: dict[int, int] = {}
    explicit_ranges: list[tuple[int, int]] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        # Evite les années bibliographiques techniques (ISBN/ISSN/DOI, métadonnées de scan).
        if any(tag in lower for tag in [
            "isbn", "issn", "doi", "object number", "objektnummer",
            "date de consultation", "date de collecte", "consulté le", "captured on",
            "url", "titre:", "title:", "plakat", "publication:", "veroeffentlichung:",
            "design:", "entwurf:", "auteur:", "author:", "client:", "print:", "druck:",
            "impression:", "dimensions", "format:", "camp:", "lager:", "bilddatei", "fichier image",
        ]):
            continue

        for a, b in re.findall(r"\b(1[89]\d{2}|20\d{2})\s*[-–]\s*(1[89]\d{2}|20\d{2})\b", line):
            start = int(a)
            end = int(b)
            if 1800 <= start <= end <= 2100:
                explicit_ranges.append((start, end))

        for y in re.findall(r"\b(1[89]\d{2}|20\d{2})\b", line):
            year = int(y)
            if 1800 <= year <= 2100:
                years_count[year] = years_count.get(year, 0) + 1

    candidate_ranges: list[tuple[int, int]] = []
    candidate_ranges.extend(explicit_ranges)

    if years_count:
        # Priorité aux années récurrentes; fallback sur les plus fréquentes.
        years = sorted(y for y, c in years_count.items() if c >= 2)
        if not years:
            years = [y for y, _ in sorted(years_count.items(), key=lambda kv: (-kv[1], kv[0]))[:12]]
            years.sort()

        start = years[0]
        prev = years[0]
        for year in years[1:]:
            if year <= prev + 1:
                prev = year
                continue
            candidate_ranges.append((start, prev))
            start = year
            prev = year
        candidate_ranges.append((start, prev))

    if not candidate_ranges:
        return normalize_periodes(fallback_value)

    # Fusion déterministe des plages qui se chevauchent ou sont adjacentes.
    candidate_ranges.sort(key=lambda r: (r[0], r[1]))
    merged: list[tuple[int, int]] = []
    for start, end in candidate_ranges:
        if not merged:
            merged.append((start, end))
            continue
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    # Priorise les périodes couvrant la plage d'intérêt, puis les plages les plus longues.
    def rank_period(item: tuple[int, int]) -> tuple[int, int, int]:
        s, e = item
        start_bound = min(interest_start_year, interest_end_year)
        end_bound = max(interest_start_year, interest_end_year)
        overlap = 1 if not (e < start_bound or s > end_bound) else 0
        span = e - s
        return (-overlap, -span, s)

    merged.sort(key=rank_period)
    selected = merged[:3]
    selected.sort(key=lambda r: (r[0], r[1]))

    normalized = [f"{s:04d}-{e:04d}" for s, e in selected]
    return normalize_periodes(normalized)


def normalize_langues(value: object, excerpt: str) -> list[str]:
    allowed = {"fr", "de", "it", "en"}
    if isinstance(value, list):
        langs = [x for x in value if isinstance(x, str) and x in allowed]
        langs = sorted(set(langs))
        if langs:
            return langs
    return detect_languages(excerpt)


def normalize_doi(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    # URL DOI -> identifiant DOI
    m_url = re.search(r"doi\.org/(10\.\d{4,9}/[^\s\]\[\)\(\"'<>]+)", raw, flags=re.IGNORECASE)
    if m_url:
        return m_url.group(1).rstrip(".,;:)")

    # DOI explicite
    m_doi = re.search(r"\b(10\.\d{4,9}/[^\s\]\[\)\(\"'<>]+)", raw, flags=re.IGNORECASE)
    if m_doi:
        return m_doi.group(1).rstrip(".,;:)")

    return ""


def normalize_isbn(value: str) -> str:
    raw = (value or "").upper().strip()
    if not raw:
        return ""
    raw = re.sub(r"[^0-9X]", "", raw)

    # ISBN-10 checksum
    if len(raw) == 10 and re.match(r"^\d{9}[0-9X]$", raw):
        total = 0
        for idx, ch in enumerate(raw):
            val = 10 if (idx == 9 and ch == "X") else int(ch)
            total += val * (10 - idx)
        if total % 11 == 0:
            return raw
        return ""

    # ISBN-13 checksum
    if len(raw) == 13 and re.match(r"^\d{13}$", raw):
        total = 0
        for idx, ch in enumerate(raw[:12]):
            weight = 1 if idx % 2 == 0 else 3
            total += int(ch) * weight
        expected = (10 - (total % 10)) % 10
        if expected == int(raw[12]):
            return raw
        return ""

    return ""


def normalize_issn(value: str) -> str:
    raw = (value or "").upper().strip()
    if not raw:
        return ""
    raw = re.sub(r"[^0-9X]", "", raw)
    if len(raw) != 8 or not re.match(r"^\d{7}[0-9X]$", raw):
        return ""

    # Validation checksum ISSN (ISO 3297):
    # somme(d1*8 + d2*7 + ... + d7*2 + check*1) % 11 == 0
    total = 0
    for idx, ch in enumerate(raw[:7]):
        total += int(ch) * (8 - idx)
    check_char = raw[7]
    check_value = 10 if check_char == "X" else int(check_char)
    total += check_value
    if total % 11 != 0:
        return ""

    return f"{raw[:4]}-{raw[4:]}"


def detect_doi_from_md(md_path: Path) -> str:
    if not md_path.exists():
        return ""

    content = md_path.read_text(encoding="utf-8", errors="replace")
    # Priorité aux premières pages (métadonnées bibliographiques) puis fallback global.
    first_page = content.split("## Page 2", 1)[0]

    doi = normalize_doi(first_page)
    if doi:
        return doi

    return normalize_doi(content)


def detect_isbn_from_md(md_path: Path) -> str:
    if not md_path.exists():
        return ""

    content = md_path.read_text(encoding="utf-8", errors="replace")
    first_page = content.split("## Page 2", 1)[0]

    patterns = [
        r"\bISBN(?:-1[03])?\s*[:\-]?\s*([0-9Xx\-\s]{10,20})",
        r"\b(97[89][0-9\-\s]{10,20})\b",
    ]

    for text_block in [first_page, content]:
        for pattern in patterns:
            for match in re.findall(pattern, text_block, flags=re.IGNORECASE):
                value = normalize_isbn(match)
                if value:
                    return value
    return ""


def detect_issn_from_md(md_path: Path) -> str:
    if not md_path.exists():
        return ""

    content = md_path.read_text(encoding="utf-8", errors="replace")
    first_page = content.split("## Page 2", 1)[0]

    # Ne détecte que les occurrences explicitement étiquetées ISSN
    # pour éviter les faux positifs de type périodes (ex: 1920-1930).
    patterns = [
        r"\bISSN\s*[:\-]?\s*([0-9]{4}\s*[-]?\s*[0-9Xx]{4})",
    ]

    for text_block in [first_page, content]:
        for pattern in patterns:
            for match in re.findall(pattern, text_block, flags=re.IGNORECASE):
                value = normalize_issn(match)
                if value:
                    return value
    return ""


def compute_pertinence(
    type_source: str,
    categorie: str,
    date_publication: str,
    periodes: list[str],
    is_readable: bool,
    has_authors: bool,
    period_interest_start_year: int,
    period_interest_end_year: int,
) -> float:
    # Base neutre
    score = 0.35

    if not is_readable:
        return 0.0

    # Type de source
    if type_source == "primaire":
        score += 0.30
    else:
        score += 0.10

    # Catégorie documentaire
    if categorie == "document officiel":
        score += 0.20
    elif categorie == "discours":
        score += 0.12
    elif categorie == "rapport":
        score += 0.08
    elif categorie == "presse":
        score += 0.05

    # Bonus si auteurs identifiés
    if has_authors:
        score += 0.05

    start_bound = min(period_interest_start_year, period_interest_end_year)
    end_bound = max(period_interest_start_year, period_interest_end_year)

    # Fiabilité temporelle (date explicite)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_publication)) and date_publication != "0000-00-00":
        score += 0.08
        try:
            year = int(date_publication[:4])
            # Légère prime si la date est dans la période d'étude.
            if start_bound <= year <= end_bound:
                score += 0.07
        except ValueError:
            pass

    # Prime de couverture de la période cible
    for period in periodes:
        m = re.match(r"^(\d{4})-(\d{4})$", period)
        if not m:
            continue
        p_start = int(m.group(1))
        p_end = int(m.group(2))
        if not (p_end < start_bound or p_start > end_bound):
            score += 0.05
            break
        score += 0.05

    # Clamp + arrondi déterministe
    score = min(1.0, max(0.0, score))
    return round(score, 2)


def detect_categorie_from_md(md_path: Path, title: str) -> str:
    if not md_path.exists():
        return "autre"

    content = md_path.read_text(encoding="utf-8", errors="replace")
    # On privilégie la première page, mais on garde une fenêtre globale pour les cas OCR incomplets.
    first_page = content.split("## Page 2", 1)[0]
    text = (first_page + "\n" + content[:4000]).lower()
    text = strip_accents(text)
    title_l = strip_accents((title or "").lower())

    def has_any(keywords: list[str]) -> bool:
        return any(k in text or k in title_l for k in keywords)

    # Règles déterministes par priorité.
    if has_any([
        "conseil federal",
        "assemblee federale",
        "feuille federale",
        "chancellerie federale",
        "message du conseil federal",
        "organisation militaire. modification de la loi",
        "bundesrat",
        "bundesgesetz",
        "botschaft",
        "office des nations unies",
    ]):
        return "document officiel"

    if has_any([
        "discours",
        "allocution",
        "speech",
        "declaration",
        "intervention",
        "prise de parole",
    ]):
        return "discours"

    if has_any([
        "rapport",
        "etude",
        "these",
        "analyse",
        "summary",
        "zusammenfassung",
        "revue suisse d'histoire",
        "politique etrangere",
        "doi",
    ]):
        return "rapport"

    if has_any([
        "le temps",
        "journal",
        "presse",
        "redaction",
        "publie le",
        "blog.",
        "news",
    ]):
        return "presse"

    return "autre"


def detect_type_source_from_md(md_path: Path, title: str, date_publication: str, categorie: str) -> str:
    if not md_path.exists():
        return "secondaire"

    content = md_path.read_text(encoding="utf-8", errors="replace")
    first_page = content.split("## Page 2", 1)[0]
    text = (first_page + "\n" + content[:5000]).lower()
    text = strip_accents(text)
    title_l = strip_accents((title or "").lower())

    def has_any(keywords: list[str]) -> bool:
        return any(k in text or k in title_l for k in keywords)

    # Sources explicitement secondaires (encyclopédies, articles de synthèse, analyses tardives).
    if has_any([
        "wikipedia",
        "dictionnaire historique de la suisse",
        "dhs",
        "clio texte",
        "etude",
        "analyse",
        "blog",
        "focus",
        "revue",
        "politique etrangere",
    ]):
        return "secondaire"

    year = 0
    if re.match(r"^\d{4}-", str(date_publication)):
        try:
            year = int(str(date_publication)[:4])
        except ValueError:
            year = 0

    # Indices de source primaire (documents institutionnels / contemporains des événements).
    strong_primary_markers = has_any([
        "message du conseil federal",
        "conseil federal",
        "assemblee federale",
        "feuille federale",
        "arrete du parlement",
        "parlamentsberatung",
        "conseil des etats",
        "conseil national",
        "propositions de la commission",
        "passer a la discussion des articles",
        "abanderung des bundesgesetzes",
        "chancellerie federale",
        "organisation militaire. modification de la loi",
        "proces-verbal",
    ])

    medium_primary_markers = has_any([
        "votation",
        "referendum",
        "discours",
        "allocution",
        "declaration officielle",
    ])

    # Marqueurs institutionnels forts => primaire même si date manquante.
    if strong_primary_markers:
        return "primaire"

    if medium_primary_markers:
        return "primaire"

    # Raccourci cohérent avec la catégorie si la date est dans la période étudiée.
    if categorie in {"document officiel", "discours"}:
        return "primaire"

    return "secondaire"


def is_generic_resume(value: str) -> bool:
    normalized = slug_token(value or "")
    if not normalized:
        return True
    generic_values = {
        slug_token("Extraction automatique du contenu source."),
        slug_token("Résumé automatique"),
        slug_token("Resume automatique"),
        slug_token("N/A"),
    }
    return normalized in generic_values


def build_resume_from_md(md_path: Path) -> str:
    if not md_path.exists():
        return ""

    content = md_path.read_text(encoding="utf-8", errors="replace")
    # On résume le texte extrait, pas les marqueurs techniques de pagination.
    content = re.sub(r"^## Page \d+\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"https?://\S+", "", content)

    lines = []
    for line in content.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^\d+\s+sur\s+\d+", s, flags=re.IGNORECASE):
            continue
        if re.search(r"\b(menu|accueil|contact|cookies|conditions d'utilisation|protection des données)\b", s, flags=re.IGNORECASE):
            continue
        lines.append(s)

    text = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected = []
    for sentence in sentences:
        s = sentence.strip(" -\t\n\r")
        if len(s) < 40 or len(s) > 280:
            continue
        if not re.search(r"[A-Za-zÀ-ÿ]{4}", s):
            continue
        selected.append(s)
        if len(selected) == 2:
            break

    if selected:
        return " ".join(selected)

    # Fallback: premier segment suffisamment informatif.
    informative_lines = [
        ln for ln in lines
        if len(ln.split()) >= 5 and re.search(r"[A-Za-zÀ-ÿ]{4}", ln)
    ]
    fallback = (informative_lines[0] if informative_lines else text[:220]).strip()
    if not fallback or len(re.findall(r"[A-Za-zÀ-ÿ]", fallback)) < 10:
        return "Texte source trop bruité pour extraire un résumé factuel fiable."
    if not fallback.endswith("."):
        fallback += "."
    return fallback


def normalize_entry(
    entry: dict,
    source_path: Path,
    md_path: Path,
    excerpt: str,
    page_count: int,
    is_readable: bool,
    known_authors: list[str],
    langues_value: str | None,
    md_metadata: dict | None = None,
    source_json_metadata: dict | None = None,
    period_interest_start_year: int = 1918,
    period_interest_end_year: int = 1939,
) -> dict:
    md_metadata = md_metadata or {}
    source_json_metadata = source_json_metadata or {}

    # Ré-identification systématique: on recalcule d'abord depuis le .md,
    # puis on retombe sur la valeur existante seulement si aucune date fiable n'est détectée.
    detected_date_publication = detect_date_publication_from_md(md_path)
    existing_date_publication = str(entry.get("date_publication") or "0000-00-00")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", detected_date_publication) and detected_date_publication != "0000-00-00":
        date_publication = detected_date_publication
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", existing_date_publication):
        date_publication = existing_date_publication
    else:
        date_publication = "0000-00-00"

    date_consultation = entry.get("date_consultation") or "0000-00-00"
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_consultation)) or date_consultation == "0000-00-00":
        date_consultation = source_creation_date(source_path)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_consultation):
        date_consultation = "0000-00-00"

    # Titre: priorité au front matter, puis à l'entrée existante, puis au nom du fichier
    title = str(md_metadata.get("titre") or md_metadata.get("title") or entry.get("titre") or source_path.stem.replace("_", " ")).strip()

    # Auteurs: combiner front matter, entrée existante et détection dans le document
    authors_from_entry = entry.get("auteurs") if isinstance(entry.get("auteurs"), list) else []
    authors_from_md = []
    # Front matter peut avoir 'auteur' ou 'auteurs'
    if "auteur" in md_metadata:
        val = md_metadata["auteur"]
        if isinstance(val, list):
            authors_from_md = val
        elif isinstance(val, str):
            authors_from_md = [val]
    elif "auteurs" in md_metadata:
        val = md_metadata["auteurs"]
        if isinstance(val, list):
            authors_from_md = val
        elif isinstance(val, str):
            authors_from_md = [val]
    
    authors = [a.strip() for a in (authors_from_md + authors_from_entry) if isinstance(a, str) and a.strip()]
    authors = sanitize_author_candidates(authors, known_authors)
    
    # Détection dans le document: uniquement si on n'a pas d'auteurs du front matter
    if not authors_from_md:
        detected_authors = detect_authors_from_md(md_path, known_authors)
        detected_authors = sanitize_author_candidates(detected_authors, known_authors)
        if detected_authors:
            authors = detected_authors + [a for a in authors if slug_token(a) not in {slug_token(x) for x in detected_authors}]
    authors = compact_author_list(authors)
    first_author = author_family_name(authors[0]) if authors else "Inconnu"
    year = date_publication[:4] if re.match(r"^\d{4}-", date_publication) else "0000"
    identifiant_source_base = f"SRC-{slug_token(first_author)}-{year}-{slug_token(title)}"

    detected_categorie = detect_categorie_from_md(md_path, title)
    categorie = detected_categorie
    if categorie == "autre":
        existing_categorie = entry.get("categorie", "autre")
        if existing_categorie in {"presse", "document officiel", "discours", "rapport"}:
            categorie = existing_categorie

    detected_type_source = detect_type_source_from_md(md_path, title, date_publication, categorie)
    type_source = detected_type_source
    if type_source not in {"primaire", "secondaire"}:
        existing_type_source = entry.get("type_source", "secondaire")
        type_source = existing_type_source if existing_type_source in {"primaire", "secondaire"} else "secondaire"

    periodes = detect_periodes_from_md(
        md_path,
        None,
        interest_start_year=period_interest_start_year,
        interest_end_year=period_interest_end_year,
    )
    pertinence = compute_pertinence(
        type_source=type_source,
        categorie=categorie,
        date_publication=date_publication,
        periodes=periodes,
        is_readable=is_readable,
        has_authors=bool(authors),
        period_interest_start_year=period_interest_start_year,
        period_interest_end_year=period_interest_end_year,
    )

    pages_value = entry.get("nombre_pages", page_count)
    try:
        pages_value = int(pages_value)
    except (TypeError, ValueError):
        pages_value = page_count

    resume_value = str(entry.get("resume") or "").strip()
    if is_generic_resume(resume_value):
        resume_value = build_resume_from_md(md_path)

    doi_value = normalize_doi(str(entry.get("DOI", "") or ""))
    if not doi_value:
        doi_value = detect_doi_from_md(md_path)

    is_wikipedia_author = any(slug_token(a) == "WIKIPEDIA" for a in authors)
    if is_wikipedia_author:
        isbn_value = ""
        issn_value = ""
    else:
        isbn_value = normalize_isbn(str(entry.get("ISBN", "") or ""))
        if not isbn_value:
            isbn_value = detect_isbn_from_md(md_path)

        issn_value = normalize_issn(str(entry.get("ISSN", "") or ""))
        if not issn_value:
            issn_value = detect_issn_from_md(md_path)

    # URL: priorité au front matter, puis à l'entrée, puis au .source.json
    url_value = str(md_metadata.get("url") or entry.get("URL") or source_json_metadata.get("url") or "").strip()

    return {
        "identifiant_technique": md5_file(source_path),
        "identifiant_source_base": identifiant_source_base,
        "identifiant_source": identifiant_source_base,
        "titre": title,
        "date_publication": date_publication,
        "date_consultation": date_consultation,
        "origine": to_rel(source_path),
        "auteurs": authors,
        "periodes": periodes,
        "ISBN": isbn_value,
        "ISSN": issn_value,
        "DOI": doi_value,
        "URL": url_value,
        "langues": langues_value,
        "pertinence": pertinence,
        "type_source": type_source,
        "lisible": bool(entry.get("lisible", is_readable)),
        "nombre_pages": pages_value,
        "categorie": categorie,
        "extrait_brut": str(entry.get("extrait_brut") or excerpt),
        "resume": resume_value,
    }


def assign_identifiant_source(entries: list[dict]) -> None:
    by_base = {}
    for entry in entries:
        by_base.setdefault(entry["identifiant_source_base"], []).append(entry)

    for base_id, group in by_base.items():
        group.sort(key=lambda x: x["identifiant_technique"])
        if len(group) == 1:
            group[0]["identifiant_source"] = base_id
            continue
        for index, item in enumerate(group, start=1):
            item["identifiant_source"] = base_id if index == 1 else f"{base_id}-{index:02d}"


def clean_internal_keys(entries: list[dict]) -> None:
    for entry in entries:
        entry.pop("identifiant_source_base", None)


def run_pdf_extraction_batch() -> bool:
    """Execute batch PDF extraction script and return True if successful."""
    extract_script = (
        ROOT
        / ".agents"
        / "skills"
        / "extract-pdf-to-md-all-sources"
        / "scripts"
        / "extract_pdf_to_md_all_sources.py"
    )
    if not extract_script.exists():
        print(f"[WARN] script PDF extraction introuvable, ignoré: {extract_script}")
        return True  # Ne pas bloquer si le script n'existe pas

    # start the PDF to Markdown generation (no need to display something because the progression bar is enough)
    cmd = [sys.executable, "-u", str(extract_script)]
    result = subprocess.run(cmd, check=False)
    
    if result.returncode != 0:
        print(f"[WARN] extraction batch échouée (code {result.returncode}).")
        return False
    
    return True


def _frontmatter_french_ratio(md_path: Path) -> float:
    """Calcule le ratio FR (0.0-1.0) à partir du front matter YAML uniquement."""
    if not md_path.exists() or md_path.suffix.lower() != ".md":
        return 0.0

    fields = _parse_front_matter_fields(md_path)

    # Cas simple: langue explicite.
    lang = str(fields.get("language") or "").strip().lower()
    if lang == "fr":
        return 1.0
    if lang:
        return 0.0

    # Cas détaillé: distribution par langue (ex: "fr:98, de:1, it:1").
    distribution = str(fields.get("language_distribution") or "").strip().lower()
    if not distribution:
        return 0.0

    values: dict[str, float] = {}
    total = 0.0
    for chunk in distribution.split(","):
        part = chunk.strip()
        if not part or ":" not in part:
            continue
        code, raw_value = part.split(":", 1)
        code = code.strip()
        numeric_text = raw_value.strip().replace("%", "")
        numeric_match = re.search(r"\d+(?:\.\d+)?", numeric_text)
        if not code or not numeric_match:
            continue
        value = float(numeric_match.group(0))
        values[code] = value
        total += value

    if total <= 0:
        return 0.0
    return values.get("fr", 0.0) / total


def is_mostly_french_markdown(md_path: Path) -> bool:
    """Compatibilité: True si le front matter indique >90 % de français."""
    return _frontmatter_french_ratio(md_path) > 0.9


def _effective_french_ratio(path: Path) -> float:
    """Ratio FR effectif pour le choix NER.

    Si aucune information de langue n'est disponible dans le front matter,
    on suppose que le document est entièrement en français (ratio = 1.0).
    """
    if not path.exists() or path.suffix.lower() != ".md":
        return 0.0

    fields = _parse_front_matter_fields(path)

    lang = str(fields.get("language") or "").strip().lower()
    if lang == "fr":
        return 1.0
    if lang:
        return 0.0

    distribution = str(fields.get("language_distribution") or "").strip()
    if not distribution:
        # Aucune information de langue -> hypothèse 100 % français.
        return 1.0

    return _frontmatter_french_ratio(path)


def choose_french_markdown_for_ner(family_paths: list[Path]) -> Path | None:
    """Retourne le Markdown de family_paths avec le ratio FR effectif le plus élevé.

    Les fichiers dont le suffixe n'est pas '.md' sont ignorés.
    Lorsque le ratio de langue française ne peut pas être calculé (absence
    d'information de langue dans le front matter), on suppose 100 % de français.
    """
    best_path: Path | None = None
    best_ratio: float = -1.0

    for path in family_paths:
        if path.suffix.lower() != ".md":
            continue
        ratio = _effective_french_ratio(path)
        if ratio > best_ratio:
            best_ratio = ratio
            best_path = path

    return best_path


def run_named_entities_extraction(
    md_path: Path,
    *,
    quiet: bool = False,
    log_file: str | Path | None = None,
    reanalyse: bool = False,
) -> bool:
    """Lance l'extraction NER vers SQLite pour un Markdown traduit en français."""
    ner_module = _load_ner_module()
    if ner_module is None:
        if not quiet:
            print(f"[WARN] script NER introuvable, extraction ignorée: {NER_EXTRACT_SCRIPT}")
        return False

    if not hasattr(ner_module, "extract_entities_to_db"):
        if not quiet:
            print("[WARN] API NER in-process introuvable (extract_entities_to_db), extraction ignorée.")
        return False

    try:
        result = ner_module.extract_entities_to_db(
            str(md_path),
            lang="fr",
            min_confidence=0.0,
            reanalyse=reanalyse,
            quiet=quiet,
            log_file=log_file,
        )
        action = str(result.get("action") or "")
        if action in {"inserted", "skipped"}:
            return True
        if not quiet:
            print(f"[WARN] extraction NER inattendue pour {to_rel(md_path)}: {result}")
        return False
    except Exception as exc:
        msg = f"[WARN] extraction NER échouée pour {to_rel(md_path)} (erreur: {exc}); la synchronisation SQLite continue."
        if not quiet:
            print(msg)
        if log_file:
            with Path(log_file).open("a", encoding="utf-8") as handle:
                handle.write(msg + "\n")
        return False


def _print_progress_bar(current: int, total: int, label: str = "") -> None:
    if total <= 0:
        return
    width = 30
    ratio = current / total
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    suffix = f" {label}" if label else ""
    end = "\n" if current >= total else "\r"
    print(f"[NER] |{bar}| {current:>3}/{total:<3}{suffix}", end=end, flush=True)


def run_named_entities_extraction_batch_from_db(con) -> None:
    """Exécute la NER pour tous les `source_document` dont `ner_status=1`."""
    candidates = list_indexed_source_documents(con, ner_status=1, limit=1_000_000)
    doc_paths: list[Path] = []
    for document in candidates:
        raw_path = str(document.get("path") or "").strip()
        if not raw_path:
            continue

        doc_path = Path(raw_path)
        if not doc_path.is_absolute():
            doc_path = (ROOT / doc_path).resolve()

        if doc_path.suffix.lower() != ".md":
            continue
        if not doc_path.exists():
            continue
        doc_paths.append(doc_path)

    total = len(doc_paths)
    if total == 0:
        print("[NER] Aucun document Markdown candidat.")
        return

    _print_progress_bar(0, total, label="préparation")
    for idx, doc_path in enumerate(doc_paths, start=1):
        label = doc_path.name[:24]
        run_named_entities_extraction(doc_path, quiet=True, log_file=NER_GLOBAL_LOG_FILE, reanalyse=False)
        _print_progress_bar(idx, total, label=label)


def sync_pdf_markdown_documents(con, source_entries: list[dict]) -> dict[str, int]:
    """Ajoute/maj dans source_document les Markdown dérivés des PDF indexés."""
    created = 0
    updated = 0
    skipped = 0
    errors = 0

    for entry in source_entries:
        origin = str(entry.get("origine") or "").strip().replace("\\", "/")
        if not origin.lower().endswith(".pdf"):
            continue

        pdf_abs = ROOT / origin
        md_abs = pdf_abs.with_suffix(".md")
        if not md_abs.exists():
            skipped += 1
            continue

        md_rel = to_rel(md_abs)
        ner_status = 1 if is_mostly_french_markdown(md_abs) else 0

        result = upsert_source(
            con,
            {
                "parent_path": origin,
                "path": md_rel,
                "file_name": md_abs.name,
                "relative_path": md_abs.name,
                "author": resolve_derived_author(md_abs),
                "ner_status": ner_status,
            },
        )

        action = str(result.get("action") or "")
        if action == "created":
            created += 1
        elif action == "updated":
            updated += 1
        else:
            errors += 1
            reason = result.get("reason")
            if reason:
                print(f"[WARN] document dérivé non synchronisé ({md_rel}): {reason}")

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


def main() -> None:
    INTEREST_PERIOD_START_YEAR = 1918
    INTEREST_PERIOD_END_YEAR = 1939

    lock_handle: TextIO | None = None
    con = None
    try:
        lock_handle, lock_message = _acquire_index_lock(INDEX_LOCK_FILE)
        if lock_handle is None:
            print(f"[INFO] {lock_message}")
            return
        print(f"[INFO] {lock_message}")

        # Nouveau dépôt sans sources: comportement normal, on sort sans erreur.
        if not SOURCES_DIR.exists():
            print(f"[INFO] aucun répertoire sources détecté ({SOURCES_DIR}); rien à indexer.")
            return

        if not run_pdf_extraction_batch():
            return

        con = get_named_entities_connection()
        current = list_indexed_sources(con)
        known_authors = load_known_authors(AUTHORS_PATH)

        by_origin = {}
        by_source_key = {}
        for item in current:
            origin = item.get("origine")
            if isinstance(origin, str) and origin:
                by_origin[origin] = item
                key = source_key_from_path(ROOT / origin)
                by_source_key[key] = item

        all_files = sorted(p for p in SOURCES_DIR.rglob("*") if p.is_file())
        md_paths = [p for p in all_files if p.suffix.lower() == ".md"]
        embedded_images = collect_embedded_markdown_images(md_paths)

        candidate_files: list[Path] = []
        for file_path in all_files:
            if file_path.name in INDEX_META_FILES:
                continue
            if file_path.name.startswith(LOCK_FILE_PREFIXES):
                continue
            if file_path.resolve() in embedded_images:
                continue
            candidate_files.append(file_path)

        derived_by_parent = _collect_derived_documents_from_frontmatter(candidate_files)

        final_entries = []
        invalid_page_sections: list[Path] = []

        for source_path in sorted(candidate_files, key=lambda p: to_rel(p)):
            # Un Markdown qui définit `source` dans son front matter est un dérivé,
            # il ne crée pas d'entrée source principale.
            if source_path.suffix.lower() == ".md":
                source_fields = _parse_front_matter_fields(source_path)
                source_value = source_fields.get("source")
                if isinstance(source_value, str) and source_value.strip():
                    continue

            analysis_md = source_path if source_path.suffix.lower() == ".md" else source_path.with_suffix(".md")

            # Contrainte obligatoire: sections `Page X` sur les Markdown analytiques.
            if analysis_md.exists() and analysis_md.suffix.lower() == ".md":
                normalize_md_page_sections(analysis_md)
                if not has_valid_page_sections(analysis_md):
                    # Repli pour les Markdown sans pagination explicite (ex: notices DHS natives).
                    if not (ensure_single_page_section(analysis_md) and has_valid_page_sections(analysis_md)):
                        invalid_page_sections.append(analysis_md)

            active_md = analysis_md

            page_count, excerpt, is_readable = md_stats(active_md)
            langues_value = markdown_language_distribution(active_md) if source_path.suffix.lower() == ".md" else None
            rel_source = to_rel(source_path)
            source_key = source_key_from_path(source_path)
            source_entry = by_origin.get(rel_source, by_source_key.get(source_key, {}))

            # Charger les métadonnées du front matter Markdown
            md_metadata = _parse_front_matter_fields(active_md)

            # Charger les métadonnées du fichier .source.json (pour documents binaires)
            source_json_metadata = load_source_json_metadata(source_path)

            entry = normalize_entry(
                source_entry,
                source_path,
                active_md,
                excerpt,
                page_count,
                is_readable,
                known_authors,
                langues_value=langues_value,
                md_metadata=md_metadata,
                source_json_metadata=source_json_metadata,
                period_interest_start_year=INTEREST_PERIOD_START_YEAR,
                period_interest_end_year=INTEREST_PERIOD_END_YEAR,
            )
            entry["ner_status"] = 1 if source_path.suffix.lower() == ".md" else 0

            final_entries.append(entry)

        assign_identifiant_source(final_entries)
        clean_internal_keys(final_entries)
        final_entries.sort(key=lambda x: x["identifiant_technique"])

        if invalid_page_sections:
            invalid_unique = sorted(set(invalid_page_sections))
            print(f"\nERREUR: {len(invalid_unique)} fichier(s) MD sans sections 'Page X' valides:")
            for p in invalid_unique:
                print(f"  - {to_rel(p)}")
            print("Corriger la structure en sections '## Page X' puis relancer le script.")
            return  # Blocage : table SQLite `source` non mise à jour

        sync_result = replace_indexed_sources(con, final_entries)
        print(
            f"ok: {sync_result['sources_count']} sources synchronisées dans SQLite "
            f"({sync_result['documents_count']} documents liés)"
        )

        pdf_md_sync = sync_pdf_markdown_documents(con, final_entries)
        print(
            "ok: documents Markdown dérivés des PDF synchronisés "
            f"(créés={pdf_md_sync['created']}, mis à jour={pdf_md_sync['updated']}, "
            f"ignorés={pdf_md_sync['skipped']}, erreurs={pdf_md_sync['errors']})"
        )

        # NER batch pilotée par la table source_document (ner_status = 1).
        run_named_entities_extraction_batch_from_db(con)
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
        if lock_handle is not None:
            _release_index_lock(lock_handle)


if __name__ == "__main__":
    main()

