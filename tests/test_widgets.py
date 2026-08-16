import os

import pytest

from proxyme.qt.widgets import TunnelTab
from proxyme.storage import repository
from proxyme.tunnel.models import TunnelMode


def _write_config(path, text):
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def tunnel_tab(isolated_ssh_config, isolated_repository, qapp):
    return TunnelTab()


def test_open_ssh_config_uses_editor_env_var_when_launchable(tunnel_tab, monkeypatch, mocker):
    monkeypatch.setenv("EDITOR", "true")
    monkeypatch.delenv("VISUAL", raising=False)
    popen = mocker.patch("subprocess.Popen")
    run = mocker.patch("subprocess.run")

    tunnel_tab._open_ssh_config()

    popen.assert_called_once()
    args = popen.call_args[0][0]
    assert args[0] == "true"
    assert args[-1].endswith("config")
    run.assert_not_called()


def test_open_ssh_config_splits_editor_with_arguments(tunnel_tab, monkeypatch, mocker):
    monkeypatch.setenv("VISUAL", "code --wait")
    popen = mocker.patch("subprocess.Popen")
    mocker.patch("subprocess.run")

    tunnel_tab._open_ssh_config()

    args = popen.call_args[0][0]
    assert args[:2] == ["code", "--wait"]


def test_open_ssh_config_falls_back_when_editor_binary_missing(tunnel_tab, monkeypatch, mocker):
    monkeypatch.setenv("EDITOR", "not-a-real-editor")
    popen = mocker.patch("subprocess.Popen", side_effect=FileNotFoundError)
    run = mocker.patch("subprocess.run")

    tunnel_tab._open_ssh_config()

    popen.assert_called_once()
    run.assert_called_once()


def test_open_ssh_config_uses_os_default_when_no_editor_env_set(tunnel_tab, monkeypatch, mocker):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    popen = mocker.patch("subprocess.Popen")
    run = mocker.patch("subprocess.run")

    tunnel_tab._open_ssh_config()

    popen.assert_not_called()
    if os.name != "nt":
        run.assert_called_once()


def test_open_ssh_config_prefers_visual_over_editor(tunnel_tab, monkeypatch, mocker):
    monkeypatch.setenv("VISUAL", "visual-editor")
    monkeypatch.setenv("EDITOR", "editor-editor")
    popen = mocker.patch("subprocess.Popen")
    mocker.patch("subprocess.run")

    tunnel_tab._open_ssh_config()

    assert popen.call_args[0][0][0] == "visual-editor"


def test_taken_manual_names_includes_ssh_hosts_and_manual_configs(
    tunnel_tab, isolated_ssh_config,
):
    _write_config(isolated_ssh_config, """
Host sshhost1
    HostName ssh1.internal
""")
    tunnel_tab._manual_configs["manual1"] = object()

    assert tunnel_tab._taken_manual_names() == {"sshhost1", "manual1"}


class TestSaveTunnelFieldsGapFilling:
    """_save_tunnel_fields() — the pre-Start gap-filling path for SSH-config hosts."""

    def _make_gap_host(self, isolated_ssh_config):
        _write_config(isolated_ssh_config, """
Host gaphost
    HostName gap.internal
""")

    def test_rejects_non_numeric_local_port(self, tunnel_tab, isolated_ssh_config):
        self._make_gap_host(isolated_ssh_config)
        tunnel_tab._fields.local_port_field.setText("not-a-port")

        assert tunnel_tab._save_tunnel_fields("gaphost") is False
        assert "1 and 65535" in tunnel_tab._fields_error_label.text()

    def test_rejects_missing_remote_host_in_local_mode(self, tunnel_tab, isolated_ssh_config):
        self._make_gap_host(isolated_ssh_config)
        tunnel_tab._fields.local_port_field.setText("5432")
        tunnel_tab._fields.remote_host_field.setText("")
        tunnel_tab._fields.remote_port_field.setText("5432")

        assert tunnel_tab._save_tunnel_fields("gaphost") is False
        assert "Remote host is required" in tunnel_tab._fields_error_label.text()

    def test_saves_valid_local_mode_fields(
        self, tunnel_tab, isolated_ssh_config, isolated_repository,
    ):
        self._make_gap_host(isolated_ssh_config)
        tunnel_tab._fields.local_port_field.setText("5432")
        tunnel_tab._fields.remote_host_field.setText("db.internal")
        tunnel_tab._fields.remote_port_field.setText("5432")

        assert tunnel_tab._save_tunnel_fields("gaphost") is True
        saved = repository.find_by_name("gaphost")
        assert saved.local_port == 5432
        assert saved.remote_host == "db.internal"

    def test_saves_bind_all_interfaces_checkbox_state(
        self, tunnel_tab, isolated_ssh_config, isolated_repository,
    ):
        self._make_gap_host(isolated_ssh_config)
        tunnel_tab._fields.local_port_field.setText("5432")
        tunnel_tab._fields.remote_host_field.setText("db.internal")
        tunnel_tab._fields.remote_port_field.setText("5432")
        tunnel_tab._fields.bind_all_checkbox.setChecked(True)

        assert tunnel_tab._save_tunnel_fields("gaphost") is True
        saved = repository.find_by_name("gaphost")
        assert saved.bind_all_interfaces is True

    def test_dynamic_mode_does_not_require_remote_fields(
        self, tunnel_tab, isolated_ssh_config, isolated_repository,
    ):
        self._make_gap_host(isolated_ssh_config)
        tunnel_tab._fields.mode_combo.setCurrentIndex(
            tunnel_tab._fields.mode_combo.findData(TunnelMode.DYNAMIC)
        )
        tunnel_tab._fields.local_port_field.setText("1080")

        assert tunnel_tab._save_tunnel_fields("gaphost") is True
        saved = repository.find_by_name("gaphost")
        assert saved.mode == TunnelMode.DYNAMIC
        assert saved.remote_host is None
        assert saved.remote_port is None


class TestSaveAllTunnelFieldsEditOverride:
    """_save_all_tunnel_fields() — the "Edit" override path for SSH-config hosts."""

    def test_rejects_non_numeric_local_port(self, tunnel_tab):
        tunnel_tab._fields.local_port_field.setText("nope")

        assert tunnel_tab._save_all_tunnel_fields("somehost") is False
        assert "1 and 65535" in tunnel_tab._fields_error_label.text()

    def test_rejects_missing_remote_host_in_local_mode(self, tunnel_tab):
        tunnel_tab._fields.local_port_field.setText("5432")
        tunnel_tab._fields.remote_host_field.setText("")
        tunnel_tab._fields.remote_port_field.setText("5432")

        assert tunnel_tab._save_all_tunnel_fields("somehost") is False
        assert "Remote host is required" in tunnel_tab._fields_error_label.text()

    def test_saves_and_clears_error_on_valid_input(self, tunnel_tab, isolated_repository):
        tunnel_tab._show_fields_error("stale error from a previous attempt")
        tunnel_tab._fields.local_port_field.setText("5432")
        tunnel_tab._fields.remote_host_field.setText("db.internal")
        tunnel_tab._fields.remote_port_field.setText("5432")

        assert tunnel_tab._save_all_tunnel_fields("somehost") is True
        assert tunnel_tab._fields_error_label.isHidden()
        saved = repository.find_by_name("somehost")
        assert saved.local_port == 5432


def test_on_start_does_not_connect_when_gap_fields_are_invalid(
    tunnel_tab, isolated_ssh_config, mocker,
):
    _write_config(isolated_ssh_config, """
Host gaphost
    HostName gap.internal
""")
    tunnel_tab.host_combo.addItem("gaphost")
    tunnel_tab.host_combo.setCurrentText("gaphost")
    tunnel_tab._fields.local_port_field.setText("not-a-port")

    start_spy = mocker.patch.object(tunnel_tab._manager, "start")
    tunnel_tab._on_start()

    start_spy.assert_not_called()
    assert "1 and 65535" in tunnel_tab._fields_error_label.text()
