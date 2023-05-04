# ***Imports***
# Local
# Core
import os
# Third
from PySide6 import QtWidgets, QtGui, QtCore


icon = os.path.dirname(os.path.realpath(__file__))


class Widgets(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self._bar = QtWidgets.QTabBar()
        self.home = self._bar.addTab("Home")
        self.settings = self._bar.addTab("Settings")

        self.start = QtWidgets.QPushButton('Start')

        self.button_box = QtWidgets.QDialogButtonBox()
        self.button_box.addButton(self.start, QtWidgets.QDialogButtonBox.ButtonRole.NoRole)

        self.main_layout.addWidget(self._bar, 5, QtCore.Qt.AlignmentFlag.AlignTop)
        self.main_layout.addWidget(self.button_box, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.start.clicked.connect(magic)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ProxYme')
        self.resize(450, 325)
        self.setWindowIcon(QtGui.QIcon(icon + os.path.sep + 'icon2.png'))
        self._widgets = Widgets()
        self.setCentralWidget(self._widgets)


class SettingWindow:
    pass


@QtCore.Slot()
def magic(self):
    print("The button works")




