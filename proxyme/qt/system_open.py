"""Open a file with the user's preferred editor, or an app the user picks explicitly."""

import json
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

_log = logging.getLogger(__name__)

_SETTINGS_FILE = Path.home() / ".proxyme" / "settings.json"


def _external_env() -> dict[str, str] | None:
    """Environment for launching external programs (editor, chosen app, ...).

    PyInstaller's onefile bootloader points LD_LIBRARY_PATH at its bundled
    libraries so the frozen app can find them, then that value leaks to every
    child process it spawns. A child process can pick up a bundled library
    instead of its own and misbehave or fail silently — this only shows up
    in the packaged binary, never when running from source. Restore the
    pre-bundling value (saved by PyInstaller itself) before spawning
    anything external. Returns None when not running frozen, so subprocess
    falls back to inheriting the environment as-is.
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


def _load_preferred_app() -> str | None:
    if not _SETTINGS_FILE.exists():
        return None
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.debug("Could not read %s: %s", _SETTINGS_FILE, exc)
        return None
    return data.get("preferred_app")


def _save_preferred_app(app_path: str) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps({"preferred_app": app_path}), encoding="utf-8")


def _ask_for_app(parent: QWidget | None) -> str | None:
    app_path, _ = QFileDialog.getOpenFileName(
        parent, "Choose an application to open this file with",
        "/usr/bin" if sys.platform not in ("win32", "darwin") else "",
        "All files (*)",
    )
    return app_path or None


def open_path(path: Path, parent: QWidget | None = None) -> None:
    """Open `path` with $VISUAL/$EDITOR if set (same convention as git/crontab).

    Otherwise, launch an app the user explicitly picked (remembered from a
    previous pick, or asked for now). Deliberately does NOT guess at an
    OS "default app": relying on xdg-open/gio's mime-type resolution proved
    unreliable from the packaged binary (mismatched bundled libraries,
    ambiguous extension-less files like ~/.ssh/config) — asking once and
    remembering the answer sidesteps that entirely.
    """
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
                "Could not launch $VISUAL/$EDITOR (%r): %s — asking which app to use",
                editor, exc,
            )

    app_path = _load_preferred_app()
    if app_path and not Path(app_path).exists():
        _log.info("Remembered app %r no longer exists — asking again", app_path)
        app_path = None

    if app_path is None:
        app_path = _ask_for_app(parent)
        if app_path is None:
            return
        _save_preferred_app(app_path)

    try:
        subprocess.Popen([app_path, str(path)], env=env)  # noqa: S603 — app chosen by the user
    except OSError as exc:
        _log.warning("Could not launch %r: %s", app_path, exc)
