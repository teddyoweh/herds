"""A real Apple-toolchain workflow on a Mac that could be anywhere.

Inspects Xcode, spins up a throwaway Swift package in a sandbox, builds it, and
runs it — a genuine native build on real macOS, driven over the relay.

    python examples/ios_build.py

Point it at your own project by setting HERDS_XCODE_PROJECT.
"""

import os

import herds

mac = herds.mac(url="https://you.herds.run", token="hx_...")   # from `herds host`

# Everything here groups under the "ios-build" App in the dashboard.
print(mac.run("xcodebuild -version", app="ios-build").stdout.strip())
print(mac.run("xcrun simctl list devices available | grep -c iPhone", app="ios-build").stdout.strip(), "iPhone simulators")

project = os.environ.get("HERDS_XCODE_PROJECT")

with herds.Sandbox.create(mac=mac, inherit_home=True, app="ios-build") as sbx:
    if project:
        sbx.put(project)
        print(sbx.exec("xcodebuild -list", timeout=120).stdout.strip())
        sbx.exec("xcodebuild -scheme App build", stream=True, timeout=1200)
    else:
        sbx.exec("mkdir Demo && cd Demo && swift package init --type executable", timeout=120)
        sbx.exec("cd Demo && swift build", stream=True, timeout=600)
        print(sbx.exec("cd Demo && swift run", timeout=120).stdout.strip())
