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
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent.parent / "plain-language-guard.py")

# Some failure details quote a stopped sentence verbatim, and a stopped
# sentence can carry an em dash. The Windows console's default codepage
# cannot encode that character, which would otherwise crash the runner
# itself on the first failing case that quotes one -- a harness bug, not a
# guard finding. Reconfigure defensively; this is a no-op everywhere the
# default encoding already handles it.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


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


def filler_sentence(word_count: int, variant: str = "") -> str:
    """Build one sentence of exactly ``word_count`` words.

    ``variant`` makes the sentence TEXTUALLY DISTINCT while leaving the word
    count and the fault profile identical. It matters: the guard drops
    duplicate findings by their text, so several identical sentences collapse
    into ONE finding and score once. A case meaning to exercise several
    findings must therefore vary the token, or it silently tests one.

    Every word is the same harmless token, so the sentence trips no rule
    except the sentence-length one: it holds no digits (no bare-number
    finding), no listed short form, and no dash. That makes the sentence
    fault score exactly the sentence-length weight for its overrun, with
    nothing else added on top -- required for the scoring tests below,
    which pin an exact fault score.
    """
    return " ".join(["filler" + variant] * word_count) + "."


# The command-line flag that selects the carry-forward (drain-and-print) mode
# on a second registration of the same hook file, on the user-prompt event.
# This flag name is this test suite's own choice, matching the contract's
# "selected by a command-line flag" language -- the implementer registers
# plain-language-guard.py a second time in settings.json with this same
# flag on the command line.
CARRY_FORWARD_FLAG = "--carry-forward"

# The new wording the guard must use once a turn is stopped. Pinned here
# because the contract states it in full: "a short correction ... and it
# says plainly not to repeat the message."
NEW_STOP_PHRASES = ["short correction", "not repeat the message"]

# The old wording the guard must no longer use. This is the literal phrase
# from today's BLOCK_HEADER, quoted in the contract's own Uncertain
# Assumptions section as the sentence that causes the duplicate.
OLD_STOP_PHRASE = "say it again"


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------

@dataclass
class Case:
    name: str
    entries: list
    expect_exit: int
    expect_stderr_contains: str = ""
    expect_stderr_contains_all: list = field(default_factory=list)
    expect_stderr_not_contains: str = ""
    expect_stderr_empty: bool = False
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
        name="a single over-long sentence is recorded, not blocked",
        entries=[user_says("go"), claude_says(
            "The reason the build fell over is that the generated client was "
            "written before the change landed and nothing on the machine checks "
            "whether the two halves agree with each other any more, which means "
            "the failure only shows up much later on.")],
        expect_exit=0,
        expect_stderr_empty=True,
    ),
    Case(
        name="stacked long dashes are blocked",
        entries=[user_says("go"), claude_says(
            "The guard — which runs at the end — reads the message "
            "— and then decides.")],
        expect_exit=2,
        expect_stderr_contains="long dashes",
    ),

    # ---- fault score: noted vs stopped ------------------------------------
    # The reported capture: one sentence four words over the limit (weighs
    # one) and one sentence ten words over (weighs two). Score three, below
    # the stop_threshold of four, so this must end at zero and print
    # nothing -- the exact defect this contract closes.
    Case(
        name="the reported capture -- two long sentences together stay noted",
        entries=[user_says("go"), claude_says(
            filler_sentence(39) + " " + filler_sentence(45))],
        expect_exit=0,
        expect_stderr_empty=True,
    ),
    # Three long sentences: weights one, two and two -- a score of five,
    # at or above the threshold of four. Must still stop. This is the
    # "must not regress" half of the same Open Question.
    Case(
        name="several long sentences together still cross the stop threshold",
        entries=[user_says("go"), claude_says(
            filler_sentence(39, "a") + " " + filler_sentence(45, "b") + " "
            + filler_sentence(45, "c"))],
        expect_exit=2,
        expect_stderr_contains_all=list(NEW_STOP_PHRASES),
        expect_stderr_not_contains=OLD_STOP_PHRASE,
    ),
    # A single short form alone weighs four, which equals the threshold on
    # its own -- one clear fault is still worth stopping the turn.
    Case(
        name="a single unwritten-out short form alone reaches the stop threshold",
        entries=[user_says("go"), claude_says("I followed TDD on this rewrite.")],
        expect_exit=2,
        expect_stderr_contains_all=list(NEW_STOP_PHRASES),
        expect_stderr_not_contains=OLD_STOP_PHRASE,
    ),
    # A single bare number alone weighs four, same reasoning.
    Case(
        name="a single bare number alone reaches the stop threshold",
        entries=[user_says("go"), claude_says("The suite came back 12/12 clean.")],
        expect_exit=2,
        expect_stderr_contains_all=list(NEW_STOP_PHRASES),
        expect_stderr_not_contains=OLD_STOP_PHRASE,
    ),
    # A single stacked-dash sentence alone weighs four, same reasoning.
    Case(
        name="a single stacked-dash sentence alone reaches the stop threshold",
        entries=[user_says("go"), claude_says(
            "The guard — which runs at the end — reads the message "
            "— and then decides.")],
        expect_exit=2,
        expect_stderr_contains_all=list(NEW_STOP_PHRASES),
        expect_stderr_not_contains=OLD_STOP_PHRASE,
    ),
    # The wording fix itself, named plainly so its purpose cannot be missed:
    # the stop no longer asks for the whole message a second time.
    Case(
        name="the stop wording asks for a short correction, not the whole message again",
        entries=[user_says("go"), claude_says("I finished step 3 and moved on.")],
        expect_exit=2,
        expect_stderr_contains_all=list(NEW_STOP_PHRASES),
        expect_stderr_not_contains=OLD_STOP_PHRASE,
    ),
    # Fifteen small findings, one over the display cap of twelve. The score
    # (fifteen) reaches the threshold on its own, so this also proves the
    # display cap never feeds back into the score: capping only the SHOWN
    # list to twelve, while still scoring and stopping on all fifteen.
    Case(
        name="many small findings are capped in what is displayed, never in what is scored",
        entries=[user_says("go"), claude_says(
            " ".join(filler_sentence(36, chr(97 + i)) for i in range(15)))],
        expect_exit=2,
        expect_stderr_contains_all=list(NEW_STOP_PHRASES)
        + ["and 3 more of the same kind"],
        expect_stderr_not_contains=OLD_STOP_PHRASE,
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


def invoke_with_stdout(hook_env: dict, payload: dict, argv_extra: list) -> tuple:
    """Same contract as :func:`invoke`, but also returns stdout and accepts
    extra command-line arguments -- needed for the carry-forward mode,
    which is selected by :data:`CARRY_FORWARD_FLAG` on the command line
    rather than by anything in the JSON payload."""
    proc = subprocess.Popen(
        ["py", "-3", HOOK] + list(argv_extra),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=hook_env,
    )
    out, err = proc.communicate(json.dumps(payload).encode("utf-8"))
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


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
    for fragment in case.expect_stderr_contains_all:
        if fragment not in err:
            return False, ("stderr did not contain %r\n  full stderr: %s"
                           % (fragment, err[:400]))
    if case.expect_stderr_not_contains and case.expect_stderr_not_contains in err:
        return False, ("stderr still contains the retired wording %r\n"
                       "  full stderr: %s"
                       % (case.expect_stderr_not_contains, err[:400]))
    if case.expect_stderr_empty and err.strip():
        return False, ("expected nothing reprinted on stderr, got: %s"
                       % err[:400])
    return True, "ok"


# --------------------------------------------------------------------------
# carry-forward cases -- the notice written on one Stop run must be
# delivered, and only delivered, on the very next user-prompt run of the
# same session, through the documented context-injection envelope.
# --------------------------------------------------------------------------

@dataclass
class CarryForwardCase:
    name: str
    entries: list
    stop_call_count: int = 1
    stop_payload_extra: dict = field(default_factory=dict)
    expect_stdout_empty: bool = True
    expect_context_contains: list = field(default_factory=list)
    env: dict = field(default_factory=dict)


CARRIED_PHRASES = ["previous message", "nothing was stopped",
                   "must not be corrected or repeated"]


CARRY_FORWARD_CASES: list[CarryForwardCase] = [
    CarryForwardCase(
        name="the reported capture is delivered next turn, not reprinted",
        entries=[user_says("go"), claude_says(
            filler_sentence(39) + " " + filler_sentence(45))],
        stop_call_count=1,
        expect_stdout_empty=False,
        expect_context_contains=list(CARRIED_PHRASES),
    ),
    CarryForwardCase(
        name="a message already on the per-session refused list still surfaces once",
        entries=[user_says("go"), claude_says("I finished step 3 and moved on.")],
        stop_call_count=2,
        expect_stdout_empty=False,
        expect_context_contains=list(CARRIED_PHRASES),
    ),
    CarryForwardCase(
        name="the repeat-suppression flag leaves nothing to deliver next turn",
        entries=[user_says("go"), claude_says("I finished step 3 and moved on.")],
        stop_call_count=1,
        stop_payload_extra={"stop_hook_active": True},
        expect_stdout_empty=True,
    ),
    # NOTE on the off switch: this suite does not add a dedicated
    # carry-forward/off-switch case. is_disabled() is (and after this
    # change must remain) the very first check in run(), before either
    # mode reads anything -- so a disabled run already prints nothing and
    # exits 0 today, for exactly the same reason it must tomorrow. No
    # black-box payload can make that combination fail today, so a case
    # asserting it would pass now and stay passing after the fix without
    # ever having pinned anything. The existing "the off switch disables
    # the guard" case above already proves the switch reaches the Stop
    # path; CLAUDE.md's own line -- "Escape hatch: CLAUDE_PLAIN_LANGUAGE_
    # GUARD=off -- disable for a session" -- makes plain the switch is
    # session-wide, not mode-specific, so the Stop-path proof already
    # covers the invariant this case would have restated.
]


def run_carry_forward_case(case: CarryForwardCase, index: int, workspace: Path) -> tuple:
    transcript = workspace / ("cf-transcript-%02d.jsonl" % index)
    with transcript.open("w", encoding="utf-8") as handle:
        for entry in case.entries:
            handle.write(json.dumps(entry) + "\n")

    session_id = "cf-session-%02d" % index
    stop_payload = {
        "session_id": session_id,
        "transcript_path": str(transcript),
        "stop_hook_active": False,
    }
    stop_payload.update(case.stop_payload_extra)

    hook_env = dict(os.environ)
    hook_env["CLAUDE_PROJECT_DIR"] = str(workspace)
    hook_env.pop("CLAUDE_PLAIN_LANGUAGE_GUARD", None)
    hook_env.update(case.env)

    # Prime the session: one or more Stop-event runs, exactly as a real
    # turn would produce, before the next user prompt arrives.
    for _ in range(case.stop_call_count):
        invoke(hook_env, stop_payload)

    # The next user prompt. Same session, same transcript -- a real
    # UserPromptSubmit payload carries the transcript path too (see
    # plan-question-advisor.py's own documented contract).
    carry_payload = {
        "session_id": session_id,
        "prompt": "continue",
        "transcript_path": str(transcript),
    }
    code, out, err = invoke_with_stdout(
        hook_env, carry_payload, [CARRY_FORWARD_FLAG])

    # The contract states this mode never ends non-zero, whatever happens.
    if code != 0:
        return False, ("carry-forward mode must always exit 0, got %d\n"
                       "  stdout: %s\n  stderr: %s" % (code, out[:400], err[:400]))

    if case.expect_stdout_empty:
        if out.strip():
            return False, ("expected nothing printed with no notice waiting, "
                           "got stdout: %s" % out[:400])
        return True, "ok"

    if not out.strip():
        return False, "expected the context-injection envelope on stdout, got nothing"
    try:
        parsed = json.loads(out)
    except Exception as exc:
        return False, ("stdout did not parse as JSON: %r\n  stdout: %s"
                       % (exc, out[:400]))
    hook_output = parsed.get("hookSpecificOutput") if isinstance(parsed, dict) else None
    if not isinstance(hook_output, dict):
        return False, "JSON on stdout has no 'hookSpecificOutput' object"
    if hook_output.get("hookEventName") != "UserPromptSubmit":
        return False, ("hookEventName should be 'UserPromptSubmit', got %r"
                       % hook_output.get("hookEventName"))
    context = hook_output.get("additionalContext")
    if not isinstance(context, str) or not context.strip():
        return False, "additionalContext is missing or empty"
    for phrase in case.expect_context_contains:
        if phrase not in context:
            return False, ("additionalContext did not contain %r\n"
                           "  full text: %s" % (phrase, context[:400]))
    return True, "ok"


def run_rules_file_absent_control():
    """The guard must still block when its rules file cannot be found.

    The Guard rules file mechanism requires this control: moving settings out of
    code is only safe if the code still guards when the settings vanish. A guard
    that falls silent when its configuration disappears is worse than one that
    never moved.

    The live rules file is NEVER renamed. Renaming it would leave the real guard
    unconfigured if this run were interrupted. Instead the hook and the path
    helper are copied into a throwaway directory with no rules file beside them,
    and the project root is pointed at a throwaway workspace, so no rules file is
    reachable by either lookup the path helper tries.

    This is also the ONLY case that exercises the built-in fallback table. Every
    other case reads the real rules file, because the path helper ranks the hook's
    own directory first.
    """
    name = "the guard still blocks when no rules file can be found"
    source = Path(__file__).resolve().parent.parent
    tmp = Path(tempfile.mkdtemp(prefix="plain-language-guard-fallback-"))
    try:
        hooks = tmp / "proj" / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        for wanted in ("plain-language-guard.py", "_project_paths.py", "_error_log.py"):
            if (source / wanted).is_file():
                shutil.copy(source / wanted, hooks)
        if (hooks / "plain-language-guard.rules.json").exists():
            return name, False, "the throwaway copy must NOT carry a rules file"

        transcript = tmp / "transcript.jsonl"
        with transcript.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(user_says("go")) + "\n")
            handle.write(json.dumps(claude_says(
                "We used TDD throughout and it worked.")) + "\n")

        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = str(tmp / "proj")
        env.pop("CLAUDE_PLAIN_LANGUAGE_GUARD", None)
        result = subprocess.run(
            [sys.executable, str(hooks / "plain-language-guard.py")],
            input=json.dumps({"transcript_path": str(transcript),
                              "session_id": "rules-absent-control"}),
            capture_output=True, text=True, env=env)

        if result.returncode != 2:
            return name, False, (
                "expected the guard to still stop the turn with no rules file, "
                "got exit %d. A guard that falls open when its settings vanish is "
                "the failure this control exists to catch." % result.returncode)
        if "Short form" not in (result.stderr or ""):
            return name, False, (
                "expected the built-in fallback short-form list to still be "
                "applied; stderr was %r" % (result.stderr or "")[:200])
        return name, True, ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
        for index, case in enumerate(CARRY_FORWARD_CASES):
            ok, detail = run_carry_forward_case(case, index, workspace)
            if ok:
                passed += 1
                print("  PASS  %s" % case.name)
            else:
                failed += 1
                print("  FAIL  %s" % case.name)
                print("        %s" % detail)
    name, ok, detail = run_rules_file_absent_control()
    if ok:
        passed += 1
        print("  PASS  %s" % name)
    else:
        failed += 1
        print("  FAIL  %s" % name)
        print("        %s" % detail)

    total = len(CASES) + len(CARRY_FORWARD_CASES) + 1
    print()
    print("results: %d passed, %d failed (of %d)" % (passed, failed, total))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
