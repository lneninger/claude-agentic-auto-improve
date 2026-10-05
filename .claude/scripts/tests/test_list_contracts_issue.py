#!/usr/bin/env python3
"""
test_list_contracts_issue.py -- /list-contracts shows each follow-up stub's
GitHub tracking issue.

A follow-up stub under .claude/concepts/followups/ is only visible through
/list-contracts, but the user works in GitHub issues. Each stub therefore
carries an `**Issue:**` field (`pending`, `#<n>` or `unavailable`), and the
listing must show it, flagging a stub with no real issue number.

House style: plain runnable script, NO pytest. check(name, cond, detail)
accumulator, PASS/FAIL summary, non-zero exit on any failure.

    py -3 .claude/scripts/tests/test_list_contracts_issue.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "list_contracts.py"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"  -- {detail}"))
    if not cond:
        failures.append(name)


def load():
    # list_contracts.py imports its sibling _claude_paths, so put the scripts folder on the path.
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("list_contracts_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUB = """# Follow-up — {title}

**Parent contract:** `.claude/concepts/parent.md`
**Date:** 2026-10-02
**Status:** stub
**Estimated scope:** small
{issue_line}
## What was noticed

Something.
"""


def write_stub(folder: Path, name: str, issue_line: str) -> Path:
    path = folder / name
    path.write_text(STUB.format(title=name, issue_line=issue_line), encoding="utf-8")
    return path


def listing(module, parsed: dict) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        module.print_human([parsed])
    return buffer.getvalue()


def main() -> int:
    module = load()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / ".claude" / "concepts" / "followups"
        folder.mkdir(parents=True)

        linked = module.parse_contract(write_stub(folder, "a.followup.md", "**Issue:** #293\n"))
        pending = module.parse_contract(write_stub(folder, "b.followup.md", "**Issue:** pending\n"))
        missing = module.parse_contract(write_stub(folder, "c.followup.md", ""))
        unavailable = module.parse_contract(write_stub(folder, "d.followup.md", "**Issue:** unavailable\n"))

        check("parse reads a linked issue number", linked.get("issue") == "#293", repr(linked.get("issue")))
        check("parse reads pending", pending.get("issue") == "pending", repr(pending.get("issue")))
        check("parse reads unavailable", unavailable.get("issue") == "unavailable", repr(unavailable.get("issue")))
        check("parse reads no Issue field as None", missing.get("issue") is None, repr(missing.get("issue")))

        out_linked = listing(module, linked)
        out_pending = listing(module, pending)
        out_missing = listing(module, missing)
        out_unavailable = listing(module, unavailable)

        check("a linked stub shows its issue number", "#293" in out_linked, out_linked)
        check("a linked stub is not flagged", "NO ISSUE" not in out_linked, out_linked)
        check("a pending stub is flagged", "NO ISSUE" in out_pending, out_pending)
        check("a stub with no Issue field is flagged", "NO ISSUE" in out_missing, out_missing)
        check("an unavailable stub is flagged", "NO ISSUE" in out_unavailable, out_unavailable)

    print()
    print(f"{len(failures)} failure(s)" if failures else "ALL PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
