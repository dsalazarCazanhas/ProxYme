from dataclasses import dataclass
from enum import Enum


class TunnelMode(Enum):
    LOCAL   = "local"    # localhost:local_port -> remote_host:remote_port
    DYNAMIC = "dynamic"  # SOCKS5 proxy on local_port


class AuthMethod(Enum):
    PASSWORD    = "password"  # noqa: S105 — enum discriminator, not a credential
    PRIVATE_KEY = "private_key"


@dataclass
class TunnelConfig:
    name:        str
    ssh_host:    str
    ssh_port:    int
    ssh_user:    str
    auth_method: AuthMethod
    mode:        TunnelMode
    local_port:  int
    remote_host: str | None  # None when mode=DYNAMIC
    remote_port: int | None  # None when mode=DYNAMIC
    key_path:    str | None  # path to private key file; None when auth_method=PASSWORD
    bind_all_interfaces: bool = False  # bind 0.0.0.0 instead of 127.0.0.1 (exposes to the LAN)
