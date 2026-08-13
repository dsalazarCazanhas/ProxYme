import argparse
import logging
import signal
import sys
from importlib.metadata import version

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from proxyme.logging_setup import init_logging
from proxyme.qt.main_window import MainWindow
from proxyme.single_instance import acquire, release


def main():
    parser = argparse.ArgumentParser(description="ProxYme — SSH tunnel manager")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args = parser.parse_args()
    if args.version:
        print(f"ProxYme {version('proxyme')}")
        return

    init_logging()
    log = logging.getLogger(__name__)

    app = QApplication(sys.argv)

    # Qt's event loop holds the GIL and never yields to Python's signal machinery.
    # A short-interval timer interrupts the loop periodically so Python can dispatch
    # pending signals (including SIGINT from Ctrl-C).
    _signal_timer = QTimer()
    _signal_timer.start(200)
    _signal_timer.timeout.connect(lambda: None)
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    if not acquire():
        msg = QMessageBox()
        msg.setWindowTitle("ProxYme")
        msg.setText("ProxYme is already running.")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.exec()
        sys.exit(0)

    log.info("ProxYme starting")
    main_box = MainWindow(app)
    main_box.show()

    try:
        exit_code = app.exec()
    finally:
        release()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
