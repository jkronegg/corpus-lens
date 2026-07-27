import json
import os
from datetime import datetime
from pathlib import Path
from typing import TextIO
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[4]
INDEX_LOCK_FILE = ROOT / ".indexer-sources.lock"

def _read_index_lock(lock_path: Path = INDEX_LOCK_FILE) -> dict:
    if not lock_path.exists():
        return {}
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _try_acquire_file_lock(lock_handle: TextIO) -> bool:
    """Acquire a non-blocking file lock.

    Windows uses msvcrt.locking, Unix uses fcntl.flock.
    """
    if os.name == "nt":
        import msvcrt

        try:
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

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


def acquire_index_lock(lock_path: Path = INDEX_LOCK_FILE, script_path: Path | None = None) -> tuple[TextIO | None, str, dict | None]:
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
        return None, f"Indexation deja en cours{details}.", None

    lock_token = uuid4().hex
    new_payload = {
        "pid": os.getpid(),
        "started_at": datetime.now().isoformat(),
        "script": str(script_path or Path(__file__).resolve()),
        "token": lock_token,
    }
    lock_handle.seek(0)
    lock_handle.truncate()
    json.dump(new_payload, lock_handle, ensure_ascii=False, indent=2)
    lock_handle.write("\n")
    lock_handle.flush()
    return lock_handle, f"Lock acquis: {lock_path}", {"pid": new_payload["pid"], "token": lock_token}


def release_index_lock(lock_handle: TextIO, lock_path: Path = INDEX_LOCK_FILE, owner: dict | None = None) -> None:
    try:
        _release_file_lock(lock_handle)
    except Exception:
        pass
    finally:
        lock_handle.close()

    if owner is None:
        return

    owner_pid = owner.get("pid")
    owner_token = owner.get("token")
    if not isinstance(owner_pid, int) or not isinstance(owner_token, str):
        return

    payload = _read_index_lock(lock_path)
    try:
        payload_pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        payload_pid = 0
    payload_token = payload.get("token")
    if payload_pid != owner_pid or payload_token != owner_token:
        return

    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass

