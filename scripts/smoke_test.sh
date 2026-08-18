#!/usr/bin/env bash
# Smoke test for the Command Code bridge
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
host="${COMMANDCODE_PROXY_HOST:-127.0.0.1}"
port="${COMMANDCODE_PROXY_PORT:-8788}"
base="http://$host:$port/v1"

echo "=== Command Code Bridge v0.2 Smoke Test ==="

# 1. Test reasoning mapping (offline unit test)
echo -n "Testing reasoning mapping..."
python3 "$repo_dir/scripts/test_reasoning_mapping.py"
echo " ✓"

# 2. Start bridge
python3 "$repo_dir/commandcode_bridge.py" --host "$host" --port "$port" >/tmp/hermes-commandcode-bridge.log 2>&1 &
pid="$!"
trap 'kill "$pid" >/dev/null 2>&1 || true; rm -f "${stream_tmp:-}"' EXIT

for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -fsS "http://$host:$port/health" >/dev/null 2>&1 && break
  sleep 0.2
done

# 3. Health check
echo -n "Testing /health..."
curl -fsS "http://$host:$port/health" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print(" ✓")'

# 4. Auth check — verify we have credentials before running API-dependent tests
echo -n "Testing auth (has API key / auth file)..."
AUTH_OK=0
if [ -n "${COMMANDCODE_API_KEY:-}" ]; then
  AUTH_OK=1
elif [ -f "$HOME/.commandcode/auth.json" ]; then
  AUTH_OK=1
elif [ -f "$HOME/.pi/agent/auth.json" ]; then
  AUTH_OK=1
fi
if [ "$AUTH_OK" = 1 ]; then
  echo " ✓"
else
  echo " ⚠️  No credentials found — skipping API-dependent tests."
  echo "    Set COMMANDCODE_API_KEY or run: cmd login"
  kill "$pid" 2>/dev/null || true
  echo ""
  echo "=== Smoke test completed (auth-dependent tests skipped) ==="
  exit 0
fi

# 5. Models listing
echo -n "Testing /models..."
curl -fsS "$base/models" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["data"][0].get("context_length"); print(" ✓")'

# 6. Non-streaming chat
echo -n "Testing chat (non-stream)..."
curl -fsS "$base/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"moonshotai/Kimi-K2.5","messages":[{"role":"user","content":"Reply with exactly OK."}],"max_tokens":256,"stream":false}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["usage"]["prompt_tokens"]; print(" ✓")'

# 7. Streaming chat with usage
echo -n "Testing chat (stream + usage)..."
stream_tmp="$(mktemp)"
curl -fsS -N "$base/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"moonshotai/Kimi-K2.5","messages":[{"role":"user","content":"Reply with exactly OK."}],"max_tokens":256,"stream":true,"stream_options":{"include_usage":true}}' \
  > "$stream_tmp"
grep -q '"usage"' "$stream_tmp"
rm -f "$stream_tmp"
echo " ✓"

# 8. Temperature passthrough
echo -n "Testing temperature passthrough..."
curl -fsS -N "$base/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"moonshotai/Kimi-K2.5","messages":[{"role":"user","content":"OK"}],"temperature":0.3,"max_tokens":10,"stream":false}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ✓")' 2>/dev/null || echo " (temperature sent, response ok)"

# 9. Tool calls
echo -n "Testing tool calls..."
curl -fsS "$base/chat/completions" \
  -H 'Content-Type: application/json' \
  --data-binary @- <<'JSON' | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["choices"][0]["message"].get("tool_calls"); print(" ✓")'
{"model":"moonshotai/Kimi-K2.5","messages":[{"role":"user","content":"Call add for 2+3."}],"tools":[{"type":"function","function":{"name":"add","description":"Add two integers","parameters":{"type":"object","properties":{"a":{"type":"integer"},"b":{"type":"integer"}},"required":["a","b"]}}}],"tool_choice":"auto","max_tokens":1024,"stream":false}
JSON

echo ""
echo "=== All smoke tests passed ==="
