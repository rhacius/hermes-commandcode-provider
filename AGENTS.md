# Hermes Command Code Provider

OpenAI-compatible local bridge + Hermes model-provider plugin for using a
Command Code Go subscription with Hermes Agent. Pure Python (stdlib) and Bash;
no Hermes source patches, no external runtime dependencies.

## Project

- **Stack:** Python 3 stdlib (bridge), Bash (launchers/installer), JSON
  (model catalog), YAML (Hermes config), systemd user unit.
- **Entry points:** `commandcode_bridge.py` (local HTTP server, loopback
  `127.0.0.1:8788`, exposes `/health`, `/v1/models`, `/v1/chat/completions`),
  `bin/hermes-commandcode` (start bridge + `exec hermes --provider commandcode`),
  `bin/hermes-commandcode-bridge` (bridge only).
- **Full architecture and data flow:** `codemap.md` at the root, plus
  per-directory codemaps in `bin/`, `scripts/`, `plugins/`, `systemd/`.
  Read the relevant one before touching a directory.

## Commands

All verified on this repo (2026-07-23). There is no build step or dependency
manifest; runtime is stdlib-only (PyYAML and `curl` only in optional paths).

- Python syntax: `python3 -m py_compile commandcode_bridge.py scripts/configure_hermes.py scripts/test_reasoning_mapping.py scripts/check_secrets.py`
- Bash syntax: `bash -n install.sh bin/hermes-commandcode bin/hermes-commandcode-bridge scripts/smoke_test.sh scripts/install-git-hooks.sh .githooks/pre-commit`
- JSON catalog: `python3 -m json.tool models.json`
- Offline unit test (reasoning mapping): `python3 scripts/test_reasoning_mapping.py`
- Secret scanner (offline): `python3 scripts/check_secrets.py --self-test && python3 scripts/check_secrets.py`
- Install local pre-commit hook: `./scripts/install-git-hooks.sh`
- Hook syntax: `bash -n .githooks/pre-commit scripts/install-git-hooks.sh`
- Full smoke test: `./scripts/smoke_test.sh` — starts the bridge, then tests
  health, models, non-streaming/streaming chat, usage, temperature, and tool
  calls. Requires `curl`; API-dependent tests are skipped when no
  `COMMANDCODE_API_KEY` or auth file (`~/.commandcode/auth.json`,
  `~/.pi/agent/auth.json`) is present.
- Install: `./install.sh [--configure]` — copies the bundle into
  `$HERMES_HOME` (`~/.hermes`) and `~/.local/bin`; `--configure` runs
  `scripts/configure_hermes.py` (requires PyYAML) and backs up `config.yaml`.

## Architecture

- `commandcode_bridge.py` — threaded `http.server`; translates OpenAI requests
  to Command Code `/alpha/generate` via `http.client` (no curl subprocesses, no
  tempfiles); maps SSE/NDJSON back to OpenAI SSE/JSON; keeps one `SESSION_ID`
  per process; auth precedence: Bearer header → `COMMANDCODE_API_KEY` → auth files.
- `plugins/model-providers/commandcode/` — Hermes `ProviderProfile`
  (`commandcode`, aliases `cc`, `command-code`, `commandcode-alpha`) registered
  at import time; `plugin.yaml` is discovery metadata only.
- `bin/` — launchers: credential discovery, optional `config.yaml`
  auto-provider (idempotent), bridge readiness (healthy → systemd → nohup/pidfile).
- `install.sh` + `scripts/configure_hermes.py` — install bundle; configurator
  rewrites `~/.hermes/config.yaml` (timestamped backup; **replaces** an existing
  `commandcode` provider entry).
- `models.json` — single source of truth for the model catalog
  (IDs, names, context lengths).
- `systemd/hermes-commandcode-bridge.service` — optional user service
  (restart-on-failure, reads `~/.hermes/.env`).

## Conventions

- **Python:** stdlib only at runtime; `from __future__ import annotations`;
  type hints; private helpers prefixed `_`; `# ── section ──` banner comments;
  upstream failures raised as descriptive `RuntimeError`. No hardcoded
  credentials/versions — configurable via `COMMANDCODE_*` env vars.
- **Bash:** `set -euo pipefail`; env vars with defaults; idempotent setup
  (add the provider only if missing, inject `--provider` only if absent);
  `exec` to replace the process.
- **Security:** bridge refuses non-loopback binding unless
  `COMMANDCODE_PROXY_ALLOW_REMOTE=1`; 10 MB request-body cap; errors returned
  as OpenAI-style `{"error": {...}}`.
- **Model catalog:** any model change must propagate to `models.json` **and**
  the fallback copies: `DEFAULT_MODELS` in `commandcode_bridge.py`, the
  fallback dict in `scripts/configure_hermes.py`, `fallback_models` in the
  plugin profile, and the README table.
- **Tests:** do not weaken `scripts/smoke_test.sh` or
  `scripts/test_reasoning_mapping.py` to force green; they hit the real API
  when credentials exist and must stay honest.

## Documentation expectations

- Update the relevant codemap (root or per-directory) when structure or
  behavior changes; keep README's env-var table, install/use flow, and model
  list in sync with code.
- Do not commit generated artifacts (`__pycache__/`, `*.pyc`, `.slim/` —
  gitignored). Do not commit credentials (`.env`, `auth.json`, private keys).

## Notes

- (task-specific notes go here)
