"""``Secret`` -- named key/value secrets stored in the control plane.

Secrets are created in the dashboard or via :meth:`Secret.create`, and attached
to a run or sandbox by name. The control plane resolves the name to its values
and injects them as environment variables at dispatch time -- the Mac daemon
never stores secret material.

    s = dc.Secret.create("openai", {"OPENAI_API_KEY": "sk-..."})
    mac.run("python agent.py", secrets=[s])           # or secrets=["openai"]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .client import HerdsClient, HerdsError, default_client


@dataclass(frozen=True)
class Secret:
    name: str

    @staticmethod
    def from_name(name: str) -> "Secret":
        return Secret(name=name)

    @staticmethod
    def create(
        name: str, values: dict[str, str], *, client: Optional[HerdsClient] = None
    ) -> "Secret":
        c = client or default_client()
        r = c._http.post("/v1/secrets", json={"name": name, "values": values})
        if r.status_code >= 400:
            raise HerdsError(r.json().get("detail", r.text))
        return Secret(name=name)

    @staticmethod
    def list(client: Optional[HerdsClient] = None) -> list[dict]:
        c = client or default_client()
        r = c._http.get("/v1/secrets")
        r.raise_for_status()
        return r.json()["secrets"]

    def __repr__(self) -> str:
        return f"Secret({self.name!r})"
