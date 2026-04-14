from abc import ABC, abstractmethod

import paramiko


class AuthStrategy(ABC):
    @abstractmethod
    def apply(self, transport: paramiko.Transport) -> None:
        """Authenticate the given SSH transport."""
        ...
