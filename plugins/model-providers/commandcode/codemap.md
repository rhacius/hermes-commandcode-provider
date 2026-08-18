# `plugins/model-providers/commandcode/`

## Responsibility

This directory defines the Hermes model-provider plugin for Command Code. It
does not implement the upstream API client or an inference transport. Instead,
it publishes a `ProviderProfile` named `commandcode` that tells Hermes to use
the local OpenAI-compatible bridge supplied by `commandcode_bridge.py`.

The profile provides:

- The provider identity and user-facing metadata: `commandcode`, aliases
  `command-code`, `commandcode-alpha`, and `cc`, display name, description, and
  signup URL.
- API-key authentication metadata through `COMMANDCODE_API_KEY`.
- The local bridge endpoints:
  `http://127.0.0.1:8788/v1` for chat completions and
  `http://127.0.0.1:8788/v1/models` for model discovery.
- Hermes defaults: omit the temperature parameter via `OMIT_TEMPERATURE`, use
  a default maximum of 32,000 tokens, and use
  `deepseek/deepseek-v4-flash` as the auxiliary model.
- The fallback model identifiers used when live discovery is unavailable. The
  list is the provider's supported-model contract and mirrors the bundled
  catalog used by the bridge and configuration script.

`plugin.yaml` supplies package metadata only: plugin name
`commandcode-provider`, kind `model-provider`, version `0.2.0`, description,
and author. Runtime registration is performed by `__init__.py`, not by the
YAML file.

## Design patterns / abstractions

- **Hermes provider-profile adapter.** `ProviderProfile` is the boundary
  between Hermes' provider selection/configuration logic and this integration.
  The module constructs one immutable-style profile value and calls
  `register_provider(commandcode)` at import time; it has no request-handling
  state or business logic.
- **Local compatibility facade.** Hermes speaks its normal provider transport
  to `127.0.0.1:8788/v1`. The separate bridge translates that OpenAI-shaped
  contract into Command Code's `/alpha/generate` contract, keeping Command
  Code-specific protocol details out of the plugin profile.
- **Configuration-as-declaration.** URLs, authentication environment names,
  defaults, aliases, and model fallback identifiers are declarative profile
  fields. There are no Hermes source patches or provider-specific conditionals
  in this directory.
- **Single-source model catalog with fallbacks.** At runtime the bridge first
  loads the repository's installed `models.json`; it can query
  `/provider/v1/models` and falls back to that catalog. The profile's
  `fallback_models` gives Hermes a usable selection list independently of a
  successful live request.
- **Sentinel-based parameter policy.** `OMIT_TEMPERATURE` is passed to the
  Hermes provider abstraction rather than implemented locally. The bridge can
  translate a temperature if one is explicitly present in an incoming request,
  but this profile does not prescribe a provider temperature.

## Flow

1. Hermes discovers the plugin directory and imports `__init__.py`.
2. Import-time registration adds the `commandcode` profile and its aliases to
   Hermes' provider registry. Hermes uses the profile's local base URL,
   authentication key name, defaults, and fallback models when selecting this
   provider.
3. The installer places the profile files under
   `~/.hermes/plugins/model-providers/commandcode/`. The
   `hermes-commandcode` launcher ensures that the bridge is healthy (or starts
   it) before invoking Hermes; it injects `--provider commandcode` when the
   caller did not select another provider.
4. Hermes sends an OpenAI-compatible `GET /v1/models` or
   `POST /v1/chat/completions` request to the local bridge. The bridge also
   accepts the equivalent paths without `/v1` and exposes `/health`.
5. For model discovery, the bridge resolves credentials from the request's
   Bearer token, `COMMANDCODE_API_KEY`, or known auth files, then attempts
   `GET /provider/v1/models`. It normalizes returned entries to OpenAI model
   metadata and uses its bundled catalog on missing credentials, malformed
   data, or upstream failure.
6. For chat completions, the bridge authenticates the request, bounds and
   parses the JSON body, and converts it to an `/alpha/generate` payload. System
   and developer messages are combined, user/assistant/tool messages and tool
   definitions are mapped to Command Code structures, and `max_tokens`,
   `temperature`, `top_p`, `stop`, and `response_format` are forwarded where
   valid. The payload also includes the process working directory, runtime
   metadata, standard permission mode, and a streaming flag.
7. The bridge calls Command Code over `http.client` using the configured API
   base, a process-lifetime session ID, and Command Code headers. It parses
   either SSE or NDJSON upstream events.
8. Upstream text, reasoning, tool calls, finish state, and usage are translated
   back into OpenAI chat-completion chunks for streaming requests. For a
   non-streaming request, the same event stream is accumulated into one
   `chat.completion` response. Errors before response headers become HTTP
   errors; errors after a stream starts become an error finish chunk.

## Integration

### Hermes plugin and configuration

- `plugins/model-providers/commandcode/__init__.py` is the installed Hermes
  integration point. `plugin.yaml` identifies the package to the plugin
  loader; it does not duplicate the profile's endpoint or model settings.
- `scripts/configure_hermes.py` updates `~/.hermes/config.yaml` when invoked
  with `install.sh --configure`: it sets `model.provider` to `commandcode`,
  selects `deepseek/deepseek-v4-flash`, sets the local base URL, and writes a
  `providers.commandcode` entry with `chat_completions` transport,
  `COMMANDCODE_API_KEY`, the default model, and context lengths loaded from
  `models.json`. It backs up an existing config before writing and replaces an
  existing `commandcode` provider entry.
- The launcher has a lighter auto-configuration path: if a config exists and
  has no `providers.commandcode` entry, it adds one from the installed model
  catalog without changing an existing entry. The profile remains the native
  provider registration, so no Hermes patches are required.

### Bridge and process lifecycle

- `commandcode_bridge.py` is the runtime transport behind the profile. It
  defaults to loopback host `127.0.0.1` and port `8788`; non-loopback binding
  requires `COMMANDCODE_PROXY_ALLOW_REMOTE=1`.
- The bridge reads `COMMANDCODE_API_BASE` (default
  `https://api.commandcode.ai`) and optional header settings
  `COMMANDCODE_VERSION`, `COMMANDCODE_PROJECT_SLUG`, and
  `COMMANDCODE_ENVIRONMENT`. Credentials may come from
  `COMMANDCODE_API_KEY`, `~/.commandcode/auth.json`, or
  `~/.pi/agent/auth.json`.
- `bin/hermes-commandcode-bridge` is a bridge-only launcher. The main
  `bin/hermes-commandcode` launcher detects an already healthy bridge, prefers
  the user systemd service when active, otherwise starts a pidfile/log-backed
  `nohup` process, waits on `/health`, and then runs Hermes.
- `systemd/hermes-commandcode-bridge.service` is the optional persistent
  process manager. It runs the installed bridge on loopback, restarts it, and
  loads environment variables from `~/.hermes/.env`.
- `install.sh` installs the bridge, `models.json`, both plugin files, and both
  launchers into the locations consumed above. The runtime dependency is the
  Python standard library; the optional configuration helper requires PyYAML.
