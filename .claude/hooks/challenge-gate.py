#!/usr/bin/env python3
# .claude/hooks/challenge-gate.py  (DRAFT — not wired, not tested)
#
# Two hook events, one file, chosen by the event name on stdin:
#
#   PostToolUse (matcher: Write|Edit|MultiEdit)  — after a `specs/phase-*.md`
#   edit: if the spec's status line still says PROPOSED and the file carries
#   no `Challenged:` line, print a one-line reminder to run /challenge. It
#   cannot block (PostToolUse never does); exit 2 puts the line in front of
#   the model, exit 0 keeps quiet.
#
#   PreToolUse (matcher: ExitPlanMode) — before a plan is presented: if the
#   plan text carries no `Challenged:` line, answer `permissionDecision:
#   "ask"` with a reason, so the developer sees "not challenged — present
#   anyway?" once and decides. Never `deny`: skipping the challenge is the
#   architect's call.
#
# Fails OPEN — exit 0, no output — on: a malformed event, an event it does not
# handle, a file outside this project, a path that is not a phase spec, a
# plan payload whose shape it does not recognise. It is a reminder, not a
# security control. Wiring is LOCAL-ONLY (gitignored .claude/settings.local.json),
# for the same reason as run-tests.py.
#
# TO VERIFY BEFORE WIRING (Gotchas): the installed build's ExitPlanMode
# tool_input — whether the plan text arrives as `tool_input["plan"]`. The
# hooks reference does not document it; if absent, the PreToolUse half fails
# open by design and only the PostToolUse half is live.
import json
import os
import re
import sys

STATUS_PROPOSED = re.compile(r"^\*\*Status: PROPOSED", re.M)
CHALLENGED = re.compile(r"^Challenged: \d{4}-\d{2}-\d{2}", re.M)
SPEC_NAME = re.compile(r"^phase-[0-9]+[a-z]?-[a-z0-9-]+\.md$")


def _spec_reminder(fp: str, root: str) -> None:
    try:
        text = open(fp, encoding="utf-8").read()
    except OSError:
        sys.exit(0)
    if STATUS_PROPOSED.search(text) and not CHALLENGED.search(text):
        rel = os.path.relpath(fp, root)
        print(
            f"[challenge-gate] {rel} is PROPOSED and not yet challenged — "
            f"run `/challenge {rel}` before asking for approval.",
            file=sys.stderr,
        )
        sys.exit(2)  # PostToolUse: shows the line to the model; blocks nothing
    sys.exit(0)


def _plan_gate(tool_input: dict) -> None:
    plan = tool_input.get("plan")
    if not isinstance(plan, str):  # shape unknown on this build: fail open
        sys.exit(0)
    if CHALLENGED.search(plan):
        sys.exit(0)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (
                "This plan has not been through /challenge (no `Challenged:` "
                "line). Present it anyway, or run /challenge first."
            ),
        }
    }
    print(json.dumps(out))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        sys.exit(0)
    if not isinstance(data, dict):
        sys.exit(0)
    event = data.get("hook_event_name")
    tool = data.get("tool_name")
    ti = data.get("tool_input")
    if not isinstance(ti, dict):
        sys.exit(0)

    root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not root:
        sys.exit(0)

    if event == "PreToolUse" and tool == "ExitPlanMode":
        _plan_gate(ti)

    if event == "PostToolUse" and tool in ("Write", "Edit", "MultiEdit"):
        fp = ti.get("file_path")
        if not isinstance(fp, str):
            sys.exit(0)
        ap = os.path.abspath(fp)
        specs = os.path.join(os.path.abspath(root), "specs") + os.sep
        if not ap.startswith(specs) or not SPEC_NAME.match(os.path.basename(ap)):
            sys.exit(0)
        _spec_reminder(ap, os.path.abspath(root))

    sys.exit(0)


if __name__ == "__main__":
    main()
