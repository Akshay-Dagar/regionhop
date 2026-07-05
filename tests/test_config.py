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


def test_provider_defaults_to_manual(tmp_path):
    path = _write(
        tmp_path,
        """
        [regions.br]
        host = "x"
        user = "y"
        """,
    )
    cfg = cfgmod.load(path)
    assert cfg.region("br").provider == "manual"


def test_missing_file_raises():
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load("/nonexistent/regionhop.toml")


def test_dumps_and_reload_roundtrip(tmp_path):
    cfg = cfgmod.Config(
        regions={
            "br": cfgmod.RegionConfig(
                "br",
                "manual",
                {"host": "203.0.113.10", "user": "azureuser", "key_path": "~/.ssh/k"},
                1080,
            )
        },
        default_region="br",
    )
    path = tmp_path / "regionhop.toml"
    cfgmod.save(cfg, path)

    reloaded = cfgmod.load(path)
    region = reloaded.region("br")
    assert reloaded.default_region == "br"
    assert region.provider == "manual"
    assert region.options["host"] == "203.0.113.10"
    assert region.local_port == 1080


def test_find_config(tmp_path, monkeypatch):
    monkeypatch.delenv("REGIONHOP_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.chdir(tmp_path)

    assert cfgmod.find_config() is None
    (tmp_path / "regionhop.toml").write_text(
        '[regions.br]\nprovider = "manual"\nhost = "x"\nuser = "y"\n', encoding="utf-8"
    )
    found = cfgmod.find_config()
    assert found is not None
    assert found.name == "regionhop.toml"


def test_dumps_includes_password(tmp_path):
    cfg = cfgmod.Config(
        regions={
            "br": cfgmod.RegionConfig(
                "br", "manual", {"host": "h", "user": "u", "password": "p@ss"}, 1080
            )
        },
        default_region="br",
    )
    path = tmp_path / "regionhop.toml"
    cfgmod.save(cfg, path)
    text = path.read_text(encoding="utf-8")
    assert 'password = "p@ss"' in text
    assert "provider" not in text  # manual is the default and is omitted
    assert cfgmod.load(path).region("br").options["password"] == "p@ss"
