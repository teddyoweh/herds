"""Modal — the same @function → .remote() the Herds example mirrors.

    modal run examples/modal/remote_function.py

Same shape as ../remote_function.py — but it runs on Modal's rented Linux, not
your Mac.
"""

import modal

app = modal.App("remote-demo")


@app.function(image=modal.Image.debian_slim())
def system_report(label: str) -> dict:
    import platform
    return {"label": label, "ran_on": platform.node(), "machine": platform.machine()}


@app.function()
def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@app.local_entrypoint()
def main():
    print("remote ->", system_report.remote("from-cloud"))
    print("fib(20) ->", fib.remote(20))
