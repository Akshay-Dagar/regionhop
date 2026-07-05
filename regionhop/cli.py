"""regionhop command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from . import config as cfgmod
from .geocheck import GeoError, exit_country
from .player import PlayerError, play_browser, play_ytdlp
from .providers import ProviderError, get_provider
from .tunnel import Tunnel, TunnelError


def _ensure_up(region: cfgmod.RegionConfig, verify: bool = True) -> tuple:
    provider = get_provider(region)
    vm = provider.ensure_running()
    tun = Tunnel(
        host=vm.host,
        user=vm.user,
        key_path=vm.key_path,
        port=region.local_port,
        password=vm.password,
    )
    if tun.is_up():
        print(f"Tunnel already up on 127.0.0.1:{tun.port}")
    else:
        print(f"Starting SOCKS5 tunnel via '{region.name}' ({tun.user}@{tun.host}) ...")
        tun.start()
        print(f"Tunnel up on 127.0.0.1:{tun.port}")
    if verify:
        try:
            geo = exit_country(tun.port)
            print(f"Exit: {geo.get('country')} ({geo.get('countryCode')}) {geo.get('query')}")
        except GeoError as exc:
            print(f"Warning: could not verify exit country: {exc}", file=sys.stderr)
    return provider, tun


def _ask(prompt: str, default: str | None = None, required: bool = False) -> str:
    hint = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{hint}: ").strip()
        if not value and default is not None:
            return default
        if value:
            return value
        if not required:
            return ""
        print("  (required)")


def _setup_wizard(args) -> cfgmod.Config:
    if not sys.stdin.isatty():
        raise cfgmod.ConfigError(
            "Setup needs an interactive terminal. Run 'regionhop init' and edit the file."
        )
    path = Path(args.config) if args.config else cfgmod.default_config_path()
    try:
        cfg = cfgmod.load(str(path)) if path.exists() else cfgmod.Config()
    except cfgmod.ConfigError:
        cfg = cfgmod.Config()

    print("regionhop setup\n")
    name = _ask("Region name", default="br")
    options = {
        "host": _ask("VM public IP / host", required=True),
        "user": _ask("SSH username", default="azureuser", required=True),
    }
    if _ask("Auth method (password/key)", default="password").lower().startswith("k"):
        options["key_path"] = _ask("SSH private key path", default="~/.ssh/id_ed25519")
    else:
        options["password"] = _ask("SSH password", required=True)

    port = int(_ask("Local SOCKS5 port", default=str(cfgmod.DEFAULT_PORT)))
    cfg.regions[name] = cfgmod.RegionConfig(
        name=name, provider="manual", options=options, local_port=port
    )
    if not cfg.default_region or _ask(
        f"Make '{name}' the default region? (Y/n)", default="Y"
    ).lower().startswith("y"):
        cfg.default_region = name

    saved = cfgmod.save(cfg, path)
    print(f"\nSaved config to {saved}")
    if options.get("password"):
        print(
            "WARNING: the SSH password is stored in PLAINTEXT there -- keep the "
            "file private; SSH keys are safer."
        )
    return cfg


def _load_or_setup(args) -> cfgmod.Config:
    try:
        return cfgmod.load(args.config)
    except cfgmod.ConfigError:
        if args.config is None and cfgmod.find_config() is None and sys.stdin.isatty():
            print("No config found \u2014 let's set up a region.\n")
            _setup_wizard(args)
            return cfgmod.load()
        raise


def cmd_setup(args, _cfg) -> int:
    _setup_wizard(args)
    print("\nReady. Watch something with:  regionhop watch <url>")
    return 0


def cmd_init(args, _cfg) -> int:
    try:
        path = cfgmod.init(args.path)
    except cfgmod.ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Wrote example config to {path}")
    print("Edit it, then run:  regionhop watch --region <name> <url>")
    return 0


def cmd_regions(_args, cfg) -> int:
    if not cfg.regions:
        print("No regions configured. Run 'regionhop setup'.")
        return 0
    for name, region in cfg.regions.items():
        default = "  (default)" if name == cfg.default_region else ""
        print(f"  {name:<12} provider={region.provider}  port={region.local_port}{default}")
    return 0


def cmd_up(args, _cfg) -> int:
    cfg = _load_or_setup(args)
    _ensure_up(cfg.region(args.region), verify=not args.no_verify)
    return 0


def cmd_watch(args, _cfg) -> int:
    if args.host:
        opts = {"host": args.host, "user": args.user or "azureuser"}
        if args.password:
            opts["password"] = args.password
        if args.key:
            opts["key_path"] = args.key
        region = cfgmod.RegionConfig(
            name="adhoc",
            provider="manual",
            options=opts,
            local_port=args.port or cfgmod.DEFAULT_PORT,
        )
    else:
        region = _load_or_setup(args).region(args.region)
    _, tun = _ensure_up(region, verify=not args.no_verify)
    if args.player == "browser":
        play_browser(args.url, tun.port)
        print("Opened in your browser through the regional proxy.")
        return 0
    return play_ytdlp(
        args.url,
        tun.port,
        quality=args.quality,
        cookies_from_browser=args.cookies_from_browser,
        download=args.download,
    )


def cmd_status(args, cfg) -> int:
    region = cfg.region(args.region)
    print(f"Region : {region.name}")
    try:
        print(f"VM     : {get_provider(region).status()}")
    except ProviderError as exc:
        print(f"VM     : error: {exc}")
    up = Tunnel("", "", None, port=region.local_port).is_up()
    print(f"Tunnel : {'UP' if up else 'down'} (127.0.0.1:{region.local_port})")
    return 0


def cmd_down(args, cfg) -> int:
    region = cfg.region(args.region)
    stopped = Tunnel("", "", None, port=region.local_port).stop()
    print("Tunnel stopped." if stopped else "No tracked tunnel to stop.")
    if args.destroy:
        get_provider(region).destroy()
    elif args.deallocate:
        get_provider(region).deallocate()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="regionhop",
        description="Watch region-locked video (incl. livestreams) via your own regional VMs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", help="path to a config file")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create an example config file")
    p_init.add_argument("path", nargs="?", help="where to write the config")
    p_init.set_defaults(func=cmd_init, needs_config=False)

    p_setup = sub.add_parser("setup", help="interactive configuration wizard")
    p_setup.set_defaults(func=cmd_setup, needs_config=False)

    p_regions = sub.add_parser("regions", help="list configured regions")
    p_regions.set_defaults(func=cmd_regions, needs_config=True)

    p_up = sub.add_parser("up", help="start the tunnel for a region")
    p_up.add_argument("-r", "--region")
    p_up.add_argument("--no-verify", action="store_true", help="skip the exit-country check")
    p_up.set_defaults(func=cmd_up, needs_config=False)

    p_watch = sub.add_parser("watch", help="watch a video/livestream through a region")
    p_watch.add_argument("url")
    p_watch.add_argument("-r", "--region")
    p_watch.add_argument("--player", choices=["browser", "yt-dlp"], default="browser")
    p_watch.add_argument(
        "--quality", default="best", help="'best', 'worst', or a max height like 720"
    )
    p_watch.add_argument("--cookies-from-browser", dest="cookies_from_browser",
                         help="pass browser cookies to yt-dlp (e.g. chrome, firefox)")
    p_watch.add_argument(
        "--download", action="store_true", help="download instead of stream (yt-dlp)"
    )
    p_watch.add_argument("--no-verify", action="store_true")
    p_watch.add_argument("--host", help="ad-hoc VM host/IP (run without a config file)")
    p_watch.add_argument("--user", help="ad-hoc SSH username (with --host)")
    p_watch.add_argument("--key", help="ad-hoc SSH private key path (with --host)")
    p_watch.add_argument("--password", help="ad-hoc SSH password (with --host; prefer --key)")
    p_watch.add_argument("--port", type=int, help="local SOCKS5 port (ad-hoc mode)")
    p_watch.set_defaults(func=cmd_watch, needs_config=False)

    p_status = sub.add_parser("status", help="show region/VM/tunnel status")
    p_status.add_argument("-r", "--region")
    p_status.set_defaults(func=cmd_status, needs_config=True)

    p_down = sub.add_parser("down", help="stop the tunnel (optionally deallocate/destroy the VM)")
    p_down.add_argument("-r", "--region")
    p_down.add_argument("--deallocate", action="store_true", help="stop VM compute billing")
    p_down.add_argument("--destroy", action="store_true", help="delete the VM entirely")
    p_down.set_defaults(func=cmd_down, needs_config=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    cfg = None
    if getattr(args, "needs_config", False):
        try:
            cfg = cfgmod.load(args.config)
        except cfgmod.ConfigError as exc:
            print(exc, file=sys.stderr)
            return 2

    try:
        return args.func(args, cfg)
    except (ProviderError, TunnelError, PlayerError, GeoError, cfgmod.ConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
