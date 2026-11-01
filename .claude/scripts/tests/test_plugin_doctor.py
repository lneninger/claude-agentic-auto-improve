#!/usr/bin/env python3
"""
Tests for plugin_doctor.py — create what a consuming project is missing.

Every test runs against a throwaway directory. Nothing touches a real project.

Run: py -3 .claude/scripts/tests/test_plugin_doctor.py
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugin_doctor import (  # noqa: E402
    REQUIREMENTS,
    Requirement,
    check,
    apply_fixes,
    scaffold_for,
)


def _fake_plugin(root: Path) -> Path:
    """A plugin tree with the sources a project copies from."""
    p = root / "plugin"
    (p / ".claude/templates").mkdir(parents=True)
    (p / ".claude/templates/concept-contract.md").write_text("# Concept Contract\n", encoding="utf-8")
    (p / ".claude/registries").mkdir(parents=True)
    (p / ".claude/registries/MECHANISMS.md").write_text("# Mechanisms\n", encoding="utf-8")
    (p / ".claude/project-profile.md").write_text(
        "# Project Profile\n\n| Slot | Value |\n|---|---|\n"
        "| `project.name` | *(the repository name)* |\n", encoding="utf-8")
    return p


class DoctorCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "proj"
        self.project.mkdir()
        self.plugin = _fake_plugin(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# --------------------------------------------------------------------------
class TestCheck(DoctorCase):
    def test_a_bare_project_reports_everything_missing(self):
        missing = check(self.project)
        self.assertTrue(missing, "a project with no .claude should report requirements")
        self.assertTrue(all(isinstance(r, Requirement) for r in missing))

    def test_an_existing_file_is_not_reported_missing(self):
        (self.project / ".claude").mkdir()
        (self.project / ".claude/project-profile.md").write_text("mine", encoding="utf-8")
        missing = check(self.project)
        self.assertNotIn(".claude/project-profile.md", [r.path for r in missing])

    def test_every_requirement_declares_how_it_is_satisfied(self):
        for r in REQUIREMENTS:
            self.assertIn(r.kind, ("dir", "copy", "scaffold", "manual"),
                          f"{r.path} declares an unknown kind {r.kind}")


# --------------------------------------------------------------------------
class TestApply(DoctorCase):
    def test_directories_are_created(self):
        apply_fixes(self.project, check(self.project), self.plugin)
        self.assertTrue((self.project / ".claude/concepts").is_dir())
        self.assertTrue((self.project / ".claude/work-items").is_dir())

    def test_a_template_is_copied_from_the_plugin(self):
        apply_fixes(self.project, check(self.project), self.plugin)
        got = self.project / ".claude/templates/concept-contract.md"
        self.assertTrue(got.is_file())
        self.assertEqual(got.read_text(encoding="utf-8"), "# Concept Contract\n")

    def test_an_existing_file_is_never_overwritten(self):
        (self.project / ".claude/templates").mkdir(parents=True)
        mine = self.project / ".claude/templates/concept-contract.md"
        mine.write_text("MINE - DO NOT TOUCH", encoding="utf-8")
        # Pass the FULL requirement list, not check()'s filtered one. check() would
        # drop this file for already existing, so filtering it would test the filter
        # rather than the guard inside apply_fixes.
        apply_fixes(self.project, list(REQUIREMENTS), self.plugin)
        self.assertEqual(mine.read_text(encoding="utf-8"), "MINE - DO NOT TOUCH",
                         "apply_fixes must refuse an existing target even when handed one")

    def test_check_also_filters_an_existing_file(self):
        (self.project / ".claude/templates").mkdir(parents=True)
        (self.project / ".claude/templates/concept-contract.md").write_text("x", encoding="utf-8")
        self.assertNotIn(".claude/templates/concept-contract.md",
                         [r.path for r in check(self.project)])

    def test_a_scaffolded_json_file_is_valid_json(self):
        apply_fixes(self.project, check(self.project), self.plugin)
        for name in ("area-mapping.json", "work-item-conventions.json"):
            f = self.project / ".claude" / name
            if f.is_file():
                json.loads(f.read_text(encoding="utf-8"))

    def test_the_report_says_what_it_did_and_what_it_left(self):
        report = apply_fixes(self.project, check(self.project), self.plugin)
        self.assertIn("created", report)
        self.assertIn("needs_authoring", report)

    def test_nothing_is_created_when_the_plugin_source_is_absent(self):
        empty = self.tmp / "no-plugin"
        empty.mkdir()
        report = apply_fixes(self.project, check(self.project), empty)
        self.assertFalse((self.project / ".claude/templates/concept-contract.md").is_file())
        self.assertTrue(report["unresolved"],
                        "a copy whose source is missing must be reported, not silently skipped")


# --------------------------------------------------------------------------
class TestAuthoredFiles(DoctorCase):
    """A file describing the project must never be silently invented."""

    def test_the_profile_is_scaffolded_but_flagged_as_needing_authoring(self):
        report = apply_fixes(self.project, check(self.project), self.plugin)
        self.assertIn(".claude/project-profile.md", report["needs_authoring"])

    def test_the_scaffolded_profile_keeps_the_placeholders_visible(self):
        apply_fixes(self.project, check(self.project), self.plugin)
        text = (self.project / ".claude/project-profile.md").read_text(encoding="utf-8")
        self.assertIn("*(", text, "placeholders must survive so the loop reads the slot as unfilled")

    #: Names belonging to the originating project. None may appear in anything the
    #: doctor writes into a different repository.
    #:
    #: An agent the plugin actually ships is NOT a leak - naming one in a worked
    #: example is the point of a template. Only a name the plugin does not ship is,
    #: because a consuming project would inherit a handoff block addressed to an
    #: agent that does not exist for it.
    LEAKS = ("ScalpingMachine", "ClientApp", "scalping-machine", "admin-panel",
             "ingestion-data-architect", "llm-training-engineer", "pinescript-developer",
             "ibkr", "Alpaca")

    def test_no_file_the_doctor_writes_leaks_a_project_specific_value(self):
        report = apply_fixes(self.project, check(self.project), self.plugin)
        checked = 0
        for rel in report["created"]:
            f = self.project / rel
            if not f.is_file():
                continue
            checked += 1
            text = f.read_text(encoding="utf-8", errors="replace")
            for leaked in self.LEAKS:
                self.assertNotIn(leaked.lower(), text.lower(),
                                 f"{rel} carries '{leaked}' from the originating project")
        self.assertGreater(checked, 0, "the scan must actually have read some files")

    def test_the_scan_would_catch_a_leak_if_one_existed(self):
        # Positive control. Without this, the scan above could pass by reading nothing
        # useful, which is how a leak test quietly stops testing.
        planted = self.project / ".claude/planted.md"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text("built for ScalpingMachine", encoding="utf-8")
        text = planted.read_text(encoding="utf-8")
        self.assertTrue(any(l.lower() in text.lower() for l in self.LEAKS),
                        "the leak list must match a known leak")

    def test_settings_is_manual_and_never_written(self):
        kinds = {r.path: r.kind for r in REQUIREMENTS}
        self.assertEqual(kinds.get(".claude/settings.json"), "manual",
                         "registering hooks turns on enforcement; that is the operator's call")
        report = apply_fixes(self.project, list(REQUIREMENTS), self.plugin)
        self.assertFalse((self.project / ".claude/settings.json").exists())
        self.assertIn(".claude/settings.json", report["left_to_you"],
                      "a manual requirement must be reported, not silently dropped")

    def test_a_manual_requirement_is_never_created_even_with_a_source(self):
        # A positive control: give the manual entry everything a copy would need,
        # and it must still not be written.
        sneaky = Requirement(".claude/settings.json", "manual", "x",
                             source=".claude/templates/concept-contract.md")
        report = apply_fixes(self.project, [sneaky], self.plugin)
        self.assertFalse((self.project / ".claude/settings.json").exists())
        self.assertEqual(report["created"], [])


class TestScaffolds(DoctorCase):
    def test_every_scaffold_requirement_has_content_to_write(self):
        for r in REQUIREMENTS:
            if r.kind == "scaffold":
                self.assertIsNotNone(scaffold_for(r.path),
                                     f"{r.path} is scaffolded but has no content defined")



class TestTheRealPluginTree(unittest.TestCase):
    """The tests above prove the mechanism. This one proves the actual content.

    A fake plugin tree cannot catch a name leaking in the real template, because the
    fake one is clean by construction. Without this, the leak test passes while the
    thing it exists to protect is dirty.
    """

    #: Only a name the plugin does not ship counts. An agent it does ship is a
    #: legitimate worked example.
    NOT_SHIPPED = ("ingestion-data-architect", "llm-training-engineer",
                   "pinescript-developer", "ScalpingMachine", "ClientApp")

    def _plugin_root(self):
        """The plugin's own checkout, never a vendored copy.

        find_plugin_root deliberately prefers the vendored copy, because that is
        what a consuming project should use. Here we want the source of truth, so
        we look for a checkout that is the plugin rather than one that embeds it.
        """
        import os
        env = os.environ.get("AGENTIC_PLUGIN_ROOT")
        candidates = [Path(env)] if env else []
        here = Path(__file__).resolve()
        # The plugin is a SIBLING of this repository, so search the parent of the
        # repository root as well as the root itself.
        for level in (3, 4):
            if level < len(here.parents):
                candidates += list(here.parents[level].glob("claude-agentic-auto-improve"))
        for c in candidates:
            if (c / "plugin.json").is_file() and (c / ".claude/templates").is_dir():
                return c
        return None

    def test_the_files_a_project_copies_carry_no_unshipped_name(self):
        root = self._plugin_root()
        if root is None:
            self.skipTest("the plugin checkout is not beside this repository")
        from plugin_doctor import REQUIREMENTS
        checked = 0
        for r in REQUIREMENTS:
            if not r.source:
                continue
            f = root / r.source
            if not f.is_file():
                continue
            checked += 1
            text = f.read_text(encoding="utf-8", errors="replace")
            for name in self.NOT_SHIPPED:
                self.assertNotIn(name, text,
                                 f"{r.source} names '{name}', which the plugin does not ship; "
                                 f"every consuming project would inherit it")
        self.assertGreater(checked, 0, "the scan must have read at least one real source file")


# --------------------------------------------------------------------------
SKILL = "/auto-improve-finish-install"


def _run_doctor_fix(project: Path, plugin: Path) -> str:
    """Run the real command line with --fix and return what it printed."""
    import contextlib
    import io
    from unittest import mock

    import plugin_doctor

    argv = ["plugin_doctor.py", "--fix", "--project", str(project), "--plugin", str(plugin)]
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf):
        plugin_doctor.main()
    return buf.getvalue()


def _lines_starting(output: str, label: str):
    return [l for l in output.splitlines() if l.strip().startswith(label)]


class TestFinishInstallSkillIsNamed(DoctorCase):
    """Contract 2026-10-04-auto-improve-finish-install-skill: the doctor points the
    operator at the skill that finishes the two steps it will not do itself."""

    def _why(self, path):
        matches = [r.why for r in REQUIREMENTS if r.path == path]
        self.assertEqual(len(matches), 1, "fixture: exactly one requirement for %s" % path)
        return matches[0]

    def test_the_settings_requirement_names_the_skill(self):
        self.assertIn(SKILL, self._why(".claude/settings.json"),
                      "the operator who cannot have settings written for them must be told "
                      "which command registers the hooks")

    def test_the_profile_requirement_names_the_skill(self):
        self.assertIn(SKILL, self._why(".claude/project-profile.md"),
                      "the operator must be told which command fills the profile slots")

    def test_the_left_alone_line_names_the_skill(self):
        out = _run_doctor_fix(self.project, self.plugin)
        lines = [l for l in _lines_starting(out, "left alone") if ".claude/settings.json" in l]
        self.assertEqual(len(lines), 1, "the settings file must be reported as left alone; got: " + repr(out))
        self.assertIn(SKILL, lines[0],
                      "the left-alone line is where the operator learns what to do next")

    def test_the_needs_you_line_is_still_printed_for_the_authored_files(self):
        out = _run_doctor_fix(self.project, self.plugin)
        text = " | ".join(_lines_starting(out, "NEEDS YOU"))
        for path in (".claude/project-profile.md", ".claude/area-mapping.json",
                     ".claude/work-item-conventions.json"):
            self.assertIn(path, text, "NEEDS YOU must still be printed for %s" % path)

    def test_the_needs_you_line_does_not_name_the_skill(self):
        # The line is shared by three files and the skill fills only one of them, so
        # repointing it would send the operator to a command that cannot help with the
        # other two. A guard against a later repoint.
        out = _run_doctor_fix(self.project, self.plugin)
        offenders = [l for l in _lines_starting(out, "NEEDS YOU") if SKILL in l]
        self.assertEqual(offenders, [],
                         "NEEDS YOU is shared by three files and must not name %s" % SKILL)

    def test_the_needs_you_guard_would_catch_a_repointed_line(self):
        repointed = "  NEEDS YOU      .claude/area-mapping.json  - run /auto-improve-finish-install"
        offenders = [l for l in _lines_starting(repointed, "NEEDS YOU") if SKILL in l]
        self.assertEqual(len(offenders), 1, "positive control: the guard must detect a repointed line")


# ==========================================================================
# plugin_doctor.py --drift  (concept contract 2026-10-12-dedupe-claude-config, Commands: "Check plugin drift")
# ==========================================================================
#
# WHAT IT IS. A project that vendors files from the plugin must keep them equal, and a hook must not be
# registered by both the project and the plugin (it would run twice). --drift compares the project root
# with the installed plugin root (or --plugin) and prints Drift findings:
#
#   content-differs | one-sided | listed-twice | registered-twice | unreadable-registration
#
# Exit codes: 0 only when the comparison ran and nothing counted; 1 for any counted finding; 4 when it could
# not compare (no plugin, plugin root equals project root, a settings or sync-config file does not parse, a
# plugin-side root folder is missing, or zero file pairs were compared). It never exits 0 when it could not
# compare. --json carries `findings`, `compared` and `compared_addons`.
#
# SHAPES SETTLED BY THE BLOCK 2 REVIEW (decisions 4 to 6 and 9 of the contract's "Interface decisions" section):
#   * the --json envelope is {"findings": [{"kind", "path", "owner"}], "compared": N, "compared_addons": M};
#     `path` is the project-relative path, or "<event>:<hook file>" for registered-twice. A run that could not
#     compare (exit 4) still prints the report, with an `error` field and `compared` 0 (decision 4);
#   * sync-config `plugin_delivered` is a list of {"path", "plugin_path"} objects (the same two names the synced
#     trees use); `repo_owned` is a list of paths from the project root; `project_enforced_hooks` is a list of
#     hook file names (decision 5);
#   * dispatcher members are read statically, from the literal CHECKS list in the hook's source; a hook module
#     is never imported (decision 6), so the fixture dispatchers below are SOURCE TEXT;
#   * a project-side hook is registered in settings.json as "${CLAUDE_PROJECT_DIR}/.claude/hooks/<file>", a
#     plugin-side one in <plugin>/.claude/hooks/hooks.json as "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/<file>";
#   * add-on drift (decision 9) is built by block 18 and tested by block 16: the TestDriftAddons classes at the
#     end of this file pin it (the `addons` object, `compared_addons`, the presence rule). The baseline
#     `compared_addons == 0` when no add-on is declared stays pinned by TestDriftBaseline.

import os  # noqa: E402
import subprocess  # noqa: E402

DOCTOR = Path(__file__).resolve().parent.parent / "plugin_doctor.py"
SCRIPTS_DIR = DOCTOR.parent
HOOKS_DIR = SCRIPTS_DIR.parent / "hooks"
PLUGIN_NAME = "agentic-auto-improve"


def _norm_path(p) -> str:
    return str(p).replace("\\", "/")


class DriftWorld:
    """A throwaway project, a throwaway plugin and a throwaway Claude config directory."""

    materialize_rows = False

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="drift-"))
        self.project = self.tmp / "proj"
        self.plugin = self.tmp / "plugin"
        self.config_dir = self.tmp / "cfg"
        self.home = self.tmp / "home"
        for d in (self.project / ".claude" / "hooks", self.plugin / ".claude" / "hooks", self.config_dir, self.home):
            d.mkdir(parents=True, exist_ok=True)
        self.config = {
            "version": "3.0",
            "synced_trees": [
                self.tree("hooks", ".claude/hooks", ".claude/hooks", ["a.py", "b.py"]),
                self.tree("scripts", ".claude/scripts", ".claude/scripts", ["s.py"]),
            ],
            "templated_in_plugin": [],
            "plugin_delivered": [
                {"path": ".claude/agents", "plugin_path": "agents"},
                {"path": ".claude/skills", "plugin_path": "skills"},
            ],
            "project_enforced_hooks": ["db-destructive-guard.py", "db-research-readonly-guard.py"],
            "repo_owned": [],
            "addons": {},
        }
        self.project_settings = {"hooks": {}}
        self.plugin_hooks_json = {"hooks": {}}
        for rel in ("a.py", "b.py"):
            self.both(".claude/hooks/" + rel, "# %s\n" % rel)
        self.both(".claude/scripts/s.py", "# s\n")
        self.plugin_put("agents/x.md", "# agent x\n")
        self.plugin_put("skills/s1/SKILL.md", "# skill s1\n")

    # ----------------------------------------------------------------- shapes
    @staticmethod
    def tree(name, path, plugin_path, files, **extra):
        t = {"name": name, "path": path, "plugin_path": plugin_path, "plugin_managed": True,
             "ownership_tier": "generic", "direction": "bidirectional", "files": list(files)}
        t.update(extra)
        return t

    def tree_named(self, name):
        return next(t for t in self.config["synced_trees"] if t["name"] == name)

    # ------------------------------------------------------------------ files
    def _put(self, root: Path, rel: str, text: str, *, eol: str = "\n", bom: bool = False) -> Path:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = text.replace("\n", eol).encode("utf-8")
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
        return path

    def project_put(self, rel, text, **kw):
        return self._put(self.project, rel, text, **kw)

    def plugin_put(self, rel, text, **kw):
        return self._put(self.plugin, rel, text, **kw)

    def both(self, rel, text):
        self.project_put(rel, text)
        self.plugin_put(rel, text)

    def project_remove(self, rel):
        (self.project / rel).unlink()

    def plugin_remove(self, rel):
        (self.plugin / rel).unlink()

    # ---------------------------------------------------------- registrations
    @staticmethod
    def exec_row(path_var: str, hook: str, *extra_args: str) -> dict:
        args = ["-3", "%s/.claude/hooks/%s" % (path_var, hook)] + list(extra_args)
        return {"type": "command", "command": "py", "args": args}

    def project_register(self, event, hook, *, matcher="Edit|Write", gate=None, shell=False, local=False):
        """Register `hook` in the project's settings (or settings.local.json). `gate` makes it a launcher row.

        When `materialize_rows` is set, the files the row launches are written too: a row to a missing file is a
        dangling-hook-row finding, which the double-registration fixtures are not about. Off by default, because
        the dangling and disabled-hook fixtures want rows whose files are absent.
        """
        if self.materialize_rows:
            for name in ((hook, "_gate_launch.py", gate) if gate else (hook,)):
                if not (self.project / ".claude" / "hooks" / name).exists():
                    self.project_put(".claude/hooks/" + name, "# %s\n" % name)
        if gate:
            row = self.exec_row("${CLAUDE_PROJECT_DIR}", "gate-launch.py",
                                "${CLAUDE_PROJECT_DIR}/.claude/hooks/%s" % gate)
        elif shell:
            row = {"type": "command", "command": 'py -3 "$CLAUDE_PROJECT_DIR/.claude/hooks/%s"' % hook}
        else:
            row = self.exec_row("${CLAUDE_PROJECT_DIR}", hook)
        target = self.project_settings
        if local:
            target = getattr(self, "project_local_settings", {"hooks": {}})
            self.project_local_settings = target
        target.setdefault("hooks", {}).setdefault(event, []).append({"matcher": matcher, "hooks": [row]})

    def plugin_register(self, event, hook, *, matcher="Edit|Write", gate=None):
        if gate:
            row = self.exec_row("${CLAUDE_PLUGIN_ROOT}", "gate-launch.py",
                                "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/%s" % gate)
        else:
            row = self.exec_row("${CLAUDE_PLUGIN_ROOT}", hook)
        self.plugin_hooks_json.setdefault("hooks", {}).setdefault(event, []).append(
            {"matcher": matcher, "hooks": [row]})

    # ------------------------------------------------------------------ build
    def write_all(self):
        claude = self.project / ".claude"
        claude.mkdir(parents=True, exist_ok=True)
        (claude / ".sync-config.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        (claude / "settings.json").write_text(json.dumps(self.project_settings, indent=2), encoding="utf-8")
        if hasattr(self, "project_local_settings"):
            (claude / "settings.local.json").write_text(json.dumps(self.project_local_settings), encoding="utf-8")
        (self.plugin / ".claude" / "hooks" / "hooks.json").write_text(
            json.dumps(self.plugin_hooks_json, indent=2), encoding="utf-8")
        (self.plugin / ".claude-plugin").mkdir(exist_ok=True)
        (self.plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": PLUGIN_NAME, "version": "0.0.0"}), encoding="utf-8")
        templates = self.plugin / ".claude" / "templates"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "concept-contract.md").write_text("# contract\n", encoding="utf-8")

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        env.update({"HOME": str(self.home), "USERPROFILE": str(self.home),
                    "CLAUDE_CONFIG_DIR": str(self.config_dir)})
        env.update(extra)
        return {k: v for k, v in env.items() if v is not None}

    def run(self, *flags, plugin=True, as_json=True, **env):
        """Run the real command line. Returns (returncode, stdout, stderr, parsed json or None)."""
        self.write_all()
        argv = [sys.executable, "-B", str(DOCTOR), "--drift", "--project", str(self.project)]
        if plugin is True:
            argv += ["--plugin", str(self.plugin)]
        elif plugin:
            argv += ["--plugin", str(plugin)]
        if as_json:
            argv.append("--json")
        argv += list(flags)
        out = subprocess.run(argv, capture_output=True, text=True, env=self.env(**env), cwd=str(self.tmp),
                             timeout=120)
        data = None
        if as_json:
            try:
                data = json.loads(out.stdout)
            except ValueError:
                data = None
        return out.returncode, out.stdout, out.stderr, data

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def _findings(data) -> list[dict]:
    if not isinstance(data, dict):
        return []
    found = data.get("findings")
    if isinstance(found, list):
        return [f for f in found if isinstance(f, dict)]
    return []


def _kinds(data) -> list[str]:
    return sorted(f.get("kind", "") for f in _findings(data))


class DriftCase(unittest.TestCase):
    def setUp(self):
        self.w = DriftWorld()

    def tearDown(self):
        self.w.cleanup()

    def drift(self, *flags, **kw):
        rc, out, err, data = self.w.run(*flags, **kw)
        self.assertIsNotNone(
            data, "--drift --json must print one JSON document on stdout. exit=%s stdout=%r stderr=%r"
                  % (rc, out[:300], err[-300:]))
        return rc, data

    def assertKinds(self, data, expected, why):
        self.assertEqual(_kinds(data), sorted(expected), why + " -- findings: " + json.dumps(_findings(data))[:600])

    def path_of(self, data, kind):
        return [_norm_path(f.get("path", "")) for f in _findings(data) if f.get("kind") == kind]


class TestDriftBaseline(DriftCase):
    def test_a_clean_comparison_exits_0_and_counts_the_declared_files(self):
        rc, data = self.drift()
        self.assertEqual(rc, 0, "nothing differs, so the comparison exits 0")
        self.assertKinds(data, [], "a clean fixture has no findings")
        self.assertEqual(data.get("compared"), 3,
                         "compared = declared vendored files present on both sides (a.py, b.py, s.py)")
        self.assertEqual(data.get("compared_addons"), 0, "no add-on is declared, so no add-on file is compared")
        self.assertEqual(sorted(data), ["compared", "compared_addons", "findings"],
                         "decision 4: the envelope carries exactly findings, compared and compared_addons "
                         "when the comparison ran")

    def test_every_finding_carries_exactly_kind_path_and_owner(self):
        self.w.project_put(".claude/hooks/b.py", "# b changed here\n")
        rc, data = self.drift()
        self.assertEqual(len(_findings(data)), 1, "fixture: one finding")
        self.assertEqual(sorted(_findings(data)[0]), ["kind", "owner", "path"],
                         "decision 4: a finding is {kind, path, owner} and nothing else")

    def test_the_plugin_delivered_agents_and_skills_never_count_as_compared(self):
        self.w.plugin_put("agents/y.md", "# y\n")
        rc, data = self.drift()
        self.assertEqual(data.get("compared"), 3,
                         "a plugin-delivered pair is presence-checked only, so it adds nothing to compared")

    def test_without_the_plugin_flag_the_installed_plugin_root_is_used(self):
        record = {"version": 2, "plugins": {PLUGIN_NAME + "@auto-improve": [
            {"scope": "user", "installPath": str(self.w.plugin), "version": "0.0.0"}]}}
        (self.w.config_dir / "plugins").mkdir(parents=True, exist_ok=True)
        (self.w.config_dir / "plugins" / "installed_plugins.json").write_text(json.dumps(record), encoding="utf-8")
        rc, data = self.drift(plugin=None)
        self.assertEqual(rc, 0, "with no --plugin, --drift asks installed_plugin_root() and compares against it")
        self.assertEqual(data.get("compared"), 3)


class TestDriftContentDiffers(DriftCase):
    def test_a_declared_file_whose_content_differs_is_content_differs(self):
        self.w.project_put(".claude/hooks/b.py", "# b changed here\n")
        rc, data = self.drift()
        self.assertEqual(rc, 1, "any counted finding exits 1")
        self.assertKinds(data, ["content-differs"], "one declared file differs")
        self.assertTrue(self.path_of(data, "content-differs")[0].endswith("hooks/b.py"))
        self.assertEqual(_findings(data)[0].get("owner"), "plugin", "a file nobody listed as repo-owned has owner plugin")
        self.assertEqual(data.get("compared"), 3, "a differing pair was still compared")

    def test_line_endings_and_a_byte_order_mark_alone_give_no_finding(self):
        self.w.project_put(".claude/hooks/a.py", "# a.py\nx = 1\n", eol="\r\n", bom=True)
        self.w.plugin_put(".claude/hooks/a.py", "# a.py\nx = 1\n", eol="\n", bom=False)
        rc, data = self.drift()
        self.assertEqual(rc, 0, "CRLF and a BOM are not drift")
        self.assertKinds(data, [], "same text, other line endings and a byte order mark")
        self.assertEqual(data.get("compared"), 3, "the pair was compared and found equal")

    def test_an_undeclared_file_that_differs_gives_no_finding(self):
        self.w.project_put(".claude/hooks/local-only-note.py", "# mine\n")
        self.w.plugin_put(".claude/hooks/local-only-note.py", "# theirs\n")
        rc, data = self.drift()
        self.assertEqual(rc, 0, "an undeclared file is a local asset and is never compared")
        self.assertKinds(data, [], "undeclared and different")
        self.assertEqual(data.get("compared"), 3)

    def test_a_templated_pair_is_exempt_and_not_counted(self):
        self.w.tree_named("hooks")["files"].append("d.json")
        self.w.project_put(".claude/hooks/d.json", '{"mine": true}\n')
        self.w.plugin_put(".claude/hooks/d.json", '{"theirs": true}\n')
        self.w.config["templated_in_plugin"].append({"path": ".claude/hooks/d.json", "plugin_path": ".claude/hooks/d.json",
                                                     "reason": "project specific"})
        rc, data = self.drift()
        self.assertEqual(rc, 0, "templated_in_plugin names a pair that is deliberately never compared")
        self.assertKinds(data, [], "templated pair")
        self.assertEqual(data.get("compared"), 3, "a templated pair is not a compared pair")

    def test_registries_are_exempt_because_the_sync_tool_compares_their_sections(self):
        self.w.config["synced_trees"].append(self.w.tree(
            "registries", ".claude/registries", ".claude/registries", ["MECHANISMS.md"], section_scoped=True))
        self.w.project_put(".claude/registries/MECHANISMS.md", "# project section\n")
        self.w.plugin_put(".claude/registries/MECHANISMS.md", "# plugin section\n")
        rc, data = self.drift()
        self.assertEqual(rc, 0, "a section-scoped tree is not compared byte for byte")
        self.assertKinds(data, [], "registries differ by design")
        self.assertEqual(data.get("compared"), 3, "registries never count")

    def test_a_flat_file_under_a_plugin_delivered_root_that_both_sides_carry_and_templated_in_plugin_names_gives_no_finding(self):
        # (Revision 3) the flow case: a skill both sides carry, deliberately different, declared templated.
        self.w.project_put(".claude/skills/flow/SKILL.md", "# the project's flow\n")
        self.w.plugin_put("skills/flow/SKILL.md", "# the plugin's flow\n")
        self.w.config["templated_in_plugin"].append({
            "path": ".claude/skills/flow/SKILL.md", "plugin_path": "skills/flow/SKILL.md", "reason": "different documents"})
        rc, data = self.drift()
        self.assertEqual(rc, 0, "templated_in_plugin exempts the file from listed-twice as well")
        self.assertKinds(data, [], "the flow case")


class TestDriftOneSided(DriftCase):
    def test_a_declared_file_present_only_in_the_project_is_one_sided(self):
        self.w.plugin_remove(".claude/hooks/b.py")
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["one-sided"], "declared in the hooks list, missing in the plugin")
        self.assertTrue(self.path_of(data, "one-sided")[0].endswith("hooks/b.py"))
        self.assertEqual(data.get("compared"), 2, "a one-sided file has no second copy, so it never counts")

    def test_a_declared_file_present_only_in_the_plugin_is_one_sided(self):
        self.w.project_remove(".claude/hooks/b.py")
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["one-sided"], "declared in the hooks list, missing in the project")
        self.assertEqual(data.get("compared"), 2)

    def _skills_tree(self, with_plugin_subfolder: bool):
        self.w.config["synced_trees"].append(self.w.tree(
            "skills", ".claude/skills", "skills", ["pr-merged/SKILL.md", "pr-merged/references/x.md"]))
        self.w.project_put(".claude/skills/pr-merged/SKILL.md", "# pr-merged\n")
        self.w.plugin_put("skills/pr-merged/SKILL.md", "# pr-merged\n")
        self.w.project_put(".claude/skills/pr-merged/references/x.md", "# x\n")
        if with_plugin_subfolder:
            self.w.plugin_put("skills/pr-merged/references/other.md", "# other\n")

    def test_a_file_a_still_declared_plugin_delivered_tree_names_in_a_skill_subfolder_the_plugin_has_is_one_sided(self):
        self._skills_tree(with_plugin_subfolder=True)
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["listed-twice", "one-sided"],
                         "SKILL.md is on both sides of a plugin-delivered root (listed-twice); references/x.md is "
                         "named by the list, the plugin has the references/ folder but not the file (one-sided)")
        self.assertTrue(self.path_of(data, "one-sided")[0].endswith("pr-merged/references/x.md"))
        self.assertEqual(data.get("compared"), 3, "neither of them counts")

    def test_the_same_file_is_not_one_sided_when_the_plugin_has_no_such_subfolder(self):
        self._skills_tree(with_plugin_subfolder=False)
        rc, data = self.drift()
        self.assertKinds(data, ["listed-twice"], "without the plugin's subfolder there is nothing to be one-sided against")

    def test_a_flat_local_agent_no_list_names_gives_no_finding(self):
        self.w.project_put(".claude/agents/local-agent.md", "# local only\n")
        rc, data = self.drift()
        self.assertEqual(rc, 0, "an agent file no list names is a local asset, even with the plugin's agents/ present")
        self.assertKinds(data, [], "flat local agent")

    def test_a_local_skill_folder_and_an_undeclared_file_in_a_shared_skill_folder_give_no_finding(self):
        self.w.project_put(".claude/skills/local-skill/SKILL.md", "# local\n")
        self.w.project_put(".claude/skills/s1/extra-reference.md", "# only here, undeclared\n")
        rc, data = self.drift()
        self.assertEqual(rc, 0, "neither a local skill folder nor an undeclared file in a shared folder is drift")
        self.assertKinds(data, [], "local skill and undeclared extra")

    def test_a_flat_agent_a_declared_plugin_delivered_tree_names_is_never_one_sided(self):
        self.w.config["synced_trees"].append(self.w.tree("agents", ".claude/agents", "agents", ["gone-soon.md"]))
        self.w.project_put(".claude/agents/local-agent.md", "# local only\n")
        self.w.project_put(".claude/agents/gone-soon.md", "# declared, project only\n")
        rc, data = self.drift()
        self.assertEqual(self.path_of(data, "one-sided"), [],
                         "the subfolder case never matches a flat agent file (gone-soon.md is named by the list but is flat), "
                         "and local-agent.md is on no list")


class TestDriftListedTwice(DriftCase):
    def test_a_file_on_both_sides_of_a_plugin_delivered_root_is_listed_twice_even_when_identical(self):
        self.w.project_put(".claude/agents/x.md", "# agent x\n")
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["listed-twice"], "the same agent in both places")
        self.assertTrue(self.path_of(data, "listed-twice")[0].endswith("agents/x.md"))

    def test_a_still_declared_plugin_delivered_tree_gives_listed_twice_only_never_content_differs(self):
        self.w.config["synced_trees"].append(self.w.tree("agents", ".claude/agents", "agents", ["x.md"]))
        self.w.project_put(".claude/agents/x.md", "# agent x, edited in the project\n")
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["listed-twice"],
                         "a root pair named in plugin_delivered is never also compared as a vendored pair")
        self.assertEqual(data.get("compared"), 3, "and it does not count")

    def test_a_skill_file_on_both_sides_is_listed_twice(self):
        self.w.project_put(".claude/skills/s1/SKILL.md", "# skill s1\n")
        rc, data = self.drift()
        self.assertKinds(data, ["listed-twice"], "a skill both sides carry")


class TestDriftRegisteredTwice(DriftCase):
    def setUp(self):
        super().setUp()
        self.w.materialize_rows = True  # the project's rows launch files that exist

    def finding(self, data, hook, event):
        hits = [f for f in _findings(data) if f.get("kind") == "registered-twice"]
        return [f for f in hits if hook in _norm_path(f.get("path", "")) and event in _norm_path(f.get("path", ""))]

    def test_a_hook_registered_by_both_for_the_same_event_is_registered_twice(self):
        self.w.project_register("PreToolUse", "a.py")
        self.w.plugin_register("PreToolUse", "a.py")
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["registered-twice"], "one hook, both registrars")
        self.assertEqual(len(self.finding(data, "a.py", "PreToolUse")), 1, "the finding names the event and the hook")

    def test_the_same_hook_on_different_events_is_not_a_double_registration(self):
        self.w.project_register("PreToolUse", "a.py")
        self.w.plugin_register("PostToolUse", "a.py")
        rc, data = self.drift()
        self.assertKinds(data, [], "the Effective hook is the (event, hook file) pair")

    def test_a_shell_form_project_registration_counts(self):
        self.w.project_register("PreToolUse", "a.py", shell=True)
        self.w.plugin_register("PreToolUse", "a.py")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "shell form launches the same file")

    def test_a_registration_in_settings_local_counts(self):
        self.w.project_register("PreToolUse", "a.py", local=True)
        self.w.plugin_register("PreToolUse", "a.py")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "settings.local.json is read beside settings.json")

    def test_a_gate_launcher_row_is_compared_by_the_gate_it_names(self):
        self.w.project_register("PreToolUse", "gate-launch.py", gate="concept-gate.py")
        self.w.plugin_register("PreToolUse", "gate-launch.py", gate="concept-gate.py")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "the same gate through the same launcher, registered twice")
        self.assertEqual(len(self.finding(data, "concept-gate.py", "PreToolUse")), 1,
                         "the finding names the GATE, not the launcher")

    def test_two_launcher_rows_for_different_gates_are_different_hooks(self):
        self.w.project_register("PreToolUse", "gate-launch.py", gate="bash-gate.py")
        self.w.plugin_register("PreToolUse", "gate-launch.py", gate="concept-gate.py")
        rc, data = self.drift()
        self.assertKinds(data, [], "the launcher is the same file but the gates differ")

    def _dispatcher(self, name, members):
        self.w.plugin_put(".claude/hooks/" + name, "CHECKS = [\n%s]\n" % "".join('    "%s",\n' % m for m in members))
        self.w.plugin_register("PostToolUse", name)

    def test_a_member_of_the_post_edit_dispatcher_registered_again_by_the_project_is_registered_twice(self):
        self._dispatcher("post-edit-dispatcher.py", ["m1.py", "m2.py"])
        self.w.project_register("PostToolUse", "m1.py")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "the dispatcher runs m1.py inside the plugin's process")
        self.assertEqual(len(self.finding(data, "m1.py", "PostToolUse")), 1)

    def test_any_registered_file_whose_module_declares_a_checks_list_is_read_as_a_dispatcher(self):
        # No post-edit-dispatcher.py at all: a second dispatcher is recognised by its CHECKS list, not by its name.
        self._dispatcher("stop-dispatcher.py", ["n1.py", "n2.py"])
        self.w.plugin_hooks_json["hooks"]["PostToolUse"][0]["hooks"][0]["args"][1] = \
            "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/stop-dispatcher.py"
        self.w.project_register("PostToolUse", "n2.py")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "n2.py is a member of a dispatcher the plugin registers")
        self.assertEqual(len(self.finding(data, "n2.py", "PostToolUse")), 1)

    def test_a_second_dispatcher_beside_the_post_edit_one_is_compared_by_members(self):
        self._dispatcher("post-edit-dispatcher.py", ["m1.py"])
        self._dispatcher("second-dispatcher.py", ["k1.py", "k2.py"])
        self.w.project_register("PostToolUse", "k2.py")
        self.w.project_register("PostToolUse", "unrelated.py")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "only k2.py is registered by both")
        self.assertEqual(len(self.finding(data, "k2.py", "PostToolUse")), 1)
        self.assertEqual(self.finding(data, "unrelated.py", "PostToolUse"), [])

    def test_the_two_project_enforced_database_guards_are_exempt(self):
        for guard in ("db-destructive-guard.py", "db-research-readonly-guard.py"):
            self.w.project_register("PreToolUse", guard, matcher="Bash")
            self.w.plugin_register("PreToolUse", guard, matcher="Bash")
        rc, data = self.drift()
        self.assertEqual(rc, 0, "the project registers its guards on purpose and the plugin copy defers")
        self.assertKinds(data, [], "project_enforced_hooks")

    def test_another_hook_is_not_exempt_just_because_the_database_guards_are(self):
        for guard in ("db-destructive-guard.py", "a.py"):
            self.w.project_register("PreToolUse", guard, matcher="Bash")
            self.w.plugin_register("PreToolUse", guard, matcher="Bash")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "only a.py is a double registration")
        self.assertEqual(len(self.finding(data, "a.py", "PreToolUse")), 1)

    def test_a_pair_listed_twice_on_one_side_is_one_finding(self):
        self.w.plugin_register("PreToolUse", "gate-launch.py", gate="concept-gate.py", matcher="Edit|Write")
        self.w.plugin_register("PreToolUse", "gate-launch.py", gate="concept-gate.py", matcher="Bash|PowerShell")
        self.w.project_register("PreToolUse", "gate-launch.py", gate="concept-gate.py")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "the plugin's two launcher rows for one gate are counted once")

    def test_a_dispatcher_whose_member_list_cannot_be_read_is_unreadable_registration(self):
        # Decision 6: members are read statically from a literal CHECKS list. The fixture is SOURCE TEXT
        # whose CHECKS is built by a call at run time, so it is not a literal. An implementation that
        # imported the module would obtain a list here and report nothing, which is the wrong answer.
        self.w.plugin_put(".claude/hooks/odd-dispatcher.py",
                          "def _members():\n    return ['m1.py', 'm2.py']\n\nCHECKS = _members()\n")
        self.w.plugin_register("PostToolUse", "odd-dispatcher.py")
        self.w.project_register("PostToolUse", "m1.py")
        rc, data = self.drift()
        self.assertEqual(rc, 1, "an unreadable registration is a counted finding")
        self.assertKinds(data, ["unreadable-registration"],
                         "a dispatcher member list that is not a literal cannot be read statically, so m1.py is "
                         "NOT reported as registered twice")

    def test_a_dispatcher_module_is_never_imported_to_read_its_members(self):
        # Decision 6. The dispatcher's source writes a witness file the moment it is imported or run, then
        # carries a literal CHECKS list. The members must still be read (m1.py is a double registration)
        # and the witness must never appear.
        witness = self.w.tmp / "witness-dispatcher-ran"
        source = ("import pathlib\npathlib.Path(%r).write_text('ran')\n\nCHECKS = [\n    \"m1.py\",\n]\n"
                  % str(witness))
        self.w.plugin_put(".claude/hooks/post-edit-dispatcher.py", source)
        self.w.plugin_register("PostToolUse", "post-edit-dispatcher.py")
        self.w.project_register("PostToolUse", "m1.py")
        rc, data = self.drift()
        self.assertKinds(data, ["registered-twice"], "the literal list is read from the source text")
        self.assertFalse(witness.exists(),
                         "the check must read CHECKS from the source text and never import or run a hook module")


class TestDriftRepoOwned(DriftCase):
    GUARD = ".claude/hooks/db-destructive-guard.py"

    def setUp(self):
        super().setUp()
        self.w.tree_named("hooks")["files"].append("db-destructive-guard.py")
        self.w.project_put(self.GUARD, "# the repository's guard\n")
        self.w.plugin_put(self.GUARD, "# the plugin's guard\n")
        self.w.config["repo_owned"] = [self.GUARD]

    def test_a_repo_owned_difference_exits_1_without_the_flag(self):
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["content-differs"], "the declared difference is still a difference")
        self.assertEqual(_findings(data)[0].get("owner"), "repo", "the owner comes from the repo_owned list")

    def test_with_ignore_repo_owned_the_same_difference_exits_0_and_is_printed_as_reported(self):
        rc, data = self.drift("--ignore-repo-owned")
        self.assertEqual(rc, 0, "a repo-owned finding never stops landing")
        self.assertKinds(data, ["content-differs"], "it is still listed")
        self.assertEqual(_findings(data)[0].get("owner"), "repo")
        rc2, out, err, _ = self.w.run("--ignore-repo-owned", as_json=False)
        self.assertEqual(rc2, 0)
        lines = [l for l in out.splitlines() if "db-destructive-guard.py" in l]
        self.assertTrue(lines and all(l.lstrip().lower().startswith("reported") for l in lines),
                        "the text output prefixes a repo-owned finding with 'reported'; got: %r" % out[-400:])

    def test_the_flag_forgives_only_repo_owned_findings(self):
        self.w.project_put(".claude/hooks/b.py", "# b changed in the project\n")
        rc, data = self.drift("--ignore-repo-owned")
        self.assertEqual(rc, 1, "a plugin-owned difference still stops landing")
        self.assertKinds(data, ["content-differs", "content-differs"], "both differences are reported")
        self.assertEqual(sorted(f.get("owner") for f in _findings(data)), ["plugin", "repo"])


class TestDriftCannotCompare(DriftCase):
    def assertReportedAsNotCompared(self, out, data, why):
        """Decision 4: exit 4 still prints the report, with an `error` field and `compared` 0."""
        self.assertIsNotNone(data, why + ": exit 4 still prints one JSON document; stdout=%r" % out[-300:])
        self.assertTrue(isinstance(data.get("error"), str) and data["error"],
                        why + ": the report carries a non-empty `error` text; got %r" % data.get("error"))
        self.assertEqual(data.get("compared"), 0, why + ": a run that could not compare reports compared 0")
        self.assertEqual(data.get("findings"), [], why + ": and no findings")

    def _raw_run(self):
        argv = [sys.executable, "-B", str(DOCTOR), "--drift", "--project", str(self.w.project),
                "--plugin", str(self.w.plugin), "--json"]
        out = subprocess.run(argv, capture_output=True, text=True, env=self.w.env(), timeout=120)
        try:
            data = json.loads(out.stdout)
        except ValueError:
            data = None
        return out, data

    def test_a_missing_plugin_side_folder_of_a_vendored_pair_exits_4(self):
        shutil.rmtree(self.w.plugin / ".claude" / "scripts")
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 4, "the plugin has no .claude/scripts folder, so nothing under it can be compared")
        self.assertReportedAsNotCompared(out, data, "missing vendored folder")

    def test_a_missing_plugin_side_folder_of_a_plugin_delivered_pair_exits_4(self):
        shutil.rmtree(self.w.plugin / "agents")
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 4, "plugin_delivered pairs are held to the same rule; out=%r err=%r" % (out[-200:], err[-200:]))
        self.assertIn("agents", out + err, "the message names the missing folder")
        self.assertReportedAsNotCompared(out, data, "missing plugin-delivered folder")

    def test_an_empty_plugin_side_folder_is_not_missing(self):
        shutil.rmtree(self.w.plugin / "agents")
        (self.w.plugin / "agents").mkdir()
        rc, data = self.drift()
        self.assertEqual(rc, 0, "an empty folder is not a missing one")

    def test_a_missing_project_side_folder_of_a_plugin_delivered_pair_gives_no_finding(self):
        self.assertFalse((self.w.project / ".claude" / "agents").exists(), "fixture: no project agents folder")
        rc, data = self.drift()
        self.assertEqual(rc, 0)
        self.assertKinds(data, [], "after the repository's agents leave, nothing is expected there")

    def test_an_empty_comparison_exits_4_and_reports_zero_compared(self):
        for tree in self.w.config["synced_trees"]:
            tree["files"] = []
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 4, "a comparison that covered zero file pairs never exits 0; out=%r" % out[-200:])
        self.assertReportedAsNotCompared(out, data, "zero file pairs")

    def test_the_plugin_root_equal_to_the_project_root_exits_4(self):
        rc, out, err, data = self.w.run(plugin=str(self.w.project))
        self.assertEqual(rc, 4, "comparing a tree with itself would always look clean; out=%r" % out[-200:])
        self.assertReportedAsNotCompared(out, data, "plugin root equals project root")

    def test_no_plugin_found_exits_4(self):
        rc, out, err, data = self.w.run(plugin=None)
        self.assertEqual(rc, 4, "no --plugin, nothing recorded and nothing cached: it cannot compare; out=%r" % out[-200:])
        self.assertReportedAsNotCompared(out, data, "no plugin found")

    def test_an_unparseable_settings_file_exits_4(self):
        self.w.write_all()
        (self.w.project / ".claude" / "settings.json").write_text("{ not json", encoding="utf-8")
        out, data = self._raw_run()
        self.assertEqual(out.returncode, 4, "a registration file that does not parse must not read as 'no registrations'")
        self.assertReportedAsNotCompared(out.stdout, data, "unparseable settings")

    def test_an_unparseable_sync_config_exits_4(self):
        self.w.write_all()
        (self.w.project / ".claude" / ".sync-config.json").write_text("{ not json", encoding="utf-8")
        out, data = self._raw_run()
        self.assertEqual(out.returncode, 4, "a sync config that does not parse cannot be compared against")
        self.assertReportedAsNotCompared(out.stdout, data, "unparseable sync config")


class TestDriftOSErrorIsNotACrash(DriftCase):
    """Review round one: an OSError while reading is a failed comparison (exit 4 and a report), never a traceback."""

    def _in_process(self, *patchers, remove_config=False):
        import contextlib
        import io
        from unittest import mock

        import plugin_doctor

        self.w.write_all()
        if remove_config:
            (self.w.project / ".claude" / ".sync-config.json").unlink()
        argv = ["plugin_doctor.py", "--drift", "--project", str(self.w.project), "--plugin", str(self.w.plugin),
                "--json"]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf):
            for p in patchers:
                p.start()
            try:
                rc = plugin_doctor.main()
            finally:
                mock.patch.stopall()
        return rc, json.loads(buf.getvalue())

    def test_an_oserror_reading_a_declared_file_exits_4_with_a_report(self):
        from unittest import mock
        real = Path.read_bytes

        def deny(self_, *a, **k):
            if self_.name == "b.py":
                raise OSError("denied")
            return real(self_, *a, **k)

        rc, data = self._in_process(mock.patch.object(Path, "read_bytes", deny))
        self.assertEqual(rc, 4, "an unreadable file means the comparison could not run")
        self.assertTrue(isinstance(data.get("error"), str) and data["error"], "the report carries an error text")
        self.assertEqual(data.get("compared"), 0)
        self.assertEqual(data.get("findings"), [])

    def test_an_oserror_listing_a_folder_exits_4_with_a_report(self):
        from unittest import mock
        rc, data = self._in_process(mock.patch("os.listdir", side_effect=OSError("denied")), remove_config=True)
        self.assertEqual(rc, 4, "no sync config reads the folders by presence; a listing that fails cannot compare")
        self.assertTrue(isinstance(data.get("error"), str) and data["error"])
        self.assertEqual(data.get("compared"), 0)


class TestFindPluginRootDelegates(unittest.TestCase):
    """find_plugin_root() with no explicit path and no template of its own returns installed_plugin_root()."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="find-root-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_with_no_explicit_path_and_no_own_template_the_installed_root_is_returned(self):
        # A copy of the scripts and hooks with NO .claude/templates/concept-contract.md beside them: the
        # "own tree" step cannot answer, so the answer must come from the installed-root resolver.
        vendored = self.tmp / "vendored"
        (vendored / ".claude" / "scripts").mkdir(parents=True)
        (vendored / ".claude" / "hooks").mkdir(parents=True)
        for src in SCRIPTS_DIR.glob("*.py"):
            shutil.copy2(src, vendored / ".claude" / "scripts" / src.name)
        for src in HOOKS_DIR.glob("*.py"):
            shutil.copy2(src, vendored / ".claude" / "hooks" / src.name)
        config = self.tmp / "cfg"
        installed = config / "plugins" / "cache" / "auto-improve" / PLUGIN_NAME / "0.5.0"
        (installed / ".claude" / "templates").mkdir(parents=True)
        (installed / ".claude" / "templates" / "concept-contract.md").write_text("# c\n", encoding="utf-8")
        (installed / ".claude-plugin").mkdir()
        (installed / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": PLUGIN_NAME}), encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        env.update({"CLAUDE_CONFIG_DIR": str(config), "HOME": str(self.tmp / "home"),
                    "USERPROFILE": str(self.tmp / "home"), "CLAUDE_PROJECT_DIR": str(self.tmp / "project")})
        code = ("import sys; sys.path.insert(0, %r); import plugin_doctor; r = plugin_doctor.find_plugin_root(); "
                "print('' if r is None else r)" % str(vendored / ".claude" / "scripts"))
        out = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[-400:])
        self.assertEqual(os.path.normcase(os.path.realpath(out.stdout.strip() or "none")),
                         os.path.normcase(os.path.realpath(str(installed))),
                         "find_plugin_root delegates its cache step to installed_plugin_root()")


# ===========================================================================
# Add-on drift (dedupe contract, Revision 3, block 16): the sync config's `addons` object and the presence rule
# ===========================================================================
# The config object is add-on name -> the add-on hook files present in this project's .claude/hooks/. Each is
# compared with <plugin>/.claude/addons/<add-on>/hooks/<file> by the content-differs rule; a listed file
# missing on either side is one-sided; the owner is `plugin`. These files count in `compared_addons`, never in
# `compared`. A listed add-on whose plugin folder or manifest is missing is exit 4, like a missing root folder.
# A project with NO sync config (a plain plugin install) is read by presence instead: an add-on counts as
# installed when any of its manifest's hook files exists in .claude/hooks/.
#
# The manifest field names come from _addon_fixture's constants, the one seam shared with the other suites.
sys.path.insert(0, str(HOOKS_DIR / "tests"))
import _addon_fixture as af  # noqa: E402


def add_addon(world, name, files, *, project=True, plugin=True, manifest=True, folder=True, listed=True):
    """Build one add-on on the plugin side (manifest + hook files) and, optionally, the project's copies."""
    if folder:
        base = world.plugin / ".claude" / "addons" / name
        (base / "hooks").mkdir(parents=True, exist_ok=True)
        if manifest:
            rows = [{af.ROW_EVENT: "PreToolUse", af.ROW_MATCHER: "Bash", af.ROW_HOOK: f} for f in files]
            (base / "addon.json").write_text(json.dumps({
                af.KEY_HOOKS: list(files), af.KEY_HELPERS: [], af.KEY_ROWS: rows, af.KEY_PREREQUISITES: [],
                af.KEY_KILL_SWITCHES: [], af.KEY_INSTALL_SKILL: "auto-improve-%s-install" % name}), encoding="utf-8")
        if plugin:
            for f in files:
                (base / "hooks" / f).write_text("# add-on hook %s\n" % f, encoding="utf-8")
    if project:
        for f in files:
            world.project_put(".claude/hooks/" + f, "# add-on hook %s\n" % f)
    if listed:
        world.config["addons"][name] = list(files)


def run_without_config(world, *flags):
    """The real command line against a project with NO sync config. Returns (rc, stdout, stderr, json)."""
    world.write_all()
    (world.project / ".claude" / ".sync-config.json").unlink()
    argv = [sys.executable, "-B", str(DOCTOR), "--drift", "--project", str(world.project), "--plugin",
            str(world.plugin), "--json"] + list(flags)
    out = subprocess.run(argv, capture_output=True, text=True, env=world.env(), cwd=str(world.tmp), timeout=120)
    try:
        data = json.loads(out.stdout)
    except ValueError:
        data = None
    return out.returncode, out.stdout, out.stderr, data


class TestDriftAddons(DriftCase):
    GATE = ".claude/hooks/bash-gate.py"

    def test_an_identical_add_on_file_is_counted_in_compared_addons_and_not_in_compared(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"])
        rc, data = self.drift()
        self.assertEqual(rc, 0, "an identical add-on file is no drift")
        self.assertKinds(data, [], "nothing differs")
        self.assertEqual(data.get("compared_addons"), 1, "one add-on file was compared")
        self.assertEqual(data.get("compared"), 3, "add-on files count in compared_addons, never in compared")

    def test_an_add_on_file_whose_content_differs_is_content_differs_with_owner_plugin(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"])
        self.w.project_put(self.GATE, "# the project edited its installed copy\n")
        rc, data = self.drift()
        self.assertEqual(rc, 1, "a counted finding exits 1")
        self.assertKinds(data, ["content-differs"], "the installed copy differs from the plugin's")
        self.assertEqual(self.path_of(data, "content-differs"), [self.GATE])
        self.assertEqual(_findings(data)[0].get("owner"), "plugin", "an add-on file's owner is the plugin")
        self.assertEqual(data.get("compared_addons"), 1, "a differing pair was still compared")
        self.assertEqual(data.get("compared"), 3, "and still not counted in compared")

    def test_line_endings_and_a_byte_order_mark_alone_give_no_add_on_finding(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"])
        self.w.project_put(self.GATE, "# add-on hook bash-gate.py\n", eol="\r\n", bom=True)
        rc, data = self.drift()
        self.assertEqual(rc, 0, "the same rule as the vendored trees")
        self.assertKinds(data, [], "CRLF and a BOM are not drift")
        self.assertEqual(data.get("compared_addons"), 1, "the pair was compared and found equal")

    def test_a_listed_file_missing_in_the_project_is_one_sided(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], project=False)
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["one-sided"], "the config lists a file the project does not have")
        self.assertEqual(self.path_of(data, "one-sided"), [self.GATE])
        self.assertEqual(_findings(data)[0].get("owner"), "plugin")
        self.assertEqual(data.get("compared_addons"), 0, "a one-sided file has no second copy, so it is not compared")

    def test_a_listed_file_missing_in_the_plugin_is_one_sided(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], plugin=False)
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["one-sided"], "the project lists a file the plugin's add-on folder lacks")
        self.assertEqual(self.path_of(data, "one-sided"), [self.GATE])
        self.assertEqual(_findings(data)[0].get("owner"), "plugin")

    def test_compared_addons_counts_the_files_of_all_three_add_ons(self):
        add_addon(self.w, "angular-tailwind", ["angular-tailwind-advisor.py"])
        add_addon(self.w, "codegraph", ["codegraph-first-guard.py", "codegraph-turn-reset.py",
                                        "codegraph-turn-tracker.py"])
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"])
        rc, data = self.drift()
        self.assertEqual(rc, 0, "five identical add-on files")
        self.assertEqual(data.get("compared_addons"), 5, "1 + 3 + 1 add-on files were compared")
        self.assertEqual(data.get("compared"), 3, "the vendored count is unchanged")

    def test_a_file_the_config_does_not_list_is_a_local_asset_even_when_the_plugin_has_it_as_an_add_on(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], listed=False)
        self.w.project_put(self.GATE, "# an unlisted, different file\n")
        rc, data = self.drift()
        self.assertEqual(rc, 0, "a file no list names is never compared")
        self.assertKinds(data, [], "no finding for an unlisted file")
        self.assertEqual(data.get("compared_addons"), 0, "and nothing was compared")

    def test_a_listed_add_on_whose_plugin_folder_is_missing_exits_4_and_names_it(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], folder=False)
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 4, "a listed add-on with no folder in the plugin cannot be compared; out=%r" % out[-300:])
        self.assertIn("strict-shell-gate", out + err, "the message names the add-on")
        self.assertIsNotNone(data, "exit 4 still prints one JSON document")
        self.assertTrue(isinstance(data.get("error"), str) and data["error"], "with a non-empty error field")
        self.assertEqual(data.get("compared"), 0, "a run that could not compare reports compared 0")
        self.assertEqual(data.get("findings"), [], "and no findings")

    def test_a_listed_add_on_whose_manifest_is_missing_exits_4_and_names_it(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], manifest=False)
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 4, "a listed add-on with no manifest cannot be compared; out=%r" % out[-300:])
        self.assertIn("strict-shell-gate", out + err, "the message names the add-on")
        self.assertIsNotNone(data, "exit 4 still prints one JSON document")
        self.assertEqual(data.get("compared"), 0, "compared 0")

    def test_control_the_same_world_with_the_manifest_present_compares(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"])
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 0, "control for the two exit-4 rows above: with folder and manifest it compares")
        self.assertEqual(data.get("compared_addons"), 1, "and the add-on file was counted")


class TestDriftAddonsPresence(DriftCase):
    """No sync config: an add-on counts as installed when any of its manifest's hook files is in .claude/hooks/."""
    GATE = ".claude/hooks/bash-gate.py"

    def test_an_add_on_with_no_file_in_the_project_is_not_installed_and_not_compared(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], project=False, listed=False)
        rc, out, err, data = run_without_config(self.w)
        self.assertEqual(rc, 0, "an add-on nobody installed is no drift; out=%r err=%r" % (out[-300:], err[-300:]))
        self.assertKinds(data, [], "no finding for an add-on that is not installed")
        self.assertEqual(data.get("compared_addons"), 0, "and nothing was compared")

    def test_an_installed_identical_add_on_file_is_compared(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], listed=False)
        rc, out, err, data = run_without_config(self.w)
        self.assertEqual(rc, 0, "identical; out=%r err=%r" % (out[-300:], err[-300:]))
        self.assertEqual(data.get("compared_addons"), 1, "read by presence: the installed file was compared")

    def test_an_installed_add_on_file_that_differs_is_content_differs(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], listed=False)
        self.w.project_put(self.GATE, "# edited after the install\n")
        rc, out, err, data = run_without_config(self.w)
        self.assertEqual(rc, 1, "a counted finding exits 1; out=%r err=%r" % (out[-300:], err[-300:]))
        self.assertKinds(data, ["content-differs"], "found by presence, with no sync config")
        self.assertEqual(self.path_of(data, "content-differs"), [self.GATE])
        self.assertEqual(_findings(data)[0].get("owner"), "plugin")

    def test_control_with_a_sync_config_that_lists_no_add_on_the_same_file_is_not_compared(self):
        add_addon(self.w, "strict-shell-gate", ["bash-gate.py"], listed=False)
        self.w.project_put(self.GATE, "# edited after the install\n")
        rc, data = self.drift()
        self.assertEqual(rc, 0, "with a config the presence rule does not apply: an unlisted file is a local asset")
        self.assertKinds(data, [], "so the finding above came from the presence rule")


# =====================================================================================================
# D-3 and D-4 (angular-tailwind followups, t5)
#
# D-3: a disabled add-on hook that is still installed. Every plugin add-on is checked, listed in the sync
#   config or not. Names are each `disabled[].hook` and its `former_names`, compared case-insensitively.
#   A file `.claude/hooks/<name>` is the finding `.claude/hooks/<name>`; a row in settings.json or
#   settings.local.json is `<layer>:<event>:<name>`, kind `disabled-hook-installed`, owner `plugin`.
#   The parity fixtures below run the doctor and the install's `_disabled_hook_refusal` on the same project.
# D-4: add-on documents are compared when the sync config lists the add-on or any document exists.
# D-5: --drift never writes.
# =====================================================================================================
import auto_improve_finish_install as install  # noqa: E402

KIND_DISABLED = "disabled-hook-installed"
ADDON = "demo-addon"
RETIRED = "retired-advisor.py"
FORMER = "old-advisor.py"
DOCS_REL = ".claude/references"


def add_disabled_addon(world, hook=RETIRED, former=(), documents=(), name=ADDON, doc_text="# doc\n"):
    """A plugin add-on whose manifest declares one disabled hook and, optionally, documents."""
    base = world.plugin / ".claude" / "addons" / name
    (base / "documents").mkdir(parents=True, exist_ok=True)
    manifest = {af.KEY_HOOKS: [], af.KEY_HELPERS: [], af.KEY_ROWS: [], af.KEY_PREREQUISITES: [],
                af.KEY_KILL_SWITCHES: [], af.KEY_INSTALL_SKILL: "auto-improve-%s-install" % name,
                af.KEY_DISABLED: [{"hook": hook, "former_names": list(former)}] if hook else []}
    if documents:
        manifest[af.KEY_DOCUMENTS] = list(documents)
        for doc in documents:
            (base / "documents" / doc).write_text(doc_text, encoding="utf-8")
    (base / "addon.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def run_raw(world, mutate=None, *flags):
    """The real command line after write_all(), with `mutate()` free to corrupt what was written."""
    world.write_all()
    if mutate:
        mutate()
    argv = [sys.executable, "-B", str(DOCTOR), "--drift", "--project", str(world.project), "--plugin",
            str(world.plugin), "--json"] + list(flags)
    out = subprocess.run(argv, capture_output=True, text=True, env=world.env(), cwd=str(world.tmp), timeout=120)
    try:
        data = json.loads(out.stdout)
    except ValueError:
        data = None
    return out.returncode, data


def install_refusal(world, manifest):
    """The install's verdict on the same project: the refusal code, or None."""
    result = install._disabled_hook_refusal(world.project, world.home, ADDON, manifest)
    return None if result is None else result.get("code")


def _paths(data, kind=KIND_DISABLED):
    return sorted(_norm_path(f["path"]) for f in _findings(data) if f.get("kind") == kind)


class TestDriftDisabledHook(DriftCase):
    FILE = ".claude/hooks/" + RETIRED

    def setUp(self):
        super().setUp()
        self.manifest = add_disabled_addon(self.w, former=[FORMER])

    # ---- the parity fixtures: both readers agree
    def test_parity_a_file_only(self):
        self.w.project_put(self.FILE, "# retired\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data), [self.FILE])
        self.assertEqual([f["owner"] for f in _findings(data) if f["kind"] == KIND_DISABLED], ["plugin"])
        self.assertEqual(install_refusal(self.w, self.manifest), "disabled-hook-present")

    def test_parity_a_settings_json_row(self):
        self.w.project_register("PreToolUse", RETIRED)
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data), ["settings.json:PreToolUse:" + RETIRED])
        self.assertEqual(install_refusal(self.w, self.manifest), "disabled-hook-present")

    def test_parity_a_row_only_in_settings_local(self):
        self.w.project_register("PreToolUse", RETIRED, local=True)
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data), ["settings.local.json:PreToolUse:" + RETIRED])
        self.assertEqual(install_refusal(self.w, self.manifest), "disabled-hook-present")

    def test_parity_both_layers(self):
        self.w.project_register("PreToolUse", RETIRED)
        self.w.project_register("PostToolUse", RETIRED, local=True)
        rc, data = run_raw(self.w)
        self.assertEqual(_paths(data), ["settings.json:PreToolUse:" + RETIRED,
                                        "settings.local.json:PostToolUse:" + RETIRED])
        self.assertEqual(install_refusal(self.w, self.manifest), "disabled-hook-present")

    def test_parity_a_former_name_file_and_row(self):
        self.w.project_put(".claude/hooks/" + FORMER, "# former\n")
        self.w.project_register("PreToolUse", FORMER)
        rc, data = run_raw(self.w)
        self.assertEqual(_paths(data), [".claude/hooks/" + FORMER, "settings.json:PreToolUse:" + FORMER])
        self.assertEqual(install_refusal(self.w, self.manifest), "disabled-hook-present")

    def test_parity_an_unrelated_hook_is_silent_in_both(self):
        self.w.project_put(".claude/hooks/other.py", "# other\n")
        self.w.project_register("PreToolUse", "other.py")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0)
        self.assertEqual(_paths(data), [])
        self.assertIsNone(install_refusal(self.w, self.manifest))

    def test_parity_an_unreadable_layer_is_exit_4_and_an_install_problem(self):
        self.w.project_register("PreToolUse", RETIRED, local=True)

        def corrupt():
            (self.w.project / ".claude" / "settings.local.json").write_text("{not json", encoding="utf-8")

        rc, data = run_raw(self.w, corrupt)
        self.assertEqual(rc, 4)
        self.assertTrue(data.get("error"))
        self.assertIsNotNone(install_refusal(self.w, self.manifest))

    # ---- the three pinned divergences
    def test_a_user_layer_row_is_silent_in_both_readers_contrary_to_the_contract(self):
        user = self.w.home   # the install is handed the Claude home itself: its user layer is home/settings.json
        row = DriftWorld.exec_row("${CLAUDE_PROJECT_DIR}", RETIRED)
        (user / "settings.json").write_text(json.dumps(
            {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [row]}]}}), encoding="utf-8")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0, "the user layer is not project drift")
        self.assertEqual(_paths(data), [])
        # The contract pins this as a divergence (the install refuses). The code does not: the install keeps only
        # the project and local layers (_disabled_hook_refusal filters on row["layer"]). Pinned as it is.
        self.assertIsNone(install_refusal(self.w, self.manifest))

    def test_divergence_a_non_object_layer_reads_as_no_rows_in_the_doctor_and_is_refused_by_the_install(self):
        self.w.project_settings = []
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0, "the doctor reads a non-object layer as no rows, as it does today")
        self.assertEqual(_paths(data), [])
        self.assertIsNotNone(install_refusal(self.w, self.manifest))

    def test_divergence_a_gate_launch_row_is_found_by_the_doctor_and_not_by_the_install(self):
        self.w.project_register("PreToolUse", "gate-launch.py", gate=RETIRED)
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data), ["settings.json:PreToolUse:" + RETIRED])
        self.assertIsNone(install_refusal(self.w, self.manifest))

    # ---- controls
    def test_the_names_are_compared_case_insensitively(self):
        self.w.project_put(".claude/hooks/Retired-Advisor.PY", "# retired\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data), [".claude/hooks/Retired-Advisor.PY"])

    def test_a_clean_project_has_no_finding(self):
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0)
        self.assertEqual(_kinds(data), [])

    def test_an_add_on_with_no_disabled_hook_flags_nothing(self):
        add_disabled_addon(self.w, hook=None, name="plain-addon")
        self.w.project_put(".claude/hooks/plain.py", "# plain\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0)
        self.assertEqual(_paths(data), [])

    def test_the_add_on_need_not_be_listed_in_the_sync_config(self):
        self.assertNotIn(ADDON, self.w.config["addons"])
        self.w.project_put(self.FILE, "# retired\n")
        rc, data = run_raw(self.w)
        self.assertEqual(_paths(data), [self.FILE])

    def test_the_kind_is_a_known_finding_kind(self):
        import plugin_doctor
        self.assertIn(KIND_DISABLED, plugin_doctor.FINDING_KINDS)


class TestDriftDocuments(DriftCase):
    DOC = "RULES.md"
    REL = "%s/%s/%s" % (DOCS_REL, ADDON, DOC)

    def setUp(self):
        super().setUp()
        add_disabled_addon(self.w, hook=None, documents=[self.DOC, "OTHER.md"])

    def listed(self):
        self.w.config["addons"][ADDON] = []

    def test_the_destination_constant_equals_the_installs(self):
        import plugin_doctor
        self.assertEqual(plugin_doctor.ADDON_DOCUMENTS_REL, install.ADDON_DOCUMENTS_REL)

    def test_a_listed_add_on_with_identical_documents_is_counted_and_clean(self):
        self.listed()
        for doc in (self.DOC, "OTHER.md"):
            self.w.project_put("%s/%s/%s" % (DOCS_REL, ADDON, doc), "# doc\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0)
        self.assertEqual(data["compared_addons"], 2)
        self.assertEqual(data["compared"], 3)

    def test_a_document_that_differs_is_content_differs(self):
        self.listed()
        self.w.project_put(self.REL, "# edited\n")
        self.w.project_put("%s/%s/OTHER.md" % (DOCS_REL, ADDON), "# doc\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data, "content-differs"), [self.REL])
        self.assertEqual(data["compared_addons"], 2)

    def test_line_endings_and_a_bom_alone_are_not_drift(self):
        self.listed()
        self.w.project_put(self.REL, "# doc\n", eol="\r\n", bom=True)
        self.w.project_put("%s/%s/OTHER.md" % (DOCS_REL, ADDON), "# doc\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0)

    def test_a_listed_add_on_with_a_document_missing_in_the_project_is_one_sided(self):
        self.listed()
        self.w.project_put(self.REL, "# doc\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data, "one-sided"), ["%s/%s/OTHER.md" % (DOCS_REL, ADDON)])
        self.assertEqual(data["compared_addons"], 1)

    def test_a_document_only_in_the_project_is_one_sided(self):
        self.listed()
        (self.w.plugin / ".claude" / "addons" / ADDON / "documents" / self.DOC).unlink()
        self.w.project_put(self.REL, "# doc\n")
        self.w.project_put("%s/%s/OTHER.md" % (DOCS_REL, ADDON), "# doc\n")
        rc, data = run_raw(self.w)
        self.assertEqual(_paths(data, "one-sided"), [self.REL])

    def test_an_unlisted_add_on_with_no_document_in_the_project_is_not_compared(self):
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0)
        self.assertEqual(_kinds(data), [])
        self.assertEqual(data["compared_addons"], 0)

    def test_an_unlisted_add_on_is_compared_when_any_document_exists(self):
        self.w.project_put(self.REL, "# doc\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data, "one-sided"), ["%s/%s/OTHER.md" % (DOCS_REL, ADDON)])
        self.assertEqual(data["compared_addons"], 1)

    def test_an_add_on_that_declares_no_documents_is_not_compared(self):
        add_disabled_addon(self.w, hook=None, name="no-docs")
        self.w.config["addons"]["no-docs"] = []
        self.w.project_put("%s/no-docs/X.md" % DOCS_REL, "# stray\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 0)

    def test_the_findings_are_owned_by_the_plugin(self):
        self.listed()
        rc, data = run_raw(self.w)
        self.assertTrue(_findings(data))
        self.assertEqual({f["owner"] for f in _findings(data)}, {"plugin"})


class TestDriftNeverWrites(DriftCase):
    @staticmethod
    def _snapshot(root: Path):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def test_a_run_with_disabled_hooks_and_documents_changes_no_file(self):
        add_disabled_addon(self.w, former=[FORMER], documents=["RULES.md"])
        self.w.config["addons"][ADDON] = []
        self.w.project_put(".claude/hooks/" + RETIRED, "# retired\n")
        self.w.project_register("PreToolUse", FORMER)
        self.w.write_all()
        before = (self._snapshot(self.w.project), self._snapshot(self.w.plugin))
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(before, (self._snapshot(self.w.project), self._snapshot(self.w.plugin)))

    def test_a_run_with_a_dangling_row_changes_no_file(self):
        _dangling_function(self)
        self.w.project_register("UserPromptSubmit", "plain-language-guard.py")
        self.w.write_all()
        before = (self._snapshot(self.w.project), self._snapshot(self.w.plugin))
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1, "the dangling row is a counted finding")
        self.assertEqual(before, (self._snapshot(self.w.project), self._snapshot(self.w.plugin)),
                         "INV-1: the scan never writes, renames or deletes")

    def test_a_run_that_compares_nothing_still_exits_4(self):
        for tree in self.w.config["synced_trees"]:
            tree["files"] = []
        add_disabled_addon(self.w, documents=["RULES.md"])
        self.w.config["addons"][ADDON] = []
        self.w.project_put("%s/%s/RULES.md" % (DOCS_REL, ADDON), "# doc\n")
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 4, "documents count in compared_addons, never in compared")


# =====================================================================================================
# Dangling hook rows (issue 71, follow-up 1). Contract: .claude/concepts/2026-10-31-warn-on-unshipped-hook-rows.md
#   A project hook row whose launched .py file is not on disk is the finding `dangling-hook-row`, path
#   `<layer>:<event>:<matcher or *>:<role>:<raw>`, owner `plugin`, with a `remedy` key in --json. The scan reads
#   the project alone (`dangling_hook_rows(project)`), runs before the plugin comparison and survives exit 4.
# =====================================================================================================
import plugin_doctor as _pd  # noqa: E402

KIND_DANGLING = "dangling-hook-row"
REMEDY = "restore the file if the plugin still ships it, otherwise remove the row"
GUARD = "plain-language-guard.py"
HOOKS_VAR = "${CLAUDE_PROJECT_DIR}/.claude/hooks/"


def _dangling_function(test):
    """The public scan, or a clear failure naming the function that does not exist yet (RED, not an import error)."""
    fn = getattr(_pd, "dangling_hook_rows", None)
    if fn is None:
        test.fail("plugin_doctor.dangling_hook_rows(project) does not exist yet: the dangling-hook-row scan is not implemented")
    return fn


def _dang(data):
    return [f for f in _findings(data) if f.get("kind") == KIND_DANGLING]


def _dang_paths(data):
    return sorted(_norm_path(f["path"]) for f in _dang(data))


class DanglingCase(DriftCase):
    def add_row(self, event, row, *, matcher="Edit|Write", local=False, drop_matcher=False):
        target = self.w.project_settings
        if local:
            target = getattr(self.w, "project_local_settings", {"hooks": {}})
            self.w.project_local_settings = target
        group = {"hooks": [row]}
        if not drop_matcher:
            group["matcher"] = matcher
        target.setdefault("hooks", {}).setdefault(event, []).append(group)

    def exec_row(self, rel, *extra, var="${CLAUDE_PROJECT_DIR}"):
        return DriftWorld.exec_row(var, rel, *extra)

    def gate_files(self, *, launcher=True, body=True, gate=True):
        for present, name in ((launcher, "gate-launch.py"), (body, "_gate_launch.py"), (gate, "concept-gate.py")):
            if present:
                self.w.project_put(".claude/hooks/" + name, "# %s\n" % name)

    def gate_row(self):
        return self.exec_row("gate-launch.py", HOOKS_VAR + "concept-gate.py")

    def scan(self):
        fn = _dangling_function(self)
        self.w.write_all()
        return fn(self.w.project)

    def assertDangling(self, data, expected, why):
        self.assertEqual(_dang_paths(data), sorted(expected), why + " -- findings: " + json.dumps(_findings(data))[:700])


class TestDriftDanglingHookRow(DanglingCase):
    # ---- the two shapes of install the parent contract found
    def test_a_prompt_submit_row_to_a_deleted_guard_is_a_finding(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        rc, data = self.drift()
        self.assertEqual(rc, 1, "a dangling row is a counted finding")
        self.assertDangling(data, ["settings.json:UserPromptSubmit:*:launched:" + HOOKS_VAR + GUARD],
                            "an empty matcher is written *")
        self.assertEqual(_dang(data)[0].get("owner"), "plugin")

    def test_a_pre_0_9_8_direct_stop_row_without_a_matcher_is_a_finding_naming_its_event(self):
        self.add_row("Stop", self.exec_row(GUARD), drop_matcher=True)
        rc, data = self.drift()
        self.assertDangling(data, ["settings.json:Stop:*:launched:" + HOOKS_VAR + GUARD],
                            "no matcher is written *, and the event is named")

    def test_both_rows_give_two_findings_each_naming_its_event(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        self.add_row("Stop", self.exec_row(GUARD), drop_matcher=True)
        rc, data = self.drift()
        self.assertDangling(data, ["settings.json:Stop:*:launched:" + HOOKS_VAR + GUARD,
                                   "settings.json:UserPromptSubmit:*:launched:" + HOOKS_VAR + GUARD],
                            "two events, two findings")

    def test_the_same_rows_with_the_file_present_give_no_finding(self):
        _dangling_function(self)
        self.w.project_put(".claude/hooks/" + GUARD, "# guard\n")
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        self.add_row("Stop", self.exec_row(GUARD), drop_matcher=True)
        rc, data = self.drift()
        self.assertDangling(data, [], "negative control: nothing is missing")

    # ---- command forms and variable spellings
    def test_shell_form_with_quotes_is_a_finding_with_the_quotes_stripped(self):
        self.add_row("UserPromptSubmit", {"type": "command", "command": 'py -3 "$CLAUDE_PROJECT_DIR/.claude/hooks/%s"' % GUARD})
        rc, data = self.drift()
        self.assertDangling(data, ["settings.json:UserPromptSubmit:Edit|Write:launched:$CLAUDE_PROJECT_DIR/.claude/hooks/" + GUARD],
                            "raw is the token as written, quotes stripped")

    def test_the_percent_spelling_and_relative_spellings_resolve_to_the_project_root(self):
        for i, prefix in enumerate(("%CLAUDE_PROJECT_DIR%/.claude/hooks/", ".claude/hooks/", "./.claude/hooks/")):
            self.add_row("PreToolUse", {"type": "command", "command": "py", "args": ["-3", prefix + "gone.py"]},
                         matcher="m%d" % i)
        rc, data = self.drift()
        self.assertEqual(len(_dang(data)), 3, "all three spellings resolve to <project>/.claude/hooks, where nothing exists")

    def test_every_installer_folder_spelling_resolves_to_the_project_hooks_folder(self):
        spellings = list(install._PROJECT_HOOK_DIRS)
        self.assertTrue(spellings)
        for i, folder in enumerate(spellings):
            self.add_row("PreToolUse", {"type": "command", "command": "py", "args": ["-3", folder + "/missing%d.py" % i]},
                         matcher="gone%d" % i)
            self.w.project_put(".claude/hooks/present%d.py" % i, "# p\n")
            self.add_row("PreToolUse", {"type": "command", "command": "py", "args": ["-3", folder + "/present%d.py" % i]},
                         matcher="here%d" % i)
        rc, data = self.drift()
        self.assertEqual(len(_dang(data)), len(spellings),
                         "INV-9: each spelling finds the existing file (no finding) and misses the absent one (one finding); "
                         + json.dumps(_findings(data))[:600])

    def test_a_windows_style_absolute_raw_path_keeps_its_colon_readable(self):
        gone = str(self.w.tmp / "elsewhere" / "gone-hook.py")
        self.add_row("Stop", {"type": "command", "command": "py", "args": ["-3", gone]})
        rc, data = self.drift()
        paths = [f["path"] for f in _dang(data)]
        self.assertEqual(len(paths), 1, "an absolute path that is not a file is a finding; got %r" % paths)
        self.assertEqual(paths[0].split(":", 4)[4], gone, "raw is everything after the fourth colon, as written")

    def test_an_existing_absolute_path_is_no_finding(self):
        _dangling_function(self)
        here = self.w.project_put("elsewhere/real.py", "# r\n")
        self.add_row("Stop", {"type": "command", "command": "py", "args": ["-3", str(here)]})
        rc, data = self.drift()
        self.assertDangling(data, [], "absolute and a file")

    # ---- gate launcher roles
    def test_a_gate_launcher_row_with_everything_present_is_clean(self):
        _dangling_function(self)
        self.gate_files()
        self.add_row("PreToolUse", self.gate_row())
        rc, data = self.drift()
        self.assertDangling(data, [], "negative control")

    def test_a_missing_launcher_is_one_finding_with_role_launched(self):
        self.gate_files(launcher=False, body=False, gate=True)
        self.add_row("PreToolUse", self.gate_row())
        rc, data = self.drift()
        self.assertDangling(data, ["settings.json:PreToolUse:Edit|Write:launched:" + HOOKS_VAR + "gate-launch.py"],
                            "a missing launcher is one finding; its body is not checked then")

    def test_a_missing_launcher_body_is_role_launcher_body(self):
        self.gate_files(body=False)
        self.add_row("PreToolUse", self.gate_row())
        rc, data = self.drift()
        self.assertDangling(data, ["settings.json:PreToolUse:Edit|Write:launcher-body:" + HOOKS_VAR + "_gate_launch.py"],
                            "the body beside the launcher; a missing body blocks like a missing launcher")

    def test_a_missing_gate_is_role_gate_argument(self):
        self.gate_files(gate=False)
        self.add_row("PreToolUse", self.gate_row())
        rc, data = self.drift()
        self.assertDangling(data, ["settings.json:PreToolUse:Edit|Write:gate-argument:" + HOOKS_VAR + "concept-gate.py"],
                            "the token after the launcher; a missing gate returns a block")

    # ---- layers, matchers, dedup
    def test_settings_local_json_is_named_as_its_layer(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="", local=True)
        rc, data = self.drift()
        self.assertDangling(data, ["settings.local.json:UserPromptSubmit:*:launched:" + HOOKS_VAR + GUARD], "layer is named")

    def test_two_matchers_give_two_findings(self):
        self.add_row("PreToolUse", self.exec_row("gone.py"), matcher="Edit")
        self.add_row("PreToolUse", self.exec_row("gone.py"), matcher="Bash")
        rc, data = self.drift()
        self.assertEqual(len(_dang(data)), 2, "INV-4: rows that differ only in matcher are two findings")

    def test_identical_rows_in_one_layer_collapse_into_one_finding(self):
        self.add_row("PreToolUse", self.exec_row("gone.py"))
        self.add_row("PreToolUse", self.exec_row("gone.py"))
        rc, data = self.drift()
        self.assertEqual(len(_dang(data)), 1, "findings are deduplicated by (kind, path)")

    # ---- skipped forms (INV-3)
    def test_forms_the_doctor_cannot_resolve_are_never_reported(self):
        _dangling_function(self)
        for i, token in enumerate(("${CLAUDE_PLUGIN_ROOT}/.claude/hooks/gone.py", "%OTHER%/hooks/gone.py",
                                   "$HOME/hooks/gone.py", "${OTHER}/hooks/gone.py", "~/hooks/gone.py")):
            self.add_row("PreToolUse", {"type": "command", "command": "py", "args": ["-3", token]}, matcher="m%d" % i)
        rc, data = self.drift()
        self.assertDangling(data, [], "INV-3: no guessing")

    def test_a_row_that_is_not_a_py_file_is_never_reported(self):
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command", "command": "node", "args": ["${CLAUDE_PROJECT_DIR}/tools/gone.js"]})
        rc, data = self.drift()
        self.assertDangling(data, [], "only .py paths are checked")

    def test_the_user_settings_layer_is_never_scanned(self):
        _dangling_function(self)
        row = {"type": "command", "command": "py", "args": ["-3", HOOKS_VAR + "gone.py"]}
        for base in (self.w.home / ".claude", self.w.config_dir):
            base.mkdir(parents=True, exist_ok=True)
            (base / "settings.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [row]}]}}), encoding="utf-8")
        rc, data = self.drift()
        self.assertDangling(data, [], "INV-8: project layers only")

    # ---- review round: shell-form quoting (reviewer F1)
    def _shell_variants(self):
        return (("$CLAUDE_PROJECT_DIR", 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/x.py'),
                ("%CLAUDE_PROJECT_DIR%", 'py -3 "%CLAUDE_PROJECT_DIR%"\\.claude\\hooks\\x.py'))

    def test_a_shell_form_row_with_the_variable_quoted_apart_from_the_path_is_no_finding_when_the_file_exists(self):
        _dangling_function(self)
        self.w.project_put(".claude/hooks/x.py", "# x\n")
        for i, (_var, command) in enumerate(self._shell_variants()):
            self.add_row("PreToolUse", {"type": "command", "command": command}, matcher="m%d" % i)
        rc, data = self.drift()
        self.assertDangling(data, [], "the closing quote before the path must not leak into the resolved path")

    def test_a_shell_form_row_with_the_variable_quoted_apart_from_the_path_is_one_finding_when_the_file_is_deleted(self):
        _dangling_function(self)
        for i, (var, command) in enumerate(self._shell_variants()):
            self.add_row("PreToolUse", {"type": "command", "command": command}, matcher="m%d" % i)
        rc, data = self.drift()
        found = _dang(data)
        self.assertEqual(len(found), 2, "one finding per row; got " + json.dumps(_findings(data))[:600])
        for (var, _cmd), finding in zip(self._shell_variants(), sorted(found, key=lambda f: f["path"])):
            parts = finding["path"].split(":", 4)
            self.assertEqual(parts[1:4], ["PreToolUse", parts[2], "launched"], "event and role are named")
            self.assertNotIn('"', parts[4], "raw is as written with the quotes removed")
            self.assertTrue(parts[4].startswith(var) and parts[4].endswith("x.py"), "raw names the variable and file: %r" % parts[4])

    def test_a_quoted_absolute_path_with_a_space_is_read_whole(self):
        _dangling_function(self)
        here = self.w.project_put("Program Files/tool dir/x.py", "# x\n")
        self.add_row("Stop", {"type": "command", "command": 'py -3 "%s"' % here})
        rc, data = self.drift()
        self.assertDangling(data, [], "a quoted absolute path with spaces that is a file is no finding")

    def test_a_gate_launch_shell_row_with_two_quoted_arguments_is_clean_when_files_exist_and_names_the_gate_when_not(self):
        _dangling_function(self)
        command = ('py -3 "$CLAUDE_PROJECT_DIR/.claude/hooks/gate-launch.py" '
                   '"$CLAUDE_PROJECT_DIR/.claude/hooks/concept-gate.py"')
        self.gate_files()
        self.add_row("PreToolUse", {"type": "command", "command": command})
        rc, data = self.drift()
        self.assertDangling(data, [], "both quoted tokens resolve to existing files")
        self.w.project_remove(".claude/hooks/concept-gate.py")
        rc, data = self.drift()
        self.assertEqual([f["path"].split(":", 4)[3] for f in _dang(data)], ["gate-argument"],
                         "only the gate argument is missing; got " + json.dumps(_findings(data))[:500])

    # ---- second review round: false positives (INV-2, INV-3)
    def test_an_apostrophe_inside_a_double_quoted_existing_path_is_no_finding(self):
        _dangling_function(self)
        here = self.w.project_put("O'Brien dir/y.py", "# y\n")
        self.w.project_put(".claude/hooks/ok.py", "# ok\n")
        self.add_row("PreToolUse", {"type": "command", "command": 'python "%s"' % here.as_posix()}, matcher="abs")
        self.add_row("PreToolUse", {"type": "command", "command": 'python "${CLAUDE_PROJECT_DIR}/O\'Brien dir/y.py"'},
                     matcher="var")
        rc, data = self.drift()
        self.assertDangling(data, [], "INV-2: the file exists; an apostrophe inside double quotes is not a quote")

    def test_an_apostrophe_inside_a_double_quoted_deleted_path_is_one_finding_keeping_the_apostrophe(self):
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command", "command": 'python "${CLAUDE_PROJECT_DIR}/O\'Brien dir/y.py"'})
        rc, data = self.drift()
        found = _dang(data)
        self.assertEqual(len(found), 1, "one finding; got " + json.dumps(_findings(data))[:500])
        raw = found[0]["path"].split(":", 4)[4]
        self.assertIn("O'Brien dir", raw, "raw still contains the apostrophe: %r" % raw)

    def test_a_backslash_escaped_space_in_a_shell_form_row_is_never_reported(self):
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command",
                                    "command": "python ${CLAUDE_PROJECT_DIR}/.claude/hooks/x\\ y.py"})
        rc, data = self.drift()
        self.assertDangling(data, [], "INV-3: an escaped space is unresolvable, so it is skipped even if absent")

    @unittest.skipUnless(os.name == "nt", "a Git Bash drive path is only meaningful on Windows")
    def test_a_git_bash_drive_path_is_never_reported_on_windows(self):
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command", "command": "python /c/Users/nobody-here/hooks/x.py"})
        rc, data = self.drift()
        self.assertDangling(data, [], "INV-3: /c/... is not resolvable by the doctor, so it is skipped")

    # ---- review round: near-miss variable names (reviewer F2, INV-3)
    def test_a_variable_name_that_only_begins_with_the_project_variable_is_never_reported(self):
        _dangling_function(self)
        tokens = ("$CLAUDE_PROJECT_DIR_ALT/.claude/hooks/x.py", "${CLAUDE_PROJECT_DIR}_ALT/.claude/hooks/x.py",
                  "%CLAUDE_PROJECT_DIR%_ALT/.claude/hooks/x.py", "$CLAUDE_PROJECT_DIRS/.claude/hooks/x.py")
        for i, token in enumerate(tokens):
            self.add_row("PreToolUse", {"type": "command", "command": "py", "args": ["-3", token]}, matcher="m%d" % i)
        rc, data = self.drift()
        self.assertDangling(data, [], "INV-3: a different variable is unresolvable, not the project folder plus a suffix")

    def test_a_second_variable_after_the_project_variable_is_never_reported(self):
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command", "command": "py",
                                    "args": ["-3", "${CLAUDE_PROJECT_DIR}/$X/gone.py"]})
        rc, data = self.drift()
        self.assertDangling(data, [], "INV-3: a second variable cannot be resolved")

    # ---- review round: a read error is a skipped row (reviewer F4)
    def test_an_oserror_while_checking_a_path_skips_that_row_and_does_not_crash_the_scan(self):
        import pathlib
        from unittest import mock
        fn = _dangling_function(self)
        self.add_row("PreToolUse", self.exec_row("unreadable.py"), matcher="a")
        self.add_row("PreToolUse", self.exec_row("gone.py"), matcher="b")
        self.w.write_all()
        original = pathlib.Path.is_file

        def is_file(path_self, *a, **kw):
            if path_self.name == "unreadable.py":
                raise PermissionError("denied: " + path_self.name)
            return original(path_self, *a, **kw)

        with mock.patch.object(pathlib.Path, "is_file", is_file):
            try:
                found = list(fn(self.w.project))
            except OSError as exc:
                self.fail("the scan crashed with %r instead of skipping the row" % exc)
        paths = [_norm_path(f.path) for f in found]
        self.assertEqual(len(paths), 1, "only the readable, missing file is reported; got %r" % paths)
        self.assertTrue(paths[0].endswith("gone.py"), "the unreadable row is skipped, not reported: %r" % paths)

    # ---- review round: pinned behaviour (critic F4-F6)
    def test_a_directory_named_like_a_py_file_counts_as_dangling(self):
        self.w.project_put(".claude/hooks/x.py/inner.txt", "dir\n")
        self.add_row("Stop", self.exec_row("x.py"))
        rc, data = self.drift()
        self.assertDangling(data, ["settings.json:Stop:Edit|Write:launched:" + HOOKS_VAR + "x.py"],
                            "INV-2: found only when the path is not a regular file; a directory is not")

    def test_an_uppercase_py_extension_is_checked_like_a_lowercase_one(self):
        self.add_row("Stop", self.exec_row("GONE.PY"))
        rc, data = self.drift()
        self.assertDangling(data, ["settings.json:Stop:Edit|Write:launched:" + HOOKS_VAR + "GONE.PY"],
                            "the extension test is case-insensitive (Windows file names), so .PY is a .py file")

    def test_a_settings_file_with_a_byte_order_mark_is_read(self):
        self.add_row("Stop", self.exec_row("gone.py"))
        self.w.write_all()
        settings = self.w.project / ".claude" / "settings.json"
        settings.write_bytes(b"\xef\xbb\xbf" + settings.read_bytes())
        found = _dangling_function(self)(self.w.project)
        self.assertEqual(len(found), 1, "a BOM-prefixed settings.json is still read")

    # ---- review round: the two findings of one row (critic F2, product decision)
    def test_a_row_that_is_both_a_disabled_hook_and_dangling_gives_both_findings(self):
        """Decision (critic F2): the two findings answer different questions. `disabled-hook-installed` says the
        add-on retired this hook; `dangling-hook-row` says the row launches a file that is not on disk. A row that is
        both is reported under BOTH kinds, once each; neither kind suppresses the other."""
        _dangling_function(self)
        add_disabled_addon(self.w, former=[FORMER])
        self.w.project_register("PreToolUse", RETIRED)
        rc, data = run_raw(self.w)
        self.assertEqual(rc, 1)
        self.assertEqual(_paths(data), ["settings.json:PreToolUse:" + RETIRED], "the disabled-hook finding")
        self.assertEqual(len(_paths(data, KIND_DANGLING)), 1, "and the dangling-row finding: " + json.dumps(_findings(data))[:500])

    # ---- report shape
    def test_merged_findings_are_sorted_with_a_kind_that_sorts_after_the_dangling_kind(self):
        """Critic F1: with a one-sided finding (sorts after dangling-hook-row) an unsorted concatenation of the
        comparison and the scan would put one-sided first."""
        self.w.plugin_remove(".claude/hooks/b.py")
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        rc, data = self.drift()
        kinds = [f["kind"] for f in _findings(data)]
        self.assertEqual(kinds, [KIND_DANGLING, "one-sided"], "dangling-hook-row sorts before one-sided; got %r" % kinds)
        order = [(f["kind"], f["path"]) for f in _findings(data)]
        self.assertEqual(order, sorted(order))

    def test_the_json_finding_carries_the_remedy_and_other_kinds_do_not(self):
        self.w.project_put(".claude/hooks/b.py", "# b changed here\n")
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        rc, data = self.drift()
        dangling = _dang(data)
        self.assertEqual(len(dangling), 1, "fixture: one dangling finding; got " + json.dumps(_findings(data))[:400])
        self.assertEqual(dangling[0].get("remedy"), REMEDY, "the fixed remedy text names both repairs")
        self.assertEqual(sorted(dangling[0]), ["kind", "owner", "path", "remedy"])
        others = [f for f in _findings(data) if f.get("kind") != KIND_DANGLING]
        self.assertTrue(others, "fixture: a content-differs finding rides along")
        self.assertTrue(all(sorted(f) == ["kind", "owner", "path"] for f in others),
                        "every other kind keeps its exact shape")
        order = [(f["kind"], f["path"]) for f in _findings(data)]
        self.assertEqual(order, sorted(order), "both sets are sorted by (kind, path)")

    def test_the_text_output_prints_the_remedy_after_the_finding(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        rc, out, err, _ = self.w.run(as_json=False)
        self.assertEqual(rc, 1)
        self.assertIn(KIND_DANGLING, out, "the finding is printed; out=%r" % out[-400:])
        self.assertIn(REMEDY, out, "the remedy is printed")

    def test_the_finding_still_counts_under_ignore_repo_owned(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        rc, data = self.drift("--ignore-repo-owned")
        self.assertEqual(rc, 1, "INV-6: owner plugin is always counted")
        self.assertEqual(len(_dang(data)), 1, "the finding is listed; got " + json.dumps(_findings(data))[:400])

    def test_finding_kinds_lists_the_new_kind(self):
        self.assertIn(KIND_DANGLING, _pd.FINDING_KINDS)

    # ---- survival (INV-7)
    def test_with_no_plugin_found_the_finding_is_listed_beside_the_error_and_exit_is_4(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        rc, out, err, data = self.w.run(plugin=None)
        self.assertEqual(rc, 4, "the comparison could not run")
        self.assertTrue(data and data.get("error"), "error holds the cause; out=%r" % out[-300:])
        self.assertDangling(data, ["settings.json:UserPromptSubmit:*:launched:" + HOOKS_VAR + GUARD],
                            "the scan does not need a plugin")

    def test_with_zero_file_pairs_the_finding_is_listed_beside_the_error_and_exit_is_4(self):
        for tree in self.w.config["synced_trees"]:
            tree["files"] = []
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 4)
        self.assertTrue(data and data.get("error"))
        self.assertEqual(len(_dang(data)), 1, "listed beside error; out=%r" % out[-300:])

    def test_the_text_output_prints_findings_before_the_cannot_compare_line(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        rc, out, err, _ = self.w.run(plugin=None, as_json=False)
        self.assertEqual(rc, 4)
        self.assertIn(KIND_DANGLING, out, "findings are printed on exit 4; out=%r" % out[-400:])
        self.assertLess(out.index(KIND_DANGLING), out.index("cannot compare"), "before the 'cannot compare' line")

    def test_an_unparseable_local_layer_is_skipped_by_the_scan_and_the_comparison_exits_4(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        self.w.write_all()
        (self.w.project / ".claude" / "settings.local.json").write_text("{ not json", encoding="utf-8")
        argv = [sys.executable, "-B", str(DOCTOR), "--drift", "--project", str(self.w.project),
                "--plugin", str(self.w.plugin), "--json"]
        out = subprocess.run(argv, capture_output=True, text=True, env=self.w.env(), timeout=120)
        try:
            data = json.loads(out.stdout)
        except ValueError:
            data = None
        self.assertEqual(out.returncode, 4, "the comparison reports the parse error")
        self.assertEqual(len(_dang(data or {})), 1, "INV-8: the readable layer is still scanned; out=%r" % out.stdout[-300:])

    # ---- third review round: anything before the launched word can change where it runs (INV-2, INV-3)
    def _no_finding_for(self, commands, why):
        """Each command launches g.py, which exists under the project's .claude/hooks; none may be reported."""
        _dangling_function(self)
        self.w.project_put(".claude/hooks/g.py", "# g\n")
        for i, command in enumerate(commands):
            self.add_row("PreToolUse", {"type": "command", "command": command}, matcher="m%d" % i)
        rc, data = self.drift()
        self.assertDangling(data, [], why + " -- findings: " + json.dumps(_findings(data))[:600])

    def test_a_cd_into_the_hooks_folder_before_a_bare_script_name_is_no_finding(self):
        self._no_finding_for(['cd "$CLAUDE_PROJECT_DIR/.claude/hooks" && python g.py'],
                             "INV-2: cd moves the working folder, so the bare name is not under the project root")

    def test_a_cd_with_a_semicolon_before_a_bare_script_name_is_no_finding(self):
        self._no_finding_for(["cd .claude/hooks; python g.py"], "INV-2: a cd before the launched word")

    def test_pushd_and_set_location_before_a_bare_script_name_are_no_finding(self):
        self._no_finding_for(["pushd .claude\\hooks && python g.py", "Set-Location .claude/hooks; python g.py"],
                             "INV-2: pushd and Set-Location also move the working folder")

    def test_a_separator_before_the_launched_word_is_no_finding(self):
        self._no_finding_for(["A=1 || python g.py", "echo hi | python g.py", "echo hi & python g.py"],
                             "INV-2: the launched word follows a separator, so earlier words may change where it runs")

    def test_a_nested_shell_command_string_is_no_finding(self):
        self._no_finding_for(["bash -c 'python .claude/hooks/g.py'", 'cmd /c "py .claude\\hooks\\g.py"',
                              'cmd /k "py .claude\\hooks\\g.py"',
                              'powershell -Command "python .claude/hooks/g.py"',
                              'pwsh -command "python .claude/hooks/g.py"'],
                             "INV-3: a word after -c, /c, /k, -Command or -command is a nested shell string, not resolvable")

    def test_a_cd_to_the_project_root_before_a_deleted_script_is_also_skipped(self):
        """Pins the accepted cost: any row with a word before the launched word is skipped, so even this deleted
        script (`cd` to the project root, then a path that does not exist) gives no finding. The doctor does not
        try to evaluate what the earlier word does; a missed true positive is preferred to a false positive."""
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command",
                                    "command": 'cd "$CLAUDE_PROJECT_DIR" && python .claude/hooks/missing.py'})
        rc, data = self.drift()
        self.assertDangling(data, [], "accepted cost: INV-3 skip wins over reporting a true positive")

    # ---- regression guards: these pass today and must keep passing
    def test_guard_a_quoted_path_with_a_space_that_is_deleted_is_still_one_finding(self):
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command", "command": 'python "my hooks/x.py"'})
        rc, data = self.drift()
        self.assertEqual(len(_dang(data)), 1, "guard: findings " + json.dumps(_findings(data))[:500])

    def test_guard_a_project_variable_path_that_is_deleted_is_still_one_finding(self):
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command", "command": "python ${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py"})
        rc, data = self.drift()
        self.assertEqual(len(_dang(data)), 1, "guard: findings " + json.dumps(_findings(data))[:500])

    def test_guard_a_separator_after_the_launched_word_still_checks_the_script(self):
        _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command", "command": "python .claude/hooks/x.py 2>/dev/null || true"})
        rc, data = self.drift()
        found = _dang(data)
        self.assertEqual(len(found), 1, "guard: findings " + json.dumps(_findings(data))[:500])
        self.assertTrue(found[0]["path"].endswith("x.py"), "the launched script is the one checked: %r" % found[0]["path"])

    # ---- fourth review round: the shell-form rule is a whitelist (INV-2, INV-3)
    def _whitelist_no_finding(self, commands, why):
        """x.py exists under the project's .claude/hooks. Each command is its own row (matcher w<i>) and its own
        subTest, so one wrongly reported row does not hide the others."""
        _dangling_function(self)
        self.w.project_put(".claude/hooks/x.py", "# x\n")
        for i, command in enumerate(commands):
            self.add_row("PreToolUse", {"type": "command", "command": command}, matcher="w%d" % i)
        rc, data = self.drift()
        found = _dang(data)
        for i, command in enumerate(commands):
            with self.subTest(command=command):
                mine = [f["path"] for f in found if ":PreToolUse:w%d:" % i in f["path"]]
                self.assertEqual(mine, [], why + " -- reported: %r" % mine)

    def test_c1_a_nested_shell_with_a_non_python_first_word_is_no_finding(self):
        self._whitelist_no_finding([
            'bash -lc "python3 .claude/hooks/x.py"',
            'sh -ec "python3 .claude/hooks/x.py"',
            'cmd /C "python .claude\\hooks\\x.py"',
            'cmd.exe /d /C "python .claude\\hooks\\x.py"',
            'powershell -C "python .claude/hooks/x.py"',
        ], "whitelist: the first word is not a python interpreter, so the row is skipped")

    def test_c2_a_multi_line_command_is_no_finding(self):
        self._whitelist_no_finding([
            "export A=1\ncd .claude/hooks\npython x.py",
            "set -e\ncd .claude/hooks\npython x.py",
        ], "whitelist: a newline outside quotes means earlier lines may change the working folder")

    def test_c3_a_launcher_that_sets_the_working_folder_is_no_finding(self):
        self._whitelist_no_finding([
            "uv run --directory .claude/hooks x.py",
            "uv --directory .claude/hooks run x.py",
            "env -C .claude/hooks python x.py",
            "env --chdir=.claude/hooks python x.py",
            "Start-Process python -WorkingDirectory .claude/hooks -ArgumentList x.py",
            "docker run -w /w python x.py",
        ], "whitelist: the first word is not a python interpreter, so the row is skipped")

    def test_w1_an_env_prefix_before_the_interpreter_is_no_finding(self):
        self._whitelist_no_finding(["A=1 PYTHONSTARTUP=s.py python .claude/hooks/x.py"],
                                   "whitelist: an env assignment is not a python word, so the row is skipped")

    def _whitelist_one_finding(self, commands, why):
        """x.py is deleted; each command must give exactly one finding (its own row and subTest)."""
        _dangling_function(self)
        for i, command in enumerate(commands):
            self.add_row("PreToolUse", {"type": "command", "command": command}, matcher="w%d" % i)
        rc, data = self.drift()
        found = _dang(data)
        for i, command in enumerate(commands):
            with self.subTest(command=command):
                mine = [f["path"] for f in found if ":PreToolUse:w%d:" % i in f["path"]]
                self.assertEqual(len(mine), 1, why + " -- reported: %r" % mine)

    def test_guard_whitelisted_shell_forms_that_are_deleted_are_each_one_finding(self):
        self._whitelist_one_finding([
            'python "my hooks/x.py"',
            "python ${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py",
            'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/x.py',
            'py -3 "%CLAUDE_PROJECT_DIR%"\\.claude\\hooks\\x.py',
            "python -B -u .claude/hooks/x.py",
            "PYTHON3.EXE .claude/hooks/x.py",
        ], "guard: an allowed interpreter and simple flags keep the row checked")

    def test_guard_a_gate_launcher_shell_row_with_the_gate_missing_is_one_gate_argument_finding(self):
        _dangling_function(self)
        self.gate_files(gate=False)
        self.add_row("PreToolUse", {"type": "command",
                                    "command": "python ${CLAUDE_PROJECT_DIR}/.claude/hooks/gate-launch.py concept-gate.py"})
        rc, data = self.drift()
        found = _dang(data)
        self.assertEqual(len(found), 1, "guard: findings " + json.dumps(_findings(data))[:500])
        self.assertIn(":gate-argument:", found[0]["path"], "the missing gate is named by its role")

    # ---- fifth review round: the whitelist also applies to exec form, backticks, metacharacters, NUL
    def _rows_no_finding(self, rows, why):
        """x.py and the gate files exist. Each row (a dict) is its own matcher r<i> and its own subTest."""
        _dangling_function(self)
        self.w.project_put(".claude/hooks/x.py", "# x\n")
        self.gate_files()
        for i, row in enumerate(rows):
            self.add_row("PreToolUse", dict(row, type="command"), matcher="r%d" % i)
        rc, data = self.drift()
        found = _dang(data)
        for i, row in enumerate(rows):
            with self.subTest(row=json.dumps(row)):
                mine = [f["path"] for f in found if ":PreToolUse:r%d:" % i in f["path"]]
                self.assertEqual(mine, [], why + " -- reported: %r" % mine)

    def _rows_one_finding(self, rows, why):
        """Nothing exists. Each row is its own matcher r<i> and its own subTest and gives exactly one finding."""
        _dangling_function(self)
        for i, row in enumerate(rows):
            self.add_row("PreToolUse", dict(row, type="command"), matcher="r%d" % i)
        rc, data = self.drift()
        found = _dang(data)
        for i, row in enumerate(rows):
            with self.subTest(row=json.dumps(row)):
                mine = [f["path"] for f in found if ":PreToolUse:r%d:" % i in f["path"]]
                self.assertEqual(len(mine), 1, why + " -- reported: %r" % mine)

    def test_c1_exec_form_with_a_non_python_command_is_no_finding(self):
        self._rows_no_finding([
            {"command": "bash", "args": ["-lc", "python3 .claude/hooks/x.py"]},
            {"command": "powershell", "args": ["-NoProfile", "-Command", "py -3 .claude/hooks/x.py"]},
            {"command": "cmd", "args": ["/C", "python .claude\\hooks\\x.py"]},
            {"command": "uv", "args": ["run", "x.py"]},
            {"command": "uv", "args": ["run", ".claude/hooks/x.py"]},
            {"command": "C:\\Tools\\BASH.EXE", "args": ["-c", "python3 .claude/hooks/x.py"]},
        ], "whitelist: the exec-form command is not a python interpreter, so the row is skipped")

    def test_c1_exec_form_with_a_python_command_and_a_non_simple_flag_is_no_finding(self):
        self._rows_no_finding([
            {"command": "python3", "args": ["-m", "pytest", ".claude/hooks/x.py"]},
            {"command": "python", "args": ["-c", "import x", ".claude/hooks/x.py"]},
            {"command": "python", "args": ["-X", "utf8", ".claude/hooks/x.py"]},
        ], "whitelist: only -3, -3.N, -2, -B, -u, -E, -I, -s, -S, -O, -OO may precede the script")

    def test_guard_exec_form_rows_with_an_allowed_interpreter_and_simple_flags_that_are_deleted_are_each_one_finding(self):
        self._rows_one_finding([
            {"command": "python3", "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py"]},
            {"command": "py", "args": ["-3", "${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py"]},
            {"command": "python", "args": ["-B", "-u", "${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py"]},
            {"command": "PYTHON3.EXE", "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py"]},
            {"command": "python3.12", "args": ["-3.12", "-OO", "${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py"]},
            {"command": "pythonw", "args": ["-E", "-s", "-S", "-I", "-O", "${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py"]},
            {"command": "python2", "args": ["-2", "${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py"]},
        ], "guard: an allowed interpreter with simple flags keeps the exec-form row checked")

    def test_guard_the_installer_written_gate_launch_row_gives_one_finding_per_missing_file(self):
        cases = ((False, True, True, "launched"), (True, False, True, "launcher-body"), (True, True, False, "gate-argument"))
        for launcher, body, gate, role in cases:
            with self.subTest(role=role):
                for name in ("gate-launch.py", "_gate_launch.py", "concept-gate.py"):
                    (self.w.project / ".claude" / "hooks" / name).unlink(missing_ok=True)
                self.gate_files(launcher=launcher, body=body, gate=gate)
                self.w.project_settings.get("hooks", {}).clear()
                self.add_row("PreToolUse", self.gate_row())
                rc, data = self.drift()
                self.assertEqual([f["path"].split(":", 4)[3] for f in _dang(data)], [role],
                                 "guard: findings " + json.dumps(_findings(data))[:500])

    def test_c2_a_backtick_command_substitution_in_a_path_is_never_reported(self):
        self._rows_no_finding([
            {"command": 'python3 "`git rev-parse --show-toplevel`/.claude/hooks/x.py"'},
            {"command": 'python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/gate-launch.py '
                        '"`pwd`/.claude/hooks/concept-gate.py"'},
            {"command": 'python3 `pwd`/.claude/hooks/x.py'},
        ], "INV-3: a backtick substitution cannot be resolved (launched and gate-argument positions)")

    def test_m1_shell_metacharacters_in_a_path_are_never_reported(self):
        self._rows_no_finding([
            {"command": "python3 .claude/hooks/x*.py"},
            {"command": "python3 .claude/hooks/[x].py"},
            {"command": "python3 <.claude/hooks/x.py"},
            {"command": "python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/gate-launch.py concept-gate.py;x.py"},
            {"command": "python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/gate-launch.py <.claude/hooks/concept-gate.py"},
        ], "INV-3: a glob, a bracket or a redirection is not a literal path, so the row is skipped")

    def test_m4_a_nul_character_in_a_script_path_does_not_crash_and_is_skipped(self):
        fn = _dangling_function(self)
        self.add_row("PreToolUse", {"type": "command", "command": 'python3 ".claude/hooks/x\u0000.py"'}, matcher="shell")
        self.add_row("PreToolUse", {"type": "command", "command": "python3", "args": [".claude/hooks/y\u0000.py"]},
                     matcher="exec")
        self.add_row("PreToolUse", {"type": "command", "command": "python3",
                                    "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/gate-launch.py", "c\u0000.py"]},
                     matcher="gate")
        self.w.write_all()
        try:
            found = list(fn(self.w.project))
        except Exception as exc:  # noqa: BLE001 - any exception is the defect under test
            self.fail("dangling_hook_rows crashed with %r on a NUL in a path instead of skipping the row" % exc)
        self.assertEqual([f.path for f in found if "NUL" in f.path or "\u0000" in f.path], [],
                         "the NUL rows are skipped, not reported")
        rc, out, err, data = self.w.run()
        self.assertNotIn("Traceback", err, "--drift must not print a traceback; stderr=%r" % err[-400:])
        self.assertFalse([f for f in _dang(data or {}) if "\u0000" in f["path"]], "no NUL finding in the report")

    def test_m2_quoted_spaces_and_a_quoted_variable_are_read_the_same_by_both_readers(self):
        """Behavioural guard: the dangling scan and registered-twice tokenise these shell rows identically."""
        self.w.project_register("PreToolUse", "p1.py", matcher="exec")
        self.add_row("Stop", {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/p2.py'},
                     matcher="shell")
        self.w.plugin_register("PreToolUse", "p1.py", matcher="p")
        self.w.plugin_register("Stop", "p2.py", matcher="p")
        self.add_row("Stop", {"type": "command", "command": 'python3 "my hooks/p3 x.py"'}, matcher="spaces")
        rc, data = self.drift()
        twice = sorted(tuple(f["path"].split(":", 1)) for f in _findings(data) if f["kind"] == "registered-twice")
        self.assertEqual(twice, [("PreToolUse", "p1.py"), ("Stop", "p2.py")],
                         "fixture: a quoted-variable shell row is a double registration; got "
                         + json.dumps(_findings(data))[:600])
        import posixpath
        names = sorted(posixpath.basename(f["path"].split(":", 4)[4].replace("\\", "/")) for f in _dang(data))
        self.assertEqual(names, ["p1.py", "p2.py", "p3 x.py"],
                         "dangling reads the same file names, and keeps the spaces of the quoted path whole")


class TestDanglingHookRowsFunction(DanglingCase):
    def test_it_is_public_pure_and_needs_no_plugin(self):
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        found = self.scan()
        self.assertEqual([(f.kind, f.owner) for f in found], [(KIND_DANGLING, "plugin")])
        self.assertEqual(_norm_path(found[0].path), "settings.json:UserPromptSubmit:*:launched:" + HOOKS_VAR + GUARD)

    def test_it_returns_nothing_for_a_project_without_settings(self):
        fn = _dangling_function(self)
        self.assertEqual(list(fn(self.w.tmp / "empty-project")), [], "no settings file, no rows, no finding")

    def test_the_comparison_does_not_include_the_finding(self):
        _dangling_function(self)
        self.add_row("UserPromptSubmit", self.exec_row(GUARD), matcher="")
        self.w.write_all()
        result = _pd.compute_drift(self.w.project, self.w.plugin)
        self.assertNotIn(KIND_DANGLING, [f.kind for f in result["findings"]],
                         "INV-7: compute_drift does not call the scan, so nothing is counted twice")

    def test_a_dangling_row_is_found_by_the_scan_and_a_present_file_is_not(self):
        self.w.project_put(".claude/hooks/here.py", "# h\n")
        self.add_row("Stop", self.exec_row("here.py"))
        self.add_row("Stop", self.exec_row("gone.py"), matcher="other")
        found = self.scan()
        self.assertEqual(len(found), 1)
        self.assertTrue(_norm_path(found[0].path).endswith("gone.py"))


class TestDanglingRowSharedReaders(DanglingCase):
    """INV-5: one token reader and one row walker."""

    def test_launched_and_first_argument_still_returns_file_names(self):
        self.assertEqual(_pd._launched_and_first_argument(self.gate_row()), ("gate-launch.py", "concept-gate.py"))

    def test_registered_twice_and_dangling_read_exec_shell_and_gate_rows_to_the_same_names(self):
        """INV-5 by behaviour: the two readers agree on which file each row launches."""
        self.w.project_register("PreToolUse", "p1.py", matcher="exec")
        self.w.project_register("Stop", "p2.py", matcher="shell", shell=True)
        self.w.project_register("SessionStart", "gate-launch.py", matcher="gate", gate="c.py")
        for event, hook, gate in (("PreToolUse", "p1.py", None), ("Stop", "p2.py", None),
                                  ("SessionStart", "gate-launch.py", "c.py")):
            self.w.plugin_register(event, hook, matcher="p", gate=gate)
        rc, data = self.drift()
        twice = sorted(tuple(f["path"].split(":", 1)) for f in _findings(data) if f["kind"] == "registered-twice")
        self.assertEqual(twice, [("PreToolUse", "p1.py"), ("SessionStart", "c.py"), ("Stop", "p2.py")],
                         "fixture: the three rows are double registrations; got " + json.dumps(_findings(data))[:600])
        import posixpath
        launched = set()
        for f in _dang(data):
            _layer, event, _matcher, role, raw = f["path"].split(":", 4)
            if role in ("launched", "gate-argument") and posixpath.basename(raw.replace("\\", "/")) != "gate-launch.py":
                launched.add((event, posixpath.basename(raw.replace("\\", "/"))))
        self.assertEqual(launched, set(twice), "dangling names the same (event, file) pairs registered-twice does")


if __name__ == "__main__":
    unittest.main(verbosity=2)
