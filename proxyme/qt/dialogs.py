import getpass

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from proxyme.qt.forms import AuthMethodFields, TunnelFieldsForm, labeled_row, parse_port
from proxyme.storage.ssh_config import format_host_block
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

    def __init__(
        self,
        parent=None,
        existing: TunnelConfig | None = None,
        taken_names: set[str] | None = None,
    ) -> None:
        super().__init__(parent)
        editing = existing is not None
        self.setWindowTitle("Edit Manual Tunnel" if editing else "Add Manual Tunnel")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._taken_names = taken_names or set()

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Name
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. my-server")
        root.addLayout(labeled_row("Name:", self._name))

        # SSH Host
        self._host = QLineEdit()
        self._host.setPlaceholderText("hostname or IP")
        root.addLayout(labeled_row("SSH Host:", self._host))

        # SSH Port
        self._port = QLineEdit("22")
        root.addLayout(labeled_row("SSH Port:", self._port))

        # SSH User
        self._user = QLineEdit(getpass.getuser())
        root.addLayout(labeled_row("SSH User:", self._user))

        # --- Auth method ---
        self._auth = AuthMethodFields()
        root.addWidget(self._auth)

        # --- Tunnel topology ---
        self._fields = TunnelFieldsForm()
        root.addWidget(self._fields)

        # Buttons
        buttons_row = QHBoxLayout()
        self._show_config_btn = QPushButton("Show SSH config…")
        self._show_config_btn.setToolTip(
            "ProxYme never writes to ~/.ssh/config — preview the equivalent "
            "Host block here and paste it in yourself if you want to keep it."
        )
        self._show_config_btn.clicked.connect(self._on_show_config)
        buttons_row.addWidget(self._show_config_btn)
        buttons_row.addStretch()

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        buttons_row.addWidget(self._buttons)
        root.addLayout(buttons_row)

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
                self._auth.set_private_key(existing.key_path)
            self._fields.set_values(
                existing.mode, existing.local_port, existing.remote_host, existing.remote_port,
            )

    # ------------------------------------------------------------------

    def _try_build_config(self) -> TunnelConfig | None:
        """Validate the current field values and build a TunnelConfig from them.

        Shows an inline error and returns None if anything required is missing
        or malformed. Used by both the OK button and the "Show SSH config" preview.
        """
        name     = self._name.text().strip()
        ssh_host = self._host.text().strip()
        ssh_user = self._user.text().strip() or getpass.getuser()

        if not name:
            self._show_error("Name is required.")
            return None
        if name in self._taken_names:
            self._show_error(f"'{name}' already exists — choose a different name.")
            return None
        if not ssh_host:
            self._show_error("SSH Host is required.")
            return None

        ssh_port = parse_port(self._port.text())
        if ssh_port is None:
            self._show_error("SSH Port must be a number between 1 and 65535.")
            return None

        local_port = parse_port(self._fields.local_port_field.text())
        if local_port is None:
            self._show_error("Local port must be a number between 1 and 65535.")
            return None

        mode = self._fields.current_mode()
        remote_host: str | None = None
        remote_port: int | None = None

        if mode == TunnelMode.LOCAL:
            remote_host = self._fields.remote_host_field.text().strip() or None
            if not remote_host:
                self._show_error("Remote host is required for LOCAL mode.")
                return None
            remote_port = parse_port(self._fields.remote_port_field.text())
            if remote_port is None:
                self._show_error("Remote port must be a number between 1 and 65535.")
                return None

        auth_method = AuthMethod.PASSWORD if self._auth.is_password() else AuthMethod.PRIVATE_KEY
        key_path: str | None = None
        if auth_method == AuthMethod.PRIVATE_KEY:
            key_path = self._auth.key_path()
            if not key_path:
                self._show_error("Identity file is required for private key auth.")
                return None

        return TunnelConfig(
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

    def _on_accept(self) -> None:
        config = self._try_build_config()
        if config is None:
            return
        self._config = config
        self.accept()

    def _on_show_config(self) -> None:
        config = self._try_build_config()
        if config is None:
            return
        SshConfigPreviewDialog(self, format_host_block(config)).exec()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def tunnel_config(self) -> TunnelConfig:
        """Call only after Dialog.Accepted."""
        return self._config


class SshConfigPreviewDialog(QDialog):
    """Read-only preview of a ~/.ssh/config Host block, with a copy-to-clipboard button.

    ProxYme never writes to ~/.ssh/config — this just renders the text so the
    user can paste it in themselves if they want the entry to persist.
    """

    def __init__(self, parent, snippet: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("SSH config preview")
        self.setModal(True)
        self.setMinimumSize(420, 220)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Paste this into your ~/.ssh/config:"))

        self._text = QPlainTextEdit(snippet)
        self._text.setReadOnly(True)
        self._text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        layout.addWidget(self._text)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to clipboard")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._text.toPlainText())
