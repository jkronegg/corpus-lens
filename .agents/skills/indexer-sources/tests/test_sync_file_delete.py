import importlib.util
import sqlite3
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ajout de scripts/ au PYTHONPATH pour l'import des modules testés
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import sync_file_delete as sut

# ---------------------------------------------------------------------------
# Schéma SQLite partagé
# ---------------------------------------------------------------------------
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "manage-named-entities-db"
    / "assets"
    / "schema.sql"
)
SCHEMA_SQL = _SCHEMA_PATH.read_text(encoding="utf-8")


# ===========================================================================
# Helpers partagés
# ===========================================================================

def _make_db() -> sqlite3.Connection:
    """Crée une base SQLite en mémoire avec le schéma minimal requis."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_SQL)
    con.commit()
    return con


def _insert_source(con, *, origine: str, signature: str = "abc123") -> int:
    cur = con.execute(
        "INSERT INTO source (signature, identifiant_source, titre, origine) "
        "VALUES (?, ?, ?, ?)",
        (signature, f"SRC-{signature}", f"Titre {origine}", origine),
    )
    con.commit()
    return cur.lastrowid


def _insert_source_document(con, *, source_id: int, path: str, signature: str = "doc123") -> int:
    cur = con.execute(
        "INSERT INTO source_document (source_id, path, file_name, signature) "
        "VALUES (?, ?, ?, ?)",
        (source_id, path, Path(path).name, signature),
    )
    con.commit()
    return cur.lastrowid


def _md(tmp_path: Path, name: str, content: str) -> Path:
    """Écrit un fichier Markdown dans tmp_path et retourne son chemin."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


class _TmpDirMixin(unittest.TestCase):
    """Mixin qui fournit self.tmp_path (Path) pour chaque méthode de test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)


# ===========================================================================
# Tests unitaires de sync_file_delete.py (module bas niveau)
# ===========================================================================


class TestSyncFileDelete(unittest.TestCase):
    def setUp(self):
        pass

    def test_sync_deleted_files_removes_missing_and_orphans(self):
        with tempfile.TemporaryDirectory() as tmp_dir:

            #Given
            # Un répertoire source avec un fichier `existing.md`
            root = Path(tmp_dir)
            sources_dir = root / "sources"
            sources_dir.mkdir(parents=True, exist_ok=True)
            (sources_dir / "existing.md").write_text("## Page 1\nOK\n", encoding="utf-8")

            # Une base de données avec 3 source_document
            con = _make_db()
            con.executemany(
                "INSERT INTO source(signature, origine, identifiant_source, titre) VALUES (?, ?, ?, ?)",
                [
                    ("sig-del", "sources/deleted.md", "i1", "t1"),
                    ("sig-ren", "sources/renamed-old.md", "i2", "t2"),
                    ("sig-keep", "sources/existing.md", "i3", "t3"),
                ],
            )
            con.executemany(
                "INSERT INTO source_document(id, source_id, path, signature, file_name) VALUES (?, ?, ?, ?, ?)",
                [
                    (1, 1, "sources/deleted.md", "sig-del", "deleted.md"),
                    (2, 2, "sources/renamed-old.md", "sig-ren", "renamed-old.md"),
                    (3, 3, "sources/existing.md", "sig-keep", "existing.md"),
                ],
            )
            con.executemany("INSERT INTO named_entity(id, key, entity_type, display_name) VALUES (?, ?, ?, ?)", [(101,"jean_dupont", "person", "Jean Dupont"), (102,"maria_bernasconi", "person", "Maria Bernasconi")])
            con.executemany("INSERT INTO person(entity_id, key, display_name) VALUES (?, ?, ?)", [(101,"jean_dupont", "Jean Dupont"), (102,"maria_bernasconi", "Maria Bernasconi")])
            con.executemany(
                "INSERT INTO mention(id, source_document_id, entity_id, source, page) VALUES (?,?, ?, ?, ?)",
                [(1, 1, 101, "sources/deleted.md", 1), (2, 2, 102, "sources/renamed-old.md", 1)],
            )
            con.commit()

            # When
            result = sut.manage_deleted_files(
                con,
                retained_signatures={"sig-keep", "sig-ren"},
                logger=lambda _msg: None,
            )

            # Then un document est supprimé
            self.assertEqual(
                result,
                {
                    "deleted_source": 1,
                    "deleted_source_document": 1,
                },
            )

            remaining_docs = con.execute("SELECT path FROM source_document ORDER BY id").fetchall()
            self.assertEqual([row["path"] for row in remaining_docs], ["sources/renamed-old.md", "sources/existing.md"])

            remaining_sources = con.execute("SELECT origine FROM source ORDER BY origine").fetchall()
            self.assertEqual(
                [row["origine"] for row in remaining_sources],
                ["sources/existing.md", "sources/renamed-old.md"],
            )

            remaining_mentions = con.execute("SELECT id FROM mention ORDER BY id").fetchall()
            self.assertEqual([row["id"] for row in remaining_mentions], [2])

            remaining_persons = con.execute("SELECT entity_id FROM person ORDER BY entity_id").fetchall()
            self.assertEqual([row["entity_id"] for row in remaining_persons], [102])

            remaining_entities = con.execute("SELECT id FROM named_entity ORDER BY id").fetchall()
            self.assertEqual([row["id"] for row in remaining_entities], [102])

            con.close()


if __name__ == "__main__":
    unittest.main()
