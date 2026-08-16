import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from proxyme.tunnel.models import TunnelMode

_CONFIG_DIR  = Path.home() / ".proxyme"
_CONFIG_FILE = _CONFIG_DIR / "tunnels.json"


@dataclass
class TunnelSupplement:
    """Stores only non-sensitive tunnel topology fields (never credentials)."""
    name:        str
    mode:        TunnelMode | None = None
    local_port:  int | None        = None
    remote_host: str | None        = None
    remote_port: int | None        = None
    bind_all_interfaces: bool      = False


def _to_dict(s: TunnelSupplement) -> dict:
    return {
        "name":        s.name,
        "mode":        s.mode.value if s.mode else None,
        "local_port":  s.local_port,
        "remote_host": s.remote_host,
        "remote_port": s.remote_port,
        "bind_all_interfaces": s.bind_all_interfaces,
    }


def _from_dict(data: dict) -> TunnelSupplement:
    mode_raw = data.get("mode")
    return TunnelSupplement(
        name        = data["name"],
        mode        = TunnelMode(mode_raw) if mode_raw else None,
        local_port  = data.get("local_port"),
        remote_host = data.get("remote_host"),
        remote_port = data.get("remote_port"),
        bind_all_interfaces = data.get("bind_all_interfaces", False),
    )


def load_all() -> list[TunnelSupplement]:
    if not _CONFIG_FILE.exists():
        return []
    with _CONFIG_FILE.open("r", encoding="utf-8") as f:
        raw: list[dict] = json.load(f)
    return [_from_dict(entry) for entry in raw]


def _secure_write(payload: str) -> None:
    """Write JSON with owner-only permissions (700 dir, 600 file) on POSIX."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        _CONFIG_DIR.chmod(0o700)
        fd = os.open(str(_CONFIG_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
    else:
        with _CONFIG_FILE.open("w", encoding="utf-8") as f:
            f.write(payload)


def save_all(supplements: list[TunnelSupplement]) -> None:
    _secure_write(json.dumps([_to_dict(s) for s in supplements], indent=2))


def find_by_name(name: str) -> TunnelSupplement | None:
    return next((s for s in load_all() if s.name == name), None)


def upsert(supplement: TunnelSupplement) -> None:
    items = load_all()
    for i, existing in enumerate(items):
        if existing.name == supplement.name:
            items[i] = supplement
            save_all(items)
            return
    items.append(supplement)
    save_all(items)


def delete_by_name(name: str) -> None:
    save_all([s for s in load_all() if s.name != name])
