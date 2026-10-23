"""P0 smoke test: one hello-world Converse call per configured model.

Records model ID, latency and token usage so we know every model works (and what it costs per
token) before anything else is built. Errors are recorded, not raised, so one bad model does not
hide the others.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from pydantic import BaseModel

PROMPT = "Reply with exactly one word: hello"


class ModelSpec(BaseModel):
    key: str
    vendor: str
    model_id: str
    temperature: float | None = None
    role: str = "repairer"


class SmokeResult(BaseModel):
    ts: str
    key: str
    role: str
    vendor: str
    model_id: str
    ok: bool
    wall_s: float | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    stop_reason: str | None = None
    reply: str | None = None
    temperature_sent: float | None = None
    error: str | None = None


def load_models(config_path: Path, include_stretch: bool = False) -> list[ModelSpec]:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    default_t = cfg["temperature"]
    groups = [("repairer", cfg["repairers"])]
    if include_stretch:
        groups.append(("repairer", cfg["stretch_repairers"]))
    specs = [
        ModelSpec(**{**m, "role": role, "temperature": m.get("temperature", default_t)})
        for role, items in groups
        for m in items
    ]
    mod = cfg["moderator"]
    specs.append(ModelSpec(**{**mod, "role": "moderator"}))
    return specs


def _converse(client, spec: ModelSpec, send_temperature: bool) -> dict:
    kwargs = {
        "modelId": spec.model_id,
        "messages": [{"role": "user", "content": [{"text": PROMPT}]}],
        "inferenceConfig": {"maxTokens": 64},
    }
    if send_temperature and spec.temperature is not None:
        kwargs["inferenceConfig"]["temperature"] = spec.temperature
    return client.converse(**kwargs)


def run_one(client, spec: ModelSpec) -> SmokeResult:
    base = dict(
        ts=datetime.now(timezone.utc).isoformat(),
        key=spec.key,
        role=spec.role,
        vendor=spec.vendor,
        model_id=spec.model_id,
    )
    sent_temp = True
    t0 = time.perf_counter()
    try:
        try:
            resp = _converse(client, spec, send_temperature=True)
        except client.exceptions.ValidationException as e:
            # Some models reject a temperature override; record that fact (it matters for the paper).
            if "temperature" not in str(e).lower():
                raise
            sent_temp = False
            t0 = time.perf_counter()
            resp = _converse(client, spec, send_temperature=False)
        wall = time.perf_counter() - t0
        usage = resp.get("usage", {})
        blocks = resp["output"]["message"]["content"]
        text = "".join(b.get("text", "") for b in blocks).strip()
        return SmokeResult(
            **base,
            ok=True,
            wall_s=round(wall, 3),
            latency_ms=resp.get("metrics", {}).get("latencyMs"),
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
            total_tokens=usage.get("totalTokens"),
            stop_reason=resp.get("stopReason"),
            reply=text[:200],
            temperature_sent=spec.temperature if sent_temp else None,
        )
    except Exception as e:  # noqa: BLE001 - record any failure per model
        return SmokeResult(**base, ok=False, wall_s=round(time.perf_counter() - t0, 3), error=f"{type(e).__name__}: {e}"[:500])


def run_smoke(config_path: Path, out_dir: Path, region: str, include_stretch: bool, profile: str | None) -> list[SmokeResult]:
    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client("bedrock-runtime", config=Config(retries={"max_attempts": 2, "mode": "standard"}, read_timeout=120))
    results = [run_one(client, spec) for spec in load_models(config_path, include_stretch)]
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"bedrock_smoke_{stamp}.jsonl"
    out.write_text("\n".join(r.model_dump_json() for r in results) + "\n", encoding="utf-8", newline="\n")
    return results
