"""Reporting *why* a control-plane call failed, without failing in the reporter.

`herds tags` against a relay whose host was down printed a JSONDecodeError
traceback instead of the reason. The error path did `r.json().get("detail")` on
a body the relay had written as plain text — so the handler for the failure
raised its own failure, and the actual message ("No Herds host is connected")
never reached the user.
"""

from __future__ import annotations

from typing import Optional

import httpx
import pytest

from herds.sdk.client import HerdsError, _raise_http, error_detail


def _resp(status: int, content: bytes, content_type: Optional[str] = None) -> httpx.Response:
    headers = {"content-type": content_type} if content_type else {}
    return httpx.Response(status_code=status, content=content, headers=headers,
                          request=httpx.Request("GET", "https://cp.example/v1/machines"))


def test_plain_text_relay_error_is_returned_verbatim():
    """The exact shape that produced the traceback."""
    r = _resp(502, b"No Herds host 'dev-elcruzo' is connected.", "text/plain; charset=utf-8")
    assert error_detail(r) == "No Herds host 'dev-elcruzo' is connected."


def test_json_detail_is_preferred():
    r = _resp(404, b'{"detail": "no such machine"}', "application/json")
    assert error_detail(r) == "no such machine"


def test_json_error_and_message_keys_also_understood():
    assert error_detail(_resp(400, b'{"error": "bad scope"}', "application/json")) == "bad scope"
    assert error_detail(_resp(400, b'{"message": "nope"}', "application/json")) == "nope"


def test_html_error_page_does_not_raise():
    r = _resp(504, b"<html><body>Gateway Timeout</body></html>", "text/html")
    assert "Gateway Timeout" in error_detail(r)


def test_malformed_body_labelled_json_still_survives():
    """Content-type is a hint, not a promise — the old guard trusted it."""
    r = _resp(500, b"<html>not json at all</html>", "application/json")
    out = error_detail(r)          # must not raise
    assert "not json" in out


def test_empty_body_falls_back_to_status():
    assert "503" in error_detail(_resp(503, b"", "text/plain"))


def test_non_dict_json_falls_back_to_text():
    r = _resp(400, b'["a", "b"]', "application/json")
    assert error_detail(r)          # some useful string, no crash


def test_json_dict_without_known_keys_falls_back_to_text():
    r = _resp(400, b'{"unexpected": 1}', "application/json")
    assert "unexpected" in error_detail(r)


def test_long_body_is_truncated():
    r = _resp(500, b"x" * 5000, "text/plain")
    out = error_detail(r)
    assert len(out) <= 401 and out.endswith("…")


# -- the CLI wrapper: a credential failure must name the door ---------------- #


def test_auth_failure_names_the_control_plane():
    """A good key at the wrong door is the characteristic failure, because
    `herds connect` and `herds host` write control_plane and api_key
    separately. A bare "missing API key" doesn't say which door was tried."""
    from herds.cli import _detail

    out = _detail(_resp(401, b'{"detail": "missing API key"}', "application/json"))
    assert "missing API key" in out
    assert "https://cp.example" in out


def test_forbidden_also_names_the_control_plane():
    from herds.cli import _detail

    assert "https://cp.example" in _detail(_resp(403, b'{"detail": "nope"}', "application/json"))


def test_non_auth_errors_are_not_cluttered_with_the_url():
    """404 or 502 is about the request, not the credential — keep it clean."""
    from herds.cli import _detail

    assert _detail(_resp(404, b'{"detail": "no such machine"}', "application/json")) == "no such machine"
    assert "cp.example" not in _detail(_resp(502, b"host down", "text/plain"))


# -- the SDK's raising wrapper, which shares the parser ---------------------- #


def test_relay_502_becomes_advice_not_a_status_code():
    with pytest.raises(HerdsError) as e:
        _raise_http(_resp(502, b"No Herds host 'x' is connected.", "text/plain"))
    assert "No Mac is connected" in str(e.value)
    assert "herds host" in str(e.value)


def test_no_herds_host_text_is_recognised_on_any_status():
    """The relay hasn't always used a 5xx for this."""
    with pytest.raises(HerdsError) as e:
        _raise_http(_resp(200, b"No Herds host is connected.", "text/plain"))
    assert "No Mac is connected" in str(e.value)


def test_auth_failures_name_the_token():
    for status in (401, 403):
        with pytest.raises(HerdsError) as e:
            _raise_http(_resp(status, b'{"detail": "missing API key"}', "application/json"))
        assert "missing API key" in str(e.value)
        assert "token" in str(e.value).lower()


def test_other_errors_surface_the_detail():
    with pytest.raises(HerdsError) as e:
        _raise_http(_resp(404, b'{"detail": "no such machine"}', "application/json"))
    assert str(e.value) == "no such machine"


def test_raise_http_never_raises_the_wrong_exception():
    """Whatever the body, the caller sees HerdsError — not a JSONDecodeError."""
    for body in (b"", b"<html/>", b"\xff\xfe", b"[]", b"plain words"):
        with pytest.raises(HerdsError):
            _raise_http(_resp(500, body, "application/json"))


def test_never_raises_across_shapes():
    """Whatever a proxy hands back, the reporter reports rather than raising."""
    bodies = [b"", b"   ", b"null", b"0", b"[]", b"{}", b"\xff\xfe binary",
              b"<html/>", b'{"detail": null}', b"just words"]
    for b in bodies:
        for ct in (None, "application/json", "text/plain", "text/html"):
            out = error_detail(_resp(500, b, ct))
            assert isinstance(out, str) and out, f"empty detail for {b!r} / {ct}"
