"""Modal — the mirror of ../ios_build.py that can't exist.

Modal runs Linux containers. There is no macOS, no Xcode, no `xcodebuild`, no
Swift toolchain, no iOS simulator. Apple's licensing forbids macOS on rented
cloud hardware, so this file has nothing to run.

That's the whole reason Herds exists: your Mac is already licensed macOS — Herds
just puts it on the internet. Run ../ios_build.py instead.
"""

raise SystemExit("Modal can't build for Apple platforms — it has no macOS. Use Herds: examples/ios_build.py")
