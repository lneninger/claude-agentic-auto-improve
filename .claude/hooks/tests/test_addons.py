#!/usr/bin/env python3
"""test_addons.py -- RED suite for the three add-ons and the default plan-question-advisor.py.

Contract: .claude/concepts/2026-10-12-dedupe-claude-config.md in the consuming repository, Revision 3 (B:
the add-on layout) and Revision 4 (D: the shared shell parser), block 16.

WHAT AN ADD-ON IS
-----------------
A hook file the plugin ships under ``.claude/addons/<add-on>/hooks/`` and does NOT register. A project gets
it only through the add-on's install skill, which copies the hook files and the helpers the add-on's
manifest names into the project's ``.claude/hooks/`` (and ``.claude/scripts/``). ``_addon_fixture.install``
does exactly that copy into an empty temporary project, and every row here runs the installed hook there.

WHAT IS PINNED
--------------
  * none of the installed hooks prints a fallback-mode banner: the helpers the manifest names are enough;
  * angular-tailwind-advisor.py prints the CSS reminder for a UI prompt, stays silent for another prompt, and
    reads the PROJECT's architecture-guard.rules.json first (it names the project's reference document);
  * the CodeGraph trio: codegraph-first-guard.py blocks a source Read with no sentinel, codegraph-turn-tracker.py
    writes the sentinel after a CodeGraph tool call (and ignores any other tool), the guard then allows the
    Read, and codegraph-turn-reset.py removes the sentinel so the guard blocks again;
  * bash-gate.py blocks a redirect into an uncovered source file, allows a covered one and a trivial one,
    and (Revision 4, D) with ``_shell_write_targets.py`` deleted from the project it exits 2 naming that
    file; the strict-shell-gate manifest names ``_shell_write_targets.py`` as a helper;
  * plan-question-advisor.py (a DEFAULT hook, run from the hooks folder beside these tests) points at the
    plugin skill ``agentic-auto-improve:plan-questions`` and never at ``~/.claude/skills``.

RED TODAY: the add-on sources and manifests do not exist in the plugin (block 18 adds them), so every
add-on row fails through ``_addon_fixture``'s own failure (an AssertionError that names what is missing),
never a skip. ``plan-question-advisor.py`` is added by block 17; its row fails until then.

Run:
    py -3 .claude/hooks/tests/test_addons.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _addon_fixture as af  # noqa: E402

FALLBACK_TEXT = "fallback mode"


def clean_env(project: Path, home: Path, extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_") and not k.startswith("GIT_")}
    env.update({"CLAUDE_PROJECT_DIR": str(project), "HOME": str(home), "USERPROFILE": str(home),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    if extra:
        env.update(extra)
    return env


class Run:
    def __init__(self, proc: subprocess.CompletedProcess):
        self.rc = proc.returncode
        self.out = proc.stdout.decode("utf-8", "replace")
        self.err = proc.stderr.decode("utf-8", "replace")

    @property
    def all_text(self) -> str:
        return self.out + "\n" + self.err

    def describe(self) -> str:
        return "exit=%s stdout=%r stderr=%r" % (self.rc, self.out[:300], self.err[:500])


class AddonCase(unittest.TestCase):
    """Installs one add-on into an empty temporary project (the fixture's own failure is the RED reason)."""

    ADD_ON = ""

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="addon-home-"))
        self.addCleanup(__import__("shutil").rmtree, self.home, True)
        self.project = af.new_project("addon-run-")
        self.hooks = {p.name: p for p in af.install(self.ADD_ON, self.project)}

    def run_hook(self, name: str, payload: dict, *, cwd: Path | None = None, extra_env: dict | None = None,
                 raw: bytes | None = None) -> Run:
        data = raw if raw is not None else json.dumps(payload).encode("utf-8")
        proc = subprocess.run([sys.executable, "-B", str(self.hooks[name])], input=data, capture_output=True,
                              cwd=str(cwd or self.project), env=clean_env(self.project, self.home, extra_env),
                              timeout=60)
        return Run(proc)

    def write(self, rel: str, text: str = "x\n") -> Path:
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def contract(self, files: list[str]) -> Path:
        body = "\n".join("- `%s`" % f for f in files)
        return self.write(".claude/concepts/fixture-contract.md",
                          "# Concept Contract - fixture\n\n**Status:** approved\n\n"
                          "**Files to touch:**\n%s\n\n## Next\n\nprose\n" % body)

    def assertNoFallbackBanner(self, run: Run) -> None:
        self.assertNotIn(FALLBACK_TEXT, run.all_text.lower(),
                         msg="no fallback-mode banner: the helpers the manifest names must have arrived: "
                             + run.describe())


class AngularTailwindAddonTests(AddonCase):
    ADD_ON = "angular-tailwind"
    HOOK = "angular-tailwind-advisor.py"

    def test_the_css_reminder_is_printed_for_a_ui_prompt_and_reads_the_projects_rules_first(self):
        self.write(".claude/hooks/architecture-guard.rules.json", json.dumps({
            "frontend_projects_root": "apps",
            "reference_documents": ["docs/FIXTURE_UI_RULES.md"]}))
        # ORDER: a plugin copy whose rules file names a DIFFERENT document is on CLAUDE_PLUGIN_ROOT. The
        # project's file must win, so the project's document appears and the plugin's does not.
        plugin_copy = Path(tempfile.mkdtemp(prefix="addon-plugin-copy-"))
        self.addCleanup(__import__("shutil").rmtree, plugin_copy, True)
        rules = plugin_copy / ".claude" / "hooks"
        rules.mkdir(parents=True)
        (rules / "architecture-guard.rules.json").write_text(json.dumps({
            "frontend_projects_root": "other", "reference_documents": ["docs/PLUGIN_TEMPLATE_RULES.md"]}),
            encoding="utf-8")
        run = self.run_hook(self.HOOK, {"prompt": "please design the dashboard component layout and its styles"},
                            extra_env={"CLAUDE_PLUGIN_ROOT": str(plugin_copy)})
        self.assertNotIn("docs/PLUGIN_TEMPLATE_RULES.md", run.out,
                         msg="the plugin copy's rules file must lose to the project's: " + run.describe())
        self.assertEqual(run.rc, 0, msg="an advisor never blocks: " + run.describe())
        out = json.loads(run.out) if run.out.strip() else {}
        context = (out.get("hookSpecificOutput") or {}).get("additionalContext", "")
        self.assertIn("Tailwind", context, msg="a UI prompt gets the CSS/Tailwind reminder: " + run.describe())
        self.assertIn("scroll-edge", context, msg="the reminder carries the scroll rule: " + run.describe())
        self.assertIn("docs/FIXTURE_UI_RULES.md", context,
                      msg="the reminder must read the PROJECT's architecture-guard.rules.json first, so it "
                          "names the project's reference document (the installed copy found its helper): "
                          + run.describe())
        self.assertNoFallbackBanner(run)

    def test_a_prompt_that_is_not_about_ui_gets_no_reminder(self):
        ui = self.run_hook(self.HOOK, {"prompt": "restyle the dashboard component layout"})
        self.assertIn("Tailwind", ui.out, msg="control: a UI prompt does get the reminder: " + ui.describe())
        run = self.run_hook(self.HOOK, {"prompt": "what is the capital of France"})
        self.assertEqual(run.rc, 0, msg=run.describe())
        self.assertEqual(run.out.strip(), "", msg="a prompt about something else gets no reminder: " + run.describe())


class CodegraphAddonTests(AddonCase):
    ADD_ON = "codegraph"
    GUARD = "codegraph-first-guard.py"
    RESET = "codegraph-turn-reset.py"
    TRACKER = "codegraph-turn-tracker.py"

    def sentinel(self) -> Path:
        return self.project / ".claude" / ".codegraph-used-this-turn"

    def read_payload(self, rel: str = "src/Thing.cs") -> dict:
        return {"tool_name": "Read", "tool_input": {"file_path": str(self.project / rel)}}

    def test_a_source_read_with_no_sentinel_is_blocked_with_the_guards_own_banner(self):
        run = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(run.rc, 2, msg="a source Read with no CodeGraph call this turn must be blocked: "
                                        + run.describe())
        self.assertIn("[codegraph-first-guard] BLOCKED", run.err, msg="the guard's own banner: " + run.describe())
        self.assertNoFallbackBanner(run)

    def test_the_tracker_writes_the_sentinel_and_the_guard_then_allows_the_read(self):
        blocked = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(blocked.rc, 2, msg="control: blocked before the tracker ran: " + blocked.describe())
        tracked = self.run_hook(self.TRACKER, {"tool_name": "mcp__codegraph__codegraph_search",
                                               "tool_input": {"query": "Thing"}})
        self.assertEqual(tracked.rc, 0, msg=tracked.describe())
        self.assertTrue(self.sentinel().is_file(), msg="the tracker must write <cwd>/.claude/.codegraph-used-this-turn")
        allowed = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(allowed.rc, 0, msg="after the tracker ran the same Read is allowed: " + allowed.describe())
        for run in (tracked, allowed):
            self.assertNoFallbackBanner(run)

    def test_the_tracker_ignores_a_tool_that_is_not_a_codegraph_tool(self):
        run = self.run_hook(self.TRACKER, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertEqual(run.rc, 0, msg=run.describe())
        self.assertFalse(self.sentinel().exists(), msg="only mcp__codegraph__* tools open the gate")
        # Control: a CodeGraph tool does write it, so the absence above is the rule.
        self.run_hook(self.TRACKER, {"tool_name": "mcp__codegraph__codegraph_node", "tool_input": {}})
        self.assertTrue(self.sentinel().exists(), msg="control: a codegraph tool writes the sentinel")

    def test_the_reset_removes_the_sentinel_so_the_guard_blocks_again(self):
        self.run_hook(self.TRACKER, {"tool_name": "mcp__codegraph__codegraph_search", "tool_input": {}})
        self.assertEqual(self.run_hook(self.GUARD, self.read_payload()).rc, 0,
                         msg="control: with the sentinel the Read is allowed")
        reset = self.run_hook(self.RESET, {"prompt": "next question"})
        self.assertEqual(reset.rc, 0, msg=reset.describe())
        self.assertFalse(self.sentinel().exists(), msg="a new prompt removes the sentinel")
        self.assertEqual(self.run_hook(self.GUARD, self.read_payload()).rc, 2,
                         msg="and the guard blocks the same Read again")
        self.assertNoFallbackBanner(reset)

    def test_a_non_source_read_is_allowed_without_the_sentinel(self):
        blocked = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(blocked.rc, 2, msg="control: a source Read is blocked: " + blocked.describe())
        run = self.run_hook(self.GUARD, self.read_payload("docs/notes.md"))
        self.assertEqual(run.rc, 0, msg="a markdown Read needs no CodeGraph call: " + run.describe())


class StrictShellGateAddonTests(AddonCase):
    ADD_ON = "strict-shell-gate"
    HOOK = "bash-gate.py"

    def bash(self, command: str) -> dict:
        return {"tool_name": "Bash", "tool_input": {"command": command}}

    def test_a_redirect_into_an_uncovered_source_file_is_blocked(self):
        target = str(self.project / "src" / "Uncovered.cs").replace("\\", "/")
        run = self.run_hook(self.HOOK, self.bash('echo "x" >> %s' % target))
        self.assertEqual(run.rc, 2, msg="bash-gate must block a redirect into an uncovered source file: "
                                        + run.describe())
        self.assertIn("[bash-gate] BLOCKED", run.err, msg="the gate's own banner: " + run.describe())
        self.assertNoFallbackBanner(run)

    def test_a_covered_file_and_a_trivial_file_are_allowed(self):
        covered = str(self.project / "src" / "Covered.cs").replace("\\", "/")
        uncovered = str(self.project / "src" / "Uncovered.cs").replace("\\", "/")
        self.contract(["src/Covered.cs"])
        blocked = self.run_hook(self.HOOK, self.bash('echo "x" >> %s' % uncovered))
        self.assertEqual(blocked.rc, 2, msg="control: the uncovered sibling is blocked: " + blocked.describe())
        run = self.run_hook(self.HOOK, self.bash('echo "x" >> %s' % covered))
        self.assertEqual(run.rc, 0, msg="a file an approved contract covers is allowed: " + run.describe())
        notes = str(self.project / "docs" / "notes.md").replace("\\", "/")
        run2 = self.run_hook(self.HOOK, self.bash('echo "x" >> %s' % notes))
        self.assertEqual(run2.rc, 0, msg="a trivial file is allowed: " + run2.describe())
        self.assertNoFallbackBanner(run)

    def test_with_the_shell_parser_deleted_the_gate_exits_2_naming_the_missing_file(self):
        parser = self.project / ".claude" / "hooks" / "_shell_write_targets.py"
        self.assertTrue(parser.is_file(), msg="fixture: the install copied _shell_write_targets.py (a helper)")
        control = self.run_hook(self.HOOK, self.bash("ls"))
        self.assertEqual(control.rc, 0, msg="control: with the parser present a harmless command is allowed: "
                                            + control.describe())
        parser.unlink()
        run = self.run_hook(self.HOOK, self.bash("ls"))
        self.assertEqual(run.rc, 2, msg="a strict gate that silently stops reading is worse than a loud one: "
                                        "it must exit 2: " + run.describe())
        self.assertIn("_shell_write_targets", run.err,
                      msg="and the message must name the missing file: " + run.describe())

    def test_the_manifest_names_the_shell_parser_as_a_helper(self):
        helpers = [h.replace("\\", "/") for h in af.helper_paths(self.ADD_ON)]
        self.assertIn(".claude/hooks/_shell_write_targets.py", helpers,
                      msg="an install must copy the parser into a project that lacks it: " + repr(helpers))
        self.assertIn(".claude/hooks/_project_paths.py", helpers, msg="and _project_paths.py: " + repr(helpers))
        self.assertIn(".claude/scripts/_contract_index.py", helpers,
                      msg="and the contract index, into the project's scripts folder: " + repr(helpers))


class PlanQuestionAdvisorTests(unittest.TestCase):
    """A DEFAULT hook: run from the hooks folder beside these tests."""

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="planq-"))
        self.addCleanup(__import__("shutil").rmtree, self.dir, True)

    def _run(self, transcript_text: str):
        hook = HOOKS_DIR / "plan-question-advisor.py"
        if not hook.is_file():
            raise AssertionError("%s does not exist yet (block 17 adds the default plan-question advisor)" % hook)
        transcript = self.dir / "transcript.jsonl"
        transcript.write_text(transcript_text, encoding="utf-8")
        proc = subprocess.run([sys.executable, "-B", str(hook)],
                              input=json.dumps({"prompt": "ask me", "transcript_path": str(transcript)}).encode(),
                              capture_output=True, cwd=str(self.dir),
                              env=clean_env(self.dir, self.dir), timeout=60)
        return Run(proc)

    def test_in_plan_mode_the_reminder_names_the_plugin_skill_and_never_the_home_skills_folder(self):
        run = self._run('{"text": "Plan mode is active"}\n')
        self.assertEqual(run.rc, 0, msg=run.describe())
        context = (json.loads(run.out).get("hookSpecificOutput") or {}).get("additionalContext", "") \
            if run.out.strip() else ""
        self.assertTrue(context, msg="plan mode gets the reminder: " + run.describe())
        self.assertIn("agentic-auto-improve:plan-questions", context,
                      msg="the pointer is the plugin skill, namespaced: " + context[:300])
        self.assertNotIn("~/.claude/skills", context,
                         msg="the old home-folder pointer must be gone (a plugin install has no such folder)")
        flat = context.replace("\\", "/")
        self.assertNotIn(".claude/skills", flat,
                         msg="nor the same folder spelled out: an expanded home path (%s) or a bare "
                             ".claude/skills pointer" % str(self.dir).replace("\\", "/"))

    def test_outside_plan_mode_it_says_nothing(self):
        in_plan = self._run('{"text": "Plan mode is active"}\n')
        self.assertTrue(in_plan.out.strip(), msg="control: plan mode speaks: " + in_plan.describe())
        run = self._run('{"text": "an ordinary turn"}\n')
        self.assertEqual(run.rc, 0, msg=run.describe())
        self.assertEqual(run.out.strip(), "", msg="outside plan mode nothing is injected: " + run.describe())


if __name__ == "__main__":
    unittest.main(verbosity=2)
