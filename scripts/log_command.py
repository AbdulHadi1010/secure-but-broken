"""Claude Code hook: append every shell command to docs/command-log/YYYY-MM-DD.jsonl (audit trail).

Wired in .claude/settings.json for PostToolUse and PostToolUseFailure on Bash|PowerShell.
Reads the hook payload (JSON) on stdin, writes one JSON line, never blocks or fails the session.
Standard library only, so it runs without the project environment.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "docs" / "command-log"


def _exit_code(resp) -> int | None:
    if isinstance(resp, dict):
        for k in ("exitCode", "exit_code", "returnCode", "code"):
            if isinstance(resp.get(k), int):
                return resp[k]
        if resp.get("interrupted"):
            return None
    return None


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {"unparsed": True}
    tool_input = payload.get("tool_input") or {}
    resp = payload.get("tool_response")
    now = datetime.now(timezone.utc)
    record = {
        "ts_utc": now.isoformat(timespec="seconds"),
        "event": payload.get("hook_event_name"),
        "tool": payload.get("tool_name"),
        "cwd": payload.get("cwd"),
        "command": tool_input.get("command"),
        "description": tool_input.get("description"),
        "background": bool(tool_input.get("run_in_background")),
        "exit_code": _exit_code(resp),
        "succeeded": payload.get("hook_event_name") == "PostToolUse",  # failures arrive as PostToolUseFailure
        "error": (payload.get("error") or "")[:500] or None,
        "session_id": payload.get("session_id"),
    }
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / f"{now:%Y-%m-%d}.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - logging must never break the session
        pass
