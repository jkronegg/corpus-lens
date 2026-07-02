#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from deep_translator import GoogleTranslator

DEFAULT_INPUT = Path(
    r"C:\Users\Julien\git\kronegg\histoire_suisse\sources\swissvotes\votation_86\debat_parlementaire.md"
)

GERMAN_HINTS = {
    "der", "die", "das", "und", "mit", "nicht", "eine", "einer", "einem", "eines", "des", "dem", "den",
    "ist", "sind", "wird", "werden", "auf", "fur", "für", "im", "in", "zu", "vom", "durch", "gegen",
    "militar", "militarjustiz", "rat", "justiz", "straf", "gesetz", "bundesrat", "standerat", "ständerat",
    "nationalrat", "volk", "stimmen", "antrag", "ablehnung", "beschwerde", "ordnung", "tage", "gericht",
    "gerichte", "prozessordnung", "kanton", "wurden", "uber", "über",
}

FRENCH_HINTS = {
    "le", "la", "les", "de", "des", "du", "et", "est", "sont", "dans", "pour", "avec", "sur", "par",
    "que", "qui", "ne", "pas", "au", "aux", "conseil", "federal", "fédéral", "justice", "militaire",
    "initiative", "tribunal", "peine", "juridiction", "commission", "rapport", "peuple", "cantons",
}

FRONT_MATTER_SKIP_KEYS = (
    "titre:",
    "source:",
    "date_extraction:",
    "pages:",
    "author:",
    "language_distribution:",
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DB_MODULE_PATH = REPO_ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts" / "db.py"

_DB_AVAILABLE = False
_GET_DB_CONNECTION = None
_UPSERT_SOURCE = None

try:
    _db_spec = importlib.util.spec_from_file_location("named_entities_db_translate_md", DB_MODULE_PATH)
    if _db_spec is not None and _db_spec.loader is not None:
        _db_module = importlib.util.module_from_spec(_db_spec)
        sys.modules[_db_spec.name] = _db_module
        _db_spec.loader.exec_module(_db_module)
        _GET_DB_CONNECTION = getattr(_db_module, "get_connection", None)
        _UPSERT_SOURCE = getattr(_db_module, "upsert_source", None)
        _DB_AVAILABLE = callable(_GET_DB_CONNECTION) and callable(_UPSERT_SOURCE)
except Exception:
    _DB_AVAILABLE = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Traduction ciblée DE->FR pour Markdown OCR Swissvotes.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Fichier Markdown source")
    parser.add_argument("--output", type=Path, default=None, help="Fichier Markdown de sortie")
    parser.add_argument("--target-lang", default="fr", help="Langue cible (par defaut: fr)")
    parser.add_argument("--source-lang", default="auto", help="Langue source (par defaut: auto)")
    parser.add_argument("--max-lines", type=int, default=0, help="Limiter le nombre de lignes traitee (0 = tout)")
    parser.add_argument("--throttle", type=float, default=0.0, help="Pause en secondes entre traductions")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas ecrire de fichier")
    parser.add_argument("--verbose", action="store_true", help="Afficher les lignes traduites (resume)")
    parser.add_argument("--foreground", action="store_true", help="Forcer l'execution au premier plan")
    parser.add_argument("--log-file", type=Path, default=None, help="Fichier log du mode arriere-plan")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def derive_log_path(out_path: Path, user_log: Path | None) -> Path:
    if user_log is not None:
        return user_log
    return out_path.with_suffix(out_path.suffix + ".log")


def launch_in_background(log_path: Path) -> int:
    raw_args = sys.argv[1:]
    child_args: list[str] = list(raw_args)
    if "--worker" not in child_args:
        child_args.append("--worker")
    if "--log-file" not in child_args:
        child_args.extend(["--log-file", str(log_path)])

    cmd = [sys.executable, "-u", str(Path(__file__).resolve()), *child_args]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write("\n=== background run start ===\n")

    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    else:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    return proc.pid


def make_logger(log_file: Path | None):
    resolved = log_file.resolve() if log_file else None

    def _log(message: str, *, flush: bool = False) -> None:
        print(message, flush=flush)
        if resolved is not None:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with resolved.open("a", encoding="utf-8") as f:
                f.write(message + "\n")

    return _log


def derive_output_path(src: Path, output: Path | None) -> Path:
    if output is not None:
        return output
    if src.name.endswith(".translated.md"):
        return src
    return src.with_name(src.stem + ".translated.md")


def word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", text.lower())


def normalize_token(token: str) -> str:
    return (
        token.replace("ä", "a")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ß", "ss")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("â", "a")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ô", "o")
        .replace("ù", "u")
    )


def score_languages(tokens: list[str], line: str) -> tuple[float, float]:
    de_score = 0.0
    fr_score = 0.0

    for token in tokens:
        norm = normalize_token(token)
        if norm in GERMAN_HINTS or token in GERMAN_HINTS:
            de_score += 1.0
        if norm in FRENCH_HINTS or token in FRENCH_HINTS:
            fr_score += 1.0

    if re.search(r"[äöüßÄÖÜ]", line):
        de_score += 3.0

    if re.search(r"\b(Nationalrat|Standerat|St\.?\s*Gallen|Bundesrat)\b", line, flags=re.IGNORECASE):
        de_score += 1.5

    return de_score, fr_score


def is_structure_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if s.startswith("## Page "):
        return True
    if s.startswith("---"):
        return True
    if any(s.startswith(prefix) for prefix in FRONT_MATTER_SKIP_KEYS):
        return True
    if re.fullmatch(r"[#>*\-\s\d.()/:,;]+", s):
        return True
    return False


def should_translate_line(line: str) -> bool:
    if is_structure_line(line):
        return False

    tokens = word_tokens(line)
    if len(tokens) < 3:
        return False

    de_score, fr_score = score_languages(tokens, line)
    de_ratio = de_score / max(len(tokens), 1)
    return (de_score >= 2.0 and de_score >= fr_score * 1.15) or de_ratio >= 0.25


def parse_front_matter(lines: list[str]) -> tuple[list[str], int]:
    if not lines or lines[0].strip() != "---":
        return [], 0

    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[: idx + 1], idx + 1
    raise RuntimeError("Front matter YAML invalide: delimiteur fermant '---' manquant")


def _extract_frontmatter_source(front_lines: list[str]) -> str:
    for line in front_lines:
        stripped = line.strip()
        if not stripped.lower().startswith("source:"):
            continue
        raw_value = stripped.split(":", 1)[1].strip().strip('"\'')
        if raw_value:
            return raw_value
    return ""


def _to_repo_rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_parent_pdf_path(source_value: str, src_path: Path) -> str:
    value = (source_value or "").strip().replace("\\", "/")
    if not value:
        return ""

    candidates = [Path(value)]
    candidates.append((src_path.parent / value).resolve())
    candidates.append((REPO_ROOT / value).resolve())

    for candidate in candidates:
        if candidate.exists() and candidate.suffix.lower() == ".pdf":
            return _to_repo_rel(candidate)
    return ""


def _register_translated_markdown(out_path: Path, parent_pdf_path: str, target_lang: str) -> None:
    if not _DB_AVAILABLE or not parent_pdf_path:
        return

    ner_status = 1 if (target_lang or "").lower() == "fr" else 0
    con = None
    try:
        con = _GET_DB_CONNECTION()
        result = _UPSERT_SOURCE(
            con,
            {
                "parent_path": parent_pdf_path,
                "path": _to_repo_rel(out_path),
                "file_name": out_path.name,
                "relative_path": out_path.name,
                "author": "skill translate-markdown",
                "ner_status": ner_status,
            },
        )
        if result.get("action") == "error":
            print(
                f"[WARN] source_document non enregistre pour {out_path}: {result.get('reason', 'inconnu')}",
                flush=True,
            )
    except Exception as exc:
        print(f"[WARN] source_document non enregistre pour {out_path}: {exc}", flush=True)
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


def update_front_matter(front_lines: list[str], target_lang: str) -> list[str]:
    if not front_lines:
        return []

    updated: list[str] = []
    has_distribution = False
    for line in front_lines:
        if line.startswith("language_distribution:"):
            updated.append(f'language_distribution: "{target_lang}:100"')
            has_distribution = True
        else:
            updated.append(line)

    if not has_distribution:
        updated.insert(-1, f'language_distribution: "{target_lang}:100"')
    return updated


def translate_line(translator: GoogleTranslator, line: str, retries: int = 4) -> str:
    for attempt in range(retries):
        try:
            translated = translator.translate(line)
            if translated:
                return translated
        except Exception:
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError("Echec traduction apres retries")


def main() -> int:
    args = parse_args()

    src = args.input.resolve()
    out = derive_output_path(src, args.output)

    if not args.worker and not args.foreground:
        log_path = derive_log_path(out, args.log_file).resolve()
        pid = launch_in_background(log_path)
        print(f"Background translation started (PID={pid})")
        print(f"Log file: {log_path}")
        #print("Use Get-Content -Wait <log_file> to follow progress.")
        #print("Use --foreground to run in the current terminal.")
        return 0

    logger = make_logger(args.log_file)

    text = src.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    front_lines, body_start = parse_front_matter(lines)
    parent_pdf_path = _resolve_parent_pdf_path(_extract_frontmatter_source(front_lines), src)

    out_lines: list[str] = []
    out_lines.extend(update_front_matter(front_lines, args.target_lang))

    body_lines = lines[body_start:]
    if args.max_lines > 0:
        body_lines = body_lines[: args.max_lines]

    translator = GoogleTranslator(source=args.source_lang, target=args.target_lang)

    translated_count = 0
    failed_count = 0
    skipped_count = 0

    for idx, line in enumerate(body_lines, start=1):
        if should_translate_line(line):
            try:
                translated_line = translate_line(translator, line)
                out_lines.append(translated_line)
                translated_count += 1
                if args.verbose and translated_count <= 10:
                    logger(f"[translated] {line[:90]}")
            except Exception:
                out_lines.append(line)
                failed_count += 1
        else:
            out_lines.append(line)
            skipped_count += 1

        if args.throttle > 0 and should_translate_line(line):
            time.sleep(args.throttle)

        if idx % 120 == 0:
            logger(
                f"processed {idx}/{len(body_lines)} | translated={translated_count} | failed={failed_count} | skipped={skipped_count}",
                flush=True,
            )

    output_text = "\n".join(out_lines).rstrip() + "\n"
    if args.dry_run:
        logger("[dry-run] Aucun fichier ecrit.")
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output_text, encoding="utf-8")
        _register_translated_markdown(out, parent_pdf_path, args.target_lang)
        logger(f"Wrote: {out}")

    logger(f"Input: {src}")
    logger(f"Translated lines: {translated_count}")
    logger(f"Failed lines kept original: {failed_count}")
    logger(f"Skipped lines: {skipped_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

