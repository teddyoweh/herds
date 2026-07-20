"""Device metadata: device_type classification + battery sampling."""

from herds.daemon import machine, metrics
from herds.protocol import MachineInfo


def test_sample_includes_battery_keys():
    s = metrics.sample()
    for k in ("cpu", "mem", "load1", "battery_pct", "battery_charging"):
        assert k in s, f"metrics.sample() missing {k}"
    # battery_pct is a float on laptops or None on desktops — never a crash.
    assert s["battery_pct"] is None or isinstance(s["battery_pct"], float)
    assert s["battery_charging"] is None or isinstance(s["battery_charging"], bool)


def test_device_type_classification():
    dt = machine._device_type
    assert dt("MacBook Pro", "Mac15,3") == "macbook_pro"
    assert dt("MacBook Air", "Mac14,2") == "macbook_air"
    assert dt("Mac mini", "Macmini9,1") == "mac_mini"
    assert dt("Mac Studio", "Mac13,1") == "mac_studio"
    assert dt("Mac Pro", "MacPro7,1") == "mac_pro"
    assert dt("iMac", "iMac21,1") == "imac"
    # Falls back to the identifier when the marketing name is absent.
    assert dt(None, "MacBookPro18,3") == "macbook_pro"
    assert dt(None, "Macmini9,1") == "mac_mini"
    # Unknown → None (UI shows a generic glyph).
    assert dt(None, "Mac99,9") is None
    assert dt(None, None) is None


def test_pretty_name_prefers_model_name_then_identifier():
    # Marketing name wins.
    assert machine._pretty_name("MacBook Pro", "Mac15,3", "Apple M4") == "MacBook Pro (Apple M4)"
    # Identifier fallback classifies when no marketing name.
    assert machine._pretty_name(None, "Macmini9,1", "Apple M2") == "Mac mini (Apple M2)"
    # No chip → bare base.
    assert machine._pretty_name("Mac Studio", "Mac13,1", None) == "Mac Studio"


def test_machineinfo_accepts_device_type():
    info = MachineInfo(machine_id="mac_x", name="MacBook Pro", model="Mac15,3",
                       device_type="macbook_pro", chip="Apple M4")
    assert info.device_type == "macbook_pro"
    # Round-trips through the wire model.
    assert MachineInfo.model_validate(info.model_dump()).device_type == "macbook_pro"
