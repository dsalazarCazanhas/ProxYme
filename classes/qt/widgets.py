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
        tab_bar = QTabWidget(self)

        # Home Tab config
        home = QWidget(self)
        start_button = QPushButton("Start")
        home_layout = QFormLayout()
        username_format = QLineEdit()
        username_format.setPlaceholderText('username')
        password_format = QLineEdit()
        password_format.setPlaceholderText('password')
        password_format.setEchoMode(QLineEdit.EchoMode.Password)
        # Build the tab
        home.setLayout(home_layout)
        home_layout.addRow('Username: ', username_format)
        home_layout.addRow('Password: ', password_format)
        home_layout.addWidget(start_button)
        home_layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignJustify)

        settings = QWidget(self)
        settings_layout = QFormLayout()
        settings.setLayout(settings_layout)
        # settings_layout.addRow('Username: ', QLineEdit(self))
        # settings_layout.addRow('Password: ', QLineEdit(self))

        tab_bar.addTab(home, "Home")
        tab_bar.addTab(settings, "Settings")
        self.main_layout.addWidget(tab_bar, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.main_layout)
