#!/usr/bin/env bash
# P8 driver on the measurement VM (docs/p8-plan.md, D-038). Start it detached as root:
#   systemd-run --unit sbb-p8 bash /home/ubuntu/sbb/scripts/vm/p8_run.sh <label> <commit>
# 1) kubeconfig for the P8 EKS cluster, 2) wait for nodes, 3) 10 gold baseline runs on EKS (stop if < 8 clean),
# 4) 88 replays (resumable), 5) logs + DONE marker to S3, 6) stop this VM. The EKS cluster keeps running until
# Abdul approves its destruction.
set -uo pipefail
label="$1"; commit="$2"
B=s3://sbb-artifacts-<AWS_ACCOUNT_ID>/p8/$label
log=/var/log/sbb-p8.log
sudo -u ubuntu -H bash -lc "
  set -ex
  cd ~/sbb
  export PATH=\$HOME/.local/bin:\$PATH
  aws eks update-kubeconfig --name sbb-p8 --region us-east-1
  export SBB_PLATFORM=eks SBB_KUBE_CONTEXT=\$(kubectl config current-context) SBB_GIT_COMMIT=$commit
  kubectl --context \$SBB_KUBE_CONTEXT wait --for=condition=Ready nodes --all --timeout=900s
  kubectl --context \$SBB_KUBE_CONTEXT get nodes -o wide
  if [ ! -f app/baseline/$label.json ]; then
    uv run harness baseline --runs 10 --label $label
    ok=\$(python3 -c \"import json;print(sum(r['ok'] for r in json.load(open('runs/baseline/$label/baseline.json'))['runs']))\")
    aws s3 cp --recursive runs/baseline/$label $B/baseline/ --only-show-errors
    if [ \"\$ok\" -lt 8 ]; then echo \"BASELINE FAILED: \$ok/10 clean\"; aws s3 cp - $B/BASELINE_FAILED <<< \"\$ok\"; exit 3; fi
    cp runs/baseline/$label/baseline.json app/baseline/$label.json
  fi
  export SBB_BASELINE=$label
  uv run python scripts/p8/replay.py run $label
  echo done | aws s3 cp - $B/DONE
" > "$log" 2>&1
aws s3 cp "$log" "$B/driver.log" --only-show-errors || true
shutdown -h now
