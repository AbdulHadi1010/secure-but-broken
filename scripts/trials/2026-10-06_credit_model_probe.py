# Which credit-covered (AWS-sold) Bedrock models can this account call? One tiny Converse call each (cents).
# Billing class from the AWS Pricing API (service code AmazonBedrock = sold by AWS = covered by credits), 2026-10-06.
import json
from pathlib import Path

import boto3
from botocore.config import Config

from harness.repair.bedrock import converse

CANDIDATES = [
    "moonshotai.kimi-k2.5", "moonshot.kimi-k2-thinking", "us.moonshotai.kimi-k3", "zai.glm-5", "zai.glm-4.7",
    "qwen.qwen3-coder-next", "qwen.qwen3-coder-480b-a35b-v1:0", "minimax.minimax-m2.5",
    "mistral.mistral-large-3-675b-instruct", "mistral.devstral-2-123b", "nvidia.nemotron-super-3-120b",
    "us.amazon.nova-premier-v1:0", "us.amazon.nova-pro-v1:0", "deepseek.v3.2", "openai.gpt-oss-120b-1:0",
]
br = boto3.Session(region_name="us-east-1").client("bedrock-runtime", config=Config(read_timeout=120, retries={"max_attempts": 2}))
res = {}
for m in CANDIDATES:
    try:
        r = converse(br, m, "Answer briefly.", [{"role": "user", "text": "Reply with exactly one word: hello"}], 0.2, max_tokens=400)
        res[m] = {"ok": True, "reply": r["text"].strip()[:40], "in": r["input_tokens"], "out": r["output_tokens"],
                  "wall_s": r["wall_s"], "temperature_sent": r["temperature_sent"]}
    except Exception as e:  # noqa: BLE001
        res[m] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:150]}"}
    print(m.ljust(42), res[m], flush=True)
Path("scripts/trials/2026-10-06_credit_model_probe.result.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
