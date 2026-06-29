#!/bin/bash
# Author: Burke Azbill
# Version: 1.2
# Date: 2026-06-29
# Script to delete old certificates and restart Kubernetes webhooks after extracting credentials from vCenter
# This script:
# 1. SSH to vCenter and run decryptK8Pwd.py
# 2. Parse output to extract IP and Password
# 3. Use those credentials to delete certificates and restart the webhooks
# 4. Retries SSH to the Supervisor node (MAX_SUP_ATTEMPTS, SUP_RETRY_DELAY seconds each) because
#    the Supervisor VIP may not accept SSH immediately after NIC reconnection.
#
# Usage: ./restart_k8s_webhooks.sh [vcenter_host]
# Example: ./restart_k8s_webhooks.sh vc-wld01-a.site-a.vcf.lab
# If no parameter is provided, it will attempt to run the command on vc-wld01-a.site-a.vcf.lab

# Configuration
VCENTER_HOST="${1:-vc-wld01-a.site-a.vcf.lab}"
VCENTER_USER="root"
DECRYPT_CMD="/usr/lib/vmware-wcp/decryptK8Pwd.py"
CREDS_FILE="/home/holuser/creds.txt"
LOG_FILE="/lmchol/hol/labstartup.log"
MAX_VC_ATTEMPTS=5
MAX_SUP_ATTEMPTS=6
SUP_RETRY_DELAY=30

# Helper function to execute SSH with fallback to sshpass
ssh_with_fallback() {
    local user=$1
    local host=$2
    shift 2
    local cmd=("$@")
    # clear stale ssh keys before proceeding
    ssh-keygen -R "${host}" 2>/dev/null

    if ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o BatchMode=yes "${user}@${host}" "${cmd[@]}" 2>/dev/null; then
        return 0
    fi
    
    # Fall back to sshpass if key auth fails
    if [[ -f "${CREDS_FILE}" ]]; then
        local password
        password=$(cat "${CREDS_FILE}")
        /usr/bin/sshpass -p "${password}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 "${user}@${host}" "${cmd[@]}"
    else
        echo "ERROR: Key-based auth failed and credentials file not found at ${CREDS_FILE}" >> "${LOG_FILE}"
        return 1
    fi
}

# Run a kubectl command on the Supervisor node via SSH, with retry.
# The Supervisor VIP may not be SSH-ready immediately after power-on or NIC reconnection.
run_on_supervisor() {
    local description="$1"
    local cmd="$2"
    local attempt=0
    while [[ $attempt -lt $MAX_SUP_ATTEMPTS ]]; do
        attempt=$((attempt + 1))
        echo "  ${description} (attempt ${attempt}/${MAX_SUP_ATTEMPTS})..." >> "${LOG_FILE}"
        if /usr/bin/sshpass -p "${nodePwd}" ssh \
            -o StrictHostKeyChecking=accept-new \
            -o UserKnownHostsFile=/dev/null \
            -o ConnectTimeout=15 \
            "root@${nodeIP}" "${cmd}" >> "${LOG_FILE}" 2>&1; then
            return 0
        fi
        if [[ $attempt -lt $MAX_SUP_ATTEMPTS ]]; then
            echo "  Attempt ${attempt} failed, retrying in ${SUP_RETRY_DELAY}s..." >> "${LOG_FILE}"
            sleep "${SUP_RETRY_DELAY}"
        fi
    done
    echo "WARNING: ${description} failed after ${MAX_SUP_ATTEMPTS} attempts — continuing" >> "${LOG_FILE}"
    return 1
}

echo "==========================================" >> "${LOG_FILE}"
echo "Connecting to vCenter to retrieve credentials..." >> "${LOG_FILE}"
echo "vCenter Host: ${VCENTER_HOST}" >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"

# SSH to vCenter and capture output, with retry
DECRYPT_OUTPUT=""
vc_attempt=0
while [[ $vc_attempt -lt $MAX_VC_ATTEMPTS ]]; do
    vc_attempt=$((vc_attempt + 1))
    echo "vCenter SSH attempt ${vc_attempt}/${MAX_VC_ATTEMPTS}..." >> "${LOG_FILE}"
    if DECRYPT_OUTPUT=$(ssh_with_fallback "${VCENTER_USER}" "${VCENTER_HOST}" "${DECRYPT_CMD}" 2>&1); then
        echo "Successfully connected to vCenter" >> "${LOG_FILE}"
        break
    fi
    DECRYPT_OUTPUT=""
    if [[ $vc_attempt -lt $MAX_VC_ATTEMPTS ]]; then
        echo "vCenter connection failed, retrying in 30s..." >> "${LOG_FILE}"
        sleep 30
    fi
done

if [[ -z "${DECRYPT_OUTPUT}" ]]; then
    echo "ERROR: Could not connect to vCenter after ${MAX_VC_ATTEMPTS} attempts — exiting" >> "${LOG_FILE}"
    exit 1
fi

# Parse the output to extract IP and Password
nodeIP=$(echo "${DECRYPT_OUTPUT}" | grep "^IP:" | awk '{print $2}')
nodePwd=$(echo "${DECRYPT_OUTPUT}" | grep "^PWD:" | awk '{print $2}')

# Validate that we got the values
if [[ -z "${nodeIP}" ]]; then
    echo "ERROR: Failed to extract IP from vCenter output" >> "${LOG_FILE}"
    echo "Raw output:" >> "${LOG_FILE}"
    echo "${DECRYPT_OUTPUT}" >> "${LOG_FILE}"
    exit 1
fi

if [[ -z "${nodePwd}" ]]; then
    echo "ERROR: Failed to extract PWD from vCenter output" >> "${LOG_FILE}"
    exit 1
fi

echo "Successfully extracted credentials from vCenter" >> "${LOG_FILE}"
echo "Node IP: ${nodeIP}" >> "${LOG_FILE}"
echo "Password retrieved: $(echo "${nodePwd}" | sed 's/./*/g')" >> "${LOG_FILE}"

# Delete expired cert secrets and restart webhook deployments.
# --ignore-not-found prevents failure when secrets have already been cleaned up.
echo "==========================================" >> "${LOG_FILE}"
echo "Deleting storage-quota-root-ca-secret..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Delete storage-quota-root-ca-secret" \
    "kubectl -n vmware-system-cert-manager delete secret storage-quota-root-ca-secret --ignore-not-found"

echo "==========================================" >> "${LOG_FILE}"
echo "Deleting storage-quota-webhook-server-internal-cert..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Delete storage-quota-webhook-server-internal-cert" \
    "kubectl -n kube-system delete secret storage-quota-webhook-server-internal-cert --ignore-not-found"

echo "==========================================" >> "${LOG_FILE}"
echo "Deleting cns-storage-quota-extension-cert..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Delete cns-storage-quota-extension-cert" \
    "kubectl -n kube-system delete secret cns-storage-quota-extension-cert --ignore-not-found"

echo "==========================================" >> "${LOG_FILE}"
echo "Restarting cns-storage-quota-extension..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Restart cns-storage-quota-extension" \
    "kubectl -n kube-system rollout restart deploy cns-storage-quota-extension"

echo "==========================================" >> "${LOG_FILE}"
echo "Restarting storage-quota-webhook..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Restart storage-quota-webhook" \
    "kubectl -n kube-system rollout restart deploy storage-quota-webhook"

sleep 20

echo "==========================================" >> "${LOG_FILE}"
echo "Scaling cci replicas back up to 1..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Scale up cci" \
    "kubectl get ns svc-cci-ns-domain-c10 >/dev/null 2>&1 && kubectl -n svc-cci-ns-domain-c10 scale deployment --all --replicas=1 || echo 'svc-cci-ns-domain-c10 not found, skipping'"

echo "==========================================" >> "${LOG_FILE}"
echo "Scaling argocd replicas back up to 1..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Scale up argocd" \
    "kubectl -n ns-argo-cd scale deployment --all --replicas=1"

echo "==========================================" >> "${LOG_FILE}"
echo "Scaling Harbor replicas back up to 1..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Scale up Harbor StatefulSets" \
    "kubectl get ns svc-harbor-domain-c10 >/dev/null 2>&1 && kubectl -n svc-harbor-domain-c10 scale sts --all --replicas=1 || echo 'svc-harbor-domain-c10 not found, skipping'"
run_on_supervisor "Scale up Harbor Deployments" \
    "kubectl get ns svc-harbor-domain-c10 >/dev/null 2>&1 && kubectl -n svc-harbor-domain-c10 scale deployment --all --replicas=1 || echo 'svc-harbor-domain-c10 not found, skipping'"

echo "" >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
echo "✓ Successfully completed certificate resets and webhook restarts" >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"

# Renew ESXi spherelet (agent node) certificates if expired.
# These 1-year certs govern ESXi→Supervisor API authentication; when they
# expire the worker nodes go NotReady, blocking the LCI controller-manager
# pod from being scheduled and causing the /appplatform1/ endpoint to 502.
SPHERELET_SCRIPT="$(dirname "$0")/renew_spherelet_certs.sh"
if [[ -x "${SPHERELET_SCRIPT}" ]]; then
    echo "==========================================" >> "${LOG_FILE}"
    echo "Renewing ESXi spherelet certificates..." >> "${LOG_FILE}"
    echo "==========================================" >> "${LOG_FILE}"
    bash "${SPHERELET_SCRIPT}" "${VCENTER_HOST}" >> "${LOG_FILE}" 2>&1 || \
        echo "WARNING: renew_spherelet_certs.sh exited non-zero; check log for details" >> "${LOG_FILE}"
else
    echo "WARNING: ${SPHERELET_SCRIPT} not found or not executable — skipping spherelet renewal" >> "${LOG_FILE}"
fi
