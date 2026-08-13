import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path

_LOG_DIR    = Path.home() / ".proxyme" / "logs"
_FMT        = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_DATE       = "%Y-%m-%d %H:%M:%S"
_KEEP_DAYS  = 30


def _purge_old_logs() -> None:
    """Delete log files older than _KEEP_DAYS days."""
    cutoff = datetime.now() - timedelta(days=_KEEP_DAYS)
    removed = 0
    for log_file in _LOG_DIR.glob("proxyme-*.log"):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff:
                log_file.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        logging.getLogger(__name__).info(
            "Purged %d log file(s) older than %d days", removed, _KEEP_DAYS,
        )


def init_logging() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    session_ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file   = _LOG_DIR / f"proxyme-{session_ts}.log"

    formatter = logging.Formatter(_FMT, datefmt=_DATE)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    # Reduce verbosity of paramiko internals
    logging.getLogger("paramiko").setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Session started — log: %s", log_file.name)

    _purge_old_logs()
