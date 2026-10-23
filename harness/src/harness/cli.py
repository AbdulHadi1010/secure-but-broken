from pathlib import Path

import typer

app = typer.Typer(help="Secure but Broken? experiment harness", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Experiment harness commands."""


@app.command("bedrock-smoke")
def bedrock_smoke(
    config: Path = typer.Option(Path("harness/config/models.json"), help="Model config"),
    out_dir: Path = typer.Option(Path("runs/smoke"), help="Where to write the JSONL result"),
    region: str = typer.Option("us-east-1"),
    profile: str = typer.Option(None, help="AWS profile (default: AWS_PROFILE / default chain)"),
    stretch: bool = typer.Option(False, help="Also test stretch models"),
):
    """Call every configured model once via Converse and record latency + token usage."""
    from harness.bedrock_smoke import run_smoke

    results = run_smoke(config, out_dir, region, stretch, profile)
    for r in results:
        status = "OK " if r.ok else "FAIL"
        detail = (
            f"{r.latency_ms}ms in={r.input_tokens} out={r.output_tokens} reply={r.reply!r}"
            if r.ok
            else r.error
        )
        typer.echo(f"[{status}] {r.role:9} {r.model_id:55} {detail}")
    raise typer.Exit(code=0 if all(r.ok for r in results) else 1)


@app.command("gold-build")
def gold_build():
    """Rebuild app/gold/manifests.yaml from upstream + images.lock.json."""
    from harness.gold import build, harden, write

    docs = harden(build())
    out = write(docs)
    typer.echo(f"wrote {out} ({len(docs)} objects)")


@app.command("baseline")
def baseline(
    runs: int = typer.Option(5, help="Number of clean runs"),
    label: str = typer.Option(..., help="Run label, e.g. local-20261003"),
):
    """Deploy gold N times on fresh kind clusters; record functional, load and the working band."""
    import json

    from harness.baseline import run_baseline

    result = run_baseline(runs, label)
    for r in result["runs"]:
        load = r.get("load", {})
        typer.echo(f"{r['run_id']}: ok={r['ok']} ready={r.get('ready_s')}s restarts={r.get('restarts_total')} "
                   f"func={r.get('functional', {}).get('pass_rate')} p95={load.get('p95_ms')} err={load.get('error_rate')} "
                   f"{r.get('error', '')}")
    typer.echo(json.dumps(result["band"], indent=1))


@app.command("upload")
def upload(
    local: Path = typer.Argument(..., help="Local directory, e.g. runs/baseline/local-20261003"),
    prefix: str = typer.Argument(..., help="S3 key prefix, e.g. baseline/local-20261003"),
):
    """Upload a run directory to the S3 artifacts bucket."""
    from harness.artifacts import BUCKET, upload_dir

    keys = upload_dir(local, prefix)
    typer.echo(f"uploaded {len(keys)} files to s3://{BUCKET}/{prefix}")


@app.command("case-build")
def case_build(type_: str = typer.Argument(..., metavar="TYPE"), service: str = typer.Argument(...)):
    """Build cases/<type>-<service>/ from gold with one injected misconfiguration."""
    from harness.cases import build_case

    typer.echo(f"built {build_case(type_, service)}")


@app.command("case-validate")
def case_validate(case: str = typer.Argument(...), deploy: bool = typer.Option(True)):
    """Validate a case: flagged by scanners, gold clean for those rules, still deploys and works."""
    import json

    from harness.cases import CASES, validate_case

    res = validate_case(CASES / case, deploy=deploy)
    typer.echo(json.dumps({k: v for k, v in res.items() if k != "pods"}, indent=1))


@app.command("run-one")
def run_one_cmd(
    case: str = typer.Option(..., "--case"),
    model: str = typer.Option(..., "--model", help="model key from harness/config/models.json"),
    condition: str = typer.Option("C0", "--condition", help="C0 | C1 | C2-LLM | C2-template"),
    repeat: int = typer.Option(1, "--repeat"),
    keep_working: bool = typer.Option(False, "--keep-working", help="prompt wording variant (protocol open item)"),
    upload: bool = typer.Option(True, "--upload/--no-upload"),
):
    """One repair chain end to end: prompt -> Bedrock -> L1..L7 -> verdict [-> feedback -> ...] -> S3 + DynamoDB."""
    import json

    from harness.orchestrate.loop import run_chain

    r = run_chain(case, model, condition, repeat, keep_working, upload)
    typer.echo(json.dumps({k: r.get(k) for k in ("run_id", "final_verdict", "n_iterations", "iterations", "s3_prefix")},
                          indent=1))


@app.command("enqueue")
def enqueue_cmd(
    batch: str = typer.Option(..., help="batch label, e.g. pilot-20261005"),
    cases: str = typer.Option(..., help="comma-separated case ids, or 'all'"),
    models: str = typer.Option(..., help="comma-separated model keys"),
    conditions: str = typer.Option("C0,C1,C2-LLM,C2-template"),
    repeats: int = typer.Option(3),
    keep_working: bool = typer.Option(False, "--keep-working"),
):
    """Put one job per chain on the fleet queue and write the batch manifest to S3 (D-027)."""
    import json

    from harness.cases import CASES
    from harness.fleet import enqueue

    case_list = sorted(p.name for p in CASES.iterdir() if (p / "meta.json").exists()) if cases == "all" \
        else cases.split(",")
    typer.echo(json.dumps(enqueue(batch, case_list, models.split(","), conditions.split(","), repeats, keep_working)))


@app.command("worker")
def worker_cmd(max_idle: int = typer.Option(900), stop_when_idle: bool = typer.Option(True)):
    """Run on a fleet VM: qualify on gold, then process chains from the queue until it stays empty."""
    import json

    from harness.fleet import work

    typer.echo(json.dumps(work(max_idle, stop_when_idle), default=str))


@app.command("completeness")
def completeness_cmd(batch: str = typer.Argument(...)):
    """Planned vs finished chains of a batch."""
    import json

    from harness.fleet import completeness

    typer.echo(json.dumps(completeness(batch), indent=1))


@app.command("vm")
def vm_cmd(action: str = typer.Argument(..., help="start | stop | state | sync | run"),
           command: str = typer.Argument("", help="shell command for 'run'"),
           timeout: int = typer.Option(3600, help="seconds, for 'run'")):
    """Control the dedicated measurement VM (D-023) via SSM."""
    from harness import vm

    if action == "start":
        typer.echo(vm.start())
    elif action == "stop":
        typer.echo(vm.stop())
    elif action == "state":
        typer.echo(vm.state())
    elif action == "sync":
        r = vm.sync()
        typer.echo(f"{r['status']} exit={r['exit_code']} commit={r['commit']}")
        typer.echo(r["stdout"][-2000:] + r["stderr"][-2000:])
    elif action in ("run", "wait"):
        r = vm.run(command, timeout_s=timeout) if action == "run" else vm.wait(command)
        typer.echo(f"{r['status']} exit={r['exit_code']} output={r['s3_output']}")
        typer.echo(r["stdout"][-6000:] + r["stderr"][-3000:])
    else:
        raise typer.BadParameter(action)


if __name__ == "__main__":
    app()
