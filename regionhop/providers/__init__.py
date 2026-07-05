"""Provider registry."""

from __future__ import annotations

from ..config import RegionConfig
from .azure import AzureProvider
from .base import Provider, ProviderError, VMInfo
from .manual import ManualProvider

_REGISTRY: dict[str, type[Provider]] = {
    "manual": ManualProvider,
    "azure": AzureProvider,
}


def get_provider(region: RegionConfig) -> Provider:
    cls = _REGISTRY.get(region.provider)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ProviderError(
            f"Unknown provider '{region.provider}'. Available: {available}"
        )
    return cls.from_options(region.options)


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


__all__ = [
    "Provider",
    "ProviderError",
    "VMInfo",
    "get_provider",
    "available_providers",
]
