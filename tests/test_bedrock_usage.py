"""Token and cost accounting of bedrock.converse, incl. models that cache prompts (Kimi K3)."""

from harness.repair import bedrock


class _Br:
    class exceptions:
        ValidationException = type("VE", (Exception,), {})

    def __init__(self, usage):
        self.usage = usage

    def converse(self, **req):
        return {"output": {"message": {"content": [{"text": "ok"}]}}, "usage": self.usage, "stopReason": "end_turn"}


def test_cache_tokens_counted_as_input():
    u = {"inputTokens": 7, "outputTokens": 50, "cacheReadInputTokens": 0, "cacheWriteInputTokens": 483}
    r = bedrock.converse(_Br(u), "us.moonshotai.kimi-k3", "s", [{"role": "user", "text": "x"}], None)
    assert r["input_tokens"] == 490 and r["input_tokens_uncached"] == 7 and r["cache_write_tokens"] == 483
    assert r["cost_usd"] == round(490 / 1e6 * 3.00 + 50 / 1e6 * 16.50, 6)


def test_plain_usage_unchanged():
    r = bedrock.converse(_Br({"inputTokens": 410, "outputTokens": 11}), "zai.glm-5", "s",
                         [{"role": "user", "text": "x"}], 0.2)
    assert r["input_tokens"] == 410 and r["cache_read_tokens"] == 0
