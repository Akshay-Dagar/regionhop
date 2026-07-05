"""Configuration loading for regionhop.

Config is TOML. Search order:
  1. path passed on the CLI (``--config``)
  2. ``$REGIONHOP_CONFIG``
  3. ``./regionhop.toml``
  4. ``$XDG_CONFIG_HOME/regionhop/config.toml`` (``~/.config/...`` by default)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PORT = 1080


class ConfigError(Exception):
    """Raised for any user-facing configuration problem."""


@dataclass
class RegionConfig:
    name: str
    provider: str
    options: dict = field(default_factory=dict)
    local_port: int = DEFAULT_PORT


@dataclass
class Config:
    regions: dict[str, RegionConfig] = field(default_factory=dict)
    default_region: str | None = None
    path: Path | None = None

    def region(self, name: str | None) -> RegionConfig:
        name = name or self.default_region
        if not name:
            raise ConfigError("No region given and no 'default_region' is set.")
        if name not in self.regions:
            known = ", ".join(self.regions) or "(none configured)"
            raise ConfigError(f"Unknown region '{name}'. Known regions: {known}")
        return self.regions[name]


def _search_paths() -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("REGIONHOP_CONFIG")
    if env:
        paths.append(Path(env))
    paths.append(Path.cwd() / "regionhop.toml")
    paths.append(default_config_path())
    return paths


def default_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "regionhop" / "config.toml"


def load(path: str | os.PathLike | None = None) -> Config:
    candidates = [Path(path)] if path else _search_paths()
    for p in candidates:
        if p and p.is_file():
            return _parse(p)
    raise ConfigError(
        "No config file found. Run 'regionhop setup' (or 'init'), "
        "or point REGIONHOP_CONFIG at your file."
    )


def find_config() -> Path | None:
    """Return the first existing config file in the search path, or None."""
    for p in _search_paths():
        if p and p.is_file():
            return p
    return None


def _parse(p: Path) -> Config:
    with open(p, "rb") as f:
        data = tomllib.load(f)

    regions: dict[str, RegionConfig] = {}
    for name, raw in (data.get("regions") or {}).items():
        if not isinstance(raw, dict):
            raise ConfigError(f"[regions.{name}] must be a table.")
        provider = raw.get("provider")
        if not provider:
            raise ConfigError(f"[regions.{name}] is missing 'provider'.")
        port = int(raw.get("local_port", DEFAULT_PORT))
        options = {k: v for k, v in raw.items() if k not in {"provider", "local_port"}}
        regions[name] = RegionConfig(name=name, provider=provider, options=options, local_port=port)

    return Config(regions=regions, default_region=data.get("default_region"), path=p)


EXAMPLE_CONFIG = """\
# regionhop configuration.
# Copy to  ~/.config/regionhop/config.toml  (or ./regionhop.toml) and edit.

default_region = "br"

# --- Bring your own VM (simplest; you manage the VM lifecycle) ---
[regions.br]
provider = "manual"
host = "203.0.113.10"              # your VM's public IP
user = "azureuser"                # SSH username
key_path = "~/.ssh/id_ed25519_br" # private key for passwordless SSH
local_port = 1080                 # local SOCKS5 port

# --- Azure-managed VM (regionhop creates/starts/stops it via the az CLI) ---
# Requires the Azure CLI (`az login`).
# [regions.jp]
# provider = "azure"
# resource_group = "regionhop-jp"
# name = "rh-jp"
# location = "japaneast"
# user = "azureuser"
# size = "Standard_B1s"
# image = "Ubuntu2204"
# ssh_public_key_path = "~/.ssh/id_ed25519_br.pub"
# key_path = "~/.ssh/id_ed25519_br"
# local_port = 1081
"""


def init(path: str | os.PathLike | None = None) -> Path:
    target = Path(path) if path else default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ConfigError(f"Config already exists at {target}")
    target.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    return target


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def dumps(cfg: Config) -> str:
    """Serialize a Config back into TOML text."""
    lines: list[str] = []
    if cfg.default_region:
        lines.append(f'default_region = "{cfg.default_region}"')
        lines.append("")
    for name, region in cfg.regions.items():
        lines.append(f"[regions.{name}]")
        lines.append(f'provider = "{region.provider}"')
        for key, value in region.options.items():
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append(f"local_port = {region.local_port}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save(cfg: Config, path: str | os.PathLike | None = None) -> Path:
    """Write a Config to disk as TOML and return the path."""
    target = Path(path) if path else (cfg.path or default_config_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps(cfg), encoding="utf-8")
    return target
