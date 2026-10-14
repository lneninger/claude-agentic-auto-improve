#!/usr/bin/env python3
"""
test_codegraph_first_guard.py -- issue #612: the CodeGraph-first gate must not block a read of a
non-source file that lives outside the project (for example a background command's `.output`
file in the system temp folder).

House style: plain runnable script, NO pytest. check(name, cond, detail) accumulator,
PASS/FAIL summary, non-zero exit on any failure.

    py -3 .claude/hooks/tests/test_codegraph_first_guard.py

WHAT THIS PINS DOWN
  #612-A  a path outside the project whose extension is not a source extension is allowed
  #612-B  the `.output` extension is allowed
  #612-C  the gate can still fire (positive controls, they pass before the change by design):
          a source file inside the project, a source file inside a sibling worktree, an unknown
          extension inside the project, and an unknown extension when the project root is unknown
  #612-D  a source-code extension outside the project stays gated (another repository's code is
          still investigated through CodeGraph's projectPath)
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# The hook is an ADD-ON file: it is found, and installed into a fixture project with its helpers, by the
# shared add-on fixture (beside this hooks folder first, else the plugin's add-on folder). A missing add-on
# FAILS this suite; it never skips.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _addon_fixture as af  # noqa: E402

ADD_ON = "codegraph"
HOOK_FILE = "codegraph-first-guard.py"

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASSED.append(name)
        print(f"PASS  {name}")
    else:
        FAILED.append(name)
        print(f"FAIL  {name}" + (f"\n        -> {detail}" if detail else ""))


def load_hook():
    hook = {p.name: p for p in af.install(ADD_ON)}[HOOK_FILE]
    spec = importlib.util.spec_from_file_location("codegraph_first_guard_under_test", hook)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # The sentinel lives under the process's cwd; pin it absent so the tests do not depend on it.
    mod.sentinel_exists = lambda: False
    return mod


def run() -> None:
    try:
        guard = load_hook()
    except af.AddonFixtureError as exc:
        check("the codegraph add-on is available to this suite (hook, manifest and helpers exist)", False, str(exc))
        return
    project = Path(tempfile.mkdtemp(prefix="cgguard-project-"))
    outside = Path(tempfile.mkdtemp(prefix="cgguard-outside-"))
    saved = os.environ.get("CLAUDE_PROJECT_DIR")
    try:
        os.environ["CLAUDE_PROJECT_DIR"] = str(project)
        out_file = str(outside / "claude" / "tasks" / "abc123.output")
        out_text = str(outside / "notes" / "result.dat")

        check("#612-A: an extensionless-class file outside the project is allowed",
              guard.classify_path(out_text) == "allowed", repr(guard.classify_path(out_text)))
        check("#612-B: a `.output` file outside the project is allowed",
              guard.classify_path(out_file) == "allowed", repr(guard.classify_path(out_file)))
        decision, why = guard.decide("Read", {"file_path": out_file})
        check("#612-A: a Read of a background `.output` file is allowed with no CodeGraph call this turn",
              decision == "allow", f"{decision}: {why}")

        # Positive controls: the gate must still be able to fire.
        inside_src = str(project / "src" / "Thing.cs")
        check("#612-C control: a source file inside the project is still gated",
              guard.classify_path(inside_src) == "source", repr(guard.classify_path(inside_src)))
        decision, why = guard.decide("Read", {"file_path": inside_src})
        check("#612-C control: a Read of a source file inside the project is blocked with no CodeGraph call",
              decision == "block", f"{decision}: {why}")
        sibling_src = str(project / ".claude" / "worktrees" / "w2" / "src" / "Thing.cs")
        check("#612-C control: a source file inside a sibling worktree is still gated",
              guard.classify_path(sibling_src) == "source", repr(guard.classify_path(sibling_src)))
        inside_unknown = str(project / "data" / "result.dat")
        check("#612-C control: an unknown extension inside the project stays gated (unknown)",
              guard.classify_path(inside_unknown) == "unknown", repr(guard.classify_path(inside_unknown)))
        sibling_unknown = str(project / ".claude" / "worktrees" / "w2" / "data" / "result.dat")
        check("#612-C control: an unknown extension inside a sibling worktree stays gated (unknown)",
              guard.classify_path(sibling_unknown) == "unknown", repr(guard.classify_path(sibling_unknown)))

        # A session started inside a worktree: the project dir is that worktree, a sibling worktree
        # is still inside the same main checkout and stays gated.
        wt = project / ".claude" / "worktrees" / "w1"
        wt.mkdir(parents=True)
        os.environ["CLAUDE_PROJECT_DIR"] = str(wt)
        check("#612-C control: with the project dir set to a worktree, a sibling worktree's unknown file stays gated",
              guard.classify_path(sibling_unknown) == "unknown", repr(guard.classify_path(sibling_unknown)))
        check("#612-A: with the project dir set to a worktree, a file outside the whole checkout is allowed",
              guard.classify_path(out_file) == "allowed", repr(guard.classify_path(out_file)))

        # #612-D a source extension outside the project stays gated.
        os.environ["CLAUDE_PROJECT_DIR"] = str(project)
        outside_src = str(outside / "other-repo" / "Thing.py")
        check("#612-D: a source-code file outside the project stays gated",
              guard.classify_path(outside_src) == "source", repr(guard.classify_path(outside_src)))

        # Fail toward gating when the project root is unknown.
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        check("#612-C control: with no project root known, the outside `.dat` file is NOT widened (unknown)",
              guard.classify_path(out_text) == "unknown", repr(guard.classify_path(out_text)))
    finally:
        if saved is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = saved
        shutil.rmtree(project, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)


if __name__ == "__main__":
    try:
        run()
    except Exception:  # noqa: BLE001 - report any setup error as a failure, never as a crash
        traceback.print_exc()
        FAILED.append("test run raised")
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed, {len(PASSED) + len(FAILED)} total")
    sys.exit(1 if FAILED else 0)
