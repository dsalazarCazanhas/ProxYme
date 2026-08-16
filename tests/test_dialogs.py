import pytest

from proxyme.qt.dialogs import ManualTunnelDialog
from proxyme.tunnel.models import AuthMethod, TunnelMode


@pytest.fixture
def dialog(qapp):
    return ManualTunnelDialog()


def _fill_minimal_local(dlg, name="myserver", host="db.internal"):
    dlg._name.setText(name)
    dlg._host.setText(host)
    dlg._fields.local_port_field.setText("5432")
    dlg._fields.remote_host_field.setText("db.internal")
    dlg._fields.remote_port_field.setText("5432")


class TestRequiredFields:
    def test_name_is_required(self, dialog):
        _fill_minimal_local(dialog, name="")
        assert dialog._try_build_config() is None
        assert "Name is required" in dialog._error_label.text()

    def test_ssh_host_is_required(self, dialog):
        _fill_minimal_local(dialog, host="")
        assert dialog._try_build_config() is None
        assert "SSH Host is required" in dialog._error_label.text()

    def test_remote_host_required_for_local_mode(self, dialog):
        _fill_minimal_local(dialog)
        dialog._fields.remote_host_field.setText("")
        assert dialog._try_build_config() is None
        assert "Remote host is required" in dialog._error_label.text()

    def test_remote_host_not_required_for_dynamic_mode(self, dialog):
        dialog._name.setText("myserver")
        dialog._host.setText("db.internal")
        dialog._fields.local_port_field.setText("1080")
        dialog._fields.mode_combo.setCurrentIndex(
            dialog._fields.mode_combo.findData(TunnelMode.DYNAMIC)
        )
        config = dialog._try_build_config()
        assert config is not None
        assert config.remote_host is None
        assert config.remote_port is None

    def test_identity_file_required_for_private_key_auth(self, dialog):
        _fill_minimal_local(dialog)
        dialog._auth.radio_key.setChecked(True)
        dialog._auth.key_path_field.setText("")
        assert dialog._try_build_config() is None
        assert "Identity file is required" in dialog._error_label.text()


class TestPortValidation:
    @pytest.mark.parametrize("field", ["_port", "local_port_field", "remote_port_field"])
    def test_rejects_non_numeric_port(self, dialog, field):
        _fill_minimal_local(dialog)
        target = dialog._fields.__dict__[field] if field != "_port" else dialog._port
        target.setText("not-a-port")
        assert dialog._try_build_config() is None
        assert "1 and 65535" in dialog._error_label.text()

    @pytest.mark.parametrize("bad_value", ["0", "-1", "65536", "999999"])
    def test_rejects_out_of_range_local_port(self, dialog, bad_value):
        _fill_minimal_local(dialog)
        dialog._fields.local_port_field.setText(bad_value)
        assert dialog._try_build_config() is None
        assert "1 and 65535" in dialog._error_label.text()

    def test_accepts_boundary_port_values(self, dialog):
        _fill_minimal_local(dialog)
        dialog._port.setText("1")
        dialog._fields.local_port_field.setText("65535")
        config = dialog._try_build_config()
        assert config is not None
        assert config.ssh_port == 1
        assert config.local_port == 65535


class TestBindAllInterfaces:
    def test_defaults_to_loopback_only(self, dialog):
        _fill_minimal_local(dialog)
        config = dialog._try_build_config()
        assert config.bind_all_interfaces is False

    def test_checkbox_is_carried_into_the_built_config(self, dialog):
        _fill_minimal_local(dialog)
        dialog._fields.bind_all_checkbox.setChecked(True)
        config = dialog._try_build_config()
        assert config.bind_all_interfaces is True

    def test_editing_prefills_checkbox_from_existing_config(self, qapp):
        from proxyme.tunnel.models import TunnelConfig
        existing = TunnelConfig(
            name="myserver", ssh_host="db.internal", ssh_port=22, ssh_user="alice",
            auth_method=AuthMethod.PASSWORD, mode=TunnelMode.LOCAL, local_port=5432,
            remote_host="db.internal", remote_port=5432, key_path=None,
            bind_all_interfaces=True,
        )
        dlg = ManualTunnelDialog(existing=existing)
        assert dlg._fields.bind_all_checkbox.isChecked() is True


class TestDuplicateNames:
    def test_rejects_name_already_taken(self, qapp):
        dlg = ManualTunnelDialog(taken_names={"myserver", "other"})
        _fill_minimal_local(dlg, name="myserver")
        assert dlg._try_build_config() is None
        assert "already exists" in dlg._error_label.text()

    def test_allows_name_not_in_taken_set(self, qapp):
        dlg = ManualTunnelDialog(taken_names={"other"})
        _fill_minimal_local(dlg, name="myserver")
        assert dlg._try_build_config() is not None

    def test_editing_excludes_its_own_name_when_caller_passes_correct_set(self, qapp):
        from proxyme.tunnel.models import TunnelConfig
        existing = TunnelConfig(
            name="myserver", ssh_host="db.internal", ssh_port=22, ssh_user="alice",
            auth_method=AuthMethod.PASSWORD, mode=TunnelMode.LOCAL, local_port=5432,
            remote_host="db.internal", remote_port=5432, key_path=None,
        )
        # Caller is expected to exclude the entry's own name from taken_names.
        dlg = ManualTunnelDialog(existing=existing, taken_names={"other-server"})
        config = dlg._try_build_config()
        assert config is not None
        assert config.name == "myserver"
