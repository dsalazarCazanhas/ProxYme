# ***Imports***
# Local
from .widgets import TabBar
# Core
import os
# Third
from PySide6 import QtGui, QtCore
from PySide6.QtWidgets import QMainWindow, QToolBar, QPushButton

icon = os.path.dirname(os.path.realpath(__file__))


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        # Init Main Window
        self.app = app
        self.setWindowTitle('ProxYTensei')
        self.resize(450, 325)
        self.setWindowIcon(QtGui.QIcon(icon + os.path.sep + 'icon2.png'))

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

        # Button Box

        toolbar.addAction(quit_action)

    def quit_app(self):
        self.app.quit()

