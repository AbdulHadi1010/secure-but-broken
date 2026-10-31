#!/usr/bin/env bash
# Run the fleet worker on an already-created (restarted) fleet VM via SSM: user data only runs on first boot.
# Fetch the code bundle of <commit>, check it out, then qualify on gold and work the queue; the worker stops the
# instance when the queue stays empty. Start it detached (SSM kills background children when its command ends):
#   systemd-run --unit sbb-rerun bash fleet_rerun_worker.sh <commit>
set -euo pipefail
commit="$1"
sudo -u ubuntu -H bash -lc "
  set -ex
  aws s3 cp s3://sbb-artifacts-<AWS_ACCOUNT_ID>/code/${commit}.bundle /home/ubuntu/repo-rerun.bundle --only-show-errors
  cd ~/sbb
  git fetch -q /home/ubuntu/repo-rerun.bundle '+refs/heads/*:refs/remotes/bundle/*'
  git checkout -q -f --detach ${commit}
  export PATH=\$HOME/.local/bin:\$PATH
  uv sync -q
  uv run harness worker --max-idle 900
" > /var/log/sbb-worker-rerun.log 2>&1 || true
aws s3 cp /var/log/sbb-worker-rerun.log "s3://sbb-artifacts-<AWS_ACCOUNT_ID>/fleet-logs/${commit}/$(hostname)-rerun.log" --only-show-errors || true
shutdown -h now
