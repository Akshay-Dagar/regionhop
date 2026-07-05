# Contributing to regionhop

Thanks for your interest! Contributions of code, docs, and providers are welcome.

## Development setup

```bash
git clone https://github.com/OWNER/regionhop && cd regionhop
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run the checks before opening a PR:

```bash
ruff check .
pytest -q
```

CI runs the same on Linux, macOS, and Windows across Python 3.11 and 3.12.

## Project layout

```
regionhop/
  cli.py          # argparse entry point and subcommands
  config.py       # TOML config loading
  tunnel.py       # SSH SOCKS5 tunnel lifecycle
  geocheck.py     # exit-country verification (tiny built-in SOCKS5 client)
  player.py       # browser / yt-dlp playback back-ends
  providers/
    base.py       # Provider ABC + VMInfo
    manual.py     # bring-your-own VM
    azure.py      # az-CLI-managed VM
tests/            # pytest unit tests (no network required)
```

## Adding a provider

1. Create `regionhop/providers/yourcloud.py` with a class that subclasses
   `Provider` and implements `from_options()` and `ensure_running()`. Implement
   `deallocate()` / `destroy()` / `status()` where the backend supports them.
2. Register it in `regionhop/providers/__init__.py`.
3. Add a short section to the README's provider table.
4. Add a unit test that doesn't require network or credentials (mock subprocess).

Keep runtime dependencies at zero where possible — shelling out to a provider's
official CLI (as `azure.py` does) is preferred over adding heavy SDKs.

## Style

- Formatting/linting via `ruff`.
- Keep functions small and typed. No new hard dependencies without discussion.

## Reporting issues

Please include your OS, Python version, the command you ran, and the output
(with any IPs/keys redacted).
