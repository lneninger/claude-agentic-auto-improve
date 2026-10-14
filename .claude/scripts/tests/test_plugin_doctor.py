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
# SHAPES THE CONTRACT LEAVES OPEN (this suite fixes them; the implementer follows, or says so):
#   * the --json envelope is {"findings": [{"kind", "path", "owner", ...}], "compared": N, "compared_addons": M};
#     `path` is the project-relative path, or "<event>:<hook file>" for registered-twice;
#   * sync-config `plugin_delivered` is a list of {"path", "plugin_path"} objects (the same two names the synced
#     trees use); `repo_owned` is a list of project-relative file paths; `project_enforced_hooks` is a list of hook
#     file names; `addons` maps an add-on name to the list of its hook file names;
#   * a plugin add-on lives at <plugin>/.claude/addons/<name>/ with addon.json and hooks/<file>;
#   * a project-side hook is registered in settings.json as "${CLAUDE_PROJECT_DIR}/.claude/hooks/<file>", a
#     plugin-side one in <plugin>/.claude/hooks/hooks.json as "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/<file>".
# Every such choice is stated again in the hand-off. None of them is an assertion about HOW the check is built.

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
        """Register `hook` in the project's settings (or settings.local.json). `gate` makes it a launcher row."""
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
        # CHECKS is declared but is built at run time, so no static reader can know its members.
        self.w.plugin_put(".claude/hooks/odd-dispatcher.py", "import sys\nCHECKS = [n for n in sys.argv]\n")
        self.w.plugin_register("PostToolUse", "odd-dispatcher.py")
        rc, data = self.drift()
        self.assertEqual(rc, 1, "an unreadable registration is a counted finding")
        self.assertKinds(data, ["unreadable-registration"], "a dispatcher member list that cannot be read")


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
    def test_a_missing_plugin_side_folder_of_a_vendored_pair_exits_4(self):
        shutil.rmtree(self.w.plugin / ".claude" / "scripts")
        rc = self.w.run()[0]
        self.assertEqual(rc, 4, "the plugin has no .claude/scripts folder, so nothing under it can be compared")

    def test_a_missing_plugin_side_folder_of_a_plugin_delivered_pair_exits_4(self):
        shutil.rmtree(self.w.plugin / "agents")
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 4, "plugin_delivered pairs are held to the same rule; out=%r err=%r" % (out[-200:], err[-200:]))
        self.assertIn("agents", out + err, "the message names the missing folder")

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
        self.assertIsNotNone(data, "the JSON document is still printed: stdout=%r" % out[-200:])
        self.assertEqual(data.get("compared"), 0)

    def test_the_plugin_root_equal_to_the_project_root_exits_4(self):
        rc, out, err, data = self.w.run(plugin=str(self.w.project))
        self.assertEqual(rc, 4, "comparing a tree with itself would always look clean; out=%r" % out[-200:])

    def test_no_plugin_found_exits_4(self):
        rc, out, err, data = self.w.run(plugin=None)
        self.assertEqual(rc, 4, "no --plugin, nothing recorded and nothing cached: it cannot compare; out=%r" % out[-200:])

    def test_an_unparseable_settings_file_exits_4(self):
        self.w.write_all()
        (self.w.project / ".claude" / "settings.json").write_text("{ not json", encoding="utf-8")
        argv = [sys.executable, "-B", str(DOCTOR), "--drift", "--project", str(self.w.project),
                "--plugin", str(self.w.plugin), "--json"]
        out = subprocess.run(argv, capture_output=True, text=True, env=self.w.env(), timeout=120)
        self.assertEqual(out.returncode, 4, "a registration file that does not parse must not read as 'no registrations'")

    def test_an_unparseable_sync_config_exits_4(self):
        self.w.write_all()
        (self.w.project / ".claude" / ".sync-config.json").write_text("{ not json", encoding="utf-8")
        argv = [sys.executable, "-B", str(DOCTOR), "--drift", "--project", str(self.w.project),
                "--plugin", str(self.w.plugin), "--json"]
        out = subprocess.run(argv, capture_output=True, text=True, env=self.w.env(), timeout=120)
        self.assertEqual(out.returncode, 4, "a sync config that does not parse cannot be compared against")


class TestDriftAddons(DriftCase):
    def setUp(self):
        super().setUp()
        self.w.config["addons"] = {"codegraph": ["cg1.py", "cg2.py"]}
        base = ".claude/addons/codegraph"
        self.w.plugin_put(base + "/addon.json", json.dumps({"name": "codegraph", "hooks": ["cg1.py", "cg2.py"]}))
        for f in ("cg1.py", "cg2.py"):
            self.w.plugin_put("%s/hooks/%s" % (base, f), "# %s\n" % f)
            self.w.project_put(".claude/hooks/" + f, "# %s\n" % f)

    def test_identical_addon_files_count_in_compared_addons_and_never_in_compared(self):
        rc, data = self.drift()
        self.assertEqual(rc, 0)
        self.assertEqual(data.get("compared_addons"), 2)
        self.assertEqual(data.get("compared"), 3, "add-on files are counted apart from vendored files")

    def test_an_addon_file_that_differs_is_content_differs_owned_by_the_plugin(self):
        self.w.project_put(".claude/hooks/cg2.py", "# edited in the project\n")
        rc, data = self.drift()
        self.assertEqual(rc, 1)
        self.assertKinds(data, ["content-differs"], "the installed add-on copy drifted")
        self.assertEqual(_findings(data)[0].get("owner"), "plugin")
        self.assertTrue(self.path_of(data, "content-differs")[0].endswith("cg2.py"))

    def test_a_listed_addon_file_missing_on_one_side_is_one_sided(self):
        self.w.project_remove(".claude/hooks/cg2.py")
        rc, data = self.drift()
        self.assertKinds(data, ["one-sided"], "listed for the add-on, absent from the project")
        self.assertEqual(data.get("compared_addons"), 1)

    def test_a_listed_addon_the_plugin_does_not_ship_exits_4(self):
        self.w.config["addons"]["ghost"] = ["ghost.py"]
        rc, out, err, data = self.w.run()
        self.assertEqual(rc, 4, "an add-on folder or manifest missing in the plugin means it cannot compare")


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
