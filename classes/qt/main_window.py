# ***Imports***
# Local
from .widgets import TabBar
from .meta import icon
# Core

# Third
from PySide6 import QtGui, QtCore
from PySide6.QtWidgets import QMainWindow, QToolBar, QStatusBar


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()

        # Init Main Window
        self.app = app
        self.setWindowTitle('ProxYTensei')
        self.resize(512, 256)
        self.setWindowIcon(QtGui.QIcon(icon['window_icon']))

        # Menubar and Menus
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Main")
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)
        # lang_menu = menu_bar.addMenu("&Lang")
        # lang_menu.addAction("English")
        # lang_menu.addAction("Spanish")
        about_menu = menu_bar.addMenu("&Help")
        about_menu.addAction("About")

        # Widgets
        tab_bar = TabBar()
        self.setCentralWidget(tab_bar)

        # toolbar ***This will be removed later!!!! cuz not needed at the moment***
        toolbar = QToolBar("My main toolbar")
        toolbar.setIconSize(QtCore.QSize(16, 16))
        self.addToolBar(toolbar)

        # Trying status bar
        self.date_time = QtCore.QDateTime()
        statusbar = QStatusBar()
        statusbar.showMessage(self.status_bar())

        # Button Box
        toolbar.addAction(quit_action)

    def quit_app(self):
        self.app.quit()

    def status_bar(self):
        self.statusBar().showMessage(f"The Process is READY at {self.date_time.currentDateTime().toString()}")
