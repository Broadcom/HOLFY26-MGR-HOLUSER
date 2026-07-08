#!/bin/bash
# Author: Burke Azbill
# Version: 1.6
# Date: 2026-07-08
# Script to renew expired Supervisor CP certificates and restart Kubernetes webhooks.
# This script:
# 1. SSH to vCenter and run decryptK8Pwd.py to get the Supervisor node IP + password
# 2. Quick VIP check — if the Supervisor VIP is already SSH-reachable (healthy
#    startup), Step A is skipped entirely; no certs are renewed, no sleep incurred.
# 3. If VIP is unreachable: discover the actual CP node IP from the VPX DB, push
#    k8s-renew-certs-5y.sh via a vCenter hop, and run it.  The script's built-in
#    THRESHOLD_DAYS=730 pre-check means it only renews certs expiring within 2 years
#    and exits cleanly (no kubelet restart) when all certs are still valid.
# 4. Wait for the Supervisor VIP to become SSH-reachable (up to MAX_SUP_ATTEMPTS retries)
# 5. Delete expired cert-manager secrets and restart the storage-quota webhook deployment
# 6. Invoke renew_spherelet_certs.sh to renew ESXi agent-node kubelet certs
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
MAX_SUP_ATTEMPTS=10
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
            -o HostKeyAlgorithms=+ssh-rsa \
            -o PubkeyAcceptedKeyTypes=+ssh-rsa \
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
echo "Node IP (VIP): ${nodeIP}" >> "${LOG_FILE}"
echo "Password retrieved: $(echo "${nodePwd}" | sed 's/./*/g')" >> "${LOG_FILE}"

# ── Step A: Conditionally renew Supervisor CP node PKI certs ──────────────────
# If the Supervisor VIP is already SSH-reachable the API server is running and
# certs are healthy — skip this step entirely (adds no delay on normal startups).
# Only when the VIP is unreachable do we probe the actual CP node IP via the
# vCenter VPX DB and push k8s-renew-certs-5y.sh there via a vCenter hop.
# The script's THRESHOLD_DAYS=730 pre-check means it only renews certs that are
# expiring within 2 years; it exits without touching anything when certs are fine.
# Service restarts (kubelet) are handled inside the script's Step 6 — we do NOT
# add a second restart here.
echo "==========================================" >> "${LOG_FILE}"
echo "Step A: Supervisor CP cert check / renewal" >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"

CERT_SCRIPT="$(dirname "$0")/k8s-renew-certs-5y.sh"

if /usr/bin/sshpass -p "${nodePwd}" ssh \
    -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=10 \
    -o HostKeyAlgorithms=+ssh-rsa \
    -o PubkeyAcceptedKeyTypes=+ssh-rsa \
    "root@${nodeIP}" "echo ok" >/dev/null 2>&1; then
    echo "  Supervisor VIP ${nodeIP} already SSH-reachable — skipping cert renewal" >> "${LOG_FILE}"
else
    echo "  Supervisor VIP ${nodeIP} not reachable — checking CP node certs..." >> "${LOG_FILE}"

    if [[ -f "${CERT_SCRIPT}" ]]; then
        # Base64-encode the password so it survives the vCenter SSH quoting layer
        nodePwd_b64=$(echo -n "${nodePwd}" | base64)

        # Discover actual CP node IP via vCenter VPX DB (the CP management network
        # is only reachable from the vCenter host, not directly from this manager)
        vpx_ips=$(ssh_with_fallback "${VCENTER_USER}" "${VCENTER_HOST}" \
            "/opt/vmware/vpostgres/current/bin/psql -U postgres -d VCDB -t -c \
\"SELECT ip_address FROM vpx_ip_address WHERE entity_id IN \
(SELECT id FROM vpx_vm WHERE file_name LIKE '%Supervisor%') \
ORDER BY entity_id, ip_address;\"" 2>/dev/null \
            | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' \
            | head -5)

        node_ip_direct=""
        for candidate_ip in ${vpx_ips}; do
            [[ "${candidate_ip}" == "${nodeIP}" ]] && continue
            probe=$(ssh_with_fallback "${VCENTER_USER}" "${VCENTER_HOST}" \
                "echo ${nodePwd_b64} | base64 -d > /tmp/.scppwd_probe && chmod 600 /tmp/.scppwd_probe && \
                 sshpass -f /tmp/.scppwd_probe ssh -o StrictHostKeyChecking=no \
                 -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5 \
                 root@${candidate_ip} 'echo REACH_OK'; \
                 rm -f /tmp/.scppwd_probe" 2>/dev/null)
            if [[ "${probe}" == *"REACH_OK"* ]]; then
                node_ip_direct="${candidate_ip}"
                echo "  Found reachable CP node: ${node_ip_direct}" >> "${LOG_FILE}"
                break
            fi
        done

        if [[ -n "${node_ip_direct}" ]]; then
            echo "  Copying k8s-renew-certs-5y.sh to vCenter ${VCENTER_HOST}..." >> "${LOG_FILE}"
            vc_pw=$(cat "${CREDS_FILE}" 2>/dev/null || true)
            /usr/bin/sshpass -p "${vc_pw}" scp \
                -o StrictHostKeyChecking=no \
                -o UserKnownHostsFile=/dev/null \
                -o ConnectTimeout=15 \
                "${CERT_SCRIPT}" "${VCENTER_USER}@${VCENTER_HOST}:/tmp/k8s-renew-certs-5y.sh" \
                >> "${LOG_FILE}" 2>&1 || true

            echo "  Running k8s-renew-certs-5y.sh on ${node_ip_direct} via vCenter hop..." >> "${LOG_FILE}"
            echo "  (Pre-check: renews only if certs expire within 730 days)" >> "${LOG_FILE}"
            CERT_RC=0
            # Use sshpass directly (not ssh_with_fallback) to avoid the double-run problem:
            # ssh_with_fallback retries via sshpass when BatchMode SSH returns non-zero for
            # ANY reason (including the cert renewal script itself exiting non-zero). The
            # second retry then fails because the cleanup in the first run already deleted
            # /tmp/k8s-renew-certs-5y.sh from vCenter. Using sshpass directly runs exactly
            # once and captures the correct exit code.
            /usr/bin/sshpass -p "${vc_pw}" ssh \
                -o StrictHostKeyChecking=no \
                -o UserKnownHostsFile=/dev/null \
                -o ConnectTimeout=15 \
                "${VCENTER_USER}@${VCENTER_HOST}" \
                "echo ${nodePwd_b64} | base64 -d > /tmp/.scppwd_cert && chmod 600 /tmp/.scppwd_cert && \
                 sshpass -f /tmp/.scppwd_cert scp -o StrictHostKeyChecking=no \
                 -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 \
                 /tmp/k8s-renew-certs-5y.sh root@${node_ip_direct}:/tmp/k8s-renew-certs-5y.sh && \
                 sshpass -f /tmp/.scppwd_cert ssh -o StrictHostKeyChecking=no \
                 -o UserKnownHostsFile=/dev/null -o ConnectTimeout=120 \
                 root@${node_ip_direct} \
                 'bash /tmp/k8s-renew-certs-5y.sh 2>&1; RC=\$?; rm -f /tmp/k8s-renew-certs-5y.sh; exit \$RC'; \
                 CERT_EXIT=\$?; rm -f /tmp/.scppwd_cert /tmp/k8s-renew-certs-5y.sh; exit \$CERT_EXIT" \
                >> "${LOG_FILE}" 2>&1 || CERT_RC=$?

            if [[ "${CERT_RC}" -eq 0 ]]; then
                echo "  Cert renewal complete — waiting 75s for API server and VIP to come up..." >> "${LOG_FILE}"
            else
                echo "  Cert renewal exited ${CERT_RC} — kubelet may have restarted mid-run; waiting 75s anyway..." >> "${LOG_FILE}"
            fi
            sleep 75
        else
            echo "  Could not reach any CP node via vCenter hop — skipping cert renewal" >> "${LOG_FILE}"
            echo "  (VIP ${nodeIP} will be retried in the SSH wait loop below)" >> "${LOG_FILE}"
        fi
    else
        echo "  WARNING: ${CERT_SCRIPT} not found — skipping CP cert renewal" >> "${LOG_FILE}"
    fi
fi

# Gate: confirm the Supervisor VIP is reachable via SSH before attempting any
# kubectl operations. The VIP may not be routable until the API server starts
# and kube-vip assigns it. A single wait-loop here prevents each of the many
# run_on_supervisor calls below from burning their own retry budget early.
echo "==========================================" >> "${LOG_FILE}"
echo "Waiting for Supervisor VIP SSH at ${nodeIP}..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
sup_ssh_ready=false
sup_check=0
while [[ $sup_check -lt $MAX_SUP_ATTEMPTS ]]; do
    sup_check=$((sup_check + 1))
    echo "  SSH connectivity check (attempt ${sup_check}/${MAX_SUP_ATTEMPTS})..." >> "${LOG_FILE}"
    if /usr/bin/sshpass -p "${nodePwd}" ssh \
        -o StrictHostKeyChecking=accept-new \
        -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=15 \
        -o HostKeyAlgorithms=+ssh-rsa \
        -o PubkeyAcceptedKeyTypes=+ssh-rsa \
        "root@${nodeIP}" "echo ok" >/dev/null 2>&1; then
        echo "  Supervisor SSH reachable." >> "${LOG_FILE}"
        sup_ssh_ready=true
        break
    fi
    if [[ $sup_check -lt $MAX_SUP_ATTEMPTS ]]; then
        echo "  No route to Supervisor yet, retrying in ${SUP_RETRY_DELAY}s..." >> "${LOG_FILE}"
        sleep "${SUP_RETRY_DELAY}"
    fi
done

if [[ "${sup_ssh_ready}" != "true" ]]; then
    echo "WARNING: Supervisor at ${nodeIP} unreachable after ${MAX_SUP_ATTEMPTS} attempts — skipping all supervisor operations" >> "${LOG_FILE}"
    exit 0
fi

# Delete expired cert secrets and restart webhook deployments.
# --ignore-not-found prevents failure when secrets have already been cleaned up.
echo "==========================================" >> "${LOG_FILE}"
echo "Deleting storage-quota-root-ca-secret..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Delete storage-quota-root-ca-secret" \
    "kubectl get ns vmware-system-cert-manager >/dev/null 2>&1 && kubectl -n vmware-system-cert-manager delete secret storage-quota-root-ca-secret --ignore-not-found || echo 'vmware-system-cert-manager not found, skipping'"

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
    "kubectl -n kube-system get deploy cns-storage-quota-extension >/dev/null 2>&1 && kubectl -n kube-system rollout restart deploy cns-storage-quota-extension || echo 'cns-storage-quota-extension not found, skipping'"

echo "==========================================" >> "${LOG_FILE}"
echo "Restarting storage-quota-webhook..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Restart storage-quota-webhook" \
    "kubectl -n kube-system get deploy storage-quota-webhook >/dev/null 2>&1 && kubectl -n kube-system rollout restart deploy storage-quota-webhook || echo 'storage-quota-webhook not found, skipping'"

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
    "kubectl get ns ns-argo-cd >/dev/null 2>&1 && kubectl -n ns-argo-cd scale deployment --all --replicas=1 || echo 'ns-argo-cd not found, skipping'"

echo "==========================================" >> "${LOG_FILE}"
echo "Scaling Harbor replicas back up to 1..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Scale up Harbor StatefulSets" \
    "kubectl get ns svc-harbor-domain-c10 >/dev/null 2>&1 && kubectl -n svc-harbor-domain-c10 scale sts --all --replicas=1 || echo 'svc-harbor-domain-c10 not found, skipping'"
run_on_supervisor "Scale up Harbor Deployments" \
    "kubectl get ns svc-harbor-domain-c10 >/dev/null 2>&1 && kubectl -n svc-harbor-domain-c10 scale deployment --all --replicas=1 || echo 'svc-harbor-domain-c10 not found, skipping'"

echo "" >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
echo "Cleaning up Failed pods cluster-wide..." >> "${LOG_FILE}"
echo "==========================================" >> "${LOG_FILE}"
run_on_supervisor "Clean up Failed pods" \
    "kubectl delete pods --all-namespaces --field-selector=status.phase=Failed"

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
