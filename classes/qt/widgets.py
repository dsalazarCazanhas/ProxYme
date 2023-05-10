# ***Imports***
# Local
# Core
import os
# Third
from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabBar, QTabWidget, QFormLayout, QLineEdit,\
    QBoxLayout, QLabel, QPushButton, QCheckBox


class TabBar(QWidget):
    def __init__(self):
        super().__init__()

        self.main_layout = QHBoxLayout()
        tab_bar = QTabWidget(self)

        # Home Tab config
        home = QWidget(self)
        home_layout = QFormLayout()

        start_button = QPushButton("Start")
        start_button.setStyleSheet('background-color:grey')
        # self.start_button.autoDefault()
        start_button.clicked.connect(self.start_button_on_click)

        username_format = QLineEdit()
        username_format.setPlaceholderText('username')
        password_format = QLineEdit()
        password_format.setPlaceholderText('password')
        password_format.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember_credentials_button = QCheckBox('Remember credentials')
        self.remember_credentials_button.stateChanged.connect(self.credential_button_checked)

        # Build the tab
        home.setLayout(home_layout)
        home_layout.addRow('Username: ', username_format)
        home_layout.addRow('Password: ', password_format)
        home_layout.addWidget(self.remember_credentials_button)
        home_layout.addWidget(start_button)
        home_layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignJustify)

        settings = QWidget(self)
        settings_layout = QFormLayout()
        settings.setLayout(settings_layout)

        tab_bar.addTab(home, "Home")
        tab_bar.addTab(settings, "Settings")
        self.main_layout.addWidget(tab_bar, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.main_layout)

    def start_button_on_click(self):
        print("Pressed button")

    def credential_button_checked(self):
        if self.remember_credentials_button.isChecked():
            print("Is checked")
        else:
            print("Is unchecked")