"""Drive the dedicated measurement VM (D-023) through SSM: start/stop, sync an exact commit, run commands.

No SSH, no inbound ports, no GitHub token on the VM: code travels as a git bundle through the artifacts bucket.
Every remote command's output is written to s3://<bucket>/ssm/ for the audit trail.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

import boto3

from harness.artifacts import BUCKET
from harness.deploy.kind import ROOT

INSTANCE_ID = "i-013e08f65a16a17e5"  # terraform output worker_vm_instance_id
REGION = "us-east-1"
REPO = "/home/ubuntu/sbb"


def _session():
    return boto3.Session(region_name=REGION)  # credentials: AWS_PROFILE locally, instance role on the VM


def state() -> str:
    r = _session().client("ec2").describe_instances(InstanceIds=[INSTANCE_ID])
    return r["Reservations"][0]["Instances"][0]["State"]["Name"]


def start(wait: bool = True) -> str:
    ec2 = _session().client("ec2")
    ec2.start_instances(InstanceIds=[INSTANCE_ID])
    if wait:
        ec2.get_waiter("instance_running").wait(InstanceIds=[INSTANCE_ID])
        _wait_ssm()
    return state()


def stop(wait: bool = False) -> str:
    ec2 = _session().client("ec2")
    ec2.stop_instances(InstanceIds=[INSTANCE_ID])
    if wait:
        ec2.get_waiter("instance_stopped").wait(InstanceIds=[INSTANCE_ID])
    return state()


def _wait_ssm(timeout_s: int = 600) -> None:
    ssm = _session().client("ssm")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        info = ssm.describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": [INSTANCE_ID]}])
        if info["InstanceInformationList"] and info["InstanceInformationList"][0]["PingStatus"] == "Online":
            return
        time.sleep(10)
    raise TimeoutError("SSM agent did not come online")


def run(command: str, timeout_s: int = 3600, as_user: str = "ubuntu", cwd: str = REPO) -> dict:
    """Run a shell command on the VM as `as_user` in `cwd`; wait; return status and output (full output in S3)."""
    ssm = _session().client("ssm")
    inner = f"cd {cwd} 2>/dev/null || cd ~; export PATH=$HOME/.local/bin:$PATH; {command}"
    script = f"sudo -iu {as_user} bash -lc {_q(inner)}" if as_user != "root" else inner
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": [script], "executionTimeout": [str(timeout_s)]},
                         OutputS3BucketName=BUCKET, OutputS3KeyPrefix="ssm", TimeoutSeconds=600,
                         Comment=command[:100])
    return wait(r["Command"]["CommandId"])


def wait(cid: str) -> dict:
    """Poll a command until it ends. The job runs on the VM, so a network blip on the laptop must not end the
    wait: transient connection errors are retried (re-attach later with `harness vm wait <command-id>`)."""
    from botocore.exceptions import ConnectionError as BotoConnectionError, EndpointConnectionError

    ssm = _session().client("ssm")
    while True:
        time.sleep(5)
        try:
            inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        except (EndpointConnectionError, BotoConnectionError):
            time.sleep(30)
            continue
        if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
            return {"command_id": cid, "status": inv["Status"], "exit_code": inv["ResponseCode"],
                    "stdout": inv["StandardOutputContent"], "stderr": inv["StandardErrorContent"],
                    "s3_output": f"s3://{BUCKET}/ssm/{cid}/"}


def _q(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def sync(ref: str = "HEAD") -> dict:
    """Bundle the repo, upload it, and make the VM's checkout exactly `ref` (refuses a dirty working tree)."""
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", "harness", "loadtest",
                            "policies", "cases", "app",
                            "infra", "scripts", "analysis", "pyproject.toml", "uv.lock"],
                           capture_output=True, text=True, cwd=ROOT).stdout.strip()
    if dirty:
        raise RuntimeError("commit your changes first; vm-sync only ships committed code:\n" + dirty)
    commit = subprocess.run(["git", "rev-parse", ref], capture_output=True, text=True, cwd=ROOT,
                            check=True).stdout.strip()
    key = f"code/{commit}.bundle"
    with tempfile.TemporaryDirectory() as td:
        b = Path(td) / "repo.bundle"
        subprocess.run(["git", "bundle", "create", str(b), "--all"], cwd=ROOT, check=True, capture_output=True)
        _session().client("s3").upload_file(str(b), BUCKET, key)
    cmd = (f"aws s3 cp s3://{BUCKET}/{key} /tmp/repo.bundle --only-show-errors && "
           f"( [ -d {REPO}/.git ] || git clone -q /tmp/repo.bundle {REPO} ) && cd {REPO} && "
           f"git fetch -q /tmp/repo.bundle '+refs/heads/*:refs/remotes/bundle/*' && "
           # -f: the VM checkout is a deployment target; result files written there may collide with committed copies
           f"git checkout -q -f --detach {commit} && git status --short --untracked-files=no | head -5 && "
           f"uv sync -q && echo SYNCED $(git rev-parse HEAD)")
    out = run(cmd, timeout_s=900, cwd="/home/ubuntu")
    out["commit"] = commit
    return out
