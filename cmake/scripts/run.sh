#!/usr/bin/env bash
# run.sh — Execute a command on Coral Dev Board via ssh.
#
# Uses mdt for device auto-detection and mdt's SSH key for authentication.
#
# Environment variables:
#   CORAL_IP  IP address (optional, auto-detected via mdt if empty)
#
# Usage: run.sh <command>
set -euo pipefail

CMD="$1"

MDT_KEY="$HOME/.config/mdt/keys/mdt.key"
if [ ! -f "$MDT_KEY" ]; then
    echo "Error: mdt key not found at $MDT_KEY" >&2
    echo "  Run: mdt shell (to generate key on first connection)" >&2
    exit 1
fi

IP="${CORAL_IP:-}"

# --- IP auto-detection via mdt ---
if [ -z "$IP" ]; then
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
fi

SSH_OPTS=(-i "$MDT_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5)

echo "Running on Coral Dev Board (${IP}): ${CMD}"
ssh "${SSH_OPTS[@]}" "mendel@${IP}" "${CMD}"
