"""Modal — deploy scheduled + web functions. Mirror of ../deploy_app.py.

    modal deploy examples/modal/deploy_app.py

Same shape as the Herds version — `@app.function(schedule=...)` for cron,
`@app.function` you can trigger, a web endpoint with a URL. The difference is
where it all runs: Modal's cloud, not your Mac (and no Apple toolchain there).
"""

import modal

app = modal.App("nightly")


@app.function(schedule=modal.Cron("0 3 * * *"))
def nightly_report() -> dict:
    import platform
    import datetime
    return {"host": platform.node(), "at": datetime.datetime.now().isoformat()}


@app.function()
def build(target: str) -> str:
    return f"built {target}"


@app.function()
@modal.fastapi_endpoint()
def status():
    return "ok"
