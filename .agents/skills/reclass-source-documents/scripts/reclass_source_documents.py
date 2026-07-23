#!/usr/bin/env python3
"""Reclasse des grappes de documents sources dans des sous-dossiers par annee de publication.

Le script:
- lit les sources indexees dans SQLite (tables `source` et `source_document`),
- detecte l'annee de publication dans le front matter YAML d'un Markdown de la grappe,
- deplace la grappe complete dans `<repertoire>/<annee>/...`,
- met a jour `source.origine`, `source_document.path` et `mention.source`.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = ROOT / "named_entities.sqlite"
SUPPORTED_GROUP_BY = "publication-year"

FRONTMATTER_RE = re.compile(r"(?s)^---\n(.*?)\n---\n?")
YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b")
DATE_KEYS = (
    "date_publication",
    "publication_date",
    "date-publication",
    "date",
)


@dataclass
class SourceRow:
    source_id: int
    origine: str


@dataclass
class SourceDocumentRow:
    doc_id: int
    source_id: int
    path: str
    parent_doc_id: int | None
    relative_path: str | None


def to_repo_rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def parse_frontmatter_fields(md_path: Path) -> dict[str, str]:
    if not md_path.exists() or md_path.suffix.lower() != ".md":
        return {}
    content = md_path.read_text(encoding="utf-8", errors="replace")
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}

    fields: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip('"\'')
        fields[key] = value
    return fields


def publication_year_from_markdown(md_paths: list[Path], preferred_md_path: Path | None = None) -> str | None:
    ordered_md_paths: list[Path] = []
    seen: set[Path] = set()

    if preferred_md_path is not None:
        preferred = preferred_md_path.resolve()
        if preferred.suffix.lower() == ".md" and preferred.exists():
            ordered_md_paths.append(preferred)
            seen.add(preferred)

    for md_path in sorted(md_paths):
        md_resolved = md_path.resolve()
        if md_resolved in seen:
            continue
        ordered_md_paths.append(md_resolved)
        seen.add(md_resolved)

    for md_path in ordered_md_paths:
        fields = parse_frontmatter_fields(md_path)
        for key in DATE_KEYS:
            raw = fields.get(key)
            if not raw:
                continue
            year_match = YEAR_RE.search(raw)
            if year_match:
                return year_match.group(1)
    return None


def select_sources_in_directory(con: sqlite3.Connection, directory_rel: str) -> list[SourceRow]:
    rows = con.execute(
        """
        SELECT s.id AS source_id, s.origine
        FROM source s
        JOIN source_document sd ON sd.source_id = s.id
        WHERE sd.parent_doc_id IS NULL
        ORDER BY s.id
        """
    ).fetchall()

    selected: list[SourceRow] = []
    target = (ROOT / directory_rel).resolve()
    for row in rows:
        origine = str(row["origine"] or "").strip().replace("\\", "/")
        if not origine:
            continue
        origin_path = (ROOT / origine).resolve()
        if origin_path.parent == target:
            selected.append(SourceRow(source_id=int(row["source_id"]), origine=origine))
    return selected


def list_source_documents(con: sqlite3.Connection, source_id: int) -> list[SourceDocumentRow]:
    rows = con.execute(
        """
        SELECT id, source_id, path, parent_doc_id, relative_path
        FROM source_document
        WHERE source_id = ?
        ORDER BY path
        """,
        (source_id,),
    ).fetchall()
    return [
        SourceDocumentRow(
            doc_id=int(row["id"]),
            source_id=int(row["source_id"]),
            path=str(row["path"]),
            parent_doc_id=row["parent_doc_id"],
            relative_path=row["relative_path"],
        )
        for row in rows
    ]


def collect_cluster_items(source_dir: Path, source_origin: Path, docs: list[SourceDocumentRow]) -> set[Path]:
    items: set[Path] = set()

    for doc in docs:
        doc_abs = (ROOT / doc.path).resolve()
        if doc_abs.exists():
            items.add(doc_abs)

    root_name = source_origin.stem
    prefix_re = re.compile(rf"^{re.escape(root_name)}(?:$|[._-]).*")
    for child in source_dir.iterdir():
        if prefix_re.match(child.name):
            items.add(child.resolve())

    # Evite de deplacer a la fois un dossier et ses descendants explicitement.
    reduced: set[Path] = set()
    for candidate in sorted(items, key=lambda p: len(p.parts)):
        if any(parent in reduced for parent in candidate.parents):
            continue
        reduced.add(candidate)
    return reduced


def build_move_plan(cluster_items: set[Path], source_dir: Path, target_year_dir: Path) -> dict[Path, Path]:
    plan: dict[Path, Path] = {}
    for old_path in sorted(cluster_items):
        try:
            relative = old_path.relative_to(source_dir)
        except ValueError:
            # Le skill reclasse uniquement les elements qui vivent dans le repertoire cible.
            continue
        new_path = (target_year_dir / relative).resolve()
        if old_path == new_path:
            continue
        plan[old_path] = new_path

    for old_path, new_path in plan.items():
        if new_path.exists() and new_path not in plan:
            raise RuntimeError(f"Conflit de chemin: {to_repo_rel(new_path)} existe deja")
    return plan


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Reclasse un repertoire de sources en sous-dossiers par annee de publication."
    )
    parser.add_argument("--directory", required=True, help="Repertoire cible (relatif au repo ou absolu)")
    parser.add_argument(
        "--group-by",
        default=SUPPORTED_GROUP_BY,
        choices=[SUPPORTED_GROUP_BY],
        help="Critere de regroupement (actuellement: publication-year)",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"Chemin vers SQLite (defaut: {DEFAULT_DB})")
    parser.add_argument("--dry-run", action="store_true", help="Affiche le plan sans deplacer ni modifier la DB")
    args = parser.parse_args()

    source_dir = Path(args.directory)
    if not source_dir.is_absolute():
        source_dir = (ROOT / source_dir).resolve()

    if not source_dir.exists() or not source_dir.is_dir():
        print(f"[erreur] repertoire introuvable: {source_dir}", file=sys.stderr)
        return 2

    try:
        source_dir_rel = to_repo_rel(source_dir)
    except ValueError:
        print("[erreur] le repertoire doit etre dans le depot.", file=sys.stderr)
        return 2

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")

    sources = select_sources_in_directory(con, source_dir_rel)
    if not sources:
        print(f"[info] aucune source indexee trouvee dans {source_dir_rel}")
        return 0

    move_plan: dict[Path, Path] = {}
    doc_path_updates: dict[str, str] = {}
    source_origins_updates: dict[int, str] = {}

    skipped_no_year = 0
    skipped_no_markdown = 0

    for source in sources:
        docs = list_source_documents(con, source.source_id)
        md_paths = [
            (ROOT / doc.path).resolve()
            for doc in docs
            if doc.path.lower().endswith(".md") and (ROOT / doc.path).exists()
        ]
        if not md_paths:
            skipped_no_markdown += 1
            continue

        origin_abs = (ROOT / source.origine).resolve()
        preferred_md_path = origin_abs if origin_abs.suffix.lower() == ".md" else origin_abs.with_suffix(".md")
        year = publication_year_from_markdown(md_paths, preferred_md_path=preferred_md_path)
        if not year:
            skipped_no_year += 1
            continue

        cluster_items = collect_cluster_items(source_dir, origin_abs, docs)
        target_year_dir = (source_dir / year).resolve()

        cluster_plan = build_move_plan(cluster_items, source_dir, target_year_dir)
        move_plan.update(cluster_plan)

        for doc in docs:
            old_abs = (ROOT / doc.path).resolve()
            new_abs = cluster_plan.get(old_abs)
            if new_abs is None:
                continue
            old_rel = to_repo_rel(old_abs)
            new_rel = to_repo_rel(new_abs)
            doc_path_updates[old_rel] = new_rel
            if old_rel == source.origine:
                source_origins_updates[source.source_id] = new_rel

    if not move_plan:
        print("[info] aucun deplacement a effectuer.")
        if skipped_no_markdown:
            print(f"[info] sources ignorees sans markdown: {skipped_no_markdown}")
        if skipped_no_year:
            print(f"[info] sources ignorees sans annee de publication frontmatter: {skipped_no_year}")
        return 0

    print(f"[plan] sources candidates: {len(sources)}")
    print(f"[plan] deplacements: {len(move_plan)}")
    for old_path, new_path in sorted(move_plan.items()):
        print(f"  - {to_repo_rel(old_path)} -> {to_repo_rel(new_path)}")

    if args.dry_run:
        print("[dry-run] aucun changement applique.")
        return 0

    executed_moves: list[tuple[Path, Path]] = []
    try:
        for old_path, new_path in sorted(move_plan.items(), key=lambda kv: len(kv[0].parts), reverse=True):
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_path), str(new_path))
            executed_moves.append((old_path, new_path))

        with con:
            for old_rel, new_rel in sorted(doc_path_updates.items()):
                con.execute(
                    "UPDATE source_document SET path = ?, file_name = ? WHERE path = ?",
                    (new_rel, Path(new_rel).name, old_rel),
                )
                con.execute("UPDATE mention SET source = ? WHERE source = ?", (new_rel, old_rel))

            for source_id, new_origin in sorted(source_origins_updates.items()):
                con.execute("UPDATE source SET origine = ? WHERE id = ?", (new_origin, source_id))

    except Exception as exc:
        # Best effort rollback des mouvements si la transaction SQL echoue.
        for old_path, new_path in reversed(executed_moves):
            try:
                if new_path.exists() and not old_path.exists():
                    old_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(new_path), str(old_path))
            except Exception:
                pass
        print(f"[erreur] reclassement interrompu: {exc}", file=sys.stderr)
        return 1
    finally:
        con.close()

    print("[ok] reclassement termine et base synchronisee (source, source_document, mention.source).")
    if skipped_no_markdown:
        print(f"[info] sources ignorees sans markdown: {skipped_no_markdown}")
    if skipped_no_year:
        print(f"[info] sources ignorees sans annee de publication frontmatter: {skipped_no_year}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

