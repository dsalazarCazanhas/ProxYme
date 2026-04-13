from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TunnelMode(Enum):
    LOCAL   = "local"    # localhost:local_port -> remote_host:remote_port
    DYNAMIC = "dynamic"  # SOCKS5 proxy on local_port


class AuthMethod(Enum):
    PASSWORD    = "password"
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
    remote_host: Optional[str]  # None when mode=DYNAMIC
    remote_port: Optional[int]  # None when mode=DYNAMIC
    key_path:    Optional[str]  # path to private key file; None when auth_method=PASSWORD
