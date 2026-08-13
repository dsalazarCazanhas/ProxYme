# Contributing to ProxYme

## Setup

```bash
uv sync
```

## Running

```bash
uv run python main.py
```

## Tests

```bash
QT_QPA_PLATFORM=offscreen uv run pytest
```

`QT_QPA_PLATFORM=offscreen` runs the Qt tests without a display — useful in CI or
over SSH. Skip it if you have a display and want windows to actually render.

## Lint

```bash
uv run ruff check .
```

CI runs both `ruff check` and the test suite on every push and pull request
against `master`.

## Guidelines

- Keep changes focused — avoid bundling unrelated refactors with a feature or fix.
- Add or update tests for any change to `proxyme/tunnel/` or `proxyme/storage/`
  (the non-UI core). UI changes in `proxyme/qt/` are covered more lightly; a
  manual smoke test is fine if a proper widget test isn't practical.
- Never log or persist credentials (passwords, passphrases, private key contents).
  `~/.proxyme/tunnels.json` only stores tunnel topology (host, port, mode) —
  keep it that way.
