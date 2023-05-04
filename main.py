# ***Imports***
# Local
from classes.qt import widgets
# Core
import sys
# Third
from PySide6 import QtWidgets


def main():
    app = QtWidgets.QApplication([])
    main_box = widgets.MainWindow()
    main_box.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
