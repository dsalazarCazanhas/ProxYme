import sys

from PySide6.QtWidgets import QApplication

from proxyme.qt.main_window import MainWindow


def main():
    app = QApplication()
    main_box = MainWindow(app)
    main_box.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
