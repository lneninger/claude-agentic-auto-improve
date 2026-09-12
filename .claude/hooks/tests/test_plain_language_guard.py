#!/usr/bin/env python3
"""
test_plain_language_guard.py -- end-to-end tests for plain-language-guard.py.

Each case writes a small fake conversation transcript, pipes a Claude-Code-style
Stop payload into the hook as a subprocess, and asserts on the exit code
(0 = let the turn end, 2 = block and ask for a rewrite) and on a fragment of
stderr. That is the same contract Claude Code itself uses, so the tests cover
real behaviour rather than private internals.

Run:
    py -3 .claude/hooks/tests/test_plain_language_guard.py

Exit code:
    0 = all tests passed
    1 = at least one test failed
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent.parent / "plain-language-guard.py")


# --------------------------------------------------------------------------
# transcript builders
# --------------------------------------------------------------------------

def user_says(text: str) -> dict:
    return {
        "type": "user",
        "isSidechain": False,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def claude_says(text: str, sidechain: bool = False) -> dict:
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"role": "assistant",
                    "content": [{"type": "text", "text": text}]},
    }


def tool_result(text: str = "ok") -> dict:
    return {
        "type": "user",
        "isSidechain": False,
        "message": {"role": "user",
                    "content": [{"type": "tool_result", "content": text}]},
    }


def tool_call(name: str = "Bash") -> dict:
    return {
        "type": "assistant",
        "isSidechain": False,
        "message": {"role": "assistant",
                    "content": [{"type": "tool_use", "name": name, "input": {}}]},
    }


CLEAN = "I read the guard file and it looks right. Nothing else to change."


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------

@dataclass
class Case:
    name: str
    entries: list
    expect_exit: int
    expect_stderr_contains: str = ""
    env: dict = field(default_factory=dict)
    payload_extra: dict = field(default_factory=dict)
    run_twice: bool = False


CASES: list[Case] = [
    # ---- clean writing passes ------------------------------------------
    Case(
        name="clean prose is allowed through",
        entries=[user_says("do the thing"), claude_says(CLEAN)],
        expect_exit=0,
    ),
    Case(
        name="turn with no prose at all is allowed through",
        entries=[user_says("do the thing"), tool_call(), tool_result()],
        expect_exit=0,
    ),

    # ---- numbered labels ------------------------------------------------
    Case(
        name="numbered label 'step 3' is blocked",
        entries=[user_says("go"), claude_says("I finished step 3 and moved on.")],
        expect_exit=2,
        expect_stderr_contains="Numbered label",
    ),
    Case(
        name="numbered label at end of sentence is blocked",
        entries=[user_says("go"), claude_says("The work stalled at phase 2.")],
        expect_exit=2,
        expect_stderr_contains="Numbered label",
    ),

    # ---- bare counts ----------------------------------------------------
    Case(
        name="count ratio is blocked",
        entries=[user_says("go"), claude_says("The suite came back 110/110.")],
        expect_exit=2,
        expect_stderr_contains="Bare count ratio",
    ),
    Case(
        name="'3 of 14' is blocked",
        entries=[user_says("go"), claude_says("Only 3 of 14 came back clean.")],
        expect_exit=2,
        expect_stderr_contains="Bare",
    ),
    Case(
        name="naked number in brackets is blocked",
        entries=[user_says("go"), claude_says("See the earlier note (4) for that.")],
        expect_exit=2,
        expect_stderr_contains="Naked number",
    ),
    Case(
        name="a web status code in brackets is allowed",
        entries=[user_says("go"),
                 claude_says("The server answered with a forbidden status (403) instead.")],
        expect_exit=0,
    ),
    Case(
        name="a date is not mistaken for a count ratio",
        entries=[user_says("go"),
                 claude_says("The note was written on 2026/08/29 and still holds.")],
        expect_exit=0,
    ),
    Case(
        name="a version number is not mistaken for a count ratio",
        entries=[user_says("go"), claude_says("The runtime here is dot net 9.0 today.")],
        expect_exit=0,
    ),
    Case(
        name="a file path is not mistaken for a count ratio",
        entries=[user_says("go"),
                 claude_says("The file lives at src/Domain/Auth/User.cs right now.")],
        expect_exit=0,
    ),

    # ---- short forms -----------------------------------------------------
    Case(
        name="unexplained short form is blocked",
        entries=[user_says("go"), claude_says("I followed TDD on this change.")],
        expect_exit=2,
        expect_stderr_contains="never written out",
    ),
    Case(
        name="short form written out in full is allowed",
        entries=[user_says("go"),
                 claude_says("I followed test-driven development (TDD) on this change.")],
        expect_exit=0,
    ),
    Case(
        name="short form only inside inline code is allowed",
        entries=[user_says("go"), claude_says("The switch is named `TDD_MODE` today.")],
        expect_exit=0,
    ),
    Case(
        name="short form only inside a fenced code block is allowed",
        entries=[user_says("go"),
                 claude_says("Here is the snippet.\n\n```\nconst UI = 1;\n```\n\nThat is all.")],
        expect_exit=0,
    ),
    Case(
        name="short form only inside a file path is allowed",
        entries=[user_says("go"),
                 claude_says("It sits under src/Services/API/Handler.cs on disk.")],
        expect_exit=0,
    ),

    # ---- sentence shape --------------------------------------------------
    Case(
        name="over-long sentence is blocked",
        entries=[user_says("go"), claude_says(
            "The reason the build fell over is that the generated client was "
            "written before the change landed and nothing on the machine checks "
            "whether the two halves agree with each other any more, which means "
            "the failure only shows up much later on.")],
        expect_exit=2,
        expect_stderr_contains="over the limit",
    ),
    Case(
        name="stacked long dashes are blocked",
        entries=[user_says("go"), claude_says(
            "The guard — which runs at the end — reads the message "
            "— and then decides.")],
        expect_exit=2,
        expect_stderr_contains="long dashes",
    ),

    # ---- scope -----------------------------------------------------------
    Case(
        name="a violation in an earlier turn is not re-blocked",
        entries=[user_says("first"), claude_says("I finished step 3 back then."),
                 user_says("second"), claude_says(CLEAN)],
        expect_exit=0,
    ),
    Case(
        name="sub-agent prose is ignored",
        entries=[user_says("go"),
                 claude_says("I finished step 3 there.", sidechain=True),
                 claude_says(CLEAN)],
        expect_exit=0,
    ),
    Case(
        name="prose written before a tool result still counts",
        entries=[user_says("go"), claude_says("I finished step 3 already."),
                 tool_call(), tool_result(), claude_says(CLEAN)],
        expect_exit=2,
        expect_stderr_contains="Numbered label",
    ),

    # ---- loop safety and bypass -------------------------------------------
    Case(
        name="stop_hook_active suppresses a second block",
        entries=[user_says("go"), claude_says("I finished step 3 and moved on.")],
        expect_exit=0,
        payload_extra={"stop_hook_active": True},
    ),
    Case(
        name="the same message is never blocked twice",
        entries=[user_says("go"), claude_says("I finished step 3 and moved on.")],
        expect_exit=0,
        run_twice=True,
    ),
    Case(
        name="the off switch disables the guard",
        entries=[user_says("go"), claude_says("I finished step 3 and moved on.")],
        expect_exit=0,
        env={"CLAUDE_PLAIN_LANGUAGE_GUARD": "off"},
    ),
    Case(
        name="a missing transcript path is allowed through",
        entries=[],
        expect_exit=0,
        payload_extra={"transcript_path": ""},
    ),
]


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

def invoke(hook_env: dict, payload: dict) -> tuple:
    proc = subprocess.Popen(
        ["py", "-3", HOOK],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=hook_env,
    )
    out, err = proc.communicate(json.dumps(payload).encode("utf-8"))
    return proc.returncode, err.decode("utf-8", "replace")


def run_case(case: Case, index: int, workspace: Path) -> tuple:
    transcript = workspace / ("transcript-%02d.jsonl" % index)
    with transcript.open("w", encoding="utf-8") as handle:
        for entry in case.entries:
            handle.write(json.dumps(entry) + "\n")

    payload = {
        "session_id": "test-session-%02d" % index,
        "transcript_path": str(transcript),
        "stop_hook_active": False,
    }
    payload.update(case.payload_extra)

    hook_env = dict(os.environ)
    hook_env["CLAUDE_PROJECT_DIR"] = str(workspace)
    hook_env.pop("CLAUDE_PLAIN_LANGUAGE_GUARD", None)
    hook_env.update(case.env)

    code, err = invoke(hook_env, payload)
    if case.run_twice:
        code, err = invoke(hook_env, payload)

    if code != case.expect_exit:
        return False, ("expected exit %d, got %d\n  stderr: %s"
                       % (case.expect_exit, code, err[:400]))
    if case.expect_stderr_contains and case.expect_stderr_contains not in err:
        return False, ("stderr did not contain %r\n  full stderr: %s"
                       % (case.expect_stderr_contains, err[:400]))
    return True, "ok"


def main() -> int:
    passed = 0
    failed = 0
    with tempfile.TemporaryDirectory(prefix="plain-language-guard-") as tmp:
        workspace = Path(tmp)
        (workspace / ".claude").mkdir(parents=True, exist_ok=True)
        for index, case in enumerate(CASES):
            ok, detail = run_case(case, index, workspace)
            if ok:
                passed += 1
                print("  PASS  %s" % case.name)
            else:
                failed += 1
                print("  FAIL  %s" % case.name)
                print("        %s" % detail)
    print()
    print("results: %d passed, %d failed (of %d)" % (passed, failed, len(CASES)))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
