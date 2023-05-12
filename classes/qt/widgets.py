# ***Imports***
# Local
from .metas import icon
# Core

# Third
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QWidget, QHBoxLayout, QTabWidget, QFormLayout, QLineEdit, QPushButton, QCheckBox


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
        username_format.setStyleSheet("color: black;")
        username_format.setStyleSheet('background-color:grey')
        self.password_format = QLineEdit()
        self.password_format.setPlaceholderText('password')
        self.password_format.setStyleSheet('background-color: grey')
        self.password_format.setEchoMode(QLineEdit.EchoMode.Password)
        # Widget with the action to see the password
        self.eye_icon_closed = QtGui.QIcon(icon['icon_eye_closed'])
        self.showPassAction = QtGui.QAction(self.eye_icon_closed, 'Show Password', self)
        self.password_format.addAction(
            self.showPassAction, QLineEdit.ActionPosition.TrailingPosition)
        self.showPassAction.setCheckable(True)
        self.showPassAction.toggled.connect(self.show_password)
        # Remember credentials checkable button
        self.remember_credentials_button = QCheckBox('Remember credentials')
        self.remember_credentials_button.stateChanged.connect(self.credential_button_checked)

        # Build the tab
        home.setLayout(home_layout)
        home_layout.addRow('Username: ', username_format)
        home_layout.addRow('Password: ', self.password_format)
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
        print("Checked" if self.remember_credentials_button.isChecked() else "Is unchecked")

    def show_password(self, show):
        if show:
            self.showPassAction.setIcon(QtGui.QIcon(icon['icon_eye_opened']))
            self.password_format.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.showPassAction.setIcon(self.eye_icon_closed)
            self.password_format.setEchoMode(QLineEdit.EchoMode.Password)
