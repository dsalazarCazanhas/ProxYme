import logging
import os
import sys
from pathlib import Path

_LOCK_FILE = Path.home() / ".proxyme" / "proxyme.lock"
_log = logging.getLogger(__name__)


def acquire() -> bool:
    """
    Try to acquire the single-instance lock.
    Returns True if this process is the only instance, False otherwise.
    """
    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if _LOCK_FILE.exists():
        try:
            pid = int(_LOCK_FILE.read_text(encoding="utf-8").strip())
            if _process_is_alive(pid):
                _log.warning("Another instance is already running (PID %s)", pid)
                return False
            # Stale lock from a previous crash — overwrite it
            _log.info("Stale lock found (PID %s no longer alive) — overwriting", pid)
        except (ValueError, OSError):
            # Corrupted lock file — overwrite it
            _log.info("Corrupted lock file found — overwriting")

    _LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    _log.info("Single-instance lock acquired (PID %s)", os.getpid())
    return True


def release() -> None:
    """Remove the lock file. Should be called on clean exit."""
    try:
        _LOCK_FILE.unlink(missing_ok=True)
        _log.info("Single-instance lock released")
    except OSError as exc:
        _log.warning("Could not remove lock file: %s", exc)


def _process_is_alive(pid: int) -> bool:
    """Check if a process with the given PID is currently running."""
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        # STILL_ACTIVE == 259
        return exit_code.value == 259
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # process exists but we can't signal it
