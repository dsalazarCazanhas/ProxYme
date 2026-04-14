import paramiko

from .base import AuthStrategy


class PasswordAuth(AuthStrategy):
    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply(self, transport: paramiko.Transport) -> None:
        transport.auth_password(self._username, self._password)
