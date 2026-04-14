import logging

from PySide6 import QtGui, QtCore
from PySide6.QtWidgets import QMainWindow, QMessageBox

from .widgets import TabBar
from .metas import icon

_log = logging.getLogger(__name__)

_THREAD_STOP_TIMEOUT_MS = 3_000  # max wait for tunnel thread to finish on close


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("ProxYme")
        self.resize(512, 256)
        self.setWindowIcon(QtGui.QIcon(icon["window_icon"]))

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Main")
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        about_menu = menu_bar.addMenu("&Help")
        about_menu.addAction("About")

        self._tab_bar = TabBar()
        self.setCentralWidget(self._tab_bar)
        self._tab_bar.tunnel_tab.status_message.connect(self.statusBar().showMessage)

        self.statusBar().showMessage(
            f"Ready  —  {QtCore.QDateTime.currentDateTime().toString()}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        """Confirm with the user before closing if a tunnel is active."""
        manager = self._tab_bar.tunnel_tab._manager
        if manager.is_running():
            reply = QMessageBox(self)
            reply.setWindowTitle("ProxYme")
            reply.setIcon(QMessageBox.Icon.Warning)
            reply.setText("A tunnel is currently active.")
            reply.setInformativeText("Closing will disconnect it. Close anyway?")
            reply.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            reply.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if reply.exec() != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

            _log.info("User confirmed close — stopping active tunnel")
            manager.stop()
            thread = manager._thread
            if thread is not None and not thread.wait(_THREAD_STOP_TIMEOUT_MS):
                _log.warning("Tunnel thread did not finish in time — forcing termination")
                thread.terminate()
                thread.wait()

        event.accept()

    def quit_app(self):
        self.close()
