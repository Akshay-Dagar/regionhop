"""SSH dynamic (SOCKS5) tunnel management.

A tunnel is just ``ssh -D <port> -N`` to the regional VM. We launch it detached
so it survives the CLI process, track its PID in a state file, and can tear it
down later. Cross-platform (Windows / macOS / Linux).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


class TunnelError(Exception):
    """Raised when a tunnel cannot be established or torn down."""


def _state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    root = Path(base) if base else Path.home() / ".local" / "state"
    d = root / "regionhop"
    d.mkdir(parents=True, exist_ok=True)
    return d


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@dataclass
class Tunnel:
    host: str
    user: str
    key_path: str | None = None
    port: int = 1080
    password: str | None = None

    @property
    def _pidfile(self) -> Path:
        return _state_dir() / f"tunnel-{self.port}.pid"

    def is_up(self) -> bool:
        return port_open(self.port)

    def _build_command(self) -> list[str]:
        cmd = ["ssh"]
        if self.password:
            # Force password auth; the password is supplied via SSH_ASKPASS.
            cmd += [
                "-o", "PreferredAuthentications=password,keyboard-interactive",
                "-o", "PubkeyAuthentication=no",
                "-o", "NumberOfPasswordPrompts=1",
            ]
        elif self.key_path:
            cmd += ["-i", os.path.expanduser(self.key_path)]
        cmd += [
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            "-N", "-C", "-D", str(self.port),
            f"{self.user}@{self.host}",
        ]
        return cmd

    def start(self, wait: float = 15.0) -> None:
        if self.is_up():
            return

        kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            kwargs["start_new_session"] = True

        askpass: str | None = None
        if self.password:
            askpass, kwargs["env"] = _make_askpass(self.password)

        try:
            proc = subprocess.Popen(self._build_command(), **kwargs)
            self._pidfile.write_text(str(proc.pid), encoding="utf-8")

            deadline = time.time() + wait
            while time.time() < deadline:
                if self.is_up():
                    return
                if proc.poll() is not None:
                    self._pidfile.unlink(missing_ok=True)
                    hint = "password" if self.password else "host, user, and key"
                    raise TunnelError(
                        f"ssh exited early (code {proc.returncode}). Check the {hint}."
                    )
                time.sleep(0.4)
            raise TunnelError(
                f"Tunnel to {self.host} did not open port {self.port} within {wait:.0f}s."
            )
        finally:
            if askpass:
                try:
                    os.remove(askpass)
                except OSError:
                    pass

    def stop(self) -> bool:
        pid: int | None = None
        if self._pidfile.exists():
            try:
                pid = int(self._pidfile.read_text().strip())
            except ValueError:
                pid = None
            self._pidfile.unlink(missing_ok=True)
        if pid is None:
            return False
        return _kill(pid)


def _make_askpass(password: str) -> tuple[str, dict]:
    """Create a throwaway SSH_ASKPASS helper that echoes the password.

    The password is passed to the helper via an environment variable, so it is
    never written to disk. Returns (askpass_path, child_env).
    """
    env = dict(os.environ)
    env["SSH_ASKPASS_REQUIRE"] = "force"
    env.setdefault("DISPLAY", "regionhop:0")
    env["REGIONHOP_ASKPASS_PW"] = password

    if os.name == "nt":
        fd, path = tempfile.mkstemp(prefix="rh-askpass-", suffix=".cmd")
        os.write(fd, b"@echo off\r\necho %REGIONHOP_ASKPASS_PW%\r\n")
        os.close(fd)
    else:
        fd, path = tempfile.mkstemp(prefix="rh-askpass-", suffix=".sh")
        os.write(fd, b'#!/bin/sh\nprintf "%s\\n" "$REGIONHOP_ASKPASS_PW"\n')
        os.close(fd)
        os.chmod(path, 0o700)
    env["SSH_ASKPASS"] = path
    return path, env


def _kill(pid: int) -> bool:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, OSError):
        return False
