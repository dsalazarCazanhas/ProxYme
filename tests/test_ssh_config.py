import pytest

from proxyme.storage.repository import TunnelSupplement, upsert
from proxyme.storage.ssh_config import (
    get_key_filename,
    get_key_path,
    load_hosts,
    peek_auth_method,
    peek_tunnel_gaps,
    resolve_tunnel,
    resolve_tunnel_partial,
)
from proxyme.tunnel.models import AuthMethod, TunnelMode


def _write_config(path, text):
    path.write_text(text, encoding="utf-8")


def test_load_hosts_excludes_wildcard(isolated_ssh_config):
    _write_config(isolated_ssh_config, """
Host *
    ServerAliveInterval 60

Host db
    HostName db.internal

Host web
    HostName web.internal
""")
    assert set(load_hosts()) == {"db", "web"}


def test_load_hosts_empty_when_no_config_file(isolated_ssh_config):
    assert load_hosts() == []


def test_resolve_tunnel_local_forward_bare_port(isolated_ssh_config):
    _write_config(isolated_ssh_config, """
Host db
    HostName db.internal
    User alice
    LocalForward 5432 127.0.0.1:5432
""")
    config = resolve_tunnel("db")

    assert config.ssh_host == "db.internal"
    assert config.ssh_user == "alice"
    assert config.mode == TunnelMode.LOCAL
    assert config.local_port == 5432
    assert config.remote_host == "127.0.0.1"
    assert config.remote_port == 5432
    assert config.auth_method == AuthMethod.PASSWORD


def test_resolve_tunnel_local_forward_with_bind_address(isolated_ssh_config):
    _write_config(isolated_ssh_config, """
Host db
    HostName db.internal
    LocalForward 127.0.0.1:5432 db.internal:5432
""")
    config = resolve_tunnel("db")
    assert config.local_port == 5432
    assert config.remote_host == "db.internal"
    assert config.remote_port == 5432


def test_resolve_tunnel_dynamic_forward(isolated_ssh_config):
    _write_config(isolated_ssh_config, """
Host proxy
    HostName proxy.internal
    DynamicForward 1080
""")
    config = resolve_tunnel("proxy")
    assert config.mode == TunnelMode.DYNAMIC
    assert config.local_port == 1080
    assert config.remote_host is None
    assert config.remote_port is None


def test_resolve_tunnel_uses_identity_file_for_private_key_auth(isolated_ssh_config, tmp_path):
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("fake key", encoding="utf-8")
    _write_config(isolated_ssh_config, f"""
Host db
    HostName db.internal
    IdentityFile {key_path}
    LocalForward 5432 db.internal:5432
""")
    config = resolve_tunnel("db")
    assert config.auth_method == AuthMethod.PRIVATE_KEY
    assert config.key_path == str(key_path)


def test_resolve_tunnel_defaults_ssh_host_to_alias_when_hostname_unset(isolated_ssh_config):
    """paramiko.SSHConfig.lookup() fills in 'hostname' with the alias itself when
    HostName isn't set — so ssh_host can never be missing for an SSH-config host."""
    _write_config(isolated_ssh_config, """
Host db
    LocalForward 5432 db.internal:5432
""")
    config = resolve_tunnel("db")
    assert config.ssh_host == "db"


def test_resolve_tunnel_fills_gaps_from_supplement(isolated_ssh_config, isolated_repository):
    _write_config(isolated_ssh_config, """
Host db
    HostName db.internal
""")
    upsert(TunnelSupplement(
        name="db", mode=TunnelMode.LOCAL, local_port=5432,
        remote_host="db.internal", remote_port=5432,
    ))

    config = resolve_tunnel("db")
    assert config.mode == TunnelMode.LOCAL
    assert config.local_port == 5432
    assert config.remote_host == "db.internal"


def test_resolve_tunnel_raises_when_no_forwarding_info_anywhere(
    isolated_ssh_config, isolated_repository,
):
    _write_config(isolated_ssh_config, """
Host db
    HostName db.internal
""")
    with pytest.raises(ValueError):
        resolve_tunnel("db")


def test_peek_tunnel_gaps_empty_when_ssh_config_has_forwarding(isolated_ssh_config):
    _write_config(isolated_ssh_config, """
Host db
    HostName db.internal
    LocalForward 5432 db.internal:5432
""")
    assert peek_tunnel_gaps("db") == set()


def test_peek_tunnel_gaps_reports_missing_fields(isolated_ssh_config, isolated_repository):
    _write_config(isolated_ssh_config, """
Host db
    HostName db.internal
""")
    gaps = peek_tunnel_gaps("db")
    assert gaps == {"mode", "local_port", "remote_host", "remote_port"}


def test_peek_tunnel_gaps_dynamic_mode_does_not_need_remote_fields(
    isolated_ssh_config, isolated_repository,
):
    _write_config(isolated_ssh_config, """
Host proxy
    HostName proxy.internal
""")
    upsert(TunnelSupplement(name="proxy", mode=TunnelMode.DYNAMIC, local_port=1080))

    assert peek_tunnel_gaps("proxy") == set()


def test_peek_auth_method_password_when_no_identity_file(isolated_ssh_config):
    _write_config(isolated_ssh_config, """
Host db
    HostName db.internal
""")
    assert peek_auth_method("db") == AuthMethod.PASSWORD


def test_get_key_filename_and_path(isolated_ssh_config):
    key_path = isolated_ssh_config.parent / "id_ed25519"
    _write_config(isolated_ssh_config, f"""
Host db
    HostName db.internal
    IdentityFile {key_path}
""")
    assert get_key_filename("db") == "id_ed25519"
    assert get_key_path("db") == str(key_path)


def test_resolve_tunnel_partial_never_raises_on_incomplete_config(
    isolated_ssh_config, isolated_repository,
):
    _write_config(isolated_ssh_config, """
Host db
    HostName db.internal
""")
    partial = resolve_tunnel_partial("db")
    assert partial == {
        "mode": None, "local_port": None, "remote_host": None, "remote_port": None,
    }


