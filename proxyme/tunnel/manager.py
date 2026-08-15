import base64
import hashlib
import logging
import select
import socket
import socketserver
import struct
import threading
from pathlib import Path

import paramiko
from PySide6.QtCore import QObject, QThread, Signal

from .auth.base import AuthStrategy
from .models import TunnelConfig, TunnelMode

_log = logging.getLogger(__name__)

_CONNECTION_TIMEOUT_S = 13  # bounds both the TCP connect and the SSH handshake


# ---------------------------------------------------------------------------
# SOCKS5 dynamic forwarding internals  (RFC 1928)
# ---------------------------------------------------------------------------

class _Socks5Handler(socketserver.BaseRequestHandler):
    """Minimal SOCKS5 handler — no auth, IPv4/IPv6/domain CONNECT only."""

    _SOCKS_VERSION = 5

    def handle(self) -> None:
        try:
            self._do_handle()
        except (ConnectionResetError, ConnectionAbortedError, OSError) as exc:
            _log.debug("SOCKS5: client disconnected early: %s", exc)

    def _do_handle(self) -> None:
        transport: paramiko.Transport = self.server.ssh_transport  # type: ignore[attr-defined]
        sock = self.request

        # --- Greeting ---
        header = self._recv_exact(2)
        if not header or header[0] != self._SOCKS_VERSION:
            return
        n_methods = header[1]
        self._recv_exact(n_methods)  # discard method list
        sock.sendall(bytes([self._SOCKS_VERSION, 0]))  # no auth

        # --- Request ---
        req = self._recv_exact(4)
        if not req or req[0] != self._SOCKS_VERSION or req[1] != 1:  # CMD=CONNECT only
            # command not supported
            sock.sendall(bytes([self._SOCKS_VERSION, 7, 0, 1, 0, 0, 0, 0, 0, 0]))
            return

        atyp = req[3]
        if atyp == 1:       # IPv4
            raw = self._recv_exact(4)
            host = socket.inet_ntoa(raw)
        elif atyp == 3:     # domain name
            length = self._recv_exact(1)[0]
            host = self._recv_exact(length).decode("utf-8", errors="replace")
        elif atyp == 4:     # IPv6
            raw = self._recv_exact(16)
            host = socket.inet_ntop(socket.AF_INET6, raw)
        else:
            # address type not supported
            sock.sendall(bytes([self._SOCKS_VERSION, 8, 0, 1, 0, 0, 0, 0, 0, 0]))
            return

        port_raw = self._recv_exact(2)
        port = struct.unpack("!H", port_raw)[0]

        # --- Open SSH channel ---
        try:
            channel = transport.open_channel(
                "direct-tcpip",
                (host, port),
                sock.getpeername(),
            )
        except Exception as exc:
            _log.debug("SOCKS5: could not open channel to %s:%s — %s", host, port, exc)
            # connection refused
            sock.sendall(bytes([self._SOCKS_VERSION, 5, 0, 1, 0, 0, 0, 0, 0, 0]))
            return

        # Success reply — bind address 0.0.0.0:0
        sock.sendall(bytes([self._SOCKS_VERSION, 0, 0, 1, 0, 0, 0, 0, 0, 0]))
        _log.debug("SOCKS5: forwarding %s:%s", host, port)

        # --- Relay ---
        try:
            while True:
                readable, _, _ = select.select([sock, channel], [], [], 1.0)
                if sock in readable:
                    data = sock.recv(4096)
                    if not data:
                        break
                    channel.send(data)
                if channel in readable:
                    data = channel.recv(4096)
                    if not data:
                        break
                    sock.send(data)
        except Exception as exc:
            _log.debug("SOCKS5 relay error: %s", exc)
        finally:
            channel.close()

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.request.recv(n - len(buf))
            if not chunk:
                raise ConnectionResetError("SOCKS5: connection closed mid-handshake")
            buf += chunk
        return buf


class _Socks5Server(socketserver.ThreadingTCPServer):
    """Local SOCKS5 proxy that tunnels every connection through an SSH transport."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, local_port: int, ssh_transport: paramiko.Transport) -> None:
        self.ssh_transport = ssh_transport
        super().__init__(("127.0.0.1", local_port), _Socks5Handler)


# ---------------------------------------------------------------------------
# Local forwarding internals
# ---------------------------------------------------------------------------

class _ForwardHandler(socketserver.BaseRequestHandler):
    """Handles one local TCP connection by forwarding it through an SSH channel."""

    def handle(self) -> None:
        transport: paramiko.Transport = self.server.ssh_transport  # type: ignore[attr-defined]
        remote_host: str = self.server.remote_host               # type: ignore[attr-defined]
        remote_port: int = self.server.remote_port               # type: ignore[attr-defined]

        try:
            channel = transport.open_channel(
                "direct-tcpip",
                (remote_host, remote_port),
                self.request.getpeername(),
            )
        except Exception:
            return

        try:
            while True:
                readable, _, _ = select.select([self.request, channel], [], [], 1.0)
                if self.request in readable:
                    data = self.request.recv(4096)
                    if not data:
                        break
                    channel.send(data)
                if channel in readable:
                    data = channel.recv(4096)
                    if not data:
                        break
                    self.request.send(data)
        except Exception as exc:
            _log.debug("Forward handler error (channel closed or network): %s", exc)
        finally:
            channel.close()


class _ForwardServer(socketserver.ThreadingTCPServer):
    """Local TCP server that forwards each connection through an SSH transport."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        local_port: int,
        ssh_transport: paramiko.Transport,
        remote_host: str,
        remote_port: int,
    ) -> None:
        self.ssh_transport = ssh_transport
        self.remote_host = remote_host
        self.remote_port = remote_port
        super().__init__(("127.0.0.1", local_port), _ForwardHandler)


# ---------------------------------------------------------------------------
# Worker — runs in a secondary QThread
# ---------------------------------------------------------------------------

class TunnelWorker(QObject):
    connected         = Signal()
    failed            = Signal(str)
    stopped           = Signal()
    host_key_unknown  = Signal(str, str, str)  # hostname, key_type, fingerprint
    host_key_mismatch = Signal(str, str, str)  # hostname, key_type, fingerprint

    def __init__(self, config: TunnelConfig, auth: AuthStrategy) -> None:
        super().__init__()
        self._config    = config
        self._auth      = auth
        self._sock:      socket.socket | None = None
        self._transport: paramiko.Transport | None = None
        self._server:    socketserver.BaseServer | None = None
        self._host_key_event:    threading.Event | None = None
        self._host_key_accepted: bool                      = False
        self._cancelled: bool = False

    def run(self) -> None:
        _log.info("Connecting to %s:%s (mode=%s)",
                  self._config.ssh_host, self._config.ssh_port, self._config.mode.value)
        try:
            sock = socket.create_connection(
                (self._config.ssh_host, self._config.ssh_port), timeout=_CONNECTION_TIMEOUT_S,
            )
            self._sock = sock
            if self._cancelled:
                raise OSError("Connection cancelled.")
            self._transport = paramiko.Transport(sock)
            self._transport.start_client(timeout=_CONNECTION_TIMEOUT_S)
            ok, reason = self._verify_host_key()
            if not ok:
                _log.warning("Host key verification failed: %s", reason)
                self.failed.emit(reason)
                self._close_connecting()
                return
            self._auth.apply(self._transport)

            # Bind the local listener while still in the "connecting" phase —
            # a failure here (e.g. the local port is already in use) gets
            # reported the same way as an auth/handshake failure, instead of
            # flashing "Connected" for an instant and then dying, with the
            # real reason visible nowhere but a signal nobody logged.
            if self._config.mode == TunnelMode.LOCAL:
                assert self._config.remote_host is not None
                assert self._config.remote_port is not None
                self._server = _ForwardServer(
                    self._config.local_port, self._transport,
                    self._config.remote_host, self._config.remote_port,
                )
            elif self._config.mode == TunnelMode.DYNAMIC:
                self._server = _Socks5Server(self._config.local_port, self._transport)
        except Exception as exc:
            if self._cancelled:
                _log.info("Connection attempt cancelled by user")
                self.failed.emit("Connection cancelled.")
            else:
                _log.warning("Connection failed: %s", exc)
                self.failed.emit(str(exc))
            self._close_connecting()
            return

        _log.info("Tunnel established — local port %s", self._config.local_port)
        self.connected.emit()

        # --- run the forwarding loop (blocks until stop() is called) ---
        try:
            self._server.serve_forever()
        except Exception as exc:
            _log.warning("Tunnel serving loop failed: %s", exc)
            self.failed.emit(str(exc))
        finally:
            if self._transport and self._transport.is_active():
                self._transport.close()
            _log.info("Tunnel stopped")
            self.stopped.emit()

    def _close_connecting(self) -> None:
        """Best-effort cleanup of a socket/transport that never reached the serving phase."""
        if self._transport is not None:
            try:
                self._transport.close()
            except Exception as exc:
                _log.debug("Error closing transport after failed connect: %s", exc)
        elif self._sock is not None:
            try:
                self._sock.close()
            except OSError as exc:
                _log.debug("Error closing socket after failed connect: %s", exc)

    def _verify_host_key(self) -> tuple[bool, str]:
        """TOFU host key verification. Returns (ok, error_message)."""
        assert self._transport is not None
        server_key = self._transport.get_remote_server_key()
        hostname   = self._config.ssh_host
        key_type   = server_key.get_name()
        digest     = hashlib.sha256(server_key.asbytes()).digest()
        fingerprint = "SHA256:" + base64.b64encode(digest).decode().rstrip("=")

        known_hosts_path = Path.home() / ".ssh" / "known_hosts"
        hk = paramiko.HostKeys()
        if known_hosts_path.exists():
            try:
                hk.load(str(known_hosts_path))
            except Exception as exc:
                _log.debug("Corrupted known_hosts — treating as empty: %s", exc)

        existing = hk.lookup(hostname)
        if existing is not None:
            if hk.check(hostname, server_key):
                _log.debug("Host key verified for %s", hostname)
                return True, ""
            # Key changed — possible MITM, always abort
            _log.error("Host key MISMATCH for %s — possible MITM!", hostname)
            self.host_key_mismatch.emit(hostname, key_type, fingerprint)
            return False, "REMOTE HOST IDENTIFICATION HAS CHANGED — connection aborted."

        # Unknown host — ask user (TOFU)
        _log.info("Unknown host %s (%s %s) — asking user", hostname, key_type, fingerprint)
        self._host_key_event    = threading.Event()
        self._host_key_accepted = False
        self.host_key_unknown.emit(hostname, key_type, fingerprint)
        timed_out = not self._host_key_event.wait(timeout=60.0)

        if timed_out or not self._host_key_accepted:
            return False, "Connection cancelled: host key not accepted."

        # Save to known_hosts
        try:
            known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
            hk.add(hostname, key_type, server_key)
            hk.save(str(known_hosts_path))
            _log.info("Saved host key for %s to known_hosts", hostname)
        except Exception as exc:
            _log.warning("Could not save host key to known_hosts: %s", exc)

        return True, ""

    def resolve_host_key(self, accept: bool) -> None:
        """Called from main thread to unblock host key verification."""
        self._host_key_accepted = accept
        if self._host_key_event is not None:
            self._host_key_event.set()

    def stop(self) -> None:
        """Signal the worker to stop cleanly. Thread-safe."""
        self._cancelled = True
        # Unblock any pending host key dialog before shutting down
        if self._host_key_event is not None and not self._host_key_event.is_set():
            self._host_key_accepted = False
            self._host_key_event.set()
        if self._server is not None:
            self._server.shutdown()
        elif self._sock is not None:
            # Still connecting/negotiating — force-close the socket to unblock
            # the blocking connect()/start_client() call in the worker thread.
            try:
                self._sock.close()
            except OSError as exc:
                _log.debug("Error force-closing in-progress connection socket: %s", exc)
        # Transport is closed inside run()'s finally block — no race condition.


# ---------------------------------------------------------------------------
# Manager — lives in the main thread; owns the worker + its QThread
# ---------------------------------------------------------------------------

class TunnelManager(QObject):
    tunnel_connected   = Signal()
    tunnel_failed      = Signal(str)
    tunnel_stopped     = Signal()
    host_key_unknown   = Signal(str, str, str)  # hostname, key_type, fingerprint
    host_key_mismatch  = Signal(str, str, str)  # hostname, key_type, fingerprint

    def __init__(self) -> None:
        super().__init__()
        self._worker: TunnelWorker | None = None
        self._thread: QThread | None      = None

    def start(self, config: TunnelConfig, auth: AuthStrategy) -> None:
        if self._thread and self._thread.isRunning():
            return

        self._worker = TunnelWorker(config, auth)
        self._thread = QThread()

        self._worker.moveToThread(self._thread)

        # wire thread lifecycle
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._cleanup)

        # re-emit worker signals to the outside world
        self._worker.connected.connect(self.tunnel_connected)
        self._worker.failed.connect(self.tunnel_failed)
        self._worker.stopped.connect(self.tunnel_stopped)
        self._worker.host_key_unknown.connect(self.host_key_unknown)
        self._worker.host_key_mismatch.connect(self.host_key_mismatch)

        # let the worker's stop/failure signals drive thread shutdown — `failed` fires
        # alone when the connection never gets past connecting (auth error, timeout,
        # cancel, rejected host key); `stopped` fires once the serving loop exits.
        # Without both, the thread never quits and start() silently no-ops forever.
        self._worker.stopped.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)

        self._thread.start()

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()

    def resolve_host_key(self, accept: bool) -> None:
        if self._worker is not None:
            self._worker.resolve_host_key(accept)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def wait_stopped(self, timeout_ms: int) -> bool:
        """Block until the worker thread finishes, forcing termination past the timeout.

        Returns True if the thread stopped cleanly within the timeout.
        """
        if self._thread is None:
            return True
        if self._thread.wait(timeout_ms):
            return True
        _log.warning("Tunnel thread did not finish in time — forcing termination")
        self._thread.terminate()
        self._thread.wait()
        return False

    def _cleanup(self) -> None:
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
