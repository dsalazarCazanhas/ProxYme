# ***Imports***
# Local
# Core
import os
# Third
from PySide6 import QtGui, QtCore
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabBar, QGroupBox, QPushButton, QLabel,\
    QDialogButtonBox


class Widgets(QWidget):
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.settings_layout = QVBoxLayout(self)
        self._bar = QTabBar()
        self.main_layout.addWidget(self._bar, 5, QtCore.Qt.AlignmentFlag.AlignTop)
        self.group_home = QGroupBox("Group Box Home")
        self.group_settings = QGroupBox("Group Box Settings")

        self.home = self._bar.addTab("Home")
        self.settings = self._bar.addTab("Settings")

        self.label_home = QLabel("Texto en Home")
        self.label_settings = QLabel("Texto en Settings")
        self.start = QPushButton('Start')

        self.button_box = QDialogButtonBox()
        self.button_box.addButton(self.start, QDialogButtonBox.ButtonRole.NoRole)

        self.main_layout.addWidget(self.button_box, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.start.clicked.connect(magic)
        if self._bar.currentIndex() == 0:
            self.main_layout.addWidget(self.label_home, 5, QtCore.Qt.AlignmentFlag.AlignCenter)
        elif self._bar.currentIndex() == 1:
            print("Setting here")
            self.main_layout.addWidget(self.label_settings, 5, QtCore.Qt.AlignmentFlag.AlignCenter)


class SettingWindow:
    pass


@QtCore.Slot()
def magic(self):
    print("The button works")


