# ***Imports***
# Local
from .widgets import TabBar
from .metas import icon
# Core

# Third
from PySide6 import QtGui, QtCore
from PySide6.QtWidgets import QMainWindow, QStatusBar


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        # Init Main Window
        self.app = app
        self.setWindowTitle('ProxYme')
        self.resize(512, 256)
        self.setWindowIcon(QtGui.QIcon(icon['window_icon']))

        # Menubar and Menus
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Main")
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)
        about_menu = menu_bar.addMenu("&Help")
        about_menu.addAction("About")

        # Widgets
        tab_bar = TabBar()
        self.setCentralWidget(tab_bar)

        # Trying status bar
        self.date_time = QtCore.QDateTime()
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)
        self.status_bar()


    def quit_app(self):
        self.app.quit()

    def status_bar(self):
        self.statusBar().showMessage(f"The Process is READY at {self.date_time.currentDateTime().toString()}")
