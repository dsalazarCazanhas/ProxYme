import pytest

from proxyme.qt.widgets import TunnelTab
from proxyme.storage import repository
from proxyme.tunnel.models import TunnelMode


def _write_config(path, text):
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def tunnel_tab(isolated_ssh_config, isolated_repository, qapp):
    return TunnelTab()


class TestOpenSshConfig:
    """Editing happens in-app now — launching an external program (an
    editor, or the OS's "default app") proved unreliable from the packaged
    binary, so there's no subprocess/OS integration left to break."""

    def test_creates_the_file_if_missing(self, tunnel_tab, isolated_ssh_config, mocker):
        assert not isolated_ssh_config.exists()
        mocker.patch("proxyme.qt.widgets.TextFileDialog")

        tunnel_tab._open_ssh_config()

        assert isolated_ssh_config.exists()

    def test_opens_an_editable_dialog_on_the_real_file(
        self, tunnel_tab, isolated_ssh_config, mocker,
    ):
        isolated_ssh_config.write_text("Host db\n", encoding="utf-8")
        dialog_cls = mocker.patch("proxyme.qt.widgets.TextFileDialog")
        dialog_cls.return_value.exec.return_value = None

        tunnel_tab._open_ssh_config()

        args, kwargs = dialog_cls.call_args
        assert args[1] == isolated_ssh_config
        assert kwargs.get("read_only", False) is False


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
