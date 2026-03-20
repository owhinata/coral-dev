#!/usr/bin/env bash
# run.sh — Execute a command on Coral Dev Board via SSH.
#
# Environment variables:
#   CORAL_USER  SSH user (required)
#   CORAL_IP    IP address (empty = auto-detect via mdt)
#
# Usage: run.sh <command>
set -euo pipefail

: "${CORAL_USER:?CORAL_USER is required}"

CMD="$1"
IP="${CORAL_IP:-}"

# --- IP auto-detection via mdt ---
if [ -z "$IP" ]; then
    if ! command -v mdt &>/dev/null; then
        echo "Error: mdt not found. Install: pip install mendel-development-tool" >&2
        echo "  Or set manually: cmake -DCORAL_IP=<ip>" >&2
        exit 1
    fi

    IP=$(mdt devices 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
    if [ -z "$IP" ]; then
        echo "Error: No Coral device found via mdt." >&2
        echo "  - Is the board connected via USB?" >&2
        echo "  - Or set manually: cmake -DCORAL_IP=<ip>" >&2
        exit 1
    fi
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=5)

echo "Running on Coral Dev Board (${IP}): ${CMD}"
ssh -t "${SSH_OPTS[@]}" "${CORAL_USER}@${IP}" "${CMD}"
