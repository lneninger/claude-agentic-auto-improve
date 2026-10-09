#!/usr/bin/env python3
"""
test_worktree_path_guards.py -- RED suite for issue 222 (worktree source is
judged like main-checkout source by every path guard).

WHAT THIS PINS DOWN
--------------------
Four PreToolUse guards -- concept-gate.py, bash-gate.py,
codegraph-first-guard.py and db-destructive-guard.py -- unconditionally
bypass ANY path containing "/.claude/" (case- and separator-insensitive).
`/task` places every worktree at ``<repo>/.claude/worktrees/<name>/``, so
every path inside a worktree contains that substring and every one of these
guards is off for all worktree work today.

This contract closes that hole with one shared rule in
``_project_paths.py``: strip every "worktree segment"
(``.claude/worktrees/<name>/``) from a path before testing it against a
guard's bypass list. A worktree's OWN ``.claude/`` configuration stays
allowed, because stripping the worktree segment turns it back into a plain
``.claude/`` file. See
``.claude/concepts/2026-09-28-222-guards-off-inside-worktrees.md``
(Data Shapes, INV-1..INV-10; Uncertain Assumptions A1..A8; Failure Modes)
for the full contract this suite is written against.

Every case below launches the REAL, on-disk hook file as a subprocess (never
imported, never stubbed -- A6). Every path is built under a fresh
``tempfile.mkdtemp()`` tree; the real repository and the real home directory
are read-only leaks guarded against with fresh ``uuid4()`` tokens and, for
the fallback cases, a redirected ``HOME``/``USERPROFILE`` (see
``snapshot_real_home_logs`` and the check in ``main()``).

EVIDENCE RULE (INV-9): a BLOCK passes only on exit 2 AND the guard's own
banner in stderr. An ALLOW passes only on exit 0 AND a positive proof of
real work: for the three PreToolUse gates, no "internal error" in stderr
PLUS a BLOCK sibling launch (same hook copy/env/cwd, a fresh main-checkout
target) that blocks in the same run. For the database guard: no new
"db-destructive-guard" line in errors.jsonl, no bytes added to db-guard.log,
PLUS a BLOCK sibling that adds exactly one BLOCK record (judged by byte
offset). Exit codes alone prove nothing -- Python exits 2 on a missing
script, and the database guard exits 0 with empty stderr when it crashes.

This is the GENERIC half of sub-task 1 (synced to the plugin -- no project
names). The local half, which drives sentinel-detector.py (a fifth,
warn-only copy of the same bypass, A7), lives in
test_sentinel_detector_worktree.py.

Run:
    py -3 .claude/hooks/tests/test_worktree_path_guards.py

Exit code:
    0 = every check passed
    1 = at least one check failed (expected while this suite is RED --
        every case marked FAILS TODAY below is failing on an assertion,
        never a crash or an import error)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

HOOKS_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = HOOKS_DIR.parent / "scripts"

# The module under test for the helper-function cases (INV-4, INV-8). This
# import is the ONE exception to "never import a guard as a module" -- it is
# not a guard, it is the shared pure-function resolver the guards will call
# into. Every guard itself is still launched as a real subprocess below.
sys.path.insert(0, str(HOOKS_DIR))
import _project_paths as pp  # noqa: E402

# The shared "Files to touch" parser -- imported ONLY so this suite can
# assert its own fixture contracts actually parse (see
# assert_contract_fixture below). Never used to decide a guard's verdict --
# that decision still comes exclusively from launching the real hook.
sys.path.insert(0, str(SCRIPTS_DIR))
from _contract_files import (  # noqa: E402
    extract_files_from_contract as _extract_files_from_contract,
    matches_path as _contract_matches_path,
)

BANNERS = {
    "concept-gate": "[concept-gate] BLOCKED",
    "bash-gate": "[bash-gate] BLOCKED",
    "codegraph-first-guard": "[codegraph-first-guard] BLOCKED",
    "db-destructive-guard": "[db-destructive-guard] BLOCKED:",
}
PROTECTED_WRITE_TEXT = "writes to a PROTECTED dev database"

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, bool(ok), detail))
    tag = "PASS" if ok else "FAIL"
    print(f"  {tag}  {name}")
    if not ok and detail:
        for line in detail.splitlines():
            print(f"        {line}")


def _decode(raw) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw or ""


def fs(p) -> str:
    """Forward-slash string form of a path, never touching the filesystem."""
    return str(p).replace("\\", "/")


#: Every token this run has minted, tracked so the real-home check (round 3,
#: task G) can tell "this run's own data" apart from unrelated growth in the
#: operator's real ~/.claude/logs/ -- a whole-file size/mtime equality check
#: flakes red the moment ANY other concurrent session appends a line there,
#: which has nothing to do with whether THIS suite leaked into it.
_ISSUED_TOKENS: list[str] = []


def tok() -> str:
    t = uuid.uuid4().hex[:10]
    _ISSUED_TOKENS.append(t)
    return t


# ---------------------------------------------------------------------------
# Rules-file-derived fixture values (never hardcoded -- read from the SAME
# file the hook reads, like test_db_destructive_guard.py). Fails loud, on
# purpose: a vacuous substitute would let the Layer-3c cases test nothing.
# ---------------------------------------------------------------------------
#
# PLUGIN PORT (contract 2026-09-28-hook-server-modes, amendment 2026-10-09, INV-O7 / INV-O3, sub-task 23).
# This is this repository's suite less the cases that launch bash-gate.py or codegraph-first-guard.py
# (both hooks are cut). The one other change: the project's rules are no longer the file beside the hook
# (the plugin ships a fictional template there). A FIXTURE PROJECT supplies this project's database
# names: the text below is written to <fixture project>/.claude/hooks/db-destructive-guard.rules.json
# for every project tree this suite builds, and to every hook copy that carries rules. It copies this
# project's rules and names ScalpingMachine and ScalpingMachine_Testing, as the contract requires.
_RULES_PATH = Path("<fixture project>/.claude/hooks/db-destructive-guard.rules.json")
_RULES = {
    "protected_databases": ["ScalpingMachine", "ScalpingMachine_Testing"],
    "production_path_allowlist": [
        "src/scalpingmachine.api/",
        "src/scalpingmachine.persistence/",
        "tools/db-protection/",
        ".claude/",
        "/.claude/",
        "docs/",
    ],
    "human_only_commands": [
        {"script": "tools/db-protection/update-dev-database.cmd"},
        {"script": "tools/db-protection/restore-latest.cmd", "flag": "--recover-missing-dev-db"},
    ],
}
RULES_NAME = "db-destructive-guard.rules.json"


def write_fixture_rules(directory: Path) -> None:
    """Write the fixture project's rules file into ``directory`` (a ``.claude/hooks`` folder)."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / RULES_NAME).write_text(json.dumps(_RULES), encoding="utf-8")


def copy_hook_file(name: str, dest_dir: Path) -> None:
    """Copy one hook-folder file beside a hook copy; the rules file comes from the fixture, never the plugin."""
    if name == RULES_NAME:
        write_fixture_rules(dest_dir)
    else:
        shutil.copy2(HOOKS_DIR / name, dest_dir / name)

_PROTECTED_DBS = [str(n) for n in (_RULES.get("protected_databases") or []) if str(n).strip()]
if not _PROTECTED_DBS:
    raise SystemExit(
        f"{_RULES_PATH} declares no protected_databases; the database-guard "
        "cases would test nothing. Refusing to run a vacuous suite."
    )
DB_PROT = _PROTECTED_DBS[0]

_SRC_ALLOWED = next(
    (str(p) for p in (_RULES.get("production_path_allowlist") or [])
     if str(p).strip().lower().startswith("src/")),
    None,
)
if _SRC_ALLOWED is None:
    raise SystemExit(
        f"{_RULES_PATH} declares no production_path_allowlist entry under "
        "src/; case D4 would test nothing. Refusing to run a vacuous suite."
    )

# Round 4 item 3 (security/code B1 -- aliased-".claude" join): the SECOND
# production_path_allowlist entry needed to build a two-component join
# reproduction, read from the same rules file so the generic suite never
# names this project literally.
_TOOLS_ALLOWED = next(
    (str(p) for p in (_RULES.get("production_path_allowlist") or [])
     if str(p).strip().lower().startswith("tools/")),
    None,
)
if _TOOLS_ALLOWED is None:
    raise SystemExit(
        f"{_RULES_PATH} declares no production_path_allowlist entry under "
        "tools/; the aliased-.claude join case would test nothing."
    )

# Built from parts so this source file does not contain the literal write
# keyword the guard itself scans for (same technique as
# test_db_destructive_guard.py).
_INSERT = "INS" + "ERT INTO"


def db_content(db_name: str) -> str:
    """A Layer-3c payload body: a protected-DB connection string paired with
    a write keyword, in the same tool input."""
    return (
        f'const string cs = "Server=(localdb)\\m;Database={db_name};'
        f'Trusted_Connection=True;";\n'
        f'await conn.ExecuteAsync("{_INSERT} Users (Id, Name) VALUES (1, \'x\')");'
    )


def db_doc_content(db_name: str) -> str:
    """A .claude/-style documentation body naming the protected DB and a
    write keyword, WITHOUT being a source-code write -- used for the
    allow-listed .claude/ ALLOW controls (D2/D3/D6/F2/F3)."""
    return (
        "Documentation example: a connection string like "
        f"`Database={db_name}` paired with `{_INSERT} Users` "
        "should be allowed inside concept contracts."
    )


# Round 3 task D: a Pass-A destructive-pattern payload (EnsureDeleted + a
# protected-DB drop), built from parts so THIS test file's own source does
# not carry the literal phrases db-destructive-guard.py itself scans for.
_ENSURE_DELETED = "Ensure" + "Deleted" + "Async"
_DROP_DATABASE = ("D" + "ROP") + " " + ("D" + "ATABASE")


def db_ensure_deleted_content(db_name: str) -> str:
    """Layer-3a-shaped payload: EF's ``EnsureDeletedAsync()`` alongside a
    literal drop of the protected database name -- the ORIGINAL
    destructive-pattern scan this hook existed for, unrelated to issue 222's
    worktree fix. Used to show the stale-helper crash (task D) breaks even
    this pre-existing protection, not just the new worktree behaviour."""
    return (
        f"await context.{_ENSURE_DELETED}();\n"
        f'// probe: sqlcmd -Q "{_DROP_DATABASE} [{db_name}]"'
    )


# ---------------------------------------------------------------------------
# Fixture tree.
#
#   <tmp>/repo/                          CLAUDE.md, .git, .claude/{logs,concepts,hooks}, src/
#   <tmp>/repo/.claude/worktrees/<wt>/   CLAUDE.md, .git, .claude/{logs,concepts,hooks}, src/
#   <tmp>/home/                          .claude/logs/  (redirected HOME/USERPROFILE target)
#   <tmp>/isolated/hooks/                fallback-mode copies (no _project_paths.py)
# ---------------------------------------------------------------------------
def make_tree() -> dict:
    root = Path(tempfile.mkdtemp(prefix="wtguard-"))
    repo = root / "repo"
    (repo / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "concepts").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "CLAUDE.md").write_text("# repo\n", encoding="utf-8")
    (repo / ".git").write_text("gitdir: ../.git/worktrees/dummy\n", encoding="utf-8")

    wt_name = f"wt-{tok()}"
    wt = repo / ".claude" / "worktrees" / wt_name
    (wt / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    (wt / ".claude" / "concepts").mkdir(parents=True, exist_ok=True)
    (wt / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    (wt / "src").mkdir(parents=True, exist_ok=True)
    (wt / "CLAUDE.md").write_text("# worktree\n", encoding="utf-8")
    (wt / ".git").write_text(f"gitdir: {fs(repo)}/.git/worktrees/{wt_name}\n", encoding="utf-8")

    # Second worktree -- round 3 task A (INV-7 negative twins): a search
    # that scans "every worktree's concepts for every target" instead of
    # only the ENCLOSING worktree's own would stay green against a single
    # worktree fixture, because there is nothing else for it to wrongly
    # find. wt2 gives it something wrong to find.
    wt2_name = f"wt-{tok()}"
    wt2 = repo / ".claude" / "worktrees" / wt2_name
    (wt2 / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    (wt2 / ".claude" / "concepts").mkdir(parents=True, exist_ok=True)
    (wt2 / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    (wt2 / "src").mkdir(parents=True, exist_ok=True)
    (wt2 / "CLAUDE.md").write_text("# worktree 2\n", encoding="utf-8")
    (wt2 / ".git").write_text(f"gitdir: {fs(repo)}/.git/worktrees/{wt2_name}\n", encoding="utf-8")

    # PLUGIN PORT: every project tree carries the fixture project's rules (INV-O3).
    for project_tree in (repo, wt, wt2):
        write_fixture_rules(project_tree / ".claude" / "hooks")

    home = root / "home"
    (home / ".claude" / "logs").mkdir(parents=True, exist_ok=True)

    isolated = root / "isolated" / "hooks"
    isolated.mkdir(parents=True, exist_ok=True)

    stale = root / "stale" / "hooks"
    stale.mkdir(parents=True, exist_ok=True)

    return {
        "root": root, "repo": repo, "wt": wt, "wt_name": wt_name,
        "wt2": wt2, "wt2_name": wt2_name,
        "home": home, "isolated": isolated, "stale": stale,
    }


def base_env(project_dir: Path) -> dict:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    for key in ("CLAUDE_CONCEPT_GATE", "CLAUDE_BASH_GATE", "CLAUDE_SKIP_CG", "CLAUDE_DESTRUCTIVE_DB_OK"):
        env.pop(key, None)
    return env


def fallback_env(project_dir: Path, home: Path) -> dict:
    env = base_env(project_dir)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    return env


def run_hook(hook_path: Path, payload: dict, cwd: Path, env: dict, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["py", "-3", str(hook_path)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True, cwd=str(cwd), env=env, timeout=timeout,
    )


def write_contract(concepts_dir: Path, name: str, files_to_touch: list[str], status: str = "approved") -> Path:
    concepts_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Concept Contract -- probe {name}",
        "",
        f"**Status:** {status}",
        "",
        # NOT "## Files to touch": _contract_files.py:76 splits on
        # r"(?im)^\*?\*?files to touch:?\*?\*?\s*$", which accepts a leading
        # run of "*" (bold markers) but not a leading "#" (a markdown
        # heading). Real contracts and the template use the bold-run form.
        # A "## " heading here parses as zero "Files to touch" entries --
        # a fixture that silently tests nothing.
        "**Files to touch:**",
        "",
    ]
    for f in files_to_touch:
        lines.append(f"- `{f}`")
    lines.append("")
    path = concepts_dir / f"{name}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def assert_contract_fixture(label: str, contract_path: Path, target: str) -> None:
    """Guard against the class of bug the heading mistake above was: a
    contract-covered ALLOW control must not be able to pass because the
    contract fixture silently parsed to an empty (or non-covering) list.
    Uses the SAME parser the guards themselves import
    (.claude/scripts/_contract_files.py), never a private re-implementation,
    so this check can never disagree with what the hooks actually see."""
    entries = _extract_files_from_contract(contract_path)
    target_norm = target.replace("\\", "/").lower()
    covers = any(_contract_matches_path(e, target_norm) for e in entries)
    ok = bool(entries) and covers
    detail = (
        f"contract={contract_path}\n"
        f"extract_files_from_contract() -> {entries!r}\n"
        f"target={target_norm!r} covers={covers}"
    )
    check(f"{label}: probe contract parses to a non-empty list covering the target", ok, detail)


def make_situation_c_copy(repo: Path, guard_filename: str, include_rules: bool = False) -> Path:
    """Copy ``guard_filename`` + ``_project_paths.py`` + ``_error_log.py``
    (+ the rules file, for the database guard) into ``<repo>/.claude/hooks/``,
    and the real ``.claude/scripts/_contract_files.py`` into
    ``<repo>/.claude/scripts/``. Returns the copy's path. This is the
    "situation c" hook copy the contract defines: CLAUDE_PROJECT_DIR = the
    main checkout, cwd = the worktree (or a subfolder of it), hook copy at
    the main checkout's own .claude/hooks/ -- the combination Uncertain
    Assumptions observed live.
    """
    dest_hooks = repo / ".claude" / "hooks"
    dest_hooks.mkdir(parents=True, exist_ok=True)
    names = [guard_filename, "_project_paths.py", "_error_log.py"]
    if include_rules:
        names.append("db-destructive-guard.rules.json")
    for name in names:
        copy_hook_file(name, dest_hooks)
    dest_scripts = repo / ".claude" / "scripts"
    dest_scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPTS_DIR / "_contract_files.py", dest_scripts / "_contract_files.py")
    return dest_hooks / guard_filename


def make_isolated_copy(isolated_dir: Path, guard_filename: str, include_rules: bool = False) -> Path:
    """Copy ONLY ``guard_filename`` + ``_error_log.py`` (+ the rules file for
    the database guard) into ``isolated_dir`` -- deliberately WITHOUT
    ``_project_paths.py`` beside it, so ``import _project_paths`` fails and
    the hook enters fallback mode (INV-5)."""
    names = [guard_filename, "_error_log.py"]
    if include_rules:
        names.append("db-destructive-guard.rules.json")
    for name in names:
        copy_hook_file(name, isolated_dir)
    return isolated_dir / guard_filename


# ---------------------------------------------------------------------------
# Round 3 task D: a STALE _project_paths.py -- imports cleanly (so every
# guard's fail-soft `except Exception: _pp = None` does NOT fire) but
# predates sub-task 2's two new functions. Every one of the five hooks calls
# them unconditionally whenever `_pp is not None` (`_segment_test_path`'s
# `if _pp is not None: return _pp.checkout_equivalent_path(...)`), with no
# `getattr` guard -- so a stale-but-present helper raises AttributeError
# instead of falling back to INV-5's fallback mode. This is code-review
# BLOCKER F1 / security BLOCKER W2.
# ---------------------------------------------------------------------------
_STALE_PROJECT_PATHS_SOURCE = '''"""Stale _project_paths.py stand-in (issue 222, round 3 task D).

Deliberately minimal: enough surface for the five hooks' OTHER calls
(concepts_roots, logs_dir) to keep working, but checkout_equivalent_path and
enclosing_worktree_root are INTENTIONALLY ABSENT -- this module stands in
for a checkout that has not picked up sub-task 2's helper additions yet.
"""
from __future__ import annotations
import os
from pathlib import Path

HOME = Path.home()
SELF_ROOT = Path(__file__).resolve().parent.parent


def project_dir():
    raw = os.environ.get("CLAUDE_PROJECT_DIR")
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except OSError:
        return Path(raw)


def claude_roots():
    roots = []

    def add(p):
        if p not in roots:
            roots.append(p)

    proj = project_dir()
    if proj is not None:
        add(proj / ".claude")
    add(SELF_ROOT)
    try:
        add(Path.cwd() / ".claude")
    except OSError:
        pass
    add(HOME / ".claude")
    return roots


def concepts_roots():
    return [r / "concepts" for r in claude_roots()]


def logs_dir():
    proj = project_dir()
    if proj is not None:
        return proj / ".claude" / "logs"
    return HOME / ".claude" / "logs"
'''


def make_stale_helper_copy(dest_dir: Path, guard_filename: str, include_rules: bool = False) -> Path:
    """Copy ``guard_filename`` + ``_error_log.py`` (+ the rules file for the
    database guard) into ``dest_dir``, alongside a STALE ``_project_paths.py``
    that imports cleanly but lacks ``checkout_equivalent_path`` /
    ``enclosing_worktree_root`` (round 3 task D)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    names = [guard_filename, "_error_log.py"]
    if include_rules:
        names.append("db-destructive-guard.rules.json")
    for name in names:
        copy_hook_file(name, dest_dir)
    (dest_dir / "_project_paths.py").write_text(_STALE_PROJECT_PATHS_SOURCE, encoding="utf-8")
    return dest_dir / guard_filename


# ---------------------------------------------------------------------------
# Round 3 task F: Windows alias spellings of the "worktrees" component that
# _worktree_segment_spans's exact (casefolded) component match does not
# recognise -- a trailing dot, an NTFS alternate-data-stream suffix, and a
# trailing space. Windows treats all three as naming the SAME directory as
# the plain spelling; the guard's segment/substring bypass test does not.
# ---------------------------------------------------------------------------
WORKTREES_ALIAS_DOT = "worktrees."
WORKTREES_ALIAS_ADS = "worktrees::$INDEX_ALLOCATION"
WORKTREES_ALIAS_SPACE = "worktrees "
WORKTREES_ALIASES = (WORKTREES_ALIAS_DOT, WORKTREES_ALIAS_ADS, WORKTREES_ALIAS_SPACE)


def snapshot_real_home_logs() -> dict:
    """Byte OFFSET of each real-home log file before this run (round 3 task
    G). NOT a whole-file size/mtime snapshot: the operator's real
    ~/.claude/logs/ is shared with every other session on the machine, so an
    unrelated concurrent write there would flip a size/mtime equality check
    red for a reason that has nothing to do with this suite. The offset
    lets :func:`assert_real_home_untouched` read only the bytes THIS run
    could have caused."""
    real_home = Path(os.path.expanduser("~"))
    out = {}
    for rel in ("db-guard.log", "errors.jsonl"):
        p = real_home / ".claude" / "logs" / rel
        try:
            out[rel] = (p, p.stat().st_size)
        except OSError:
            out[rel] = (p, 0)
    return out


def assert_real_home_untouched(before: dict, run_tokens: list[str], temp_root_prefix: str) -> tuple[bool, str]:
    """After the run, whatever bytes were APPENDED to a real-home log file
    must not mention this run's temp-root prefix or any token it minted.
    Unrelated growth (another session logging its own, unrelated block) is
    explicitly NOT a failure -- only OUR data leaking into the real home is.
    This is the content-based replacement for the old whole-file
    size/mtime-equality check, which flaked whenever a parallel session
    wrote to the same file during this run for an unrelated reason."""
    problems: list[str] = []
    for rel, (p, before_size) in before.items():
        try:
            with p.open("rb") as f:
                f.seek(before_size)
                new_bytes = f.read()
        except OSError:
            continue
        if not new_bytes:
            continue
        new_text = new_bytes.decode("utf-8", "replace")
        hits: list[str] = []
        if temp_root_prefix and temp_root_prefix in new_text:
            hits.append("this run's temp-root prefix")
        for t in run_tokens:
            if t and t in new_text:
                hits.append(f"probe token {t!r}")
                break  # one token hit is enough to name the file as a problem
        if hits:
            problems.append(f"{p}: new bytes mention {hits} -- {new_text[:300]!r}")
    ok = not problems
    detail = "\n".join(problems) if problems else (
        "no bytes appended to the real home logs during this run mention "
        "this run's temp-root prefix or any of its probe tokens"
    )
    return ok, detail


# ---------------------------------------------------------------------------
# Proof helpers (INV-9).
# ---------------------------------------------------------------------------
def assert_block(guard_key: str, proc: subprocess.CompletedProcess, extra_text: Optional[str] = None) -> tuple[bool, str]:
    stderr = _decode(proc.stderr)
    banner = BANNERS[guard_key]
    ok = proc.returncode == 2 and banner in stderr
    if extra_text is not None:
        ok = ok and extra_text in stderr
    detail = f"rc={proc.returncode} stderr={stderr[:500]!r}"
    return ok, detail


def assert_equivalence_block(
    guard_key: str,
    wt_proc: subprocess.CompletedProcess,
    main_proc: subprocess.CompletedProcess,
    extra_text: Optional[str] = None,
) -> tuple[bool, str]:
    """BOTH the worktree launch and its main-checkout counterpart must
    independently BLOCK with the guard's own banner -- two identical wrong
    verdicts (e.g. both ALLOW) cannot pass this."""
    wt_ok, wt_detail = assert_block(guard_key, wt_proc, extra_text)
    main_ok, main_detail = assert_block(guard_key, main_proc, extra_text)
    ok = wt_ok and main_ok
    detail = f"worktree: {wt_detail}\nmain-checkout: {main_detail}"
    return ok, detail


def run_gate_allow_case(
    guard_key: str,
    hook_path: Path,
    allow_payload: dict,
    sibling_payload: dict,
    cwd: Path,
    env: dict,
    pre_sibling: Optional[Callable[[], None]] = None,
) -> tuple[bool, str]:
    """Concept-gate / bash-gate / codegraph-first-guard ALLOW proof: exit 0,
    no 'internal error' in stderr, AND a BLOCK sibling (same hook copy, env,
    cwd; only the target differs) that BLOCKs with its own banner in the
    same run."""
    allow_proc = run_hook(hook_path, allow_payload, cwd, env)
    if pre_sibling is not None:
        pre_sibling()
    sibling_proc = run_hook(hook_path, sibling_payload, cwd, env)

    allow_stderr = _decode(allow_proc.stderr)
    sib_stderr = _decode(sibling_proc.stderr)
    banner = BANNERS[guard_key]

    ok = (
        allow_proc.returncode == 0
        and "internal error" not in allow_stderr
        and sibling_proc.returncode == 2
        and banner in sib_stderr
    )
    detail = (
        f"ALLOW launch: rc={allow_proc.returncode} stderr={allow_stderr[:400]!r}\n"
        f"BLOCK sibling: rc={sibling_proc.returncode} stderr={sib_stderr[:400]!r}"
    )
    return ok, detail


def _new_bytes(before: bytes, after: bytes) -> bytes:
    if len(after) >= len(before) and after[: len(before)] == before:
        return after[len(before):]
    # File was rotated/rewritten underneath us -- treat everything as new so
    # the check fails loud instead of silently passing.
    return after


def _read_bytes_safe(p: Path) -> bytes:
    try:
        return p.read_bytes()
    except OSError:
        return b""


def run_db_allow_case(
    hook_path: Path,
    allow_payload: dict,
    sibling_payload: dict,
    cwd: Path,
    env: dict,
    logs_dir: Path,
) -> tuple[bool, str]:
    """Database-guard ALLOW proof (INV-9): the ALLOW launch adds no new
    "db-destructive-guard" line to errors.jsonl and no bytes to db-guard.log
    (an allow-list ALLOW returns before _audit is reached). Its BLOCK
    sibling, same content on a fresh main-checkout target, must BLOCK with
    the Layer-3c text and add EXACTLY ONE new BLOCK record to db-guard.log,
    judged by byte offset before/after that one launch."""
    errors_path = logs_dir / "errors.jsonl"
    dbguard_path = logs_dir / "db-guard.log"

    before_errors = _read_bytes_safe(errors_path)
    before_dbguard = _read_bytes_safe(dbguard_path)

    allow_proc = run_hook(hook_path, allow_payload, cwd, env)

    after_errors = _read_bytes_safe(errors_path)
    after_dbguard = _read_bytes_safe(dbguard_path)

    new_error_bytes = _new_bytes(before_errors, after_errors)
    new_error_text = new_error_bytes.decode("utf-8", "replace")
    has_new_dbguard_error_line = False
    for line in new_error_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("hook") == "db-destructive-guard":
            has_new_dbguard_error_line = True

    dbguard_grew = len(after_dbguard) > len(before_dbguard)

    # -- BLOCK sibling, byte offset judged around ONLY this launch. --------
    before_sibling_dbguard = _read_bytes_safe(dbguard_path)
    sibling_proc = run_hook(hook_path, sibling_payload, cwd, env)
    after_sibling_dbguard = _read_bytes_safe(dbguard_path)

    sib_new_bytes = _new_bytes(before_sibling_dbguard, after_sibling_dbguard)
    sib_new_text = sib_new_bytes.decode("utf-8", "replace")
    sib_block_records = []
    for line in sib_new_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("decision") == "BLOCK":
            sib_block_records.append(rec)

    sib_stderr = _decode(sibling_proc.stderr)

    ok = (
        allow_proc.returncode == 0
        and not has_new_dbguard_error_line
        and not dbguard_grew
        and sibling_proc.returncode == 2
        and BANNERS["db-destructive-guard"] in sib_stderr
        and PROTECTED_WRITE_TEXT in sib_stderr
        and len(sib_block_records) == 1
    )
    detail = (
        f"ALLOW launch: rc={allow_proc.returncode}\n"
        f"  new errors.jsonl bytes with hook=db-destructive-guard: {has_new_dbguard_error_line}\n"
        f"  db-guard.log grew during ALLOW launch: {dbguard_grew}\n"
        f"BLOCK sibling: rc={sibling_proc.returncode} stderr={sib_stderr[:400]!r}\n"
        f"  new BLOCK records written by sibling: {len(sib_block_records)}"
    )
    return ok, detail


# ---------------------------------------------------------------------------
# Case runners.
# ---------------------------------------------------------------------------
@dataclass
class GateCase:
    id: str
    guard_key: str
    hook_path: Path
    payload: dict
    cwd: Path
    env: dict
    expect: str  # "block" | "allow"
    fails_today: bool
    extra_block_text: Optional[str] = None
    main_payload: Optional[dict] = None
    sibling_payload: Optional[dict] = None
    pre_sibling: Optional[Callable[[], None]] = None
    #: Run immediately before this case's own payload is launched -- NOT at
    #: case-construction time. Cases that share mutable fixture state (e.g.
    #: the CodeGraph sentinel file, which two different cases need present
    #: and two others need absent) must set this instead of calling the
    #: mutation inline while the case list is being built: every case in a
    #: `cases: list[...]` is constructed before ANY of them runs, so an
    #: inline call mutates shared state for every later case's construction
    #: too, not just its own execution.
    setup: Optional[Callable[[], None]] = None


def run_gate_case(c: GateCase) -> None:
    if c.setup is not None:
        c.setup()
    if c.expect == "block":
        proc = run_hook(c.hook_path, c.payload, c.cwd, c.env)
        if c.main_payload is not None:
            main_proc = run_hook(c.hook_path, c.main_payload, c.cwd, c.env)
            ok, detail = assert_equivalence_block(c.guard_key, proc, main_proc, c.extra_block_text)
        else:
            ok, detail = assert_block(c.guard_key, proc, c.extra_block_text)
    else:
        assert c.sibling_payload is not None, f"{c.id}: ALLOW case needs a sibling_payload"
        ok, detail = run_gate_allow_case(
            c.guard_key, c.hook_path, c.payload, c.sibling_payload, c.cwd, c.env, c.pre_sibling,
        )
    label = f"{c.id} [{'FAILS TODAY' if c.fails_today else 'control'}]"
    check(label, ok, detail)


@dataclass
class DbCase:
    id: str
    hook_path: Path
    payload: dict
    cwd: Path
    env: dict
    logs_dir: Path
    expect: str
    fails_today: bool
    main_payload: Optional[dict] = None
    sibling_payload: Optional[dict] = None


def run_db_case(c: DbCase) -> None:
    if c.expect == "block":
        proc = run_hook(c.hook_path, c.payload, c.cwd, c.env)
        if c.main_payload is not None:
            main_proc = run_hook(c.hook_path, c.main_payload, c.cwd, c.env)
            ok, detail = assert_equivalence_block("db-destructive-guard", proc, main_proc, PROTECTED_WRITE_TEXT)
        else:
            ok, detail = assert_block("db-destructive-guard", proc, PROTECTED_WRITE_TEXT)
    else:
        assert c.sibling_payload is not None, f"{c.id}: ALLOW case needs a sibling_payload"
        ok, detail = run_db_allow_case(c.hook_path, c.payload, c.sibling_payload, c.cwd, c.env, c.logs_dir)
    label = f"{c.id} [{'FAILS TODAY' if c.fails_today else 'control'}]"
    check(label, ok, detail)


def write_payload(file_path: str, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}


def bash_append_payload(target: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": f'echo "worktree guard probe" >> {target}'}}


def read_payload(file_path: str) -> dict:
    return {"tool_name": "Read", "tool_input": {"file_path": file_path}}


def grep_path_payload(path: str, pattern: str = "TODO") -> dict:
    return {"tool_name": "Grep", "tool_input": {"path": path, "pattern": pattern}}


# ===========================================================================
# concept-gate (W1-W11)
# ===========================================================================
def run_concept_gate_cases(tree: dict) -> None:
    hook = HOOKS_DIR / "concept-gate.py"
    repo, wt, wt_name = tree["repo"], tree["wt"], tree["wt_name"]

    cases: list[GateCase] = []

    # W1 a: worktree src/Probe_<tok>.cs, no contract -> BLOCK, equals main
    t = tok()
    cases.append(GateCase(
        id="W1", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(fs(wt / "src" / f"Probe_{t}.cs"), "public class Probe {}\n"),
        main_payload=write_payload(fs(repo / "src" / f"Probe_{t}.cs"), "public class Probe {}\n"),
        cwd=repo, env=base_env(repo), expect="block", fails_today=True,
    ))

    # W2 a: same target, approved contract in the WORKTREE's own concepts -> ALLOW
    t = tok()
    target = fs(wt / "src" / f"Probe_{t}.cs")
    _w2_contract = write_contract(wt / ".claude" / "concepts", f"probe_{t}", [f"src/Probe_{t}.cs"])
    assert_contract_fixture("W2", _w2_contract, target)
    sib_t = tok()
    cases.append(GateCase(
        id="W2", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(target, "public class Probe {}\n"),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n"),
        cwd=repo, env=base_env(repo), expect="allow", fails_today=False,
    ))

    # W3 a: main src/Probe_<tok>.cs, no contract -> BLOCK (parity control)
    t = tok()
    cases.append(GateCase(
        id="W3", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(fs(repo / "src" / f"Probe_{t}.cs"), "public class Probe {}\n"),
        cwd=repo, env=base_env(repo), expect="block", fails_today=False,
    ))

    # W4 a: <repo>/.claude/hooks/x_<tok>.py -> ALLOW (positive control)
    t = tok()
    sib_t = tok()
    cases.append(GateCase(
        id="W4", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(fs(repo / ".claude" / "hooks" / f"x_{t}.py"), "# probe\n"),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n"),
        cwd=repo, env=base_env(repo), expect="allow", fails_today=False,
    ))

    # W5 a: worktree .claude/hooks/x_<tok>.py -> ALLOW (worktree-own control)
    t = tok()
    sib_t = tok()
    cases.append(GateCase(
        id="W5", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(fs(wt / ".claude" / "hooks" / f"x_{t}.py"), "# probe\n"),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n"),
        cwd=repo, env=base_env(repo), expect="allow", fails_today=False,
    ))

    # W6 b: worktree src/Probe_<tok>.cs, no contract -> BLOCK
    t = tok()
    cases.append(GateCase(
        id="W6", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(fs(wt / "src" / f"Probe_{t}.cs"), "public class Probe {}\n"),
        cwd=wt, env=base_env(wt), expect="block", fails_today=True,
    ))

    # W7 b: same target, DRAFT contract in the worktree -> BLOCK
    t = tok()
    target = fs(wt / "src" / f"Probe_{t}.cs")
    write_contract(wt / ".claude" / "concepts", f"probe_draft_{t}", [f"src/Probe_{t}.cs"], status="draft")
    cases.append(GateCase(
        id="W7", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(target, "public class Probe {}\n"),
        cwd=wt, env=base_env(wt), expect="block", fails_today=True,
    ))

    # W7a (round 3 task H NIT): the same draft-contract scenario, but in
    # situation a (CLAUDE_PROJECT_DIR and cwd both the main checkout) --
    # W7 only ever exercised situation b. IGNORED_STATUSES must reject a
    # draft contract found via the extra-roots (A3) mechanism too, not just
    # via the ordinary project_dir() rank W7 happens to hit in situation b.
    t = tok()
    target = fs(wt / "src" / f"Probe_{t}.cs")
    write_contract(wt / ".claude" / "concepts", f"probe_draft_a_{t}", [f"src/Probe_{t}.cs"], status="draft")
    cases.append(GateCase(
        id="W7a", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(target, "public class Probe {}\n"),
        cwd=repo, env=base_env(repo), expect="block", fails_today=False,
    ))

    # Situation c: copied hook at <repo>/.claude/hooks/
    c_hook = make_situation_c_copy(repo, "concept-gate.py")

    # W8 c, cwd = worktree root: worktree src/Probe_<tok>.cs, no contract -> BLOCK
    t = tok()
    cases.append(GateCase(
        id="W8", guard_key="concept-gate", hook_path=c_hook,
        payload=write_payload(fs(wt / "src" / f"Probe_{t}.cs"), "public class Probe {}\n"),
        cwd=wt, env=base_env(repo), expect="block", fails_today=True,
    ))

    # W9 c, cwd = <wt>/src: same target, approved contract in the worktree's
    # own concepts -> ALLOW (only A3 reaches that folder from a subfolder cwd)
    t = tok()
    target = fs(wt / "src" / f"Probe_{t}.cs")
    _w9_contract = write_contract(wt / ".claude" / "concepts", f"probe_subfolder_{t}", [f"src/Probe_{t}.cs"])
    assert_contract_fixture("W9", _w9_contract, target)
    sib_t = tok()
    cases.append(GateCase(
        id="W9", guard_key="concept-gate", hook_path=c_hook,
        payload=write_payload(target, "public class Probe {}\n"),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n"),
        cwd=wt / "src", env=base_env(repo), expect="allow", fails_today=False,
    ))

    # W10 c, cwd = <wt>/src: same target shape, no contract -> BLOCK
    t = tok()
    cases.append(GateCase(
        id="W10", guard_key="concept-gate", hook_path=c_hook,
        payload=write_payload(fs(wt / "src" / f"Probe_{t}.cs"), "public class Probe {}\n"),
        cwd=wt / "src", env=base_env(repo), expect="block", fails_today=True,
    ))

    # W11 a: doubled separator between .claude and worktrees -> ALLOW (control)
    t = tok()
    sib_t = tok()
    doubled = fs(repo) + "/.claude//worktrees/" + wt_name + f"/.claude/hooks/x_{t}.py"
    cases.append(GateCase(
        id="W11", guard_key="concept-gate", hook_path=hook,
        payload=write_payload(doubled, "# probe\n"),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n"),
        cwd=repo, env=base_env(repo), expect="allow", fails_today=False,
    ))

    for c in cases:
        run_gate_case(c)


# ===========================================================================
# PLUGIN PORT (sub-task 23): the bash-gate (B1-B9) and codegraph-first-guard (C1-C10) cases are cut
# with those hooks; every other case below is this repository's, unchanged.
# ===========================================================================


# ===========================================================================
# db-destructive-guard (D1-D7)
# ===========================================================================
def run_db_guard_cases(tree: dict) -> None:
    hook = HOOKS_DIR / "db-destructive-guard.py"
    repo, wt, wt_name = tree["repo"], tree["wt"], tree["wt_name"]
    logs_dir = repo / ".claude" / "logs"

    cases: list[DbCase] = []

    # D1 a: worktree src/Probe_<tok>.cs -> BLOCK (Layer 3c), equals main
    t = tok()
    cases.append(DbCase(
        id="D1", hook_path=hook,
        payload=write_payload(fs(wt / "src" / f"Probe_{t}.cs"), db_content(DB_PROT)),
        main_payload=write_payload(fs(repo / "src" / f"Probe_{t}.cs"), db_content(DB_PROT)),
        cwd=repo, env=base_env(repo), logs_dir=logs_dir, expect="block", fails_today=True,
    ))

    # D2 a: project .claude/concepts/example_<tok>.md -> ALLOW (control)
    t = tok()
    sib_t = tok()
    cases.append(DbCase(
        id="D2", hook_path=hook,
        payload=write_payload(fs(repo / ".claude" / "concepts" / f"example_{t}.md"), db_doc_content(DB_PROT)),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT)),
        cwd=repo, env=base_env(repo), logs_dir=logs_dir, expect="allow", fails_today=False,
    ))

    # D3 a: worktree .claude/concepts/example_<tok>.md -> ALLOW (control)
    t = tok()
    sib_t = tok()
    cases.append(DbCase(
        id="D3", hook_path=hook,
        payload=write_payload(fs(wt / ".claude" / "concepts" / f"example_{t}.md"), db_doc_content(DB_PROT)),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT)),
        cwd=repo, env=base_env(repo), logs_dir=logs_dir, expect="allow", fails_today=False,
    ))

    # D4 a: worktree <first src/ allow-list entry>appsettings.json -> ALLOW, equals main
    t = tok()
    sib_t = tok()
    wt_target = fs(wt / _SRC_ALLOWED / "appsettings.json")
    main_target = fs(repo / _SRC_ALLOWED / "appsettings.json")
    cases.append(DbCase(
        id="D4 (worktree)", hook_path=hook,
        payload=write_payload(wt_target, db_content(DB_PROT)),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT)),
        cwd=repo, env=base_env(repo), logs_dir=logs_dir, expect="allow", fails_today=False,
    ))
    sib_t2 = tok()
    cases.append(DbCase(
        id="D4 (main, equals worktree)", hook_path=hook,
        payload=write_payload(main_target, db_content(DB_PROT)),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t2}.cs"), db_content(DB_PROT)),
        cwd=repo, env=base_env(repo), logs_dir=logs_dir, expect="allow", fails_today=False,
    ))

    c_hook = make_situation_c_copy(repo, "db-destructive-guard.py", include_rules=True)
    c_logs_dir = repo / ".claude" / "logs"

    # D5 c, cwd = worktree root: worktree src/Probe_<tok>.cs -> BLOCK
    t = tok()
    cases.append(DbCase(
        id="D5", hook_path=c_hook,
        payload=write_payload(fs(wt / "src" / f"Probe_{t}.cs"), db_content(DB_PROT)),
        cwd=wt, env=base_env(repo), logs_dir=c_logs_dir, expect="block", fails_today=True,
    ))

    # D6 c, cwd = worktree root: worktree .claude/concepts/example_<tok>.md -> ALLOW
    t = tok()
    sib_t = tok()
    cases.append(DbCase(
        id="D6", hook_path=c_hook,
        payload=write_payload(fs(wt / ".claude" / "concepts" / f"example_{t}.md"), db_doc_content(DB_PROT)),
        sibling_payload=write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT)),
        cwd=wt, env=base_env(repo), logs_dir=c_logs_dir, expect="allow", fails_today=False,
    ))

    # D7 a: <repo>/.claude/./worktrees/<wt>/src/Probe_<tok>.cs -> BLOCK
    t = tok()
    dotted = fs(repo) + "/.claude/./worktrees/" + wt_name + f"/src/Probe_{t}.cs"
    cases.append(DbCase(
        id="D7", hook_path=hook,
        payload=write_payload(dotted, db_content(DB_PROT)),
        cwd=repo, env=base_env(repo), logs_dir=logs_dir, expect="block", fails_today=True,
    ))

    for c in cases:
        run_db_case(c)


# ===========================================================================
# Fallback mode (INV-5) -- three cases per guard, four guards.
# ===========================================================================
def run_fallback_cases(tree: dict) -> None:
    repo, wt, wt_name, home, isolated_root = (
        tree["repo"], tree["wt"], tree["wt_name"], tree["home"], tree["isolated"],
    )

    guard_specs = [
        ("concept-gate", "concept-gate.py", False,
         lambda t: write_payload(fs(wt / "src" / f"Probe_{t}.cs"), "public class Probe {}\n"),
         lambda t: write_payload(fs(repo / ".claude" / "hooks" / f"x_{t}.py"), "# probe\n"),
         lambda t: write_payload(fs(wt / ".claude" / "hooks" / f"x_{t}.py"), "# probe\n")),
        ("db-destructive-guard", "db-destructive-guard.py", True,
         lambda t: write_payload(fs(wt / "src" / f"Probe_{t}.cs"), db_content(DB_PROT)),
         lambda t: write_payload(fs(repo / ".claude" / "concepts" / f"example_{t}.md"), db_doc_content(DB_PROT)),
         lambda t: write_payload(fs(wt / ".claude" / "concepts" / f"example_{t}.md"), db_doc_content(DB_PROT))),
    ]

    for guard_key, filename, include_rules, block_payload_fn, project_allow_fn, wt_allow_fn in guard_specs:
        isolated_dir = isolated_root / guard_key
        isolated_dir.mkdir(parents=True, exist_ok=True)
        hook_copy = make_isolated_copy(isolated_dir, filename, include_rules=include_rules)
        env = fallback_env(repo, home)

        # F1: worktree src/Probe_<tok>.cs (the same shape as the guard's own
        # "1" case) -> BLOCK, AND stderr names "_project_paths.py" and the
        # isolated hooks path.
        t = tok()
        proc = run_hook(hook_copy, block_payload_fn(t), repo, env)
        stderr = _decode(proc.stderr)
        expected_missing_path = fs(isolated_dir / "_project_paths.py")
        banner = BANNERS[guard_key]
        extra_text = "" if guard_key != "db-destructive-guard" else PROTECTED_WRITE_TEXT
        ok = (
            proc.returncode == 2
            and banner in stderr
            and (extra_text == "" or extra_text in stderr)
            and "_project_paths.py" in stderr
            and expected_missing_path in stderr.replace("\\", "/")
        )
        detail = f"rc={proc.returncode} stderr={stderr[:500]!r}\nexpected missing-helper path: {expected_missing_path!r}"
        check(f"F1-{guard_key} [FAILS TODAY]", ok, detail)

        # F2: project <repo>/.claude/hooks/x_<tok>.py -> ALLOW (control)
        t = tok()
        sib_t = tok()
        allow_proc = run_hook(hook_copy, project_allow_fn(t), repo, env)
        sib_payload = block_payload_fn(f"sibling_{sib_t}")
        # Route the sibling through the main checkout (uncovered, always
        # blocks today and after the fix) instead of the worktree.
        if guard_key == "db-destructive-guard":
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT))
        else:
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n")

        if guard_key == "db-destructive-guard":
            ok, detail = run_db_allow_case(hook_copy, project_allow_fn(t), sib_payload, repo, env, home / ".claude" / "logs")
        else:
            ok, detail = run_gate_allow_case(guard_key, hook_copy, project_allow_fn(t), sib_payload, repo, env)
        check(f"F2-{guard_key} [control]", ok, detail)

        # F3: worktree .claude/hooks/x_<tok>.py -> ALLOW (control)
        t = tok()
        sib_t = tok()
        if guard_key == "db-destructive-guard":
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT))
            ok, detail = run_db_allow_case(hook_copy, wt_allow_fn(t), sib_payload, repo, env, home / ".claude" / "logs")
        else:
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n")
            ok, detail = run_gate_allow_case(guard_key, hook_copy, wt_allow_fn(t), sib_payload, repo, env)
        check(f"F3-{guard_key} [control]", ok, detail)


# ===========================================================================
# Round 3 task A: INV-7 negative twins. A mutant that "searches every
# worktree's concepts for every target" instead of only the ENCLOSING
# worktree's own stayed green against the round-2 suite, because that suite
# never gave it a SECOND worktree to wrongly find a contract in.
# ===========================================================================
def run_task_a_negative_twins(tree: dict) -> None:
    repo, wt, wt2 = tree["repo"], tree["wt"], tree["wt2"]

    # ---- concept-gate ----
    hook = HOOKS_DIR / "concept-gate.py"

    t = tok()
    sibling_target = fs(wt2 / "src" / f"Probe_{t}.cs")
    contract = write_contract(wt / ".claude" / "concepts", f"taska_cg_sibling_{t}", [f"src/Probe_{t}.cs"])
    assert_contract_fixture("task A concept-gate sibling", contract, sibling_target)
    proc = run_hook(hook, write_payload(sibling_target, "public class Probe {}\n"), repo, base_env(repo))
    ok, detail = assert_block("concept-gate", proc)
    check("task A concept-gate sibling: contract only in wt, target in wt2 -> BLOCK [control]", ok, detail)

    t = tok()
    main_target = fs(repo / "src" / f"Probe_{t}.cs")
    contract = write_contract(wt / ".claude" / "concepts", f"taska_cg_main_{t}", [f"src/Probe_{t}.cs"])
    assert_contract_fixture("task A concept-gate main-target", contract, main_target)
    proc = run_hook(hook, write_payload(main_target, "public class Probe {}\n"), repo, base_env(repo))
    ok, detail = assert_block("concept-gate", proc)
    check("task A concept-gate main-target: contract only in wt, target in main -> BLOCK [control]", ok, detail)


# ===========================================================================
# Round 3 task B: INV-2 corner. A file sitting directly in
# <repo>/.claude/worktrees/ (not inside any named worktree) is treated as
# the root of a worktree NAMED after that file -- its checkout-equivalent
# path is the repo root, so it gets no segment bypass. Its raw filename and
# extension still apply, so a trivial extension there stays trivial.
# ===========================================================================
def run_task_b_inv2_corner(tree: dict) -> None:
    hook = HOOKS_DIR / "concept-gate.py"
    repo = tree["repo"]

    t = tok()
    sib_t = tok()
    md_target = fs(repo / ".claude" / "worktrees" / f"notes_{t}.md")
    sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n")
    ok, detail = run_gate_allow_case(
        "concept-gate", hook,
        write_payload(md_target, "# notes\n"),
        sib_payload, repo, base_env(repo),
    )
    check("task B: <repo>/.claude/worktrees/notes_<tok>.md -> ALLOW (trivial extension) [control]", ok, detail)

    t = tok()
    py_target = fs(repo / ".claude" / "worktrees" / f"notes_{t}.py")
    proc = run_hook(hook, write_payload(py_target, "# probe\n"), repo, base_env(repo))
    ok, detail = assert_block("concept-gate", proc)
    check("task B: <repo>/.claude/worktrees/notes_<tok>.py -> BLOCK (not a trivial extension) [control]", ok, detail)


# ===========================================================================
# Round 3 task D: stale helper (code-review BLOCKER F1 / security W2). Every
# guard's `_segment_test_path` calls `_pp.checkout_equivalent_path(...)`
# unconditionally whenever `_pp is not None`, with no getattr guard -- so a
# STALE (importable, but pre-issue-222) _project_paths.py raises
# AttributeError instead of falling back to INV-5's fallback mode.
# ===========================================================================
def run_task_d_stale_helper(tree: dict) -> None:
    repo, wt, stale_root = tree["repo"], tree["wt"], tree["stale"]

    def stale_case_prefix(guard_key: str) -> str:
        return f"task D stale-helper {guard_key} [FAILS TODAY]"

    # ---- concept-gate (the bash-gate and codegraph-first-guard rows are cut with those hooks) ----
    for guard_key, filename, main_payload_fn, wt_payload_fn, proj_cfg_fn, wt_cfg_fn in (
        (
            "concept-gate", "concept-gate.py",
            lambda p: write_payload(p, "public class Probe {}\n"),
            lambda p: write_payload(p, "public class Probe {}\n"),
            lambda p: write_payload(p, "# probe\n"),
            lambda p: write_payload(p, "# probe\n"),
        ),
    ):
        dest = stale_root / guard_key
        hook_copy = make_stale_helper_copy(dest, filename)
        env = base_env(repo)
        prefix = stale_case_prefix(guard_key)

        t = tok()
        proc = run_hook(hook_copy, main_payload_fn(fs(repo / "src" / f"Probe_{t}.cs")), repo, env)
        ok, detail = assert_block(guard_key, proc)
        check(f"{prefix}: main-checkout src -> BLOCK", ok, detail)

        t = tok()
        proc = run_hook(hook_copy, wt_payload_fn(fs(wt / "src" / f"Probe_{t}.cs")), repo, env)
        ok, detail = assert_block(guard_key, proc)
        check(f"{prefix}: worktree src -> BLOCK", ok, detail)

        t = tok()
        sib_t = tok()
        sib_payload = wt_payload_fn(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"))
        ok, detail = run_gate_allow_case(
            guard_key, hook_copy,
            proj_cfg_fn(fs(repo / ".claude" / "hooks" / f"x_{t}.py")),
            sib_payload, repo, env,
        )
        check(f"{prefix}: project .claude/ config -> ALLOW", ok, detail)

        t = tok()
        sib_t = tok()
        sib_payload = wt_payload_fn(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"))
        ok, detail = run_gate_allow_case(
            guard_key, hook_copy,
            wt_cfg_fn(fs(wt / ".claude" / "hooks" / f"x_{t}.py")),
            sib_payload, repo, env,
        )
        check(f"{prefix}: worktree's own .claude/ -> ALLOW", ok, detail)

    # ---- db-destructive-guard: its own evidence shape ----
    db_dest = stale_root / "db-destructive-guard"
    db_hook_copy = make_stale_helper_copy(db_dest, "db-destructive-guard.py", include_rules=True)
    db_env = base_env(repo)
    db_logs_dir = repo / ".claude" / "logs"
    db_prefix = stale_case_prefix("db-destructive-guard")

    t = tok()
    proc = run_hook(db_hook_copy, write_payload(fs(repo / "src" / f"Probe_{t}.cs"), db_content(DB_PROT)), repo, db_env)
    ok, detail = assert_block("db-destructive-guard", proc, PROTECTED_WRITE_TEXT)
    check(f"{db_prefix}: main-checkout src (Layer 3c content) -> BLOCK", ok, detail)

    t = tok()
    proc = run_hook(db_hook_copy, write_payload(fs(wt / "src" / f"Probe_{t}.cs"), db_content(DB_PROT)), repo, db_env)
    ok, detail = assert_block("db-destructive-guard", proc, PROTECTED_WRITE_TEXT)
    check(f"{db_prefix}: worktree src (Layer 3c content) -> BLOCK", ok, detail)

    t = tok()
    sib_t = tok()
    ok, detail = run_db_allow_case(
        db_hook_copy,
        write_payload(fs(repo / ".claude" / "concepts" / f"example_{t}.md"), db_doc_content(DB_PROT)),
        write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT)),
        repo, db_env, db_logs_dir,
    )
    check(f"{db_prefix}: project .claude/ config -> ALLOW", ok, detail)

    t = tok()
    sib_t = tok()
    ok, detail = run_db_allow_case(
        db_hook_copy,
        write_payload(fs(wt / ".claude" / "concepts" / f"example_{t}.md"), db_doc_content(DB_PROT)),
        write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT)),
        repo, db_env, db_logs_dir,
    )
    check(f"{db_prefix}: worktree's own .claude/ -> ALLOW", ok, detail)

    # The specific case named in the round-3 brief: a Pass-A destructive
    # pattern (EnsureDeletedAsync + a literal protected-DB drop) UNRELATED
    # to issue 222's worktree fix, to show the stale-helper crash breaks
    # even the hook's ORIGINAL protection, not just the new worktree logic.
    t = tok()
    proc = run_hook(
        db_hook_copy,
        write_payload(fs(repo / "src" / f"Probe_{t}.cs"), db_ensure_deleted_content(DB_PROT)),
        repo, db_env,
    )
    ok, detail = assert_block("db-destructive-guard", proc)
    check(f"{db_prefix}: EnsureDeletedAsync + protected-DB drop (Pass A, pre-existing) -> BLOCK", ok, detail)


# ===========================================================================
# Round 3 task E: fallback spellings (code-review F2 / security W3). Doubled
# separators and "." components INSIDE the worktree-segment marker itself,
# under GENUINE fallback mode (import _project_paths raised -- the helper is
# actually missing, not merely stale).
# ===========================================================================
def run_task_e_fallback_spellings(tree: dict) -> None:
    repo, wt, wt_name, isolated_root = tree["repo"], tree["wt"], tree["wt_name"], tree["isolated"]

    guard_specs = [
        ("concept-gate", "concept-gate.py", False,
         lambda p: write_payload(p, "public class Probe {}\n"),
         lambda p: write_payload(p, "# probe\n")),
        ("db-destructive-guard", "db-destructive-guard.py", True,
         lambda p: write_payload(p, db_content(DB_PROT)),
         lambda p: write_payload(p, db_doc_content(DB_PROT))),
    ]

    for guard_key, filename, include_rules, src_payload_fn, cfg_payload_fn in guard_specs:
        isolated_dir = isolated_root / f"taskE-{guard_key}"
        isolated_dir.mkdir(parents=True, exist_ok=True)
        hook_copy = make_isolated_copy(isolated_dir, filename, include_rules=include_rules)
        env = fallback_env(repo, tree["home"])
        prefix = f"task E fallback {guard_key}"

        # "." component inside the worktree-segment marker. Empirically a
        # genuine gap for codegraph-first-guard and db-destructive-guard
        # ONLY: _fallback_checkout_equivalent's dot-removal regex
        # `(^|/)\.(?=/|$)` consumes the "/" BEFORE the dot but not the "/"
        # AFTER it (that "/" is only a lookahead, never part of the match),
        # so "/.claude/./worktrees/" becomes "/.claude//worktrees/" -- a
        # doubled separator introduced AFTER the doubled-separator collapse
        # already ran, so it is never cleaned up, and the worktree-marker
        # regex (which requires exactly one "/") never matches. concept-gate
        # and bash-gate are accidentally shielded from this because they
        # both convert the target to a `pathlib.Path` before calling
        # `_segment_test_path` -- pathlib's own parser drops a "." component
        # during construction, so the buggy regex never sees one.
        dot_today_fails = guard_key in ("codegraph-first-guard", "db-destructive-guard")
        t = tok()
        dotted = fs(repo) + "/.claude/./worktrees/" + wt_name + f"/src/Probe_{t}.cs"
        proc = run_hook(hook_copy, src_payload_fn(dotted), repo, env)
        extra = PROTECTED_WRITE_TEXT if guard_key == "db-destructive-guard" else None
        ok, detail = assert_block(guard_key, proc, extra)
        dot_tag = "[FAILS TODAY]" if dot_today_fails else "[control]"
        check(f"{prefix}: /.claude/./worktrees/<wt>/src/... -> BLOCK {dot_tag}", ok, detail)

        # doubled separator inside the worktree-segment marker -- handled by
        # the FIRST collapse step regardless of guard, so this is a control
        # for all four.
        t = tok()
        doubled = fs(repo) + "/.claude//worktrees/" + wt_name + f"/src/Probe_{t}.cs"
        proc = run_hook(hook_copy, src_payload_fn(doubled), repo, env)
        ok, detail = assert_block(guard_key, proc, extra)
        check(f"{prefix}: /.claude//worktrees/<wt>/src/... -> BLOCK [control]", ok, detail)

        # the worktree's own .claude/ via a "." component -- must stay ALLOW.
        t = tok()
        sib_t = tok()
        own_claude_dotted = (
            fs(repo) + "/.claude/worktrees/" + wt_name + f"/.claude/./hooks/x_{t}.py"
        )
        if guard_key == "db-destructive-guard":
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT))
            ok, detail = run_db_allow_case(
                hook_copy, cfg_payload_fn(own_claude_dotted), sib_payload, repo, env,
                tree["home"] / ".claude" / "logs",
            )
        else:
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n")
            ok, detail = run_gate_allow_case(guard_key, hook_copy, cfg_payload_fn(own_claude_dotted), sib_payload, repo, env)
        check(f"{prefix}: worktree's own .claude/ via /./ -> ALLOW [control]", ok, detail)


# ===========================================================================
# Round 3 task F: Windows alias spellings of "worktrees" (security W1).
# ===========================================================================
def run_task_f_windows_aliases(tree: dict) -> None:
    repo, wt, wt_name = tree["repo"], tree["wt"], tree["wt_name"]

    # ---- helper-level equivalence: all three aliases ----
    fn_ceq = getattr(pp, "checkout_equivalent_path", None)
    plain_input = f"R/.claude/worktrees/{wt_name}/src/X.cs"
    plain_expected_result = fn_ceq(plain_input) if fn_ceq is not None else None
    for alias in WORKTREES_ALIASES:
        alias_input = f"R/.claude/{alias}/{wt_name}/src/X.cs"
        label = f"task F helper: checkout_equivalent_path('{alias}') == plain spelling's result [FAILS TODAY]"
        if fn_ceq is None:
            check(label, False, "checkout_equivalent_path is not defined")
            continue
        try:
            alias_result = fn_ceq(alias_input)
        except Exception as exc:  # noqa: BLE001
            check(label, False, f"raised {exc!r}")
            continue
        # The plain spelling strips the segment, giving "R/src/X.cs"; an
        # alias that is recognised the same way must give the same result.
        ok = alias_result == plain_expected_result
        check(label, ok, f"alias input={alias_input!r} alias result={alias_result!r} plain result={plain_expected_result!r}")

    # ---- per-guard, normal mode: dot + ADS aliases -> BLOCK ----
    guard_specs = [
        ("concept-gate", HOOKS_DIR / "concept-gate.py",
         lambda p: write_payload(p, "public class Probe {}\n"), None),
        ("db-destructive-guard", HOOKS_DIR / "db-destructive-guard.py",
         lambda p: write_payload(p, db_content(DB_PROT)), PROTECTED_WRITE_TEXT),
    ]
    for guard_key, hook_path, payload_fn, extra_text in guard_specs:
        for alias in (WORKTREES_ALIAS_DOT, WORKTREES_ALIAS_ADS):
            t = tok()
            alias_target = fs(repo) + f"/.claude/{alias}/" + wt_name + f"/src/Probe_{t}.cs"
            proc = run_hook(hook_path, payload_fn(alias_target), repo, base_env(repo))
            ok, detail = assert_block(guard_key, proc, extra_text)
            check(f"task F {guard_key}: alias '{alias}' -> BLOCK [FAILS TODAY]", ok, detail)

    # One spot-check for the trailing-space alias (treated like the trailing
    # dot, per the brief) -- concept-gate only, to avoid tripling the matrix
    # above for a spelling that differs from the dot case only in which
    # single character trails "worktrees".
    t = tok()
    space_target = fs(repo) + f"/.claude/{WORKTREES_ALIAS_SPACE}/" + wt_name + f"/src/Probe_{t}.cs"
    proc = run_hook(HOOKS_DIR / "concept-gate.py", write_payload(space_target, "public class Probe {}\n"), repo, base_env(repo))
    ok, detail = assert_block("concept-gate", proc)
    check("task F concept-gate: alias 'worktrees ' (trailing space) -> BLOCK [FAILS TODAY]", ok, detail)

    # ---- per-guard, normal mode: worktree's own .claude/ under the dot
    # alias must stay ALLOW (the raw path still contains a literal
    # "/.claude/" from the worktree's OWN nested config, independent of the
    # outer alias spelling). ----
    for guard_key, hook_path, payload_fn, _extra in guard_specs:
        t = tok()
        sib_t = tok()
        own_claude_alias = fs(repo) + f"/.claude/{WORKTREES_ALIAS_DOT}/" + wt_name + f"/.claude/hooks/x_{t}.py"
        if guard_key == "db-destructive-guard":
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT))
            ok, detail = run_db_allow_case(
                hook_path,
                write_payload(own_claude_alias, db_doc_content(DB_PROT)),
                sib_payload, repo, base_env(repo), repo / ".claude" / "logs",
            )
        else:
            own_payload = write_payload(own_claude_alias, "# probe\n")
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n")
            ok, detail = run_gate_allow_case(guard_key, hook_path, own_payload, sib_payload, repo, base_env(repo))
        check(f"task F {guard_key}: worktree's own .claude/ under alias '{WORKTREES_ALIAS_DOT}' -> ALLOW [control]", ok, detail)

    # ---- fallback mode, db-destructive-guard: same two aliases -> BLOCK ----
    for guard_key, filename, include_rules, payload_fn, extra_text in (
        ("db-destructive-guard", "db-destructive-guard.py", True,
         lambda p: write_payload(p, db_content(DB_PROT)), PROTECTED_WRITE_TEXT),
    ):
        isolated_dir = tree["isolated"] / f"taskF-{guard_key}"
        isolated_dir.mkdir(parents=True, exist_ok=True)
        hook_copy = make_isolated_copy(isolated_dir, filename, include_rules=include_rules)
        env = fallback_env(repo, tree["home"])
        for alias in (WORKTREES_ALIAS_DOT, WORKTREES_ALIAS_ADS):
            t = tok()
            alias_target = fs(repo) + f"/.claude/{alias}/" + wt_name + f"/src/Probe_{t}.cs"
            proc = run_hook(hook_copy, payload_fn(alias_target), repo, env)
            ok, detail = assert_block(guard_key, proc, extra_text)
            check(f"task F fallback {guard_key}: alias '{alias}' -> BLOCK [FAILS TODAY]", ok, detail)


# ===========================================================================
# Round 4 item 1: ONE fallback table driving all four generic-suite copies
# (the fifth, sentinel-detector, is the local suite's own table). Per
# test-strategy-critic pass 2 (BLOCKERS B1-B3): task E/F's per-guard loops
# left bash-gate and concept-gate untested for the alias rows, and left the
# "worktreesX must still ALLOW in fallback mode" boundary (INV-5 x INV-8)
# completely unwitnessed for every copy. This table is a NEW, independent
# witness -- it does not replace run_task_e_fallback_spellings or the
# fallback half of run_task_f_windows_aliases, which stay as they are.
# ===========================================================================
def run_fallback_table(tree: dict) -> None:
    repo, wt, wt_name = tree["repo"], tree["wt"], tree["wt_name"]

    guard_specs = [
        ("concept-gate", "concept-gate.py", False,
         lambda p: write_payload(p, "public class Probe {}\n"),
         lambda p: write_payload(p, "# probe\n")),
        ("db-destructive-guard", "db-destructive-guard.py", True,
         lambda p: write_payload(p, db_content(DB_PROT)),
         lambda p: write_payload(p, db_doc_content(DB_PROT))),
    ]

    for guard_key, filename, include_rules, src_payload_fn, cfg_payload_fn in guard_specs:
        isolated_dir = tree["isolated"] / f"fbtable-{guard_key}"
        isolated_dir.mkdir(parents=True, exist_ok=True)
        hook_copy = make_isolated_copy(isolated_dir, filename, include_rules=include_rules)
        env = fallback_env(repo, tree["home"])
        extra = PROTECTED_WRITE_TEXT if guard_key == "db-destructive-guard" else None
        prefix = f"fallback table {guard_key}"

        block_rows = [
            ("plain worktree source", fs(wt / "src" / f"Probe_{{t}}.cs")),
            ("/./ variant", fs(repo) + "/.claude/./worktrees/" + wt_name + "/src/Probe_{t}.cs"),
            ("// variant", fs(repo) + "/.claude//worktrees/" + wt_name + "/src/Probe_{t}.cs"),
            ("'worktrees.' variant", fs(repo) + "/.claude/worktrees./" + wt_name + "/src/Probe_{t}.cs"),
            ("'worktrees::$INDEX_ALLOCATION' variant",
             fs(repo) + "/.claude/worktrees::$INDEX_ALLOCATION/" + wt_name + "/src/Probe_{t}.cs"),
        ]
        for row_name, template in block_rows:
            t = tok()
            target = template.format(t=t)
            proc = run_hook(hook_copy, src_payload_fn(target), repo, env)
            ok, detail = assert_block(guard_key, proc, extra)
            check(f"{prefix}: {row_name} -> BLOCK [control]", ok, detail)

        # ALLOW row: the worktree's own .claude/ file.
        t = tok()
        sib_t = tok()
        own_claude = fs(wt / ".claude" / "hooks" / f"x_{t}.py")
        if guard_key == "db-destructive-guard":
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT))
            ok, detail = run_db_allow_case(
                hook_copy, cfg_payload_fn(own_claude), sib_payload, repo, env,
                tree["home"] / ".claude" / "logs",
            )
        else:
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n")
            ok, detail = run_gate_allow_case(guard_key, hook_copy, cfg_payload_fn(own_claude), sib_payload, repo, env)
        check(f"{prefix}: worktree's own .claude/ file -> ALLOW [control]", ok, detail)

        # ALLOW row (B3): <repo>/.claude/worktreesX/<n>/hooks/x_<tok>.py --
        # "worktreesX" is not a whole "worktrees" component (INV-8), so this
        # must stay allowed via the untouched raw "/.claude/" bypass, even
        # in fallback mode.
        t = tok()
        sib_t = tok()
        worktreesx_target = fs(repo) + "/.claude/worktreesX/" + wt_name + f"/hooks/x_{t}.py"
        if guard_key == "db-destructive-guard":
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), db_content(DB_PROT))
            ok, detail = run_db_allow_case(
                hook_copy, cfg_payload_fn(worktreesx_target), sib_payload, repo, env,
                tree["home"] / ".claude" / "logs",
            )
        else:
            sib_payload = write_payload(fs(repo / "src" / f"ProbeSibling_{sib_t}.cs"), "public class Probe {}\n")
            ok, detail = run_gate_allow_case(guard_key, hook_copy, cfg_payload_fn(worktreesx_target), sib_payload, repo, env)
        check(f"{prefix}: <repo>/.claude/worktreesX/<n>/hooks/x_<tok>.py -> ALLOW [control]", ok, detail)


# ===========================================================================
# Round 4 item 3: aliased-".claude" join (security BLOCKER B1 / code
# BLOCKER B1). _worktree_segment_spans still applies
# _windows_alias_normalize to the FIRST component (".claude") as well as the
# second ("worktrees"), so an aliased ".claude" spelling sitting between two
# halves of a two-component allow-list entry gets folded away, JOINING the
# two halves into a recognised entry that was never actually there.
# ===========================================================================
def run_aliased_claude_join(tree: dict) -> None:
    repo, wt_name = tree["repo"], tree["wt_name"]

    src_tail = _SRC_ALLOWED.split("/", 1)[1]   # e.g. "scalpingmachine.api/"
    tools_head, tools_tail = _TOOLS_ALLOWED.split("/", 1)  # "tools", "db-protection/"

    db_hook = HOOKS_DIR / "db-destructive-guard.py"

    t = tok()
    target = fs(repo) + "/src/.claude./worktrees/" + wt_name + "/" + src_tail + f"X_{t}.cs"
    proc = run_hook(db_hook, write_payload(target, db_content(DB_PROT)), repo, base_env(repo))
    ok, detail = assert_block("db-destructive-guard", proc, PROTECTED_WRITE_TEXT)
    check("task 3 db-destructive-guard: src/.claude./worktrees/<w>/<src-allowlist-tail> join -> BLOCK [FAILS TODAY]", ok, detail)

    t = tok()
    target = fs(repo) + "/src/.claude::$INDEX_ALLOCATION/worktrees/" + wt_name + "/" + src_tail + f"X_{t}.cs"
    proc = run_hook(db_hook, write_payload(target, db_content(DB_PROT)), repo, base_env(repo))
    ok, detail = assert_block("db-destructive-guard", proc, PROTECTED_WRITE_TEXT)
    check("task 3 db-destructive-guard: src/.claude::$INDEX_ALLOCATION/worktrees/<w>/<src-allowlist-tail> join -> BLOCK [FAILS TODAY]", ok, detail)

    t = tok()
    target = fs(repo) + f"/{tools_head}/.claude./worktrees/" + wt_name + "/" + tools_tail + f"x_{t}.py"
    proc = run_hook(db_hook, write_payload(target, db_content(DB_PROT)), repo, base_env(repo))
    ok, detail = assert_block("db-destructive-guard", proc, PROTECTED_WRITE_TEXT)
    check("task 3 db-destructive-guard: tools/.claude./worktrees/<w>/<tools-allowlist-tail> join -> BLOCK [FAILS TODAY]", ok, detail)

    # Helper-level: once the join is fixed, an aliased ".claude" is not a
    # worktree segment at all, so checkout_equivalent_path must return the
    # input completely unchanged (forward-slash normalized only).
    fn_ceq = getattr(pp, "checkout_equivalent_path", None)
    fn_root = getattr(pp, "enclosing_worktree_root", None)
    helper_input = "R/src/.claude./worktrees/w/src/X.cs"
    if fn_ceq is None:
        check("task 3 helper: checkout_equivalent_path('...src/.claude./worktrees/w/...') returns input unchanged [FAILS TODAY]",
              False, "checkout_equivalent_path is not defined")
    else:
        try:
            actual = fn_ceq(helper_input)
            check(
                "task 3 helper: checkout_equivalent_path('...src/.claude./worktrees/w/...') returns input unchanged [FAILS TODAY]",
                actual == helper_input, f"actual={actual!r} expected={helper_input!r}",
            )
        except Exception as exc:  # noqa: BLE001
            check("task 3 helper: checkout_equivalent_path('...src/.claude./worktrees/w/...') returns input unchanged [FAILS TODAY]",
                  False, f"raised {exc!r}")
    if fn_root is None:
        check("task 3 helper: enclosing_worktree_root('...src/.claude./worktrees/w/...') returns None [FAILS TODAY]",
              False, "enclosing_worktree_root is not defined")
    else:
        try:
            actual_root = fn_root(helper_input)
            check(
                "task 3 helper: enclosing_worktree_root('...src/.claude./worktrees/w/...') returns None [FAILS TODAY]",
                actual_root is None, f"actual={actual_root!r}",
            )
        except Exception as exc:  # noqa: BLE001
            check("task 3 helper: enclosing_worktree_root('...src/.claude./worktrees/w/...') returns None [FAILS TODAY]",
                  False, f"raised {exc!r}")


# ===========================================================================
# Helper functions (INV-4, INV-8): _project_paths.checkout_equivalent_path
# and _project_paths.enclosing_worktree_root, looked up via getattr so a
# missing function is a FAILED check (an assertion), never an
# AttributeError/ImportError that would crash the suite.
# ===========================================================================
def run_helper_cases() -> None:
    fn_ceq = getattr(pp, "checkout_equivalent_path", None)
    fn_root = getattr(pp, "enclosing_worktree_root", None)
    const_wt_dir = getattr(pp, "WORKTREES_DIRNAME", None)

    check(
        "helper: _project_paths.checkout_equivalent_path is defined [FAILS TODAY]",
        fn_ceq is not None,
        "getattr(_project_paths, 'checkout_equivalent_path', None) is None -- not implemented yet",
    )
    check(
        "helper: _project_paths.enclosing_worktree_root is defined [FAILS TODAY]",
        fn_root is not None,
        "getattr(_project_paths, 'enclosing_worktree_root', None) is None -- not implemented yet",
    )
    check(
        "helper: _project_paths.WORKTREES_DIRNAME == 'worktrees' [FAILS TODAY]",
        const_wt_dir == "worktrees",
        f"actual={const_wt_dir!r}",
    )

    def ceq_case(name: str, input_path: str, expected: str) -> None:
        if fn_ceq is None:
            check(f"helper checkout_equivalent_path: {name} [FAILS TODAY]", False,
                  "checkout_equivalent_path is not defined")
            return
        try:
            actual = fn_ceq(input_path)
        except Exception as exc:  # noqa: BLE001
            check(f"helper checkout_equivalent_path: {name} [FAILS TODAY]", False,
                  f"raised {exc!r} for input {input_path!r}")
            return
        ok = actual == expected
        check(f"helper checkout_equivalent_path: {name} [FAILS TODAY]", ok,
              f"input={input_path!r} expected={expected!r} actual={actual!r}")

    ceq_case("forward slashes", "R/.claude/worktrees/w/src/X.cs", "R/src/X.cs")
    # NIT (round 3 task H): a hardcoded drive letter here fixed nothing this
    # helper is supposed to prove -- the backslash-vs-forward-slash rule is
    # drive-independent. Kept drive-free so the input names no local
    # filesystem fact.
    ceq_case("backslashes", r"repo\.claude\worktrees\w\src\X.cs", "repo/src/X.cs")
    ceq_case("mixed case", "R/.CLAUDE/WorkTrees/w/src/X.cs", "R/src/X.cs")
    ceq_case("nested pair", "R/.claude/worktrees/a/.claude/worktrees/b/src/X", "R/src/X")
    ceq_case("worktree root, no trailing part", "R/.claude/worktrees/w", "R")
    ceq_case("'.claude/worktrees' with no name", "R/.claude/worktrees", "R/.claude/worktrees")
    ceq_case("'.claude' not a whole component", "R/foo.claude/worktrees/x", "R/foo.claude/worktrees/x")
    ceq_case("doubled separator inside the worktree part", "R/.claude//worktrees/w/src/X", "R/src/X")
    ceq_case("'.' component inside the worktree part", "R/.claude/./worktrees/w/src/X", "R/src/X")
    ceq_case("leading './' kept", "./repo/.claude/worktrees/w/src/X.cs", "./repo/src/X.cs")
    ceq_case("leading network-path pair kept", "//server/share/.claude/worktrees/w/src/X.cs", "//server/share/src/X.cs")
    ceq_case("no segment, plain", "R/src/X.cs", "R/src/X.cs")
    ceq_case("no segment, doubled separator elsewhere (unchanged but for slashes)", "R//src/X.cs", "R//src/X.cs")

    def root_case(name: str, input_path: str, expected: Optional[str]) -> None:
        if fn_root is None:
            check(f"helper enclosing_worktree_root: {name} [FAILS TODAY]", False,
                  "enclosing_worktree_root is not defined")
            return
        try:
            actual = fn_root(input_path)
        except Exception as exc:  # noqa: BLE001
            check(f"helper enclosing_worktree_root: {name} [FAILS TODAY]", False,
                  f"raised {exc!r} for input {input_path!r}")
            return
        actual_norm = str(actual).replace("\\", "/") if actual is not None else None
        ok = actual_norm == expected
        check(f"helper enclosing_worktree_root: {name} [FAILS TODAY]", ok,
              f"input={input_path!r} expected={expected!r} actual={actual_norm!r}")

    root_case("plain worktree path", "R/.claude/worktrees/w/src/X.cs", "R/.claude/worktrees/w")
    root_case("no segment -> None", "R/src/X.cs", None)
    root_case("innermost of a nested pair", "R/.claude/worktrees/a/.claude/worktrees/b/src/X",
               "R/.claude/worktrees/a/.claude/worktrees/b")

    # -------------------------------------------------------------------
    # Round 3 task C: INV-8 helper boundary. "worktreesX" is a DIFFERENT
    # whole component from "worktrees" (WORKTREES_DIRNAME) -- it must never
    # be recognised as a worktree-segment marker.
    # -------------------------------------------------------------------
    _c_input = "R/.claude/worktreesX/w/src/X.cs"
    if fn_ceq is None:
        check("task C: checkout_equivalent_path('...worktreesX...') returns input unchanged [control]", False,
              "checkout_equivalent_path is not defined")
    else:
        try:
            _c_actual = fn_ceq(_c_input)
            check("task C: checkout_equivalent_path('...worktreesX...') returns input unchanged [control]",
                  _c_actual == _c_input, f"actual={_c_actual!r} expected={_c_input!r}")
        except Exception as exc:  # noqa: BLE001
            check("task C: checkout_equivalent_path('...worktreesX...') returns input unchanged [control]",
                  False, f"raised {exc!r}")
    if fn_root is None:
        check("task C: enclosing_worktree_root('...worktreesX...') returns None [control]", False,
              "enclosing_worktree_root is not defined")
    else:
        try:
            _c_root = fn_root(_c_input)
            check("task C: enclosing_worktree_root('...worktreesX...') returns None [control]",
                  _c_root is None, f"actual={_c_root!r}")
        except Exception as exc:  # noqa: BLE001
            check("task C: enclosing_worktree_root('...worktreesX...') returns None [control]",
                  False, f"raised {exc!r}")


# ===========================================================================
# main
# ===========================================================================
def main() -> int:
    home_before = snapshot_real_home_logs()

    tree = make_tree()
    try:
        print("-- concept-gate (W1-W11) --")
        run_concept_gate_cases(tree)
        print("-- db-destructive-guard (D1-D7) --")
        run_db_guard_cases(tree)
        print("-- fallback mode (F1-F3 x 2 guards) --")
        run_fallback_cases(tree)
        print("-- helper functions (_project_paths) --")
        run_helper_cases()
        print("-- round 3 task A: INV-7 negative twins --")
        run_task_a_negative_twins(tree)
        print("-- round 3 task B: INV-2 corner --")
        run_task_b_inv2_corner(tree)
        print("-- round 3 task D: stale helper --")
        run_task_d_stale_helper(tree)
        print("-- round 3 task E: fallback spellings --")
        run_task_e_fallback_spellings(tree)
        print("-- round 3 task F: Windows aliases --")
        run_task_f_windows_aliases(tree)
        print("-- round 4 item 1: fallback table (the remaining generic-suite copies) --")
        run_fallback_table(tree)
        print("-- round 4 item 3: aliased-.claude join --")
        run_aliased_claude_join(tree)
    finally:
        ok, detail = assert_real_home_untouched(home_before, list(_ISSUED_TOKENS), fs(tree["root"]))
        check(
            "the REAL ~/.claude/logs/db-guard.log and errors.jsonl received no new "
            "bytes mentioning this run's temp root or any of its probe tokens",
            ok, detail,
        )
        shutil.rmtree(tree["root"], ignore_errors=True)

    failed = sum(1 for _, ok, _ in _results if not ok)
    print()
    print(f"results: {len(_results) - failed} passed, {failed} failed (of {len(_results)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
