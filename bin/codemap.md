# bin/

## Responsibility

`bin/` contains the two executable entry points for operating the local
Command Code bridge:

- `hermes-commandcode` is the normal Hermes launcher. It discovers credentials,
  optionally adds the provider to Hermes configuration, ensures that the local
  bridge is healthy, and then replaces itself with the real `hermes` process.
- `hermes-commandcode-bridge` is the bridge-only launcher. It resolves the
  installed bridge script and starts it without configuring Hermes, managing a
  background process, or injecting command-line arguments.

These scripts are process and environment orchestration. The HTTP proxy,
request translation, authentication fallback, model discovery, and upstream
Command Code communication belong to `commandcode_bridge.py`, not to this
directory.

## Design patterns / abstractions

- **Environment-configured launchers:** host, port, Hermes home, Python
  executable, log path, API key, and Hermes executable are selected through
  environment variables with local defaults. Both scripts use strict Bash
  mode (`set -euo pipefail`).
- **Health-gated process coordination:** `hermes-commandcode` treats
  `GET /health` as the readiness contract. It prefers an already healthy
  bridge, otherwise waits for an active user systemd service, and finally falls
  back to a `nohup` process tracked by a PID file. It polls readiness after
  either service startup or fallback startup and fails rather than invoking
  Hermes against an unready proxy.
- **Idempotent setup:** credential detection only fills an absent
  `COMMANDCODE_API_KEY`; provider configuration is added only when the
  `commandcode` provider is missing; and `--provider commandcode` is injected
  only when the caller has not supplied `--provider` or `-P`.
- **Inline integration shims:** small Python heredocs perform JSON credential
  extraction and optional YAML configuration editing. They deliberately do
  not form a reusable library boundary; failures in these optional setup
  steps are suppressed so bridge startup can continue.
- **Process replacement and argument pass-through:** after preparation,
  `hermes-commandcode` uses `exec` so signals and exit status belong to
  Hermes. The bridge-only entry point uses `exec` to make the Python bridge
  the directly managed process and appends caller arguments unchanged.

## Flow

### `hermes-commandcode`

1. Resolve `host` and `port` from `COMMANDCODE_PROXY_HOST` and
   `COMMANDCODE_PROXY_PORT` (default `127.0.0.1:8788`), then derive the
   installed bridge, PID, and log paths under `HERMES_HOME` (default
   `~/.hermes`).
2. If `COMMANDCODE_API_KEY` is unset, run the credential shim against
   `$HERMES_HOME/.commandcode/auth.json`, `~/.commandcode/auth.json`, and
   `~/.pi/agent/auth.json`. It accepts a direct `apiKey`/`commandcode` string
   or the nested `commandcode.access` value, exporting the first match.
3. If `$HERMES_HOME/config.yaml` exists and PyYAML is importable, load it and
   add a `providers.commandcode` entry when absent. The generated entry points
   at `http://127.0.0.1:8788/v1`, uses `COMMANDCODE_API_KEY`, selects
   `chat_completions`, and imports model context lengths from
   `$HERMES_HOME/models.json` when available.
4. Probe `http://$host:$port/health`. If it is not ready, check the user
   systemd unit `hermes-commandcode-bridge.service` and wait for it to become
   healthy. If that unit is not active, remove a stale PID file, start
   `$HERMES_HOME/commandcode_bridge.py` with `nohup`, append output to the
   configured log, record its PID, and poll health.
5. Abort with diagnostics if the bridge remains unhealthy. Otherwise resolve
   Hermes from `HERMES_BIN`, `PATH`, or the supported `$HERMES_HOME/.local/bin`,
   `$HOME/.local/bin`, and `/usr/local/bin` locations.
6. Prepend `--provider commandcode` unless the original arguments already
   contain `--provider` or `-P`, then `exec` the resolved Hermes binary with
   the resulting argument vector.

### `hermes-commandcode-bridge`

1. Resolve the same host, port, Hermes home, and Python executable settings.
2. `exec` the installed `$HERMES_HOME/commandcode_bridge.py` with `--host` and
   `--port`, followed by all caller-supplied arguments. All server lifecycle
   and request behavior then occurs in the Python bridge.

## Integration

- `install.sh` installs `commandcode_bridge.py` as
  `$HERMES_HOME/commandcode_bridge.py` and these scripts as
  `$HOME/.local/bin/hermes-commandcode` and
  `$HOME/.local/bin/hermes-commandcode-bridge`; the launchers assume those
  paths unless `HERMES_HOME`, `PYTHON`, or `HERMES_BIN` overrides them.
- The launchers start or locate the Python bridge, whose local HTTP interface
  exposes `/health`, `/v1/models`, and `/v1/chat/completions`. Hermes' provider
  profile and the auto-generated config use the local OpenAI-compatible base
  URL `http://127.0.0.1:8788/v1`. The auto-configuration URL is fixed to that
  address even when the launcher is given non-default proxy host or port
  values, so custom endpoint settings require matching Hermes configuration.
- The systemd unit runs the same installed Python bridge on the default local
  address. `hermes-commandcode` recognizes that unit only as a readiness/startup
  source; it does not enable, restart, or otherwise manage the unit.
- Credential and runtime settings are passed to the bridge through
  `COMMANDCODE_API_KEY`, `COMMANDCODE_PROXY_HOST`, and
  `COMMANDCODE_PROXY_PORT`. The ad-hoc path also redirects bridge output to
  `HERMES_COMMANDCODE_PROXY_LOG`; the standalone launcher leaves output and
  lifecycle management to its caller.
- The normal launcher requires `curl` for its health probe, while the Python
  bridge itself is launched through the selected Python interpreter. Neither
  launcher calls the upstream Command Code API directly.
