import logging
from pathlib import Path
from typing import ClassVar

import paramiko
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from proxyme.qt.dialogs import ManualTunnelDialog, PassphraseDialog
from proxyme.qt.forms import AuthMethodFields, TunnelFieldsForm, parse_port
from proxyme.qt.system_open import open_path
from proxyme.storage import repository, ssh_config
from proxyme.storage.repository import TunnelSupplement
from proxyme.storage.ssh_config import (
    get_key_path,
    peek_auth_method,
    peek_tunnel_gaps,
    resolve_tunnel,
    resolve_tunnel_partial,
)
from proxyme.tunnel.auth.base import AuthStrategy
from proxyme.tunnel.auth.password import PasswordAuth
from proxyme.tunnel.auth.private_key import PrivateKeyAuth, load_private_key
from proxyme.tunnel.manager import TunnelManager
from proxyme.tunnel.models import AuthMethod, TunnelConfig, TunnelMode

from .metas import icon

_log = logging.getLogger(__name__)


class _StatusIndicator(QLabel):
    _COLORS: ClassVar[dict[str, str]] = {
        "ready":      "#888888",
        "connecting": "#E6A817",
        "connected":  "#27AE60",
        "failed":     "#C0392B",
        "stopped":    "#888888",
    }

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(14, 14)
        self.set_state("ready")

    def set_state(self, state: str) -> None:
        color = self._COLORS.get(state, "#888888")
        self.setStyleSheet(f"background-color: {color}; border-radius: 7px;")


class TunnelTab(QWidget):
    status_message = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self._manager = TunnelManager()
        self._manager.tunnel_connected.connect(self._on_connected)
        self._manager.tunnel_failed.connect(self._on_failed)
        self._manager.tunnel_stopped.connect(self._on_stopped)
        self._manager.host_key_unknown.connect(self._on_host_key_unknown)
        self._manager.host_key_mismatch.connect(self._on_host_key_mismatch)

        # Manual tunnel configs live in memory only — never persisted
        self._manual_configs: dict[str, TunnelConfig] = {}

        root = QVBoxLayout(self)
        root.setSpacing(10)

        # --- Host row ---
        host_row = QHBoxLayout()
        host_label = QLabel("Host:")
        self.host_combo = QComboBox()
        self.host_combo.currentTextChanged.connect(self._on_host_changed)
        edit_config_btn = QPushButton("Edit SSH config")
        edit_config_btn.setFlat(True)
        edit_config_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        edit_config_btn.clicked.connect(self._open_ssh_config)
        add_manual_btn = QPushButton("+ Manual")
        add_manual_btn.setFlat(True)
        add_manual_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        add_manual_btn.setToolTip(
            "Manual entries live in memory only — they're not saved when you close the app."
        )
        add_manual_btn.clicked.connect(self._on_add_manual)
        host_row.addWidget(host_label)
        host_row.addWidget(self.host_combo, stretch=1)
        host_row.addWidget(edit_config_btn)
        host_row.addWidget(add_manual_btn)
        root.addLayout(host_row)

        # --- Auth area ---
        auth_section = QVBoxLayout()
        auth_section.setSpacing(4)

        self._auth = AuthMethodFields()
        auth_section.addWidget(self._auth)

        # Password field (shown when Password selected)
        self._password_row = QWidget()
        pw_layout = QHBoxLayout(self._password_row)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        self._password_field = QLineEdit()
        self._password_field.setPlaceholderText("password")
        self._password_field.setEchoMode(QLineEdit.EchoMode.Password)
        _eye_closed = QtGui.QIcon(icon['icon_eye_closed'])
        self._show_pass_action = QtGui.QAction(_eye_closed, "Show", self)
        self._show_pass_action.setCheckable(True)
        self._show_pass_action.toggled.connect(self._toggle_password_visibility)
        self._password_field.addAction(
            self._show_pass_action, QLineEdit.ActionPosition.TrailingPosition
        )
        pw_layout.addWidget(self._password_field)
        auth_section.addWidget(self._password_row)

        self._auth.password_selected.connect(self._on_auth_radio_changed)
        root.addLayout(auth_section)

        # --- Tunnel fields (shown only when missing from SSH config + JSON) ---
        self._fields = TunnelFieldsForm()
        self._fields.setVisible(False)
        root.addWidget(self._fields)

        self._fields_error_label = QLabel()
        self._fields_error_label.setStyleSheet("color: #C0392B;")
        self._fields_error_label.setVisible(False)
        root.addWidget(self._fields_error_label)

        # --- Read-only config display (shown when all tunnel fields are resolved) ---
        self._config_display_widget = QWidget()
        _grey = "color: #888888;"
        cd_layout = QVBoxLayout(self._config_display_widget)
        cd_layout.setContentsMargins(0, 0, 0, 0)
        cd_layout.setSpacing(2)

        self._cd_mode_label  = QLabel()
        self._cd_local_label = QLabel()
        self._cd_rhost_label = QLabel()
        self._cd_rport_label = QLabel()
        self._cd_bind_label  = QLabel()
        for _lbl in (self._cd_mode_label, self._cd_local_label,
                     self._cd_rhost_label, self._cd_rport_label, self._cd_bind_label):
            _lbl.setStyleSheet(_grey)
            cd_layout.addWidget(_lbl)

        _edit_row = QHBoxLayout()
        _edit_row.addStretch()
        self._edit_config_btn = QPushButton("Edit")
        self._edit_config_btn.clicked.connect(self._on_edit_clicked)
        _edit_row.addWidget(self._edit_config_btn)
        cd_layout.addLayout(_edit_row)

        self._config_display_widget.setVisible(False)
        root.addWidget(self._config_display_widget)

        # --- Edit-override actions (Save / Cancel) ---
        self._edit_actions_widget = QWidget()
        ea_layout = QHBoxLayout(self._edit_actions_widget)
        ea_layout.setContentsMargins(0, 0, 0, 0)
        self._save_edit_btn   = QPushButton("Save")
        self._cancel_edit_btn = QPushButton("Cancel")
        self._save_edit_btn.clicked.connect(self._on_save_edit)
        self._cancel_edit_btn.clicked.connect(self._on_cancel_edit)
        ea_layout.addStretch()
        ea_layout.addWidget(self._cancel_edit_btn)
        ea_layout.addWidget(self._save_edit_btn)
        self._edit_actions_widget.setVisible(False)
        root.addWidget(self._edit_actions_widget)

        self._in_edit_override: bool = False

        # --- Status row ---
        status_row = QHBoxLayout()
        self._indicator = _StatusIndicator()
        self._status_text = QLabel("Ready")
        status_row.addWidget(self._indicator)
        status_row.addWidget(self._status_text)
        status_row.addStretch()
        root.addLayout(status_row)

        # --- Button row ---
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setVisible(False)
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        root.addLayout(btn_row)

        root.addStretch()
        self._reload_hosts()

    @property
    def manager(self) -> TunnelManager:
        return self._manager

    # ------------------------------------------------------------------
    # Host management
    # ------------------------------------------------------------------

    def _reload_hosts(self) -> None:
        self.host_combo.blockSignals(True)
        self.host_combo.clear()

        ssh_hosts = ssh_config.load_hosts()
        manual_names = list(self._manual_configs.keys())
        all_hosts = ssh_hosts + [n for n in manual_names if n not in ssh_hosts]

        if all_hosts:
            self.host_combo.addItems(all_hosts)
            self.host_combo.blockSignals(False)
            self._on_host_changed(self.host_combo.currentText())
            self.start_btn.setEnabled(True)
        else:
            self.host_combo.addItem("(no hosts configured)")
            self.host_combo.blockSignals(False)
            self.start_btn.setEnabled(False)

    def _on_host_changed(self, alias: str) -> None:
        if not alias or alias.startswith("("):
            return
        _log.info("Host selected: %s", alias)

        self._in_edit_override = False
        self._edit_actions_widget.setVisible(False)
        self._clear_fields_error()

        # --- Manual host (in-memory, fully resolved) ---
        if alias in self._manual_configs:
            config = self._manual_configs[alias]
            if config.auth_method == AuthMethod.PRIVATE_KEY:
                self._auth.set_private_key(config.key_path)
                self._password_row.setVisible(False)
                self._auth.key_row.setVisible(True)
            else:
                self._auth.radio_password.setChecked(True)
                self._password_row.setVisible(True)
                self._auth.key_row.setVisible(False)
            self._fields.setVisible(False)
            self._update_config_display({
                "mode":        config.mode,
                "local_port":  config.local_port,
                "remote_host": config.remote_host,
                "remote_port": config.remote_port,
                "bind_all_interfaces": config.bind_all_interfaces,
            })
            self._config_display_widget.setVisible(True)
            return

        # --- SSH config host ---
        method = peek_auth_method(alias)
        if method == AuthMethod.PRIVATE_KEY:
            self._auth.set_private_key(get_key_path(alias))
            self._password_row.setVisible(False)
            self._auth.key_row.setVisible(True)
        else:
            self._auth.radio_password.setChecked(True)
            self._password_row.setVisible(True)
            self._auth.key_row.setVisible(False)

        gaps = peek_tunnel_gaps(alias)
        if gaps:
            self._config_display_widget.setVisible(False)
            self._fields.mode_row.setVisible("mode" in gaps)
            self._fields.local_port_row.setVisible("local_port" in gaps)
            self._fields.remote_host_row.setVisible("remote_host" in gaps)
            self._fields.remote_port_row.setVisible("remote_port" in gaps)
            self._fields.bind_all_row.setVisible(True)
            self._fields.setVisible(True)

            supplement = repository.find_by_name(alias)
            self._fields.bind_all_checkbox.setChecked(
                supplement.bind_all_interfaces if supplement else False,
            )
            if supplement:
                if "local_port" in gaps and supplement.local_port:
                    self._fields.local_port_field.setText(str(supplement.local_port))
                if "remote_host" in gaps and supplement.remote_host:
                    self._fields.remote_host_field.setText(supplement.remote_host)
                if "remote_port" in gaps and supplement.remote_port:
                    self._fields.remote_port_field.setText(str(supplement.remote_port))
        else:
            self._fields.setVisible(False)
            partial = resolve_tunnel_partial(alias)
            self._update_config_display(partial)
            self._config_display_widget.setVisible(True)

    def _update_config_display(self, partial: dict) -> None:
        mode = partial.get("mode")
        mode_str = mode.value.upper() if mode else "—"
        self._cd_mode_label.setText(f"Mode:        {mode_str}")
        self._cd_local_label.setText(f"Local port:  {partial.get('local_port') or '—'}")
        is_local = (mode == TunnelMode.LOCAL) if mode else True
        self._cd_rhost_label.setVisible(is_local)
        self._cd_rport_label.setVisible(is_local)
        self._cd_rhost_label.setText(f"Remote host: {partial.get('remote_host') or '—'}")
        self._cd_rport_label.setText(f"Remote port: {partial.get('remote_port') or '—'}")
        if partial.get("bind_all_interfaces"):
            self._cd_bind_label.setText("Bind:        0.0.0.0 (reachable from other devices)")
            self._cd_bind_label.setStyleSheet("color: #E6A817;")
        else:
            self._cd_bind_label.setText("Bind:        127.0.0.1 (this machine only)")
            self._cd_bind_label.setStyleSheet("color: #888888;")

    def _show_fields_error(self, message: str) -> None:
        self._fields_error_label.setText(message)
        self._fields_error_label.setVisible(True)

    def _clear_fields_error(self) -> None:
        self._fields_error_label.setVisible(False)

    def _on_edit_clicked(self) -> None:
        alias = self.host_combo.currentText()

        # Manual host — reopen dialog pre-filled
        if alias in self._manual_configs:
            taken_names = self._taken_manual_names() - {alias}
            dialog = ManualTunnelDialog(
                self, existing=self._manual_configs[alias], taken_names=taken_names,
            )
            if dialog.exec() == ManualTunnelDialog.DialogCode.Accepted:
                config = dialog.tunnel_config()
                self._manual_configs[config.name] = config
                self._on_host_changed(alias)
            return

        partial = resolve_tunnel_partial(alias)

        self._in_edit_override = True
        self._config_display_widget.setVisible(False)

        # Show all tunnel fields pre-filled with current values
        mode = partial.get("mode")
        self._fields.set_values(
            mode, partial.get("local_port"), partial.get("remote_host"), partial.get("remote_port"),
            partial.get("bind_all_interfaces", False),
        )

        self._fields.mode_row.setVisible(True)
        self._fields.local_port_row.setVisible(True)
        is_local = (mode == TunnelMode.LOCAL) if mode else True
        self._fields.remote_host_row.setVisible(is_local)
        self._fields.remote_port_row.setVisible(is_local)
        self._fields.bind_all_row.setVisible(True)
        self._fields.setVisible(True)
        self._edit_actions_widget.setVisible(True)

    def _on_save_edit(self) -> None:
        alias = self.host_combo.currentText()
        if not self._save_all_tunnel_fields(alias):
            return
        self._in_edit_override = False
        self._edit_actions_widget.setVisible(False)
        self._on_host_changed(alias)  # refresh to read-only display

    def _on_cancel_edit(self) -> None:
        self._in_edit_override = False
        self._edit_actions_widget.setVisible(False)
        self._on_host_changed(self.host_combo.currentText())  # restore read-only display

    def _save_all_tunnel_fields(self, alias: str) -> bool:
        """Persist tunnel topology to the JSON supplement (edit-override path).

        Returns True on success. Shows an inline error and returns False if
        any field is missing or malformed — never silently drops a typo.
        """
        mode = self._fields.current_mode()

        local_port = parse_port(self._fields.local_port_field.text())
        if local_port is None:
            self._show_fields_error("Local port must be a number between 1 and 65535.")
            return False

        remote_host: str | None = None
        remote_port: int | None = None
        if mode == TunnelMode.LOCAL:
            remote_host = self._fields.remote_host_field.text().strip() or None
            if not remote_host:
                self._show_fields_error("Remote host is required for LOCAL mode.")
                return False
            remote_port = parse_port(self._fields.remote_port_field.text())
            if remote_port is None:
                self._show_fields_error("Remote port must be a number between 1 and 65535.")
                return False

        repository.upsert(TunnelSupplement(
            name        = alias,
            mode        = mode,
            local_port  = local_port,
            remote_host = remote_host,
            remote_port = remote_port,
            bind_all_interfaces = self._fields.bind_all_interfaces(),
        ))
        _log.info("Tunnel supplement saved for host: %s", alias)
        self._clear_fields_error()
        return True

    # ------------------------------------------------------------------
    # SSH config editor
    # ------------------------------------------------------------------

    def _open_ssh_config(self) -> None:
        path = Path.home() / ".ssh" / "config"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        # ~/.ssh/config has no extension, so OS-level "open with default app"
        # resolution is often ambiguous and falls back to an app picker —
        # open_path() tries $VISUAL/$EDITOR first to sidestep that.
        open_path(path)

    def _on_add_manual(self) -> None:
        dialog = ManualTunnelDialog(self, taken_names=self._taken_manual_names())
        if dialog.exec() != ManualTunnelDialog.DialogCode.Accepted:
            return
        config = dialog.tunnel_config()
        self._manual_configs[config.name] = config
        self._reload_hosts()
        idx = self.host_combo.findText(config.name)
        if idx >= 0:
            self.host_combo.setCurrentIndex(idx)

    def _taken_manual_names(self) -> set[str]:
        """Names a new/renamed manual entry must not collide with — SSH-config
        hosts silently disappear from the host list if a manual entry shadows
        their name, so this is enforced at add/edit time instead."""
        return set(ssh_config.load_hosts()) | set(self._manual_configs.keys())

    # ------------------------------------------------------------------
    # Auth building
    # ------------------------------------------------------------------

    def _on_auth_radio_changed(self, password_checked: bool) -> None:
        self._password_row.setVisible(password_checked)

    def _build_auth(self, config: TunnelConfig) -> AuthStrategy | None:
        if self._auth.is_password():
            return PasswordAuth(config.ssh_user, self._password_field.text())

        # Private key — probe whether passphrase is needed (main thread, safe for dialog)
        key_path = self._auth.key_path()
        passphrase: str | None = None
        try:
            load_private_key(key_path)
        except paramiko.PasswordRequiredException:
            dialog = PassphraseDialog(self)
            if dialog.exec() != PassphraseDialog.DialogCode.Accepted:
                return None
            passphrase = dialog.passphrase() or None
        except Exception as exc:
            # Other errors (file not found, wrong format) will surface in the worker
            _log.debug("Private key probe failed (will surface in worker): %s", exc)

        return PrivateKeyAuth(config.ssh_user, key_path, passphrase=passphrase)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        alias = self.host_combo.currentText()

        # Manual host — config fully resolved in memory
        if alias in self._manual_configs:
            config = self._manual_configs[alias]
        else:
            if not self._save_tunnel_fields(alias):
                return
            try:
                config = resolve_tunnel(alias)
            except ValueError as exc:
                self._set_idle("failed", f"Config error: {exc}")
                return

        auth = self._build_auth(config)
        if auth is None:
            return

        self._set_connecting()
        _log.info("Start requested for host: %s", alias)
        self._manager.start(config, auth)

    def _save_tunnel_fields(self, alias: str) -> bool:
        """Persist any manually filled tunnel fields to the JSON supplement.

        Returns True if there was nothing to save, or saving succeeded. Shows
        an inline error and returns False if a filled-in gap field is invalid.
        """
        gaps = peek_tunnel_gaps(alias)
        if not gaps:
            return True

        supplement = repository.find_by_name(alias)

        mode = (
            self._fields.current_mode() if "mode" in gaps
            else (supplement.mode if supplement else TunnelMode.LOCAL)
        )

        if "local_port" in gaps:
            local_port = parse_port(self._fields.local_port_field.text())
            if local_port is None:
                self._show_fields_error("Local port must be a number between 1 and 65535.")
                return False
        else:
            local_port = supplement.local_port if supplement else None

        if "remote_host" in gaps:
            if mode == TunnelMode.LOCAL:
                remote_host = self._fields.remote_host_field.text().strip() or None
                if not remote_host:
                    self._show_fields_error("Remote host is required for LOCAL mode.")
                    return False
            else:
                remote_host = None
        else:
            remote_host = supplement.remote_host if supplement else None

        if "remote_port" in gaps:
            if mode == TunnelMode.LOCAL:
                remote_port = parse_port(self._fields.remote_port_field.text())
                if remote_port is None:
                    self._show_fields_error("Remote port must be a number between 1 and 65535.")
                    return False
            else:
                remote_port = None
        else:
            remote_port = supplement.remote_port if supplement else None

        if local_port is None:
            self._show_fields_error("Local port is required.")
            return False

        repository.upsert(TunnelSupplement(
            name        = alias,
            mode        = mode,
            local_port  = local_port,
            remote_host = remote_host,
            remote_port = remote_port,
            bind_all_interfaces = self._fields.bind_all_interfaces(),
        ))
        self._clear_fields_error()
        return True

    def _on_stop(self) -> None:
        self._manager.stop()

    # ------------------------------------------------------------------
    # TunnelManager signal handlers
    # ------------------------------------------------------------------

    def _on_connected(self) -> None:
        self._set_connected()

    def _on_failed(self, error: str) -> None:
        self._set_idle("failed", f"Failed: {error}")

    def _on_stopped(self) -> None:
        self._password_field.clear()
        self._set_idle("stopped", "Stopped")

    # ------------------------------------------------------------------
    # UI state machine
    # ------------------------------------------------------------------

    def _set_connecting(self) -> None:
        self._lock_form(True)
        self.start_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.stop_btn.setEnabled(True)
        self._update_status("connecting", "Connecting…")

    def _set_connected(self) -> None:
        self.stop_btn.setEnabled(True)
        self._update_status("connected", "Connected")

    def _set_idle(self, state: str, message: str) -> None:
        self._lock_form(False)
        self.start_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self._update_status(state, message)

    def _lock_form(self, locked: bool) -> None:
        self.host_combo.setEnabled(not locked)
        self._password_field.setEnabled(not locked)
        self._fields.setEnabled(not locked)
        self._config_display_widget.setEnabled(not locked)
        self._edit_actions_widget.setEnabled(not locked)

    def _update_status(self, state: str, message: str) -> None:
        self._indicator.set_state(state)
        self._status_text.setText(message)
        self.status_message.emit(message)

    # ------------------------------------------------------------------
    # Host key verification (TOFU)
    # ------------------------------------------------------------------

    def _on_host_key_unknown(self, hostname: str, key_type: str, fingerprint: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("Unknown Host")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(f"The authenticity of host <b>{hostname}</b> cannot be established.")
        msg.setInformativeText(
            f"Key type: {key_type}<br>"
            f"Fingerprint: <code>{fingerprint}</code><br><br>"
            "Do you want to trust this host and connect?"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        accepted = msg.exec() == QMessageBox.StandardButton.Yes
        self._manager.resolve_host_key(accepted)

    def _on_host_key_mismatch(self, hostname: str, key_type: str, fingerprint: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("Host Key Changed")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(f"WARNING: Remote host identification has changed for <b>{hostname}</b>!")
        msg.setInformativeText(
            "This may indicate a man-in-the-middle attack.<br><br>"
            f"Key type: {key_type}<br>"
            f"New fingerprint: <code>{fingerprint}</code><br><br>"
            "Connection has been aborted."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    # ------------------------------------------------------------------

    def _toggle_password_visibility(self, show: bool) -> None:
        if show:
            self._show_pass_action.setIcon(QtGui.QIcon(icon['icon_eye_opened']))
            self._password_field.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._show_pass_action.setIcon(QtGui.QIcon(icon['icon_eye_closed']))
            self._password_field.setEchoMode(QLineEdit.EchoMode.Password)


class TabBar(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QHBoxLayout(self)
        tab_bar = QTabWidget(self)

        self.tunnel_tab = TunnelTab()
        tab_bar.addTab(self.tunnel_tab, "Tunnels")

        layout.addWidget(tab_bar, 0, QtCore.Qt.AlignmentFlag.AlignTop)
