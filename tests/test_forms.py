import pytest

from proxyme.qt.forms import parse_port


@pytest.mark.parametrize("text,expected", [
    ("22", 22),
    ("5432", 5432),
    ("1", 1),
    ("65535", 65535),
    ("  22  ", 22),
])
def test_parse_port_accepts_valid_ports(text, expected):
    assert parse_port(text) == expected


@pytest.mark.parametrize("text", [
    "0", "-1", "65536", "99999",
    "not a number", "", "  ", "5432a", "5.5",
])
def test_parse_port_rejects_invalid_or_out_of_range(text):
    assert parse_port(text) is None
