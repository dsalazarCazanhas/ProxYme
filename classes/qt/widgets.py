# ***Imports***
# Local
# Core
import os
# Third
from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabBar, QTabWidget, QFormLayout, QLineEdit,\
    QBoxLayout, QLabel, QPushButton


class TabBar(QWidget):

    def __init__(self):
        super().__init__()
        self.main_layout = QHBoxLayout()
        self.button_layout = QVBoxLayout()
        # self._bar = QTabBar()
        tab_bar = QTabWidget(self)

        home = QWidget(self)
        home_layout = QFormLayout()
        home.setLayout(home_layout)
        home_layout.addRow('Username: ', QLineEdit(self))
        home_layout.addRow('Password: ', QLineEdit(self))
        # self._bar.addTab("Home")
        # self._bar.addTab("Settings")
        settings = QWidget(self)
        settings_layout = QFormLayout()
        settings.setLayout(settings_layout)
        # settings_layout.addRow('Username: ', QLineEdit(self))
        # settings_layout.addRow('Password: ', QLineEdit(self))

        start_button = QPushButton("Start")
        tab_bar.addTab(home, "Home")
        tab_bar.addTab(settings, "Settings")
        self.main_layout.addWidget(tab_bar, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        self.main_layout.addChildLayout(self.button_layout)
        self.main_layout.addWidget(start_button)
        self.setLayout(self.main_layout)
