import time

from proxyme.logging_setup import latest_log_file


def test_latest_log_file_returns_none_when_dir_missing(tmp_path, monkeypatch):
    import proxyme.logging_setup as logging_setup_module
    monkeypatch.setattr(logging_setup_module, "_LOG_DIR", tmp_path / "does-not-exist")
    assert latest_log_file() is None


def test_latest_log_file_returns_none_when_no_logs_present(tmp_path, monkeypatch):
    import proxyme.logging_setup as logging_setup_module
    monkeypatch.setattr(logging_setup_module, "_LOG_DIR", tmp_path)
    assert latest_log_file() is None


def test_latest_log_file_returns_most_recently_modified(tmp_path, monkeypatch):
    import proxyme.logging_setup as logging_setup_module
    monkeypatch.setattr(logging_setup_module, "_LOG_DIR", tmp_path)

    older = tmp_path / "proxyme-2026-01-01_000000.log"
    newer = tmp_path / "proxyme-2026-06-01_000000.log"
    older.write_text("old session", encoding="utf-8")
    time.sleep(0.01)
    newer.write_text("new session", encoding="utf-8")

    assert latest_log_file() == newer


def test_latest_log_file_ignores_non_log_files(tmp_path, monkeypatch):
    import proxyme.logging_setup as logging_setup_module
    monkeypatch.setattr(logging_setup_module, "_LOG_DIR", tmp_path)

    (tmp_path / "proxyme.lock").write_text("123", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("hi", encoding="utf-8")
    assert latest_log_file() is None
