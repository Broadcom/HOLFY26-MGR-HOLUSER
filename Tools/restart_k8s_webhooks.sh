#!/bin/bash

# Script to restart Kubernetes webhooks after extracting credentials from vCenter
# This script:
# 1. SSH to vCenter and run decryptK8Pwd.py
# 2. Parse output to extract IP and Password
# 3. Use those credentials to restart the webhooks
#
# Usage: ./restart_k8s_webhooks.sh [vcenter_host]
# Example: ./restart_k8s_webhooks.sh vc-wld01-a.site-a.vcf.lab
# If no parameter is provided, it will attempt to run the command on vc-wld01-a.site-a.vcf.lab

set -e  # Exit on error

# Configuration
VCENTER_HOST="${1:-vc-wld01-a.site-a.vcf.lab}"
VCENTER_USER="root"
DECRYPT_CMD="/usr/lib/vmware-wcp/decryptK8Pwd.py"
CREDS_FILE="/home/holuser/creds.txt"

# Helper function to execute SSH with fallback to sshpass
ssh_with_fallback() {
    local user=$1
    local host=$2
    shift 2
    local cmd=("$@")
    
    # Try key-based authentication first
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "${user}@${host}" "${cmd[@]}" 2>/dev/null; then
        return 0
    fi
    
    # Fall back to sshpass if key auth fails
    if [[ -f "${CREDS_FILE}" ]]; then
        local password=$(cat "${CREDS_FILE}")
        /usr/bin/sshpass -p "${password}" ssh "${user}@${host}" "${cmd[@]}"
    else
        echo "ERROR: Key-based authentication failed and credentials file not found at ${CREDS_FILE}"
        return 1
    fi
}

echo "=========================================="
echo "Connecting to vCenter to retrieve credentials..."
echo "vCenter Host: ${VCENTER_HOST}"
echo "=========================================="

# SSH to vCenter and capture the output
DECRYPT_OUTPUT=$(ssh_with_fallback "${VCENTER_USER}" "${VCENTER_HOST}" "${DECRYPT_CMD}")

# Parse the output to extract IP and Password
nodeIP=$(echo "${DECRYPT_OUTPUT}" | grep "^IP:" | awk '{print $2}')
nodePwd=$(echo "${DECRYPT_OUTPUT}" | grep "^PWD:" | awk '{print $2}')

# Validate that we got the values
if [[ -z "${nodeIP}" ]]; then
    echo "ERROR: Failed to extract IP from vCenter output"
    echo "Raw output:"
    echo "${DECRYPT_OUTPUT}"
    exit 1
fi

if [[ -z "${nodePwd}" ]]; then
    echo "ERROR: Failed to extract PWD from vCenter output"
    exit 1
fi

echo "Successfully extracted credentials from vCenter"
echo "Node IP: ${nodeIP}"
echo "Password retrieved: $(echo "${nodePwd}" | sed 's/./*/g')"
echo ""

# Execute the kubectl commands to restart webhooks
# The following two must be restarted for HOL-2636 Workload Supervisor cluster when the certificates have expired
# the restart triggers the regenerationo fthe certificates, allowing for vm creation in the lab
echo "=========================================="
echo "Restarting storage-quota-webhook..."
echo "=========================================="
ssh_with_fallback "root" "${nodeIP}" "kubectl -n kube-system rollout restart deploy storage-quota-webhook"

echo ""
echo "=========================================="
echo "Restarting cns-storage-quota-extension..."
echo "=========================================="

ssh_with_fallback "root" "${nodeIP}" "kubectl -n kube-system rollout restart deploy cns-storage-quota-extension"

echo ""
echo "=========================================="
echo "✓ Successfully completed webhook restarts"
echo "=========================================="
