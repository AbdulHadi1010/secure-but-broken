#!/usr/bin/env bash
# Debug (2026-10-06): fleet workers died ~0.7 s into the user-data inner script with no error message.
# Re-run the same inner steps as root -> ubuntu with tracing, but end with `harness --help` instead of the worker.
# Finding: `sudo -iu` escapes the command so newlines become line continuations and the script collapses into
# `set -e aws ...` (runs nothing, exit 0). Fix: `sudo -u ubuntu -H bash -lc` (no -i).
# Usage (as root on the measurement VM): bash scripts/vm/debug_fleet_userdata.sh <commit>
commit="$1"
sudo -u ubuntu -H bash -lc "
  set -ex
  echo HOME=\$HOME PATH=\$PATH
  command -v aws git uv || true
  aws s3 cp s3://sbb-artifacts-<AWS_ACCOUNT_ID>/code/${commit}.bundle /tmp/repo-debug.bundle --only-show-errors
  cd ~/sbb
  git fetch -q /tmp/repo-debug.bundle '+refs/heads/*:refs/remotes/bundle/*'
  git status --short | head -5
  export PATH=\$HOME/.local/bin:\$PATH
  uv run harness --help | head -3
" 2>&1
echo "exit=$?"
