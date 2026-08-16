import stat
import sys

import pytest

from proxyme.storage.repository import (
    TunnelSupplement,
    delete_by_name,
    find_by_name,
    load_all,
    upsert,
)
from proxyme.tunnel.models import TunnelMode


def test_load_all_returns_empty_list_when_file_missing(isolated_repository):
    assert load_all() == []


def test_upsert_then_find_by_name(isolated_repository):
    supplement = TunnelSupplement(
        name="db", mode=TunnelMode.LOCAL, local_port=5432,
        remote_host="db.internal", remote_port=5432,
    )
    upsert(supplement)

    found = find_by_name("db")
    assert found == supplement


def test_upsert_overwrites_existing_entry_with_same_name(isolated_repository):
    upsert(TunnelSupplement(name="db", mode=TunnelMode.LOCAL, local_port=1111))
    upsert(TunnelSupplement(name="db", mode=TunnelMode.LOCAL, local_port=2222))

    all_entries = load_all()
    assert len(all_entries) == 1
    assert all_entries[0].local_port == 2222


def test_delete_by_name_removes_only_matching_entry(isolated_repository):
    upsert(TunnelSupplement(name="db", mode=TunnelMode.LOCAL, local_port=1111))
    upsert(TunnelSupplement(name="web", mode=TunnelMode.DYNAMIC, local_port=1080))

    delete_by_name("db")

    remaining = load_all()
    assert [s.name for s in remaining] == ["web"]


def test_find_by_name_returns_none_when_absent(isolated_repository):
    assert find_by_name("missing") is None


def test_supplement_never_stores_credentials(isolated_repository):
    """TunnelSupplement has no field for password/passphrase — guard against regressions."""
    field_names = set(TunnelSupplement.__dataclass_fields__)
    assert field_names == {
        "name", "mode", "local_port", "remote_host", "remote_port", "bind_all_interfaces",
    }


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only permission bits")
def test_save_all_writes_owner_only_permissions(isolated_repository):
    upsert(TunnelSupplement(name="db", mode=TunnelMode.LOCAL, local_port=5432))

    dir_mode = stat.S_IMODE(isolated_repository.parent.stat().st_mode)
    file_mode = stat.S_IMODE(isolated_repository.stat().st_mode)
    assert dir_mode == 0o700
    assert file_mode == 0o600
