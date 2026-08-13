import paramiko
import pytest

from proxyme.tunnel.auth.password import PasswordAuth
from proxyme.tunnel.auth.private_key import PrivateKeyAuth, load_private_key


def test_password_auth_applies_transport_auth_password(mocker):
    transport = mocker.Mock(spec=paramiko.Transport)
    PasswordAuth("alice", "s3cret").apply(transport)
    transport.auth_password.assert_called_once_with("alice", "s3cret")


def test_load_private_key_raises_when_path_is_none():
    with pytest.raises(ValueError, match="No private key path"):
        load_private_key(None)


def test_load_private_key_raises_for_unparseable_file(tmp_path):
    bogus = tmp_path / "not_a_key"
    bogus.write_text("this is not a valid key", encoding="utf-8")
    with pytest.raises(paramiko.SSHException):
        load_private_key(str(bogus))


def test_load_private_key_propagates_password_required(tmp_path, mocker):
    key_file = tmp_path / "id_rsa"
    key_file.write_text("placeholder", encoding="utf-8")

    mocker.patch.object(
        paramiko.Ed25519Key, "from_private_key_file",
        side_effect=paramiko.PasswordRequiredException("locked"),
    )
    with pytest.raises(paramiko.PasswordRequiredException):
        load_private_key(str(key_file))


def test_load_private_key_tries_ed25519_before_others(tmp_path, mocker):
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("placeholder", encoding="utf-8")

    fake_key = mocker.Mock(spec=paramiko.PKey)
    from_file = mocker.patch.object(
        paramiko.Ed25519Key, "from_private_key_file", return_value=fake_key,
    )
    other = mocker.patch.object(paramiko.RSAKey, "from_private_key_file")

    result = load_private_key(str(key_file))

    assert result is fake_key
    from_file.assert_called_once_with(str(key_file), password=None)
    other.assert_not_called()


def test_load_private_key_encodes_passphrase(tmp_path, mocker):
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("placeholder", encoding="utf-8")
    from_file = mocker.patch.object(
        paramiko.Ed25519Key, "from_private_key_file", return_value=mocker.Mock(),
    )

    load_private_key(str(key_file), passphrase="hunter2")  # noqa: S106 — test fixture, not a real secret

    from_file.assert_called_once_with(str(key_file), password=b"hunter2")


def test_private_key_auth_applies_transport_auth_publickey(tmp_path, mocker):
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("placeholder", encoding="utf-8")
    fake_key = mocker.Mock(spec=paramiko.PKey)
    mocker.patch.object(paramiko.Ed25519Key, "from_private_key_file", return_value=fake_key)

    transport = mocker.Mock(spec=paramiko.Transport)
    PrivateKeyAuth("alice", str(key_file)).apply(transport)

    transport.auth_publickey.assert_called_once_with("alice", fake_key)
