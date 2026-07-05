"""Manual provider: you created the VM, regionhop just uses it.

The simplest and most portable back-end -- works with any cloud or bare metal.
regionhop will not create, start, or stop the machine; you manage its lifecycle.
"""

from __future__ import annotations

from .base import Provider, ProviderError, VMInfo


class ManualProvider(Provider):
    name = "manual"

    def __init__(
        self,
        host: str,
        user: str,
        key_path: str | None = None,
        password: str | None = None,
    ):
        if not host or not user:
            raise ProviderError("The 'manual' provider requires 'host' and 'user'.")
        self.host = host
        self.user = user
        self.key_path = key_path
        self.password = password

    @classmethod
    def from_options(cls, options: dict) -> ManualProvider:
        return cls(
            host=options.get("host", ""),
            user=options.get("user", ""),
            key_path=options.get("key_path"),
            password=options.get("password"),
        )

    def ensure_running(self) -> VMInfo:
        return VMInfo(self.host, self.user, self.key_path, self.password)

    def deallocate(self) -> None:
        print("[manual] Unmanaged VM -- stop it yourself in your provider's console.")

    def destroy(self) -> None:
        print("[manual] Unmanaged VM -- delete it yourself in your provider's console.")

    def status(self) -> str:
        return f"manual {self.user}@{self.host} (unmanaged)"
