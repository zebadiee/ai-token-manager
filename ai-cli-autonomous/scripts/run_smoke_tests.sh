#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="${TMPDIR:-/tmp}/ai_cli_smoke"
mkdir -p "$LOG_DIR"

IMMERSIVE_LOG="$LOG_DIR/immersive.log"
LEGACY_LOG="$LOG_DIR/legacy.log"
FAILOVER_LOG="$LOG_DIR/failover.log"

run_cli() {
  local log_file="$1"
  shift
  "$@" > "$log_file" 2>&1
}

echo "🧪 Testing immersive mode..."
run_cli "$IMMERSIVE_LOG" env AI_CLI_FORCE_IMMERSIVE=1 python3 autonomous_ai_cli.py < tests/immersive_chat.txt
if ! tr -d '\r' < "$IMMERSIVE_LOG" | grep -q '💬 Immersive Chat'; then
  echo "❌ Immersive introduction missing" >&2
  exit 1
fi
if ! tr -d '\r' < "$IMMERSIVE_LOG" | grep -q 'You'; then
  echo "❌ Immersive user panel missing" >&2
  exit 1
fi
echo "✅ Immersive OK"

echo "🧪 Testing legacy fallback..."
run_cli "$LEGACY_LOG" env AI_CLI_FORCE_IMMERSIVE=0 python3 autonomous_ai_cli.py < tests/legacy_chat.txt
if tr -d '\r' < "$LEGACY_LOG" | grep -q '💬 Immersive Chat'; then
  echo "❌ Legacy run triggered immersive intro" >&2
  exit 1
fi
if ! tr -d '\r' < "$LEGACY_LOG" | grep -q 'Autonomous AI CLI is ready'; then
  echo "❌ Legacy run did not reach interactive prompt" >&2
  exit 1
fi
echo "✅ Legacy OK"

echo "🧪 Testing failover rendering..."
run_cli "$FAILOVER_LOG" python3 autonomous_ai_cli.py <<'EOF'
quick Force failover test
exit
EOF
if ! tr -d '\r' < "$FAILOVER_LOG" | grep -q '⚠️'; then
  echo "❌ Failover warnings not surfaced" >&2
  exit 1
fi
echo "✅ Failover OK"

echo "🎉 Smoke tests passed (logs in $LOG_DIR)"
