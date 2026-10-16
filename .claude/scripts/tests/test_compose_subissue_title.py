#!/usr/bin/env python3
"""
test_compose_subissue_title.py -- RED-first suite for the sub-issue title
helper `.claude/scripts/compose_subissue_title.py` (contract
.claude/concepts/2026-10-15-subissue-title-parent-ref.md).

House style: plain runnable script, NO pytest (see test_verify_parent_link.py).
check(name, cond, detail) accumulator, PASS/FAIL summary, non-zero exit on any
failure.

    py -3 .claude/scripts/tests/test_compose_subissue_title.py

Two ways to drive the helper:
  * the CLI, by subprocess and absolute path, for the cases that are about the
    process itself (exit codes, environment, cwd purity, argv oddities, human
    output mode);
  * compose() imported in-process, for the pure-logic tables. If the module is
    not importable cleanly, every table falls back to the CLI, so a missing
    helper fails by check() message and never by ImportError.

Every case builds its own fixture conventions file under a temp dir, except the
"real corpus" and sync cases. CLAUDE_PROJECT_DIR is removed from the child
environment unless a case sets it deliberately.

Mutation-review additions (survivors M04..M24) are grouped under their own
banner comments below.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO = SCRIPTS.parent.parent
SUBJECT = SCRIPTS / "compose_subissue_title.py"
SHIPPED_CONVENTIONS = REPO / ".claude" / "work-item-conventions.json"
PARENT_AWARE = REPO / "skills" / "task" / "references" / "parent-aware-mode.md"
FLOW_SKILL = REPO / "skills" / "flow" / "SKILL.md"
SKILLS_DIR = REPO / "skills"
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


def slug(label: str) -> str:
    """Stable, readable temp-file stem for a case label (never abs(hash(...)))."""
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "case"


# ---------------------------------------------------------------- fixtures

PATTERN = r"^\[(FEATURE|BUG|IMPROVEMENT|REFACTOR|PERF|SECURITY|DOCS|CHORE|SPIKE)\] .+"
TAGS = ["FEATURE", "BUG", "IMPROVEMENT", "REFACTOR", "PERF", "SECURITY", "DOCS", "CHORE", "SPIKE"]
FORMAT = "[<EFFORT>] P:#<parent> ST:<subtask> - <Title>"
LEGEND = "P = parent issue, ST = sub-task (its position in the parent's plan)"
EXPECTED = "[PERF] P:#638 ST:16 - Fix Earnings Index (dotnet-backend-architect)"
BARE = "Fix Earnings Index (dotnet-backend-architect)"


def conventions(fmt: str | None = FORMAT, with_sub: bool = True, with_title: bool = True,
                pattern: str = PATTERN) -> dict:
    data: dict = {"$comment": "fixture"}
    if with_title:
        it: dict = {
            "$comment": "fixture",
            "format": "[<EFFORT>] <Title>",
            "pattern": pattern,
            "exactlyOne": True,
            "effortTypes": [{"tag": t, "means": t} for t in TAGS],
        }
        if with_sub:
            it["subIssue"] = {"$comment": "fixture", "legend": LEGEND, "format": fmt}
        data["issueTitle"] = it
    return data


def write_conv(tmp: Path, data, name: str = "conv.json") -> Path:
    p = tmp / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def run(args: list[str], env_extra: dict | None = None, cwd: Path | None = None):
    """Run the helper CLI. CLAUDE_PROJECT_DIR is removed unless env_extra sets it."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SUBJECT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=60, cwd=str(cwd) if cwd else None,
    )


def compose(conv: Path | None, tag="PERF", parent="638", subtask="16", title=BARE, env_extra=None,
            cwd: Path | None = None, as_json: bool = True):
    """CLI call (the process-level cases)."""
    args = ["--type", tag, "--parent", parent, "--subtask", subtask, "--title", title]
    if as_json:
        args.append("--json")
    if conv is not None:
        args += ["--conventions", str(conv)]
    return run(args, env_extra=env_extra, cwd=cwd)


# In-process compose() for the pure-logic tables ------------------------------

def _load_module():
    if not SUBJECT.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("compose_subissue_title_under_test", SUBJECT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod if callable(getattr(mod, "compose", None)) else None
    except BaseException:  # noqa: BLE001 - a broken import must degrade to the CLI, not crash the suite
        return None


MOD = _load_module()


class _Proc:
    def __init__(self, returncode: int, stdout: str, stderr: str = ""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def cmp(conv: Path | None, tag="PERF", parent="638", subtask="16", title=BARE):
    """Table-style call: in-process compose() when importable, else the CLI. Returns a proc-like."""
    if MOD is None or conv is None:
        return compose(conv, tag=tag, parent=parent, subtask=subtask, title=title)
    saved = os.environ.pop("CLAUDE_PROJECT_DIR", None)
    try:
        result = MOD.compose(tag, parent, subtask, title, str(conv))
    except BaseException as exc:  # noqa: BLE001 - surfaced as a failed check, never a traceback
        return _Proc(1, "", "%s: %s" % (type(exc).__name__, exc))
    finally:
        if saved is not None:
            os.environ["CLAUDE_PROJECT_DIR"] = saved
    return _Proc(0 if result.get("verdict") == "composed" else 2, json.dumps(result))


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
          f"expected exit 2 with JSON, got rc={proc.returncode} stdout={proc.stdout.strip()[:100]!r} "
          f"stderr={proc.stderr.strip()[:100]!r}")
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
check("subject is importable (compose() callable) for the in-process tables", MOD is not None,
      "module did not import cleanly; tables fall back to the CLI")

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    good = write_conv(tmp, conventions())

    # 1. normal case (CLI)
    p = compose(good)
    expect_composed("normal", p, EXPECTED)
    out = parse(p)
    check("normal: legend not required in title", isinstance(out, dict) and "legend" not in str(out.get("title", "")).lower()
          and LEGEND not in str(out.get("title", "")), f"got {out!r}")

    # 2. leading '#' and whitespace
    expect_composed("leading-hash", cmp(good, parent="#638"), EXPECTED)
    expect_composed("trimmed-parent", cmp(good, parent=" 638 "), EXPECTED)
    expect_composed("trimmed-subtask", cmp(good, subtask=" 16 "), EXPECTED)

    # 3. every composed title matches the fixture pattern, for every tag
    for tag in TAGS:
        o = parse(cmp(good, tag=tag))
        t = o.get("title") if isinstance(o, dict) else None
        check(f"pattern: {tag} title matches issueTitle.pattern (I-1)",
              isinstance(t, str) and re.match(PATTERN, t) is not None and "P:#638" in t and "ST:16" in t,
              f"got {t!r}")

    # 4. changed format changes output (I-3)
    colon = write_conv(tmp, conventions(fmt="[<EFFORT>] P:#<parent> ST:<subtask>: <Title>"), "colon.json")
    expect_composed("format-changed", cmp(colon),
                    "[PERF] P:#638 ST:16: Fix Earnings Index (dotnet-backend-architect)")

    # 5. shell-hostile bare title passes through verbatim
    nasty = 'Fix "quotes" and `ticks` and $HOME ok'
    expect_composed("verbatim", cmp(good, title=nasty), f"[PERF] P:#638 ST:16 - {nasty}")

    # 6. conventions-missing
    expect_refused("conventions: no file", cmp(tmp / "nope.json"), "conventions-missing")
    expect_refused("conventions: no issueTitle",
                   cmp(write_conv(tmp, conventions(with_title=False), "noit.json")), "conventions-missing")
    expect_refused("conventions: no issueTitle.subIssue",
                   cmp(write_conv(tmp, conventions(with_sub=False), "nosub.json")), "conventions-missing")
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
        c = write_conv(tmp, conventions(fmt=fmt), f"bad-{slug(label)}.json")
        expect_refused(f"format-malformed: {label}", cmp(c), "format-malformed")

    # 8. parent faults
    expect_refused("parent-missing", cmp(good, parent=""), "parent-missing")
    for raw in ["0", "-3", "##638", "abc", "638.0", "owner/repo#638"]:
        expect_refused(f"parent-not-positive-integer: {raw!r}", cmp(good, parent=raw),
                       "parent-not-positive-integer")

    # 9. subtask faults
    expect_refused("subtask-missing", cmp(good, subtask=""), "subtask-missing")
    for raw in ["0", "t16", "16.0", "-1"]:
        expect_refused(f"subtask-not-positive-integer: {raw!r}", cmp(good, subtask=raw),
                       "subtask-not-positive-integer")

    # 10. bare-title-invalid
    for label, t in [("empty", ""), ("whitespace", "   "), ("newline", "Fix\nIndex"),
                     ("already tagged", "[PERF] Fix Index")]:
        expect_refused(f"bare-title-invalid: {label}", cmp(good, title=t), "bare-title-invalid")

    # 11. pattern-mismatch
    expect_refused("pattern-mismatch: undeclared tag", cmp(good, tag="WIBBLE"), "pattern-mismatch")

    # 12. refusal order, two faults at once
    expect_refused("order: parent before title", cmp(good, parent="abc", title=""),
                   "parent-not-positive-integer")
    expect_refused("order: parent-missing before subtask", cmp(good, parent="", subtask="zzz"),
                   "parent-missing")
    expect_refused("order: subtask before title", cmp(good, subtask="t16", title=""),
                   "subtask-not-positive-integer")
    expect_refused("order: format before parent",
                   cmp(write_conv(tmp, conventions(fmt="[<EFFORT>] ST:<subtask> - <Title>"), "ord.json"),
                       parent="abc"),
                   "format-malformed")
    expect_refused("order: title before pattern", cmp(good, tag="WIBBLE", title=""), "bare-title-invalid")

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

    # ===================================================================
    # Mutation-review hardening
    # ===================================================================

    # --- M21 purity with cwd = the snapshotted dir (a helper writing to its cwd is caught)
    cwd_dir = tmp / "cwd-sandbox"
    cwd_dir.mkdir()
    cwd_conv = write_conv(tmp, conventions(), "cwd-conv.json")
    snap_before = snapshot(tmp)
    r_ok = compose(cwd_conv, cwd=cwd_dir)
    r_bad = compose(cwd_conv, parent="abc", cwd=cwd_dir)
    r_human = compose(cwd_conv, cwd=cwd_dir, as_json=False)
    snap_after = snapshot(tmp)
    check("purity(cwd): helper ran in the snapshotted dir", r_ok.returncode == 0 and r_bad.returncode == 2
          and r_human.returncode == 0, f"rc={r_ok.returncode}/{r_bad.returncode}/{r_human.returncode}")
    check("purity(cwd): no file appears in cwd or beside the fixtures (I-4, M21)", snap_before == snap_after,
          f"new: {sorted(set(snap_after) - set(snap_before))}")
    check("purity(cwd): cwd dir stays empty", list(cwd_dir.iterdir()) == [],
          f"found {[x.name for x in cwd_dir.iterdir()]}")

    # --- M22 / I-4 AST: no subprocess/shutil/os.system, never opens a file for writing
    if SUBJECT.is_file():
        tree = ast.parse(SUBJECT.read_text(encoding="utf-8"))
        offences: list[str] = []
        write_attrs = {"write_text", "write_bytes", "touch", "mkdir", "unlink", "rmdir", "makedirs",
                       "remove", "removedirs", "truncate", "symlink_to", "hardlink_to"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in {"subprocess", "shutil"}:
                        offences.append("import " + a.name)
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in {"subprocess", "shutil"}:
                    offences.append("from %s import ..." % node.module)
            elif isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Attribute):
                    if isinstance(f.value, ast.Name) and f.value.id == "os" and (
                            f.attr in {"system", "popen", "startfile"} or f.attr.startswith(("spawn", "exec"))):
                        offences.append("os." + f.attr)
                    if f.attr in write_attrs:
                        offences.append("." + f.attr + "()")
                is_open = (isinstance(f, ast.Name) and f.id == "open") or (isinstance(f, ast.Attribute) and f.attr == "open")
                if is_open:
                    mode_node = None
                    idx = 1 if (isinstance(f, ast.Name)) else 0
                    if len(node.args) > idx:
                        mode_node = node.args[idx]
                    for kw in node.keywords:
                        if kw.arg == "mode":
                            mode_node = kw.value
                    if mode_node is not None:
                        if not (isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str)
                                and not set(mode_node.value) & set("wax+")):
                            offences.append("open() with a mode that may write")
        check("purity(AST): no subprocess/shutil/os.system/file-write calls in the helper (I-4, M22)",
              offences == [], f"found {offences}")
    else:
        check("purity(AST): helper present to inspect", False, f"{SUBJECT} is absent")

    # --- M15 / M16 / M18: unreadable conventions are conventions-missing, never a traceback.
    # Empty format: the contract's closed order checks conventions-missing FIRST ("issueTitle.subIssue.format
    # absent or unreadable"); an empty string is as unusable as an absent one, so it is conventions-missing,
    # not format-malformed.
    bad_json = tmp / "invalid.json"
    bad_json.write_text("{ this is not json", encoding="utf-8")
    expect_refused("unreadable: invalid JSON (M16)", cmp(bad_json), "conventions-missing")
    arr = write_conv(tmp, [1, 2], "array.json")
    expect_refused("unreadable: JSON is not an object", cmp(arr), "conventions-missing")
    nopat = conventions()
    del nopat["issueTitle"]["pattern"]
    expect_refused("unreadable: issueTitle without pattern", cmp(write_conv(tmp, nopat, "nopat.json")),
                   "conventions-missing")
    expect_refused("unreadable: invalid regex in pattern (M15)",
                   cmp(write_conv(tmp, conventions(pattern="^(unclosed"), "badre.json")), "conventions-missing")
    expect_refused("unreadable: empty format string (M18)",
                   cmp(write_conv(tmp, conventions(fmt=""), "emptyfmt.json")), "conventions-missing")

    # --- M09 / M23 / I-2 post-render: the rendered title fails the pattern -> pattern-mismatch, no title
    nospace = write_conv(tmp, conventions(fmt="[<EFFORT>]P:#<parent> ST:<subtask> - <Title>"), "nospace.json")
    expect_refused("post-render: no space after the bracket fails issueTitle.pattern",
                   cmp(nospace), "pattern-mismatch")
    narrow = write_conv(tmp, conventions(pattern=r"^\[(FEATURE|BUG)\] .+"), "narrow.json")
    expect_refused("post-render: pattern narrower than effortTypes", cmp(narrow, tag="PERF"), "pattern-mismatch")
    expect_composed("post-render: narrow pattern still composes a tag it allows", cmp(narrow, tag="BUG"),
                    "[BUG] P:#638 ST:16 - Fix Earnings Index (dotnet-backend-architect)")

    # --- M10 exactly-once for EVERY placeholder
    exact_once = {
        "missing <Title>": "[<EFFORT>] P:#<parent> ST:<subtask>",
        "missing <EFFORT> (not led by it)": "P:#<parent> ST:<subtask> - <Title>",
        "repeated <Title>": "[<EFFORT>] P:#<parent> ST:<subtask> - <Title> <Title>",
        "repeated <EFFORT>": "[<EFFORT>] P:#<parent> ST:<subtask> - <Title> <EFFORT>",
        "repeated <subtask>": "[<EFFORT>] P:#<parent> ST:<subtask> ST:<subtask> - <Title>",
    }
    for label, fmt in exact_once.items():
        c = write_conv(tmp, conventions(fmt=fmt), f"once-{slug(label)}.json")
        expect_refused(f"format-malformed(exactly-once): {label}", cmp(c), "format-malformed")

    # --- M11 / M12 / M13 numeric input tables
    for raw in ["#", "   ", " # "]:
        expect_refused(f"parent-missing: {raw!r} (M11)", cmp(good, parent=raw), "parent-missing")
    expect_refused("subtask-not-positive-integer: '#16' (M12)", cmp(good, subtask="#16"),
                   "subtask-not-positive-integer")
    arabic = "٦٣٨"  # Arabic-Indic 638
    expect_refused("parent-not-positive-integer: Arabic-Indic digits (M13)", cmp(good, parent=arabic),
                   "parent-not-positive-integer")
    expect_refused("subtask-not-positive-integer: Arabic-Indic digits (M13)", cmp(good, subtask=arabic),
                   "subtask-not-positive-integer")
    expect_refused("parent-not-positive-integer: '#' + Arabic-Indic digits (M13)", cmp(good, parent="#" + arabic),
                   "parent-not-positive-integer")

    # --- M04 bare-title control characters (not just \n)
    for label, t in [("carriage return", "Fix\rIndex"), ("tab", "Fix\tIndex"), ("NUL", "Fix\x00Index"),
                     ("U+2028 line separator", "Fix Index"), ("U+2029 paragraph separator", "Fix Index"),
                     ("escape", "Fix\x1bIndex")]:
        expect_refused(f"bare-title-invalid: {label} (M04)", cmp(good, title=t), "bare-title-invalid")

    # --- M05 single-pass: placeholders inside the bare title are not expanded
    tricky = "Fix <parent> <Title> <EFFORT> <subtask>"
    expect_composed("single-pass: placeholder-looking bare title is verbatim (M05)", cmp(good, title=tricky),
                    f"[PERF] P:#638 ST:16 - {tricky}")

    # --- M14 bare title trimmed in the output
    expect_composed("trim: '  Fix X  ' is trimmed in the composed title (M14)", cmp(good, title="  Fix X  "),
                    "[PERF] P:#638 ST:16 - Fix X")

    # --- unicode round trip byte-exact through the CLI JSON
    uni = "Fix — em dash 修复指数"
    expect_composed("unicode: em dash and CJK round-trip byte-exact through the CLI JSON",
                    compose(good, title=uni), f"[PERF] P:#638 ST:16 - {uni}")

    # --- argv oddities: a bare title starting with '--' must never be argparse exit 2 without JSON
    for odd in ["--help me", "--help", "--json", "-x"]:
        pr = compose(good, title=odd)
        o = parse(pr)
        ok = isinstance(o, dict) and ((pr.returncode == 0 and o.get("verdict") == "composed")
                                      or (pr.returncode == 2 and o.get("verdict") == "refused"))
        check(f"argv: bare title {odd!r} yields a JSON composition or refusal, never a bare argparse exit",
              ok, f"rc={pr.returncode} stdout={pr.stdout.strip()[:80]!r} stderr={pr.stderr.strip()[:80]!r}")
        if isinstance(o, dict) and o.get("verdict") == "composed":
            check(f"argv: bare title {odd!r} composed verbatim", o.get("title") == f"[PERF] P:#638 ST:16 - {odd}",
                  f"got {o.get('title')!r}")

    # --- M19 human (non-JSON) output mode
    human_bad = compose(good, parent="abc", as_json=False)
    check("human mode: a refusal exits 2", human_bad.returncode == 2, f"rc={human_bad.returncode}")
    check("human mode: a refusal names its cause (M19)", "parent-not-positive-integer" in human_bad.stdout,
          f"stdout={human_bad.stdout.strip()[:120]!r}")
    human_bad_conv = compose(tmp / "nope.json", as_json=False)
    check("human mode: conventions-missing names its cause", "conventions-missing" in human_bad_conv.stdout,
          f"stdout={human_bad_conv.stdout.strip()[:120]!r}")
    human_ok = compose(good, as_json=False)
    check("human mode: composed prints the title and exits 0", human_ok.returncode == 0
          and human_ok.stdout.strip() == EXPECTED, f"rc={human_ok.returncode} stdout={human_ok.stdout.strip()[:120]!r}")

    # --- I-6: CLAUDE_PROJECT_DIR set / unset, no --conventions
    proj_ok = tmp / "proj-ok"
    (proj_ok / ".claude").mkdir(parents=True)
    write_conv(proj_ok / ".claude", conventions(fmt="[<EFFORT>] P:#<parent> ST:<subtask>: <Title>"),
               "work-item-conventions.json")
    expect_composed("I-6: CLAUDE_PROJECT_DIR set, project file present -> composes from that file (M07)",
                    compose(None, env_extra={"CLAUDE_PROJECT_DIR": str(proj_ok)}),
                    "[PERF] P:#638 ST:16: Fix Earnings Index (dotnet-backend-architect)")
    proj_empty = tmp / "proj-empty"
    (proj_empty / ".claude").mkdir(parents=True)
    r6 = compose(None, env_extra={"CLAUDE_PROJECT_DIR": str(proj_empty)})
    expect_refused("I-6: CLAUDE_PROJECT_DIR set but project file absent -> conventions-missing, never the plugin file",
                   r6, "conventions-missing")
    o6 = parse(r6)
    reason6 = str(o6.get("reason", "")) if isinstance(o6, dict) else ""
    norm6 = reason6.replace("\\", "/").lower()
    missing_path = (proj_empty / ".claude" / "work-item-conventions.json").as_posix().lower()
    check("I-6: the reason names the missing project path", missing_path in norm6,
          f"expected {missing_path!r} in reason {reason6!r}")
    r6u = compose(None)
    expect_refused("I-6: CLAUDE_PROJECT_DIR unset -> conventions-missing mentioning the root", r6u,
                   "conventions-missing", reason_contains="root")

    # --- remediation pin: pasted block equals the shipped subIssue block
    miss = parse(compose(tmp / "nope.json"))
    remediation = str(miss.get("remediation", "")) if isinstance(miss, dict) else ""
    check("remediation: conventions-missing carries a non-empty remediation (M24)", remediation.strip() != "",
          f"got {miss!r}")
    pasted = None
    first, last = remediation.find("{"), remediation.rfind("}")
    if first != -1 and last > first:
        try:
            pasted = json.loads(remediation[first:last + 1])
        except ValueError:
            pasted = None
    check("remediation: contains a parseable JSON block", isinstance(pasted, dict), f"remediation={remediation[:160]!r}")
    if SHIPPED_CONVENTIONS.is_file():
        shipped_sub = json.loads(SHIPPED_CONVENTIONS.read_text(encoding="utf-8"))["issueTitle"]["subIssue"]
        check("remediation: pasted format equals the shipped issueTitle.subIssue.format",
              isinstance(pasted, dict) and pasted.get("format") == shipped_sub["format"],
              f"pasted={pasted!r} shipped={shipped_sub['format']!r}")
        check("remediation: pasted legend equals the shipped issueTitle.subIssue.legend",
              isinstance(pasted, dict) and pasted.get("legend") == shipped_sub["legend"],
              f"pasted={pasted!r} shipped={shipped_sub['legend']!r}")

# 14. real corpus: shipped conventions file
if SHIPPED_CONVENTIONS.is_file():
    expect_composed("real corpus", compose(SHIPPED_CONVENTIONS), EXPECTED)
    shipped = json.loads(SHIPPED_CONVENTIONS.read_text(encoding="utf-8"))
    sub = shipped.get("issueTitle", {}).get("subIssue", {})
    check("real corpus: issueTitle.subIssue has $comment, legend, format",
          all(isinstance(sub.get(k), str) and sub.get(k) for k in ("$comment", "legend", "format")),
          f"got keys {sorted(sub)}")
else:
    shipped, sub = {}, {}
    check("real corpus: shipped conventions file exists", False, str(SHIPPED_CONVENTIONS))

# ------------------------------------------------------- skill-sync checks

CAUSES_FALLBACK = [
    "conventions-missing", "format-malformed", "parent-missing", "parent-not-positive-integer",
    "subtask-missing", "subtask-not-positive-integer", "bare-title-invalid", "pattern-mismatch",
]
helper_causes = getattr(MOD, "CAUSES", None) if MOD is not None else None
check("sync: helper exposes CAUSES (the closed, ordered list)",
      isinstance(helper_causes, (list, tuple)) and len(helper_causes) > 0, "compose_subissue_title.CAUSES missing")
CAUSES = list(helper_causes) if isinstance(helper_causes, (list, tuple)) and helper_causes else CAUSES_FALLBACK

prose = PARENT_AWARE.read_text(encoding="utf-8") if PARENT_AWARE.is_file() else ""
check("sync: parent-aware-mode.md exists", bool(prose), str(PARENT_AWARE))
check("sync: parent-aware-mode.md names compose_subissue_title.py", "compose_subissue_title.py" in prose,
      "helper not named in prose")
for cause in CAUSES:
    check(f"sync: parent-aware-mode.md names cause {cause}", cause in prose, "cause not named")
cause_like = set(re.findall(r"`([a-z]+(?:-[a-z]+)*-(?:missing|invalid|malformed|mismatch|integer))`", prose))
check("sync: no invented *-missing/*-invalid-style cause", cause_like <= set(CAUSES),
      f"extra: {sorted(cause_like - set(CAUSES))}")


def refusal_table_causes(text: str) -> list[str]:
    """First column of the refusal table (the one headed '| Cause |'), in document order."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if re.match(r"^\|\s*Cause\s*\|", ln)), None)
    if start is None:
        return []
    found: list[str] = []
    for ln in lines[start + 1:]:
        if not ln.lstrip().startswith("|"):
            break
        m = re.match(r"^\|\s*`([^`]+)`\s*\|", ln)
        if m:
            found.append(m.group(1))
    return found


table_causes = refusal_table_causes(prose)
check("sync: refusal table first column holds no invented cause", bool(table_causes) and set(table_causes) <= set(CAUSES),
      f"table={table_causes} extra={sorted(set(table_causes) - set(CAUSES))}")
check("sync: refusal table lists every helper cause", set(table_causes) >= set(CAUSES),
      f"missing from table: {sorted(set(CAUSES) - set(table_causes))}")
check("sync: refusal table order equals the helper's CAUSES order", table_causes == list(CAUSES),
      f"table={table_causes} helper={list(CAUSES)}")
check("sync: old literal '[<TYPE>] <bare title>' template is gone", "[<TYPE>] <bare title>" not in prose,
      "old title template still present")

flow = FLOW_SKILL.read_text(encoding="utf-8") if FLOW_SKILL.is_file() else ""
check("sync: skills/flow/SKILL.md contains no:parent-issue", "no:parent-issue" in flow, "note not added")

doctor = DOCTOR.read_text(encoding="utf-8") if DOCTOR.is_file() else ""
check("sync: plugin_doctor.py scaffold contains subIssue", "subIssue" in doctor, "scaffold lacks subIssue block")

# plugin_doctor.SCAFFOLDS conventions entry must carry the shipped block's format and legend
scaffold_sub = None
try:
    sys.path.insert(0, str(SCRIPTS))
    import plugin_doctor  # type: ignore  # noqa: E402
    scaffold_json = json.loads(plugin_doctor.SCAFFOLDS[".claude/work-item-conventions.json"])
    scaffold_sub = scaffold_json.get("issueTitle", {}).get("subIssue")
except BaseException as exc:  # noqa: BLE001
    print(f"      (plugin_doctor import/parse failed: {type(exc).__name__}: {exc})")
finally:
    if str(SCRIPTS) in sys.path:
        sys.path.remove(str(SCRIPTS))
check("sync: plugin_doctor.SCAFFOLDS conventions entry parses and has issueTitle.subIssue",
      isinstance(scaffold_sub, dict), f"got {scaffold_sub!r}")
check("sync: scaffold subIssue.format equals the shipped block's",
      isinstance(scaffold_sub, dict) and scaffold_sub.get("format") == sub.get("format"),
      f"scaffold={scaffold_sub and scaffold_sub.get('format')!r} shipped={sub.get('format')!r}")
check("sync: scaffold subIssue.legend equals the shipped block's",
      isinstance(scaffold_sub, dict) and scaffold_sub.get("legend") == sub.get("legend"),
      f"scaffold={scaffold_sub and scaffold_sub.get('legend')!r} shipped={sub.get('legend')!r}")

# The shape is declared once: no skill file restates the format, its skeleton, or the legend.
shipped_format = sub.get("format") or FORMAT
shipped_legend = sub.get("legend") or LEGEND
skill_hits = {"format": [], "P:# skeleton": [], "ST: skeleton": [], "legend": []}
for f in sorted(SKILLS_DIR.rglob("*")):
    if not f.is_file():
        continue
    try:
        txt = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    rel = f.relative_to(REPO).as_posix()
    if shipped_format in txt:
        skill_hits["format"].append(rel)
    if "P:#" in txt:
        skill_hits["P:# skeleton"].append(rel)
    if re.search(r"(?<![A-Za-z])ST:", txt):
        skill_hits["ST: skeleton"].append(rel)
    if shipped_legend in txt or "its position in the parent's plan" in txt:
        skill_hits["legend"].append(rel)
for what, files in skill_hits.items():
    check(f"single source: the shipped {what} appears in NO file under skills/", files == [],
          f"restated in {files}")

# ------------------------------------------------- shell replay of the skill block

BASH_FENCE = re.compile(r"^\s*```\s*(bash|sh|shell)?\s*$")


def find_bash() -> str | None:
    """Git for Windows' bash first (the one Claude Code uses), never the WSL launcher."""
    git = shutil.which("git")
    if git:
        candidate = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("bash")
    if found and "system32" not in found.lower():
        return found
    return None


def fenced_blocks(text: str) -> list[str]:
    blocks, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        m = re.match(r"^\s*```\s*([A-Za-z0-9_-]*)\s*$", lines[i])
        if m:
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("```"):
                j += 1
            if m.group(1) in ("bash", "sh", "shell"):
                blocks.append("\n".join(lines[i + 1:j]))
            i = j
        i += 1
    return blocks


PLACEHOLDER = re.compile(r"<[A-Za-z][^<>\n]*>")


def unquoted_placeholders(block: str) -> list[str]:
    """<PLACEHOLDER> tokens on shell lines that do not sit inside double quotes (heredoc bodies and comments skipped)."""
    bad: list[str] = []
    heredoc_end = None
    for line in block.splitlines():
        if heredoc_end is not None:
            if line.strip() == heredoc_end:
                heredoc_end = None
            continue
        if line.lstrip().startswith("#"):
            continue
        hd = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", line)
        in_dq = in_sq = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and not in_sq:
                i += 2
                continue
            if ch == "'" and not in_dq:
                in_sq = not in_sq
            elif ch == '"' and not in_sq:
                in_dq = not in_dq
            elif ch == "<" and not in_dq:
                m = PLACEHOLDER.match(line, i)
                if m:
                    bad.append(m.group(0))
                    i = m.end()
                    continue
            i += 1
        if hd:
            heredoc_end = hd.group(2)
    return bad


REPLAY_TITLES = {
    "double quote": 'Say "hi" now',
    "backtick": "Run `ls` now",
    "command substitution": "Cost $(echo PWNED) ok",
    "single quote": "Don't stop",
    "leading dashes": "--help me",
    "em dash": "Fix — dash",
    "CJK": "修复指数",
}
BODY_TEXT = "BODY LINE one\nBODY LINE two with \"quotes\" and $(x)"

RECORDER = textwrap.dedent('''\
    import json, os, sys
    tool, argv = sys.argv[1], sys.argv[2:]
    try:
        stdin = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.buffer.read().decode("utf-8")
    except Exception:
        stdin = ""
    body = None
    for i, a in enumerate(argv):
        path = None
        if a == "--body-file" and i + 1 < len(argv):
            path = argv[i + 1]
        elif a.startswith("--body-file="):
            path = a.split("=", 1)[1]
        if path is not None:
            try:
                body = stdin if path == "-" else open(path, "rb").read().decode("utf-8")
            except Exception as exc:
                body = "<unreadable: %s>" % exc
    with open(os.environ["STUB_REC"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"tool": tool, "argv": argv, "body": body, "stdin": stdin}) + "\\n")
    if tool == "gh":
        print("https://github.com/o/r/issues/99")
    else:
        print(json.dumps({"verdict": "linked"}))
''')


def posix(p) -> str:
    return str(p).replace("\\", "/")


def build_project(root: Path, with_helper: bool = True) -> tuple[Path, Path]:
    """A throwaway project holding copies of the real scripts, a stub verifier, and a stub bin dir."""
    proj = root / "proj"
    (proj / ".claude" / "scripts").mkdir(parents=True)
    (proj / ".claude" / "hooks").mkdir(parents=True)
    for f in SCRIPTS.glob("*.py"):
        if f.name in ("verify_parent_link.py",) or (f.name == "compose_subissue_title.py" and not with_helper):
            continue
        shutil.copy(f, proj / ".claude" / "scripts" / f.name)
    for f in (REPO / ".claude" / "hooks").glob("*.py"):
        shutil.copy(f, proj / ".claude" / "hooks" / f.name)
    shutil.copy(SHIPPED_CONVENTIONS, proj / ".claude" / "work-item-conventions.json")
    bindir = root / "bin"
    bindir.mkdir()
    (bindir / "rec.py").write_text(RECORDER, encoding="utf-8")
    (bindir / "gh").write_text('#!/bin/sh\nexec "%s" "%s" gh "$@"\n' % (posix(sys.executable), posix(bindir / "rec.py")),
                               encoding="utf-8", newline="\n")
    (bindir / "py").write_text('#!/bin/sh\n[ "$1" = "-3" ] && shift\nexec "%s" "$@"\n' % posix(sys.executable),
                               encoding="utf-8", newline="\n")
    (proj / ".claude" / "scripts" / "verify_parent_link.py").write_text(
        "import sys\nsys.argv = [sys.argv[0], 'verify'] + sys.argv[1:]\n"
        "exec(compile(open(%r, encoding='utf-8').read(), 'rec.py', 'exec'))\n" % str(bindir / "rec.py"),
        encoding="utf-8")
    return proj, bindir


def fill(block: str, title: str) -> str:
    def sub_one(m: re.Match) -> str:
        inner = m.group(0)[1:-1].lower()
        if "bare" in inner:
            return title
        if "sub_task" in inner or "supplied" in inner:
            return BODY_TEXT
        if "parent" in inner:
            return "638"
        if inner in ("type", "effort") or "effort" in inner:
            return "PERF"
        if inner in ("k", "ordinal") or "ordinal" in inner:
            return "16"
        if inner == "sub":
            return "99"
        return "X"
    return PLACEHOLDER.sub(sub_one, block)


def replay(bash: str, block: str, title: str, root: Path, with_helper: bool = True):
    proj, bindir = build_project(root, with_helper)
    rec = root / "rec.jsonl"
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env.update({
        "CLAUDE_PROJECT_DIR": posix(proj), "CLAUDE_CONFIG_DIR": posix(root / "cfg"), "HOME": posix(root / "home"),
        "USERPROFILE": str(root / "home"), "STUB_REC": str(rec),
        "PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8",
    })
    for v in ("VPL", "CST", "TITLE", "BARE", "OUT"):
        env.pop(v, None)
    (root / "cfg").mkdir(exist_ok=True)
    (root / "home").mkdir(exist_ok=True)
    script = "cd '%s'\n%s\n" % (posix(proj), fill(block, title))
    cp = subprocess.run([bash, "--noprofile", "--norc", "-c", script], env=env, capture_output=True,
                        stdin=subprocess.DEVNULL, timeout=180)
    calls = []
    if rec.is_file():
        calls = [json.loads(x) for x in rec.read_text(encoding="utf-8").splitlines() if x.strip()]
    return cp, calls


def title_arg(argv: list[str]) -> str | None:
    for i, a in enumerate(argv):
        if a == "--title" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--title="):
            return a.split("=", 1)[1]
    return None


all_blocks = fenced_blocks(prose)
compose_blocks = [b for b in all_blocks if "compose_subissue_title.py" in b]
create_blocks = [b for b in all_blocks if "gh issue create" in b]
one_block = next((b for b in all_blocks if "compose_subissue_title.py" in b and "gh issue create" in b), None)

check("replay: ONE fenced bash block both composes the title and creates the issue",
      one_block is not None,
      "compose and `gh issue create` live in different fenced blocks (RED until the skill block is rewritten)")

union = "\n".join(compose_blocks[:1] + create_blocks[:1]) if one_block is None else one_block
unq = unquoted_placeholders(union) if union.strip() else ["<no block>"]
check("replay: every <PLACEHOLDER> on a shell line of the block sits inside double quotes", unq == [],
      f"unquoted: {sorted(set(unq))}")

if one_block is not None:
    check("replay: the block itself locates verify_parent_link.py", "verify_parent_link.py" in one_block,
          "no lookup of the verifier inside the block")
    check("replay: the block itself locates compose_subissue_title.py", "compose_subissue_title.py" in one_block,
          "helper not located inside the block")
    check("replay: the block names a HALT message", "HALT" in one_block, "no named HALT message")
    check("replay: the issue body goes through --body-file, never --body \"...text\"",
          "--body-file" in one_block and not re.search(r"--body(?![-\w])", one_block),
          "block passes --body inline")
else:
    for name in ("the block itself locates verify_parent_link.py", "the block itself locates compose_subissue_title.py",
                 "the block names a HALT message", "the issue body goes through --body-file, never --body \"...text\""):
        check(f"replay: {name}", False, "no single self-contained block to inspect")

bash = find_bash()
if bash is None:
    check("replay: bash genuinely absent -- shell replay skipped", True)
    print("      (skip: Git Bash not found; the static replay checks above still ran)")
elif one_block is None:
    for label in REPLAY_TITLES:
        check(f"replay[{slug(label)}]: recorded --title is the byte-exact composed title", False,
              "no single block to run")
    check("replay: HALT when the helper is missing", False, "no single block to run")
else:
    for label, bare in REPLAY_TITLES.items():
        with tempfile.TemporaryDirectory() as rtd:
            cp, calls = replay(bash, one_block, bare, Path(rtd))
            creates = [c for c in calls if c["tool"] == "gh" and c["argv"][:2] == ["issue", "create"]]
            expected_title = f"[PERF] P:#638 ST:16 - {bare}"
            got = title_arg(creates[0]["argv"]) if creates else None
            tag = slug(label)
            check(f"replay[{tag}]: block exited 0 and issued exactly one gh issue create",
                  cp.returncode == 0 and len(creates) == 1,
                  f"rc={cp.returncode} creates={len(creates)} stderr={cp.stderr.decode('utf-8', 'replace').strip()[-200:]!r}")
            check(f"replay[{tag}]: recorded --title is the byte-exact UTF-8 composed title",
                  got is not None and got.encode("utf-8") == expected_title.encode("utf-8"),
                  f"expected {expected_title!r}, got {got!r}")
            check(f"replay[{tag}]: no trailing CR on the title", got is not None and not got.endswith("\r"),
                  f"got {got!r}")
            if creates:
                argv = creates[0]["argv"]
                check(f"replay[{tag}]: body reaches gh via --body-file, not --body",
                      any(a == "--body-file" or a.startswith("--body-file=") for a in argv)
                      and not any(a == "--body" or a.startswith("--body=") for a in argv),
                      f"argv={argv!r}")
                check(f"replay[{tag}]: body file holds the supplied SUB_TASK text verbatim",
                      isinstance(creates[0]["body"], str) and creates[0]["body"].strip() == BODY_TEXT.strip(),
                      f"body={creates[0]['body']!r}")
            else:
                check(f"replay[{tag}]: body reaches gh via --body-file, not --body", False, "no gh issue create call")

    with tempfile.TemporaryDirectory() as rtd:
        cp, calls = replay(bash, one_block, "Fix X", Path(rtd), with_helper=False)
        said = (cp.stdout + cp.stderr).decode("utf-8", "replace")
        check("replay: helper missing -> named HALT message naming the helper, nonzero exit, nothing created",
              cp.returncode != 0 and "HALT" in said and "compose_subissue_title.py" in said
              and not [c for c in calls if c["tool"] == "gh"],
              f"rc={cp.returncode} said={said.strip()[-200:]!r} gh_calls={len([c for c in calls if c['tool'] == 'gh'])}")

# ------------------------------------------------- second implementation review (RED cases)

STRICT_VERIFIER = textwrap.dedent('''\
    import argparse, re, sys

    def strict_int(s):
        if not re.fullmatch(r"[0-9]+", s):
            raise argparse.ArgumentTypeError("invalid int value: %r" % s)
        return int(s)

    ap = argparse.ArgumentParser(prog="verify_parent_link.py")
    ap.add_argument("--sub", type=strict_int)
    ap.add_argument("--parent", type=strict_int)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--repair-attempted", action="store_true")
    ap.parse_args()
    sys.argv = [sys.argv[0], "verify"] + sys.argv[1:]
    exec(compile(open(REC_PATH, encoding="utf-8").read(), "rec.py", "exec"))
''')

GH_STUB = '#!/bin/sh\nPY="%s"\nREC="%s"\ncase "$GH_MODE" in\n' \
          '  garbage) "$PY" "$REC" gh "$@" >/dev/null; echo "warning: something"; exit 0;;\n' \
          '  fail) "$PY" "$REC" gh "$@" >/dev/null; echo "gh: boom" >&2; exit 1;;\n' \
          '  *) exec "$PY" "$REC" gh "$@";;\nesac\n'


def fill_x(block: str, title: str, parent: str = "638", body: str = BODY_TEXT) -> str:
    def sub_one(m: re.Match) -> str:
        inner = m.group(0)[1:-1].lower()
        if "bare" in inner:
            return title
        if "sub_task" in inner or "supplied" in inner:
            return body
        if "parent" in inner:
            return parent
        if "effort" in inner or inner == "type":
            return "PERF"
        if inner in ("k", "ordinal") or "ordinal" in inner:
            return "16"
        if inner.startswith("sub"):
            return "99"
        return "X"
    return PLACEHOLDER.sub(sub_one, block)


def replay_x(bash: str, block: str, title: str, root: Path, parent: str = "638", body: str = BODY_TEXT,
             gh_mode: str = "ok", helper_src: str | None = None):
    """Like replay(), but with a strict (argparse-int) verifier stub, a mode-switchable gh stub and an optional helper shim."""
    proj, bindir = build_project(root, True)
    rec = root / "rec.jsonl"
    (proj / ".claude" / "scripts" / "verify_parent_link.py").write_text(
        "REC_PATH = %r\n" % str(bindir / "rec.py") + STRICT_VERIFIER, encoding="utf-8")
    (bindir / "gh").write_text(GH_STUB % (posix(sys.executable), posix(bindir / "rec.py")),
                               encoding="utf-8", newline="\n")
    if helper_src is not None:
        (proj / ".claude" / "scripts" / "compose_subissue_title.py").write_text(helper_src, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env.update({
        "CLAUDE_PROJECT_DIR": posix(proj), "CLAUDE_CONFIG_DIR": posix(root / "cfg"), "HOME": posix(root / "home"),
        "USERPROFILE": str(root / "home"), "STUB_REC": str(rec), "GH_MODE": gh_mode,
        "PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8",
    })
    for v in ("VPL", "CST", "TITLE", "BARE", "OUT", "SUB", "URL"):
        env.pop(v, None)
    (root / "cfg").mkdir(exist_ok=True)
    (root / "home").mkdir(exist_ok=True)
    script = "cd '%s'\n%s\n" % (posix(proj), fill_x(block, title, parent, body))
    cp = subprocess.run([bash, "--noprofile", "--norc", "-c", script], env=env, capture_output=True,
                        stdin=subprocess.DEVNULL, timeout=180)
    calls = []
    if rec.is_file():
        calls = [json.loads(x) for x in rec.read_text(encoding="utf-8").splitlines() if x.strip()]
    return cp, calls


def argval(argv: list[str], flag: str) -> str | None:
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def verifier_calls(calls: list[dict]) -> list[dict]:
    return [c for c in calls if c["tool"] == "verify" and "--sub" in c["argv"]]


def said_of(cp) -> str:
    return (cp.stdout + cp.stderr).decode("utf-8", "replace")


# --- B1: the parent placeholder may be filled as '#638' or ' 638 '; gh and the verifier get digits only
for label, pv in (("hash", "#638"), ("spaces", " 638 ")):
    n = f"B1[{label}]"
    if bash is None or one_block is None:
        for what in ("block exits 0", "gh issue create gets --parent 638 (digits only)",
                     "verifier gets --parent 638 and --sub 99 (digits only)"):
            check(f"{n}: {what}", bash is None, "no single block or no bash to replay")
        continue
    with tempfile.TemporaryDirectory() as rtd:
        cp, calls = replay_x(bash, one_block, "Fix X", Path(rtd), parent=pv)
        creates = [c for c in calls if c["tool"] == "gh" and c["argv"][:2] == ["issue", "create"]]
        vcs = verifier_calls(calls)
        check(f"{n}: block exits 0", cp.returncode == 0,
              f"rc={cp.returncode} said={said_of(cp).strip()[-240:]!r}")
        check(f"{n}: gh issue create gets --parent 638 (digits only)",
              len(creates) == 1 and argval(creates[0]["argv"], "--parent") == "638",
              f"create argv={[c['argv'] for c in creates]!r}")
        check(f"{n}: verifier gets --parent 638 and --sub 99 (digits only)",
              len(vcs) == 1 and argval(vcs[0]["argv"], "--parent") == "638" and argval(vcs[0]["argv"], "--sub") == "99",
              f"verifier argv={[c['argv'] for c in vcs]!r}")

# --- W1: CREATED line before the verifier; separate repair block
if bash is None or one_block is None:
    check("W1: block prints 'CREATED: #<n> <url>' before the verifier runs", bash is None, "no block or no bash")
else:
    with tempfile.TemporaryDirectory() as rtd:
        cp, calls = replay_x(bash, one_block, "Fix X", Path(rtd))
        out_text = cp.stdout.decode("utf-8", "replace")
        url99 = "https://github.com/o/r/issues/99"
        line_idx = next((i for i, ln in enumerate(out_text.splitlines())
                         if re.search(r"CREATED.*#99.*" + re.escape(url99), ln)), None)
        verdict_idx = next((i for i, ln in enumerate(out_text.splitlines()) if '"verdict"' in ln), None)
        check("W1: block prints 'CREATED: #<n> <url>' before the verifier runs",
              line_idx is not None and verdict_idx is not None and line_idx < verdict_idx,
              f"created_line_idx={line_idx} verdict_idx={verdict_idx} stdout={out_text.strip()[-240:]!r}")

repair_block = all_blocks[1] if len(all_blocks) >= 2 else None
NOREP = "no second bash block (the separate repair block) in parent-aware-mode.md"
check("W1: a SEPARATE repair fenced block exists (second bash block)", repair_block is not None, NOREP)
if repair_block is not None:
    check("W1: repair block contains no `gh issue create`", "gh issue create" not in repair_block,
          "the repair block could create a duplicate sub-issue")
    check("W1: repair block runs `gh issue edit` with --parent",
          bool(re.search(r"gh issue edit\b[^\n]*--parent", repair_block)), "no `gh issue edit ... --parent` line")
    check("W1: repair block runs the verifier with --repair-attempted", "--repair-attempted" in repair_block,
          "no --repair-attempted")
    first_run = None
    for ln in repair_block.splitlines():
        m = re.match(r'^\s*py\s+-3\s+"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?"', ln)
        if m:
            first_run = m.group(1)
            break
    check("W1: repair block's first `py -3 \"$VAR\"` line runs VPL (the lookup cut rule)", first_run == "VPL",
          f"first run line variable={first_run!r}")
else:
    for what in ("repair block contains no `gh issue create`", "repair block runs `gh issue edit` with --parent",
                 "repair block runs the verifier with --repair-attempted",
                 "repair block's first `py -3 \"$VAR\"` line runs VPL (the lookup cut rule)"):
        check(f"W1: {what}", False, NOREP)
m_never = re.search(r"never\s+(?:be\s+)?re-?run", prose, re.I)
check("W1: prose says the create block must never be re-run",
      bool(m_never) and "create" in prose[max(0, m_never.start() - 200):m_never.end() + 200].lower(),
      "no 'never ... re-run' sentence about the create block")
if bash is None or repair_block is None:
    check("W1: repair block replay -> gh issue edit 99 --parent 638, then verifier --sub 99 --parent 638 --repair-attempted",
          bash is None, NOREP)
else:
    with tempfile.TemporaryDirectory() as rtd:
        cp, calls = replay_x(bash, repair_block, "Fix X", Path(rtd))
        edits = [c for c in calls if c["tool"] == "gh" and c["argv"][:2] == ["issue", "edit"]]
        vcs = verifier_calls(calls)
        ok = (len(edits) == 1 and edits[0]["argv"][2:3] == ["99"] and argval(edits[0]["argv"], "--parent") == "638"
              and len(vcs) == 1 and argval(vcs[0]["argv"], "--sub") == "99"
              and argval(vcs[0]["argv"], "--parent") == "638" and "--repair-attempted" in vcs[0]["argv"]
              and not [c for c in calls if c["tool"] == "gh" and c["argv"][:2] == ["issue", "create"]])
        check("W1: repair block replay -> gh issue edit 99 --parent 638, then verifier --sub 99 --parent 638 --repair-attempted",
              ok, f"rc={cp.returncode} edits={[c['argv'] for c in edits]!r} verifier={[c['argv'] for c in vcs]!r} "
                  f"said={said_of(cp).strip()[-160:]!r}")

# --- W2: gh output that is not an issue URL, or gh failing, halts before the verifier
for label, mode in (("non-URL output with exit 0", "garbage"), ("non-zero exit", "fail")):
    n = f"W2[{mode}]"
    if bash is None or one_block is None:
        check(f"{n}: HALT named, nonzero exit, verifier not called ({label})", bash is None, "no block or no bash")
        continue
    with tempfile.TemporaryDirectory() as rtd:
        cp, calls = replay_x(bash, one_block, "Fix X", Path(rtd), gh_mode=mode)
        said = said_of(cp)
        check(f"{n}: HALT named, nonzero exit, verifier not called ({label})",
              "HALT" in said and cp.returncode != 0 and not verifier_calls(calls),
              f"rc={cp.returncode} verifier_calls={len(verifier_calls(calls))} said={said.strip()[-200:]!r}")

# --- W4: helper robustness (numeric extremes, usage error, crashed helper)
with tempfile.TemporaryDirectory() as td4:
    conv4 = write_conv(Path(td4), conventions())
    huge = "9" * 5000
    for what, kw, cause in (("parent of 5000 digits", {"parent": huge}, "parent-not-positive-integer"),
                            ("sub-task ordinal of 5000 digits", {"subtask": huge}, "subtask-not-positive-integer"),
                            ("parent of 19 digits", {"parent": "9" * 19}, "parent-not-positive-integer"),
                            ("sub-task ordinal of 19 digits", {"subtask": "9" * 19}, "subtask-not-positive-integer")):
        proc = compose(conv4, **kw)
        expect_refused(f"W4: {what}", proc, cause)
        check(f"W4: {what}: no Python traceback", "Traceback" not in proc.stderr, proc.stderr.strip()[-160:])
    nines = "9" * 18
    expect_composed("W4: parent of 18 digits", compose(conv4, parent=nines), f"[PERF] P:#{nines} ST:16 - {BARE}")
    expect_composed("W4: sub-task ordinal of 18 digits", compose(conv4, subtask=nines),
                    f"[PERF] P:#638 ST:{nines} - {BARE}")
    usage = run(["--type", "PERF", "--parent", "638", "--subtask", "16", "--title"])
    check("W4: --title as the last argument exits 2 with no JSON on stdout",
          usage.returncode == 2 and parse(usage) is None, f"rc={usage.returncode} stdout={usage.stdout.strip()[:80]!r}")

for label, src in (("exit 2, no stdout", "import sys\nsys.exit(2)\n"),
                   ("exit 2, usage text on stdout", "import sys\nprint('usage: compose [-h]')\nsys.exit(2)\n")):
    n = f"W4[crashed helper: {label}]"
    if bash is None or one_block is None:
        check(f"{n}: HALT says 'helper failed' with 'rc=', not 'refused'; nothing created", bash is None,
              "no block or no bash")
        continue
    with tempfile.TemporaryDirectory() as rtd:
        cp, calls = replay_x(bash, one_block, "Fix X", Path(rtd), helper_src=src)
        said = said_of(cp)
        check(f"{n}: HALT says 'helper failed' with 'rc=', not 'refused'; nothing created",
              "HALT" in said and "helper failed" in said and "rc=" in said and "refused" not in said
              and cp.returncode != 0 and not [c for c in calls if c["tool"] == "gh"],
              f"rc={cp.returncode} said={said.strip()[-200:]!r}")

# --- N5: the SUB_TASK here-document delimiter is guarded. A shell replay cannot show this: the fill is
# textual, so the shell parser ends the here-document at the colliding line before any block code runs.
# The guard is therefore an instruction in the prose, checked as text.
prose_outside = re.sub(r"```.*?```", "", prose, flags=re.S)
guard = [p for p in re.split(r"\n\s*\n", prose_outside)
         if "SUB_TASK_END" in p and re.search(r"\bline\b", p, re.I) and re.search(r"equal|exactly|identical|alone", p, re.I)]
check("N5: prose instructs checking that no SUB_TASK body line equals the delimiter SUB_TASK_END",
      bool(guard), "no paragraph outside the code block names SUB_TASK_END with a line-equality check")

# --- N4 / N1 / N2
with tempfile.TemporaryDirectory() as td7:
    bom = Path(td7) / "bom.json"
    bom.write_bytes(b"\xef\xbb\xbf" + json.dumps(conventions()).encode("utf-8"))
    expect_composed("N4: conventions file saved with a UTF-8 BOM", compose(bom), EXPECTED)
    good7 = write_conv(Path(td7), conventions())
    for label, ch in (("U+202E bidi override", "‮"), ("U+200B zero-width space", "​")):
        expect_refused(f"N2: bare title with {label}", compose(good7, title=f"Fix{ch}Index"), "bare-title-invalid")
src_text = SUBJECT.read_text(encoding="utf-8") if SUBJECT.is_file() else ""
check("N1: helper holds no dead sys.path.insert for _claude_paths", "sys.path.insert" not in src_text,
      "compose_subissue_title.py still calls sys.path.insert")

# ----------------------------------------------------------------- summary

print()
print(f"{PASSED + len(FAILURES)} checks: {PASSED} passed, {len(FAILURES)} failed")
if FAILURES:
    print("FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("ALL PASS")
