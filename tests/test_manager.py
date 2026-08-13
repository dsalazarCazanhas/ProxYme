from pathlib import Path

import paramiko
import pytest

from proxyme.tunnel.manager import TunnelWorker, _Socks5Handler
from proxyme.tunnel.models import AuthMethod, TunnelConfig, TunnelMode


def _make_config(**overrides) -> TunnelConfig:
    defaults = {
        "name": "db", "ssh_host": "db.internal", "ssh_port": 22, "ssh_user": "alice",
        "auth_method": AuthMethod.PASSWORD, "mode": TunnelMode.LOCAL, "local_port": 5432,
        "remote_host": "db.internal", "remote_port": 5432, "key_path": None,
    }
    defaults.update(overrides)
    return TunnelConfig(**defaults)


@pytest.fixture(scope="module")
def fake_key():
    return paramiko.RSAKey.generate(1024)


@pytest.fixture(scope="module")
def other_key():
    return paramiko.RSAKey.generate(1024)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """_verify_host_key reads/writes ~/.ssh/known_hosts directly via Path.home()."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


class TestVerifyHostKeyTOFU:
    def test_unknown_host_prompts_and_saves_on_accept(self, isolated_home, mocker, fake_key):
        config = _make_config()
        worker = TunnelWorker(config, auth=mocker.Mock())
        worker._transport = mocker.Mock()
        worker._transport.get_remote_server_key.return_value = fake_key

        worker.host_key_unknown.connect(lambda *_: worker.resolve_host_key(True))

        ok, reason = worker._verify_host_key()

        assert (ok, reason) == (True, "")
        known_hosts = isolated_home / ".ssh" / "known_hosts"
        assert known_hosts.exists()
        hk = paramiko.HostKeys(str(known_hosts))
        assert hk.check("db.internal", fake_key)

    def test_unknown_host_rejected_by_user(self, isolated_home, mocker, fake_key):
        config = _make_config()
        worker = TunnelWorker(config, auth=mocker.Mock())
        worker._transport = mocker.Mock()
        worker._transport.get_remote_server_key.return_value = fake_key

        worker.host_key_unknown.connect(lambda *_: worker.resolve_host_key(False))

        ok, reason = worker._verify_host_key()

        assert ok is False
        assert "not accepted" in reason
        assert not (isolated_home / ".ssh" / "known_hosts").exists()

    def test_known_matching_host_passes_without_prompting(self, isolated_home, mocker, fake_key):
        known_hosts_path = isolated_home / ".ssh" / "known_hosts"
        known_hosts_path.parent.mkdir(parents=True)
        hk = paramiko.HostKeys()
        hk.add("db.internal", fake_key.get_name(), fake_key)
        hk.save(str(known_hosts_path))

        config = _make_config()
        worker = TunnelWorker(config, auth=mocker.Mock())
        worker._transport = mocker.Mock()
        worker._transport.get_remote_server_key.return_value = fake_key

        prompted = mocker.Mock()
        worker.host_key_unknown.connect(prompted)

        ok, reason = worker._verify_host_key()

        assert (ok, reason) == (True, "")
        prompted.assert_not_called()

    def test_changed_key_is_rejected_as_possible_mitm(
        self, isolated_home, mocker, fake_key, other_key,
    ):
        known_hosts_path = isolated_home / ".ssh" / "known_hosts"
        known_hosts_path.parent.mkdir(parents=True)
        hk = paramiko.HostKeys()
        hk.add("db.internal", other_key.get_name(), other_key)
        hk.save(str(known_hosts_path))

        config = _make_config()
        worker = TunnelWorker(config, auth=mocker.Mock())
        worker._transport = mocker.Mock()
        worker._transport.get_remote_server_key.return_value = fake_key  # different from stored

        mismatch_signal = mocker.Mock()
        worker.host_key_mismatch.connect(mismatch_signal)

        ok, reason = worker._verify_host_key()

        assert ok is False
        assert "IDENTIFICATION HAS CHANGED" in reason
        mismatch_signal.assert_called_once()


class TestSocks5RecvExact:
    class _FakeSocket:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def recv(self, n: int) -> bytes:
            chunk, self._data = self._data[:n], self._data[n:]
            return chunk

    class _FakeHandler:
        """Bare object exposing just the `.request` attribute _recv_exact needs."""
        def __init__(self, data: bytes) -> None:
            self.request = TestSocks5RecvExact._FakeSocket(data)

    def test_reads_exactly_n_bytes_across_multiple_recv_calls(self):
        handler = self._FakeHandler(b"hello world")
        assert _Socks5Handler._recv_exact(handler, 5) == b"hello"
        assert _Socks5Handler._recv_exact(handler, 6) == b" world"

    def test_raises_when_peer_closes_mid_handshake(self):
        handler = self._FakeHandler(b"")
        with pytest.raises(ConnectionResetError):
            _Socks5Handler._recv_exact(handler, 3)
