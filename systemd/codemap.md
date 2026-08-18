# systemd/

## Responsibility

`hermes-commandcode-bridge.service` is the user-level process-supervision
definition for the local Command Code bridge. It keeps the installed
`~/.hermes/commandcode_bridge.py` available at `127.0.0.1:8788`, restarts it
after failure, and makes it start with the user's `default.target`. The unit
does not implement proxying, authentication, or model translation; those are
responsibilities of `commandcode_bridge.py`.

## Design patterns/abstractions

- **Declarative user service:** The unit is intended for
  `~/.config/systemd/user/` and uses `%h` so its executable and environment
  file resolve relative to the user's home directory. `WantedBy=default.target`
  makes it opt-in through `systemctl --user enable` rather than a system-wide
  boot service.
- **Supervised long-lived process:** `Type=simple` treats the Python process
  started by `ExecStart` as the service. `Restart=always` with
  `RestartSec=3` provides recovery after crashes or other exits.
- **Environment boundary:** `EnvironmentFile=%h/.hermes/.env` supplies runtime
  configuration such as `COMMANDCODE_API_KEY`; the unit additionally forces
  `COMMANDCODE_PROXY_VERBOSE=1` for service-side request/error logging.
- **Fixed loopback endpoint:** `ExecStart` explicitly binds `127.0.0.1` on
  port `8788`, matching the provider's OpenAI-compatible base URL while
  avoiding a network-facing API-key endpoint. It invokes the Python bridge
  directly, not `bin/hermes-commandcode-bridge`.
- **Network ordering, not network ownership:** `After=` and `Wants=` for
  `network-online.target` order startup around network availability; the
  bridge itself owns the upstream HTTP(S) connection and local HTTP server.

## Flow

1. Install the unit into the per-user systemd directory, run
   `systemctl --user daemon-reload`, and enable/start
   `hermes-commandcode-bridge.service`. The user manager then loads
   `%h/.hermes/.env`, applies the verbose flag, and executes
   `%h/.hermes/commandcode_bridge.py --host 127.0.0.1 --port 8788`.
2. `commandcode_bridge.py` creates a threaded HTTP server and maintains one
   session UUID for the lifetime of that bridge process. Its `/health` route
   reports readiness; `/models` and `/v1/models` return the live Command Code
   model catalog (or the local fallback catalog).
3. Hermes sends OpenAI-compatible requests to `/v1/chat/completions` (the
   bridge also accepts the path without `/v1`). The bridge resolves the API
   key, translates messages/tools and supported sampling/response-format
   options into an `/alpha/generate` request, and sends Command Code headers
   including the session and project metadata.
4. Upstream events are consumed as SSE or NDJSON. Streaming requests are
   emitted as OpenAI `chat.completion.chunk` SSE events; non-streaming requests
   collect the same events into one `chat.completion` response. Text,
   reasoning, tool calls, finish reasons, and usage are mapped at this layer.
5. If the bridge exits, systemd waits three seconds and starts it again. A
   service stop or user-manager shutdown terminates the process instead of
   invoking the ad-hoc launcher fallback.

## Integration

- **Installed bridge:** `install.sh` places the executable at
  `~/.hermes/commandcode_bridge.py`. The service's `%h` paths therefore
  assume the normal `HERMES_HOME` layout; changing `HERMES_HOME` does not
  change this unit's paths.
- **Hermes provider:** The Command Code provider profile and generated
  `config.yaml` use `http://127.0.0.1:8788/v1` as `base_url` and
  `/v1/models` as the model endpoint. `/health` is the service readiness
  check; it is intentionally outside the `/v1` OpenAI route namespace.
- **Combined launcher:** `bin/hermes-commandcode` first probes the configured
  `http://$host:$port/health`. If it is not ready but
  `systemctl --user is-active hermes-commandcode-bridge.service` succeeds, it
  waits for this service. Otherwise it starts the bridge ad hoc with `nohup`,
  a pidfile, and a log file. Once ready, the launcher runs Hermes and injects
  `--provider commandcode` unless the caller supplied a provider.
- **Standalone launcher:** `bin/hermes-commandcode-bridge` is an alternate
  direct launcher for the same Python file. The systemd unit bypasses it, so
  its `PYTHON`, `HERMES_HOME`, and host/port environment handling do not apply
  to the systemd `ExecStart` command.
- **Configuration alignment:** The unit's fixed loopback address and port
  must match the provider and launcher settings. The API key must be present
  in the referenced `.env` (or otherwise available to the bridge); the
  bridge also supports its normal environment/auth-file key resolution for
  requests and model discovery.
