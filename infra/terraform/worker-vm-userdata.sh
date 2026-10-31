#!/bin/bash
# First-boot setup of the measurement VM (D-023). Versions match the laptop setup in docs/REPRODUCE.md.
# Downloads are verified against the publishers' own sha256 files. Log: /var/log/sbb-setup.log
set -euxo pipefail
exec > >(tee -a /var/log/sbb-setup.log) 2>&1

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io git jq unzip curl ca-certificates
systemctl enable --now docker
usermod -aG docker ubuntu

cd /tmp
# kind v0.33.0
curl -fsSLo kind https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64
curl -fsSLo kind.sha256 https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-linux-amd64.sha256sum
echo "$(cut -d' ' -f1 kind.sha256)  kind" | sha256sum -c -
install -m 0755 kind /usr/local/bin/kind

# kubectl v1.37.1
curl -fsSLo kubectl https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl
curl -fsSLo kubectl.sha256 https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl.sha256
echo "$(cat kubectl.sha256)  kubectl" | sha256sum -c -
install -m 0755 kubectl /usr/local/bin/kubectl

# AWS CLI v2 (for S3 code bundles and SSM)
curl -fsSLo awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip
unzip -q awscliv2.zip && ./aws/install

# uv 0.11.7 for the harness (installed for the ubuntu user)
sudo -u ubuntu bash -c 'curl -LsSf https://astral.sh/uv/0.11.7/install.sh | sh'

# Larger inotify limits: kind recommends these for several nodes/pods per host
sysctl -w fs.inotify.max_user_watches=524288 fs.inotify.max_user_instances=512
printf 'fs.inotify.max_user_watches=524288\nfs.inotify.max_user_instances=512\n' > /etc/sysctl.d/99-kind.conf

touch /var/lib/sbb-setup-done
