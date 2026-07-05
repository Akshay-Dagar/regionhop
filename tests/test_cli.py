from regionhop.cli import build_parser


def test_setup_command_registered():
    ns = build_parser().parse_args(["setup"])
    assert ns.func.__name__ == "cmd_setup"
    assert ns.needs_config is False


def test_watch_adhoc_flags():
    ns = build_parser().parse_args(
        ["watch", "https://x", "--host", "1.2.3.4", "--user", "u", "--key", "k", "--port", "1099"]
    )
    assert ns.host == "1.2.3.4"
    assert ns.user == "u"
    assert ns.key == "k"
    assert ns.port == 1099
    assert ns.func.__name__ == "cmd_watch"
    # watch handles its own config loading now
    assert ns.needs_config is False


def test_up_does_not_require_preloaded_config():
    ns = build_parser().parse_args(["up", "-r", "br"])
    assert ns.needs_config is False


def test_watch_defaults_to_browser():
    ns = build_parser().parse_args(["watch", "https://x"])
    assert ns.player == "browser"
    assert ns.host is None


def test_setup_wizard_writes_config(tmp_path, monkeypatch):
    import regionhop.cli as cli
    import regionhop.config as cfgmod

    # answers: region, provider, host, user, auth-method, key, port
    answers = iter(["br", "manual", "203.0.113.10", "azureuser", "key", "~/.ssh/k", "1080"])
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: next(answers))
    monkeypatch.setattr(
        cli.sys, "stdin", type("FakeStdin", (), {"isatty": staticmethod(lambda: True)})()
    )

    path = tmp_path / "regionhop.toml"
    args = type("Args", (), {"config": str(path)})()
    cfg = cli._setup_wizard(args)

    assert path.exists()
    assert cfg.default_region == "br"
    region = cfg.region("br")
    assert region.provider == "manual"
    assert region.options["host"] == "203.0.113.10"
    assert region.options["key_path"] == "~/.ssh/k"
    assert region.local_port == 1080
    # and it round-trips from disk
    assert cfgmod.load(path).region("br").options["user"] == "azureuser"


def test_setup_wizard_password(tmp_path, monkeypatch):
    import regionhop.cli as cli

    # region, provider, host, user, auth-method, password, port
    answers = iter(["br", "manual", "1.2.3.4", "u", "password", "s3cr3t", "1080"])
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: next(answers))
    monkeypatch.setattr(
        cli.sys, "stdin", type("FakeStdin", (), {"isatty": staticmethod(lambda: True)})()
    )

    path = tmp_path / "regionhop.toml"
    args = type("Args", (), {"config": str(path)})()
    cfg = cli._setup_wizard(args)

    region = cfg.region("br")
    assert region.options["password"] == "s3cr3t"
    assert "key_path" not in region.options


