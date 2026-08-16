"""Open a file with the user's preferred editor, falling back to the OS default app."""

import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

_log = logging.getLogger(__name__)


def _external_env() -> dict[str, str] | None:
    """Environment for launching external programs (editor, xdg-open, ...).

    PyInstaller's onefile bootloader points LD_LIBRARY_PATH at its bundled
    libraries so the frozen app can find them, then that value leaks to every
    child process it spawns. A child like xdg-open (or whatever it execs)
    can pick up a bundled library instead of its own and misbehave or fail
    silently — this only shows up in the packaged binary, never when running
    from source. Restore the pre-bundling value (saved by PyInstaller itself)
    before spawning anything external. Returns None when not running frozen,
    so subprocess falls back to inheriting the environment as-is.
    """
    if not hasattr(sys, "_MEIPASS"):
        return None
    env = os.environ.copy()
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original is not None:
        env["LD_LIBRARY_PATH"] = original
    else:
        env.pop("LD_LIBRARY_PATH", None)
    return env


def open_path(path: Path) -> None:
    """Open `path` with $VISUAL/$EDITOR if set (same convention as git/crontab),
    else the OS's default-app handler for that file."""
    env = _external_env()
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        try:
            subprocess.Popen(  # noqa: S603 — editor from user's own env
                [*shlex.split(editor), str(path)], env=env,
            )
            return
        except OSError as exc:
            _log.warning(
                "Could not launch $VISUAL/$EDITOR (%r): %s — falling back to OS default",
                editor, exc,
            )

    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 — caller-provided path, not attacker-controlled
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], env=env)  # noqa: S603,S607 — fixed launcher
    else:
        subprocess.run(["xdg-open", str(path)], env=env)  # noqa: S603,S607 — fixed launcher
