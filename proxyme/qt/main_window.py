from .widgets import TabBar
from .metas import icon

from PySide6 import QtGui, QtCore
from PySide6.QtWidgets import QMainWindow, QToolBar, QStatusBar


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle('ProxYTensei')
        self.resize(512, 256)
        self.setWindowIcon(QtGui.QIcon(icon['window_icon']))

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Main")
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)
        about_menu = menu_bar.addMenu("&Help")
        about_menu.addAction("About")

        tab_bar = TabBar()
        self.setCentralWidget(tab_bar)

        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QtCore.QSize(16, 16))
        self.addToolBar(toolbar)

        self.date_time = QtCore.QDateTime()
        statusbar = QStatusBar()
        statusbar.showMessage(self.status_bar())

        toolbar.addAction(quit_action)

    def quit_app(self):
        self.app.quit()

    def status_bar(self):
        self.statusBar().showMessage(f"The Process is READY at {self.date_time.currentDateTime().toString()}")
