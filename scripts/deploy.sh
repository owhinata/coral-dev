#!/usr/bin/env bash
# deploy.sh — Deploy files to Coral Dev Board via scp.
#
# Uses mdt for device auto-detection and mdt's SSH key for authentication.
#
# Environment variables:
#   CORAL_DEPLOY_DIR  Remote deploy directory
#   CORAL_IP          IP address (optional, auto-detected via mdt if empty)
#
# Usage: deploy.sh <local:remote> [...]
set -euo pipefail

: "${CORAL_DEPLOY_DIR:?CORAL_DEPLOY_DIR is required}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

MDT_KEY="$HOME/.config/mdt/keys/mdt.key"
if [ ! -f "$MDT_KEY" ]; then
    echo "Error: mdt key not found at $MDT_KEY" >&2
    echo "  Run: mdt shell (to generate key on first connection)" >&2
    exit 1
fi

IP=$("$SCRIPT_DIR/resolve-ip.sh")

SSH_OPTS=(-i "$MDT_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5)

ssh "${SSH_OPTS[@]}" mendel@"${IP}" "mkdir -p ${CORAL_DEPLOY_DIR}"

# --- SCP transfer ---
for mapping in "$@"; do
    local_path="${mapping%%:*}"
    remote_name="${mapping#*:}"
    if [ ! -f "$local_path" ]; then
        echo "Error: File not found: $local_path" >&2
        exit 1
    fi
    echo "  ${remote_name}"
    scp -q "${SSH_OPTS[@]}" "$local_path" "mendel@${IP}:${CORAL_DEPLOY_DIR}/${remote_name}"
done

echo "Deployed to ${IP}:${CORAL_DEPLOY_DIR}/"
