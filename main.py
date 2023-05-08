# ***Imports***
# Local
from classes.qt.mainwindow import MainWindow
# Core
import sys
# Third
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication()
    main_box = MainWindow()
    main_box.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
