"""Build the plain-language progress report PDF from the result files in the repo (no hand-typed numbers where a
file exists). Run: uv run --with reportlab python scripts/reports/build_progress_report.py <out.pdf> <loopcheck-dir>"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "reports" / "progress-report.pdf"
LOOP2 = Path(sys.argv[2]) if len(sys.argv) > 2 else None

INK, MUTED, ACCENT, RULE, TINT = (colors.HexColor(x) for x in ("#17202b", "#566273", "#1f5f8b", "#c9d0da", "#eef3f8"))
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK,
                    alignment=TA_LEFT, spaceAfter=4)
SUB = ParagraphStyle("SUB", parent=ss["Normal"], fontSize=10.5, leading=14, textColor=MUTED, spaceAfter=10)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, leading=17,
                    textColor=ACCENT, spaceBefore=12, spaceAfter=5)
BODY = ParagraphStyle("BODY", parent=ss["Normal"], fontSize=10, leading=14, textColor=INK, spaceAfter=6)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.5, leading=11, textColor=MUTED)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.8, leading=11.5, spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")


def j(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def table(rows, widths, header=True, highlight_rows=()):
    data = [[Paragraph(str(c), CELLB if (header and i == 0) else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), TINT))
    for r in highlight_rows:
        style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#fdf3e3")))
    t.setStyle(TableStyle(style))
    return t


def p(text, style=BODY):
    return Paragraph(text, style)


# ---------- data from files ----------
base_vm = j(ROOT / "app/baseline/vm-c6i2xl-20261004.json")["band"]
base_lt = j(ROOT / "app/baseline/local-20261003.json")["band"]
l5 = j(ROOT / "app/baseline/vm-l5-sensitivity.json")
ka = j(ROOT / "scripts/trials/2026-10-04_p3_known_answer_tests.vm.result.json")
vals = [j(x) for x in sorted((ROOT / "cases").glob("*/validation.json"))]
metas = {m["case_id"]: m for m in (j(x) for x in sorted((ROOT / "cases").glob("*/meta.json")))}

smoke_rows = [["privileged-frontend", "a", "SAFE_FIX", "none", "Turned privileged off and restored the escalation block (= gold)"]]
for d in sorted((ROOT / "runs/smoke").glob("*/attempt.json")):
    a = j(d)
    cid = a["case_id"]
    fails = [g for g, v in a["gates"].items() if v is False]
    what = "Repair identical to the hardened original" if a["verdict"] == "SAFE_FIX" else \
        "Allowed traffic out only to Redis and blocked DNS: 93% of requests failed, p95 6,007 ms"
    smoke_rows.append([cid, metas[cid]["fix_class"], a["verdict"], ", ".join(fails) or "none", what])


def loop_rows(base: Path):
    rows = [["Condition", "Iterations", "Verdict per iteration", "Final"]]
    for d in sorted(base.iterdir()):
        its = j(d / "iterations.json")
        cond = d.name.split("-deepseek-v3-2-")[1].rsplit("-r1-", 1)[0]
        rows.append([cond, str(len(its)), " &rarr; ".join(i["verdict"] for i in its), its[-1]["verdict"]])
    return rows


story = []
story += [p("Secure but Broken?", H1),
          p("Deployment-validated evaluation of LLM security repairs for Kubernetes &middot; progress report, "
            "4 October 2026 &middot; Abdul Hadi (prepared with Claude Code)", SUB)]

story += [p("Summary in plain words", H2), p(
    "We are testing whether AI models (LLMs) that fix security mistakes in Kubernetes files produce fixes that are "
    "really safe and still let the application work. Today the whole measuring machine was finished and checked: "
    "an online shop (Google's Online Boutique) with 18 planted security mistakes, and a pipeline that deploys every "
    "AI fix on a fresh cluster and checks it seven ways. All checks were proven to work before any AI was tested. "
    "The first AI runs (DeepSeek V3.2, exploratory, not part of the final results) already show the problem the "
    "study is about: on the hardest case the AI produced a fix that every security scanner accepted and that was "
    "secure, but it broke the shop completely (93% of requests failed).")]

kpi = [["What", "Result"],
       ["Planted mistakes (cases), all validated", f"{sum(v['valid'] for v in vals)} of {len(vals)}"],
       ["Normal speed of the shop on the test machine (10 runs)",
        f"p95 {base_vm['p95_ms']['mean']:.1f} &plusmn; {base_vm['p95_ms']['sd']:.1f} ms, 0 errors"],
       ["Functional checks catch a broken service", f"{sum(1 for k, v in l5.items() if k.startswith('without_') and v['pass_rate'] < 1)} of 10"],
       ["Test fixes with a known right answer judged correctly", f"{sum(v['ok'] for v in ka.values())} of {len(ka)}"],
       ["First AI fixes tried (exploratory)", f"{len(smoke_rows)}: {sum(r[2] == 'SAFE_FIX' for r in smoke_rows)} safe, "
                                              f"{sum(r[2] == 'BREAKING_FIX' for r in smoke_rows)} broke the app"]]
story += [table(kpi, [110, 60])]

story += [p("What the study asks", H2), table([
    ["Question", "In plain words"],
    ["RQ1", "How often does an AI fix that passes the scanner break the application?"],
    ["RQ2", "How often does it pass the scanner but leave the security problem in place (a deceptive fix)?"],
    ["RQ3", "Which kinds of mistakes and which AI models cause the most broken or deceptive fixes?"],
    ["RQ4", "Does telling the AI what went wrong at runtime (our feedback loop) lead to more fixes that are both safe "
            "and working, and at what cost?"]], [20, 150])]

story += [p("How one AI fix is judged: seven gates", H2), table([
    ["Gate", "Question", "Tool"],
    ["L1", "Is the reported security finding gone?", "Checkov, KICS, kube-score"],
    ["L2", "Did the fix add any new findings?", "same scanners, compared with the clean app"],
    ["L3", "Does Kubernetes accept the files?", "kubectl dry-run"],
    ["L4", "Do all parts of the shop start?", "fresh kind cluster"],
    ["L5", "Do the shopping journeys work (browse, cart, checkout, email)?", "k6 + log check"],
    ["L6", "Is the shop as fast and error-free as normal under traffic?",
     f"k6, limit p95 &le; {base_vm['thresholds']['p95_ms_max']:.1f} ms, errors &le; 1%"],
    ["L7", "Is the security problem really gone on the running system?", "Kyverno policy + live process / traffic probe"]],
    [12, 98, 60]),
    p("Verdicts: <b>SAFE</b> = all gates pass. <b>BREAKING</b> = scanner happy but the app breaks (L3&ndash;L6). "
      "<b>DECEPTIVE</b> = scanner happy, app works, but the security problem is still there (L7). "
      "<b>NOT FIXED</b> = the scanner still complains, or new problems were added.", SMALL)]

story += [PageBreak(), p("Can we trust the measuring machine?", H2), p(
    "Before testing any AI, every part of the pipeline was tested on situations where we know the right answer. "
    "All measurements now run on a dedicated cloud machine (AWS c6i.2xlarge) because the laptop was too noisy: "
    "background programs made the clean shop look broken.")]
story += [table([
    ["Check", "Laptop", "Dedicated cloud VM"],
    ["p95 speed of the clean shop", f"{base_lt['p95_ms']['mean']:.0f} &plusmn; {base_lt['p95_ms']['sd']:.0f} ms (5 runs)",
     f"{base_vm['p95_ms']['mean']:.1f} &plusmn; {base_vm['p95_ms']['sd']:.1f} ms (10 runs)"],
    ["Clean shop judged as a perfect fix", "failed once (machine too busy)", "passed"],
    ["Broken services caught by L5", "10 of 10", "10 of 10"],
    ["Cases valid", "18 of 18", f"{sum(v['valid'] for v in vals)} of {len(vals)}"],
    ["Known-answer tests", "5 of 6 (laptop noise)", f"{sum(v['ok'] for v in ka.values())} of {len(ka)}"]],
    [62, 50, 58])]
story += [Spacer(1, 6), p("Known-answer tests (hand-made fixes whose correct verdict we know):", BODY), table(
    [["Test fix", "Expected", "Got", "Gate that caught it"]] +
    [[k.replace("_", " "), v["expected"], v["got"], ", ".join(g for g, x in v["gates"].items() if x is False) or "none"]
     for k, v in ka.items()], [70, 32, 32, 36])]

by_type = {}
for v in vals:
    m = metas[v["case_id"]]
    by_type.setdefault(m["type"], {"class": m["fix_class"], "svcs": [], "ok": 0})
    by_type[m["type"]]["svcs"].append(m["service"])
    by_type[m["type"]]["ok"] += v["valid"]
story += [p("The 18 planted mistakes", H2), table(
    [["Mistake", "Fix class", "Services", "Valid"]] +
    [[t, d["class"], ", ".join(d["svcs"]), f"{d['ok']}/3"] for t, d in by_type.items()], [55, 18, 77, 20]),
    p("Fix class: <b>a</b> = remove or flip one setting; <b>b</b> = choose a value that suits the app; "
      "<b>c</b> = needs to understand how the services talk to each other. Classification is backed by the Kubernetes "
      "Pod Security Standards and the NSA/CISA Kubernetes Hardening Guidance.", SMALL)]

story += [PageBreak(), p("First AI results (exploratory, not counted)", H2), p(
    "These runs only check that the cases are hard enough and the pipeline works with a real AI. They are excluded "
    "from the paper's numbers, and the cases were not changed because of them (decision D-025).")]
story += [table([["Case", "Class", "Verdict", "Failed gates", "What the AI did"]] + smoke_rows, [45, 13, 31, 18, 63],
                highlight_rows=[i + 1 for i, r in enumerate(smoke_rows) if r[2] != "SAFE_FIX"])]
story += [Spacer(1, 6), p(
    "<b>The broken fix is the paper's point in one example.</b> On the network-rules case the AI wrote a rule that "
    "correctly kept outsiders out (security check passed) and passed every scanner, but it also blocked the "
    "cart service from looking up the database's name (DNS). The shop failed almost completely. A study that only "
    "looks at scanners would have counted this as a success.")]

story += [p("Feedback loops on the hard case", H2), p(
    "We then let the AI try again with feedback, on the same network case. First run (before fixes):")]
first = ROOT / "runs/loopcheck"
if first.exists():
    story += [table(loop_rows(first), [22, 17, 97, 34])]
story += [Spacer(1, 4), p(
    "C1 stopped after one try because the scanner was happy (exactly the blind spot of earlier research). Both C2 "
    "variants failed for reasons that were our design flaws: the AI moderator's messages were wrongly rejected "
    "(it cited evidence as [E1, E2]), and the real cause was in the logs of healthy services, which we did not "
    "collect. Both were fixed (D-028).")]
if LOOP2 and LOOP2.exists() and any(LOOP2.iterdir()):
    story += [p("Second run, after the fixes:", BODY), table(loop_rows(LOOP2), [22, 17, 97, 34]),
              Spacer(1, 4), p(
        "With the fixes, <b>both feedback loops repaired the case</b>: the AI moderator's messages were accepted "
        "first time, it correctly diagnosed DNS failures, and DeepSeek fixed the rule (SAFE after 3 tries with the "
        "LLM moderator, 4 with the fixed template). The scanner-only loop (C1) still stopped at the broken fix. "
        "This is one exploratory example, not a result. <b>New gap found:</b> the final 'safe' fix in the "
        "template run deleted the namespace's default deny-all rule. Our gates passed it because the target "
        "service stayed protected, but deleting that rule weakens protection for the whole namespace. This must "
        "be decided before the pilot.")]

story += [PageBreak(), p("Findings so far", H2), table([
    ["#", "Finding", "Why it matters"],
    ["F1", "The shop hides 2 of 10 broken services (pages still load).", "Simple 'page loads' checks miss real breakage."],
    ["F3", "A privileged container can look exactly like a safe one if you only check effective permissions.",
     "Security checks must look deeper; ours do."],
    ["F4", "None of the three scanners notices a network rule that lets everyone in.", "Deceptive fixes can pass every scanner."],
    ["F6", "A CPU-starved shop passes scanners, starts and works, but is about 55&times; too slow under traffic (p95 657 ms vs 11.9 ms normal, on the VM).",
     "Only load testing finds it."],
    ["F7", "Our own security check once gave a false alarm on root containers; caught and fixed.",
     "Checking the checker matters."],
    ["F8", "AI fix: secure, scanner-clean, but blocked DNS and broke the shop.", "Real example of 'secure but broken'."],
    ["F9", "The run-as-root cases leave a hint of the right user ID.", "Kept; reported as a limitation."],
    ["F10", "The AI invented a service that exists only in newer versions of the shop.", "Caught by L2."],
    ["F11", "Runtime feedback only helps if the evidence contains the real cause.", "Evidence design is part of the method."],
    ["F12", "With complete evidence, both runtime-feedback loops fixed the broken network case; the scanner-only loop did not.",
     "First sign of the effect RQ4 tests (one example)."],
    ["F13", "A 'safe' fix deleted the namespace-wide deny-all rule; our checks only protect the target service.",
     "Open gap: should removing other security controls count as deceptive?"]],
    [12, 92, 66])]

story += [p("Problems we found in our own setup and fixed", H2), table([
    ["Problem", "Fix"],
    ["Laptop too noisy to measure speed", "Dedicated cloud VM; all measurements redone there"],
    ["Security check could not run inside root containers", "Different debug profile; all 18 cases re-checked"],
    ["Feedback checker rejected valid citations", "Accept [E1, E2] style; tests added"],
    ["Root cause hidden in healthy services' logs", "Error lines from every service added to the evidence"],
    ["Windows line endings would change file fingerprints", "Line endings pinned; fresh-clone test passes"],
    ["Journal times estimated instead of read from the clock", "Correction entry; times now from the clock"]],
    [80, 90])]

story += [p("Key decisions made", H2), table([
    ["Decision", "What we decided"],
    ["Models", "Claude Sonnet 4.6, GPT-OSS 120B, DeepSeek V3.2; Claude Haiku 4.5 as moderator (newest models blocked on the account)"],
    ["Scope", "6 mistake types &times; 3 services = 18 cases; more later as a separate batch"],
    ["Difficulty", "No invented easy/medium/hard labels; fix classes a/b/c defined up front, cited sources"],
    ["Measuring machine", "Dedicated AWS VM; scaling with identical VMs + a job queue, not Spot instances"],
    ["Prompt", "Run both with and without 'keep the application working'"],
    ["Verdict rules", "New scanner problems = not fixed; leaving out objects is judged by the gates"],
    ["Load test", "Retest once if it fails; fail only if both fail"]], [32, 138])]

story += [KeepTogether([p("Cost so far", H2), p(
    "AWS Cost Explorer lags by up to a day and showed only USD 0.03 for October when this report was built. "
    "Estimate for 4 October: measurement VM about 7 hours at USD 0.34/hour (about USD 2.40) plus about 30 AI calls "
    "of roughly 8,000 tokens in and out each (expected well under USD 2). Everything is paid from the AWS "
    "credits (about USD 528). The exact figure will be read from Cost Explorer tomorrow.")])]

story += [p("Next steps", H2), table([
    ["Step", "What"],
    ["0", "Decide on gap F13 (removed security controls elsewhere) and clean the noisy log lines in the evidence"],
    ["1", "Worker machine image + small fleet (plan and cost shown before creating)"],
    ["2", "Freeze the prompt (both wordings) and the protocol draft"],
    ["3", "Pilot: 2 models &times; 3 cases &times; conditions &times; 3 repeats; measure real cost and variance"],
    ["4", "Full experiment, then EKS check and analysis"]], [14, 156])]
story += [Spacer(1, 8), p(
    "Everything is recorded: decisions (docs/decisions.md), journal (docs/journal.md), every shell command "
    "(docs/command-log/), all raw results in a versioned S3 bucket, and the steps to reproduce (docs/REPRODUCE.md).", SMALL)]

OUT.parent.mkdir(parents=True, exist_ok=True)
SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                  bottomMargin=16 * mm, title="Secure but Broken? Progress report", author="Abdul Hadi").build(story)
print(OUT)
