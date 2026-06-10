"""``App`` and ``@app.function`` -- the Modal-style decorator surface.

    app = dc.App("my-builds")

    @app.function(machine="default", image=dc.Image.python("3.13"))
    def build(target: str) -> dict:
        import platform
        return {"target": target, "ran_on": platform.node()}

    @app.local_entrypoint()
    def main():
        print(build.remote("release"))

``.remote()`` ships the function's *source* to the Mac and runs it under the
target Python, returning the (JSON-serializable) result. This works for
self-contained, module-level functions -- closures and non-importable globals
are out of scope (that's the documented limit; ``mac.run`` covers the rest).
``.local()`` just calls it in-process, like Modal.
"""

from __future__ import annotations

import inspect
import json
import textwrap
from typing import Any, Callable, Optional, Union

from .image import Image
from .mac import Mac, mac as get_mac

_RESULT_MARKER = "__DARWIN_RESULT__"
_ERROR_MARKER = "__DARWIN_ERROR__"


class RemoteExecutionError(RuntimeError):
    pass


def _driver_source(fn: Callable) -> str:
    src = textwrap.dedent(inspect.getsource(fn))
    # Strip the decorator lines so the bare function body remains.
    lines = src.splitlines()
    while lines and lines[0].lstrip().startswith("@"):
        lines.pop(0)
    body = "\n".join(lines)
    return body


_DRIVER_TEMPLATE = """\
import json, sys, traceback

{body}

if __name__ == "__main__":
    _payload = json.loads(sys.argv[1])
    try:
        _res = {fn_name}(*_payload["args"], **_payload["kwargs"])
        print("{marker}" + json.dumps(_res), flush=True)
    except Exception:
        print("{err_marker}" + traceback.format_exc(), file=sys.stderr, flush=True)
        sys.exit(17)
"""


class Function:
    def __init__(
        self,
        fn: Callable,
        app: "App",
        *,
        machine: str = "default",
        image: Union[Image, str, None] = None,
        volumes: Optional[dict] = None,
        timeout: Optional[int] = None,
    ):
        self.fn = fn
        self.app = app
        self.machine = machine
        self.image = image if image is not None else Image.python("3.13")
        self.volumes = volumes
        self.timeout = timeout
        self.__name__ = fn.__name__

    # Calling the wrapped object directly == running locally (like Modal).
    def __call__(self, *args, **kwargs) -> Any:
        return self.fn(*args, **kwargs)

    def local(self, *args, **kwargs) -> Any:
        return self.fn(*args, **kwargs)

    def remote(self, *args, **kwargs) -> Any:
        m = get_mac(self.machine)
        driver = _DRIVER_TEMPLATE.format(
            body=_driver_source(self.fn),
            fn_name=self.fn.__name__,
            marker=_RESULT_MARKER,
            err_marker=_ERROR_MARKER,
        )
        payload = json.dumps({"args": list(args), "kwargs": kwargs})
        result = m.run(
            ["python3", "-c", driver, payload],
            image=self.image,
            volumes=self.volumes,
            timeout=self.timeout,
        )
        if not result.ok:
            raise RemoteExecutionError(
                f"{self.__name__} failed on {self.machine} (exit {result.exit_code}):\n"
                f"{result.stderr.strip()}"
            )
        for line in result.stdout.splitlines():
            if line.startswith(_RESULT_MARKER):
                return json.loads(line[len(_RESULT_MARKER):])
        return None


class App:
    def __init__(self, name: str = "darwin-app", *, image: Union[Image, str, None] = None):
        self.name = name
        self.image = image
        self.functions: dict[str, Function] = {}
        self._entrypoint: Optional[Callable] = None

    def function(
        self,
        *,
        machine: str = "default",
        image: Union[Image, str, None] = None,
        volumes: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> Callable[[Callable], Function]:
        def decorator(fn: Callable) -> Function:
            wrapped = Function(
                fn, self,
                machine=machine,
                image=image if image is not None else self.image,
                volumes=volumes,
                timeout=timeout,
            )
            self.functions[fn.__name__] = wrapped
            return wrapped

        return decorator

    def local_entrypoint(self) -> Callable[[Callable], Callable]:
        def decorator(fn: Callable) -> Callable:
            self._entrypoint = fn
            return fn

        return decorator

    def run_entrypoint(self, *args, **kwargs) -> Any:
        if self._entrypoint is None:
            raise RuntimeError("no @app.local_entrypoint() defined")
        return self._entrypoint(*args, **kwargs)
