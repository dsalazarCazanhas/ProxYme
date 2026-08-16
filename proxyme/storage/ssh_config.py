import getpass
import logging
import os
from pathlib import Path
from typing import TypeVar

import paramiko

from proxyme.storage import repository
from proxyme.storage.repository import TunnelSupplement
from proxyme.tunnel.models import AuthMethod, TunnelConfig, TunnelMode

_T = TypeVar("_T")

_log = logging.getLogger(__name__)

_SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"

# Sentinel — marks a field as absent in the SSH config
_MISSING = object()


def _load_ssh_config() -> paramiko.SSHConfig:
    config = paramiko.SSHConfig()
    if _SSH_CONFIG_PATH.exists():
        with _SSH_CONFIG_PATH.open("r", encoding="utf-8") as f:
            config.parse(f)
    return config


def load_hosts() -> list[str]:
    """Return all named Host aliases from ~/.ssh/config (excludes wildcard '*')."""
    config = _load_ssh_config()
    return [h for h in config.get_hostnames() if h != "*"]


def resolve_tunnel(host_alias: str) -> TunnelConfig:
    """
    Build a TunnelConfig by merging ~/.ssh/config (primary) with
    ~/.proxyme/tunnels.json (supplement for missing fields).

    Raises ValueError if critical fields are still missing after merging.
    """
    ssh_data   = _load_ssh_config().lookup(host_alias)
    supplement = repository.find_by_name(host_alias)  # may be None

    # --- SSH connection fields (SSH config is primary) ---
    ssh_host = _resolve_field("ssh_host",  ssh_data.get("hostname"), supplement)
    ssh_port = _parse_port(ssh_data.get("port")) or 22
    ssh_user = _resolve_field("ssh_user",  ssh_data.get("user", getpass.getuser()), supplement)

    # --- Identity / auth method ---
    identity_files = _as_list(ssh_data.get("identityfile"))
    key_path = _resolve_field("key_path", _first(identity_files), supplement)
    # Never persisted in the supplement (credentials aren't stored) — always derived.
    auth_method = AuthMethod.PRIVATE_KEY if key_path else AuthMethod.PASSWORD

    # --- Forwarding mode ---
    local_forwards   = _as_list(ssh_data.get("localforward"))
    dynamic_forwards = _as_list(ssh_data.get("dynamicforward"))

    if local_forwards:
        mode, local_port, remote_host, remote_port, bind_all = _parse_local_forward(
            local_forwards[0],
        )
    elif dynamic_forwards:
        mode        = TunnelMode.DYNAMIC
        bind_all, local_port = _parse_bind_and_port(dynamic_forwards[0])
        remote_host = None
        remote_port = None
    else:
        # No forwarding in SSH config — require supplement
        mode        = _resolve_field("mode",        None, supplement)
        local_port  = _resolve_field("local_port",  None, supplement)
        remote_host = _resolve_field("remote_host", None, supplement)
        remote_port = _resolve_field("remote_port", None, supplement)
        bind_all    = getattr(supplement, "bind_all_interfaces", False) if supplement else False

    # --- Validate critical fields (rebind to narrow Optional away) ---
    ssh_host    = _require(ssh_host,    "ssh_host",    host_alias)
    ssh_port    = _require(ssh_port,    "ssh_port",    host_alias)
    ssh_user    = _require(ssh_user,    "ssh_user",    host_alias)
    auth_method = _require(auth_method, "auth_method", host_alias)
    mode        = _require(mode,        "mode",        host_alias)
    local_port  = _require(local_port,  "local_port",  host_alias)
    if mode == TunnelMode.LOCAL:
        _require(remote_host, "remote_host", host_alias)
        _require(remote_port, "remote_port", host_alias)

    return TunnelConfig(
        name        = host_alias,
        ssh_host    = ssh_host,
        ssh_port    = ssh_port,
        ssh_user    = ssh_user,
        auth_method = auth_method,
        mode        = mode,
        local_port  = local_port,
        remote_host = remote_host,
        remote_port = remote_port,
        key_path    = _expand_key_path(key_path),
        bind_all_interfaces = bind_all,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_field(field: str, ssh_value, supplement: TunnelSupplement | None):
    """Return ssh_value if present, else the same field from supplement, else None."""
    if ssh_value is not None:
        return ssh_value
    if supplement is not None:
        return getattr(supplement, field, None)
    return None


def _parse_port(raw: str | None) -> int | None:
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _first(items: list) -> str | None:
    return items[0] if items else None


_BIND_ALL_ADDRESSES = {"0.0.0.0", "*"}  # noqa: S104 — recognizing, not choosing, the bind address


def _parse_bind_and_port(raw: str) -> tuple[bool, int]:
    """Parse a "[bind_addr:]port" value (used by DynamicForward, and the local
    side of LocalForward). Returns (bind_all_interfaces, port)."""
    bind_addr, _, port_str = raw.strip().rpartition(":")
    return bind_addr in _BIND_ALL_ADDRESSES, int(port_str)


def _parse_local_forward(raw: str):
    """
    Parse a LocalForward value.
    Accepted formats:
      "5432 db.internal:5432"
      "127.0.0.1:5432 db.internal:5432"
      "0.0.0.0:5432 db.internal:5432"
    """
    parts = raw.strip().split()
    if len(parts) != 2:
        raise ValueError(f"Cannot parse LocalForward value: {raw!r}")

    local_part, remote_part = parts

    bind_all, local_port = _parse_bind_and_port(local_part)

    # remote side — always "host:port"
    remote_host, _, remote_port_str = remote_part.rpartition(":")
    remote_port = int(remote_port_str)

    return TunnelMode.LOCAL, local_port, remote_host, remote_port, bind_all


def _expand_key_path(path: str | None) -> str | None:
    """Expand ~ and env vars in key paths, never log the result."""
    if path is None:
        return None
    return str(Path(os.path.expandvars(path)).expanduser())


def peek_tunnel_gaps(host_alias: str) -> set[str]:
    """
    Return the set of field names that are missing for a complete TunnelConfig,
    after merging SSH config and JSON supplement. Never raises.
    Fields: 'mode', 'local_port', 'remote_host', 'remote_port'
    """
    ssh_data   = _load_ssh_config().lookup(host_alias)
    supplement = repository.find_by_name(host_alias)

    local_forwards   = _as_list(ssh_data.get("localforward"))
    dynamic_forwards = _as_list(ssh_data.get("dynamicforward"))

    gaps: set[str] = set()

    if local_forwards or dynamic_forwards:
        return gaps  # forwarding fully defined in SSH config

    # Check supplement
    mode        = getattr(supplement, "mode",        None) if supplement else None
    local_port  = getattr(supplement, "local_port",  None) if supplement else None
    remote_host = getattr(supplement, "remote_host", None) if supplement else None
    remote_port = getattr(supplement, "remote_port", None) if supplement else None

    if mode is None:
        gaps.add("mode")
    if local_port is None:
        gaps.add("local_port")
    if mode == TunnelMode.LOCAL or mode is None:
        if remote_host is None:
            gaps.add("remote_host")
        if remote_port is None:
            gaps.add("remote_port")

    return gaps


def format_host_block(config: TunnelConfig) -> str:
    """Render a TunnelConfig as a ~/.ssh/config `Host` block, for the user to copy
    and paste by hand. ProxYme never writes to ~/.ssh/config itself.

    Password auth has no SSH config equivalent, so nothing credential-related is
    ever included here — only topology (host, port, identity file path, forwarding).
    """
    lines = [f"Host {config.name}"]
    lines.append(f"    HostName {config.ssh_host}")
    lines.append(f"    User {config.ssh_user}")
    if config.ssh_port != 22:
        lines.append(f"    Port {config.ssh_port}")
    if config.auth_method == AuthMethod.PRIVATE_KEY and config.key_path:
        lines.append(f"    IdentityFile {config.key_path}")
    bind_prefix = "0.0.0.0:" if config.bind_all_interfaces else ""
    if config.mode == TunnelMode.LOCAL:
        lines.append(
            f"    LocalForward {bind_prefix}{config.local_port} "
            f"{config.remote_host}:{config.remote_port}"
        )
    elif config.mode == TunnelMode.DYNAMIC:
        lines.append(f"    DynamicForward {bind_prefix}{config.local_port}")
    return "\n".join(lines)


def peek_auth_method(host_alias: str) -> AuthMethod:
    """Return the auth method detectable from SSH config alone."""
    ssh_data = _load_ssh_config().lookup(host_alias)
    identity_files = _as_list(ssh_data.get("identityfile"))
    return AuthMethod.PRIVATE_KEY if identity_files else AuthMethod.PASSWORD


def get_key_filename(host_alias: str) -> str | None:
    """Return the filename (not full path) of the first IdentityFile, or None."""
    ssh_data = _load_ssh_config().lookup(host_alias)
    identity_files = _as_list(ssh_data.get("identityfile"))
    return Path(identity_files[0]).name if identity_files else None


def get_key_path(host_alias: str) -> str | None:
    """Return the full expanded path of the first IdentityFile, or None."""
    ssh_data = _load_ssh_config().lookup(host_alias)
    identity_files = _as_list(ssh_data.get("identityfile"))
    return _expand_key_path(_first(identity_files))


def _as_list(val: object) -> list[str]:
    """Normalise a paramiko SSHConfig value to list[str]."""
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, str):
        return [val]
    return []


def _require(value: _T | None, field: str, alias: str) -> _T:
    if value is None:
        _log.warning("Missing field '%s' for host '%s'", field, alias)
        raise ValueError(
            f"Missing required field '{field}' for host '{alias}'. "
            f"Define it in ~/.ssh/config or add a supplement entry in ~/.proxyme/tunnels.json."
        )
    return value


def resolve_tunnel_partial(host_alias: str) -> dict:
    """
    Like resolve_tunnel() but never raises.
    Returns a dict with keys: mode, local_port, remote_host, remote_port.
    Values are None when not resolved.
    """
    ssh_data   = _load_ssh_config().lookup(host_alias)
    supplement = repository.find_by_name(host_alias)

    local_forwards   = _as_list(ssh_data.get("localforward"))
    dynamic_forwards = _as_list(ssh_data.get("dynamicforward"))

    if local_forwards:
        _, local_port, remote_host, remote_port, bind_all = _parse_local_forward(
            local_forwards[0],
        )
        mode = TunnelMode.LOCAL
    elif dynamic_forwards:
        mode        = TunnelMode.DYNAMIC
        bind_all, local_port = _parse_bind_and_port(dynamic_forwards[0])
        remote_host = None
        remote_port = None
    else:
        mode        = getattr(supplement, "mode",        None) if supplement else None
        local_port  = getattr(supplement, "local_port",  None) if supplement else None
        remote_host = getattr(supplement, "remote_host", None) if supplement else None
        remote_port = getattr(supplement, "remote_port", None) if supplement else None
        bind_all    = getattr(supplement, "bind_all_interfaces", False) if supplement else False

    return {
        "mode":        mode,
        "local_port":  local_port,
        "remote_host": remote_host,
        "remote_port": remote_port,
        "bind_all_interfaces": bind_all,
    }
