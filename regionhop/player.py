"""Playback back-ends: a proxied Chromium browser, or yt-dlp.

Both route through the local SOCKS5 tunnel opened by :mod:`regionhop.tunnel`.
A real browser is the most reliable for livestreams (it slips past YouTube's
datacenter-IP bot check); yt-dlp is best for downloading/recording.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile


class PlayerError(Exception):
    """Raised when no playback back-end is available."""


_WINDOWS_BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
_MACOS_BROWSERS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
_LINUX_BROWSERS = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "brave-browser",
    "microsoft-edge",
]


def find_browser() -> str | None:
    """Locate a Chromium-based browser (Chrome/Chromium/Brave/Edge)."""
    if sys.platform.startswith("win"):
        candidates = _WINDOWS_BROWSERS
    elif sys.platform == "darwin":
        candidates = _MACOS_BROWSERS
    else:
        candidates = []
    for path in candidates:
        if os.path.exists(path):
            return path
    for name in (*_LINUX_BROWSERS, "chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def play_browser(url: str, proxy_port: int, profile_dir: str | None = None) -> subprocess.Popen:
    """Open ``url`` in a Chromium browser routed through the SOCKS5 proxy."""
    browser = find_browser()
    if not browser:
        raise PlayerError("No Chromium-based browser (Chrome/Chromium/Brave/Edge) found.")
    profile = profile_dir or os.path.join(tempfile.gettempdir(), "regionhop-profile")
    args = [
        browser,
        f"--user-data-dir={profile}",
        f"--proxy-server=socks5://127.0.0.1:{proxy_port}",
        "--proxy-bypass-list=<-loopback>",
        "--new-window",
        url,
    ]
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(args, **kwargs)


def _format_selector(quality: str) -> str:
    if quality in ("best", "worst"):
        return quality
    if str(quality).isdigit():
        return f"bv*[height<={quality}]+ba/b[height<={quality}]"
    return quality


def _find_media_player() -> str | None:
    for name in ("mpv", "ffplay"):
        found = shutil.which(name)
        if found:
            return found
    return None


def play_ytdlp(
    url: str,
    proxy_port: int,
    quality: str = "best",
    cookies_from_browser: str | None = None,
    download: bool = False,
    out_dir: str = ".",
) -> int:
    """Stream (to mpv/ffplay) or download ``url`` via yt-dlp through the proxy."""
    if not shutil.which("yt-dlp"):
        raise PlayerError("yt-dlp not found on PATH. Install it: https://github.com/yt-dlp/yt-dlp")
    base = ["yt-dlp", "--proxy", f"socks5://127.0.0.1:{proxy_port}"]
    if cookies_from_browser:
        base += ["--cookies-from-browser", cookies_from_browser]
    fmt = _format_selector(quality)

    if download:
        cmd = base + ["-f", fmt, "-o", os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s"), url]
        return subprocess.run(cmd, check=False).returncode

    player = _find_media_player()
    if player:
        yt = subprocess.Popen(
            base + ["-f", fmt, "--hls-use-mpegts", "-o", "-", url],
            stdout=subprocess.PIPE,
        )
        assert yt.stdout is not None
        pl = subprocess.Popen([player, "-"], stdin=yt.stdout)
        yt.stdout.close()
        pl.wait()
        yt.wait()
        return pl.returncode

    # No player installed: just print the direct stream URL(s).
    return subprocess.run(base + ["-g", url], check=False).returncode
