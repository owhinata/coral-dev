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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

MDT_KEY="$HOME/.config/mdt/keys/mdt.key"
if [ ! -f "$MDT_KEY" ]; then
    echo "Error: mdt key not found at $MDT_KEY" >&2
    echo "  Run: mdt shell (to generate key on first connection)" >&2
    exit 1
fi

IP=$("$SCRIPT_DIR/resolve-ip.sh")

SSH_OPTS=(-i "$MDT_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5)

echo "Running on Coral Dev Board (${IP}): ${CMD}"
ssh "${SSH_OPTS[@]}" "mendel@${IP}" "${CMD}"
