# Structured literature search — protocol (v1, approved by Abdul 2026-10-06)

Purpose: show that the research gap is real, with a search anyone can repeat (a lightweight systematic search, not a
full systematic review). Written before searching; changes after the search starts are logged in this file.

## Question
Which studies evaluate LLM-generated repairs (or generation) of infrastructure-as-code or Kubernetes configurations, and
how do they judge success: static scanner / verification only, deployment, application behaviour, or security intent
on the running system?

## Sources
| Source | Why |
|---|---|
| IEEE Xplore | SE and security venues (ICSE, ASE, QRS, …) |
| ACM Digital Library | FSE, MSR, CCS |
| Scopus | broad index, catches journals (EMSE, TOSEM, JSS) |
| arXiv (cs.SE, cs.CR) | most 2025–2026 work appears here first |
| Google Scholar | only for forward/backward snowballing of included papers |

Period: January 2023 – October 2026 (LLM era). Language: English.

## Search string (adapted to each database's syntax; exact strings and dates recorded per run)
```
("large language model*" OR LLM* OR GPT* OR "code model*" OR "generative AI")
AND ("infrastructure as code" OR IaC OR Kubernetes OR Terraform OR Helm OR "cloud configuration" OR misconfiguration*)
AND (repair* OR fix* OR remediat* OR harden* OR generat*)
```

## Inclusion criteria (all must hold)
1. An LLM produces or repairs IaC / Kubernetes / cloud configuration.
2. The study evaluates the produced configurations empirically (not only a position or vision paper).
3. Peer-reviewed paper, or arXiv preprint with an evaluation section.

## Exclusion criteria (any one excludes)
1. LLMs only explain or classify misconfigurations, without producing a configuration.
2. Application code security (not configuration).
3. Non-English, no full text, duplicate version of an included paper (keep the latest).

## Screening
1. Title and abstract screening, then full-text screening, each with the reason recorded for every exclusion.
2. A random 20% of decisions is screened again by a second person (or by Abdul a week later); disagreements resolved
   and agreement reported.
3. One round of backward and forward snowballing on the included set.
4. Counts at each step reported as a PRISMA-style flow (found → after duplicates → after title/abstract → after full text
   → after snowballing).

## Data extracted per included paper (= the columns of the gap table)
Venue and year · artefact (Kubernetes, Terraform, …) · task (repair, generation, hardening) · models · success criterion ·
deploys the result (yes/no, where) · checks application behaviour (function, load) · checks security intent at runtime ·
feedback loop (none, scanner, runtime) · dataset size · main finding.

## Seed set
The six works already in our notes (LLMSecConfig, TerraProbe, IaC-Guard-V, KuTIE, KubeGuard, IaCGen/DPIaC-Eval) and the
papers in Abdul's literature matrix (Literature_Matrix_Cloud_DevOps_AI.xlsx). The search must find these; if it misses
any, the search string is too narrow and is revised (revision logged).

## Output
`docs/lit-review/search-log.md` (every query, date, hit count), `docs/lit-review/screening.csv`, the PRISMA counts, and
an updated research-gap table for the paper and the pitch.

## Changes after the search started (logged as the protocol requires)
- 2026-10-17 — **Scopus replaced by OpenAlex.** Scopus needs an institutional login that the automated search cannot use;
  OpenAlex (open index of ~250M works incl. IEEE, ACM, Springer, Elsevier venues) runs the same string through a public
  API, so the search is repeatable by anyone. The exact filter is in search-log.md.
- 2026-10-17 — **Wildcards expanded.** Neither arXiv nor OpenAlex supports truncation; each truncated term (LLM*, repair*,
  fix*, remediat*, harden*, generat*, misconfiguration*) is expanded into its word forms (scripts/lit/search.py).
- 2026-10-17 — **arXiv query split.** The full three-group query times out on the arXiv API; it is run once per IaC term,
  and the task group is applied to title+abstract locally (same logical query). Categories: cs.SE, cs.CR, cs.AI, cs.DC, cs.LG, cs.CL.
- 2026-10-17 — **No language filter in OpenAlex.** OpenAlex's language field is often empty (523 hits without, 251 with
  `language:en`); English-only is applied at screening instead (exclusion criterion 3).
- 2026-10-17 — **IEEE Xplore and ACM DL** not yet run (no open API usable from the script); pending decision with Abdul.
- 2026-10-17 — **Seed check against Abdul's literature matrix (Excel, read with his permission).** Of 21 in-scope seed
  papers (themes A, C and the two repair papers of theme B; themes D-F are outside the question), v1 found 17. Missed:
  A1 and A2 (Ansible), C2 (Ansible, "self-healing"), A4 IaC-Eval. Per this protocol the string was revised:
  - **v1.1**: model group + "language model(s)", "foundation model(s)"; IaC group + Ansible, CloudFormation, Pulumi,
    Puppet, Chef, Dockerfile(s), Docker Compose -> 192 new records (R0517-R0708); A1, A2 found.
  - **v1.2**: task group + "self-healing" -> 12 new records (R0709-R0720); C2 found.
  - **IaC-Eval (A4) cannot be found by any title/abstract search**: OpenAlex has no abstract for it and it is not on
    arXiv. It is added through snowballing. This is a known limitation of abstract-based searching.
  Earlier records keep their ids and decisions (scripts/lit/add_records.py); new records are screened with the same codes.
- 2026-10-17 — **IEEE Xplore run** in the browser (v1.2 string with native wildcards, 2023-2026, metadata search):
  232 hits, 127 new records (R0721-R0847), abstracts taken from IEEE's own search service (first 450 characters).
- 2026-10-17 — **Second screener = independent AI session** (Abdul asked Claude to do the re-screening): a separate
  session, given only the sampled titles/abstracts and the criteria, with no access to the first decisions. This is
  weaker than a human second screener and is reported as such. Block 1 (144 of R0001-R0720): stage agreement 92.4%,
  kappa 0.78. Disagreements resolved conservatively (forward to full text if either screener says so); 2 records
  changed X -> ?. Samples are drawn once per block and never redrawn (scripts/lit/screening.py).
- 2026-10-17 — Block 2 (25 of R0721-R0847, IEEE): stage agreement 96.0%, kappa 0.86 (before resolution); 1 record
  changed X -> ?. **Reported agreement = before resolution**: block 1 92.4% / 0.78, block 2 96.0% / 0.86.
- 2026-10-17 — **ACM Digital Library**: blocked by a Cloudflare bot check in the automated browser; not bypassed.
  ACM-published work is covered through OpenAlex (ACM DOIs 10.1145/...) and arXiv; status pending Abdul.
- 2026-10-17 — **Full-text retrieval** (not specified in v1): three automated passes, only open copies, nothing behind a
  login, paywall or bot check. Pass 1 (scripts/lit/fetch_fulltext.py): arXiv, then OpenAlex open-access locations.
  Pass 2 (fetch_fulltext_pass2.py): arXiv title search, Semantic Scholar openAccessPdf; title similarity >= 0.92.
  Pass 3 (fetch_fulltext_pass3.py): Zenodo API, the DOI landing page's citation_pdf_url tag, and open URLs found by
  web search for high-priority records (listed with how they were found in fulltext-manual-urls.csv); a PDF is used
  only if the record's title is on its first page. Records with no copy after all passes are excluded as "no full
  text" (exclusion criterion 3) and listed by name in the PRISMA flow.
- 2026-10-17 — **Full-text exclusion codes**: reported against the protocol criteria. Screening shorthand X1 = inclusion
  criterion 1 not met (IC1), X3 = no empirical evaluation (IC2); duplicates and missing full texts = E3. Counts come
  from scripts/lit/prisma.py.
- 2026-10-17 — **Duplicate versions** (E3, keep the latest): R0097 (ChaosEater arXiv) -> R0170 (ASE 2025);
  R0295 -> R0470 (same authors, extended benchmark). The longer older version may still be read for detail.
- 2026-10-17 — **ACM Digital Library run** (v1.2 string, Title OR Abstract per group, E-Publication Date 2023-2026):
  done in Abdul's own Chrome via the Claude in Chrome extension after Abdul passed the Cloudflare check and signed in
  himself (the automated browser pane could not pass the check; it was not bypassed). Cookie banner: necessary cookies
  only. 51 hits; DOIs saved to raw/acm-v1.2-20261017-dois.txt, metadata and full abstracts for each DOI from OpenAlex
  (scripts/lit/acm_hits.py -> raw/acm-v1.2-20261017.jsonl). 39 hits matched existing records (OpenAlex already
  covered most of ACM); 12 new records R0848-R0859 screened (2 to full text). Block 3 second screening (2 of 12):
  stage agreement 2/2.
- 2026-10-17 — **Full texts fetched in the browser**: ACM (18) and MDPI (1) open-access PDFs that refuse scripted
  downloads were fetched inside Abdul's Chrome session with his permission and imported with
  scripts/lit/import_browser_pdfs.py (same first-page title check, sha256 in the manifest). Not obtainable: R0001
  (SciTePress download behind a CAPTCHA, not attempted), R0182 (VU repository 403), R0287 (IEEE, paywalled),
  R0665 (MDPI, browser blocked a second download; Abdul can download it by hand).
- 2026-10-17 — **Full texts read in the browser without saving**: when Chrome blocked further downloads, open-access
  PDFs (IEEE Access, SSRN, theses, IOS Press, AIS, Zenodo) were parsed in memory in Abdul's Chrome session with pdf.js
  (scripts/lit/browser_reader.js) or read from the publisher's HTML full text; no copy is stored, so the manifest
  has no sha256 for these. A local receiver for PDFs was considered and refused by the permission system; not used.
- 2026-10-17 — **Not accessible after all routes**: 57 records, reasons per record in fulltext-manifest.csv
  (scripts/lit/mark_unavailable.py): 44 IEEE Xplore paywalled ("locked"), 4 Springer chapters, 1 Elsevier, 1
  ResearchGate, 1 IEEE DataPort, 1 CAPTCHA (SciTePress), 1 repository 403, 3 open copies whose download the browser
  blocked (R0015, R0406, R0665; Abdul can download them), 1 no copy found (R0069). Excluded as "no full text"
  (criterion 3) unless Abdul obtains copies (e.g. institutional IEEE access).
- 2026-10-18 — **Snowballing** (step 3), one round on the included studies: OpenAlex references + citing works
  (scripts/lit/snowball.py) and Semantic Scholar references + citations (snowball_s2.py), kept if published in the
  search period and matching the three keyword groups of the search string; four leads found by hand
  (snowball-manual-leads.csv). 160 kept hits -> 6 new records (R0860-R0865); all other hits were already records.
  Limitation: OpenAlex lists few references for arXiv papers, and 13 seeds (theses, SSRN/Zenodo and recent venue
  papers: R0474 R0249 R0262 R0802 R0164 R0383 R0098 R0122 R0403 R0370 R0106 R0132 R0228) are not in Semantic Scholar,
  so for those only OpenAlex links were followed. Snowball block second screening (1 record): agreement 1/1.
- 2026-10-23 — **Requested full texts**: Abdul obtained 53 of the 58 missing PDFs through his professor
  (full_doc.zip). Unpacked with scripts/lit/unpack_requested.py (path checks, PDFs only) into a scratch folder and
  imported with import_browser_pdfs.py (first-page title check passed for all 53; sha256 in the manifest; PDFs stay
  out of git). Still not obtained: R0055, R0219, R0475 (Springer chapters), R0149 (IEEE DataPort), R0862 (TerraFault).
  Duplicate versions found among them (E3, latest kept): R0756 KubeTeus -> R0229 KubeTeus+; R0860 -> R0447 (extended
  CCIS 2026 paper; R0860 was first linked to R0188 and corrected).
- 2026-10-23 — **Full-text second screening** (protocol step 2 applied to the full-text stage, which v1 left implicit):
  blind 20% sample (37 records, seed 20261023), independent AI session with criteria + full texts only. Agreement
  before resolution 89.2%, kappa 0.75; 2 disagreements were duplicate versions (first decision kept), 2 resolved in
  favour of the second screener (R0033 -> E1, R0397 -> IC1). Details: ft-rescreen-resolution.md.
