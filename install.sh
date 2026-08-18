#!/usr/bin/env bash
# Hermes Command Code bridge installer (v0.2 — no patches, no curl dependency)
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hermes_home="${HERMES_HOME:-$HOME/.hermes}"
bin_dir="${HOME}/.local/bin"
configure=0

for arg in "$@"; do
  case "$arg" in
    --configure) configure=1 ;;
    -h|--help)
      echo "Usage: ./install.sh [--configure]"
      echo ""
      echo "  --configure   Also update ~/.hermes/config.yaml for the bridge"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

echo "=== Installing Hermes Command Code Provider v0.2 ==="

# 1. Install bridge
mkdir -p "$hermes_home/plugins/model-providers/commandcode" "$bin_dir"
install -m 755 "$repo_dir/commandcode_bridge.py" "$hermes_home/commandcode_bridge.py"
install -m 644 "$repo_dir/plugins/model-providers/commandcode/__init__.py" \
  "$hermes_home/plugins/model-providers/commandcode/__init__.py"
install -m 644 "$repo_dir/plugins/model-providers/commandcode/plugin.yaml" \
  "$hermes_home/plugins/model-providers/commandcode/plugin.yaml"
install -m 755 "$repo_dir/bin/hermes-commandcode" "$bin_dir/hermes-commandcode"
install -m 755 "$repo_dir/bin/hermes-commandcode-bridge" "$bin_dir/hermes-commandcode-bridge"
install -m 644 "$repo_dir/models.json" "$hermes_home/models.json"

echo "  ✓ Bridge:       $hermes_home/commandcode_bridge.py"
echo "  ✓ Models:       $hermes_home/models.json (single source of truth)"
echo "  ✓ Plugin:       $hermes_home/plugins/model-providers/commandcode/"
echo "  ✓ Launcher:     $bin_dir/hermes-commandcode"
echo "  ✓ Bridge-only:  $bin_dir/hermes-commandcode-bridge"

# 2. Configure Hermes
if [ "$configure" = 1 ]; then
  echo ""
  echo "=== Configuring ~/.hermes/config.yaml ==="
  python3 "$repo_dir/scripts/configure_hermes.py"
  echo ""
  echo "  ✓ No Hermes patches applied (not needed)"
fi

echo ""
echo "=== Installed ==="
echo ""
echo "Next steps:"
echo "  1. Authenticate with Command Code:"
echo "     cmd login"
echo "     # or: export COMMANDCODE_API_KEY=..."
echo ""
echo "  2. Start Hermes with the bridge:"
echo "     hermes-commandcode"
echo ""
echo "  3. Or start the bridge manually:"
echo "     hermes-commandcode-bridge"
echo ""
echo "  4. One-shot test:"
echo "     hermes-commandcode -z 'Reply with exactly OK.'"
echo ""
echo "  5. Check that auth is working:"
echo "     curl http://127.0.0.1:8788/v1/health"
echo "     curl http://127.0.0.1:8788/v1/models"
echo ""
