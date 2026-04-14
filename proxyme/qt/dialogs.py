import getpass
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDialogButtonBox, QComboBox, QRadioButton, QPushButton,
    QFileDialog, QWidget, QButtonGroup,
)

from proxyme.tunnel.models import AuthMethod, TunnelConfig, TunnelMode


class PassphraseDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Passphrase required")
        self.setModal(True)
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)

        label = QLabel("Enter passphrase for the private key:")
        layout.addWidget(label)

        self._field = QLineEdit()
        self._field.setEchoMode(QLineEdit.EchoMode.NoEcho)
        self._field.setPlaceholderText("passphrase")
        self._field.returnPressed.connect(self.accept)
        layout.addWidget(self._field)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def passphrase(self) -> str:
        return self._field.text()


class ManualTunnelDialog(QDialog):
    """Dialog for creating or editing a manual tunnel entry (no SSH config required)."""

    def __init__(self, parent=None, existing: Optional[TunnelConfig] = None) -> None:
        super().__init__(parent)
        editing = existing is not None
        self.setWindowTitle("Edit Manual Tunnel" if editing else "Add Manual Tunnel")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        def _row(label: str, widget: QWidget) -> QHBoxLayout:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(100)
            row.addWidget(lbl)
            row.addWidget(widget, stretch=1)
            return row

        # Name
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. my-server")
        root.addLayout(_row("Name:", self._name))

        # SSH Host
        self._host = QLineEdit()
        self._host.setPlaceholderText("hostname or IP")
        root.addLayout(_row("SSH Host:", self._host))

        # SSH Port
        self._port = QLineEdit("22")
        root.addLayout(_row("SSH Port:", self._port))

        # SSH User
        self._user = QLineEdit(getpass.getuser())
        root.addLayout(_row("SSH User:", self._user))

        # --- Auth method ---
        auth_group_widget = QWidget()
        auth_layout = QHBoxLayout(auth_group_widget)
        auth_layout.setContentsMargins(0, 0, 0, 0)
        self._auth_group = QButtonGroup(self)
        self._radio_password = QRadioButton("Password")
        self._radio_key      = QRadioButton("Private key")
        self._radio_password.setChecked(True)
        self._auth_group.addButton(self._radio_password)
        self._auth_group.addButton(self._radio_key)
        auth_layout.addWidget(self._radio_password)
        auth_layout.addWidget(self._radio_key)
        auth_layout.addStretch()
        root.addLayout(_row("Auth:", auth_group_widget))

        # Identity file row (visible only when Private key selected)
        self._key_row = QWidget()
        key_layout = QHBoxLayout(self._key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self._key_path = QLineEdit()
        self._key_path.setPlaceholderText("path to private key")
        self._key_browse = QPushButton("Browse…")
        self._key_browse.clicked.connect(self._browse_key)
        key_layout.addWidget(self._key_path, stretch=1)
        key_layout.addWidget(self._key_browse)
        self._key_row.setVisible(False)
        root.addLayout(_row("Identity file:", self._key_row))

        self._radio_key.toggled.connect(self._key_row.setVisible)

        # --- Mode ---
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("LOCAL  (-L)",  TunnelMode.LOCAL)
        self._mode_combo.addItem("DYNAMIC (-D)", TunnelMode.DYNAMIC)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        root.addLayout(_row("Mode:", self._mode_combo))

        # Local port
        self._local_port = QLineEdit()
        self._local_port.setPlaceholderText("e.g. 5432")
        root.addLayout(_row("Local port:", self._local_port))

        # Remote host
        self._remote_host_row = QWidget()
        rh_layout = QHBoxLayout(self._remote_host_row)
        rh_layout.setContentsMargins(0, 0, 0, 0)
        self._remote_host = QLineEdit()
        self._remote_host.setPlaceholderText("e.g. db.internal")
        rh_layout.addWidget(self._remote_host)
        root.addLayout(_row("Remote host:", self._remote_host_row))

        # Remote port
        self._remote_port_row = QWidget()
        rp_layout = QHBoxLayout(self._remote_port_row)
        rp_layout.setContentsMargins(0, 0, 0, 0)
        self._remote_port = QLineEdit()
        self._remote_port.setPlaceholderText("e.g. 5432")
        rp_layout.addWidget(self._remote_port)
        root.addLayout(_row("Remote port:", self._remote_port_row))

        # Buttons
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        root.addWidget(self._buttons)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #C0392B;")
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Pre-fill if editing an existing config
        if existing is not None:
            self._name.setText(existing.name)
            self._name.setEnabled(False)  # name is the key — don't allow rename
            self._host.setText(existing.ssh_host)
            self._port.setText(str(existing.ssh_port))
            self._user.setText(existing.ssh_user)
            if existing.auth_method == AuthMethod.PRIVATE_KEY:
                self._radio_key.setChecked(True)
                self._key_path.setText(existing.key_path or "")
                self._key_row.setVisible(True)
            idx = self._mode_combo.findData(existing.mode)
            if idx >= 0:
                self._mode_combo.setCurrentIndex(idx)
            self._local_port.setText(str(existing.local_port))
            self._remote_host.setText(existing.remote_host or "")
            self._remote_port.setText(str(existing.remote_port) if existing.remote_port else "")
            is_local = existing.mode == TunnelMode.LOCAL
            self._remote_host_row.setVisible(is_local)
            self._remote_port_row.setVisible(is_local)

    # ------------------------------------------------------------------

    def _on_mode_changed(self, _index: int) -> None:
        is_local = self._mode_combo.currentData() == TunnelMode.LOCAL
        self._remote_host_row.setVisible(is_local)
        self._remote_port_row.setVisible(is_local)

    def _browse_key(self) -> None:
        start = str(Path.home() / ".ssh")
        path, _ = QFileDialog.getOpenFileName(
            self, "Select private key", start, "All files (*)"
        )
        if path:
            self._key_path.setText(path)

    def _on_accept(self) -> None:
        name     = self._name.text().strip()
        ssh_host = self._host.text().strip()
        ssh_user = self._user.text().strip() or getpass.getuser()

        try:
            ssh_port = int(self._port.text())
        except ValueError:
            self._show_error("SSH Port must be a number.")
            return

        try:
            local_port = int(self._local_port.text())
        except ValueError:
            self._show_error("Local port must be a number.")
            return

        if not name:
            self._show_error("Name is required.")
            return
        if not ssh_host:
            self._show_error("SSH Host is required.")
            return

        mode = self._mode_combo.currentData()
        remote_host: Optional[str] = None
        remote_port: Optional[int] = None

        if mode == TunnelMode.LOCAL:
            remote_host = self._remote_host.text().strip() or None
            if not remote_host:
                self._show_error("Remote host is required for LOCAL mode.")
                return
            try:
                remote_port = int(self._remote_port.text())
            except ValueError:
                self._show_error("Remote port must be a number.")
                return

        auth_method = AuthMethod.PRIVATE_KEY if self._radio_key.isChecked() else AuthMethod.PASSWORD
        key_path: Optional[str] = None
        if auth_method == AuthMethod.PRIVATE_KEY:
            key_path = self._key_path.text().strip() or None
            if not key_path:
                self._show_error("Identity file is required for private key auth.")
                return

        self._config = TunnelConfig(
            name        = name,
            ssh_host    = ssh_host,
            ssh_port    = ssh_port,
            ssh_user    = ssh_user,
            auth_method = auth_method,
            mode        = mode,
            local_port  = local_port,
            remote_host = remote_host,
            remote_port = remote_port,
            key_path    = key_path,
        )
        self.accept()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def tunnel_config(self) -> TunnelConfig:
        """Call only after Dialog.Accepted."""
        return self._config
