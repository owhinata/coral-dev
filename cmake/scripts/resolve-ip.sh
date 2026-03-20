#!/usr/bin/env bash
# resolve-ip.sh — Resolve Coral Dev Board IP with caching.
#
# Outputs the IP address to stdout.
# Caches the result in <project-root>/.coral-ip for 5 minutes.
#
# Environment variables:
#   CORAL_IP  IP address (optional, skips detection if set)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CACHE_FILE="$PROJECT_ROOT/.coral-ip"
CACHE_TTL=300  # seconds

# --- Explicit IP ---
if [ -n "${CORAL_IP:-}" ]; then
    echo "$CORAL_IP"
    exit 0
fi

# --- Cached IP (valid if cache file exists and is fresh) ---
if [ -f "$CACHE_FILE" ]; then
    age=$(( $(date +%s) - $(stat -c %Y "$CACHE_FILE") ))
    if [ "$age" -lt "$CACHE_TTL" ]; then
        cached_ip=$(cat "$CACHE_FILE")
        if [ -n "$cached_ip" ]; then
            echo "$cached_ip"
            exit 0
        fi
    fi
fi

# --- Auto-detect via mdt ---
if ! command -v mdt &>/dev/null; then
    echo "Error: mdt not found. Install: pip install mendel-development-tool" >&2
    echo "  Or set: CORAL_IP=<ip>" >&2
    exit 1
fi

IP=$(mdt devices 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
if [ -z "$IP" ]; then
    echo "Error: No Coral device found via mdt." >&2
    echo "  - Is the board connected via USB?" >&2
    echo "  - Or set: CORAL_IP=<ip>" >&2
    exit 1
fi

echo "$IP" > "$CACHE_FILE"
echo "Detected Coral Dev Board IP: ${IP}" >&2
echo "$IP"
