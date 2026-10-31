import pytest

from harness.baseline import band
from harness.checks.k6 import functional_result, load_result, parse_summary


def _run(p95, err, ok=True, ready=60.0):
    return {"ok": ok, "ready_s": ready, "restarts_total": 0, "load": {"p95_ms": p95, "error_rate": err}}


def test_band_follows_protocol_rule():
    b = band([_run(100, 0.0), _run(110, 0.002), _run(120, 0.001), _run(105, 0.0), _run(115, 0.0)])
    assert b["p95_ms"]["mean"] == pytest.approx(110)
    assert b["thresholds"]["p95_ms_max"] == pytest.approx(110 + 3 * b["p95_ms"]["sd"])
    assert b["thresholds"]["error_rate_max"] == pytest.approx(0.002 + 0.01)


def test_failed_runs_counted_but_excluded_from_band():
    b = band([_run(100, 0.0), _run(9999, 0.5, ok=False), _run(110, 0.0)])
    assert b["n_runs"] == 3 and b["n_ok"] == 2
    assert b["p95_ms"]["max"] == 110


def test_parse_summary_and_results():
    log = 'noise\n===K6_SUMMARY_BEGIN===\n{"root_group":{"checks":[{"name":"index 200","passes":1,"fails":0},' \
          '{"name":"checkout 200","passes":0,"fails":1}],"groups":[]},"metrics":{' \
          '"http_req_duration{phase:main}":{"values":{"p(95)":42.5,"p(99)":80,"med":10}},' \
          '"http_req_failed{phase:main}":{"values":{"rate":0.01}},"checks{phase:main}":{"values":{"rate":0.99}},' \
          '"http_reqs":{"values":{"count":1000,"rate":8.3}}}}\n===K6_SUMMARY_END===\n'
    s = parse_summary(log)
    assert functional_result(s)["pass_rate"] == 0.5
    lr = load_result(s)
    assert lr["p95_ms"] == 42.5 and lr["error_rate"] == 0.01 and lr["requests_total"] == 1000


def test_parse_summary_requires_markers():
    with pytest.raises(ValueError):
        parse_summary("no summary here")
