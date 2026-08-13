import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from proxyme.storage import repository as repo_module
from proxyme.storage import ssh_config as ssh_config_module


@pytest.fixture
def isolated_repository(tmp_path, monkeypatch):
    """Point the tunnel supplement repository at a throwaway directory."""
    config_dir = tmp_path / ".proxyme"
    config_file = config_dir / "tunnels.json"
    monkeypatch.setattr(repo_module, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(repo_module, "_CONFIG_FILE", config_file)
    return config_file


@pytest.fixture
def isolated_ssh_config(tmp_path, monkeypatch):
    """Point the SSH config reader at a throwaway ~/.ssh/config file."""
    config_path = tmp_path / ".ssh" / "config"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ssh_config_module, "_SSH_CONFIG_PATH", config_path)
    return config_path


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
