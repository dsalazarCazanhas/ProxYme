import pytest

import proxyme.qt.system_open as system_open_module
from proxyme.qt.widgets import TunnelTab
from proxyme.storage import repository
from proxyme.tunnel.models import TunnelMode


def _write_config(path, text):
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def tunnel_tab(isolated_ssh_config, isolated_repository, qapp):
    return TunnelTab()


@pytest.fixture(autouse=True)
def isolated_open_settings(tmp_path, monkeypatch):
    """Point the remembered "open with" app setting at a throwaway file."""
    monkeypatch.setattr(system_open_module, "_SETTINGS_FILE", tmp_path / "settings.json")


def test_open_ssh_config_uses_editor_env_var_when_launchable(tunnel_tab, monkeypatch, mocker):
    monkeypatch.setenv("EDITOR", "true")
    monkeypatch.delenv("VISUAL", raising=False)
    popen = mocker.patch("subprocess.Popen")
    dialog = mocker.patch("proxyme.qt.system_open.QFileDialog.getOpenFileName")

    tunnel_tab._open_ssh_config()

    popen.assert_called_once()
    args = popen.call_args[0][0]
    assert args[0] == "true"
    assert args[-1].endswith("config")
    dialog.assert_not_called()


def test_open_ssh_config_splits_editor_with_arguments(tunnel_tab, monkeypatch, mocker):
    monkeypatch.setenv("VISUAL", "code --wait")
    popen = mocker.patch("subprocess.Popen")

    tunnel_tab._open_ssh_config()

    args = popen.call_args[0][0]
    assert args[:2] == ["code", "--wait"]


def test_open_ssh_config_prefers_visual_over_editor(tunnel_tab, monkeypatch, mocker):
    monkeypatch.setenv("VISUAL", "visual-editor")
    monkeypatch.setenv("EDITOR", "editor-editor")
    popen = mocker.patch("subprocess.Popen")

    tunnel_tab._open_ssh_config()

    assert popen.call_args[0][0][0] == "visual-editor"


class TestOpenPathAppPicker:
    """No $VISUAL/$EDITOR — never silently guesses an OS "default app"
    (that resolution proved unreliable from the packaged binary); instead
    asks the user to pick an app once and remembers the choice."""

    def _no_editor_env(self, monkeypatch):
        monkeypatch.delenv("EDITOR", raising=False)
        monkeypatch.delenv("VISUAL", raising=False)

    def test_asks_user_to_pick_an_app_when_nothing_remembered(
        self, tunnel_tab, monkeypatch, mocker,
    ):
        self._no_editor_env(monkeypatch)
        popen = mocker.patch("subprocess.Popen")
        mocker.patch(
            "proxyme.qt.system_open.QFileDialog.getOpenFileName",
            return_value=("/usr/bin/nano", ""),
        )

        tunnel_tab._open_ssh_config()

        popen.assert_called_once()
        args = popen.call_args[0][0]
        assert args[0] == "/usr/bin/nano"
        assert args[-1].endswith("config")

    def test_remembers_the_chosen_app_for_next_time(self, tunnel_tab, monkeypatch, mocker):
        self._no_editor_env(monkeypatch)
        mocker.patch("subprocess.Popen")
        dialog = mocker.patch(
            "proxyme.qt.system_open.QFileDialog.getOpenFileName",
            return_value=("/usr/bin/nano", ""),
        )

        tunnel_tab._open_ssh_config()
        dialog.assert_called_once()

        dialog.reset_mock()
        tunnel_tab._open_ssh_config()
        dialog.assert_not_called()

    def test_does_nothing_when_the_picker_is_cancelled(self, tunnel_tab, monkeypatch, mocker):
        self._no_editor_env(monkeypatch)
        popen = mocker.patch("subprocess.Popen")
        mocker.patch(
            "proxyme.qt.system_open.QFileDialog.getOpenFileName", return_value=("", ""),
        )

        tunnel_tab._open_ssh_config()

        popen.assert_not_called()

    def test_asks_again_when_the_remembered_app_no_longer_exists(
        self, tunnel_tab, monkeypatch, mocker,
    ):
        self._no_editor_env(monkeypatch)
        system_open_module._save_preferred_app("/does/not/exist/editor")
        popen = mocker.patch("subprocess.Popen")
        dialog = mocker.patch(
            "proxyme.qt.system_open.QFileDialog.getOpenFileName",
            return_value=("/usr/bin/nano", ""),
        )

        tunnel_tab._open_ssh_config()

        dialog.assert_called_once()
        assert popen.call_args[0][0][0] == "/usr/bin/nano"


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
