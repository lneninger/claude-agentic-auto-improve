#!/usr/bin/env python3
"""
test_compose_subissue_title.py -- RED-first suite for the sub-issue title
helper `.claude/scripts/compose_subissue_title.py` (contract
.claude/concepts/2026-10-15-subissue-title-parent-ref.md).

House style: plain runnable script, NO pytest (see test_verify_parent_link.py).
check(name, cond, detail) accumulator, PASS/FAIL summary, non-zero exit on any
failure.

    py -3 .claude/scripts/tests/test_compose_subissue_title.py

The helper is driven ONLY through its CLI by subprocess, by absolute path, so
that while it is absent every case fails with a clear check() message rather
than an ImportError. Every case except the "real corpus" one builds its own
fixture conventions file under a temp dir. CLAUDE_PROJECT_DIR is removed from
the child environment unless a case sets it deliberately.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO = SCRIPTS.parent.parent
SUBJECT = SCRIPTS / "compose_subissue_title.py"
SHIPPED_CONVENTIONS = REPO / ".claude" / "work-item-conventions.json"
PARENT_AWARE = REPO / "skills" / "task" / "references" / "parent-aware-mode.md"
FLOW_SKILL = REPO / "skills" / "flow" / "SKILL.md"
DOCTOR = SCRIPTS / "plugin_doctor.py"

FAILURES: list[str] = []
PASSED = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
        print(f"PASS  {name}")
    else:
        FAILURES.append(name)
        print(f"FAIL  {name}" + (f" -- {detail}" if detail else ""))


# ---------------------------------------------------------------- fixtures

PATTERN = r"^\[(FEATURE|BUG|IMPROVEMENT|REFACTOR|PERF|SECURITY|DOCS|CHORE|SPIKE)\] .+"
TAGS = ["FEATURE", "BUG", "IMPROVEMENT", "REFACTOR", "PERF", "SECURITY", "DOCS", "CHORE", "SPIKE"]
FORMAT = "[<EFFORT>] P:#<parent> ST:<subtask> - <Title>"
LEGEND = "P = parent issue, ST = sub-task (its position in the parent's plan)"
EXPECTED = "[PERF] P:#638 ST:16 - Fix Earnings Index (dotnet-backend-architect)"
BARE = "Fix Earnings Index (dotnet-backend-architect)"


def conventions(fmt: str | None = FORMAT, with_sub: bool = True, with_title: bool = True) -> dict:
    data: dict = {"$comment": "fixture"}
    if with_title:
        it: dict = {
            "$comment": "fixture",
            "format": "[<EFFORT>] <Title>",
            "pattern": PATTERN,
            "exactlyOne": True,
            "effortTypes": [{"tag": t, "means": t} for t in TAGS],
        }
        if with_sub:
            it["subIssue"] = {"$comment": "fixture", "legend": LEGEND, "format": fmt}
        data["issueTitle"] = it
    return data


def write_conv(tmp: Path, data: dict, name: str = "conv.json") -> Path:
    p = tmp / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def run(args: list[str], env_extra: dict | None = None, keep_project_dir: bool = False):
    env = dict(os.environ)
    if not keep_project_dir:
        env.pop("CLAUDE_PROJECT_DIR", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SUBJECT), *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


def compose(conv: Path | None, tag="PERF", parent="638", subtask="16", title=BARE, env_extra=None):
    args = ["--type", tag, "--parent", parent, "--subtask", subtask, "--title", title, "--json"]
    if conv is not None:
        args += ["--conventions", str(conv)]
    return run(args, env_extra=env_extra)


def parse(proc):
    try:
        return json.loads(proc.stdout)
    except Exception:
        return None


def expect_composed(name: str, proc, title: str) -> None:
    out = parse(proc)
    check(f"{name}: exit 0", proc.returncode == 0,
          f"expected exit 0, got {proc.returncode}; helper missing or wrong. stderr={proc.stderr.strip()[:120]!r}")
    check(f"{name}: JSON verdict composed", isinstance(out, dict) and out.get("verdict") == "composed",
          f"got {out!r}")
    check(f"{name}: exact title", isinstance(out, dict) and out.get("title") == title,
          f"expected {title!r}, got {out.get('title') if isinstance(out, dict) else out!r}")


def expect_refused(name: str, proc, cause: str, reason_contains: str | None = None) -> None:
    out = parse(proc)
    ok_json = isinstance(out, dict)
    check(f"{name}: exit 2", proc.returncode == 2 and ok_json,
          f"expected exit 2 with JSON, got rc={proc.returncode} stdout={proc.stdout.strip()[:100]!r}; helper missing")
    check(f"{name}: verdict refused", ok_json and out.get("verdict") == "refused", f"got {out!r}")
    check(f"{name}: cause {cause}", ok_json and out.get("cause") == cause,
          f"expected {cause!r}, got {out.get('cause') if ok_json else out!r}")
    check(f"{name}: has reason", ok_json and isinstance(out.get("reason"), str) and out["reason"].strip() != "",
          f"got {out!r}")
    check(f"{name}: no title key (I-2)", ok_json and "title" not in out, f"got {out!r}")
    if reason_contains is not None:
        check(f"{name}: reason mentions {reason_contains!r}",
              ok_json and reason_contains.lower() in str(out.get("reason", "")).lower(),
              f"got {out.get('reason') if ok_json else out!r}")


# ------------------------------------------------------------------- cases

check("subject exists at .claude/scripts/compose_subissue_title.py", SUBJECT.is_file(),
      f"{SUBJECT} is absent (RED: helper not yet written)")

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    good = write_conv(tmp, conventions())

    # 1. normal case
    p = compose(good)
    expect_composed("normal", p, EXPECTED)
    out = parse(p)
    check("normal: legend not required in title", isinstance(out, dict) and "legend" not in str(out.get("title", "")).lower()
          and LEGEND not in str(out.get("title", "")), f"got {out!r}")

    # 2. leading '#' and whitespace
    expect_composed("leading-hash", compose(good, parent="#638"), EXPECTED)
    expect_composed("trimmed-parent", compose(good, parent=" 638 "), EXPECTED)
    expect_composed("trimmed-subtask", compose(good, subtask=" 16 "), EXPECTED)

    # 3. every composed title matches the fixture pattern, for every tag
    for tag in TAGS:
        o = parse(compose(good, tag=tag))
        t = o.get("title") if isinstance(o, dict) else None
        check(f"pattern: {tag} title matches issueTitle.pattern (I-1)",
              isinstance(t, str) and re.match(PATTERN, t) is not None and "P:#638" in t and "ST:16" in t,
              f"got {t!r}")

    # 4. changed format changes output (I-3)
    colon = write_conv(tmp, conventions(fmt="[<EFFORT>] P:#<parent> ST:<subtask>: <Title>"), "colon.json")
    expect_composed("format-changed", compose(colon),
                    "[PERF] P:#638 ST:16: Fix Earnings Index (dotnet-backend-architect)")

    # 5. shell-hostile bare title passes through verbatim
    nasty = 'Fix "quotes" and `ticks` and $HOME ok'
    expect_composed("verbatim", compose(good, title=nasty), f"[PERF] P:#638 ST:16 - {nasty}")

    # 6. conventions-missing
    expect_refused("conventions: no file", compose(tmp / "nope.json"), "conventions-missing")
    expect_refused("conventions: no issueTitle",
                   compose(write_conv(tmp, conventions(with_title=False), "noit.json")), "conventions-missing")
    expect_refused("conventions: no issueTitle.subIssue",
                   compose(write_conv(tmp, conventions(with_sub=False), "nosub.json")), "conventions-missing")
    expect_refused("conventions: root not determinable (I-6)",
                   compose(None), "conventions-missing", reason_contains="root")

    # 7. format-malformed
    bad_formats = {
        "missing parent": "[<EFFORT>] ST:<subtask> - <Title>",
        "missing subtask": "[<EFFORT>] P:#<parent> - <Title>",
        "repeated placeholder": "[<EFFORT>] P:#<parent> P:#<parent> ST:<subtask> - <Title>",
        "not led by effort": "P:#<parent> [<EFFORT>] ST:<subtask> - <Title>",
    }
    for label, fmt in bad_formats.items():
        c = write_conv(tmp, conventions(fmt=fmt), f"bad-{abs(hash(label))}.json")
        expect_refused(f"format-malformed: {label}", compose(c), "format-malformed")

    # 8. parent faults
    expect_refused("parent-missing", compose(good, parent=""), "parent-missing")
    for raw in ["0", "-3", "##638", "abc", "638.0", "owner/repo#638"]:
        expect_refused(f"parent-not-positive-integer: {raw!r}", compose(good, parent=raw),
                       "parent-not-positive-integer")

    # 9. subtask faults
    expect_refused("subtask-missing", compose(good, subtask=""), "subtask-missing")
    for raw in ["0", "t16", "16.0", "-1"]:
        expect_refused(f"subtask-not-positive-integer: {raw!r}", compose(good, subtask=raw),
                       "subtask-not-positive-integer")

    # 10. bare-title-invalid
    for label, t in [("empty", ""), ("whitespace", "   "), ("newline", "Fix\nIndex"),
                     ("already tagged", "[PERF] Fix Index")]:
        expect_refused(f"bare-title-invalid: {label}", compose(good, title=t), "bare-title-invalid")

    # 11. pattern-mismatch
    expect_refused("pattern-mismatch: undeclared tag", compose(good, tag="WIBBLE"), "pattern-mismatch")

    # 12. refusal order, two faults at once
    expect_refused("order: parent before title", compose(good, parent="abc", title=""),
                   "parent-not-positive-integer")
    expect_refused("order: parent-missing before subtask", compose(good, parent="", subtask="zzz"),
                   "parent-missing")
    expect_refused("order: subtask before title", compose(good, subtask="t16", title=""),
                   "subtask-not-positive-integer")
    expect_refused("order: format before parent",
                   compose(write_conv(tmp, conventions(fmt="[<EFFORT>] ST:<subtask> - <Title>"), "ord.json"),
                           parent="abc"),
                   "format-malformed")
    expect_refused("order: title before pattern", compose(good, tag="WIBBLE", title=""), "bare-title-invalid")

    # 13. purity (I-4): no file written anywhere in the fixture dir
    def snapshot(d: Path) -> dict:
        return {str(f.relative_to(d)): hashlib.sha256(f.read_bytes()).hexdigest()
                for f in d.rglob("*") if f.is_file()}

    before = snapshot(tmp)
    ran = compose(good)
    compose(good, parent="abc")
    after = snapshot(tmp)
    check("purity: helper ran (exit 0) for the listing comparison", ran.returncode == 0,
          f"rc={ran.returncode}; helper missing")
    check("purity: no file written or modified (I-4)", before == after, f"before={sorted(before)} after={sorted(after)}")

# 14. real corpus: shipped conventions file
if SHIPPED_CONVENTIONS.is_file():
    expect_composed("real corpus", compose(SHIPPED_CONVENTIONS), EXPECTED)
    shipped = json.loads(SHIPPED_CONVENTIONS.read_text(encoding="utf-8"))
    sub = shipped.get("issueTitle", {}).get("subIssue", {})
    check("real corpus: issueTitle.subIssue has $comment, legend, format",
          all(isinstance(sub.get(k), str) and sub.get(k) for k in ("$comment", "legend", "format")),
          f"got keys {sorted(sub)}")
else:
    check("real corpus: shipped conventions file exists", False, str(SHIPPED_CONVENTIONS))

# ------------------------------------------------------- skill-sync checks

CAUSES = [
    "conventions-missing", "format-malformed", "parent-missing", "parent-not-positive-integer",
    "subtask-missing", "subtask-not-positive-integer", "bare-title-invalid", "pattern-mismatch",
]
prose = PARENT_AWARE.read_text(encoding="utf-8") if PARENT_AWARE.is_file() else ""
check("sync: parent-aware-mode.md exists", bool(prose), str(PARENT_AWARE))
check("sync: parent-aware-mode.md names compose_subissue_title.py", "compose_subissue_title.py" in prose,
      "helper not named in prose")
for cause in CAUSES:
    check(f"sync: parent-aware-mode.md names cause {cause}", cause in prose, "cause not named")
cause_like = set(re.findall(r"`([a-z]+(?:-[a-z]+)*-(?:missing|invalid|malformed|mismatch|integer))`", prose))
check("sync: no invented *-missing/*-invalid-style cause", cause_like <= set(CAUSES),
      f"extra: {sorted(cause_like - set(CAUSES))}")
check("sync: old literal '[<TYPE>] <bare title>' template is gone", "[<TYPE>] <bare title>" not in prose,
      "old title template still present")

flow = FLOW_SKILL.read_text(encoding="utf-8") if FLOW_SKILL.is_file() else ""
check("sync: skills/flow/SKILL.md contains no:parent-issue", "no:parent-issue" in flow, "note not added")

doctor = DOCTOR.read_text(encoding="utf-8") if DOCTOR.is_file() else ""
check("sync: plugin_doctor.py scaffold contains subIssue", "subIssue" in doctor, "scaffold lacks subIssue block")

# ----------------------------------------------------------------- summary

print()
print(f"{PASSED} passed, {len(FAILURES)} failed")
if FAILURES:
    print("FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("ALL PASS")
