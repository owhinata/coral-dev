#!/usr/bin/env bash
# deploy.sh — Auto-detect Coral Dev Board IP and deploy files via SCP.
#
# Environment variables:
#   CORAL_USER       SSH user (required)
#   CORAL_IP         IP address (empty = auto-detect via mdt)
#   CORAL_DEPLOY_DIR Remote deploy directory
#
# Usage: deploy.sh <local:remote> [...]
set -euo pipefail

: "${CORAL_USER:?CORAL_USER is required}"
: "${CORAL_DEPLOY_DIR:?CORAL_DEPLOY_DIR is required}"

IP="${CORAL_IP:-}"

# --- IP auto-detection via mdt ---
if [ -z "$IP" ]; then
    echo "CORAL_IP not set. Auto-detecting via mdt..."
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
    echo "Detected Coral Dev Board IP: ${IP}"
fi

# --- SSH connection test ---
SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=5)

echo "Connecting to ${CORAL_USER}@${IP}..."
if ! ssh "${SSH_OPTS[@]}" "${CORAL_USER}@${IP}" true 2>/dev/null; then
    echo "Error: Cannot connect to ${CORAL_USER}@${IP}" >&2
    echo "  - Verify board is powered on and network-connected" >&2
    echo "  - Set up SSH key: ssh-copy-id ${CORAL_USER}@${IP}" >&2
    exit 1
fi

ssh "${SSH_OPTS[@]}" "${CORAL_USER}@${IP}" "mkdir -p ${CORAL_DEPLOY_DIR}"

# --- SCP transfer ---
for mapping in "$@"; do
    local_path="${mapping%%:*}"
    remote_name="${mapping#*:}"
    if [ ! -f "$local_path" ]; then
        echo "Error: File not found: $local_path" >&2
        exit 1
    fi
    echo "  ${remote_name}"
    scp -q "${SSH_OPTS[@]}" "$local_path" "${CORAL_USER}@${IP}:${CORAL_DEPLOY_DIR}/${remote_name}"
done

echo "Deployed to ${IP}:${CORAL_DEPLOY_DIR}/"
