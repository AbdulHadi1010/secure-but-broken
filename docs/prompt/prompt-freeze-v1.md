# Prompts — FROZEN v1 (approved by Abdul 2026-10-06, D-031; version label v1-frozen-2026-10-06)

Once approved, these texts are frozen for the pilot and the full experiment; any change is a logged deviation.
Exact source: `harness/src/harness/repair/prompt.py`, `harness/src/harness/moderator/feedback.py`.

## Repairer — system prompt (sha256 c3d3f9fe6a00f61b3cc787f85043862f72c39146e8c3aa7a1968d460e81d34ae)
```
You are a Kubernetes engineer. You fix security findings in Kubernetes manifests. Reply with the complete corrected manifest set in exactly one ```yaml fenced block containing every object (separated by ---), and nothing else.
```

## Repairer — first user message, wording W0 (no "keep working")
```
A security scanner reported these findings for the manifests below.
- [<tool>] <rule id>: <rule title> (resource: <Kind>/<name>)

Fix the findings below. Return the full manifest set.

```yaml
<full case manifests>
```
```

## Repairer — first user message, wording W1 (adds "Keep the application working.")
```
A security scanner reported these findings for the manifests below.
- [<tool>] <rule id>: <rule title> (resource: <Kind>/<name>)

Fix the findings below. Keep the application working. Return the full manifest set.

```yaml
<full case manifests>
```
```
Placeholders are filled per case: one line per finding of the case's target and coupled scanner rules, as the scanner
reports them, then the full case manifests. Never included: the type label, fix class, reference fix, gold content.

## Feedback after a failed attempt
- C0: none (one attempt).
- C1: `The scanner still reports:` + one line per remaining finding + `Fix these findings. Return the complete manifest set.`
- C2-template: `What failed` / `Evidence` (numbered [E1]…) / `Constraints still required` built by `c2_template`.
- C2-LLM: moderator below, same evidence; leakage + grounding checks; 2 regenerations, then the C2 template.
- Unparsable reply (all conditions): a fixed format reminder.

## Moderator — system prompt (sha256 0ac76815560b8dde20da49ac9bbfbabad7ad5eae203de371e8013246c17cbfd5)
```
You review the result of an automated test of a Kubernetes manifest repair and write feedback for the engineer who will try again. Rules: (1) Use exactly three sections with these headings: 'What failed', 'Evidence', 'Constraints still required'. (2) Every bullet under 'What failed' must cite at least one evidence id like [E2] from the evidence list, and must only state what the evidence shows. (3) Never write YAML, code blocks, manifest snippets, field names with values, or the concrete fix; describe the problem, not the solution. (4) Do not invent evidence.
```

## Settings
| Setting | Value |
|---|---|
| Repairer temperature | 0.2 (recorded per call; a model that rejects it runs at its default, recorded as null) |
| Repairer max output tokens | 16,000 |
| Moderator | mistral.mistral-large-3-675b-instruct, temperature 0.0, max 2,000 tokens (D-032; was Claude Haiku 4.5) |
| Max iterations | 5 (C0: 1) |
| Repairers | us.moonshotai.kimi-k3, zai.glm-5, deepseek.v3.2 (D-032) |
