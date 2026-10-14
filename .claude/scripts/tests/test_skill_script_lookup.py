#!/usr/bin/env python3
"""
Tests for the one canonical "find the plugin's script" snippet that every skill carries.

Contract: .claude/concepts/2026-10-12-dedupe-claude-config.md in the consuming repository, Extension
Points ("The resolver order goes into every skill's script lookup ... One snippet is shared by every
copy") and scope note 3 (today's `ls ... | head -1` picks cache folder 0.3.1 ahead of 0.8.1, and
would pick 0.10.0 last).

WHAT IS PINNED DOWN
-------------------
Claude Code runs a skill's bash blocks in a shell. Each skill that needs one of the plugin's scripts
(pr_merged.py, land_contract.py, verify_parent_link.py, auto_improve_finish_install.py) carries a block
that finds it. The order is fixed: the project copy, then CLAUDE_PLUGIN_ROOT, then the installPath that
installed_plugins.json records (an entry for this project first, then the user entry), then the newest
cache folder compared as numbers.

How the copies are found: every line under skills/**/*.md that contains "agentic-auto-improve/*/" is a
line that searches the plugin cache. Today that search finds advance, pr-merged, flow, task and
auto-improve-finish-install.

How they are judged (decision 8 of the block 2 review): the fenced bash block holding each such line
is cut at the FIRST line that runs the script, `py -3 "$VAR" ...`, and the variable named on that line
is the one read back. No line inside the lookup (before that run line) may start with `py` or `python`,
so a lookup that shells out to Python is a failure here, and so is a block with no such run line. The
cut text is RUN in bash over a table of fixture setups; the variable is compared with the path the
table expects, and with what installed_plugin_root() answers in the same environment. All copies must
give the same answers, which is what "one snippet shared by every copy" means in behaviour. bash
missing is a FAILURE, not a skip: this check has no meaning without a shell.

Every case builds a throwaway Claude config directory and a throwaway project. Nothing real is read.

Run: py -3 .claude/scripts/tests/test_skill_script_lookup.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
HOOKS_DIR = SCRIPTS_DIR.parent / "hooks"
PLUGIN_ROOT = SCRIPTS_DIR.parent.parent
SKILLS = PLUGIN_ROOT / "skills"
PLUGIN_NAME = "agentic-auto-improve"
KEY = PLUGIN_NAME + "@auto-improve"
NEEDLE = "agentic-auto-improve/*/"
#: The line that runs the script: `py -3 "$VAR" ...` (or `${VAR}`). It ends the lookup and names the variable.
RUN_LINE = re.compile(r'^\s*py\s+-3\s+"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?"')
#: A line inside the lookup that starts a Python process: not allowed (decision 8).
PYTHON_LINE = re.compile(r"^\s*(?:py|python3?)\b")
SCRIPT = re.compile(r"\.claude/scripts/([A-Za-z0-9_]+\.py)")


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


def snippets() -> list[dict]:
    """Every fenced bash block under skills/ that holds a plugin-cache search line, cut before the run line."""
    found = []
    for path in sorted(SKILLS.rglob("*.md")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        i = 0
        while i < len(lines):
            if lines[i].lstrip().startswith("```"):
                j = i + 1
                while j < len(lines) and not lines[j].lstrip().startswith("```"):
                    j += 1
                block = lines[i + 1:j]
                if any(NEEDLE in line for line in block):
                    cut, var = [], None
                    for line in block:
                        run = RUN_LINE.match(line)
                        if run:
                            var = run.group(1)
                            break
                        cut.append(line)
                    text = textwrap.dedent("\n".join(cut)).strip("\n")
                    script = next((m.group(1) for m in map(SCRIPT.search, text.splitlines()) if m), None)
                    python_lines = [ln.strip() for ln in cut if PYTHON_LINE.match(ln)]
                    found.append({"file": path.relative_to(PLUGIN_ROOT).as_posix(), "start": i + 1,
                                  "text": text, "var": var, "script": script, "python_lines": python_lines})
                i = j
            i += 1
    return found


class World:
    def __init__(self, scripts: list[str], home_layout: bool = False):
        """home_layout: the Claude config directory is HOME/.claude and CLAUDE_CONFIG_DIR is not set at all."""
        self.tmp = Path(tempfile.mkdtemp(prefix="skill-lookup-"))
        self.home = self.tmp / "home"
        self.config = (self.home / ".claude") if home_layout else (self.tmp / "claude-config")
        self.home_layout = home_layout
        self.project = self.tmp / "proj"
        for d in (self.config, self.home, self.project):
            d.mkdir(parents=True, exist_ok=True)
        self.scripts = scripts

    def posix(self, p: Path) -> str:
        return str(p).replace("\\", "/")

    def version(self, name: str, market: str = "auto-improve") -> Path:
        d = self.config / "plugins" / "cache" / market / PLUGIN_NAME / name
        (d / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (d / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": PLUGIN_NAME}), encoding="utf-8")
        (d / ".claude" / "templates").mkdir(parents=True, exist_ok=True)
        (d / ".claude" / "templates" / "concept-contract.md").write_text("# c\n", encoding="utf-8")
        (d / ".claude" / "scripts").mkdir(parents=True, exist_ok=True)
        for s in self.scripts:
            (d / ".claude" / "scripts" / s).write_text("# stub\n", encoding="utf-8")
        return d

    def record(self, entries: dict) -> None:
        (self.config / "plugins").mkdir(parents=True, exist_ok=True)
        (self.config / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": entries}), encoding="utf-8")

    def env(self, **extra) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        env.update({"HOME": self.posix(self.home), "USERPROFILE": str(self.home),
                    "CLAUDE_PROJECT_DIR": self.posix(self.project)})
        if not self.home_layout:
            env["CLAUDE_CONFIG_DIR"] = self.posix(self.config)
        env.update(extra)
        return env

    def run_snippet(self, bash: str, snippet: dict, **extra_env) -> str:
        if not snippet["var"]:
            raise AssertionError("%s:%d has no run line of the form py -3 \"$VAR\" ..., so the variable to read "
                                 "back is unknown" % (snippet["file"], snippet["start"]))
        # The sentinel separates the snippet's own output (a block may echo) from the value we read back.
        script = "cd '%s'\n%s\nprintf '\\n@@VALUE@@%%s' \"$%s\"\n" % (
            self.posix(self.project), snippet["text"], snippet["var"])
        out = subprocess.run([bash, "--noprofile", "--norc", "-c", script], env=self.env(**extra_env),
                             capture_output=True, text=True, timeout=120)
        value = out.stdout.rsplit("@@VALUE@@", 1)[-1].strip() if "@@VALUE@@" in out.stdout else ""
        if value and os.name == "nt":
            conv = subprocess.run([bash, "--noprofile", "--norc", "-c", "cygpath -m \"$1\" 2>/dev/null || printf %s \"$1\"",
                                   "_", value], capture_output=True, text=True, timeout=60)
            value = conv.stdout.strip() or value
        return value

    def resolver_answer(self, **extra_env) -> str | None:
        code = ("import sys; sys.path.append(%r); import _project_paths as p; "
                "f = getattr(p, 'installed_plugin_root', None)\n"
                "if f is None: raise SystemExit('installed_plugin_root does not exist yet (missing symbol)')\n"
                "r = f(); print('' if r is None else r)" % str(HOOKS_DIR))
        out = subprocess.run([sys.executable, "-B", "-c", code], env=self.env(**extra_env), capture_output=True,
                             text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError("the resolver failed: " + (out.stderr or out.stdout)[-300:])
        return out.stdout.strip() or None

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def norm(path) -> str:
    return os.path.normcase(os.path.realpath(str(path))) if path else ""


class TestSkillScriptLookup(unittest.TestCase):

    def setUp(self):
        self.snips = snippets()
        self.bash = find_bash()
        scripts = sorted({s["script"] for s in self.snips if s["script"]})
        self.world = World(scripts)

    def tearDown(self):
        self.world.cleanup()

    # --------------------------------------------------------------- finding
    def test_the_search_for_the_cache_pattern_finds_skill_blocks(self):
        files = sorted({s["file"] for s in self.snips})
        self.assertGreater(len(files), 0,
                           "the search for %r must find at least one block under skills/ (it finds advance, "
                           "pr-merged, flow, task and auto-improve-finish-install today)" % NEEDLE)
        for s in self.snips:
            self.assertTrue(s["script"],
                            "%s:%d: the lookup must name a .claude/scripts/ path (script=%r)"
                            % (s["file"], s["start"], s["script"]))

    def test_every_block_ends_its_lookup_at_a_line_that_runs_the_script_and_names_the_variable(self):
        # Decision 8: the first `py -3 "$VAR" ...` line ends the lookup and names the variable to read.
        # A block with no such line has no variable the test can read, so it fails here and not later.
        self.assertGreater(len(self.snips), 0, "no snippet found to judge")
        for s in self.snips:
            with self.subTest(block="%s:%d" % (s["file"], s["start"])):
                self.assertIsNotNone(s["var"],
                                     "the block must carry a line of the form py -3 \"$VAR\" ... that runs the "
                                     "script; the variable on that line is the one the lookup assigns")
                self.assertRegex(s["text"], r"(?m)^\s*%s=" % re.escape(s["var"] or "VAR"),
                                 "the lookup must assign the variable that the run line uses")

    def test_no_line_inside_the_lookup_starts_with_py_or_python(self):
        # Decision 8: the lookup is plain shell. A lookup that shells out to Python needs Python to find
        # Python's own script and cannot be cut at the first run line.
        self.assertGreater(len(self.snips), 0, "no snippet found to judge")
        for s in self.snips:
            with self.subTest(block="%s:%d" % (s["file"], s["start"])):
                self.assertEqual(s["python_lines"], [],
                                 "no line of the lookup may start with py or python; found %r" % s["python_lines"])

    def test_bash_is_available_because_this_check_has_no_meaning_without_it(self):
        self.assertIsNotNone(self.bash, "bash is missing: this is a failure, not a skip")

    # -------------------------------------------------------- the case table
    def each(self, check):
        self.assertIsNotNone(self.bash, "bash is missing: this is a failure, not a skip")
        self.assertGreater(len(self.snips), 0, "no snippet found to run")
        for snip in self.snips:
            with self.subTest(block="%s:%d" % (snip["file"], snip["start"])):
                check(snip)

    def expected_script(self, root: Path, snip: dict) -> str:
        return norm(root / ".claude" / "scripts" / snip["script"])

    def test_the_newest_cache_folder_wins_by_version_number(self):
        w = self.world
        for v in ("0.3.1", "0.8.1", "0.10.0"):
            newest = w.version(v)
        newest = w.version("0.10.0")

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(got), self.expected_script(newest, snip),
                             "cache folders 0.3.1, 0.8.1 and 0.10.0 give 0.10.0; got %r" % got)
            self.assertEqual(norm(w.resolver_answer()), norm(newest),
                             "installed_plugin_root() gives the same folder as the snippet")
        self.each(check)

    def test_in_the_default_layout_the_newer_of_0_3_1_and_0_8_1_wins_not_the_first_listed(self):
        # Scope note 3 of the contract: the old `ls ... | head -1` picked 0.3.1 ahead of 0.8.1. Here the
        # Claude config directory is the home .claude and CLAUDE_CONFIG_DIR is not set, so the only thing
        # that can make an answer wrong is the ordering.
        self.world.cleanup()
        self.world = w = World(sorted({s["script"] for s in self.snips if s["script"]}), home_layout=True)
        w.version("0.3.1")
        newer = w.version("0.8.1")

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(got), self.expected_script(newer, snip),
                             "0.8.1 is newer than 0.3.1; got %r" % got)
            self.assertEqual(norm(w.resolver_answer()), norm(newer))
        self.each(check)

    def test_in_the_default_layout_0_10_0_beats_0_9_0_and_0_8_1(self):
        self.world.cleanup()
        self.world = w = World(sorted({s["script"] for s in self.snips if s["script"]}), home_layout=True)
        for v in ("0.9.0", "0.8.1"):
            w.version(v)
        newest = w.version("0.10.0")

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(got), self.expected_script(newest, snip),
                             "0.10.0 is newer than 0.9.0 (versions are numbers, not text); got %r" % got)
            self.assertEqual(norm(w.resolver_answer()), norm(newest))
        self.each(check)

    def test_a_cache_folder_whose_name_is_not_a_version_is_ignored(self):
        # Mirrors the resolver row: 'latest' and 'backup' sort after digits in a version sort but are not
        # versions, so a version sort in bash could put them ahead of 0.8.1.
        w = self.world
        real = w.version("0.8.1")
        w.version("latest")
        w.version("backup")

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(got), self.expected_script(real, snip),
                             "'latest' and 'backup' are not versions; 0.8.1 is the answer; got %r" % got)
            self.assertEqual(norm(w.resolver_answer()), norm(real))
        self.each(check)

    def test_the_project_path_is_compared_with_case_and_slashes_folded(self):
        # Mirrors the resolver row: the record spells the project upper-case with backslashes, the
        # environment spells it lower-case with forward slashes. Still this project.
        w = self.world
        user, scoped = w.version("0.8.1"), w.version("0.7.1")
        spelled = str(w.project).replace("/", "\\").upper()
        w.record({KEY: [{"scope": "user", "installPath": str(user), "version": "0.8.1"},
                        {"scope": "project", "projectPath": spelled, "installPath": str(scoped),
                         "version": "0.7.1"}]})
        project_env = w.posix(w.project).lower()

        def check(snip):
            got = w.run_snippet(self.bash, snip, CLAUDE_PROJECT_DIR=project_env)
            self.assertEqual(norm(got), self.expected_script(scoped, snip),
                             "a project path spelled with other slashes and letter case is still this project: %r" % got)
            self.assertEqual(norm(w.resolver_answer(CLAUDE_PROJECT_DIR=project_env)), norm(scoped))
        self.each(check)

    def test_a_project_scope_entry_for_another_project_is_ignored(self):
        w = self.world
        user, other = w.version("0.8.1"), w.version("0.7.1")
        w.record({KEY: [{"scope": "project", "projectPath": str(w.tmp / "Another"), "installPath": str(other),
                         "version": "0.7.1"},
                        {"scope": "user", "installPath": str(user), "version": "0.8.1"}]})

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(got), self.expected_script(user, snip),
                             "an entry scoped to a different project must not be used: %r" % got)
            self.assertEqual(norm(w.resolver_answer()), norm(user))
        self.each(check)

    def test_the_recorded_user_install_path_beats_a_newer_cache_folder(self):
        w = self.world
        recorded = w.version("0.8.1")
        w.version("0.10.0")
        w.record({KEY: [{"scope": "user", "installPath": str(recorded), "version": "0.8.1"}]})

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(got), self.expected_script(recorded, snip),
                             "installed_plugins.json records the version Claude Code runs: %r" % got)
            self.assertEqual(norm(w.resolver_answer()), norm(recorded))
        self.each(check)

    def test_the_project_scope_entry_for_this_project_beats_the_user_entry(self):
        w = self.world
        user, scoped = w.version("0.8.1"), w.version("0.7.1")
        w.record({KEY: [{"scope": "user", "installPath": str(user), "version": "0.8.1"},
                        {"scope": "project", "projectPath": str(w.project), "installPath": str(scoped),
                         "version": "0.7.1"}]})

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(got), self.expected_script(scoped, snip),
                             "an entry scoped to this project is chosen before the user entry: %r" % got)
            self.assertEqual(norm(w.resolver_answer()), norm(scoped))
        self.each(check)

    def test_a_recorded_path_that_is_missing_falls_through_to_the_newest_cache_folder(self):
        w = self.world
        w.version("0.3.1")
        newest = w.version("0.9.0")
        w.record({KEY: [{"scope": "user", "installPath": str(w.config / "gone" / "0.8.1"), "version": "0.8.1"}]})

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(got), self.expected_script(newest, snip),
                             "a recorded folder that was deleted falls through to the cache: %r" % got)
            self.assertEqual(norm(w.resolver_answer()), norm(newest))
        self.each(check)

    def test_the_plugin_root_variable_beats_the_record_and_the_cache(self):
        w = self.world
        w.version("0.10.0")
        named = w.version("0.1.0", market="elsewhere")
        w.record({KEY: [{"scope": "user", "installPath": str(w.version("0.8.1")), "version": "0.8.1"}]})

        def check(snip):
            got = w.run_snippet(self.bash, snip, CLAUDE_PLUGIN_ROOT=w.posix(named))
            self.assertEqual(norm(got), self.expected_script(named, snip),
                             "CLAUDE_PLUGIN_ROOT names the running version: %r" % got)
            self.assertEqual(norm(w.resolver_answer(CLAUDE_PLUGIN_ROOT=w.posix(named))), norm(named))
        self.each(check)

    def test_a_project_copy_of_the_script_is_found_first(self):
        w = self.world
        w.version("0.10.0")
        local_dir = w.project / ".claude" / "scripts"
        local_dir.mkdir(parents=True)
        for s in w.scripts:
            (local_dir / s).write_text("# vendored\n", encoding="utf-8")

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(norm(w.project / got) if not os.path.isabs(got) and not re.match(r"^[A-Za-z]:", got)
                             else norm(got), norm(local_dir / snip["script"]),
                             "a vendored project finds its own copy before any plugin install: %r" % got)
        self.each(check)

    def test_nothing_found_gives_an_empty_value_so_the_skill_can_stop(self):
        w = self.world

        def check(snip):
            got = w.run_snippet(self.bash, snip)
            self.assertEqual(got, "", "with no script anywhere the variable must be empty; got %r" % got)
        self.each(check)


if __name__ == "__main__":
    unittest.main(verbosity=2)
