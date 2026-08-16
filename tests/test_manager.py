import logging
import socket
import threading
import time
from pathlib import Path

import paramiko
import pytest

from proxyme.tunnel.manager import TunnelWorker, _ForwardServer, _Socks5Handler, _Socks5Server
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


class TestBindAllInterfaces:
    """bind_all_interfaces controls whether local servers listen on 127.0.0.1
    (default, safest) or 0.0.0.0 (reachable from other devices/containers)."""

    def _free_port(self) -> int:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        return port

    def test_forward_server_defaults_to_loopback_only(self, mocker):
        server = _ForwardServer(self._free_port(), mocker.Mock(), "db.internal", 5432)
        try:
            assert server.server_address[0] == "127.0.0.1"
        finally:
            server.server_close()

    def test_forward_server_binds_all_interfaces_when_requested(self, mocker):
        server = _ForwardServer(
            self._free_port(), mocker.Mock(), "db.internal", 5432, bind_all_interfaces=True,
        )
        try:
            assert server.server_address[0] == "0.0.0.0"  # noqa: S104
        finally:
            server.server_close()

    def test_socks5_server_defaults_to_loopback_only(self, mocker):
        server = _Socks5Server(self._free_port(), mocker.Mock())
        try:
            assert server.server_address[0] == "127.0.0.1"
        finally:
            server.server_close()

    def test_socks5_server_binds_all_interfaces_when_requested(self, mocker):
        server = _Socks5Server(self._free_port(), mocker.Mock(), bind_all_interfaces=True)
        try:
            assert server.server_address[0] == "0.0.0.0"  # noqa: S104
        finally:
            server.server_close()


class TestLocalBindFailure:
    """Regression coverage for a real bug found in production: when the SSH
    handshake succeeds but binding the local listener fails (e.g. the local
    port is already in use), the actual error used to vanish — it was only
    emitted as a Qt signal, never logged, and the UI briefly showed
    "Connected" before flipping back to idle with no visible reason why."""

    @pytest.fixture
    def occupied_port(self):
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        yield port
        blocker.close()

    def _worker_with_mocked_ssh(self, mocker, config):
        worker = TunnelWorker(config, auth=mocker.Mock())
        mocker.patch("socket.create_connection", return_value=mocker.Mock())
        mocker.patch("paramiko.Transport", return_value=mocker.Mock(is_active=lambda: False))
        mocker.patch.object(worker, "_verify_host_key", return_value=(True, ""))
        return worker

    def test_bind_failure_is_logged_not_just_signaled(self, occupied_port, mocker, caplog):
        config = _make_config(mode=TunnelMode.DYNAMIC, local_port=occupied_port,
                               remote_host=None, remote_port=None)
        worker = self._worker_with_mocked_ssh(mocker, config)

        failed_messages = []
        worker.failed.connect(failed_messages.append)

        with caplog.at_level(logging.WARNING, logger="proxyme.tunnel.manager"):
            worker.run()

        assert failed_messages, "failed signal should fire when the local bind fails"
        assert any(
            "connection failed" in rec.message.lower() and failed_messages[0] in rec.message
            for rec in caplog.records
        ), "the actual bind error must be logged, not only emitted as a signal"

    def test_connected_signal_does_not_fire_before_bind_succeeds(self, occupied_port, mocker):
        config = _make_config(mode=TunnelMode.DYNAMIC, local_port=occupied_port,
                               remote_host=None, remote_port=None)
        worker = self._worker_with_mocked_ssh(mocker, config)

        connected = mocker.Mock()
        worker.connected.connect(connected)

        worker.run()

        connected.assert_not_called()

    def test_local_mode_bind_failure_also_logged(self, occupied_port, mocker, caplog):
        config = _make_config(mode=TunnelMode.LOCAL, local_port=occupied_port,
                               remote_host="db.internal", remote_port=5432)
        worker = self._worker_with_mocked_ssh(mocker, config)

        failed_messages = []
        worker.failed.connect(failed_messages.append)

        with caplog.at_level(logging.WARNING, logger="proxyme.tunnel.manager"):
            worker.run()

        assert failed_messages
        assert any("connection failed" in rec.message.lower() for rec in caplog.records)


class TestStopReleasesTheLocalPort:
    """Regression test for a real bug found in production: stop() called
    server.shutdown() (which only stops the serve_forever() loop) but never
    server_close() (which actually releases the socket), so the local port
    stayed bound after "stop" and the next Start always failed with
    "Address already in use"."""

    def _worker_with_mocked_ssh(self, mocker, config):
        worker = TunnelWorker(config, auth=mocker.Mock())
        mocker.patch("socket.create_connection", return_value=mocker.Mock())
        mocker.patch("paramiko.Transport", return_value=mocker.Mock(is_active=lambda: False))
        mocker.patch.object(worker, "_verify_host_key", return_value=(True, ""))
        return worker

    def test_local_port_is_free_again_immediately_after_stop(self, mocker):
        # Let the OS hand out a free port rather than guessing one.
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()

        config = _make_config(mode=TunnelMode.DYNAMIC, local_port=port,
                               remote_host=None, remote_port=None)
        worker = self._worker_with_mocked_ssh(mocker, config)

        # Poll worker state directly rather than relying on Qt signals — signals
        # emitted from a plain (non-QThread) background thread aren't delivered
        # without an active Qt event loop pumping them, which this test has none
        # of. Thread completion via join() needs no event loop and is reliable.
        run_thread = threading.Thread(target=worker.run, daemon=True)
        run_thread.start()

        deadline = time.monotonic() + 5
        while worker._server is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert worker._server is not None, "worker never reached the serving phase"

        worker.stop()
        run_thread.join(timeout=5)
        assert not run_thread.is_alive(), "worker thread never finished stopping"

        # The real assertion: the port must be immediately bindable again —
        # this is exactly what a second Start attempt does.
        retry = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            retry.bind(("127.0.0.1", port))
        except OSError as exc:
            pytest.fail(f"local port {port} was not released after stop(): {exc}")
        finally:
            retry.close()
