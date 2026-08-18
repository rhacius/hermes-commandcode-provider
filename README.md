# Hermes Command Code Provider (v0.2)

A Hermes **model-provider plugin** for using Hermes Agent with a [Command Code](https://commandcode.ai/)
Go subscription — no `curl` subprocess, no tempfiles, no Hermes patches.

## Why this exists

Command Code Go subscriptions authenticate the CLI (`cmd`) but don't include
direct API access. This plugin runs a local OpenAI-compatible bridge backed by
your existing Command Code login — pure Python, stdlib only.

## What's improved over v0.1

| Feature | Original [MitoroMisaka](https://github.com/MitoroMisaka/hermes-commandcode-provider) | v0.2 (this fork) |
|---|---|---|
| **API transport** | `subprocess.Popen` + curl + 2 tempfiles/request | `http.client` — zero subprocess, zero tempfiles |
| **Sampling params** | Ignored (temperature, top_p, stop) | **Passed through to the model** |
| **response_format** | Ignored | **Passed through** (JSON mode, JSON schema) |
| **Session ID** | New UUID per request | **Persistent per bridge instance** (like CLI) |
| **Headers** | Hardcoded (`"0.24.1"`, `"hermes-cc"`) | **Configurable via env vars** |
| **Hermes patches** | 2 patches (doctor + model picker) | **Zero patches** — plugin stays within Hermes plugin API |
| **Dependencies** | Python + `curl` | **Python stdlib only** (no external deps) |
| **Code size** | ~690 lines | ~530 lines (simpler, faster) |

## Requirements

- macOS or Linux
- Hermes Agent v0.14.0 or newer
- Python 3
- A Command Code login or API key

Authenticate first:

```bash
cmd login
```

Or export an API key:

```bash
export COMMANDCODE_API_KEY="..."
```

The bridge also reads `~/.commandcode/auth.json` and `~/.pi/agent/auth.json`.

## Install

```bash
git clone https://github.com/your-fork/hermes-commandcode-provider.git
cd hermes-commandcode-provider
./install.sh --configure
```

The installer copies the bridge, plugin, and launcher to `~/.hermes/`. With
`--configure`, it also updates `~/.hermes/config.yaml` (backed up first).

**No Hermes source patches are applied.** The plugin registers as a native
`model-provider` and Hermes auto-discovers fallback models.

## Use

```bash
# Launch bridge + Hermes in one command:
hermes-commandcode

# Or start the bridge manually first, then Hermes normally:
hermes-commandcode-bridge
hermes

# One-shot test:
hermes -z 'Reply with exactly OK.'

# Switch model explicitly:
hermes --provider commandcode -m moonshotai/Kimi-K2.5 -z 'Reply with exactly OK.'
```

## Supported Models

The bridge fetches the live catalog from `api.commandcode.ai/provider/v1/models`
and falls back to a bundled catalog when offline.

| Model | Context |
|---|---|
| `claude-sonnet-5` | 1,000,000 |
| `claude-sonnet-4-6` | 1,000,000 |
| `claude-fable-5` | 1,000,000 |
| `claude-opus-5` | 1,000,000 |
| `claude-opus-4-8` | 1,000,000 |
| `claude-opus-4-7` | 1,000,000 |
| `claude-haiku-4-5-20251001` | 200,000 |
| `gpt-5.6-sol` | 1,050,000 |
| `gpt-5.6-terra` | 1,050,000 |
| `gpt-5.6-luna` | 1,050,000 |
| `gpt-5.5` | 200,000 |
| `gpt-5.4` | 400,000 |
| `gpt-5.3-codex` | 400,000 |
| `gpt-5.4-mini` | 400,000 |
| `moonshotai/Kimi-K3` | 1,000,000 |
| `moonshotai/Kimi-K2.7-Code` | 256,000 |
| `moonshotai/Kimi-K2.7-Code-Highspeed` | 262,000 |
| `moonshotai/Kimi-K2.6` | 256,000 |
| `moonshotai/Kimi-K2.5` | 256,000 |
| `zai-org/GLM-5.2` | 1,000,000 |
| `zai-org/GLM-5.2-Fast` | 1,000,000 |
| `zai-org/GLM-5.1` | 200,000 |
| `zai-org/GLM-5` | 200,000 |
| `MiniMaxAI/MiniMax-M3` | 1,000,000 |
| `MiniMaxAI/MiniMax-M2.7` | 200,000 |
| `MiniMaxAI/MiniMax-M2.5` | 200,000 |
| `deepseek/deepseek-v4-pro` | 1,000,000 |
| `deepseek/deepseek-v4-flash` | 1,000,000 |
| `Qwen/Qwen3.8-Max` | 1,000,000 |
| `Qwen/Qwen3.7-Max` | 1,000,000 |
| `Qwen/Qwen3.7-Plus` | 1,000,000 |
| `Qwen/Qwen3.7-Flash` | 1,000,000 |
| `Qwen/Qwen3.6-Max-Preview` | 200,000 |
| `Qwen/Qwen3.6-Plus` | 200,000 |
| `stepfun/Step-3.7-Flash` | 256,000 |
| `stepfun/Step-3.5-Flash` | 1,000,000 |
| `tencent/hy3-paid` | 262,144 |
| `nvidia/nemotron-3-ultra-550b-a55b` | 1,000,000 |
| `sakana/fugu-ultra` | 1,000,000 |
| `google/gemini-3.6-flash` | 1,000,000 |
| `google/gemini-3.5-flash` | 1,000,000 |
| `google/gemini-3.5-flash-lite` | 1,000,000 |
| `google/gemini-3.1-flash-lite` | 1,000,000 |
| `xiaomi/mimo-v2.5-pro` | 1,000,000 |
| `xiaomi/mimo-v2.5` | 1,000,000 |
| `thinkingmachines/inkling` | 256,000 |
| `thinkingmachines/inkling-small` | 1,000,000 |
| `poolside/laguna-s-2.1-free` | 256,000 |
| `meta/muse-spark-1.1` | 1,048,576 |
| `meta/muse-spark-1.2` | 1,048,576 |
| `meta/muse-spark-1.2-contributor` | 1,048,576 |
| `xai/grok-4.5` | 500,000 |

## Configuration

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `COMMANDCODE_API_KEY` | — | API key (overrides auth files) |
| `COMMANDCODE_API_BASE` | `https://api.commandcode.ai` | API endpoint |
| `COMMANDCODE_VERSION` | `0.24.1` | `x-command-code-version` header |
| `COMMANDCODE_PROJECT_SLUG` | `hermes-agent` | `x-project-slug` header |
| `COMMANDCODE_ENVIRONMENT` | `production` | `x-cli-environment` header |
| `COMMANDCODE_PROXY_HOST` | `127.0.0.1` | Bridge listen address |
| `COMMANDCODE_PROXY_PORT` | `8788` | Bridge listen port |
| `COMMANDCODE_PROXY_VERBOSE` | — | Enable request logging |
| `HERMES_COMMANDCODE_PROXY_LOG` | `~/.hermes/commandcode_bridge.log` | Log file path |

## Development

```bash
# Offline secret scan (stdlib; prints only masked values)
python3 scripts/check_secrets.py --self-test
python3 scripts/check_secrets.py

# Install the pre-commit hook for this checkout
./scripts/install-git-hooks.sh
```

The hook runs `scripts/check_secrets.py --staged` and, when installed,
`gitleaks protect --staged`. CI (`.github/workflows/secret-scan.yml`) runs
the same stdlib scanner plus Gitleaks against the full history.

## Smoke Test

```bash
./scripts/smoke_test.sh
```

Tests:
- `/v1/models` returns model metadata with context lengths
- Non-streaming chat with usage
- Streaming chat with final `usage` chunk
- Temperature passthrough
- Tool call translation
- Reasoning content preservation

## Files Installed

```
~/.hermes/commandcode_bridge.py
~/.hermes/models.json
~/.hermes/plugins/model-providers/commandcode/__init__.py
~/.hermes/plugins/model-providers/commandcode/plugin.yaml
~/.local/bin/hermes-commandcode
~/.local/bin/hermes-commandcode-bridge
```

## License

MIT

## Systemd service (recommended)

For a persistent bridge that auto-starts with your system:

```bash
# Install the service
cp systemd/hermes-commandcode-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now hermes-commandcode-bridge.service

# Verify
systemctl --user status hermes-commandcode-bridge.service
curl http://127.0.0.1:8788/health
```

The service reads the API key from `~/.hermes/.env` (line: `COMMANDCODE_API_KEY=...`).

When the systemd service is running, `hermes-commandcode` detects it automatically
and skips starting the bridge ad-hoc.
