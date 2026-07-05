"""Provider abstraction: something that yields a reachable regional VM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """Raised for provider configuration or backend failures."""


@dataclass
class VMInfo:
    host: str
    user: str
    key_path: str | None = None
    password: str | None = None


class Provider(ABC):
    name = "base"

    @classmethod
    @abstractmethod
    def from_options(cls, options: dict) -> Provider:
        """Build a provider instance from a region's config options."""

    @abstractmethod
    def ensure_running(self) -> VMInfo:
        """Make sure a VM exists and is running; return how to reach it."""

    def deallocate(self) -> None:
        raise ProviderError(f"The '{self.name}' provider does not support deallocate().")

    def destroy(self) -> None:
        raise ProviderError(f"The '{self.name}' provider does not support destroy().")

    def status(self) -> str:
        return "unknown"
