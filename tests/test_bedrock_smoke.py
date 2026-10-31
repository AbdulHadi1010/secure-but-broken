from pathlib import Path

from harness.bedrock_smoke import load_models, run_one, ModelSpec

CONFIG = Path(__file__).resolve().parents[1] / "harness" / "config" / "models.json"


def test_config_has_three_repairers_and_one_moderator():
    specs = load_models(CONFIG)
    assert [s.role for s in specs].count("repairer") == 3
    mods = [s for s in specs if s.role == "moderator"]
    assert len(mods) == 1 and mods[0].temperature == 0.0


def test_model_ids_are_unique_and_us_scoped():
    specs = load_models(CONFIG, include_stretch=True)
    ids = [s.model_id for s in specs]
    assert len(ids) == len(set(ids))
    assert not any(i.startswith("global.") for i in ids)


class _FakeClient:
    class exceptions:
        class ValidationException(Exception):
            pass

    def converse(self, **kw):
        return {
            "output": {"message": {"content": [{"text": "hello"}]}},
            "usage": {"inputTokens": 9, "outputTokens": 1, "totalTokens": 10},
            "metrics": {"latencyMs": 123},
            "stopReason": "end_turn",
        }


def test_run_one_records_usage():
    r = run_one(_FakeClient(), ModelSpec(key="k", vendor="v", model_id="m", temperature=0.2))
    assert r.ok and r.input_tokens == 9 and r.output_tokens == 1 and r.latency_ms == 123
