from herds.control.store import Store
from herds.daemon import images
from herds.protocol import JobState, MachineStatus


def test_store_machine_lifecycle():
    s = Store(":memory:")
    s.upsert_machine("mac_1", "MBP", "local", {"chip": "M4"}, MachineStatus.ONLINE, 123)
    machines = s.list_machines()
    assert len(machines) == 1
    assert machines[0]["machine_id"] == "mac_1"
    assert machines[0]["status"] == "online"
    s.set_machine_status("mac_1", MachineStatus.OFFLINE, 456)
    assert s.get_machine("mac_1")["status"] == "offline"


def test_store_api_keys_and_tokens():
    s = Store(":memory:")
    key = s.create_api_key("alice", "laptop")
    assert s.owner_for_api_key(key) == "alice"
    assert s.owner_for_api_key("bogus") is None
    tok = s.create_device_token("mac_9", "alice")
    info = s.device_token_info(tok)
    assert info == {"machine_id": "mac_9", "owner": "alice"}


def test_store_jobs():
    s = Store(":memory:")
    s.create_job("req_1", "mac_1", "echo hi", 1000)
    s.update_job("req_1", JobState.SUCCEEDED, exit_code=0, duration_ms=5)
    jobs = s.list_jobs()
    assert jobs[0]["state"] == "succeeded"
    assert jobs[0]["exit_code"] == 0


def test_image_resolution_names():
    r = images.resolve("xcode:26")
    assert any("xcode" in n for n in r.notes)

    r2 = images.resolve(None)
    assert r2.env == {}

    r3 = images.resolve("node:22")
    assert any("node" in n for n in r3.notes)

    r4 = images.resolve("totally-unknown")
    assert any("unknown" in n for n in r4.notes)
