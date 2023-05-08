# ***Imports***
# Local
from .widgets import Widgets
# Core
import os
# Third
from PySide6 import QtGui
from PySide6.QtWidgets import QMainWindow

icon = os.path.dirname(os.path.realpath(__file__))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ProxYTensei')
        self.resize(450, 325)
        self.setWindowIcon(QtGui.QIcon(icon + os.path.sep + 'icon2.png'))
        self._widgets = Widgets()
        self.setCentralWidget(self._widgets)

