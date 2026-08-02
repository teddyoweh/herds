"""One token to join a Mac, instead of a link and a token in the right order.

The endpoint was never a second secret — it's just where the token is valid. So
it travels inside the token, shaped like ``user@host``:

    herds_sk_mqoa56xOPbW1WUex9EC2rBMFv0CMyEwA@you.relay.herds.run

Readable on purpose. An opaque blob that silently points a Mac at someone
else's relay is a real risk; you can read this one before you paste it.
"""

from __future__ import annotations

import pytest

from herds import config


def test_roundtrip():
    packed = config.join_token("herds_sk_abc", "https://you.relay.herds.run")
    assert packed == "herds_sk_abc@you.relay.herds.run"
    assert config.split_token(packed) == ("herds_sk_abc", "https://you.relay.herds.run")


def test_join_strips_scheme_and_trailing_slash():
    assert config.join_token("t", "https://a.b/") == "t@a.b"
    assert config.join_token("t", "http://a.b") == "t@a.b"


def test_bare_token_leaves_url_unresolved():
    """No '@' means fall back to config/env, exactly as before."""
    assert config.split_token("herds_sk_plain") == ("herds_sk_plain", None)


@pytest.mark.parametrize("host,expected", [
    ("you.relay.herds.run", "https://you.relay.herds.run"),
    ("localhost:8787", "http://localhost:8787"),
    ("127.0.0.1:8787", "http://127.0.0.1:8787"),
    ("0.0.0.0:9000", "http://0.0.0.0:9000"),
])
def test_scheme_inference(host, expected):
    assert config.split_token(f"tok@{host}") == ("tok", expected)


def test_never_downgrades_a_real_host_off_tls():
    """Anything not loopback must resolve to https — a token is a credential."""
    for host in ("example.com", "a.relay.herds.run", "10.0.0.5", "myhost:8787"):
        _, url = config.split_token(f"tok@{host}")
        assert url.startswith("https://"), f"{host} was downgraded to plaintext"


def test_explicit_scheme_is_respected():
    assert config.split_token("tok@http://box.local:8787") == ("tok", "http://box.local:8787")
    assert config.split_token("tok@https://x.io") == ("tok", "https://x.io")


def test_token_containing_at_uses_the_last_one():
    """Secrets are urlsafe-base64 so this is defensive, not expected."""
    assert config.split_token("we@ird@host.tld") == ("we@ird", "https://host.tld")


@pytest.mark.parametrize("bad", ["", "   ", "@", "@host.tld", "tok@"])
def test_malformed_input_degrades_to_a_bare_token(bad):
    """Never raise while parsing a credential — fall back to old behaviour."""
    token, url = config.split_token(bad)
    assert url is None or isinstance(url, str)


def test_whitespace_is_tolerated():
    assert config.split_token("  tok@host.tld  ") == ("tok", "https://host.tld")


def test_cli_connect_takes_one_argument():
    """The signature is the feature: `herds connect <token>` must be valid."""
    import inspect

    from herds.cli import connect

    params = inspect.signature(connect).parameters
    assert "token" in params
    # The legacy second positional must still exist so old commands keep working.
    assert "legacy_token" in params


def test_install_script_handles_both_forms():
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "web" / "public" / "install"
    body = script.read_text()
    assert 'exec "$HERDS" connect "$1"\n' in body, "single-token form missing"
    assert 'exec "$HERDS" connect "$1" "$2"' in body, "legacy form must keep working"
