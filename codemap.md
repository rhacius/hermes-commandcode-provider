# Repository Atlas: hermes-commandcode-provider

## Project Responsibility

This repository packages a Hermes Agent model-provider integration for a
Command Code Go subscription. It combines a pure-Python, OpenAI-compatible
local bridge with Hermes plugin metadata, launchers, optional configuration
mutation, a shared model catalog, and an optional user-level systemd service.
The bridge keeps Command Code authentication and protocol translation outside
Hermes itself, so no Hermes source patches or external runtime dependencies are
required for proxying.

## System Entry Points

- `commandcode_bridge.py`: threaded local HTTP server exposing `/health`, model
  discovery, and OpenAI-compatible chat completions. It authenticates against
  Command Code, forwards requests to `/alpha/generate`, and translates SSE or
  NDJSON responses back to OpenAI response formats.
- `install.sh`: copies the bridge, catalog, provider package, and launchers to
  the Hermes installation; `--configure` additionally invokes the YAML
  configuration adapter.
- `bin/hermes-commandcode`: normal user-facing launcher. It discovers an API
  key, optionally adds a missing provider entry, ensures bridge readiness, and
  executes Hermes with `--provider commandcode` by default.
- `bin/hermes-commandcode-bridge`: standalone bridge launcher for callers that
  manage Hermes separately.
- `plugins/model-providers/commandcode/__init__.py`: declares and registers the
  Hermes `ProviderProfile` for the local bridge; `plugin.yaml` supplies plugin
  discovery metadata.
- `scripts/configure_hermes.py`: explicit configuration adapter that updates
  `~/.hermes/config.yaml` and backs up an existing file.
- `models.json`: bundled model IDs, display names, and context lengths used by
  installation, configuration, bridge fallback discovery, and Hermes defaults.
- `systemd/hermes-commandcode-bridge.service`: optional persistent user service
  for the installed bridge.

## Architecture and Data Flow

1. `install.sh` installs the bridge and `models.json` under `$HERMES_HOME`, the
   provider files under `$HERMES_HOME/plugins/model-providers/commandcode/`,
   and both launchers under `~/.local/bin`. With `--configure`, it runs the
   repository's `configure_hermes.py` after copying the runtime files.
2. Hermes discovers `plugin.yaml`, imports `__init__.py`, and registers a
   `ProviderProfile` named `commandcode` with aliases and fallback models. The
   profile points Hermes to `http://127.0.0.1:8788/v1` and advertises
   `COMMANDCODE_API_KEY` as its credential environment variable.
3. The combined launcher first checks `/health`, then prefers an already
   healthy bridge, a running user systemd service, or a PID-file/nohup fallback.
   Once ready, it resolves the Hermes executable and replaces itself with the
   Hermes process.
4. Hermes sends `GET /v1/models` or `POST /v1/chat/completions` to the local
   bridge. The bridge resolves credentials from the request, environment, or
   known auth files; loads or refreshes the model catalog; validates and maps
   messages, tools, sampling parameters, and response-format options; and
   submits an authenticated `/alpha/generate` request to Command Code.
5. The bridge maintains one session ID per process, accepts upstream SSE or
   NDJSON, and returns either streaming OpenAI SSE chunks or one accumulated
   non-streaming completion. Text, reasoning, tool calls, finish state, and
   usage are preserved where available.

## Design

- **Adapter boundary:** Hermes knows only the declarative provider profile and
  local OpenAI-compatible URL. Command Code-specific HTTP, authentication,
  headers, session state, and event translation remain in the bridge.
- **Catalog contract:** `models.json` is the bundled fallback and installation
  source. The bridge can query Command Code's live catalog and normalizes it;
  provider fallback IDs and generated Hermes context lengths should remain
  aligned with the bundled catalog.

## Integration

- **Runtime configuration:** the default bridge is loopback-only at
  `127.0.0.1:8788`; `COMMANDCODE_PROXY_HOST`, `COMMANDCODE_PROXY_PORT`, and
  bridge/API header environment variables provide controlled overrides. The
  systemd unit intentionally uses the fixed default loopback endpoint.
- **Dependencies:** bridge and launchers use Python/Bash standard facilities;
  the explicit YAML configurator requires PyYAML, and launcher health probes
  use `curl`. Upstream communication uses Python `http.client` rather than
  curl or temporary files.
- **Lifecycle alternatives:** systemd supervises a long-lived bridge with
  restart-on-failure semantics; the normal launcher falls back to a managed
  `nohup` process when systemd is unavailable; the bridge-only launcher leaves
  lifecycle management to its caller.

## Repository Directory Map

| Directory | Responsibility Summary | Detailed Map |
|---|---|---|
| `bin/` | Environment-configured launchers that coordinate bridge readiness and Hermes process execution. | [View Map](bin/codemap.md) |
| `plugins/` | Aggregate Hermes plugin namespace containing provider categories and concrete plugin packages. | [View Map](plugins/codemap.md) |
| `plugins/model-providers/` | Model-provider category and declarative provider registration boundary. | [View Map](plugins/model-providers/codemap.md) |
| `plugins/model-providers/commandcode/` | Concrete Command Code `ProviderProfile` and plugin metadata package. | [View Map](plugins/model-providers/commandcode/codemap.md) |
| `scripts/` | Installation-time Hermes configuration adapter and operational integration helpers. | [View Map](scripts/codemap.md) |
| `systemd/` | Declarative user-service supervision for the persistent bridge process. | [View Map](systemd/codemap.md) |

## Mapping Scope

Human-written `codemap.md` files are the atlas. `.slim/codemap.json` is a
local Slim cache (gitignored) and is not versioned — it embeds a
machine-specific absolute path.

Developer-only secret scanning lives in `scripts/check_secrets.py`,
`.githooks/pre-commit`, and `.github/workflows/secret-scan.yml`. Those
paths are not part of the runtime bridge.
