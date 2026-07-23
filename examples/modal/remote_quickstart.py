"""Modal — run · volume · sandbox. Mirror of ../remote_quickstart.py.

    modal run examples/modal/remote_quickstart.py

Same App / Volume / Sandbox mental model — on Modal's Linux, not your Mac.
"""

import modal

app = modal.App.lookup("demo", create_if_missing=True)
vol = modal.Volume.from_name("demo-cache", create_if_missing=True)

sb = modal.Sandbox.create(app=app, volumes={"/cache": vol})

# Run a command.
print(sb.exec("cat", "/etc/os-release").stdout.read().strip())

# Volume — persists across runs.
sb.exec("bash", "-c", "echo 1.2.3 > /cache/version.txt")
print(sb.exec("cat", "/cache/version.txt").stdout.read().strip())

sb.terminate()
