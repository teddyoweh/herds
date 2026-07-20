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

_RESULT_MARKER = "__HERDS_RESULT__"
_ERROR_MARKER = "__HERDS_ERROR__"


class RemoteExecutionError(RuntimeError):
    pass


def _driver_source(fn: Callable) -> str:
    try:
        src = textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError) as exc:  # -c, REPL, exec, lambdas have no readable source
        raise RemoteExecutionError(
            f"can't read the source of {getattr(fn, '__name__', fn)!r} to ship it — "
            "define @app.function in a .py file (not a REPL, `python -c`, or a lambda)."
        ) from exc
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
        schedule: Optional[str] = None,
        port: Optional[int] = None,
    ):
        self.fn = fn
        self.app = app
        self.machine = machine
        self.image = image if image is not None else Image.python("3.13")
        self.volumes = volumes
        self.timeout = timeout
        self.schedule = schedule
        self.port = port           # set → this function is a web endpoint (a server)
        self.__name__ = fn.__name__

    @property
    def kind(self) -> str:
        if self.port:
            return "web"
        return "scheduled" if self.schedule else "function"

    def _driver(self) -> str:
        """The full, self-contained script this function ships to the Mac —
        arg-independent, so deploy can store it and a trigger just appends args."""
        return _DRIVER_TEMPLATE.format(
            body=_driver_source(self.fn),
            fn_name=self.fn.__name__,
            marker=_RESULT_MARKER,
            err_marker=_ERROR_MARKER,
        )

    # Calling the wrapped object directly == running locally (like Modal).
    def __call__(self, *args, **kwargs) -> Any:
        return self.fn(*args, **kwargs)

    def local(self, *args, **kwargs) -> Any:
        return self.fn(*args, **kwargs)

    def remote(self, *args, **kwargs) -> Any:
        m = get_mac(self.machine)
        driver = self._driver()
        payload = json.dumps({"args": list(args), "kwargs": kwargs})
        result = m.run(
            ["python3", "-c", driver, payload],
            image=self.image,
            volumes=self.volumes,
            timeout=self.timeout,
            app=self.app.name,   # group this run under its App
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
    def __init__(self, name: str = "herds-app", *, image: Union[Image, str, None] = None):
        self.name = name
        self.image = image
        self.functions: dict[str, Function] = {}
        self._entrypoint: Optional[Callable] = None

    @classmethod
    def lookup(cls, name: str, *, create_if_missing: bool = True,
               image: Union[Image, str, None] = None) -> "App":
        """Get a handle to an app by name, registering it on the control plane
        if it doesn't exist yet — the zero-config, Modal-style entry point::

            app = herds.App.lookup("my-builds")
            app.function(build).remote("release")
        """
        app = cls(name, image=image)
        if create_if_missing:
            from .client import default_client
            try:
                default_client()._http.post("/v1/apps", json={"name": name})
            except Exception:  # noqa: BLE001 — registration is best-effort; runs still stamp it
                pass
        return app

    def function(
        self,
        *,
        machine: str = "default",
        image: Union[Image, str, None] = None,
        volumes: Optional[dict] = None,
        timeout: Optional[int] = None,
        schedule: Optional[str] = None,
    ) -> Callable[[Callable], Function]:
        """Register a function. ``schedule="*/5 * * * *"`` (cron) makes ``deploy()``
        run it on that cadence, on the Mac, without your laptop."""
        def decorator(fn: Callable) -> Function:
            wrapped = Function(
                fn, self,
                machine=machine,
                image=image if image is not None else self.image,
                volumes=volumes,
                timeout=timeout,
                schedule=schedule,
            )
            self.functions[fn.__name__] = wrapped
            return wrapped

        return decorator

    def web_endpoint(
        self,
        *,
        port: int,
        machine: str = "default",
        image: Union[Image, str, None] = None,
        volumes: Optional[dict] = None,
    ) -> Callable[[Callable], Function]:
        """Register a function that starts a server on ``port``. ``deploy()`` runs
        it as a keep-alive sandbox and exposes ``port`` as a public URL::

            @app.web_endpoint(port=8000)
            def api():
                import http.server, socketserver
                socketserver.TCPServer(("", 8000), http.server.SimpleHTTPRequestHandler).serve_forever()

        The function should bind ``port`` and block (serve). The URL appears on the
        app's dashboard page after deploy.
        """
        def decorator(fn: Callable) -> Function:
            wrapped = Function(
                fn, self, machine=machine,
                image=image if image is not None else self.image,
                volumes=volumes, port=port,
            )
            self.functions[fn.__name__] = wrapped
            return wrapped

        return decorator

    def deploy(self) -> "App":
        """Persist this app's functions on the control plane so they can run
        without the client alive — trigger them over the API or (with a
        ``schedule=``) let the control plane fire them on cron. Modal's
        ``modal deploy``, for your Mac::

            app = herds.App("nightly")
            @app.function(schedule="0 3 * * *")
            def report(): ...
            app.deploy()
        """
        from .client import default_client, HerdsError

        c = default_client()
        c._http.post("/v1/apps", json={"name": self.name})
        for fn in self.functions.values():
            image = fn.image.name if isinstance(fn.image, Image) else fn.image
            r = c._http.post(
                f"/v1/apps/{self.name}/functions",
                json={
                    "name": fn.__name__,
                    "source": fn._driver(),
                    "image": image,
                    "schedule": fn.schedule,
                    "kind": fn.kind,
                    "port": fn.port,
                },
            )
            if r.status_code >= 400:
                raise HerdsError(f"deploy of {fn.__name__} failed: {r.text}")
        return self

    def function_names(self) -> list[str]:
        return list(self.functions)

    def local_entrypoint(self) -> Callable[[Callable], Callable]:
        def decorator(fn: Callable) -> Callable:
            self._entrypoint = fn
            return fn

        return decorator

    def run_entrypoint(self, *args, **kwargs) -> Any:
        if self._entrypoint is None:
            raise RuntimeError("no @app.local_entrypoint() defined")
        return self._entrypoint(*args, **kwargs)
