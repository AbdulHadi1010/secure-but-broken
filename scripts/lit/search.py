"""Structured literature search (docs/lit-review/search-protocol.md v1): run the protocol's search string against
open APIs and store every hit, with the exact query, date and count.

  uv run python scripts/lit/search.py arxiv
  uv run python scripts/lit/search.py openalex
Output: docs/lit-review/raw/<source>-<date>.jsonl (one hit per line) and an appended entry in docs/lit-review/search-log.md.

The protocol string uses truncation (repair*, LLM*); neither API supports wildcards, so each truncated term is
expanded into its word forms below (the expansion is part of the logged query).
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "docs" / "lit-review" / "raw"
LOG = ROOT / "docs" / "lit-review" / "search-log.md"
UA = "secure-but-broken-litsearch/1.0 (mailto:<CONTACT_EMAIL>)"
# Python on Windows here has no usable CA store; use the Mozilla bundle shipped with botocore (already a dependency)
import botocore  # noqa: E402

CTX = ssl.create_default_context(cafile=os.path.join(os.path.dirname(botocore.__file__), "cacert.pem"))

LLM = ["large language model", "large language models", "LLM", "LLMs", "GPT", "code model", "code models",
       "generative AI"]
IAC = ["infrastructure as code", "infrastructure-as-code", "IaC", "Kubernetes", "Terraform", "Helm",
       "cloud configuration", "misconfiguration", "misconfigurations"]
# v1.1 (2026-10-17, seed check missed three Ansible papers): terms ADDED to both groups; the v1 run is kept as is.
VERSION = "v1"
if os.environ.get("SEARCH_VERSION") in ("v1.1", "v1.2"):
    VERSION = os.environ["SEARCH_VERSION"]
    LLM = LLM + ["language model", "language models", "foundation model", "foundation models"]
    IAC = IAC + ["Ansible", "CloudFormation", "Pulumi", "Puppet", "Chef", "Dockerfile", "Dockerfiles", "Docker Compose"]
TASK = ["repair", "repairs", "repairing", "fix", "fixes", "fixing", "remediate", "remediation", "remediating",
        "harden", "hardening", "generate", "generation", "generating", "generated"]
if VERSION == "v1.2":  # seed check: C2 (self-healing of IaC projects) uses none of the v1 task words
    TASK = TASK + ["self-healing", "self healing"]
START, END = "2023-01-01", "2026-10-31"


def _get(url: str, timeout: int = 60) -> bytes:
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                return r.read()
        except Exception:  # noqa: BLE001 - retried, then raised
            if attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def _task_match(text: str) -> bool:
    """The protocol's third group (repair* OR fix* OR remediat* OR harden* OR generat*) as word prefixes."""
    import re

    words = r"repair|fix|remediat|harden|generat" + (r"|self[- ]heal" if VERSION == "v1.2" else "")
    return bool(re.search(rf"\b({words})", text, re.IGNORECASE))


def arxiv() -> tuple[str, list[dict]]:
    """The full three-group query times out on the arXiv API, so it is run as one query per IaC term
    (LLM group AND that term AND categories AND dates) and the third group is applied to title+abstract locally.
    Union over the IaC terms = the protocol's (LLM) AND (IaC) AND (task)."""
    one = lambda t: f'all:"{t}"' if " " in t or "-" in t else f"all:{t}"  # noqa: E731
    llm = "(" + " OR ".join(one(t) for t in LLM) + ")"
    tail = (f"(cat:cs.SE OR cat:cs.CR OR cat:cs.AI OR cat:cs.DC OR cat:cs.LG OR cat:cs.CL) AND "
            f"submittedDate:[{START.replace('-', '')}0000 TO {END.replace('-', '')}2359]")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    seen, hits, queries = set(), [], []
    for iac in IAC:
        q = f"{llm} AND {one(iac)} AND {tail}"
        queries.append(q)
        start = 0
        while True:
            url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
                {"search_query": q, "start": start, "max_results": 200, "sortBy": "submittedDate", "sortOrder": "ascending"})
            root = ET.fromstring(_get(url, timeout=180))
            entries = root.findall("a:entry", ns)
            for e in entries:
                h = {"source": "arxiv", "id": e.findtext("a:id", namespaces=ns).rsplit("/abs/", 1)[-1],
                     "title": " ".join(e.findtext("a:title", namespaces=ns).split()),
                     "abstract": " ".join((e.findtext("a:summary", namespaces=ns) or "").split()),
                     "date": e.findtext("a:published", namespaces=ns)[:10],
                     "authors": [a.findtext("a:name", namespaces=ns) for a in e.findall("a:author", ns)],
                     "doi": e.findtext("{http://arxiv.org/schemas/atom}doi")}
                if h["id"] not in seen and _task_match(h["title"] + " " + h["abstract"]):
                    seen.add(h["id"])
                    hits.append(h)
            if len(entries) < 200:
                break
            start += 200
            time.sleep(3)  # arXiv API etiquette
        time.sleep(3)
    return "\n".join(queries) + "\n+ local filter on title+abstract: \\b(repair|fix|remediat|harden|generat)", hits


def openalex() -> tuple[str, list[dict]]:
    group = lambda terms: "(" + " OR ".join(f'"{t}"' for t in terms) + ")"  # noqa: E731
    q = f"{group(LLM)} AND {group(IAC)} AND {group(TASK)}"
    # language is checked at screening: OpenAlex's language field is often empty (523 hits without, 251 with language:en)
    flt = f"title_and_abstract.search:{q},from_publication_date:{START},to_publication_date:{END}"
    hits, page = [], 1
    while True:  # numbered paging (cursor paging needs an API key since 2026; page paging covers up to 10,000 hits)
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"filter": flt, "per-page": 200, "page": page, "sort": "publication_date:asc", "mailto": "<CONTACT_EMAIL>"})
        d = json.loads(_get(url))
        page += 1
        for w in d["results"]:
            inv = w.get("abstract_inverted_index") or {}
            words = sorted(((i, wd) for wd, idx in inv.items() for i in idx))
            loc = w.get("primary_location") or {}
            hits.append({"source": "openalex", "id": w["id"].rsplit("/", 1)[-1], "title": w.get("title") or "",
                         "abstract": " ".join(wd for _, wd in words), "date": w.get("publication_date"),
                         "authors": [a["author"]["display_name"] for a in w.get("authorships", [])],
                         "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
                         "venue": ((loc.get("source") or {}).get("display_name")), "type": w.get("type")})
        if len(d["results"]) < 200:
            break
    if len(hits) != d["meta"]["count"]:
        raise RuntimeError(f"OpenAlex paging incomplete: {len(hits)} of {d['meta']['count']}")
    return flt, hits


def main(source: str) -> None:
    when = datetime.now(timezone.utc)
    query, hits = {"arxiv": arxiv, "openalex": openalex}[source]()
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"{source}-{VERSION}-{when:%Y%m%d}.jsonl"
    out.write_text("".join(json.dumps(h, ensure_ascii=False) + "\n" for h in hits), encoding="utf-8", newline="\n")
    if not LOG.exists():
        LOG.write_text("# Literature search log (append-only)\n", encoding="utf-8", newline="\n")
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n## {source} — {when:%Y-%m-%d %H:%M} UTC\n- Hits: {len(hits)}\n- Raw: `{out.relative_to(ROOT).as_posix()}`\n"
                f"- Exact query:\n```\n{query}\n```\n")
    print(source, len(hits), out)


if __name__ == "__main__":
    main(sys.argv[1])
