#!/usr/bin/env python3
"""Memory off changes nothing, and the Step 1.5 text says so.

Contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (invariant I-M0, Extension Points
"/design-first new Step 1.5", Handoff 3).

Two halves:

1. PARITY. With memory off (profile absent, every slot still the placeholder, and the server slot set to
   `none`), every command /design-first Step 1.5 runs is run against a copy of every Work Item Brief under
   .claude/work-items/ and two fixture briefs. Each brief must stay byte-identical to its original, and no
   file may appear anywhere in the temporary project tree. Input files for the commands live OUTSIDE the tree,
   so a new file in the tree can only have been written by the script.

2. TEXT. The Step 1.5 text, the central-memory reference, the data-architect rule, the template line format
   and the /flow stop-list line exist; no skill text names a memory tool; /task is untouched by this feature
   (a content check, not a hash pin, so unrelated /task edits do not break it).

Run: py -3 .claude/scripts/tests/test_memory_off_parity.py
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = SCRIPTS_DIR.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
import memory_boundary as mb  # noqa: E402

WORK_ITEMS = PLUGIN_ROOT / ".claude" / "work-items"
PLACEHOLDER = "*(the name of the MCP server that holds shared memory, or `none` to turn memory off)*"
SLOT_NAMES = ("memory.server", "memory.retrieve-tool", "memory.capture-tool", "memory.shape", "memory.project-key")

FIXTURE_BRIEFS = {
    "fixture-lf.md": ("---\nid: 1\ntitle: Fixture one\nbranch: task/fixture-one\ncontract: none\nstatus: implementing\n"
                      "---\n\n# Fixture one\n\n## Acceptance criteria\n- [ ] first\n- [ ] second\n\n"
                      "## Memory used\nRetrieved: m-1@2 | project | validated | applies | cited \"A title\"\n"),
    "fixture-crlf.md": ("---\r\nid: 2\r\ntitle: Fixture two\r\nbranch: task/fixture-two\r\ncontract: none\r\n"
                        "status: designing\r\n---\r\n\r\n# Fixture two\r\n\r\n## Acceptance criteria\r\n- one\r\n"),
}


def profile_text(server: str) -> str:
    values = {name: PLACEHOLDER for name in SLOT_NAMES}
    values["memory.server"] = server
    rows = "\n".join("| `%s` | %s |" % (k, v) for k, v in values.items())
    return "# Project profile\n\n## Slots\n\n| Slot | Value |\n|---|---|\n%s\n\n## Worked shape\n" % rows


# variant name -> profile text, or None for "no profile file at all"
VARIANTS = {
    "profile-absent": None,
    "placeholder-slots": profile_text(PLACEHOLDER),
    "server-none": profile_text("none"),
}


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = mb.main([str(a) for a in argv])
    out = buf.getvalue().strip()
    return code, (json.loads(out) if out else None)


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def all_briefs() -> dict:
    found = {p.name: p.read_bytes() for p in sorted(WORK_ITEMS.glob("*.md"))}
    for name, text in FIXTURE_BRIEFS.items():
        found[name] = text.encode("utf-8")
    return found


class MemoryOffParityTests(unittest.TestCase):
    def test_the_real_briefs_are_found_so_the_loop_is_not_vacuous(self):
        briefs = all_briefs()
        self.assertGreater(len([n for n in briefs if not n.startswith("fixture-")]), 0,
                           "no brief found under .claude/work-items/")
        self.assertEqual(len([n for n in briefs if n.startswith("fixture-")]), 2)

    def test_every_step_1_5_command_with_memory_off_leaves_every_brief_byte_identical(self):
        originals = all_briefs()
        for variant, profile in VARIANTS.items():
            with self.subTest(variant=variant):
                tmp = Path(tempfile.mkdtemp(prefix="memory-off-"))
                self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
                project, inputs = tmp / "project", tmp / "inputs"
                (project / ".claude" / "work-items").mkdir(parents=True)
                inputs.mkdir()
                if profile is not None:
                    (project / ".claude" / "project-profile.md").write_bytes(profile.encode("utf-8"))
                for name, data in originals.items():
                    (project / ".claude" / "work-items" / name).write_bytes(data)
                response = inputs / "response.json"
                response.write_text(json.dumps({"items": [
                    {"id": "m-1", "version": "2", "scope": "project", "status": "validated", "title": "T"}]}),
                    encoding="utf-8")
                outcome = inputs / "outcome.json"
                outcome.write_text(json.dumps({"state": "enabled", "retrieved": [
                    {"id": "m-1", "version": "2", "scope": "project", "status": "validated",
                     "title": "T", "decision": "applies"}]}), encoding="utf-8")
                contract = inputs / "contract.md"
                contract.write_text("## Lessons referenced\n- Memory item m-1@2\n", encoding="utf-8")
                before = snapshot(project)

                code, status = run("status", "--project", project)
                self.assertEqual(code, 0)
                self.assertEqual(status["state"], "disabled")
                self.assertEqual(status["line"], "", "disabled prints no line")

                for name in originals:
                    brief = project / ".claude" / "work-items" / name
                    code, data = run("retrieve-request", "--project", project, "--brief", brief)
                    self.assertEqual((code, data["refused"]), (1, "not-enabled"), name)
                    code, data = run("record", "--project", project, "--brief", brief, "--outcome", outcome)
                    self.assertEqual((code, data["refused"]), (1, "not-enabled"), name)
                    code, _ = run("check-contract", "--project", project, "--brief", brief, "--contract", contract)
                    self.assertEqual(code, 0, name)
                    self.assertEqual(brief.read_bytes(), originals[name], "%s changed under %s" % (name, variant))
                code, normalised = run("normalise", "--project", project, "--input", response)
                self.assertEqual(code, 0)
                # The reference has the model write the normalise output to a second file outside the tree and
                # pass that file to changed-items.
                second = inputs / "normalised.json"
                second.write_text(json.dumps(normalised), encoding="utf-8")
                code, _ = run("changed-items", "--project", project, "--input", second)
                self.assertEqual(code, 0)

                after = snapshot(project)
                self.assertEqual(sorted(set(after) - set(before)), [], "a new file appeared in the project tree")
                self.assertEqual(after, before, "a file in the project tree changed")

    def test_positive_control_an_enabled_profile_does_write_the_section(self):
        # Without this the byte-identical check could pass because record never writes at all.
        tmp = Path(tempfile.mkdtemp(prefix="memory-on-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        slots = {"memory.server": "central", "memory.retrieve-tool": "recall", "memory.capture-tool": "remember",
                 "memory.shape": "v0", "memory.project-key": "demo"}
        rows = "\n".join("| `%s` | `%s` |" % kv for kv in slots.items())
        (tmp / ".claude").mkdir()
        (tmp / ".claude" / "project-profile.md").write_text(
            "# P\n\n## Slots\n\n| Slot | Value |\n|---|---|\n%s\n\n## Worked shape\n" % rows, encoding="utf-8")
        brief = tmp / "brief.md"
        brief.write_bytes(FIXTURE_BRIEFS["fixture-lf.md"].encode("utf-8"))
        original = brief.read_bytes()
        outcome = tmp / "outcome.json"
        outcome.write_text(json.dumps({"state": "enabled", "retrieved": [
            {"id": "m-9", "version": "1", "scope": "project", "status": "validated", "title": "T",
             "decision": "applies"}]}), encoding="utf-8")
        code, _ = run("record", "--project", tmp, "--brief", brief, "--outcome", outcome)
        self.assertEqual(code, 0)
        self.assertNotEqual(brief.read_bytes(), original)
        self.assertIn(b"Retrieved: m-9@1", brief.read_bytes())

    def test_positive_control_an_unconfigured_profile_does_write_its_one_line(self):
        # Unconfigured is not disabled: Step 1.5 point 3 records it, so record must write there. Without this the
        # disabled byte-identity could pass because record refuses everything.
        tmp = Path(tempfile.mkdtemp(prefix="memory-unconfigured-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        slots = {"memory.server": "central", "memory.retrieve-tool": "recall", "memory.capture-tool": "remember",
                 "memory.shape": "nope", "memory.project-key": "demo"}
        rows = "\n".join("| `%s` | `%s` |" % kv for kv in slots.items())
        (tmp / ".claude").mkdir()
        (tmp / ".claude" / "project-profile.md").write_text(
            "# P\n\n## Slots\n\n| Slot | Value |\n|---|---|\n%s\n\n## Worked shape\n" % rows, encoding="utf-8")
        brief = tmp / "brief.md"
        brief.write_bytes(FIXTURE_BRIEFS["fixture-lf.md"].replace("## Memory used\n", "## Memory used\nstale\n")
                          .encode("utf-8"))
        original = brief.read_bytes()
        outcome = tmp / "outcome.json"
        outcome.write_text(json.dumps({"state": "unconfigured", "date": "2026-11-02", "retrieved": [
            {"id": "m-9", "version": "1", "scope": "project", "status": "validated", "title": "T",
             "decision": "applies"}]}), encoding="utf-8")
        code, _ = run("record", "--project", tmp, "--brief", brief, "--outcome", outcome)
        self.assertEqual(code, 0)
        self.assertNotEqual(brief.read_bytes(), original)
        self.assertIn(b"Memory: unconfigured (shape-unknown) | 2026-11-02", brief.read_bytes())
        # the outcome's own item is ignored; the keep rule leaves the brief's earlier Retrieved: line in place
        self.assertNotIn(b"m-9@1", brief.read_bytes())
        self.assertIn(b'Retrieved: m-1@2 | project | validated | applies | cited "A title"', brief.read_bytes())


def read(rel: str) -> str:
    return (PLUGIN_ROOT / rel).read_text(encoding="utf-8")


def section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


class TaskIsUntouchedTests(unittest.TestCase):
    def test_task_skill_names_neither_the_section_nor_the_adapter(self):
        text = read("skills/task/SKILL.md")
        self.assertNotIn("Memory used", text, "the section is documented in the design-first reference only")
        self.assertNotIn("memory_boundary", text, "/task never calls the memory adapter")


class Step15TextTests(unittest.TestCase):
    DF = "skills/design-first/SKILL.md"
    REF = "skills/design-first/references/central-memory.md"

    def step(self) -> str:
        text = read(self.DF)
        return section(text, "## Step 1.5", "## Step 2:")

    def test_step_1_5_sits_between_step_1_and_step_2(self):
        text = read(self.DF)
        self.assertLess(text.index("## Step 1:"), text.index("## Step 1.5"))
        self.assertLess(text.index("## Step 1.5"), text.index("## Step 2:"))
        self.assertIn("Consult the Central Memory System", self.step())

    def test_step_1_5_runs_status_through_the_standard_lookup_block(self):
        step = self.step()
        self.assertIn("agentic-auto-improve/*/", step, "the standard script lookup block")
        self.assertIn("memory_boundary.py", step)
        self.assertRegex(step, r'py -3 "\$MEM" status')

    def test_disabled_and_empty_lookup_print_and_write_nothing(self):
        step = self.step()
        self.assertRegex(step, r"(?s)disabled.{0,300}print(s)? nothing.{0,200}writ(e|es) nothing")
        self.assertRegex(step, r"(?i)empty lookup|MEM.{0,40}empty|comes back empty")

    def test_any_failure_prints_one_line_and_treats_memory_as_off(self):
        step = self.step()
        self.assertRegex(step, r"(?i)non-zero exit")
        self.assertRegex(step, r"(?i)crash")
        self.assertRegex(step, r"(?i)timeout")
        self.assertRegex(step, r"(?i)unreadable")
        self.assertRegex(step, r"(?is)one line.{0,400}memory (as )?off")
        self.assertIn("Step 2", step)

    def test_unconfigured_records_and_prints_one_line(self):
        self.assertRegex(self.step(), r"(?is)unconfigured.{0,300}one line")

    def test_enabled_reads_the_reference_and_the_architect_gets_applies_items_only(self):
        step = self.step()
        self.assertIn("references/central-memory.md", step)
        self.assertIn("memory_items", step)
        self.assertRegex(step, r"(?i)only .{0,20}`?applies`? items")

    def test_step_3_runs_check_contract(self):
        step3 = section(read(self.DF), "## Step 3: Present", "## Step 3.4")
        self.assertIn("check-contract", step3)
        self.assertIn("not-cited", step3)
        self.assertIn("uncleared-item", step3)

    def test_the_reference_carries_the_procedure(self):
        ref = read(self.REF)
        for needle in ("tool list", "one call", "no retry", "unavailable", "normalise", "changed-items",
                       "at most 8", "two multi-select", "four options", "memory_items", "check-contract",
                       "not-cited", "uncleared-item", "Parent contract", "## Memory used", "quoted data",
                       "does-not-apply"):
            self.assertIn(needle.lower(), ref.lower(), "the reference lacks %r" % needle)
        self.assertRegex(ref, r"(?i)only on the user'?s yes")

    def test_applicability_answers_come_only_from_the_user(self):
        ref = read(self.REF)
        self.assertRegex(ref, r"(?is)applies.{0,200}(only|never).{0,200}user|user.{0,200}(only|alone).{0,200}applies")

    def test_data_architect_has_the_memory_items_rule(self):
        text = read("agents/data-architect.md")
        self.assertIn("Memory items", text)
        self.assertIn("memory_items", text)
        self.assertIn("Memory item <id>@<version>", text)

    def test_template_has_the_memory_item_line_format_under_lessons_referenced(self):
        text = read(".claude/templates/concept-contract.md")
        lessons = section(text, "## Lessons referenced", "## Implementation Handoff")
        self.assertIn("Memory item <id>@<version>", lessons)

    def test_flow_lists_the_applicability_question_among_the_operators_calls(self):
        text = read("skills/flow/SKILL.md")
        block = section(text, "**Always the operator's call", "**Retry budget.**")
        self.assertRegex(block, r"(?is)memory applicability question.{0,120}Step 1\.5")

    def test_no_skill_text_names_a_memory_tool(self):
        for rel in (self.DF, self.REF, "agents/data-architect.md", ".claude/templates/concept-contract.md",
                    "skills/flow/SKILL.md"):
            text = read(rel)
            for name in ("memory_retrieve", "memory_capture"):
                self.assertNotIn(name, text, "%s names a memory tool: the id comes from the script's output" % rel)
            self.assertIsNone(re.search(r"mcp__[A-Za-z0-9_-]+__memory", text), rel)


class ProjectHistoryRecordTextTests(unittest.TestCase):
    """Revision 7: the Project history record is stated in host onboarding and on every Step 1.5 printed line."""

    FI = "skills/auto-improve-finish-install/SKILL.md"
    DF = "skills/design-first/SKILL.md"
    REF = "skills/design-first/references/central-memory.md"
    AGREEMENT = ".claude/agreements/use-the-project-history-record.md"
    SUFFIX = "; design continues from the project history record (registries and concept contracts)"

    def fi_section(self) -> str:
        return section(read(self.FI), "## The project history record", "## Add-ons")

    def point(self, n: int) -> str:
        step = section(read(self.DF), "## Step 1.5", "## Step 2:")
        m = re.search(r"(?ms)^%d\. .*?(?=^\d+\. |\Z)" % n, step)
        self.assertIsNotNone(m, "Step 1.5 point %d" % n)
        return m.group(0)

    def test_the_section_sits_after_stage_2_and_before_add_ons(self):
        text = read(self.FI)
        self.assertLess(text.index("## Stage 2:"), text.index("## The project history record"))
        self.assertLess(text.index("## The project history record"), text.index("## Add-ons"))

    def test_the_section_names_every_part_of_the_record(self):
        sec = self.fi_section()
        for needle in (".claude/registries/MECHANISMS.md", "VOCABULARY.md", "JOURNAL.md", "INTEGRATION.md",
                       ".claude/concepts/", ".claude/work-items/"):
            self.assertIn(needle, sec)

    def test_the_central_memory_system_only_supplements(self):
        flat = re.sub(r"\s+", " ", self.fi_section())
        self.assertRegex(flat, r"(?i)Central Memory System.{0,200}only supplements")
        self.assertRegex(flat, r"(?i)never replaces or hides")

    def test_the_doctor_runs_in_report_mode_and_fix_waits_for_a_yes(self):
        sec = self.fi_section()
        self.assertRegex(sec, r"plugin_doctor\.py\" --project \.")
        flat = re.sub(r"\s+", " ", sec)
        self.assertIn("--fix", flat, "the section must mention --fix")
        # I3: every --fix line in the whole file, not only this section, with a word-bounded ask word in its paragraph
        self.assertEqual(fix_lines_without_ask(read(self.FI)), [])
        self.assertRegex(flat, r"(?i)ask(s)? before .{0,40}--fix|only after the user says yes")

    def test_nothing_appends_on_every_run(self):
        flat = re.sub(r"\s+", " ", self.fi_section())
        self.assertIsNone(re.search(r"(?i)on every run.{0,80}append|append.{0,80}on every run", flat))

    def test_step_1_5_lead_sentence(self):
        step = section(read(self.DF), "## Step 1.5", "## Step 2:")
        flat = re.sub(r"\s+", " ", step)
        self.assertRegex(flat, r"(?i)design history is its Project history record")
        self.assertRegex(flat, r"(?i)in every memory state, including disabled")
        self.assertRegex(flat, r"(?i)only supplements it")
        self.assertRegex(flat, r"(?i)never replace, hide or skip a registry read")

    def test_point_1_still_prints_and_writes_nothing_on_disabled(self):
        p1 = self.point(1)
        self.assertRegex(p1, r"(?is)disabled.{0,300}print(s)? nothing.{0,200}writ(e|es) nothing")
        self.assertRegex(p1, r"(?i)Project history record is read as always")
        self.assertRegex(p1, r"(?i)Nothing is printed or written on disabled")
        self.assertNotIn(self.SUFFIX, p1)

    def test_every_printed_line_in_other_states_ends_with_the_suffix(self):
        self.assertIn(self.SUFFIX, self.point(2))
        p3 = re.sub(r"\s+", " ", self.point(3))
        self.assertGreaterEqual(p3.count(self.SUFFIX), 2, "status line and the skipped-for-want-of-a-brief line")
        self.assertIn(self.SUFFIX, self.point(4))

    def test_the_reference_ground_rule(self):
        ref = read(self.REF)
        ground = section(ref, "## Ground rules", "## 1.")
        flat = re.sub(r"\s+", " ", ground)
        self.assertRegex(flat, r"(?i)Project history record")
        self.assertRegex(flat, r"(?i)only supplements")
        self.assertIn(self.SUFFIX, flat)

    def test_the_shipped_agreement(self):
        text = read(self.AGREEMENT)
        self.assertTrue(text.startswith("# Use the Project History Record"))
        self.assertLess(len(text), 400)
        self.assertNotRegex(text, r"(?i)memory_|mcp__")


ASK_WORD = re.compile(r"(?i)\b(asks?|asked|asking|only after|says yes|agrees?|confirm\w*)\b")
BLANK_LINE = re.compile(r"\n[ \t]*\n")


def fix_lines_without_ask(text: str) -> list:
    """Every `--fix` in `text` whose own paragraph holds no ask word before it (I3).

    A paragraph is a run of lines between blank lines. A paragraph that is a code fence belongs to the prose
    paragraph just above it, so the sentence that introduces the command counts. The look-back stops at the
    paragraph: an ask word in an earlier section is no confirmation for this command.
    """
    blocks = BLANK_LINE.split(text)
    bad = []
    for i, block in enumerate(blocks):
        for m in re.finditer(r"--fix\b", block):
            before = block[:m.start()]
            if block.lstrip().startswith("```") and i > 0:
                before = blocks[i - 1] + "\n" + before
            if not ASK_WORD.search(before):
                bad.append(block[max(0, m.start() - 60):m.end()].strip())
    return bad


class FixAskPinTests(unittest.TestCase):
    """I3 controls: the scan fails on a bare --fix and on an ask word that is only part of another word."""

    def test_a_bare_fix_after_no_ask_is_found(self):
        planted = "If there is no profile, run the doctor first:\n\n```bash\n$PY plugin_doctor.py --fix\n```\n"
        self.assertEqual(len(fix_lines_without_ask(planted)), 1)

    def test_a_task_word_is_no_ask(self):
        planted = "This task scaffolds the profile:\n\n```bash\n$PY plugin_doctor.py --fix\n```\n"
        self.assertEqual(len(fix_lines_without_ask(planted)), 1)

    def test_an_ask_in_an_earlier_paragraph_does_not_count(self):
        planted = "Ask the user once.\n\nThen run the doctor.\n\n```bash\n$PY plugin_doctor.py --fix\n```\n"
        self.assertEqual(len(fix_lines_without_ask(planted)), 1)

    def test_an_ask_before_the_fence_in_the_same_paragraph_counts(self):
        ok = "Ask the user once. Only after a yes, run:\n\n```bash\n$PY plugin_doctor.py --fix\n```\n"
        self.assertEqual(fix_lines_without_ask(ok), [])

    def test_the_real_file_has_every_fix_line_covered(self):
        text = read("skills/auto-improve-finish-install/SKILL.md")
        self.assertGreaterEqual(text.count("--fix"), 4)
        self.assertEqual(fix_lines_without_ask(text), [])


class FinishInstallStage1aTests(unittest.TestCase):
    """W1 and I-5: Stage 1a reports, shows the missing list, asks once, and runs --fix only on a yes."""

    FI = "skills/auto-improve-finish-install/SKILL.md"

    def stage_1a(self) -> str:
        return section(read(self.FI), "### 1a.", "### 1b.")

    def history(self) -> str:
        return section(read(self.FI), "## The project history record", "## Add-ons")

    def test_stage_1a_runs_the_doctor_in_report_mode_first(self):
        s = self.stage_1a()
        self.assertRegex(s, r"plugin_doctor\.py\" --project \.")
        self.assertLess(s.index("--project ."), s.index("--fix"))

    def test_stage_1a_shows_the_missing_list_as_what_fix_would_create(self):
        flat = re.sub(r"\s+", " ", self.stage_1a())
        self.assertRegex(flat, r"(?i)missing.{0,200}(exactly )?what .{0,20}--fix.{0,20}would create")

    def test_stage_1a_asks_once_and_runs_fix_only_on_a_yes(self):
        flat = re.sub(r"\s+", " ", self.stage_1a())
        self.assertRegex(flat, r"(?i)ask(s)? (the user )?once")
        self.assertRegex(flat, r"(?i)only after the user says yes")
        self.assertRegex(flat, r"(?i)never run(s)? it (on its own|without)")

    def test_planted_bare_stage_1a_fix_fails(self):
        planted = ("### 1a. Is there a profile yet?\n\nIf `.claude/project-profile.md` does not exist, run the doctor "
                   "first:\n\n```bash\n$PY \"<dir of FI>/plugin_doctor.py\" --fix\n```\n\n### 1b. Preview\n")
        self.assertEqual(len(fix_lines_without_ask(section(planted, "### 1a.", "### 1b."))), 1)

    # I-5, the four runs
    def test_run_a_profile_exists_stage_1a_is_skipped_and_the_history_check_holds_the_only_ask(self):
        flat = re.sub(r"\s+", " ", self.stage_1a())
        self.assertRegex(flat, r"(?i)profile already exists.{0,80}skip")
        self.assertRegex(re.sub(r"\s+", " ", self.history()), r"(?i)holds the only ask")

    def test_run_b_after_a_yes_the_later_check_finds_nothing_missing_and_asks_nothing(self):
        flat = re.sub(r"\s+", " ", self.history())
        self.assertRegex(flat, r"(?i)Stage 1a.{0,300}yes.{0,300}nothing (is )?missing.{0,100}asks? nothing")

    def test_run_c_after_a_no_stage_1_needs_a_profile_and_the_later_check_does_not_ask_again(self):
        flat = re.sub(r"\s+", " ", self.stage_1a())
        self.assertRegex(flat, r"(?i)\bno\b.{0,200}needs a profile.{0,100}Stage 2")
        hist = re.sub(r"\s+", " ", self.history())
        self.assertRegex(hist, r"(?i)Stage 1a.{0,300}\bno\b.{0,300}does not ask again.{0,200}command to run later")

    def test_run_d_plugin_not_found_the_first_step_to_reach_it_asks_and_that_is_the_one_ask(self):
        flat = re.sub(r"\s+", " ", read(self.FI))
        self.assertRegex(flat, r"(?i)NOT FOUND.{0,300}first.{0,200}asks? for the plugin path.{0,100}the run's one ask")


SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
FIX_ASK_FORBIDDEN = re.compile(r"(?i)\boffer\b|\bask\s+(?:the user|once|whether|if)\b|preview again|run the preview")
#: Stage 2 asks nothing about --fix; the run's one ask is Stage 1a's or the history record check's.
FIX_STAGE_2_REQUIRED = (r"(?i)\bStage 2 asks nothing about\b", r"(?i)\bone ask\b", r"\bStage 1a\b",
                        r"(?i)\bhistory record check\b")


def stage_2_fix_violations(text: str) -> list:
    """Sentences in Stage 2 that treat --fix as something Stage 2 offers, asks or re-previews (I-5).

    Every sentence holding --fix must say Stage 2 asks nothing about it and name the run's one ask. No sentence
    holding --fix, and no sentence of the scaffold-missing bullet, may offer, ask (with or without a condition)
    or promise to run the preview again.
    """
    stage = re.sub(r"\s+", " ", section(text, "## Stage 2", "## Stage 3"))
    bullet = re.search(r"- `scaffold-missing`:.*?(?= - `[a-z-]+`:|$)", stage)
    sentences = SENTENCE_END.split(stage)
    in_bullet = set(SENTENCE_END.split(bullet.group(0))) if bullet else set()
    bad = []
    for sentence in sentences:
        holds_fix = "--fix" in sentence
        if not holds_fix and not any(sentence in b or b in sentence for b in in_bullet):
            continue
        if FIX_ASK_FORBIDDEN.search(sentence):
            bad.append(sentence)
        elif holds_fix and not all(re.search(p, sentence) for p in FIX_STAGE_2_REQUIRED):
            bad.append(sentence)
    return bad


class Stage2FixIsNeverAskedTests(unittest.TestCase):
    """F2: the scaffold-missing bullet of Stage 2 must not take the run's one ask (I-5 runs a-d)."""

    FI = "skills/auto-improve-finish-install/SKILL.md"
    REWORDED = ("- `scaffold-missing`: the file is absent, and this command never creates it. Stage 2 asks nothing "
                "about `plugin_doctor.py --fix`: the run's one ask is Stage 1a's, or the history record check's "
                "when Stage 1a was skipped. Name the missing file and go on with the other files. Once the "
                "doctor's fix has created it, the next run of this skill proposes its content.")

    @staticmethod
    def planted(bullet: str) -> str:
        return "## Stage 2: files\n\n%s\n- `unrecognised`: never written.\n\n## Stage 3: hooks\n" % bullet

    def test_control_masters_bullet_fails(self):
        planted = self.planted("- `scaffold-missing`: the file is absent. This command never creates it. Offer to run\n"
                               "  `plugin_doctor.py --fix` (see \"The project history record\" for the ask-first rule), "
                               "then run the preview again.")
        self.assertTrue(stage_2_fix_violations(planted))

    def test_control_an_ask_whether_to_run_fix_fails(self):
        planted = self.planted("- `scaffold-missing`: the file is absent. Ask the user whether to run `plugin_doctor.py --fix`.")
        self.assertTrue(stage_2_fix_violations(planted))

    def test_control_the_conditional_ask_fails(self):
        planted = self.planted("- `scaffold-missing`: the file is absent. If this run has not yet asked about "
                               "`plugin_doctor.py --fix`, ask once.")
        self.assertTrue(stage_2_fix_violations(planted))

    def test_control_a_re_preview_promise_in_its_own_sentence_fails(self):
        planted = self.planted(self.REWORDED + " Then run the preview again.")
        self.assertTrue(stage_2_fix_violations(planted))

    def test_control_the_reworded_bullet_passes(self):
        self.assertEqual(stage_2_fix_violations(self.planted(self.REWORDED)), [])

    def test_the_real_stage_2_holds_no_fix_ask_offer_or_re_preview(self):
        text = read(self.FI)
        self.assertIn("`scaffold-missing`", section(text, "## Stage 2", "## Stage 3"))
        self.assertEqual(stage_2_fix_violations(text), [])
        self.assertEqual(fix_lines_without_ask(text), [])


class MemoryReferenceTextTests(unittest.TestCase):
    """I1, I2, Q4 and I6 pins."""

    REF = "skills/design-first/references/central-memory.md"
    CC = "skills/pr-merged/references/contract-completion.md"
    SUFFIX = ProjectHistoryRecordTextTests.SUFFIX

    @staticmethod
    def unavailable_examples_without_suffix(text: str, suffix: str) -> list:
        return [m for m in re.findall(r"`(Memory: unavailable[^`]*)`", text) if not m.endswith(suffix)]

    def test_i1_every_backticked_unavailable_example_ends_with_the_suffix(self):
        ref = read(self.REF)
        self.assertTrue(re.findall(r"`Memory: unavailable[^`]*`", ref), "the reference has the example")
        self.assertEqual(self.unavailable_examples_without_suffix(ref, self.SUFFIX), [])

    def test_i1_control_a_bare_example_is_found(self):
        planted = "print one line (`Memory: unavailable (tool-absent)`) and go on"
        self.assertEqual(len(self.unavailable_examples_without_suffix(planted, self.SUFFIX)), 1)
        good = "print one line (`Memory: unavailable (tool-absent)%s`)" % self.SUFFIX
        self.assertEqual(self.unavailable_examples_without_suffix(good, self.SUFFIX), [])

    def step_5a_1(self) -> str:
        m = re.search(r"(?ms)^\s+1\. \*\*Read the candidates.*?(?=^\s+2\. \*\*)", read(self.CC))
        self.assertIsNotNone(m, "5a.1")
        return re.sub(r"\s+", " ", m.group(0))

    def test_i2_5a_1_names_default_branch_unknown_and_the_one_rerun(self):
        s = self.step_5a_1()
        self.assertIn("default-branch-unknown", s)
        self.assertRegex(s, r"(?i)re-run.{0,200}--default-branch")
        self.assertIn("git symbolic-ref refs/remotes/origin/HEAD", s)
        self.assertRegex(s, r"(?i)from the user")
        self.assertRegex(s, r"(?i)never a guessed")

    def test_i2_control_the_old_text_fails(self):
        old = "1. **Read the candidates** It refuses `not-flipped`, `brief-not-carried` and `capture-not-enabled`."
        self.assertNotIn("default-branch-unknown", old)

    def test_the_step_labels_are_unchanged(self):
        text = read(self.CC)
        for label in ("1. **A read-only dry run first", "2. **Stop only when", "3. **Show the one confirmation",
                      "4. **On yes, disclose", "5. **Run for real", "5a. **Capture", "6. **Put the stable branch",
                      "7. **Copy exactly", "8. **Open a draft pull request", "9. **Remove the records worktree"):
            self.assertIn(label, text)
        for sub in ("Read the candidates", "No candidates ends the step silently", "Ask the capture question",
                    "Send each confirmed candidate", "Record the receipts", "No outcome of this step blocks"):
            self.assertIn(sub, text)

    def test_q4_section_3_records_the_empty_outcome_and_prints_one_line_with_the_suffix(self):
        sec = re.sub(r"\s+", " ", section(read(self.REF), "## 3.", "## 4."))
        m = re.search(r"(?i)An empty `items` list means an empty retrieval:(.{0,400})", sec)
        self.assertIsNotNone(m)
        self.assertNotRegex(m.group(1), r"(?i)print nothing|write nothing")
        self.assertRegex(m.group(1), r"(?i)record")
        self.assertIn("`Memory: enabled | <date>%s`" % self.SUFFIX, m.group(1))

    def test_i6_the_retrieve_tool_and_shape_rows_say_none_with_a_server_set_reports_unconfigured(self):
        text = read(".claude/project-profile.md")
        for slot in ("memory.retrieve-tool", "memory.shape"):
            row = [l for l in text.splitlines() if l.startswith("| `%s`" % slot)]
            self.assertEqual(len(row), 1, slot)
            self.assertRegex(row[0], r"(?i)`none` with a server set.{0,40}unconfigured", slot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
