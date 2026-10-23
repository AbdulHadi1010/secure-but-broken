"""Feedback between iterations (CLAUDE.md §3, §5).

C1          : raw scanner findings in a fixed template; stops once the scanner is clean (prior-work status quo)
C2-template : deterministic What failed / Evidence / Constraints message from the evaluator record
C2-LLM      : moderator LLM (Haiku 4.5, temperature 0) writes the same three sections from the same numbered
              evidence; every message passes a leakage check and a grounding check, else regenerate (max 2),
              else fall back to the C2 template. Everything is logged.
The moderator never receives gold content, the type label, the fix class or the reference fix.
"""

from __future__ import annotations

import hashlib
import re

GATE_WORDS = {
    "l1": "the scanner still reports the original security finding",
    "l2": "the scanner reports findings that the original application did not have",
    "l3": "the API server rejected the manifests",
    "l4": "not every workload became ready",
    "l5": "user journeys failed",
    "l6": "the application did not stay within its normal error rate and latency under load",
    "l7": "the security intent is not met on the running system",
}

CONSTRAINTS = ("The security findings must stay fixed and the security intent must be met on the running system. "
               "Do not weaken or remove other security settings. Return the complete manifest set.")


# ---------- evidence ----------

def evidence_items(rec: dict) -> list[tuple[str, str]]:
    """Numbered, factual evidence from one attempt record. Only observations; no fixes."""
    items: list[str] = []
    st = rec.get("static", {})
    for k in st.get("remaining_target_findings", []):
        items.append(f"scanner finding still present: {k}")
    for k in st.get("findings_beyond_gold", []):
        if k not in st.get("remaining_target_findings", []):
            items.append(f"scanner finding not present originally: {k}")
    if rec.get("l3_error"):
        items.append(f"API server error: {rec['l3_error'][-400:]}")
    ev = rec.get("evidence", {})
    for p in ev.get("pods", []):
        if not p["ready"] or p["restarts"]:
            why = ", ".join(f"{k}={p[k]}" for k in ("last_terminated_reason", "waiting_reason") if p.get(k))
            items.append(f"pod {p['name']} phase={p['phase']} ready={p['ready']} restarts={p['restarts']}"
                         + (f" ({why})" if why else ""))
    for line in ev.get("warning_events", [])[-8:]:
        items.append(f"warning event: {' '.join(line.split())[:300]}")
    for pod, tail in ev.get("log_tails", {}).items():
        last = [x for x in tail.splitlines() if x.strip()][-3:]
        if last:
            items.append(f"log tail of {pod}: {' | '.join(last)[:400]}")
    for pod, lines in ev.get("error_lines", {}).items():
        items.append(f"error lines in the log of {pod}: {' | '.join(lines)[:500]}")
    for name, c in rec.get("functional", {}).get("checks", {}).items():
        if c.get("fails"):
            items.append(f"user journey check failed: {_check_words(name)}")
    load = rec.get("load")
    if load and rec.get("gates", {}).get("l6") is False:
        b = load["band"]
        items.append(f"load test: {load['error_rate']:.1%} of requests failed (must be at most {b['error_rate_max']:.1%}); "
                     f"95th percentile latency {load['p95_ms']:.1f} ms (must be at most {b['p95_ms_max']:.1f} ms)")
    it = rec.get("intent", {})
    if it and it.get("pass") is False:
        for f in it.get("static", {}).get("failures", []):
            items.append(f"policy check failed: {f}")
        r = it.get("runtime", {})
        if not it.get("runtime_ok"):
            facts = {k: r.get(k) for k in ("cap_bnd", "no_new_privs", "uid_effective", "limits", "result") if k in r}
            if "cap_bnd" in facts:
                facts["cap_bnd"] = f"{facts['cap_bnd']:#x}"
            items.append(f"runtime observation of the deployed service: {facts}")
        # D-034: no-regression results (D-030) were judged but never shown; observations vs the given manifests only
        reg = it.get("regression", {})
        for f in reg.get("policy_failures_other_workloads", []):
            items.append(f"policy check failed on another workload: {f}")
        for p in reg.get("netpol_problems", []):
            items.append(f"compared with the manifests you were given: {p}")
        for s in reg.get("opened_to_outside", []):
            items.append(f"service {s} is now reachable from a pod outside the namespace")
        for s in reg.get("probe_unknown", []):
            items.append(f"isolation of service {s} could not be confirmed")
    return [(f"E{i}", t) for i, t in enumerate(items, 1)]


def _check_words(name: str) -> str:
    """k6 check names as plain words (the moderator misread 'index 200' as 'returned 200')."""
    if name.endswith(" 200"):
        return f"'{name[:-4]}' did not return HTTP 200"
    return f"'{name}' was not true"


# ---------- C1 ----------

def c1_message(rec: dict) -> str | None:
    """None when the scanner is clean: C1 has nothing further to say (loop ends)."""
    st = rec.get("static", {})
    keys = sorted(set(st.get("remaining_target_findings", [])) | set(st.get("findings_beyond_gold", [])))
    if not keys:
        return None
    return "The scanner still reports:\n" + "\n".join(f"- {k}" for k in keys) + \
        "\nFix these findings. Return the complete manifest set."


# ---------- C2 template ----------

def c2_template(rec: dict) -> str:
    g = rec.get("gates", {})
    failed = [gate for gate in ("l1", "l2", "l3", "l4", "l5", "l6", "l7") if g.get(gate) is False]
    ev = evidence_items(rec)
    return ("What failed\n" + "\n".join(f"- {GATE_WORDS[x]}" for x in failed) +
            "\n\nEvidence\n" + "\n".join(f"[{i}] {t}" for i, t in ev) +
            f"\n\nConstraints still required\n- {CONSTRAINTS}")


# ---------- C2 LLM moderator ----------

MODERATOR_SYSTEM = (
    "You review the result of an automated test of a Kubernetes manifest repair and write feedback for the engineer "
    "who will try again. Rules: (1) Use exactly three sections with these headings: 'What failed', 'Evidence', "
    "'Constraints still required'. (2) Every bullet under 'What failed' must cite at least one evidence id like [E2] "
    "from the evidence list, and must only state what the evidence shows. (3) Never write YAML, code blocks, "
    "manifest snippets, field names with values, or the concrete fix; describe the problem, not the solution. "
    "(4) Do not invent evidence."
)


def moderator_user(rec: dict, latest_manifest: str) -> str:
    ev = evidence_items(rec)
    g = rec.get("gates", {})
    failed = [GATE_WORDS[x] for x in ("l1", "l2", "l3", "l4", "l5", "l6", "l7") if g.get(x) is False]
    return ("Failed checks:\n" + "\n".join(f"- {f}" for f in failed) + "\n\nEvidence:\n" +
            "\n".join(f"[{i}] {t}" for i, t in ev) + "\n\nThe engineer's latest manifests:\n" + latest_manifest)


MODERATOR_PROMPT_SHA = hashlib.sha256(MODERATOR_SYSTEM.encode()).hexdigest()[:16]

YAML_LINE = re.compile(r"^\s*-?\s*[A-Za-z][A-Za-z0-9_.-]*:\s+\S", re.MULTILINE)
SECTIONS = ("What failed", "Evidence", "Constraints still required")


def gold_diff_tokens(gold_yaml: str, case_yaml: str) -> set[str]:
    """Lines in gold that are not in the case (= the answer), plus their values. Used ONLY by the leakage check."""
    case_lines = {x.strip() for x in case_yaml.splitlines()}
    out = set()
    for x in gold_yaml.splitlines():
        s = x.strip()
        if s and s not in case_lines and not s.startswith("#"):
            out.add(s)
            if ":" in s:
                v = s.split(":", 1)[1].strip().strip("'\"")
                if len(v) >= 3 and v not in {"true", "false", "null", "[]", "{}"}:
                    out.add(v)
    return out


def leakage_check(msg: str, diff_tokens: set[str]) -> list[str]:
    problems = []
    if "```" in msg:
        problems.append("code block")
    if YAML_LINE.search(msg.split("Evidence", 1)[0]) or YAML_LINE.search(msg.split("Constraints still required", 1)[-1]):
        problems.append("yaml-like key: value line")
    for t in diff_tokens:
        if re.search(r"(?<![\w.])" + re.escape(t) + r"(?![\w.])", msg):
            problems.append(f"gold value: {t[:40]}")
    return problems


def grounding_check(msg: str, evidence_ids: set[str]) -> list[str]:
    problems = [f"missing section: {s}" for s in SECTIONS if s not in msg]
    wf = msg.split("What failed", 1)[-1].split("Evidence", 1)[0]
    bullets = [b for b in wf.splitlines() if b.strip().startswith(("-", "*", "•"))]
    if not bullets:
        problems.append("no bullets under What failed")
    for b in bullets:
        # citations may be single [E2] or grouped [E1, E2, E3] (D-028)
        cited = {e for grp in re.findall(r"\[([^\]]*)\]", b) for e in re.findall(r"E\d+", grp)}
        if not cited:
            problems.append(f"uncited claim: {b.strip()[:60]}")
        elif cited - evidence_ids:
            problems.append(f"cites unknown evidence: {sorted(cited - evidence_ids)}")
    return problems


def c2_llm(rec: dict, latest_manifest: str, diff_tokens: set[str], call) -> dict:
    """call(system, user) -> text. Returns the message used plus a full log of every try."""
    ids = {i for i, _ in evidence_items(rec)}
    tries = []
    for n in range(3):  # first try + 2 regenerations
        text = call(MODERATOR_SYSTEM, moderator_user(rec, latest_manifest))
        leak, ground = leakage_check(text, diff_tokens), grounding_check(text, ids)
        tries.append({"try": n + 1, "text": text, "leakage": leak, "grounding": ground})
        if not leak and not ground:
            return {"message": text, "source": "llm", "tries": tries, "prompt_sha": MODERATOR_PROMPT_SHA}
    return {"message": c2_template(rec), "source": "template_fallback", "tries": tries,
            "prompt_sha": MODERATOR_PROMPT_SHA}
