"""RED suite for the component SCSS rule of architecture-guard.py (G-1 and G-2).

Contract: .claude/concepts/2026-10-07-query-builder-followups.md, sub-task 2
("SCSS rule wording and guard"), cases G1..G14.

Each case writes ``x.component.ts`` and ``x.component.scss`` into a fresh temp
folder, launches THIS worktree's ``architecture-guard.py`` (found relative to
this file, never the plugin copy and never the main checkout) with a Write
payload on stdin, and asserts the printed stderr TEXT.

Every stylesheet example is multi-line: the guard sees only a line that holds
nothing but ``name: value;`` (RX_CSS_PROP), so the property sits alone on its
own line.

"Warned" means the line ``line <n>: <property text>`` appears in stderr. Both
today's output and the new G-2 layout print that form, so the controls assert
something that holds before and after the change.

Labels (against the guard BEFORE the GREEN change, by real result):
  FAIL TODAY (by assertion): G1 G4 G4b G7 G11 G12
  PASS TODAY (controls):     G2 G2b G3 G5 G6a G6b G14 G8 G9 G10 G13
Labels (added after the review; against the CURRENT guard):
  FAIL NOW (by assertion, code review W-1/N-2 drift): G15 G16 G17 G18
Round 3 additions (labels recorded in the handoff after running): G19..G24.
G1/G5/G7/G11 (and G2b) also append an unscoped rule that must still be warned, and assert
there is no "internal error", so a crashed or never-closing allowed context cannot pass.

Run:  py -3 .claude\\hooks\\tests\\test_architecture_guard_scss.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
GUARD = HOOKS_DIR / "architecture-guard.py"
REPO_ROOT = HOOKS_DIR.parent.parent

DEAD_HOST_SUGGESTION = (
    "`:host` matches nothing in a ViewEncapsulation.None component, so the "
    "browser discards this rule. Scope it under the component's element "
    "selector instead, for example `my-widget .vendor-class`."
)
RAW_PROPERTY_SUGGESTION = (
    "This property has a 1:1 Tailwind utility. Move it to the template as a "
    "class. In a ViewEncapsulation.None component, a rule scoped under the "
    "component's element selector may keep it here."
)

#: stderr of today's guard for the height-chain template warning, with the
#: written file's path replaced by <PATH>. Captured from the unchanged guard.
G13_EXPECTED = (
    "\n"
    "--------------------------------------------------------------\n"
    "[architecture-guard] WARN -- component SCSS has raw properties: <PATH>\n"
    "--------------------------------------------------------------\n"
    '  line 1: <div class="p-2"\n'
    "  -> Move these to the template as Tailwind utilities. See the design-pattern document.\n"
    "--------------------------------------------------------------\n"
    "\n"
)

G1_SCSS = "my-widget .vendor-x {\n  padding: 0;\n}\n"
G4_SCSS = ":host ::ng-deep .vendor-x {\n  padding: 0;\n}\n"
WARNED_PADDING = re.compile(r"line \d+: padding: 0;")
WARNED_MARGIN = re.compile(r"line \d+: margin: 0;")
#: A second, unscoped rule appended after a quiet one. It must be warned in every mode, so a
#: run that stays quiet on the first rule AND loud on this one proves the guard did not crash
#: (fail-open) and did not leave an allowed context open for the rest of the file.
AFTER_RULE = ".cb-after {\n  margin: 0;\n}\n"


def component_ts(encapsulation_line: str | None, selector: str = "my-widget",
                 import_line: str | None = None) -> str:
    """Return a minimal component source with the given encapsulation line."""
    imp = import_line or "import { Component, ViewEncapsulation } from '@angular/core';"
    enc = f",\n  {encapsulation_line}" if encapsulation_line else ""
    return (
        f"{imp}\n"
        f"@Component({{\n  selector: '{selector}',\n  template: ''{enc}\n}})\n"
        "export class XComponent {}\n"
    )


NONE_TS = component_ts("encapsulation: ViewEncapsulation.None")


class Result:
    def __init__(self, returncode: int, stderr: str, path: str):
        self.returncode = returncode
        self.stderr = stderr
        self.path = path

    def warned(self) -> bool:
        return bool(WARNED_PADDING.search(self.stderr))

    def after_warned(self) -> bool:
        return bool(WARNED_MARGIN.search(self.stderr))

    def crashed(self) -> bool:
        return "internal error" in self.stderr


def run_guard(files: dict[str, str | bytes], written: str) -> Result:
    """Write ``files`` into a temp dir, run the worktree guard on ``written``."""
    with tempfile.TemporaryDirectory(prefix="archguard_scss_") as tmp:
        for name, body in files.items():
            target = Path(tmp) / name
            if isinstance(body, bytes):
                target.write_bytes(body)
            else:
                target.write_text(body, encoding="utf-8", newline="\n")
        target_path = str(Path(tmp) / written)
        content = files[written]
        assert isinstance(content, str)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": target_path, "content": content},
        }
        proc = subprocess.run(
            [sys.executable, str(GUARD)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        return Result(proc.returncode, proc.stderr, target_path)


def run_scss(scss: str, ts: str | bytes | None) -> Result:
    files: dict[str, str | bytes] = {"x.component.scss": scss}
    if ts is not None:
        files["x.component.ts"] = ts
    return run_guard(files, "x.component.scss")


def assert_quiet_then_loud(tc: unittest.TestCase, r: Result) -> None:
    """The first (padding) rule is quiet, the appended unscoped rule is loud, nothing crashed."""
    tc.assertEqual(r.returncode, 0)
    tc.assertFalse(r.crashed(),
                   f"the guard must not hit its fail-open wrapper; stderr was:\n{r.stderr}")
    tc.assertFalse(r.warned(),
                   f"the scoped rule must not be warned; stderr was:\n{r.stderr}")
    tc.assertTrue(r.after_warned(),
                  "the unscoped rule AFTER the quiet one must still be warned (the allowed "
                  f"context must close); stderr was:\n{r.stderr}")


class GuardIsTheWorktreeCopy(unittest.TestCase):
    def test_guard_under_test_is_this_worktrees_copy(self):
        self.assertTrue(GUARD.is_file(), "the worktree guard file must exist")
        self.assertEqual(GUARD.resolve().parent.parent.parent, REPO_ROOT.resolve())
        self.assertNotIn("plugins", str(GUARD.resolve()).lower().split("\\"))


class FailToday(unittest.TestCase):
    def test_g1_unencapsulated_element_scoped_rule_is_not_warned(self):
        r = run_scss(G1_SCSS + AFTER_RULE, NONE_TS)
        assert_quiet_then_loud(self, r)

    def test_g4_dead_host_group_and_raw_property_group_each_print_once(self):
        r = run_scss(G4_SCSS, NONE_TS)
        self.assertEqual(r.returncode, 0)
        self.assertIn("[scss-warn:dead-host]", r.stderr)
        self.assertEqual(r.stderr.count(DEAD_HOST_SUGGESTION), 1, r.stderr)
        self.assertIn("[scss-warn:raw-property]", r.stderr)
        self.assertEqual(r.stderr.count(RAW_PROPERTY_SUGGESTION), 1, r.stderr)

    def test_g4b_dead_host_group_only_when_no_raw_property(self):
        scss = ":host ::ng-deep .vendor-x {\n  @apply p-0;\n}\n"
        r = run_scss(scss, NONE_TS)
        self.assertEqual(r.returncode, 0)
        self.assertIn("[scss-warn:dead-host]", r.stderr)
        self.assertNotIn("[scss-warn:raw-property]", r.stderr)
        self.assertNotIn("This property has a 1:1 Tailwind utility", r.stderr)

    def test_g7_aliased_none_import_and_numeric_two_are_unencapsulated(self):
        aliased = component_ts(
            "encapsulation: VE.None",
            import_line="import { Component, ViewEncapsulation as VE } from '@angular/core';",
        )
        numeric = component_ts("encapsulation: 2")
        for label, ts in (("VE.None", aliased), ("2", numeric)):
            with self.subTest(spelling=label):
                r = run_scss(G1_SCSS + AFTER_RULE, ts)
                assert_quiet_then_loud(self, r)

    def test_g11_own_class_under_the_element_scope_is_silent(self):
        r = run_scss("my-widget .own {\n  padding: 0;\n}\n" + AFTER_RULE, NONE_TS)
        assert_quiet_then_loud(self, r)

    def test_g12_warned_stylesheet_prints_the_new_banner(self):
        r = run_scss(".cb-a {\n  padding: 0;\n}\n", NONE_TS)
        self.assertEqual(r.returncode, 0)
        self.assertIn("component SCSS warnings", r.stderr)


class PassTodayControls(unittest.TestCase):
    def test_g2_import_names_view_encapsulation_but_no_key_is_unclassified_and_warned(self):
        # component_ts(None) still imports ViewEncapsulation, so the guard classifies this as
        # "unclassified" (not "default"); the true default case is G2b below.
        r = run_scss(G1_SCSS, component_ts(None))
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.warned(), r.stderr)

    def test_g2b_true_default_component_ng_deep_block_is_quiet_without_dead_host(self):
        # No ViewEncapsulation anywhere in the file: the real default component.
        ts = component_ts(None, import_line="import { Component } from '@angular/core';")
        r = run_scss(G4_SCSS + AFTER_RULE, ts)
        self.assertEqual(r.returncode, 0)
        self.assertFalse(r.crashed(), r.stderr)
        self.assertFalse(r.warned(),
                         f"a default component's :host ::ng-deep block keeps raw properties; stderr:\n{r.stderr}")
        self.assertNotIn("[scss-warn:dead-host]", r.stderr,
                         "a default component has a host element, so :host is not dead")
        self.assertTrue(r.after_warned(), r.stderr)

    def test_g3_own_class_block_in_none_component_is_warned(self):
        r = run_scss(".cb-a {\n  padding: 0;\n}\n", NONE_TS)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.warned(), r.stderr)

    def test_g5_encapsulated_ng_deep_block_is_quiet(self):
        ts = component_ts("encapsulation: ViewEncapsulation.Emulated")
        r = run_scss(G4_SCSS + AFTER_RULE, ts)
        assert_quiet_then_loud(self, r)
        self.assertNotIn("[scss-warn:dead-host]", r.stderr,
                         "an encapsulated component has a host element, so :host ::ng-deep is not dead")

    def test_g6a_missing_sibling_ts_still_warns_and_exits_zero(self):
        r = run_scss(G1_SCSS, None)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.warned(), r.stderr)

    def test_g6b_undecodable_sibling_ts_still_warns(self):
        bad = NONE_TS.encode("utf-8") + b"\n// \xff\xfe\n"
        r = run_scss(G1_SCSS, bad)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.warned(), r.stderr)

    def test_g14_non_element_selector_is_not_a_scope(self):
        ts = component_ts("encapsulation: ViewEncapsulation.None", selector="[myWidget]")
        r = run_scss("[myWidget] .vendor-x {\n  padding: 0;\n}\n", ts)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.warned(), r.stderr)

    def test_g8_sibling_combinator_after_scope_is_warned(self):
        r = run_scss("my-widget ~ .vendor-x {\n  padding: 0;\n}\n", NONE_TS)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.warned(), r.stderr)

    def test_g9_every_comma_member_must_be_scoped(self):
        same_line = "my-widget .vendor-x, .other .y {\n  padding: 0;\n}\n"
        split_unscoped_first = ".other .y,\nmy-widget .vendor-x {\n  padding: 0;\n}\n"
        for label, scss in (("one line", same_line), ("split, unscoped first", split_unscoped_first)):
            with self.subTest(form=label):
                r = run_scss(scss, NONE_TS)
                self.assertEqual(r.returncode, 0)
                self.assertTrue(r.warned(), r.stderr)

    def test_g10_other_encapsulation_values_are_warned(self):
        spellings = [
            "encapsulation: ViewEncapsulation.Emulated",
            "encapsulation: 0",
            "encapsulation: ViewEncapsulation.ShadowDom",
            "encapsulation: 3",
            "encapsulation: someFlag",
        ]
        for line in spellings:
            with self.subTest(spelling=line):
                r = run_scss(G1_SCSS, component_ts(line))
                self.assertEqual(r.returncode, 0)
                self.assertTrue(r.warned(), r.stderr)

    def test_g13_template_height_chain_output_is_unchanged(self):
        html = '<div class="p-2">\n  <div class="scroll-edge flex-1 min-h-0"></div>\n</div>\n'
        r = run_guard({"x.component.html": html}, "x.component.html")
        self.assertEqual(r.returncode, 0)
        actual = r.stderr.replace(r.path, "<PATH>")
        self.assertEqual(actual, G13_EXPECTED)


def raw_ts(*decorator_lines: str, before: str = "", imp: str = "import { Component } from '@angular/core';") -> str:
    """A component source with extra raw lines inside the decorator and optional text before it."""
    body = "".join(f"  {line}\n" for line in decorator_lines)
    return (
        f"{imp}\n{before}"
        f"@Component({{\n  selector: 'my-widget',\n  template: '',\n{body}}})\n"
        "export class XComponent {}\n"
    )


class CommentedOutKeyAndDecoratorScope(unittest.TestCase):
    """Code review W-1 and N-2: the guard must read the component, not its comments."""

    def _assert_default_ng_deep_is_honest(self, ts: str) -> None:
        # Test review W-A: a same-run loud anchor (AFTER_RULE must be warned) and a crash check,
        # so a crashed scan cannot look like a correct quiet result.
        r = run_scss(G4_SCSS + AFTER_RULE, ts)
        self.assertEqual(r.returncode, 0)
        self.assertFalse(r.crashed(),
                         f"the guard must not hit its fail-open wrapper; stderr was:\n{r.stderr}")
        self.assertNotIn("[scss-warn:dead-host]", r.stderr,
                         "a commented-out encapsulation key does not make the component "
                         f"unencapsulated, so :host is not dead; stderr was:\n{r.stderr}")
        self.assertFalse(r.warned(),
                         "a default component's :host ::ng-deep block keeps raw properties; "
                         f"stderr was:\n{r.stderr}")
        self.assertTrue(r.after_warned(),
                        "the unscoped rule AFTER the quiet block must still be warned; "
                        f"stderr was:\n{r.stderr}")

    def test_g15_line_commented_out_none_key_leaves_a_default_component(self):
        self._assert_default_ng_deep_is_honest(
            raw_ts("// encapsulation: ViewEncapsulation.None,"))

    def test_g16_block_commented_out_none_key_leaves_a_default_component(self):
        self._assert_default_ng_deep_is_honest(
            raw_ts("/* encapsulation: ViewEncapsulation.None, */"))

    def test_g17_commented_out_key_beside_a_live_none_key_still_reads_the_live_one(self):
        ts = raw_ts("// encapsulation: ViewEncapsulation.Emulated,",
                    "encapsulation: ViewEncapsulation.None,",
                    imp="import { Component, ViewEncapsulation } from '@angular/core';")
        r = run_scss(G1_SCSS + AFTER_RULE, ts)
        assert_quiet_then_loud(self, r)

    def test_g18_component_selector_is_used_not_an_earlier_decorators(self):
        before = "@Directive({\n  selector: '[dir]',\n})\nexport class DirDirective {}\n"
        ts = raw_ts("encapsulation: ViewEncapsulation.None,", before=before,
                    imp="import { Component, Directive, ViewEncapsulation } from '@angular/core';")
        r = run_scss(G1_SCSS + AFTER_RULE, ts)
        assert_quiet_then_loud(self, r)

    def test_g19_regex_quote_then_commented_out_key_is_still_a_default_component(self):
        # Code review pass 2, W-1: a stray ' (a regex literal) must not put the rest of the file
        # "inside a string", because a ' string ends at a line break.
        ts = raw_ts("// encapsulation: ViewEncapsulation.None,", before="const r = /'/;\n")
        self._assert_default_ng_deep_is_honest(ts)

    def test_g20_live_none_key_after_a_regex_quote_still_reads_none(self):
        ts = raw_ts("encapsulation: ViewEncapsulation.None,", before="const r = /'/;\n",
                    imp="import { Component, ViewEncapsulation } from '@angular/core';")
        r = run_scss(G1_SCSS + AFTER_RULE, ts)
        assert_quiet_then_loud(self, r)

    def test_g21_live_none_key_after_a_double_quote_oddity_still_reads_none(self):
        ts = raw_ts("encapsulation: ViewEncapsulation.None,", before='const r = /"/;\n// note\n',
                    imp="import { Component, ViewEncapsulation } from '@angular/core';")
        r = run_scss(G1_SCSS + AFTER_RULE, ts)
        assert_quiet_then_loud(self, r)

    def test_g22_doc_comment_before_the_decorator_leaves_a_none_component_none(self):
        # Test review pass 2, W-A / N-a: a /** doc */ comment (and a quoted '/*') must not make
        # the guard lose the key or crash in its block-comment branch.
        imp = "import { Component, ViewEncapsulation } from '@angular/core';"
        for label, before in (("doc comment", "/** Doc for the widget. */\n"),
                              ("quoted slash-star then doc", "const g = '/*';\n/** Doc. */\n")):
            with self.subTest(before=label):
                ts = raw_ts("encapsulation: ViewEncapsulation.None,", before=before, imp=imp)
                r = run_scss(G1_SCSS + AFTER_RULE, ts)
                assert_quiet_then_loud(self, r)


class TrailingCommentAfterCommaMember(unittest.TestCase):
    """Code review pass 2, W-2: a trailing comment must not break comma-member joining."""

    def test_g23_unscoped_comma_member_with_a_trailing_comment_is_still_warned(self):
        for label, first in (("line comment", ".other, // legacy"),
                             ("block comment", ".other, /* legacy */")):
            with self.subTest(comment=label):
                r = run_scss(f"{first}\nmy-widget .y {{\n  padding: 0;\n}}\n", NONE_TS)
                self.assertEqual(r.returncode, 0)
                self.assertFalse(r.crashed(), r.stderr)
                self.assertTrue(r.warned(),
                                "the unscoped comma member `.other` must make the whole rule "
                                f"warned; stderr was:\n{r.stderr}")

    def test_g24_scoped_comma_members_with_a_trailing_comment_stay_quiet(self):
        r = run_scss("my-widget .x, // both scoped\nmy-widget .y {\n  padding: 0;\n}\n" + AFTER_RULE,
                     NONE_TS)
        assert_quiet_then_loud(self, r)


class ClosedBlockCommentInsideSelectorLine(unittest.TestCase):
    """Code review pass 3, W-3: a CLOSED comment must not cut the rest of the selector line."""

    def test_g25a_unscoped_member_before_a_closed_comment_is_still_warned(self):
        r = run_scss(".other /* x */,\nmy-widget .b {\n  padding: 0;\n}\n", NONE_TS)
        self.assertEqual(r.returncode, 0)
        self.assertFalse(r.crashed(), r.stderr)
        self.assertTrue(r.warned(),
                        "the unscoped member `.other` (followed by a closed comment and a "
                        f"comma) must make the rule warned; stderr was:\n{r.stderr}")

    def test_g25b_closed_comment_after_a_scoped_selector_stays_quiet(self):
        r = run_scss("my-widget .a /* note */ {\n  padding: 0;\n}\n" + AFTER_RULE, NONE_TS)
        assert_quiet_then_loud(self, r)

    def test_g25c_closed_comment_between_scope_and_class_stays_quiet(self):
        r = run_scss("my-widget /* c */ .a {\n  padding: 0;\n}\n" + AFTER_RULE, NONE_TS)
        assert_quiet_then_loud(self, r)

    def test_g25d_unclosed_comment_on_a_selector_line_is_cut_safely(self):
        r = run_scss("my-widget .a { /* never closed\n  padding: 0;\n}\n", NONE_TS)
        self.assertEqual(r.returncode, 0)
        self.assertFalse(r.crashed(),
                         f"an unclosed comment must not crash the guard; stderr was:\n{r.stderr}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
