#!/bin/bash
# =============================================================================
# k8s-renew-certs-5y.sh  v5
# Date: 2026-07-08
# Renew ALL Kubernetes certificates with 5-year validity
#
# Features:
#   - Pre-check: only proceeds when any cert expires within THRESHOLD_DAYS (2y)
#   - Version-adaptive: uses kubeadm ClusterConfiguration certificateValidityPeriod
#     on kubeadm >= 1.29; falls back to two-pass OpenSSL re-sign on older releases
#   - Covers PKI certs, kubeconfig embedded certs (including kubelet.conf and
#     super-admin.conf which kubeadm does not renew), kubelet rotating + serving certs
#   - Handles Supervisor-specific standalone scheduler.crt if present
#   - Explicitly restarts control plane pods (kube-apiserver, kube-controller-manager,
#     kube-scheduler, etcd) via crictl, then restarts kubelet for kubelet cert pickup
#   - Comprehensive expiry validation at the end
#
# Requirements:
#   - Run as root on the kubeadm control-plane node (or vSphere Supervisor CP node)
#   - OpenSSL 1.1.1+ (3.x preferred)
#   - kubeadm (optional but preferred), systemctl, crictl
#   - Cluster CA certs must still be valid (/etc/kubernetes/pki/ca.crt etc.)
#
# Usage:
#   bash k8s-renew-certs-5y.sh            # Full renewal (with pre-check)
#   bash k8s-renew-certs-5y.sh --dry-run  # Show current expiry only, no changes
#   bash k8s-renew-certs-5y.sh --force    # Skip pre-check, always renew
#
# Tested on: Kubernetes v1.27, v1.30, Photon OS 5, OpenSSL 3.0.8
#            (config path auto-activates on kubeadm >= 1.29)
#            vSphere Supervisor Control Plane nodes (VCF 9.0/9.1)
# =============================================================================
set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
DAYS=1825               # Target cert validity: 5 years  (1825 days)
THRESHOLD_DAYS=730      # Renew if any cert expires within this many days (2 years)

PKI=/etc/kubernetes/pki
K8S=/etc/kubernetes
KUBELET_PKI=/var/lib/kubelet/pki
NODE=$(hostname)
BACKUP_DIR="$K8S/cert-backup-$(date +%Y%m%d-%H%M%S)"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# ─── Helpers ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
step()  { echo; echo -e "${CYAN}━━━ $* ━━━${NC}"; }

# ─── Preflight ────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]]                           && error "Must run as root"
command -v openssl >/dev/null 2>&1          || error "openssl not found in PATH"
command -v systemctl >/dev/null 2>&1        || error "systemctl not found in PATH"
command -v kubeadm >/dev/null 2>&1          || warn  "kubeadm not found — using OpenSSL-only path for all PKI certs"
command -v crictl >/dev/null 2>&1           || warn  "crictl not found — control plane pods will be restarted via kubelet"
[[ -f "$PKI/ca.crt" && -f "$PKI/ca.key" ]] || error "Cluster CA not found at $PKI/ca.crt / $PKI/ca.key"

CRICTL=$(command -v crictl 2>/dev/null || true)

# ─── Dry-run ──────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--dry-run" ]]; then
    step "Dry-run: certificate expiry status"
    kubeadm certs check-expiration 2>/dev/null || true
    echo
    for F in "$KUBELET_PKI/kubelet-client-current.pem" "$KUBELET_PKI/kubelet.crt"; do
        [[ -f "$F" ]] && openssl x509 -in "$F" -noout -enddate -subject 2>/dev/null && echo
    done
    exit 0
fi

# =============================================================================
# STEP 0 — Pre-check: evaluate whether any cert expires within THRESHOLD_DAYS
# =============================================================================
step "Step 0: Pre-check — scanning for certs expiring within ${THRESHOLD_DAYS} days"

THRESHOLD_SEC=$((THRESHOLD_DAYS * 86400))
NEEDS_RENEWAL=false

# Returns 0 (true) if the cert needs renewal; prints status line
check_cert() {
    local FILE="$1" LABEL="$2"
    if [[ ! -f "$FILE" ]]; then
        warn "  MISSING  $LABEL"
        NEEDS_RENEWAL=true
        return
    fi
    local EXP
    # Use || EXP="" to prevent set -e from triggering when openssl cannot parse
    # an empty or non-cert file (e.g. kubeconfig without embedded client-certificate-data)
    EXP=$(openssl x509 -in "$FILE" -noout -enddate 2>/dev/null | cut -d= -f2) || EXP=""
    if ! openssl x509 -in "$FILE" -checkend "$THRESHOLD_SEC" >/dev/null 2>&1; then
        warn "  RENEW    $LABEL  (expires ${EXP:-unknown})"
        NEEDS_RENEWAL=true
    else
        info "  OK       $LABEL  (expires $EXP)"
    fi
}

# Check PKI cert files
check_cert "$PKI/apiserver.crt"                "apiserver"
check_cert "$PKI/apiserver-kubelet-client.crt" "apiserver-kubelet-client"
check_cert "$PKI/apiserver-etcd-client.crt"    "apiserver-etcd-client"
check_cert "$PKI/front-proxy-client.crt"       "front-proxy-client"
check_cert "$PKI/etcd/server.crt"              "etcd/server"
check_cert "$PKI/etcd/peer.crt"                "etcd/peer"
check_cert "$PKI/etcd/healthcheck-client.crt"  "etcd/healthcheck-client"

# Check kubeconfig embedded certs
for KC in "$K8S/admin.conf" "$K8S/controller-manager.conf" "$K8S/scheduler.conf"; do
    if [[ -f "$KC" ]]; then
        awk '/client-certificate-data:/{print $2}' "$KC" | base64 -d > "$TMPDIR/kc_check.crt" 2>/dev/null || true
        check_cert "$TMPDIR/kc_check.crt" "$(basename "$KC") (embedded)"
    fi
done

# Check kubelet certs
check_cert "$KUBELET_PKI/kubelet-client-current.pem" "kubelet-client-current"
check_cert "$KUBELET_PKI/kubelet.crt"                "kubelet serving cert"

if [[ "$NEEDS_RENEWAL" == "false" && "${1:-}" != "--force" ]]; then
    info ""
    info "All certificates are valid for more than ${THRESHOLD_DAYS} days."
    info "No renewal needed. Use --force to override."
    exit 0
fi
info ""
info "Renewal required — proceeding."

# =============================================================================
# STEP 1 — Backup
# =============================================================================
step "Step 1: Backing up existing certs → $BACKUP_DIR"
mkdir -p "$BACKUP_DIR/pki"
cp -r "$PKI/." "$BACKUP_DIR/pki/"
for F in "$K8S"/*.conf; do [[ -f "$F" ]] && cp "$F" "$BACKUP_DIR/"; done
cp "$KUBELET_PKI/kubelet-client-current.pem" "$BACKUP_DIR/" 2>/dev/null || true
cp "$KUBELET_PKI/kubelet.crt"               "$BACKUP_DIR/kubelet-serving.crt" 2>/dev/null || true
info "Backup complete: $BACKUP_DIR"

# =============================================================================
# STEP 2 — Renew control-plane + kubeconfig certs
#
# Strategy depends on kubeadm version:
#   >= 1.29 → ClusterConfiguration.certificateValidityPeriod supported;
#             kubeadm sets the duration directly — no OpenSSL re-sign needed
#   <  1.29 → certificateValidityPeriod unknown; run kubeadm for correct
#             structure then re-sign every cert to DAYS via OpenSSL
# =============================================================================

# ─── Helpers for two-pass OpenSSL fallback ────────────────────────────────────

# Extract Key Usage + Extended Key Usage from a cert and write an extension file.
# Shared by both resign_pki_cert and resign_kubeconfig.
# $3 (optional): "client" → supplies clientAuth EKU/KU defaults when absent from cert
_build_ext_file() {
    local CERT_TEXT="$1" EXT_FILE="$2" ROLE="${3:-}"
    > "$EXT_FILE"

    # SANs (PKI server certs only; client certs won't have them)
    local SANS
    SANS=$(echo "$CERT_TEXT" | \
        awk '/Subject Alternative Name/{getline; gsub(/^[[:space:]]+/,""); print}' | \
        sed 's/IP Address:/IP:/g' || true)
    [[ -n "$SANS" ]] && echo "subjectAltName = $SANS" >> "$EXT_FILE"

    # Key Usage (may be critical)
    local KU_CRITICAL="" KU=""
    if echo "$CERT_TEXT" | grep -q "Key Usage: critical" 2>/dev/null; then
        KU_CRITICAL="critical, "
    fi
    KU=$(echo "$CERT_TEXT" | \
        awk '/X509v3 Key Usage/{getline; gsub(/^[[:space:]]+/,""); print}' | \
        sed 's/Digital Signature/digitalSignature/g
             s/Non Repudiation/nonRepudiation/g
             s/Key Encipherment/keyEncipherment/g
             s/Data Encipherment/dataEncipherment/g
             s/Certificate Sign/keyCertSign/g
             s/CRL Sign/cRLSign/g' || true)
    # Fallback for client role when source cert is missing Key Usage (stripped by earlier run)
    if [[ -z "$KU" && "$ROLE" == "client" ]]; then
        KU="digitalSignature, keyEncipherment"
        KU_CRITICAL="critical, "
    fi
    [[ -n "$KU" ]] && echo "keyUsage = ${KU_CRITICAL}${KU}" >> "$EXT_FILE"

    # Extended Key Usage
    local EKU=""
    EKU=$(echo "$CERT_TEXT" | \
        awk '/X509v3 Extended Key Usage/{getline; gsub(/^[[:space:]]+/,""); print}' | \
        sed 's/TLS Web Server Authentication/serverAuth/g
             s/TLS Web Client Authentication/clientAuth/g' || true)
    # Fallback for client role when source cert is missing EKU
    [[ -z "$EKU" && "$ROLE" == "client" ]] && EKU="clientAuth"
    [[ -n "$EKU" ]] && echo "extendedKeyUsage = $EKU" >> "$EXT_FILE"
}

# Re-sign a PKI cert file in-place (preserves SANs, Key Usage, EKU)
resign_pki_cert() {
    local CERT="$1" KEY="$2" CA_CERT="$3" CA_KEY="$4"

    local CERT_TEXT EXT_FILE="$TMPDIR/pki.ext"
    CERT_TEXT=$(openssl x509 -noout -text -in "$CERT" 2>/dev/null)

    _build_ext_file "$CERT_TEXT" "$EXT_FILE"

    local SUBJ
    SUBJ=$(openssl x509 -noout -subject -in "$CERT" 2>/dev/null | \
        sed 's/subject=//' | sed 's/ = /=/g; s/, /\//g; s/^/\//')

    openssl req -new -key "$KEY" -subj "$SUBJ" -out "$TMPDIR/pki.csr" 2>/dev/null

    if [[ -s "$EXT_FILE" ]]; then
        openssl x509 -req -in "$TMPDIR/pki.csr" \
            -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
            -extfile "$EXT_FILE" -days "$DAYS" -out "$CERT" 2>/dev/null
    else
        openssl x509 -req -in "$TMPDIR/pki.csr" \
            -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
            -days "$DAYS" -out "$CERT" 2>/dev/null
    fi

    local EXP
    EXP=$(openssl x509 -in "$CERT" -noout -enddate 2>/dev/null | cut -d= -f2)
    info "  $(basename "$CERT")  →  expires $EXP"
    rm -f "$TMPDIR/pki.csr" "$EXT_FILE"
}

# Re-sign the embedded client cert in a kubeconfig in-place
# Preserves Subject, Key Usage, and Extended Key Usage.
# Falls back to standard clientAuth extensions if the source cert is missing them.
resign_kubeconfig() {
    local KUBECONFIG="$1" CA_CERT="$2" CA_KEY="$3"
    local CERT="$TMPDIR/kc.crt" KEY="$TMPDIR/kc.key" NEW_CERT="$TMPDIR/kc-new.crt"

    # Extract embedded cert and key (|| true prevents pipefail on empty awk match)
    awk '/client-certificate-data:/{print $2}' "$KUBECONFIG" | base64 -d > "$CERT" 2>/dev/null || true
    awk '/client-key-data:/{print $2}'         "$KUBECONFIG" | base64 -d > "$KEY"  2>/dev/null || true
    if [[ ! -s "$CERT" || ! -s "$KEY" ]]; then
        warn "  $(basename "$KUBECONFIG") — could not extract embedded cert/key, skipping"
        return
    fi

    local CERT_TEXT EXT_FILE="$TMPDIR/kc.ext"
    CERT_TEXT=$(openssl x509 -noout -text -in "$CERT" 2>/dev/null || true)
    # Pass "client" so missing KU/EKU are filled with standard clientAuth defaults
    _build_ext_file "$CERT_TEXT" "$EXT_FILE" "client"

    local SUBJ
    SUBJ=$(openssl x509 -noout -subject -in "$CERT" 2>/dev/null | \
        sed 's/subject=//' | sed 's/ = /=/g; s/, /\//g; s/^/\//')

    openssl req -new -key "$KEY" -subj "$SUBJ" -out "$TMPDIR/kc.csr" 2>/dev/null

    if [[ -s "$EXT_FILE" ]]; then
        openssl x509 -req -in "$TMPDIR/kc.csr" \
            -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
            -extfile "$EXT_FILE" -days "$DAYS" -out "$NEW_CERT" 2>/dev/null
    else
        openssl x509 -req -in "$TMPDIR/kc.csr" \
            -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
            -days "$DAYS" -out "$NEW_CERT" 2>/dev/null
    fi

    local NEW_B64
    NEW_B64=$(base64 -w0 < "$NEW_CERT")
    sed -i "s|^\([[:space:]]*client-certificate-data:\).*|\1 $NEW_B64|" "$KUBECONFIG"

    local EXP
    EXP=$(openssl x509 -in "$NEW_CERT" -noout -enddate 2>/dev/null | cut -d= -f2)
    info "  $(basename "$KUBECONFIG")  →  expires $EXP"
    rm -f "$CERT" "$KEY" "$TMPDIR/kc.csr" "$NEW_CERT" "$EXT_FILE"
}

HOURS=$((DAYS * 24))

step "Step 2: Renewing control-plane + kubeconfig certs (${DAYS}-day / 5-year target)"

KUBEADM_MINOR=0
if command -v kubeadm >/dev/null 2>&1; then
    KUBEADM_MINOR=$(kubeadm version -o short 2>/dev/null | grep -oE 'v1\.[0-9]+' | head -1 | cut -d. -f2 || echo 0)
fi

if [[ "${KUBEADM_MINOR:-0}" -ge 29 ]]; then
    # ── Config-driven path (kubeadm >= 1.29) ─────────────────────────────────
    info "kubeadm v1.${KUBEADM_MINOR} — using ClusterConfiguration.certificateValidityPeriod"
    info "Generating kubeadm-config.yaml with certificateValidityPeriod: ${HOURS}h0m0s"

    cat > "$TMPDIR/kubeadm-config.yaml" <<EOF
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
certificateValidityPeriod: ${HOURS}h0m0s
EOF

    kubeadm certs renew all --config "$TMPDIR/kubeadm-config.yaml" 2>&1 || \
        warn "kubeadm reported an error — will fall through to OpenSSL re-sign below"

    info ""
    info "Verifying resulting expiry dates:"
    for CERT in "$PKI/apiserver.crt" "$PKI/etcd/server.crt" "$PKI/etcd/peer.crt"; do
        EXP=$(openssl x509 -in "$CERT" -noout -enddate 2>/dev/null | cut -d= -f2)
        info "  $(basename "$CERT")  →  expires $EXP"
    done

elif [[ "${KUBEADM_MINOR:-0}" -gt 0 ]]; then
    # ── Two-pass OpenSSL path (kubeadm < 1.29) ────────────────────────────────
    info "kubeadm v1.${KUBEADM_MINOR} — certificateValidityPeriod not supported"
    info "Using two-pass approach: kubeadm renew (1y structure) + OpenSSL re-sign (5y)"
    echo

    info "Pass 1: kubeadm certs renew all  (establishes correct cert structure + SANs)"
    kubeadm certs renew all 2>&1 || \
        warn "kubeadm reported an error — continuing with OpenSSL re-sign using local CA"
else
    info "kubeadm not found — using OpenSSL-only re-sign path"
fi

# ── OpenSSL re-sign pass (always runs — extends validity to 5y and covers
#    certs that kubeadm misses, e.g. Supervisor-specific scheduler.crt) ───────
echo
info "OpenSSL re-sign pass — re-signing all PKI certs to ${DAYS}-day (5y) validity"
info "[ cluster CA-signed ]"
resign_pki_cert "$PKI/apiserver.crt"                "$PKI/apiserver.key"               "$PKI/ca.crt"           "$PKI/ca.key"
resign_pki_cert "$PKI/apiserver-kubelet-client.crt" "$PKI/apiserver-kubelet-client.key" "$PKI/ca.crt"           "$PKI/ca.key"
resign_pki_cert "$PKI/front-proxy-client.crt"       "$PKI/front-proxy-client.key"       "$PKI/front-proxy-ca.crt" "$PKI/front-proxy-ca.key"
# Supervisor CP nodes carry a standalone scheduler.crt (not embedded in scheduler.conf)
if [[ -f "$PKI/scheduler.crt" && -f "$PKI/scheduler.key" ]]; then
    resign_pki_cert "$PKI/scheduler.crt" "$PKI/scheduler.key" "$PKI/ca.crt" "$PKI/ca.key"
fi

info "[ etcd CA-signed ]"
resign_pki_cert "$PKI/apiserver-etcd-client.crt"   "$PKI/apiserver-etcd-client.key"   "$PKI/etcd/ca.crt" "$PKI/etcd/ca.key"
resign_pki_cert "$PKI/etcd/server.crt"             "$PKI/etcd/server.key"             "$PKI/etcd/ca.crt" "$PKI/etcd/ca.key"
resign_pki_cert "$PKI/etcd/peer.crt"               "$PKI/etcd/peer.key"               "$PKI/etcd/ca.crt" "$PKI/etcd/ca.key"
resign_pki_cert "$PKI/etcd/healthcheck-client.crt" "$PKI/etcd/healthcheck-client.key" "$PKI/etcd/ca.crt" "$PKI/etcd/ca.key"

echo
info "[ kubeconfig embedded client certs ]"
# Standard kubeadm kubeconfigs
resign_kubeconfig "$K8S/admin.conf"              "$PKI/ca.crt" "$PKI/ca.key"
resign_kubeconfig "$K8S/controller-manager.conf" "$PKI/ca.crt" "$PKI/ca.key"
resign_kubeconfig "$K8S/scheduler.conf"          "$PKI/ca.crt" "$PKI/ca.key"
# vSphere Supervisor CP adds super-admin.conf (kubeadm >= 1.28 may handle this,
# but we re-sign via OpenSSL as well to guarantee 5-year validity)
[[ -f "$K8S/super-admin.conf" ]] && \
    resign_kubeconfig "$K8S/super-admin.conf" "$PKI/ca.crt" "$PKI/ca.key"
# kubelet.conf holds the node's own bootstrap client cert — kubeadm never renews
# this file; when it expires kubelet cannot start, which prevents the API server
# static pod from being scheduled and leaves the Supervisor stuck in "Configuring".
[[ -f "$K8S/kubelet.conf" ]] && \
    resign_kubeconfig "$K8S/kubelet.conf" "$PKI/ca.crt" "$PKI/ca.key"

# =============================================================================
# STEP 3 — Renew kubelet rotating client cert (always manual — kubeadm never
#          manages /var/lib/kubelet/pki/)
# =============================================================================
step "Step 3: Renewing kubelet rotating client cert (${DAYS} days)"
NEW_KUBELET_CLIENT="$KUBELET_PKI/kubelet-client-$(date +%Y-%m-%d-%H-%M-%S).pem"

openssl genrsa -out "$TMPDIR/kbl.key" 2048 2>/dev/null
openssl req -new \
    -key  "$TMPDIR/kbl.key" \
    -subj "/O=system:nodes/CN=system:node:${NODE}" \
    -out  "$TMPDIR/kbl.csr" 2>/dev/null
openssl x509 -req \
    -in "$TMPDIR/kbl.csr" -CA "$PKI/ca.crt" -CAkey "$PKI/ca.key" \
    -CAcreateserial -days "$DAYS" -sha256 -out "$TMPDIR/kbl.crt" 2>/dev/null

cat "$TMPDIR/kbl.crt" "$TMPDIR/kbl.key" > "$NEW_KUBELET_CLIENT"
chmod 600 "$NEW_KUBELET_CLIENT"
ln -sf "$NEW_KUBELET_CLIENT" "$KUBELET_PKI/kubelet-client-current.pem"
EXP=$(openssl x509 -in "$NEW_KUBELET_CLIENT" -noout -enddate 2>/dev/null | cut -d= -f2)
info "  kubelet-client-current.pem  →  expires $EXP"

# =============================================================================
# STEP 4 — Renew kubelet serving cert (self-signed, always manual)
# =============================================================================
step "Step 4: Renewing kubelet serving cert (self-signed, ${DAYS} days)"
NODE_IP=$(ip -4 addr show | awk '/inet / && !/127\.0\.0\.1/{print $2}' | cut -d/ -f1 | head -1)
NODE_IP=${NODE_IP:-127.0.0.1}

openssl req -newkey rsa:2048 -nodes \
    -keyout "$TMPDIR/kbl-serve.key" \
    -x509 -days "$DAYS" \
    -subj "/CN=${NODE}@$(date +%s)" \
    -addext "subjectAltName=DNS:${NODE},IP:${NODE_IP},IP:127.0.0.1" \
    -out "$TMPDIR/kbl-serve.crt" 2>/dev/null

cp "$TMPDIR/kbl-serve.crt" "$KUBELET_PKI/kubelet.crt"
cp "$TMPDIR/kbl-serve.key" "$KUBELET_PKI/kubelet.key"
chmod 644 "$KUBELET_PKI/kubelet.crt"
chmod 600 "$KUBELET_PKI/kubelet.key"
EXP=$(openssl x509 -in "$KUBELET_PKI/kubelet.crt" -noout -enddate 2>/dev/null | cut -d= -f2)
info "  kubelet.crt  →  expires $EXP"

# =============================================================================
# STEP 5 — Update root kubeconfig
# =============================================================================
step "Step 5: Updating root kubeconfig"
mkdir -p /root/.kube
# Suppress the "same file" warning that occurs on Supervisor nodes where
# admin.conf and /root/.kube/config share the same inode.
cp -f "$K8S/admin.conf" /root/.kube/config 2>/dev/null || true
info "  /root/.kube/config updated from admin.conf"

# =============================================================================
# STEP 6 — Restart control plane pods, then kubelet
#
# a) Stop each control plane container via crictl — kubelet immediately
#    restarts them as static pods and they load the renewed PKI/kubeconfig certs.
# b) Restart kubelet so it picks up the renewed kubelet client + serving certs.
#    Kubelet restart also triggers a second static pod reconcile, which is benign.
# =============================================================================
step "Step 6: Restarting control plane pods and kubelet"

if [[ -n "$CRICTL" ]]; then
    info "[ Stopping control plane containers via crictl ]"
    for POD in kube-apiserver kube-controller-manager kube-scheduler etcd; do
        CID=$("$CRICTL" ps --name "^${POD}$" -q 2>/dev/null | head -1 || true)
        if [[ -n "$CID" ]]; then
            "$CRICTL" stop "$CID" >/dev/null 2>&1 && info "  Stopped: $POD (container $CID)"
        else
            warn "  Not running: $POD (will start after kubelet restart)"
        fi
    done
    info "  Waiting 15s for kubelet to restart static pods..."
    sleep 15
else
    info "  crictl unavailable — skipping explicit container stop (kubelet restart will handle it)"
fi

info "[ Restarting kubelet (picks up renewed kubelet certs) ]"
systemctl restart kubelet
info "  Waiting 30s for all pods to come up..."
sleep 30

# =============================================================================
# STEP 7 — Validation
# =============================================================================
step "Step 7: Validation"

info "[ Node status ]"
kubectl get nodes

echo
info "[ Control plane pod status ]"
kubectl get pods -n kube-system \
    -l 'component in (kube-apiserver,kube-controller-manager,kube-scheduler,etcd)' \
    -o wide 2>/dev/null || kubectl get pods -n kube-system

echo
info "[ Certificate expiry — kubeadm summary ]"
kubeadm certs check-expiration 2>/dev/null || true

echo
info "[ Kubelet certs ]"
openssl x509 -in "$KUBELET_PKI/kubelet-client-current.pem" -noout -enddate -subject 2>/dev/null
openssl x509 -in "$KUBELET_PKI/kubelet.crt"                -noout -enddate -subject 2>/dev/null

echo
info "[ apiserver SAN check ]"
openssl x509 -in "$PKI/apiserver.crt" -noout -text 2>/dev/null | \
    grep -A2 "Subject Alternative Name" || warn "No SANs found in apiserver.crt — verify manually"

echo
info "[ kubelet.conf cert ]"
if [[ -f "$K8S/kubelet.conf" ]]; then
    awk '/client-certificate-data:/{print $2}' "$K8S/kubelet.conf" | base64 -d | \
        openssl x509 -noout -enddate -subject 2>/dev/null || \
        warn "Could not decode kubelet.conf client cert"
fi

echo
info "All done. Backup saved at: $BACKUP_DIR"
info "Certs renewed to ~${DAYS}-day (5-year) validity."
