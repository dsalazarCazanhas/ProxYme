# ***Imports***
# Local
from classes.qt.main_window import MainWindow
from classes.qt.widgets import TabBar
# Core
import sys
# Third
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication()
    main_box = MainWindow(app)
    main_box.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
