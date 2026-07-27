import sqlite3
import unittest
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import sync_file_move as sut

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

class TestSourceMoveSync(unittest.TestCase):
    def setUp(self):
        pass

    def test_correct_moved_file_records_updates_source_and_source_document(self):
        # Given

        # Base de données avec une source
        con = _make_db()
        cur = con.execute(
            "INSERT INTO source(signature, identifiant_source, titre, origine) VALUES (?, ?, ?, ?)",
            ("abc123", "SRC-abc123", "Titre de test", "sources/old-name.pdf"),
        )
        source_id = cur.lastrowid
        con.execute(
            "INSERT INTO source_document(source_id, signature, path, file_name) VALUES (?, ?, ?, ?)",
            (source_id, "abc123", "sources/old-name.pdf", "old-name.pdf"),
        )

        # When
        logs = []
        result = sut.manage_moved_file(
            con,
            file_sig="abc123",
            rel_path="sources/new-name.pdf",
            logger=logs.append,
        )

        # Then
        source_row = con.execute("SELECT origine FROM source WHERE signature = ?", ("abc123",)).fetchone()
        document_row = con.execute(
            "SELECT path FROM source_document WHERE signature = ?",
            ("abc123",),
        ).fetchone()

        self.assertEqual(
            result,
            {
                "source_found": True,
                "source_document_found": True,
                "corrected_source": True,
                "corrected_source_document": True,
                "corrected_childs": [],
            },
        )
        self.assertEqual(source_row["origine"], "sources/new-name.pdf")
        self.assertEqual(document_row["path"], "sources/new-name.pdf")
        self.assertEqual(len(logs), 2)
        con.close()

    def test_correct_moved_file_records_is_noop_when_path_is_already_current(self):
        #Given
        con = _make_db()
        cur = con.execute(
            "INSERT INTO source(signature, identifiant_source, titre, origine) VALUES (?, ?, ?, ?)",
            ("sig-doc-1", "SRC-sig-doc-1", "Titre courant", "sources/current-doc.md"),
        )
        source_id = cur.lastrowid
        con.execute(
            "INSERT INTO source_document(source_id, signature, path, file_name) VALUES (?, ?, ?, ?)",
            (source_id, "sig-doc-1", "sources/current-doc.md", "current-doc.md"),
        )

        # When
        result = sut.manage_moved_file(
            con,
            file_sig="sig-doc-1",
            rel_path="sources/current-doc.md",
            logger=lambda _msg: None,
        )

        # Then
        self.assertEqual(
            result,
            {
                "source_found": True,
                "source_document_found": True,
                "corrected_source": False,
                "corrected_source_document": False,
                "corrected_childs": [],
            },
        )
        con.close()


if __name__ == "__main__":
    unittest.main()

