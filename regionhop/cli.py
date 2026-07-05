"""regionhop command-line interface."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from . import config as cfgmod
from .geocheck import GeoError, exit_country
from .player import PlayerError, play_browser, play_ytdlp
from .providers import ProviderError, get_provider
from .tunnel import Tunnel, TunnelError


def _ensure_up(region: cfgmod.RegionConfig, verify: bool = True) -> tuple:
    provider = get_provider(region)
    vm = provider.ensure_running()
    tun = Tunnel(host=vm.host, user=vm.user, key_path=vm.key_path, port=region.local_port)
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
        print("No regions configured. Run 'regionhop init'.")
        return 0
    for name, region in cfg.regions.items():
        default = "  (default)" if name == cfg.default_region else ""
        print(f"  {name:<12} provider={region.provider}  port={region.local_port}{default}")
    return 0


def cmd_up(args, cfg) -> int:
    _ensure_up(cfg.region(args.region), verify=not args.no_verify)
    return 0


def cmd_watch(args, cfg) -> int:
    _, tun = _ensure_up(cfg.region(args.region), verify=not args.no_verify)
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

    p_regions = sub.add_parser("regions", help="list configured regions")
    p_regions.set_defaults(func=cmd_regions, needs_config=True)

    p_up = sub.add_parser("up", help="start the tunnel for a region")
    p_up.add_argument("-r", "--region")
    p_up.add_argument("--no-verify", action="store_true", help="skip the exit-country check")
    p_up.set_defaults(func=cmd_up, needs_config=True)

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
    p_watch.set_defaults(func=cmd_watch, needs_config=True)

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
