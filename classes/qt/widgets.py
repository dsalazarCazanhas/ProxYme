# ***Imports***
# Local
from .meta import icon
# Core

# Third
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QWidget, QHBoxLayout, QTabWidget, QFormLayout, QLineEdit, QPushButton, QCheckBox


class TabBar(QWidget):
    def __init__(self):
        super().__init__()

        # Init Layout and the tab bar
        self.main_layout = QHBoxLayout()
        self.tab_bar = QTabWidget(self)

        # Home Tab config
        self.home = QWidget(self)
        self.home_layout = QFormLayout()

        # Start Button
        self.start_button = QPushButton("&Start")
        self.start_button.clicked.connect(self.start_button_on_click)

        # Home tab fields and configs
        # Username
        self.username_format = QLineEdit()
        self.username_format.setPlaceholderText('username')
        # Password
        self.password_format = QLineEdit()
        self.password_format.setPlaceholderText('password')
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

        # Building the home tab
        self.home.setLayout(self.home_layout)
        self.home_layout.addRow('Username: ', self.username_format)
        self.home_layout.addRow('Password: ', self.password_format)
        self.home_layout.addWidget(self.remember_credentials_button)
        self.home_layout.addWidget(self.start_button)
        self.home_layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignJustify)

        # Settings tab
        settings = QWidget(self)
        settings_layout = QFormLayout()
        settings.setLayout(settings_layout)

        # Adding the configs to the Bar Tab
        self.tab_bar.addTab(self.home, "Home")
        self.tab_bar.addTab(settings, "Settings")
        self.main_layout.addWidget(self.tab_bar, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.main_layout)

    # SLOTS for the signals
    def start_button_on_click(self):
        if not self.username_format.text() or not self.password_format.text():
            print("Check again, you let a field empty!")
        else:
            print({self.username_format.text(): self.password_format.text()})

    def credential_button_checked(self):
        print("Checked" if self.remember_credentials_button.isChecked() else "Is unchecked")

    def show_password(self, show):
        if show:
            self.showPassAction.setIcon(QtGui.QIcon(icon['icon_eye_opened']))
            self.password_format.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.showPassAction.setIcon(self.eye_icon_closed)
            self.password_format.setEchoMode(QLineEdit.EchoMode.Password)
