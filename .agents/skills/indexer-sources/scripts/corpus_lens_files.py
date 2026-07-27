import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def to_rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()

