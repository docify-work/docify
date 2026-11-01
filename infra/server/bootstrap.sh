#!/usr/bin/env bash
# =============================================================================
# Docify server bootstrap (cloud-init user_data) - Master Doc §12.4
#
# Rendered by Terraform templatefile() in modules/server. Template rules:
#   - Terraform fills every "dollar + {name}" placeholder (only used in the
#     block of variables right below).
#   - Shell variables that need braces are written with a DOUBLED dollar in
#     this file, which is Terraform's escape; the rendered script has one.
#   - Plain $NAME (no braces) is never touched by Terraform.
#
# Runs once on the first boot of a NEW instance (cloud-init default). Every
# step is idempotent, so it can be re-run safely by hand:
#   sudo bash /var/lib/cloud/instance/scripts/part-001
#
# Steps:
#   1. data volume -> /data (mkfs ONLY if it has no filesystem)
#   2. OS: unattended-upgrades, chrony, aws cli, jq, swapfile
#   3. ecr-credential-provider (kubelet pulls from ECR with the instance role)
#   4. k3s (pinned) + config.yaml + "don't start without /data" drop-in
#   5. docify-dns.service: point origin records at this instance's IP, every boot
#   6. Argo CD (helm) + root app-of-apps Application
#   7. marker file /etc/docify/bootstrap.done
# Log: /var/log/docify-bootstrap.log
# =============================================================================
set -euo pipefail

exec > >(tee -a /var/log/docify-bootstrap.log) 2>&1

# ---- values injected by Terraform ---------------------------------------------
REGION="${region}"
ACCOUNT_ID="${account_id}"
DOMAIN="${domain}"
HOSTED_ZONE_ID="${hosted_zone_id}"
ORIGIN_FQDNS="${origin_fqdns}"
DATA_VOLUME_ID="${data_volume_id}"
ARCH="${architecture}"
K3S_VERSION="${k3s_version}"
ECR_CP_VERSION="${ecr_credential_provider_ver}"
ECR_CP_SHA256="${ecr_credential_provider_sha256}"
HELM_VERSION="${helm_version}"
HELM_SHA256="${helm_sha256}"
ARGOCD_CHART_VERSION="${argocd_chart_version}"
GIT_REPO_URL="${git_repo_url}"
GIT_REVISION="${git_revision}"
ROOT_APP_PATH="${root_app_path}"
ROOT_VALUES_FILES="${root_values_files}"
ARGOCD_VALUES_PATH="${argocd_values_path}"

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
export DEBIAN_FRONTEND=noninteractive
export HOME="$${HOME:-/root}" # cloud-init may run without HOME; helm needs it
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

MARKER=/etc/docify/bootstrap.done
mkdir -p /etc/docify

log() { echo "[docify-bootstrap] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

# retry <attempts> <sleep-seconds> <command...>
retry() {
  local attempts=$1 pause=$2 i
  shift 2
  for ((i = 1; i <= attempts; i++)); do
    if "$@"; then return 0; fi
    log "attempt $i/$attempts failed: $*"
    sleep "$pause"
  done
  return 1
}

if [ -f "$MARKER" ]; then
  log "marker $MARKER exists - re-running idempotent steps anyway"
fi
log "start (region=$REGION domain=$DOMAIN origins='$ORIGIN_FQDNS' arch=$ARCH k3s=$K3S_VERSION)"

# =============================================================================
# 1. Data volume -> /data
# =============================================================================
# On Nitro instances EBS volumes show up as NVMe devices; the stable name
# contains the volume id without the dash. The attachment is created by
# Terraform right after the instance, so wait for it (up to 10 min).
DATA_DEV="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_$${DATA_VOLUME_ID//-/}"
log "step 1: waiting for data volume $DATA_DEV"
for _ in $(seq 1 120); do
  [ -e "$DATA_DEV" ] && break
  sleep 5
done
if [ ! -e "$DATA_DEV" ]; then
  log "ERROR: data volume $DATA_VOLUME_ID never appeared - refusing to continue"
  exit 1
fi

# SAFETY: only format a volume that has NO filesystem. A re-attached volume
# (instance rebuild) keeps its data - mkfs on it would wipe the database.
FS_TYPE="$(blkid -o value -s TYPE "$DATA_DEV" || true)"
if [ -z "$FS_TYPE" ]; then
  log "step 1: no filesystem on data volume -> mkfs.ext4 (first ever boot)"
  mkfs.ext4 -L docify-data "$DATA_DEV"
else
  log "step 1: data volume already has $FS_TYPE - NOT formatting"
fi

DATA_UUID="$(blkid -o value -s UUID "$DATA_DEV")"
mkdir -p /data
# fstab by UUID (device names can change). nofail: the OS still boots (and
# SSM still works) if the volume is missing; k3s then refuses to start
# because of RequiresMountsFor=/data (step 4) -> no empty DB on the root disk.
if ! grep -q "UUID=$DATA_UUID" /etc/fstab; then
  echo "UUID=$DATA_UUID /data ext4 defaults,nofail,x-systemd.device-timeout=60s 0 2" >>/etc/fstab
fi
systemctl daemon-reload
mountpoint -q /data || mount /data

mkdir -p /data/postgres /data/local-path /data/prometheus /data/loki
chown 999:999 /data/postgres # uid/gid of the postgres user in the official image
chmod 0700 /data/postgres

# =============================================================================
# 2. OS packages, time sync, security updates, swap
# =============================================================================
log "step 2: packages"
retry 5 10 apt-get update -y
retry 3 10 apt-get install -y --no-install-recommends \
  unattended-upgrades chrony jq curl ca-certificates

# Security updates only (Ubuntu's default unattended-upgrades origins), no auto-reboot.
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
systemctl enable --now unattended-upgrades

# Amazon Time Sync Service (link-local, no internet needed). GitHub App JWTs
# fail if the clock drifts (F42).
mkdir -p /etc/chrony/sources.d
echo "server 169.254.169.123 prefer iburst minpoll 4 maxpoll 4" >/etc/chrony/sources.d/aws.sources
systemctl enable --now chrony
chronyc reload sources >/dev/null 2>&1 || systemctl restart chrony

# AWS CLI v2 (snap published by AWS) for the DNS updater and SSM commands.
if ! command -v aws >/dev/null 2>&1; then
  retry 5 10 snap install aws-cli --classic
fi

# 2 GiB swapfile: protects system daemons only (pods run with NoSwap).
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
echo 'vm.swappiness=10' >/etc/sysctl.d/99-docify-swap.conf
sysctl -p /etc/sysctl.d/99-docify-swap.conf

# =============================================================================
# 3. ecr-credential-provider (kubelet plugin: ECR pulls via the instance role)
# =============================================================================
log "step 3: ecr-credential-provider $ECR_CP_VERSION"
ECR_CP_BIN=/usr/local/bin/ecr-credential-provider
if ! echo "$ECR_CP_SHA256  $ECR_CP_BIN" | sha256sum -c --status 2>/dev/null; then
  ECR_CP_URL="https://artifacts.k8s.io/binaries/cloud-provider-aws/$ECR_CP_VERSION/linux/$ARCH/ecr-credential-provider-linux-$ARCH"
  retry 5 10 curl -fsSL -o /tmp/ecr-credential-provider "$ECR_CP_URL"
  # Refuse to install anything whose checksum doesn't match the pinned one.
  echo "$ECR_CP_SHA256  /tmp/ecr-credential-provider" | sha256sum -c -
  install -m 0755 /tmp/ecr-credential-provider "$ECR_CP_BIN"
  rm -f /tmp/ecr-credential-provider
fi

mkdir -p /etc/rancher/k3s
cat >/etc/rancher/k3s/ecr-credential-provider.yaml <<'EOF'
apiVersion: kubelet.config.k8s.io/v1
kind: CredentialProviderConfig
providers:
  - name: ecr-credential-provider
    matchImages:
      - "*.dkr.ecr.*.amazonaws.com"
    defaultCacheDuration: "12h"
    apiVersion: credentialprovider.kubelet.k8s.io/v1
EOF

# =============================================================================
# 4. k3s
# =============================================================================
log "step 4: k3s $K3S_VERSION"
cat >/etc/rancher/k3s/config.yaml <<'EOF'
write-kubeconfig-mode: "0600"
secrets-encryption: true
node-name: docify-server
default-local-storage-path: /data/local-path
kubelet-arg:
  - "image-credential-provider-config=/etc/rancher/k3s/ecr-credential-provider.yaml"
  - "image-credential-provider-bin-dir=/usr/local/bin"
EOF

# Kubelet settings go in a KubeletConfiguration drop-in, not kubelet-arg flags:
# Kubernetes 1.36 removed --shutdown-grace-period* as flags (kubelet refuses to
# start: "unknown flag"), and the other ones are deprecated as flags too.
# k3s merges every file in this directory into the kubelet config.
mkdir -p /var/lib/rancher/k3s/agent/etc/kubelet.conf.d
cat >/var/lib/rancher/k3s/agent/etc/kubelet.conf.d/50-docify.conf <<'EOF'
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
systemReserved:
  cpu: 100m
  memory: 300Mi
kubeReserved:
  cpu: 100m
  memory: 300Mi
evictionHard:
  memory.available: 200Mi
  nodefs.available: "10%"
failSwapOn: false
shutdownGracePeriod: 180s
shutdownGracePeriodCriticalPods: 30s
EOF

# k3s must never start without /data mounted (otherwise Postgres would
# happily initialise an EMPTY database on the root disk - F25).
mkdir -p /etc/systemd/system/k3s.service.d
cat >/etc/systemd/system/k3s.service.d/10-require-data.conf <<'EOF'
[Unit]
RequiresMountsFor=/data
EOF

if ! k3s --version 2>/dev/null | grep -qF "$K3S_VERSION"; then
  # Install script pinned to the same tag as the binary ('+' must be URL-encoded).
  retry 5 10 curl -fsSL -o /tmp/k3s-install.sh \
    "https://raw.githubusercontent.com/k3s-io/k3s/$${K3S_VERSION/+/%2B}/install.sh"
  INSTALL_K3S_VERSION="$K3S_VERSION" INSTALL_K3S_SKIP_START=true sh /tmp/k3s-install.sh
  rm -f /tmp/k3s-install.sh
fi
systemctl daemon-reload
systemctl enable k3s
systemctl start k3s

log "step 4: waiting for the node to become Ready"
retry 60 10 test -f "$KUBECONFIG"
retry 60 10 kubectl wait --for=condition=Ready node --all --timeout=10s

# =============================================================================
# 5. docify-dns.service - DNS follows the instance's public IP (D26)
# =============================================================================
log "step 5: docify-dns.service"
cat >/usr/local/sbin/docify-dns-update <<'EOF'
#!/usr/bin/env bash
# UPSERT origin A records -> this instance's current public IPv4 (TTL 60).
# Runs at every boot (the public IP changes on each stop/start).
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
IMDS=http://169.254.169.254/latest
TOKEN="$(curl -fsS -X PUT "$IMDS/api/token" -H 'X-aws-ec2-metadata-token-ttl-seconds: 300')"
IP="$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" "$IMDS/meta-data/public-ipv4")"
CHANGES="[]"
for fqdn in ${origin_fqdns}; do
  CHANGES="$(jq -c --arg name "$fqdn" --arg ip "$IP" \
    '. + [{Action: "UPSERT", ResourceRecordSet: {Name: $name, Type: "A", TTL: 60, ResourceRecords: [{Value: $ip}]}}]' \
    <<<"$CHANGES")"
done
aws route53 change-resource-record-sets \
  --hosted-zone-id "${hosted_zone_id}" \
  --change-batch "{\"Comment\":\"docify-dns boot update\",\"Changes\":$CHANGES}" >/dev/null
echo "docify-dns: ${origin_fqdns} -> $IP"
EOF
chmod 0755 /usr/local/sbin/docify-dns-update

cat >/etc/systemd/system/docify-dns.service <<'EOF'
[Unit]
Description=Docify: point origin DNS records at this instance's public IP
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=900
StartLimitBurst=30

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/docify-dns-update
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable docify-dns.service
systemctl start docify-dns.service || log "WARN: docify-dns failed on first try; systemd will retry"

# =============================================================================
# 6. Argo CD + root Application (app-of-apps, D12)
# =============================================================================
log "step 6: helm $HELM_VERSION"
if ! helm version --short 2>/dev/null | grep -qF "$HELM_VERSION"; then
  HELM_TGZ="helm-$HELM_VERSION-linux-$ARCH.tar.gz"
  retry 5 10 curl -fsSL -o "/tmp/$HELM_TGZ" "https://get.helm.sh/$HELM_TGZ"
  echo "$HELM_SHA256  /tmp/$HELM_TGZ" | sha256sum -c -
  tar -xzf "/tmp/$HELM_TGZ" -C /tmp "linux-$ARCH/helm"
  install -m 0755 "/tmp/linux-$ARCH/helm" /usr/local/bin/helm
  rm -rf "/tmp/$HELM_TGZ" "/tmp/linux-$ARCH"
fi

# raw.githubusercontent.com/<owner>/<repo>/<rev>/<path> (public repo, no creds)
REPO_SLUG="$${GIT_REPO_URL#https://github.com/}"
REPO_SLUG="$${REPO_SLUG%.git}"
ARGOCD_VALUES_URL="https://raw.githubusercontent.com/$REPO_SLUG/$GIT_REVISION/$ARGOCD_VALUES_PATH"

if ! helm status argocd -n argocd >/dev/null 2>&1; then
  log "step 6: installing Argo CD chart $ARGOCD_CHART_VERSION"
  # Same values file, release name and namespace as the 'argocd' Application in
  # the root chart -> Argo CD adopts this release and manages itself afterwards.
  retry 5 10 curl -fsSL -o /etc/docify/argocd-values.yaml "$ARGOCD_VALUES_URL"
  retry 5 10 helm repo add argo https://argoproj.github.io/argo-helm --force-update
  retry 3 30 helm upgrade --install argocd argo/argo-cd \
    --namespace argocd --create-namespace \
    --version "$ARGOCD_CHART_VERSION" \
    -f /etc/docify/argocd-values.yaml \
    --wait --timeout 15m
else
  log "step 6: Argo CD already installed - skipping helm install"
fi

# Root Application. Non-secret, environment-specific values that must NOT live
# in the public repo (account id) are injected here as Helm parameters; the
# root chart passes them down to the child Applications.
VALUE_FILES_YAML=""
for f in $ROOT_VALUES_FILES; do
  VALUE_FILES_YAML="$VALUE_FILES_YAML        - $f"$'\n'
done

cat >/etc/docify/root-app.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: $GIT_REPO_URL
    targetRevision: $GIT_REVISION
    path: $ROOT_APP_PATH
    helm:
      releaseName: root
      valueFiles:
$VALUE_FILES_YAML      parameters:
        - name: global.aws.accountId
          value: "$ACCOUNT_ID"
          forceString: true
        - name: global.aws.hostedZoneId
          value: "$HOSTED_ZONE_ID"
          forceString: true
        - name: global.aws.region
          value: "$REGION"
          forceString: true
        - name: global.domain
          value: "$DOMAIN"
          forceString: true
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    retry:
      limit: 10
      backoff:
        duration: 30s
        factor: 2
        maxDuration: 5m
EOF
retry 10 15 kubectl apply -f /etc/docify/root-app.yaml

# =============================================================================
# 7. Done
# =============================================================================
date -u +%Y-%m-%dT%H:%M:%SZ >"$MARKER"
log "bootstrap complete - marker $MARKER written"
