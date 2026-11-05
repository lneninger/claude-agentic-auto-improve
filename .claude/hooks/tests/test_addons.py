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
  * the CodeGraph trio (issue #259): with a Project index (.codegraph/codegraph.db) and a configured server the
    codegraph-first-guard.py blocks a source Read with no marker; codegraph-turn-tracker.py writes the SESSION-keyed
    marker (turn.json in <system temp>/auto-improve-codegraph-<session_id>/) after any CodeGraph tool call (and
    ignores any other tool); the guard then allows the Read; codegraph-turn-reset.py removes the marker so the
    guard blocks again. The guard fails open, with a logged reason, when there is no index, no server, a disabled
    server or a subagent; the identical retry of a blocked call is allowed once; the manifest grants the wildcard
    only and lists released hashes;
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

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
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
    #: How the hooks get into the project. A disabled hook is installed through ``af.install_disabled``.
    INSTALLER = staticmethod(af.install)

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="addon-home-"))
        self.addCleanup(__import__("shutil").rmtree, self.home, True)
        # A temp folder per test: the CodeGraph hooks keep their Session folder in the system temp folder, so a
        # row never reads or writes the developer's real one.
        self.tmp = Path(tempfile.mkdtemp(prefix="addon-tmp-"))
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.project = af.new_project("addon-run-")
        self.hooks = {p.name: p for p in self.INSTALLER(self.ADD_ON, self.project)}

    def run_hook(self, name: str, payload: dict, *, cwd: Path | None = None, extra_env: dict | None = None,
                 raw: bytes | None = None) -> Run:
        data = raw if raw is not None else json.dumps(payload).encode("utf-8")
        env = {"TMP": str(self.tmp), "TEMP": str(self.tmp), "TMPDIR": str(self.tmp)}
        env.update(extra_env or {})
        proc = subprocess.run([sys.executable, "-B", str(self.hooks[name])], input=data, capture_output=True,
                              cwd=str(cwd or self.project), env=clean_env(self.project, self.home, env),
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
    """The advisor is a DISABLED hook: no install writes it, so these rows install it through the fixture's
    ``install_disabled`` and test the script that still ships for anyone who turns it back on."""
    ADD_ON = "angular-tailwind"
    HOOK = "angular-tailwind-advisor.py"
    INSTALLER = staticmethod(af.install_disabled)

    def test_the_manifest_installs_no_hook_and_declares_the_advisor_as_disabled(self):
        self.assertEqual(af.hook_files(self.ADD_ON), [], msg="no hook is installed")
        self.assertEqual(af.registrations(self.ADD_ON), [], msg="and no row is written")
        self.assertEqual(af.disabled_hook_files(self.ADD_ON), [self.HOOK], msg="the advisor is the disabled hook")
        self.assertEqual(sorted(self.hooks), [self.HOOK], msg="install_disabled copied exactly that file")
        self.assertNotIn(af.KEY_KILL_SWITCHES, af.manifest(self.ADD_ON),
                         msg="the add-on declares no kill switch (decision 3 of issue #84)")

    def test_disabled_note_names_both_defects_to_fix_before_turning_it_back_on(self):
        note = (Path(af.__file__).resolve().parents[2] / "addons" / self.ADD_ON / "DISABLED.md").read_text(
            encoding="utf-8")
        self.assertIn('"ui"', note, msg="defect 1: the keyword pattern can never match 'ui'")
        self.assertIn("_project_paths", note, msg="defect 2: the rules file falls back to the home folder")
        self.assertIn("home folder", note)
        self.assertIn("released_sha256", note, msg="the new hash must be added")
        self.assertIn("add-ons declare no kill switch", note.lower(), msg="step 2 no longer offers a kill switch")
        self.assertNotIn("Decide on a kill switch", note)

    def test_the_kept_script_no_longer_reads_the_arch_advisor_switch(self):
        text = self.hooks[self.HOOK].read_text(encoding="utf-8")
        self.assertNotIn("CLAUDE_ARCH_ADVISOR", text, msg="the switch and its docstring lines are gone")
        run = self.run_hook(self.HOOK, {"prompt": "restyle the dashboard component styles"},
                            extra_env={"CLAUDE_ARCH_ADVISOR": "off"})
        self.assertIn("Tailwind", run.out, msg="control: the old switch value no longer silences it: "
                                               + run.describe())
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

    def test_the_layout_nudge_names_the_design_skills_and_no_path_and_is_suppressed_when_they_are_named(self):
        LAYOUT = "design the dashboard layout"
        REFERENCE_DOC = "docs/FIXTURE_UI_RULES.md"
        self.write(".claude/hooks/architecture-guard.rules.json", json.dumps({
            "frontend_projects_root": "apps", "reference_documents": [REFERENCE_DOC]}))

        def context_of(run: Run) -> str:
            out = json.loads(run.out) if run.out.strip() else {}
            return (out.get("hookSpecificOutput") or {}).get("additionalContext", "")

        def nudge_region(context: str) -> str:
            # The nudge starts at the second "[architecture-advisor]" line (the first is the CSS reminder).
            marker = "[architecture-advisor]"
            first = context.find(marker)
            second = context.find(marker, first + 1) if first >= 0 else -1
            return context[second:] if second >= 0 else ""

        def path_tokens(text: str) -> list[str]:
            # A path is a token holding a separator (/ or \) plus one of: $ % ~, a leading / or ., or a
            # file extension. Only brackets and quotes are stripped from the token edges (never ".").
            found = []
            for raw in text.split():
                tok = raw.strip("()[]{}<>`'\"")
                if not tok or ("/" not in tok and "\\" not in tok):
                    continue
                last = re.split(r"[\\/]", tok)[-1]
                if any(c in tok for c in "$%~") or tok[0] in "/." or re.search(r"\.\w+$", last):
                    found.append(tok)
            return found

        # Control (as in the "no reminder" row): a UI prompt with no layout word gets the CSS reminder, no nudge.
        plain = self.run_hook(self.HOOK, {"prompt": "restyle the component styles"})
        with self.subTest(row="d: no layout word, no nudge"):
            self.assertIn("Tailwind", plain.out, msg="control: a UI prompt does get the reminder: " + plain.describe())
            self.assertEqual(nudge_region(context_of(plain)), "",
                             msg="(d) a UI prompt with no layout word gets no layout nudge: " + plain.describe())

        # (a) a layout prompt gets a nudge naming the two plugin skills, the INV-1 clauses, and no old catalog / path.
        run = self.run_hook(self.HOOK, {"prompt": LAYOUT})
        context = context_of(run)
        region = nudge_region(context)
        with self.subTest(row="a: nudge names the skills and carries the INV-1 clauses"):
            self.assertEqual(run.rc, 0, msg="an advisor never blocks: " + run.describe())
            self.assertNotEqual(region, "", msg="(a) a layout prompt gets a nudge (a second [architecture-advisor] "
                                                "block): " + run.describe())
            for needle in ("agentic-auto-improve:application-design", "agentic-auto-improve:website-design"):
                self.assertIn(needle, region, msg="(a) the nudge names the plugin skill " + needle + ": " + region)
            self.assertEqual(region.count("agentic-auto-improve:"), 2,
                             msg="(a) exactly the two plugin skills are named, no third: " + region)
            for clause in ("advisory", "review.documents", "the project file wins", "carry on without them"):
                self.assertIn(clause, region, msg="(a) INV-1 clause %r must be in the nudge: %s" % (clause, region))
            for banned in ("ui-ux-pro-max", "~/", ".claude/references/"):
                self.assertNotIn(banned, region, msg="(a) the nudge must not name the phantom catalog %r: %s"
                                                     % (banned, region))
            self.assertIn(REFERENCE_DOC, context,
                          msg="control: the configured reference document is listed by the reminder: "
                              + run.describe())
            self.assertNotIn(REFERENCE_DOC, region,
                             msg="(a) the nudge region must not name the configured reference document: " + region)

        # (b) no path-shaped token in the nudge region; positive controls prove the extractor can fail.
        with self.subTest(row="b: no path-shaped token"):
            planted_paths = ["~/.claude/x.md", "/usr/share/refs/patterns.md",
                             "${CLAUDE_PLUGIN_ROOT}/skills/x/SKILL.md", "skills\\x\\y.md",
                             "C:\\tmp\\z.txt", "./refs/x.md", "docs/a.json"]
            self.assertEqual(path_tokens(" ".join(planted_paths)), planted_paths,
                             msg="control: the extractor must catch exactly one token per planted path shape")
            self.assertEqual(path_tokens("see Layout/UX hint"), [], msg="control: Layout/UX is not a path")
            self.assertEqual(path_tokens(region), [],
                             msg="(b) the nudge names no filesystem path of any kind: " + region)

        # (c) a layout prompt that already names a design skill gets no nudge (it carries a layout keyword,
        # so the old hook, which only knew reference filenames, still nudged it). INV-3 is case-insensitive.
        for named in ("application-design", "website-design", "Website-Design"):
            with self.subTest(row="c: names %s" % named):
                named_run = self.run_hook(self.HOOK, {"prompt": "%s using %s" % (LAYOUT, named)})
                self.assertIn("Tailwind", named_run.out,
                              msg="control: the CSS reminder still prints: " + named_run.describe())
                self.assertEqual(nudge_region(context_of(named_run)), "",
                                 msg="(c) a prompt that already names %s gets no nudge: %s"
                                     % (named, named_run.describe()))

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
    #: The release before the fix; its hooks are what an old install carries (the released_sha256 baseline).
    BASELINE_COMMIT = "643b667"

    def setUp(self) -> None:
        super().setUp()
        # A Project index and a configured server, so the gate is armed (the positive control of the contract);
        # every fail-open row removes exactly one of them. A session id per test: no two tests share a folder.
        af.plant_index(self.project)
        af.plant_server(self.project)
        self.sid = "s" + uuid.uuid4().hex

    def marker(self, session: str | None = None) -> Path:
        """The Turn marker: turn.json in the session's folder under the (fixture) system temp folder."""
        return af.session_folder(self.tmp, session or self.sid) / "turn.json"

    def legacy_sentinel(self) -> Path:
        return self.project / ".claude" / ".codegraph-used-this-turn"

    def payload(self, tool: str, tool_input: dict, **extra) -> dict:
        body = {"session_id": self.sid, "cwd": str(self.project), "tool_name": tool, "tool_input": tool_input}
        body.update(extra)
        return body

    def read_payload(self, rel: str = "src/Thing.cs", **extra) -> dict:
        return self.payload("Read", {"file_path": str(self.project / rel)}, **extra)

    def assertAllowedBecause(self, run: Run, reason: str) -> None:
        self.assertEqual(run.rc, 0, msg="the call must be allowed: " + run.describe())
        self.assertIn("[codegraph-first-guard] allowed", run.err, msg="one stderr line says why: " + run.describe())
        self.assertIn(reason, run.err, msg="and names the reason " + reason + ": " + run.describe())

    def test_a_source_read_with_no_marker_is_blocked_with_the_guards_own_banner(self):
        run = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(run.rc, 2, msg="a source Read with an index, a server and no CodeGraph call this turn must be "
                                        "blocked: " + run.describe())
        self.assertIn("[codegraph-first-guard] BLOCKED", run.err, msg="the guard's own banner: " + run.describe())
        self.assertNoFallbackBanner(run)

    def test_the_tracker_writes_the_session_marker_and_the_guard_then_allows_the_read(self):
        blocked = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(blocked.rc, 2, msg="control: blocked before the tracker ran: " + blocked.describe())
        tracked = self.run_hook(self.TRACKER, self.payload("mcp__codegraph__codegraph_search", {"query": "Thing"}))
        self.assertEqual(tracked.rc, 0, msg=tracked.describe())
        self.assertTrue(self.marker().is_file(), msg="the tracker must write turn.json in the session's folder under "
                                                     "the system temp folder: " + str(self.marker()))
        self.assertFalse(self.legacy_sentinel().exists(), msg="and no longer writes <cwd>/.claude/.codegraph-used-this-turn")
        allowed = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(allowed.rc, 0, msg="after the tracker ran the same Read is allowed: " + allowed.describe())
        # The blocked call above issued a retry ticket for this exact Read, so the retry escape would allow it too.
        # Only the absence of an `allowed (` line proves that the MARKER did it (the escape always prints one).
        self.assertNotIn("allowed (", allowed.err,
                         msg="allowed by the marker, not by the retry escape (which prints `allowed (...)`): "
                             + allowed.describe())
        for run in (tracked, allowed):
            self.assertNoFallbackBanner(run)

    def test_a_subagents_tracker_call_opens_the_gate_for_the_parent_session(self):
        # A subagent's payload carries the PARENT's session_id plus agent_id: the marker lands in the parent's folder.
        control = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(control.rc, 2, msg="control: the parent's Read is blocked first: " + control.describe())
        session = "s" + uuid.uuid4().hex
        tracked = self.run_hook(self.TRACKER, self.payload("mcp__codegraph__codegraph_explore", {"query": "q"},
                                                           session_id=session, agent_id="a1",
                                                           agent_type="general-purpose"))
        self.assertEqual(tracked.rc, 0, msg=tracked.describe())
        parent = self.run_hook(self.GUARD, self.read_payload(session_id=session))
        self.assertEqual(parent.rc, 0, msg="the parent's plain Read is allowed: " + parent.describe())
        self.assertNotIn("allowed (", parent.err,
                         msg="by the shared marker (nothing printed), not by an escape: " + parent.describe())

    def test_the_tracker_writes_the_marker_for_the_explore_tool_and_for_a_future_tool_name(self):
        for tool, extra in (("mcp__codegraph__codegraph_explore", {"mcp_server": "codegraph"}),
                            ("mcp__codegraph__codegraph_zz_future_tool", {})):
            with self.subTest(tool=tool):
                session = "s" + uuid.uuid4().hex
                body = {"session_id": session, "cwd": str(self.project), "tool_name": tool,
                        "tool_input": {"query": "q"}}
                body.update(extra)
                run = self.run_hook(self.TRACKER, body)
                self.assertEqual(run.rc, 0, msg=run.describe())
                marker = self.marker(session)
                self.assertTrue(marker.is_file(), msg="any mcp__codegraph__ tool opens the turn: " + str(marker))
                data = json.loads(marker.read_text(encoding="utf-8"))
                self.assertEqual(sorted(data), ["pid", "summary", "tool", "ts"], msg="the marker shape: " + repr(data))
                self.assertEqual(data["tool"], tool)

    def test_the_tracker_ignores_a_tool_that_is_not_a_codegraph_tool(self):
        run = self.run_hook(self.TRACKER, self.payload("Bash", {"command": "ls"}))
        self.assertEqual(run.rc, 0, msg=run.describe())
        self.assertFalse(self.marker().exists(), msg="only mcp__codegraph__* tools open the gate")
        # Control: a CodeGraph tool does write it (a legacy tool name still counts), so the absence above is the rule.
        self.run_hook(self.TRACKER, self.payload("mcp__codegraph__codegraph_node", {}))
        self.assertTrue(self.marker().exists(), msg="control: a codegraph tool writes the marker")

    def test_the_marker_survives_a_directory_change(self):
        self.run_hook(self.TRACKER, self.payload("mcp__codegraph__codegraph_explore", {"query": "q"}))
        elsewhere = self.project / "src" / "deeper"
        elsewhere.mkdir(parents=True, exist_ok=True)
        moved = self.payload("Read", {"file_path": str(self.project / "src" / "Thing.cs")}, cwd=str(elsewhere))
        run = self.run_hook(self.GUARD, moved, cwd=elsewhere)
        self.assertEqual(run.rc, 0, msg="same session, another cwd: the marker still opens the gate: " + run.describe())
        other = dict(moved, session_id="s" + uuid.uuid4().hex)
        self.assertEqual(self.run_hook(self.GUARD, other, cwd=elsewhere).rc, 2,
                         msg="control: another session does not share it")

    def test_the_reset_removes_the_marker_so_the_guard_blocks_again(self):
        self.run_hook(self.TRACKER, self.payload("mcp__codegraph__codegraph_search", {"query": "Thing"}))
        self.assertTrue(self.marker().is_file(), msg="control: the tracker wrote the session marker: " + str(self.marker()))
        self.assertEqual(self.run_hook(self.GUARD, self.read_payload()).rc, 0,
                         msg="control: with the marker the Read is allowed")
        reset = self.run_hook(self.RESET, self.payload("", {}, prompt="next question"))
        self.assertEqual(reset.rc, 0, msg=reset.describe())
        self.assertFalse(self.marker().exists(), msg="a new prompt removes the marker")
        self.assertEqual(self.run_hook(self.GUARD, self.read_payload()).rc, 2,
                         msg="and the guard blocks the same Read again")
        self.assertNoFallbackBanner(reset)

    def test_a_non_source_read_is_allowed_without_the_marker(self):
        blocked = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(blocked.rc, 2, msg="control: a source Read is blocked: " + blocked.describe())
        run = self.run_hook(self.GUARD, self.read_payload("docs/notes.md"))
        self.assertEqual(run.rc, 0, msg="a markdown Read needs no CodeGraph call: " + run.describe())

    # --- the five reasons to let reads through (issue #259) ---------------------------------------------------------
    def test_no_project_index_lets_the_read_through_even_when_a_decoy_codegraph_folder_exists(self):
        for ancestor in af.ancestors_holding(self.project, *af.CODEGRAPH_INDEX):
            if ancestor.resolve() != self.project.resolve():
                self.fail("precondition: an ancestor of the fixture project holds a real codegraph.db: %s" % ancestor)
        (self.project / ".codegraph" / "codegraph.db").unlink()
        run = self.run_hook(self.GUARD, self.read_payload())
        self.assertAllowedBecause(run, "fail-open:no-index")
        shutil.rmtree(self.project / ".codegraph")
        af.plant_decoy(self.project)  # CodeGraph's per-user folder shape: daemons/, telemetry.json, NO codegraph.db
        decoy = self.run_hook(self.GUARD, self.read_payload(session_id="s" + uuid.uuid4().hex))
        self.assertAllowedBecause(decoy, "fail-open:no-index")
        af.plant_index(self.project)
        armed = self.run_hook(self.GUARD, self.read_payload(session_id="s" + uuid.uuid4().hex))
        self.assertEqual(armed.rc, 2, msg="control: with codegraph.db back the gate is armed again: " + armed.describe())

    def test_no_configured_server_lets_the_read_through(self):
        (self.project / ".mcp.json").unlink()
        run = self.run_hook(self.GUARD, self.read_payload())
        self.assertAllowedBecause(run, "fail-open:server-not-configured")

    def test_a_disabled_server_lets_the_read_through(self):
        af.plant_server(self.project, disabled=True)
        run = self.run_hook(self.GUARD, self.read_payload())
        self.assertAllowedBecause(run, "fail-open:server-disabled")

    def test_a_subagent_payload_lets_the_read_through_and_the_same_payload_without_agent_id_does_not(self):
        sub = self.read_payload(agent_id="agent-1234", agent_type="general-purpose")
        self.assertAllowedBecause(self.run_hook(self.GUARD, sub), "fail-open:subagent")
        plain = self.run_hook(self.GUARD, self.read_payload(session_id="s" + uuid.uuid4().hex))
        self.assertEqual(plain.rc, 2, msg="control: the main session's payload (no agent_id) is blocked: " + plain.describe())

    def test_the_identical_retry_of_a_blocked_call_is_allowed_once(self):
        first = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(first.rc, 2, msg="control: the first call is blocked: " + first.describe())
        retry = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(retry.rc, 0, msg="the identical retry is allowed (retry escape): " + retry.describe())
        self.assertIn("retry-escape-used", retry.err, msg="and says so on stderr: " + retry.describe())
        again = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(again.rc, 2, msg="single use: the next identical call is blocked again: " + again.describe())

    def test_the_next_prompt_clears_a_retry_ticket(self):
        self.assertEqual(self.run_hook(self.GUARD, self.read_payload()).rc, 2, msg="control: blocked, ticket issued")
        tickets = list(af.session_folder(self.tmp, self.sid).glob("ticket-*"))
        self.assertEqual(len(tickets), 1, msg="the block must issue ticket-<fingerprint> in the Session folder: %s" % tickets)
        self.run_hook(self.RESET, self.payload("", {}, prompt="next"))
        self.assertEqual(list(af.session_folder(self.tmp, self.sid).glob("ticket-*")), [],
                         msg="the reset hook deletes this session's tickets")
        again = self.run_hook(self.GUARD, self.read_payload())
        self.assertEqual(again.rc, 2, msg="after the reset the identical call has no ticket: " + again.describe())

    # --- the manifest (acceptance criteria 7 and the upgrade path) --------------------------------------------------
    def test_the_manifest_grants_the_wildcard_only(self):
        self.assertEqual(af.permissions_allow("codegraph"), [af.CODEGRAPH_WILDCARD],
                         msg="permissions_allow must be exactly ['mcp__codegraph__*']; never a per-tool name")

    def test_the_manifest_lists_the_released_hash_of_every_hook_as_it_shipped_before_the_fix(self):
        released = af.released_hashes("codegraph")
        hooks = af.hook_files("codegraph")
        self.assertEqual(sorted(released), sorted(hooks), msg="released_sha256 has one entry per active hook")
        for name in hooks:
            shown = subprocess.run(["git", "show", "%s:.claude/addons/codegraph/hooks/%s" % (self.BASELINE_COMMIT, name)],
                                   capture_output=True, cwd=str(af.PROJECT_ROOT))
            if shown.returncode != 0:
                self.skipTest("the baseline commit %s is not available in this checkout (this check needs the full git "
                              "history: a shallow clone cannot show it, and the released hashes go unchecked)"
                              % self.BASELINE_COMMIT)
            data = shown.stdout
            if data.startswith(b"\xef\xbb\xbf"):
                data = data[3:]
            folded = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
            self.assertIn(folded, released[name],
                          msg="%s as released at %s (folded) must be in released_sha256, so addon-remove can delete an "
                              "unedited old copy" % (name, self.BASELINE_COMMIT))


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
