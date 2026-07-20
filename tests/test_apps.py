"""Apps: store rollups + the /v1/apps control-plane endpoints."""

from fastapi.testclient import TestClient

from herds.control import create_app
from herds.control.store import Store


def test_store_app_rollup_counts():
    s = Store(":memory:")
    s.upsert_app("demo", "local", 1000, description="builds")
    s.create_job("req_1", "mac_1", "echo hi", 1000, app="demo")
    s.create_job("req_2", "mac_1", "echo bye", 1001, app="demo")
    s.create_job("req_3", "mac_1", "unrelated", 1002)  # no app
    s.touch_sandbox("sbx_1", "mac_1", None, 1003, app="demo")

    apps = s.list_apps("local")
    assert len(apps) == 1
    a = apps[0]
    assert a["name"] == "demo"
    assert a["job_count"] == 2          # only the two stamped jobs
    assert a["sandbox_count"] == 1
    # Filtered listing groups correctly.
    assert {j["request_id"] for j in s.list_jobs(app="demo")} == {"req_1", "req_2"}


def test_store_migration_idempotent():
    # Re-opening a DB path must not fail re-running the ALTER migrations.
    Store(":memory:")
    s = Store(":memory:")
    s._ensure_app_columns()  # no-op the second time
    s.upsert_app("x", "local", 1)
    assert s.get_app("x", "local")["name"] == "x"


def test_apps_endpoints_crud_and_grouping():
    app = create_app(":memory:")
    c = TestClient(app)

    assert c.get("/v1/apps").json() == {"apps": []}

    made = c.post("/v1/apps", json={"name": "demo", "description": "builds"}).json()
    assert made["name"] == "demo" and made["owner"] == "local"

    listed = c.get("/v1/apps").json()["apps"]
    assert listed[0]["name"] == "demo" and listed[0]["job_count"] == 0

    detail = c.get("/v1/apps/demo").json()
    assert detail["app"]["name"] == "demo"
    assert detail["jobs"] == [] and detail["functions"] == []

    assert c.get("/v1/apps/missing").status_code == 404

    assert c.delete("/v1/apps/demo").json() == {"deleted": "demo"}
    assert c.get("/v1/apps").json() == {"apps": []}


def test_deploy_function_and_schedule_row():
    app = create_app(":memory:")
    c = TestClient(app)

    # A scheduled function: deploy stores it AND creates a cron row.
    r = c.post("/v1/apps/nightly/functions", json={
        "name": "report",
        "source": "def report():\n    return 42\n",
        "schedule": "0 3 * * *",
        "kind": "scheduled",
    })
    body = r.json()
    assert body["ok"] is True and body["function"] == "report"

    detail = c.get("/v1/apps/nightly").json()
    assert detail["app"]["deployed_ms"]  # marked deployed
    assert detail["functions"][0]["name"] == "report"
    assert detail["functions"][0]["schedule"] == "0 3 * * *"

    scheds = c.get("/v1/schedules").json()["schedules"]
    assert len(scheds) == 1
    assert scheds[0]["cron"] == "0 3 * * *"
    assert "__herds_app__" in scheds[0]["command"]


def test_trigger_missing_function_404():
    app = create_app(":memory:")
    c = TestClient(app)
    c.post("/v1/apps", json={"name": "demo"})
    assert c.post("/v1/apps/demo/functions/nope", json={"args": []}).status_code == 404


def test_web_endpoint_stored_without_machine():
    # No machine online: deploy still succeeds, function is stored with its port,
    # url stays null (endpoint couldn't boot). Doesn't raise.
    app = create_app(":memory:")
    c = TestClient(app)
    r = c.post("/v1/apps/site/functions", json={
        "name": "api",
        "source": "def api():\n    pass\n",
        "kind": "web",
        "port": 8000,
    })
    assert r.json()["ok"] is True and r.json()["url"] is None
    fn = c.get("/v1/apps/site").json()["functions"][0]
    assert fn["kind"] == "web" and fn["port"] == 8000 and fn["url"] is None
