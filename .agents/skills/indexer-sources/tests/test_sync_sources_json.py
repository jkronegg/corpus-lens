"""
Tests unitaires pour `sync_sources_json.py`.

Point 4 : Recherche d'entités nommées dans le texte Markdown
          (détection de la langue, sélection du Markdown français, NER)

Les tests des points 2 et 3 vivent dans `test_sync_file_add.py`.
Les tests du point 1 (suppressions/renommages) vivent dans `test_sync_file_delete.py`.
"""

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ajout de scripts/ au PYTHONPATH pour l'import du module testé
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import sync_sources_json as sut


# ===========================================================================
# Helpers partagés
# ===========================================================================


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


if __name__ == "__main__":
    unittest.main()



