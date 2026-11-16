#!/usr/bin/env python3
"""
test_switch_env_scan.py -- no shipped hook or script reads a plugin-owned switch from the environment.

Contract: .claude/concepts/2026-11-16-file-based-switches.md (the Inventory of environment reads, the
No-environment rule, the Switch catalog, and sub-task 1, "RED tests").

WHAT IS PINNED DOWN
-------------------
1. Every shipped Python file under .claude/hooks, .claude/scripts and .claude/addons/*/hooks (any
   folder named tests, fixtures or __pycache__ is left out) is parsed with the ast module.
2. A LITERAL read of an environment variable (os.environ.get("X"), os.environ["X"], "X" in os.environ,
   os.getenv("X")) must name a variable in one of three lists taken from the contract: HOST (supplied by
   Claude Code), PLATFORM (operating system or third-party tool plumbing) or TEST_ONLY (can only turn an
   allow into a block). Any other name, such as the retired CLAUDE_CONCEPT_GATE, fails.
3. A read whose name is not a literal, an alias of os.environ, a copy of the whole environment, or
   os.environ handed to a function must be on REVIEWED_SITES, a list of (file, function, kind) rows a
   person looked at. A site that is not listed fails. A listed site that no longer exists fails too, so
   the list cannot rot.
4. TEXT row: no retired variable name appears in shipped hooks, scripts, skills, CONTRIBUTING or README,
   outside the README section "Change notes by version".
5. TABLE row: the switch table of the README lists exactly the keys of the helper's catalog.

THE LIMIT OF THIS SCAN (named on purpose)
-----------------------------------------
The scan reads syntax only. It does NOT see getattr(os, "environ"), an import done through text
(importlib or __import__ with a built name), a mapping reached through a function parameter (a function
that receives os.environ is flagged where it is CALLED, not where the parameter is used), a name built at
run time and then read through a reviewed site, or an environment variable read by a child process.
A person adding such a read defeats this scan; the review of the pull request is the second control.

The scan is proved by two positive controls that plant CLAUDE_MADE_UP_SWITCH and an alias of
os.environ, so a scanner that stopped finding reads would fail loudly instead of passing empty.

ROWS THAT FAIL AT BASE are marked unittest.expectedFailure. Block 5 (ordinary switches) removes the mark
from the literal-read row, block 6 (documents) from the text and table rows.

Run: py -3 .claude/scripts/tests/test_switch_env_scan.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = ROOT / ".claude" / "hooks"

# --------------------------------------------------------------------------------------------------
# The contract's lists.
# --------------------------------------------------------------------------------------------------
#: Host-supplied, kept (Inventory: "Host-supplied, kept").
HOST = frozenset({
    "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_CONFIG_DIR",
    "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
})
#: Platform and third-party tool plumbing, kept. SYSTEMROOT and the other copied names are what the
#: isolated git environment copies from the caller (_protected_names.COPIED_ENV and its local copy).
PLATFORM = frozenset({
    "PATH", "LOCALAPPDATA", "GH_REPO", "GH_HOST",
    "XDG_CACHE_HOME", "HOME", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
})
#: Test-only, kept: can only turn an allow into a block.
TEST_ONLY = frozenset({"DB_GUARD_FAULT_INJECTION"})
ALLOWED_LITERAL_NAMES = HOST | PLATFORM | TEST_ONLY

#: The retired variable names (nine switches, the arm variable, and the four skill-text variables).
RETIRED_NAMES = (
    "CLAUDE_CONCEPT_GATE", "CLAUDE_ACTIVE_CONTRACT", "CLAUDE_ARCH_GUARD", "CLAUDE_ACCURACY_TRACKER",
    "CLAUDE_INTEGRATION_CHECK", "CLAUDE_MEMORY_PAGER", "CLAUDE_WORKING_AGREEMENTS",
    "CLAUDE_PLAN_QUESTION_ADVISOR", "CLAUDE_CONTRACT_INDEX", "CLAUDE_DESTRUCTIVE_DB_OK",
    "CLAUDE_CONTRACT_SKIP", "CLAUDE_VERIFY_REVIEW_GATE", "CLAUDE_SKIP_CG", "CLAUDE_BASH_GATE",
)

#: The nine keys of the Switch catalog (Inventory table).
CATALOG_KEYS = frozenset({
    "concept_gate", "pinned_contract", "architecture_guard", "accuracy_tracker", "integration_check",
    "memory_pager", "working_agreements", "plan_question_advisor", "contract_index",
})

#: Reviewed sites: (file relative to the repository, enclosing function, kind). Each row was read by a
#: person on 2026-11-16 against the contract's Inventory paragraph "Reads whose name is not a literal" and
#: "Whole-environment copies handed to child processes". None of them changes the plugin's own
#: behaviour by a person's choice. Kinds: nonliteral, alias, whole, passed, other.
REVIEWED_SITES = frozenset({
    # a loop over the two session-id names (_error_log.py, _session_id)
    (".claude/hooks/_error_log.py", "_session_id", "nonliteral"),
    # the ${VAR} expansion of hook-row text (_project_paths.py, _expand_variables)
    (".claude/hooks/_project_paths.py", "_expand_variables", "nonliteral"),
    # whole-environment copies handed to child processes
    (".claude/hooks/_main_checkout_guard.py", "_merge_direction", "passed"),
    (".claude/hooks/_protected_names.py", "git", "passed"),
    (".claude/scripts/concept_changed_check.py", "_git", "passed"),
    (".claude/scripts/land_contract.py", "_run_long", "passed"),
    (".claude/scripts/merge_direction.py", "_env_without_gh_repo", "whole"),
    (".claude/scripts/pr_merged.py", "fetch_default_branch", "whole"),
    (".claude/scripts/pr_merged.py", "read_records_state", "whole"),
    # the isolated child-process environment copies platform variables from the caller (two copies)
    (".claude/hooks/_protected_names.py", "git_environment", "alias"),
    (".claude/hooks/_protected_names.py", "git_environment", "nonliteral"),
    (".claude/scripts/land_contract.py", "git_environment", "alias"),
    (".claude/scripts/land_contract.py", "git_environment", "nonliteral"),
    # a mapping chosen by the caller, falling back to the process environment (GH_REPO only)
    (".claude/scripts/pr_merged.py", "_own_slug", "other"),
    # session_parent_base(os.environ, os.name) reads LOCALAPPDATA, XDG_CACHE_HOME and HOME (three add-on hooks)
    (".claude/addons/codegraph/hooks/codegraph-first-guard.py", "resolve_session_parent", "passed"),
    (".claude/addons/codegraph/hooks/codegraph-turn-reset.py", "resolve_session_parent", "passed"),
    (".claude/addons/codegraph/hooks/codegraph-turn-tracker.py", "resolve_session_parent", "passed"),
})


# --------------------------------------------------------------------------------------------------
# The scanner.
# --------------------------------------------------------------------------------------------------
class Finding(NamedTuple):
    file: str
    function: str
    kind: str          # literal, nonliteral, alias, whole, passed, other
    name: str          # the variable name for a literal read, else ""
    line: int


def _is_str(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


class _Scanner:
    """Finds reads of os.environ in one module. Syntax only (see the limit in the module docstring)."""

    def __init__(self, tree: ast.Module, file: str):
        self.tree = tree
        self.file = file
        self.parent: dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent[id(child)] = node
        self.os_names: set[str] = set()       # names bound to the os module
        self.environ_names: set[str] = set()  # names bound to os.environ (imports and aliases)
        self.getenv_names: set[str] = set()   # names bound to os.getenv
        self._collect_imports()
        self._collect_aliases()

    # -- collection ------------------------------------------------------------------------------
    def _collect_imports(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == "os":
                        self.os_names.add(a.asname or "os")
            elif isinstance(node, ast.ImportFrom) and node.module == "os":
                for a in node.names:
                    if a.name == "environ":
                        self.environ_names.add(a.asname or "environ")
                    elif a.name == "getenv":
                        self.getenv_names.add(a.asname or "getenv")

    def is_env(self, node: ast.AST | None) -> bool:
        if isinstance(node, ast.Attribute) and node.attr == "environ":
            return isinstance(node.value, ast.Name) and node.value.id in self.os_names
        return isinstance(node, ast.Name) and node.id in self.environ_names

    def _collect_aliases(self) -> None:
        changed = True
        while changed:
            changed = False
            for node in ast.walk(self.tree):
                value, targets = None, []
                if isinstance(node, ast.Assign):
                    value, targets = node.value, node.targets
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    value, targets = node.value, [node.target]
                elif isinstance(node, ast.NamedExpr):
                    value, targets = node.value, [node.target]
                if value is not None and self.is_env(value):
                    for t in targets:
                        if isinstance(t, ast.Name) and t.id not in self.environ_names:
                            self.environ_names.add(t.id)
                            changed = True

    # -- classification --------------------------------------------------------------------------
    def function_of(self, node: ast.AST) -> str:
        cur = self.parent.get(id(node))
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return cur.name
            cur = self.parent.get(id(cur))
        return "<module>"

    def _literal_or_not(self, name_node: ast.AST | None, at: ast.AST) -> Finding:
        if _is_str(name_node):
            return Finding(self.file, self.function_of(at), "literal", name_node.value, at.lineno)
        return Finding(self.file, self.function_of(at), "nonliteral", "", at.lineno)

    def findings(self) -> list[Finding]:
        out: list[Finding] = []
        for node in ast.walk(self.tree):
            # os.getenv("X") / getenv("X")
            if isinstance(node, ast.Call):
                f = node.func
                is_getenv = (
                    (isinstance(f, ast.Attribute) and f.attr == "getenv"
                     and isinstance(f.value, ast.Name) and f.value.id in self.os_names)
                    or (isinstance(f, ast.Name) and f.id in self.getenv_names)
                )
                if is_getenv:
                    out.append(self._literal_or_not(node.args[0] if node.args else None, node))
            if not self.is_env(node):
                continue
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
                continue  # the alias name on the left of an assignment is reported once, by its value
            par = self.parent.get(id(node))
            fn = self.function_of(node)
            if isinstance(par, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and getattr(par, "value", None) is node:
                out.append(Finding(self.file, fn, "alias", "", node.lineno))
            elif isinstance(par, ast.Attribute) and par.value is node:
                call = self.parent.get(id(par))
                if isinstance(call, ast.Call) and call.func is par and par.attr in ("get", "pop", "setdefault"):
                    out.append(self._literal_or_not(call.args[0] if call.args else None, call))
                else:
                    out.append(Finding(self.file, fn, "whole", "", node.lineno))
            elif isinstance(par, ast.Subscript) and par.value is node:
                if isinstance(par.ctx, ast.Load):
                    out.append(self._literal_or_not(par.slice, par))
            elif isinstance(par, ast.Compare) and node in par.comparators:
                idx = par.comparators.index(node)
                if isinstance(par.ops[idx], (ast.In, ast.NotIn)) and idx == 0:
                    out.append(self._literal_or_not(par.left, par))
                else:
                    out.append(Finding(self.file, fn, "other", "", node.lineno))
            elif isinstance(par, ast.Call) and (node in par.args or any(k.value is node for k in par.keywords)):
                out.append(Finding(self.file, fn, "passed", "", node.lineno))
            elif isinstance(par, (ast.Dict, ast.For, ast.comprehension, ast.Starred, ast.Return, ast.keyword)):
                out.append(Finding(self.file, fn, "whole", "", node.lineno))
            elif isinstance(par, ast.Subscript):
                pass  # a Store or Del target is a write, not a read
            else:
                out.append(Finding(self.file, fn, "other", "", node.lineno))
        return out


def scan_source(source: str, file: str = "<planted>") -> list[Finding]:
    return _Scanner(ast.parse(source), file).findings()


_SKIP_PARTS = {"tests", "fixtures", "__pycache__"}


def shipped_python_files() -> list[Path]:
    roots = [ROOT / ".claude" / "hooks", ROOT / ".claude" / "scripts"]
    roots += sorted((ROOT / ".claude" / "addons").glob("*/hooks"))
    files: list[Path] = []
    for r in roots:
        if r.is_dir():
            files += [p for p in r.rglob("*.py") if not (_SKIP_PARTS & set(p.relative_to(ROOT).parts))]
    return sorted(set(files))


def scan_shipped() -> list[Finding]:
    found: list[Finding] = []
    for path in shipped_python_files():
        rel = path.relative_to(ROOT).as_posix()
        found += scan_source(path.read_text(encoding="utf-8"), rel)
    return found


# --------------------------------------------------------------------------------------------------
# Text and table helpers.
# --------------------------------------------------------------------------------------------------
_TEXT_SUFFIXES = {".py", ".json", ".md", ".txt", ".cmd", ".ps1", ".sh", ".yml", ".yaml", ".toml"}
#: The helper's catalog may name the old variable in its "replaces" field (contract, Switch catalog entry:
#: "replaces (old variable name, for documents only)"). Ambiguity reported in the hand-off.
_TEXT_EXEMPT = {".claude/hooks/_switches.py"}


def strip_change_notes(readme_text: str) -> str:
    """README text without the section "Change notes by version" (up to the next heading of its level or higher)."""
    lines = readme_text.splitlines()
    out: list[str] = []
    skipping, level = False, 0
    for line in lines:
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m:
            if skipping and len(m.group(1)) <= level:
                skipping = False
            if not skipping and m.group(2).strip().lower().startswith("change notes by version"):
                skipping, level = True, len(m.group(1))
        if not skipping:
            out.append(line)
    return "\n".join(out)


def shipped_text_files() -> list[Path]:
    files: list[Path] = []
    for sub in ("skills", ".claude/hooks", ".claude/scripts", ".claude/addons"):
        base = ROOT / sub
        if base.is_dir():
            files += [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES
                      and not (_SKIP_PARTS & set(p.relative_to(ROOT).parts))]
    for single in ("CONTRIBUTING.md", "README.md"):
        if (ROOT / single).is_file():
            files.append(ROOT / single)
    return sorted(set(files))


def retired_names_in(text: str) -> list[str]:
    return [n for n in RETIRED_NAMES if n in text]


def readme_switch_table_keys(readme_text: str) -> set[str] | None:
    """Keys in the first column of the README table whose header row has the cells Key, Values and Default."""
    lines = readme_text.splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().strip("`").lower() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "key" and "values" in cells and "default" in cells:
            keys: set[str] = set()
            for row in lines[i + 2:]:
                if not row.lstrip().startswith("|"):
                    break
                first = row.strip().strip("|").split("|")[0].strip().strip("`").strip()
                if first:
                    keys.add(first)
            return keys
    return None


def catalog_keys_from_helper() -> set[str]:
    """The keys the helper's catalog declares, read in a separate process so nothing leaks between tests."""
    code = (
        "import sys, json\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import _switches\n"
        "r = _switches.effective_switches()\n"
        "if isinstance(r, dict):\n"
        "    keys = list(r)\n"
        "else:\n"
        "    keys = [x['key'] if isinstance(x, dict) else x.key for x in r]\n"
        "print(json.dumps(sorted(keys)))\n"
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    proc = subprocess.run([sys.executable, "-I", "-c", code, str(HOOKS_DIR)], capture_output=True,
                          env=env, timeout=60, cwd=str(ROOT))
    if proc.returncode != 0:
        raise AssertionError("the switch helper could not be loaded: " + proc.stderr.decode("utf-8", "replace")[-400:])
    return set(json.loads(proc.stdout.decode("utf-8")))


# --------------------------------------------------------------------------------------------------
# Rows.
# --------------------------------------------------------------------------------------------------
class ScannerPositiveControls(unittest.TestCase):
    """These rows pass at base. They prove the scanner still finds what it must (Journal 2026-10-05)."""

    def test_a_planted_made_up_switch_is_found_and_is_not_an_allowed_name(self):
        found = scan_source("import os\ndef f():\n    return os.environ.get('CLAUDE_MADE_UP_SWITCH')\n")
        self.assertEqual([(f.kind, f.name) for f in found], [("literal", "CLAUDE_MADE_UP_SWITCH")],
                         "the planted read must be found as a literal read")
        self.assertNotIn("CLAUDE_MADE_UP_SWITCH", ALLOWED_LITERAL_NAMES,
                         "a made-up name must fall outside the host, platform and test-only lists")

    def test_every_literal_read_form_is_found(self):
        src = (
            "import os\nfrom os import environ, getenv as g\n"
            "a = os.environ['CLAUDE_A']\nb = os.getenv('CLAUDE_B')\nc = 'CLAUDE_C' in os.environ\n"
            "d = environ.get('CLAUDE_D')\ne = g('CLAUDE_E')\nf = os.environ.pop('CLAUDE_F', None)\n"
        )
        self.assertEqual(sorted(f.name for f in scan_source(src) if f.kind == "literal"),
                         ["CLAUDE_A", "CLAUDE_B", "CLAUDE_C", "CLAUDE_D", "CLAUDE_E", "CLAUDE_F"])

    def test_a_write_is_not_a_read(self):
        self.assertEqual(scan_source("import os\nos.environ['CLAUDE_X'] = '1'\n"), [])

    def test_an_alias_of_the_environment_is_found_and_so_is_a_read_through_it(self):
        src = "import os\ndef f():\n    e = os.environ\n    return e.get('CLAUDE_VIA_ALIAS')\n"
        kinds = sorted((f.kind, f.name) for f in scan_source(src))
        self.assertIn(("alias", ""), kinds, "the alias assignment must be reported")
        self.assertIn(("literal", "CLAUDE_VIA_ALIAS"), kinds, "a read through the alias must be reported")

    def test_a_non_literal_name_is_found(self):
        found = scan_source("import os\ndef f(key):\n    return os.environ.get(key)\n")
        self.assertEqual([(f.kind, f.function) for f in found], [("nonliteral", "f")])

    def test_the_environment_passed_to_a_function_or_copied_is_found(self):
        src = ("import os\ndef f():\n    g(os.environ)\n    h = dict(os.environ)\n"
               "    k = {**os.environ}\n    return os.environ.copy()\n")
        kinds = sorted(f.kind for f in scan_source(src))
        self.assertEqual(kinds, ["passed", "passed", "whole", "whole"])

    def test_a_planted_alias_site_is_not_on_the_reviewed_list(self):
        found = scan_source("import os\ndef sneaky():\n    e = os.environ\n    return e\n", "sneaky.py")
        sites = {(f.file, f.function, f.kind) for f in found}
        self.assertTrue(sites and not (sites <= REVIEWED_SITES),
                        "an unreviewed alias must not be accepted by the reviewed list")

    def test_the_change_notes_section_is_the_only_part_cut_from_the_readme(self):
        text = "# T\nCLAUDE_ARCH_GUARD kept\n### Change notes by version\nCLAUDE_ARCH_GUARD cut\n#### sub\ncut too\n### Next\nafter\n"
        kept = strip_change_notes(text)
        self.assertIn("kept", kept)
        self.assertIn("after", kept)
        self.assertNotIn("cut too", kept)
        self.assertNotIn("CLAUDE_ARCH_GUARD cut", kept)

    def test_the_table_reader_finds_a_switch_table(self):
        text = "x\n| Key | Values | Default | Effect | Allowed in |\n|---|---|---|---|---|\n| `concept_gate` | on, off | on | e | both |\n| `memory_pager` | on, off | on | e | both |\n\nafter\n"
        self.assertEqual(readme_switch_table_keys(text), {"concept_gate", "memory_pager"})

    def test_the_shipped_tree_is_found_and_not_empty(self):
        files = {p.relative_to(ROOT).as_posix() for p in shipped_python_files()}
        for must in (".claude/hooks/concept-gate.py", ".claude/scripts/_contract_index.py",
                     ".claude/addons/strict-shell-gate/hooks/bash-gate.py"):
            self.assertIn(must, files, "the scan must cover " + must)
        self.assertFalse([f for f in files if "/tests/" in f], "test files are excluded from the scan")


class ShippedEnvironmentReads(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.findings = scan_shipped()

    @unittest.expectedFailure  # base: retired switch variables are still read; block 5 removes the mark
    def test_every_literal_read_names_a_host_platform_or_test_only_variable(self):
        bad = sorted({(f.file, f.line, f.name) for f in self.findings
                      if f.kind == "literal" and f.name not in ALLOWED_LITERAL_NAMES})
        self.assertEqual(bad, [], "No-environment rule: these literal environment reads name a variable that is "
                                  "not in the host, platform or test-only lists of the contract")

    def test_every_non_literal_alias_or_passed_environment_read_is_a_reviewed_site(self):
        sites = {(f.file, f.function, f.kind) for f in self.findings if f.kind != "literal"}
        unreviewed = sorted(sites - REVIEWED_SITES)
        self.assertEqual(unreviewed, [],
                         "a read that is not a literal name, an alias of os.environ, or os.environ handed to a "
                         "function must be reviewed by a person and listed in REVIEWED_SITES")
        stale = sorted(REVIEWED_SITES - sites)
        self.assertEqual(stale, [], "these reviewed sites no longer exist; remove them from REVIEWED_SITES")

    @unittest.expectedFailure  # base: README, skills and hooks still name the retired variables; block 6 removes the mark
    def test_no_retired_variable_name_in_shipped_text(self):
        hits: list[tuple[str, str]] = []
        for path in shipped_text_files():
            rel = path.relative_to(ROOT).as_posix()
            if rel in _TEXT_EXEMPT:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if rel == "README.md":
                text = strip_change_notes(text)
            hits += [(rel, n) for n in retired_names_in(text)]
        self.assertEqual(hits, [], "no retired variable name may remain in shipped hooks, scripts, skills, "
                                   "CONTRIBUTING or README outside 'Change notes by version'")

    @unittest.expectedFailure  # base: no switch helper and no switch table; block 6 removes the mark
    def test_the_readme_switch_table_equals_the_catalog_keys(self):
        table = readme_switch_table_keys((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIsNotNone(table, "the README must hold a switch table whose header cells are Key, Values, Default")
        catalog = catalog_keys_from_helper()
        self.assertEqual(catalog, set(CATALOG_KEYS), "the catalog must hold exactly the nine keys of the Inventory")
        self.assertEqual(table, catalog, "the README switch table must list exactly the catalog keys")


if __name__ == "__main__":
    unittest.main(verbosity=2)
