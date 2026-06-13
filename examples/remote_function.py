"""Run real Python on your Mac with the Modal-style decorator.

``.remote()`` ships this function's source to the Mac and runs it under the
target Python, returning the JSON-serializable result. Run this as a file (not
``python -c``) so the source is introspectable.

    herds serve            # terminal A
    herds connect          # terminal B
    python examples/remote_function.py
"""

import herds

app = herds.App("remote-demo")


@app.function(image=herds.Image.python("3.13"))
def system_report(label: str) -> dict:
    import platform
    import os
    return {
        "label": label,
        "ran_on": platform.node(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "cwd_is_sandbox": "herds/sandboxes" in os.getcwd(),
    }


@app.function()
def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@app.local_entrypoint()
def main():
    print("local  ->", system_report.local("from-laptop"))
    print("remote ->", system_report.remote("from-mac"))
    print("fib(20) on the Mac ->", fib.remote(20))


if __name__ == "__main__":
    app.run_entrypoint()
