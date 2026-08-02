"""Precise mouse/scroll input for a remote Mac, with no dependencies on the Mac.

macOS stopped shipping PyObjC with the system interpreter, so ``import Quartz``
is not available on a stock Mac. But CoreGraphics is a plain C framework, and
``ctypes`` is stdlib — so we drive real CGEvents by loading the framework
directly. The payload below is executed with ``/usr/bin/python3`` (present on
every Mac since 10.15, currently 3.9.6), which is why it must stay 3.9-clean.

AppleScript's ``System Events`` can *type*, but it cannot move or click a mouse
at a coordinate. This closes that hole: real HID-level events that behave
exactly like a physical mouse, including drag and momentum-free scrolling.
"""

from __future__ import annotations

# Executed via `/usr/bin/python3 -c SCRIPT <action> <args...>` on the Mac.
# Self-contained on purpose: it must run whether herds was installed via uv
# tool, pipx or pip, none of which put `herds` on the system interpreter's path.
SCRIPT = r'''
import ctypes, sys, time

CG = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

CG.CGEventCreate.restype = ctypes.c_void_p
CG.CGEventCreate.argtypes = [ctypes.c_void_p]
CG.CGEventGetLocation.restype = CGPoint
CG.CGEventGetLocation.argtypes = [ctypes.c_void_p]
CG.CGEventCreateMouseEvent.restype = ctypes.c_void_p
CG.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
CG.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
CG.CGEventCreateScrollWheelEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                             ctypes.c_int32, ctypes.c_int32]
CG.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
CG.CGEventSetIntegerValueField.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int64]
CG.CFRelease.argtypes = [ctypes.c_void_p]
CG.CGMainDisplayID.restype = ctypes.c_uint32
CG.CGDisplayPixelsWide.restype = ctypes.c_size_t
CG.CGDisplayPixelsWide.argtypes = [ctypes.c_uint32]
CG.CGDisplayPixelsHigh.restype = ctypes.c_size_t
CG.CGDisplayPixelsHigh.argtypes = [ctypes.c_uint32]

TAP = 0                    # kCGHIDEventTap — inject as though from hardware
MOVED, DRAGGED = 5, 6
DOWN = {"left": 1, "right": 3, "center": 25}
UP = {"left": 2, "right": 4, "center": 26}
BTN = {"left": 0, "right": 1, "center": 2}
SCROLL, CLICK_STATE = 22, 1
UNIT_PIXEL = 0

def _post(ev):
    CG.CGEventPost(TAP, ev)
    CG.CFRelease(ev)

def cursor():
    ev = CG.CGEventCreate(None)
    p = CG.CGEventGetLocation(ev)
    CG.CFRelease(ev)
    return p.x, p.y

def move(x, y):
    _post(CG.CGEventCreateMouseEvent(None, MOVED, CGPoint(x, y), 0))

def click(x, y, button="left", count=1):
    move(x, y)
    time.sleep(0.01)          # let the UI register hover before the press
    pt = CGPoint(x, y)
    for i in range(1, count + 1):
        for kind in (DOWN[button], UP[button]):
            ev = CG.CGEventCreateMouseEvent(None, kind, pt, BTN[button])
            # Click-state is what distinguishes a double-click from two clicks.
            CG.CGEventSetIntegerValueField(ev, CLICK_STATE, i)
            _post(ev)
        time.sleep(0.02)

def drag(x1, y1, x2, y2, button="left", steps=24):
    move(x1, y1)
    time.sleep(0.02)
    _post(CG.CGEventCreateMouseEvent(None, DOWN[button], CGPoint(x1, y1), BTN[button]))
    # Interpolate: a single jump reads as a teleport and many targets ignore it.
    for i in range(1, steps + 1):
        t = i / float(steps)
        _post(CG.CGEventCreateMouseEvent(
            None, DRAGGED, CGPoint(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t), BTN[button]))
        time.sleep(0.008)
    _post(CG.CGEventCreateMouseEvent(None, UP[button], CGPoint(x2, y2), BTN[button]))

def scroll(dy, dx=0):
    _post(CG.CGEventCreateScrollWheelEvent(None, UNIT_PIXEL, 2, int(dy), int(dx)))

def screen():
    d = CG.CGMainDisplayID()
    return CG.CGDisplayPixelsWide(d), CG.CGDisplayPixelsHigh(d)

a = sys.argv[1:]
op = a[0]
if op == "cursor":
    print("%d %d" % cursor())
elif op == "screen":
    print("%d %d" % screen())
elif op == "move":
    move(float(a[1]), float(a[2]))
elif op == "click":
    click(float(a[1]), float(a[2]), a[3] if len(a) > 3 else "left",
          int(a[4]) if len(a) > 4 else 1)
elif op == "drag":
    drag(float(a[1]), float(a[2]), float(a[3]), float(a[4]),
         a[5] if len(a) > 5 else "left")
elif op == "scroll":
    scroll(float(a[1]), float(a[2]) if len(a) > 2 else 0)
else:
    sys.stderr.write("unknown op %s\n" % op)
    sys.exit(2)
'''


def command(op: str, *args) -> list:
    """argv that performs ``op`` on the Mac using its own system interpreter."""
    return ["/usr/bin/python3", "-c", SCRIPT, op, *[str(a) for a in args]]


# Accessibility tree via the AX C API.
#
# The obvious implementation is AppleScript ("tell application \"System
# Events\"..."), and that is what herds used. It cannot work from a
# launchd-managed daemon: sending an AppleEvent requires an Automation TCC
# grant, the consent prompt can only be shown to a foreground app, and a
# headless daemon therefore *blocks until the event times out* rather than
# failing. Measured: `osascript -e "return 1+1"` returns in 72ms from the
# daemon; the same call wrapped in `tell application "System Events"` hangs.
#
# AXUIElement is a plain C API gated on Accessibility only — no AppleEvent, no
# Automation, no prompt. Same data, and it actually works headless.
AX_SCRIPT = r'''
import ctypes, subprocess, sys

CF = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
AX = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")

UTF8 = 0x08000100
CF.CFStringCreateWithCString.restype = ctypes.c_void_p
CF.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
CF.CFStringGetCString.restype = ctypes.c_bool
CF.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
CF.CFGetTypeID.restype = ctypes.c_ulong
CF.CFGetTypeID.argtypes = [ctypes.c_void_p]
CF.CFStringGetTypeID.restype = ctypes.c_ulong
CF.CFArrayGetTypeID.restype = ctypes.c_ulong
CF.CFArrayGetCount.restype = ctypes.c_long
CF.CFArrayGetCount.argtypes = [ctypes.c_void_p]
CF.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
CF.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
CF.CFRelease.argtypes = [ctypes.c_void_p]

AX.AXUIElementCreateApplication.restype = ctypes.c_void_p
AX.AXUIElementCreateApplication.argtypes = [ctypes.c_int]
AX.AXUIElementCopyAttributeValue.restype = ctypes.c_int
AX.AXUIElementCopyAttributeValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                             ctypes.POINTER(ctypes.c_void_p)]
AX.AXValueGetValue.restype = ctypes.c_bool
AX.AXValueGetValue.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
AX.AXValueGetTypeID.restype = ctypes.c_ulong
AX.AXIsProcessTrusted.restype = ctypes.c_bool
AX.AXUIElementPerformAction.restype = ctypes.c_int
AX.AXUIElementPerformAction.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]
class CGSize(ctypes.Structure):
    _fields_ = [("w", ctypes.c_double), ("h", ctypes.c_double)]

def cfstr(t):
    return CF.CFStringCreateWithCString(None, t.encode("utf-8"), UTF8)

def pystr(ref):
    if not ref:
        return ""
    buf = ctypes.create_string_buffer(1024)
    if CF.CFStringGetCString(ref, buf, 1024, UTF8):
        return buf.value.decode("utf-8", "replace")
    return ""

def attr(el, name):
    out = ctypes.c_void_p()
    if AX.AXUIElementCopyAttributeValue(el, cfstr(name), ctypes.byref(out)) != 0:
        return None
    return out.value

def as_point(ref):
    p = CGPoint()
    return (p.x, p.y) if ref and AX.AXValueGetValue(ref, 1, ctypes.byref(p)) else None

def as_size(ref):
    s = CGSize()
    return (s.w, s.h) if ref and AX.AXValueGetValue(ref, 2, ctypes.byref(s)) else None

def label(el):
    for a in ("AXTitle", "AXDescription", "AXValue", "AXLabel", "AXHelp"):
        ref = attr(el, a)
        if ref and CF.CFGetTypeID(ref) == CF.CFStringGetTypeID():
            t = pystr(ref)
            if t:
                return t
    return ""

def pid_for(name):
    for flag in ("-x", "-f"):
        r = subprocess.run(["pgrep", flag, name], capture_output=True, text=True)
        if r.stdout.strip():
            return int(r.stdout.split()[0])
    raise SystemExit("no process matching %r" % name)

def walk(el, depth, max_depth, rows, limit):
    if depth > max_depth or len(rows) >= limit:
        return
    role = pystr(attr(el, "AXRole")) or "?"
    pos = as_point(attr(el, "AXPosition")) or (-1, -1)
    size = as_size(attr(el, "AXSize")) or (0, 0)
    rows.append("%d\t%s\t%s\t%d\t%d\t%d\t%d" % (
        depth, role, label(el).replace("\t", " ").replace("\n", " "),
        pos[0], pos[1], size[0], size[1]))
    kids = attr(el, "AXChildren")
    if kids and CF.CFGetTypeID(kids) == CF.CFArrayGetTypeID():
        for i in range(min(CF.CFArrayGetCount(kids), limit)):
            walk(CF.CFArrayGetValueAtIndex(kids, i), depth + 1, max_depth, rows, limit)

a = sys.argv[1:]
op = a[0]
if op == "trusted":
    print("1" if AX.AXIsProcessTrusted() else "0")
    raise SystemExit(0)

app = AX.AXUIElementCreateApplication(pid_for(a[1]))
if op == "windows":
    wins = attr(app, "AXWindows")
    n = CF.CFArrayGetCount(wins) if wins else 0
    for i in range(n):
        print("%d\t%s" % (i + 1, label(CF.CFArrayGetValueAtIndex(wins, i))))
elif op == "tree":
    which = a[2] if len(a) > 2 else "window"
    max_depth = int(a[3]) if len(a) > 3 else 12
    limit = int(a[4]) if len(a) > 4 else 4000
    rows = []
    if which == "menubar":
        root = attr(app, "AXMenuBar")
        if root:
            walk(root, 0, max_depth, rows, limit)
    else:
        wins = attr(app, "AXWindows")
        idx = int(which) - 1 if which.isdigit() else 0
        if wins and CF.CFArrayGetCount(wins) > idx:
            walk(CF.CFArrayGetValueAtIndex(wins, idx), 0, max_depth, rows, limit)
    sys.stdout.write("\n".join(rows))
else:
    sys.stderr.write("unknown ax op %s\n" % op)
    sys.exit(2)
'''


def ax_command(op: str, *args) -> list:
    """argv that queries the Mac's accessibility tree via the AX C API."""
    return ["/usr/bin/python3", "-c", AX_SCRIPT, op, *[str(a) for a in args]]


# Readiness probe, run ON the Mac inside the daemon's process tree.
#
# TCC grants are per-process, not per-user, so a probe that runs in the CLI on
# your laptop tells you nothing about whether the daemon can drive the GUI. The
# Accessibility check in particular must be AXIsProcessTrusted() -- System
# Events' `UI elements enabled` is a global flag that reports true even when
# this process is untrusted and every synthetic event is silently dropped.
DOCTOR_SCRIPT = r'''
import ctypes, json, os, subprocess, sys, tempfile

def sh(args, timeout=10):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None

res = {}

AX = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
AX.AXIsProcessTrusted.restype = ctypes.c_bool
res["accessibility"] = bool(AX.AXIsProcessTrusted())

shot = os.path.join(tempfile.gettempdir(), "herds_doctor.png")
r = sh(["screencapture", "-x", shot])
res["screen_recording"] = bool(r and r.returncode == 0 and os.path.exists(shot)
                               and os.path.getsize(shot) > 5000)
try:
    os.remove(shot)
except OSError:
    pass

try:
    with open(os.path.expanduser("~/Library/Application Support/com.apple.TCC/TCC.db"), "rb") as fh:
        fh.read(16)
    res["full_disk_access"] = True
except Exception:
    res["full_disk_access"] = False

r = sh(["launchctl", "managername"])
res["gui_session"] = bool(r and "Aqua" in (r.stdout or ""))

# Automation: a bounded AppleEvent. From a daemon with no grant this BLOCKS
# rather than failing, so a timeout is the diagnosis, not an inconclusive result.
r = sh(["osascript", "-e", 'tell application "System Events" to return 1'], timeout=5)
res["automation"] = bool(r and r.returncode == 0 and (r.stdout or "").strip() == "1")

res["chrome"] = os.path.exists("/Applications/Google Chrome.app")
r = sh(["xcode-select", "-p"])
res["xcode"] = bool(r and r.returncode == 0 and (r.stdout or "").strip())

# The binary that actually needs the TCC grants: the daemon's real executable,
# not the `herds` shim and not the caller's terminal.
res["responsible_binary"] = os.path.realpath(sys.executable)
res["ppid_cmd"] = ""
r = sh(["ps", "-o", "comm=", "-p", str(os.getppid())])
if r:
    res["ppid_cmd"] = (r.stdout or "").strip()

print(json.dumps(res))
'''


def doctor_command() -> list:
    """argv that reports GUI/TCC readiness from inside the Mac's daemon tree."""
    return ["/usr/bin/python3", "-c", DOCTOR_SCRIPT]
