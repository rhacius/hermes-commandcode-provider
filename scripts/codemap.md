# scripts/

## Responsibility

The `scripts/` directory contains the operational setup code for connecting an
installed Hermes Agent to the local Command Code bridge. Its implementation
entry point is `configure_hermes.py`; it turns the repository's model catalog
into the Hermes provider configuration and points Hermes at the loopback
OpenAI-compatible endpoint.

The directory also contains `smoke_test.sh`,
`test_reasoning_mapping.py`, `check_secrets.py`, and
`install-git-hooks.sh`, but those are verification-only artifacts rather
than runtime/configuration components and are intentionally not part of the
core map below.

## Design patterns / abstractions

- **Configuration adapter:** `configure_hermes.py` translates this project's
  model catalog and bridge contract into Hermes' `config.yaml` schema. It sets
  the `commandcode` provider, `chat_completions` transport, loopback `base_url`,
  API-key environment variable, default model, and per-model context lengths.
- **Single source with defensive fallback:** `_load_models()` reads
  `<repository>/models.json`, filters a JSON-list catalog to entries containing
  model IDs and context lengths, and falls back to the embedded catalog when
  the file is missing, unreadable, malformed, or not a list. (A valid but empty
  list produces an empty configured catalog.)
- **Preserving update:** `main()` loads the existing YAML as a mapping,
  creates `model`/`providers` mappings when absent, and changes only the
  provider settings it owns. Before writing, it copies an existing config to a
  timestamped `.before-commandcode-YYYYMMDD-HHMMSS` backup. The provider entry
  itself is deliberately replaced, and the script warns about that behavior.
- **Environment-driven installation boundary:** `install.sh` uses
  `HERMES_HOME` (default `~/.hermes`) and installs the bridge, plugin, model
  catalog, and launchers as a coherent bundle. `--configure` is an explicit
  opt-in to run the Python YAML mutator; installation without it does not
  modify Hermes configuration.
- **Launcher/orchestrator split:** the installed `hermes-commandcode` launcher
  owns credential discovery, lazy provider setup, bridge readiness, and Hermes
  process replacement. `hermes-commandcode-bridge` is intentionally a thin
  bridge-only wrapper. A user systemd service is another supported bridge
  lifecycle, with the combined launcher falling back to a PID-file/nohup
  process when systemd is unavailable.

## Flow

1. `install.sh` resolves the repository directory, target Hermes home, and
   `~/.local/bin`; validates its only option (`--configure`); then copies
   `commandcode_bridge.py`, the provider plugin files, `models.json`, and both
   launchers. With `--configure`, it invokes
   `scripts/configure_hermes.py` after the files are installed.
2. `configure_hermes.py` optionally loads `$HERMES_HOME/config.yaml` with
   PyYAML, backs it up, normalizes a non-mapping/empty document to `{}`, and
   writes:
   - `model.provider = commandcode`
   - `model.default = deepseek/deepseek-v4-flash`
   - `model.base_url = http://127.0.0.1:8788/v1`
   - `providers.commandcode` with the bridge URL, `COMMANDCODE_API_KEY`,
     `chat_completions`, the same default model, and catalog-derived context
     lengths.
   It creates the parent directory and emits the resulting path and backup
   path.
3. At runtime, `bin/hermes-commandcode` uses the configured host/port and
   `HERMES_HOME`, detects a bearer credential from `COMMANDCODE_API_KEY` or
   known auth JSON files, and exports it when found. If `config.yaml` exists
   but has no `commandcode` provider, its embedded YAML routine adds one using
   the installed `models.json` (without overwriting an existing provider).
4. The combined launcher probes `/health`. It reuses a healthy bridge, waits
   for an active `hermes-commandcode-bridge.service`, or starts the installed
   bridge with `nohup`, a PID file, and a log file. It waits for readiness,
   resolves `HERMES_BIN` or a `hermes` executable, injects
   `--provider commandcode` unless the caller already supplied `--provider` or
   `-P`, and `exec`s Hermes with the original arguments.
5. The bridge receives Hermes' OpenAI-compatible `/v1/chat/completions` calls,
   resolves the API key, translates messages/tools and sampling settings into
   Command Code `/alpha/generate` requests, and maps upstream SSE events back
   to OpenAI JSON or SSE responses. Its `/health` and `/v1/models` endpoints
   are the readiness and catalog contracts used by the launchers/configuration.

## Integration

| Component | Contract with `scripts/` and the bridge |
| --- | --- |
| `install.sh` | Installs `commandcode_bridge.py` at `$HERMES_HOME/commandcode_bridge.py`, plugin metadata under `$HERMES_HOME/plugins/model-providers/commandcode/`, `models.json` at `$HERMES_HOME/models.json`, and the two launchers in `~/.local/bin`. It invokes `configure_hermes.py` from the repository, so that script reads the repository catalog rather than the installed copy. |
| `configure_hermes.py` | Requires PyYAML. Writes Hermes' provider URL as `http://127.0.0.1:8788/v1`; the bridge exposes `/health`, `/models`, `/v1/models`, and `/v1/chat/completions`. It uses the `COMMANDCODE_API_KEY` name expected by Hermes and the bridge. |
| `bin/hermes-commandcode` | Is the normal user-facing integration. It expects the installed bridge and model catalog in `$HERMES_HOME`, supports `COMMANDCODE_PROXY_HOST`, `COMMANDCODE_PROXY_PORT`, `HERMES_COMMANDCODE_PROXY_LOG`, `PYTHON`, and `HERMES_BIN`, and uses `curl`, `systemctl --user`, `nohup`, and a PID file for lifecycle management. |
| `bin/hermes-commandcode-bridge` | Starts only `$HERMES_HOME/commandcode_bridge.py` with the configured host and port, allowing Hermes and the proxy to be managed independently. |
| `systemd/hermes-commandcode-bridge.service` | Optional user-service integration. It starts the installed bridge on loopback port `8788`, loads `$HERMES_HOME/.env`, enables verbose logging, and restarts on failure. The combined launcher detects this service before using its ad-hoc fallback. |
| `commandcode_bridge.py` | Uses the installed sibling `models.json` as its live/fallback catalog, reads API credentials from the environment or `~/.commandcode/auth.json`/`~/.pi/agent/auth.json`, and maintains one session ID per bridge process. It refuses non-loopback binding unless `COMMANDCODE_PROXY_ALLOW_REMOTE=1`. |

For verification context only, `smoke_test.sh` starts the bridge and checks
health, models, non-streaming and streaming completions, usage, sampling, and
tool calls; it is not a production integration layer.
`check_secrets.py` is a stdlib scanner for accidental secret literals
(masked output); `--staged` fails closed if git is missing or errors.
`install-git-hooks.sh` installs `.githooks/pre-commit` into
`git rev-parse --git-path hooks` and refuses to overwrite a different
existing hook. CI additionally runs Gitleaks via
`.github/workflows/secret-scan.yml`.
