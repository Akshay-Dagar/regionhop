import textwrap

import pytest

from regionhop import config as cfgmod


def _write(tmp_path, body: str):
    p = tmp_path / "regionhop.toml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_parse_regions(tmp_path):
    path = _write(
        tmp_path,
        """
        default_region = "br"

        [regions.br]
        provider = "manual"
        host = "203.0.113.10"
        user = "azureuser"
        key_path = "~/.ssh/id_ed25519_br"
        local_port = 1080
        """,
    )
    cfg = cfgmod.load(path)
    assert cfg.default_region == "br"
    region = cfg.region(None)
    assert region.provider == "manual"
    assert region.options["host"] == "203.0.113.10"
    assert region.local_port == 1080


def test_default_port(tmp_path):
    path = _write(
        tmp_path,
        """
        [regions.us]
        provider = "manual"
        host = "x"
        user = "y"
        """,
    )
    cfg = cfgmod.load(path)
    assert cfg.region("us").local_port == cfgmod.DEFAULT_PORT


def test_unknown_region_raises(tmp_path):
    path = _write(
        tmp_path,
        """
        [regions.us]
        provider = "manual"
        host = "x"
        user = "y"
        """,
    )
    cfg = cfgmod.load(path)
    with pytest.raises(cfgmod.ConfigError):
        cfg.region("br")


def test_missing_provider_raises(tmp_path):
    path = _write(
        tmp_path,
        """
        [regions.br]
        host = "x"
        """,
    )
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load(path)


def test_missing_file_raises():
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load("/nonexistent/regionhop.toml")
