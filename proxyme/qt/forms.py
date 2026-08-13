"""Form widgets shared between TunnelTab and ManualTunnelDialog."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from proxyme.tunnel.models import TunnelMode

_LABEL_WIDTH = 100
_INFO_ICON_WIDTH = 18


def parse_port(text: str) -> int | None:
    """Parse a port number, returning None if it's not an integer or is out
    of the valid 1-65535 range."""
    try:
        port = int(text.strip())
    except ValueError:
        return None
    if not (1 <= port <= 65535):
        return None
    return port


def _info_icon(tooltip: str) -> QLabel:
    icon = QLabel("ⓘ")  # ⓘ
    icon.setFixedWidth(_INFO_ICON_WIDTH)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setStyleSheet("color: #6E9BD1;")
    icon.setToolTip(tooltip)
    icon.setCursor(Qt.CursorShape.WhatsThisCursor)
    return icon


def labeled_row(label_text: str, widget: QWidget, tooltip: str | None = None) -> QHBoxLayout:
    row = QHBoxLayout()
    label = QLabel(label_text)
    label.setFixedWidth(_LABEL_WIDTH)
    row.addWidget(label)
    if tooltip:
        row.addWidget(_info_icon(tooltip))
    else:
        spacer = QLabel()
        spacer.setFixedWidth(_INFO_ICON_WIDTH)
        row.addWidget(spacer)
    row.addWidget(widget, stretch=1)
    return row


class TunnelFieldsForm(QWidget):
    """Mode + local port + remote host/port fields.

    Remote host/port rows auto-hide in DYNAMIC mode. Each row is exposed as a
    QWidget so callers can additionally hide/show it (e.g. only display fields
    missing from the SSH config).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("LOCAL  (-L)", TunnelMode.LOCAL)
        self.mode_combo.addItem("DYNAMIC (-D)", TunnelMode.DYNAMIC)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.local_port_field = QLineEdit()
        self.local_port_field.setPlaceholderText("e.g. 5432")

        self.remote_host_field = QLineEdit()
        self.remote_host_field.setPlaceholderText("e.g. db.internal")

        self.remote_port_field = QLineEdit()
        self.remote_port_field.setPlaceholderText("e.g. 5432")

        self.mode_row = QWidget()
        self.mode_row.setLayout(labeled_row(
            "Mode:", self.mode_combo,
            tooltip=(
                "LOCAL (-L): forwards a fixed local port to a specific remote host:port "
                "(e.g. a database).\n"
                "DYNAMIC (-D): opens a SOCKS5 proxy that routes arbitrary traffic "
                "through the SSH server."
            ),
        ))

        self.local_port_row = QWidget()
        self.local_port_row.setLayout(labeled_row(
            "Local port:", self.local_port_field,
            tooltip="Port on YOUR machine where the tunnel listens.",
        ))

        self.remote_host_row = QWidget()
        self.remote_host_row.setLayout(labeled_row(
            "Remote host:", self.remote_host_field,
            tooltip="Destination host, as seen FROM the SSH server — not from your machine.",
        ))

        self.remote_port_row = QWidget()
        self.remote_port_row.setLayout(labeled_row(
            "Remote port:", self.remote_port_field,
            tooltip="Destination port on that remote host.",
        ))

        for row in (self.mode_row, self.local_port_row, self.remote_host_row, self.remote_port_row):
            layout.addWidget(row)

    def _on_mode_changed(self, _index: int) -> None:
        is_local = self.mode_combo.currentData() == TunnelMode.LOCAL
        self.remote_host_row.setVisible(is_local)
        self.remote_port_row.setVisible(is_local)

    def current_mode(self) -> TunnelMode:
        return self.mode_combo.currentData()

    def set_mode(self, mode: TunnelMode | None) -> None:
        if mode is None:
            return
        idx = self.mode_combo.findData(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)

    def set_values(
        self,
        mode: TunnelMode | None,
        local_port: int | None,
        remote_host: str | None,
        remote_port: int | None,
    ) -> None:
        self.set_mode(mode)
        self.local_port_field.setText(str(local_port) if local_port is not None else "")
        self.remote_host_field.setText(remote_host or "")
        self.remote_port_field.setText(str(remote_port) if remote_port is not None else "")


class AuthMethodFields(QWidget):
    """Password/private-key radio group + identity-file row (with Browse…)."""

    password_selected = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        radios_row = QHBoxLayout()
        radios_row.setContentsMargins(0, 0, 0, 0)
        auth_label = QLabel("Auth:")
        auth_label.setFixedWidth(_LABEL_WIDTH)
        self.button_group = QButtonGroup(self)
        self.radio_password = QRadioButton("Password")
        self.radio_key = QRadioButton("Private key")
        self.radio_password.setChecked(True)
        self.button_group.addButton(self.radio_password)
        self.button_group.addButton(self.radio_key)
        radios_row.addWidget(auth_label)
        radios_row.addWidget(_info_icon(
            "Applies to this session only — independent of what your ~/.ssh/config says.",
        ))
        radios_row.addWidget(self.radio_password)
        radios_row.addWidget(self.radio_key)
        radios_row.addStretch()
        radios_widget = QWidget()
        radios_widget.setLayout(radios_row)

        self.key_row = QWidget()
        key_layout = QHBoxLayout(self.key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self.key_path_field = QLineEdit()
        self.key_path_field.setPlaceholderText("path to private key")
        self.key_path_field.setToolTip(
            "Supports Ed25519, ECDSA and RSA keys. "
            "You'll be prompted for a passphrase if the key needs one.",
        )
        self.key_browse_btn = QPushButton("Browse…")
        self.key_browse_btn.clicked.connect(self._browse_key)
        key_layout.addWidget(self.key_path_field, stretch=1)
        key_layout.addWidget(self.key_browse_btn)
        self.key_row.setVisible(False)

        self.radio_key.toggled.connect(self.key_row.setVisible)
        self.radio_password.toggled.connect(self.password_selected)

        layout.addWidget(radios_widget)
        layout.addWidget(self.key_row)

    def _browse_key(self) -> None:
        start = str(Path.home() / ".ssh")
        path, _ = QFileDialog.getOpenFileName(self, "Select private key", start, "All files (*)")
        if path:
            self.key_path_field.setText(path)

    def is_password(self) -> bool:
        return self.radio_password.isChecked()

    def key_path(self) -> str | None:
        return self.key_path_field.text().strip() or None

    def set_private_key(self, key_path: str | None) -> None:
        self.radio_key.setChecked(True)
        self.key_path_field.setText(key_path or "")
