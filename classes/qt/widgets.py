# ***Imports***
# Local
# Core
import os
# Third
from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabBar


class TabBar(QWidget):

    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout()
        self._bar = QTabBar()
        home = self._bar.addTab("Home")
        settings = self._bar.addTab("Settings")
        self.main_layout.addWidget(self._bar, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.main_layout)

    def tab_change(self):
        print("the tab changes")
