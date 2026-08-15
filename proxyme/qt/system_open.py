"""Open a file with the user's preferred editor, falling back to the OS default app."""

import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

_log = logging.getLogger(__name__)


def open_path(path: Path) -> None:
    """Open `path` with $VISUAL/$EDITOR if set (same convention as git/crontab),
    else the OS's default-app handler for that file."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        try:
            subprocess.Popen([*shlex.split(editor), str(path)])  # noqa: S603 — editor from user's own env
            return
        except OSError as exc:
            _log.warning(
                "Could not launch $VISUAL/$EDITOR (%r): %s — falling back to OS default",
                editor, exc,
            )

    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 — caller-provided path, not attacker-controlled
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)])  # noqa: S603,S607 — fixed launcher
    else:
        subprocess.run(["xdg-open", str(path)])  # noqa: S603,S607 — fixed launcher
