"""D-031: the prompt texts are frozen. If this test fails, a prompt changed: that is a protocol deviation that must be
logged in docs/decisions.md and approved by Abdul before the hashes below are updated."""
import hashlib

from harness.moderator import feedback
from harness.repair import prompt

EX = [{"tool": "<tool>", "rule": "<rule id>", "title": "<rule title>", "kind": "<Kind>", "name": "<name>"}]
FROZEN = {
    "SYSTEM": "c3d3f9fe6a00f61b3cc787f85043862f72c39146e8c3aa7a1968d460e81d34ae",
    "MODERATOR": "0ac76815560b8dde20da49ac9bbfbabad7ad5eae203de371e8013246c17cbfd5",
    "W0": "7ca95175f86a506a6d18d8ad6e3cc037563f438bd6a8961602301205d9ecad8b",
    "W1": "ee26c8d38a02722eb78c5dee4622614c8b072d8a858fe6a900dac0a67d06fba2",
    "CONSTRAINTS": "b536b11d7432091be27824df798ecc3ba6e6a35a8f82e954ce075d6ccb1a3369",
}


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def test_prompts_unchanged():
    now = {
        "SYSTEM": h(prompt.SYSTEM),
        "MODERATOR": h(feedback.MODERATOR_SYSTEM),
        "W0": h(prompt.build_user_prompt(EX, "<m>", keep_working=False)),
        "W1": h(prompt.build_user_prompt(EX, "<m>", keep_working=True)),
        "CONSTRAINTS": h(feedback.CONSTRAINTS),
    }
    assert now == FROZEN
    assert prompt.PROMPT_VERSION == "v1-frozen-2026-10-06"
