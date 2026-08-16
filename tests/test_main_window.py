import pytest
from PySide6.QtWidgets import QMessageBox

from proxyme.qt.main_window import MainWindow


@pytest.fixture
def main_window(isolated_ssh_config, isolated_repository, qapp):
    return MainWindow(qapp)


def test_view_logs_shows_message_when_none_exist(main_window, tmp_path, monkeypatch, mocker):
    import proxyme.logging_setup as logging_setup_module
    monkeypatch.setattr(logging_setup_module, "_LOG_DIR", tmp_path / "empty")

    info = mocker.patch.object(QMessageBox, "information")
    main_window._view_logs()
    info.assert_called_once()


def test_view_logs_opens_the_most_recent_log_file(main_window, tmp_path, monkeypatch, mocker):
    import proxyme.logging_setup as logging_setup_module
    monkeypatch.setattr(logging_setup_module, "_LOG_DIR", tmp_path)
    log_file = tmp_path / "proxyme-2026-01-01_000000.log"
    log_file.write_text("session log", encoding="utf-8")

    dialog_cls = mocker.patch("proxyme.qt.main_window.TextFileDialog")
    dialog_cls.return_value.exec.return_value = None

    main_window._view_logs()

    args, kwargs = dialog_cls.call_args
    assert args[1] == log_file
    assert kwargs.get("read_only") is True
