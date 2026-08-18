#!/usr/bin/env python3
"""Configure Hermes config.yaml for the Command Code bridge."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path


def _load_models() -> dict[str, int]:
    """Load model catalog from models.json."""
    repo = Path(__file__).resolve().parents[1]
    models_path = repo / "models.json"
    if models_path.exists():
        try:
            raw = models_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return {
                    item["id"]: item["context_length"]
                    for item in parsed
                    if isinstance(item, dict) and "id" in item and "context_length" in item
                }
        except Exception:
            pass
    # Fallback (should not happen in normal use)
    return {
"claude-sonnet-5": 1000000,
        "claude-sonnet-4-6": 1000000,
        "claude-fable-5": 1000000,
        "claude-opus-5": 1000000,
        "claude-opus-4-8": 1000000,
        "claude-opus-4-7": 1000000,
        "claude-haiku-4-5-20251001": 200000,
        "gpt-5.6-sol": 1050000,
        "gpt-5.6-terra": 1050000,
        "gpt-5.6-luna": 1050000,
        "gpt-5.5": 200000,
        "gpt-5.4": 400000,
        "gpt-5.3-codex": 400000,
        "gpt-5.4-mini": 400000,
        "moonshotai/Kimi-K3": 1000000,
        "moonshotai/Kimi-K2.7-Code": 256000,
        "moonshotai/Kimi-K2.7-Code-Highspeed": 262000,
        "moonshotai/Kimi-K2.6": 256000,
        "moonshotai/Kimi-K2.5": 256000,
        "zai-org/GLM-5.2": 1000000,
        "zai-org/GLM-5.2-Fast": 1000000,
        "zai-org/GLM-5.1": 200000,
        "zai-org/GLM-5": 200000,
        "MiniMaxAI/MiniMax-M3": 1000000,
        "MiniMaxAI/MiniMax-M2.7": 200000,
        "MiniMaxAI/MiniMax-M2.5": 200000,
        "deepseek/deepseek-v4-pro": 1000000,
        "deepseek/deepseek-v4-flash": 1000000,
        "Qwen/Qwen3.8-Max": 1000000,
        "Qwen/Qwen3.7-Max": 1000000,
        "Qwen/Qwen3.7-Plus": 1000000,
        "Qwen/Qwen3.7-Flash": 1000000,
        "Qwen/Qwen3.6-Max-Preview": 200000,
        "Qwen/Qwen3.6-Plus": 200000,
        "stepfun/Step-3.7-Flash": 256000,
        "stepfun/Step-3.5-Flash": 1000000,
        "tencent/hy3-paid": 262144,
        "nvidia/nemotron-3-ultra-550b-a55b": 1000000,
        "sakana/fugu-ultra": 1000000,
        "google/gemini-3.6-flash": 1000000,
        "google/gemini-3.5-flash": 1000000,
        "google/gemini-3.5-flash-lite": 1000000,
        "google/gemini-3.1-flash-lite": 1000000,
        "xiaomi/mimo-v2.5-pro": 1000000,
        "xiaomi/mimo-v2.5": 1000000,
        "thinkingmachines/inkling": 256000,
        "thinkingmachines/inkling-small": 1000000,
        "poolside/laguna-s-2.1-free": 256000,
        "meta/muse-spark-1.1": 1048576,
        "meta/muse-spark-1.2": 1048576,
        "meta/muse-spark-1.2-contributor": 1048576,
        "xai/grok-4.5": 500000,
    }


def main() -> int:
    try:
        import yaml
    except ImportError:
        print("PyYAML is required. Install via: pip install pyyaml", file=sys.stderr)
        return 1

    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    config_path = hermes_home / "config.yaml"

    config: dict = {}
    backup_path: Path | None = None
    if config_path.exists():
        backup_path = config_path.with_suffix(
            config_path.suffix + f".before-commandcode-{time.strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copy2(config_path, backup_path)
        print(f"Backup: {backup_path}")
        with config_path.open(encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}

    if not isinstance(config, dict):
        config = {}

    model_cfg = config.setdefault("model", {})
    model_cfg["provider"] = "commandcode"
    model_cfg["default"] = "deepseek/deepseek-v4-flash"
    model_cfg["base_url"] = "http://127.0.0.1:8788/v1"

    models_dict = _load_models()
    providers = config.setdefault("providers", {})
    providers["commandcode"] = {
        "name": "Command Code",
        "base_url": "http://127.0.0.1:8788/v1",
        "key_env": "COMMANDCODE_API_KEY",
        "transport": "chat_completions",
        "model": "deepseek/deepseek-v4-flash",
        "default_model": "deepseek/deepseek-v4-flash",
        "models": {model: {"context_length": ctx} for model, ctx in models_dict.items()},
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=False, allow_unicode=True)

    print(f"Updated {config_path}")
    if backup_path:
        print(f"  Backup saved: {backup_path}")
    print("  ⚠️ This OVERWRITES any existing 'commandcode' provider entry.")
    print("  ⚠️ Re-apply custom context lengths if you had any.")
    print("No Hermes patches applied — plugin uses fallback_models natively.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
