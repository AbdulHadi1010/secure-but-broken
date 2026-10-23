#!/bin/bash
# Fleet worker first boot (D-027): the image already holds the tools and warm image caches of the validated VM.
# Check out the exact commit of this batch, then qualify on gold and work the queue; the instance stops when idle.
set -euxo pipefail
exec > >(tee -a /var/log/sbb-worker.log) 2>&1
# Always stop the instance when the worker ends (idle, error or crash), after saving the log to S3.
trap 'sleep 2; aws s3 cp /var/log/sbb-worker.log s3://${bucket}/fleet-logs/${commit}/$(hostname).log --only-show-errors || true; shutdown -h now' EXIT
# Not `sudo -i`: it escapes the command and turns newlines into line continuations (nothing runs).
sudo -u ubuntu -H bash -lc '
  set -ex
  aws s3 cp s3://${bucket}/code/${commit}.bundle /tmp/repo.bundle --only-show-errors
  cd ~/sbb
  git fetch -q /tmp/repo.bundle "+refs/heads/*:refs/remotes/bundle/*"
  git checkout -q -f --detach ${commit}
  export PATH=$HOME/.local/bin:$PATH
  uv sync -q
  uv run harness worker --max-idle 900
'
