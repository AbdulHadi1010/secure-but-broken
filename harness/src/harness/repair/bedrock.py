"""One repairer (or moderator) call through the Bedrock Converse API, with everything needed for the record."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import boto3
from botocore.config import Config

MAX_TOKENS = 16000  # full manifest set is ~1300 lines; reasoning models (GPT-OSS) also spend tokens thinking

_PRICES = None


def cost_usd(model_id: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """Estimated cost of one call from harness/config/prices.json (Pricing API snapshot). None if no price known."""
    global _PRICES
    if _PRICES is None:
        import json
        from pathlib import Path

        _PRICES = json.loads((Path(__file__).resolve().parents[4] / "harness" / "config" / "prices.json")
                             .read_text(encoding="utf-8"))["models"]
    p = _PRICES.get(model_id)
    if p is None or input_tokens is None or output_tokens is None:
        return None
    return round(input_tokens / 1e6 * p["in"] + output_tokens / 1e6 * p["out"], 6)


def client(profile: str | None = None, region: str = "us-east-1"):
    return boto3.Session(profile_name=profile, region_name=region).client(
        "bedrock-runtime", config=Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=600))


def converse(bedrock, model_id: str, system: str, messages: list[dict], temperature: float | None,
             max_tokens: int = MAX_TOKENS) -> dict:
    """messages: [{"role": "user"|"assistant", "text": str}, ...]. Returns text (answer only), reasoning, usage."""
    cfg: dict = {"maxTokens": max_tokens}
    if temperature is not None:
        cfg["temperature"] = temperature
    req = {
        "modelId": model_id,
        "system": [{"text": system}],
        "messages": [{"role": m["role"], "content": [{"text": m["text"]}]} for m in messages],
        "inferenceConfig": cfg,
    }
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()
    temperature_dropped = False
    try:
        resp = bedrock.converse(**req)
    except bedrock.exceptions.ValidationException as e:
        if "temperature" not in str(e).lower():
            raise
        req["inferenceConfig"].pop("temperature", None)  # some models reject it; recorded below
        temperature_dropped = True
        resp = bedrock.converse(**req)
    blocks = resp["output"]["message"]["content"]
    answer = "".join(b.get("text", "") for b in blocks)
    reasoning = "".join(b.get("reasoningContent", {}).get("reasoningText", {}).get("text", "") for b in blocks)
    usage = resp.get("usage", {})
    # Some models (Kimi K3) cache prompts automatically and report the cached part separately; count it as input.
    # Cost charges cache tokens at the full input price (upper bound) until the bill shows the cache price.
    cache_r, cache_w = usage.get("cacheReadInputTokens") or 0, usage.get("cacheWriteInputTokens") or 0
    tokens_in = None if usage.get("inputTokens") is None else usage["inputTokens"] + cache_r + cache_w
    return {
        "model_id": model_id,
        "started": started,
        "wall_s": round(time.perf_counter() - t0, 2),
        "latency_ms": resp.get("metrics", {}).get("latencyMs"),
        "stop_reason": resp.get("stopReason"),
        "input_tokens": tokens_in,
        "input_tokens_uncached": usage.get("inputTokens"),
        "cache_read_tokens": cache_r,
        "cache_write_tokens": cache_w,
        "output_tokens": usage.get("outputTokens"),
        "temperature_sent": None if temperature_dropped else temperature,
        "cost_usd": cost_usd(model_id, tokens_in, usage.get("outputTokens")),
        "text": answer,
        "reasoning": reasoning or None,
    }
