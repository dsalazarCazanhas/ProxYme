from typing import Optional

import paramiko

from .base import AuthStrategy


def load_private_key(key_path: Optional[str], passphrase: Optional[str] = None) -> paramiko.PKey:
    """
    Load a private key trying each supported type in order.
    Raises PasswordRequiredException if the key is passphrase-protected and none was given.
    Raises ValueError if the file cannot be parsed as any known key type.
    """
    if key_path is None:
        raise ValueError("No private key path configured for this host.")
    password = passphrase.encode() if passphrase else None
    # DSSKey (DSA) was removed in paramiko 3.x; only include classes that exist.
    key_classes = [
        cls for cls in [
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
            paramiko.RSAKey,
            getattr(paramiko, "DSSKey", None),
        ]
        if cls is not None
    ]
    last_exc: Exception = ValueError(f"Could not load private key: {key_path}")
    for cls in key_classes:
        try:
            return cls.from_private_key_file(key_path, password=password)
        except paramiko.PasswordRequiredException:
            raise
        except Exception as exc:
            last_exc = exc
    raise last_exc


class PrivateKeyAuth(AuthStrategy):
    def __init__(self, username: str, key_path: Optional[str], passphrase: Optional[str] = None) -> None:
        self._username   = username
        self._key_path   = key_path
        self._passphrase = passphrase

    def apply(self, transport: paramiko.Transport) -> None:
        key = load_private_key(self._key_path, self._passphrase)
        transport.auth_publickey(self._username, key)
