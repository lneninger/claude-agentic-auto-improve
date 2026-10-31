"""RED suite for the guard's post-edit view and matching precision (G-4, G-5, V-2).

Contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md, sub-task t1
(ledger rows W4 W5 W6a W6b W7 W8 W11, rules G-4, G-5, V-2).

Every case launches THIS worktree's ``architecture-guard.py`` in a subprocess, with a JSON
event on stdin and ``CLAUDE_PROJECT_DIR`` pointing at a fresh temp project, and asserts the
exit code and the printed stderr. Nothing is imported from the guard, so absent behaviour
shows up as an assertion failure.

Forced-raise tests (one per V-2 step)
-------------------------------------
A step has to be forceable to raise, so the guard needs a module-level function for it. The
tests find the step by NAME, with a case-insensitive regex over the guard's own module-level
functions. The names the GREEN step must give its seams contain:

    view builder ............................ "view"            (e.g. build_post_edit_view)
    per-call whole-file pass ................ "whole_file"      (e.g. scan_whole_file_rules)
    view-against-disk comparison ............ "introduc|compar" (e.g. rule_is_introduced)
    de-duplication .......................... "dedup|dedupe|unique|duplicate"
    G-5 reference-variable test ............. "reference|ref_var|refvar"

A tiny runner (written into the temp project, so it is removed with it) loads the guard,
replaces every matching function with one that raises, then calls ``main()`` with the same
outer catch as the guard's ``__main__`` block. A forced-raise test passes only when
  (1) at least one seam was found,
  (2) at least one seam was called (the step ran), and
  (3) the guard still exits 2 on text that blocks today (fail closed).

Run:  py -3 .claude\\hooks\\tests\\test_architecture_guard_precision.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
GUARD = HOOKS_DIR / "architecture-guard.py"
REPO_ROOT = HOOKS_DIR.parent.parent

WARN_HEADER = "[architecture-guard] WARN"

RUNNER_SOURCE = '''\
import importlib.util
import re
import sys
import types

guard, pattern, seams_file, fired_file = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("architecture_guard_under_test", guard)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

rx = re.compile(pattern, re.IGNORECASE)
skip = {"main", "log", "log_event"}
names = [
    n for n, v in vars(mod).items()
    if isinstance(v, types.FunctionType) and v.__module__ == mod.__name__
    and n not in skip and rx.search(n)
]
open(seams_file, "w", encoding="utf-8").write("\\n".join(names))
open(fired_file, "w", encoding="utf-8").write("")


def make(name):
    def forced(*args, **kwargs):
        with open(fired_file, "a", encoding="utf-8") as fh:
            fh.write(name + "\\n")
        raise RuntimeError("forced V-2 fault in " + name)
    return forced


for n in names:
    setattr(mod, n, make(n))

try:
    mod.main()
except SystemExit:
    raise
except Exception as e:  # same outer catch as the guard's __main__ block
    mod.log("internal error (failing open): %s" % e)
    sys.exit(0)
'''

#: Step name -> (regex over guard function names, human description).
STEPS = {
    "view builder": (r"view", "a function whose name contains 'view'"),
    "whole-file pass": (r"whole_?file", "a function whose name contains 'whole_file'"),
    "view-against-disk comparison": (r"introduc|compar", "a function whose name contains 'introduc' or 'compar'"),
    "de-duplication": (r"dedup|unique|duplicate", "a function whose name contains 'dedup', 'unique' or 'duplicate'"),
    "G-5 reference test": (r"reference|ref_?var", "a function whose name contains 'reference' or 'ref_var'"),
}


class Result:
    def __init__(self, returncode: int, stderr: str, seams: list[str] | None = None,
                 fired: list[str] | None = None):
        self.returncode = returncode
        self.stderr = stderr
        self.seams = seams
        self.fired = fired


def run(rel: str, tool_name: str, tool_input: dict, disk: str | bytes | None = None,
        step: str | None = None) -> Result:
    """Run the guard once. ``disk`` pre-creates the target (bytes are written as given)."""
    with tempfile.TemporaryDirectory(prefix="archguard_prec_") as tmp:
        project = Path(tmp).resolve()
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if disk is not None:
            target.write_bytes(disk if isinstance(disk, bytes) else disk.encode("utf-8"))
        tool_input = {"file_path": str(target), **tool_input}
        payload = {"tool_name": tool_name, "tool_input": tool_input}
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_ARCH_GUARD"}
        env["CLAUDE_PROJECT_DIR"] = str(project)
        if step is None:
            argv = [sys.executable, str(GUARD)]
            seams_file = fired_file = None
        else:
            runner = project / "_runner.py"
            runner.write_text(RUNNER_SOURCE, encoding="utf-8")
            seams_file = project / "_seams.txt"
            fired_file = project / "_fired.txt"
            argv = [sys.executable, "-I", str(runner), str(GUARD), STEPS[step][0],
                    str(seams_file), str(fired_file)]
        proc = subprocess.run(
            argv, input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=str(REPO_ROOT), env=env, timeout=60,
        )
        seams = fired = None
        if seams_file is not None and seams_file.exists():
            seams = [s for s in seams_file.read_text(encoding="utf-8").splitlines() if s]
        if fired_file is not None and fired_file.exists():
            fired = [s for s in fired_file.read_text(encoding="utf-8").splitlines() if s]
        return Result(proc.returncode, proc.stderr, seams, fired)


def edit(rel: str, old: str, new: str, disk: str | bytes | None, replace_all: bool = False,
         step: str | None = None) -> Result:
    ti = {"old_string": old, "new_string": new}
    if replace_all:
        ti["replace_all"] = True
    return run(rel, "Edit", ti, disk, step)


def multi(rel: str, edits: list[tuple[str, str]], disk: str | bytes | None,
          step: str | None = None) -> Result:
    return run(rel, "MultiEdit",
               {"edits": [{"old_string": o, "new_string": n} for o, n in edits]}, disk, step)


def write(rel: str, content: str) -> Result:
    return run(rel, "Write", {"content": content})


HTML = "src/x.component.html"
TS = "src/x.component.ts"
SCSS = "src/x.component.scss"

#: A fragment whose own first <div> has no height, and which holds the height-chain anchor.
FRAGMENT = '<div class="p-2">\n  <table class="scroll-edge flex-1 min-h-0"></table>\n</div>'
#: A file whose root claims height, with one slot for the fragment.
DISK_H_FULL = '<div class="h-full">\n  <p>x</p>\n  PLACEHOLDER\n</div>\n'
DISK_NO_HEIGHT = '<div class="p-4">\n  <p>x</p>\n  PLACEHOLDER\n</div>\n'

TS_PLAIN = (
    "@Component({\n"
    "  selector: 'x-y',\n"
    "  templateUrl: './x.component.html',\n"
    "})\n"
    "export class X {}\n"
)
TS_WITH_TEMPLATE = (
    "@Component({\n"
    "  selector: 'x-y',\n"
    "  template: '<p></p>',\n"
    "})\n"
    "export class X {}\n"
)


def blocked_rules(stderr: str) -> list[str]:
    return re.findall(r"^\s*\[([^\]]+)\]", stderr, flags=re.MULTILINE)


class PostEditViewTests(unittest.TestCase):
    """G-4: whole-file rules are judged once per file on the post-edit view."""

    # --- W7: the height chain sees the whole file -------------------------------------

    def test_fragment_inside_file_with_h_full_root_gives_no_warning(self):
        r = edit(HTML, "PLACEHOLDER", FRAGMENT, DISK_H_FULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(WARN_HEADER, r.stderr,
                         "W7: the root <div> of the whole file carries h-full, so the fragment "
                         "must not trigger the height-chain warning")

    def test_control_fragment_inside_file_without_root_height_still_warns(self):
        r = edit(HTML, "PLACEHOLDER", FRAGMENT, DISK_NO_HEIGHT)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(WARN_HEADER, r.stderr,
                      "the view's root has no height, so the height-chain warning must stay")

    def test_replace_all_builds_the_view(self):
        disk = '<div class="h-full">\n  PLACEHOLDER\n  <p>x</p>\n  PLACEHOLDER\n</div>\n'
        r = edit(HTML, "PLACEHOLDER", FRAGMENT, disk, replace_all=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(WARN_HEADER, r.stderr,
                         "replace_all applies to every occurrence, so the view exists and its "
                         "root h-full silences the warning")

    def test_ambiguous_old_string_makes_the_view_unavailable(self):
        disk = '<div class="h-full">\n  PLACEHOLDER\n  <p>x</p>\n  PLACEHOLDER\n</div>\n'
        r = edit(HTML, "PLACEHOLDER", FRAGMENT, disk)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(WARN_HEADER, r.stderr,
                      "old-string-ambiguous: no view, so the fragment is judged as today (warns)")

    def test_missing_file_makes_the_view_unavailable(self):
        r = edit(HTML, "PLACEHOLDER", FRAGMENT, disk=None)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(WARN_HEADER, r.stderr,
                      "file-unreadable: no view, so the fragment is judged as today (warns)")

    def test_old_string_missing_from_disk_makes_the_view_unavailable(self):
        r = edit(HTML, "NOT THERE", FRAGMENT, DISK_H_FULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(WARN_HEADER, r.stderr,
                      "old-string-missing: no view, so the fragment is judged as today (warns)")

    def test_non_utf8_bytes_make_the_view_unavailable(self):
        disk = b'<div class="h-full">\n  <p>\xff\xfe</p>\n  PLACEHOLDER\n</div>\n'
        r = edit(HTML, "PLACEHOLDER", FRAGMENT, disk)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(WARN_HEADER, r.stderr,
                      "not-utf8: no view, so the fragment is judged as today (warns)")

    def test_missing_file_still_blocks_a_line_violation(self):
        r = edit(HTML, "PLACEHOLDER", '<p class="text-gray-500"></p>', disk=None)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("[gray-utility:text-gray]", r.stderr)

    def test_crlf_file_still_gets_a_view(self):
        disk = b'<div class="h-full">\r\n  <p>x</p>\r\n  PLACEHOLDER\r\n</div>\r\n'
        r = edit(HTML, "  <p>x</p>\n  PLACEHOLDER", "  <p>x</p>\n  " + FRAGMENT, disk)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(WARN_HEADER, r.stderr,
                         "CRLF is folded to LF in disk text and old_string, so a multi-line "
                         "old_string matches and the view's h-full root silences the warning")

    def test_crlf_in_new_string_is_folded_too(self):
        disk = b'<div class="h-full">\r\n  <p>x</p>\r\n  PLACEHOLDER\r\n</div>\r\n'
        r = edit(HTML, "PLACEHOLDER", FRAGMENT.replace("\n", "\r\n"), disk)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(WARN_HEADER, r.stderr)

    def test_write_keeps_todays_behaviour(self):
        r = write(HTML, FRAGMENT + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(WARN_HEADER, r.stderr, "a Write is judged on its own content, as today")

    # --- W6a / frequency: once per file per call -------------------------------------

    def test_three_edit_multiedit_reports_the_height_warning_once(self):
        disk = '<div class="p-4">\n  AAA\n  BBB\n  CCC\n</div>\n'
        r = multi(HTML, [("AAA", FRAGMENT), ("BBB", FRAGMENT), ("CCC", FRAGMENT)], disk)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr.count(WARN_HEADER), 1,
                         "the whole-file pass runs once per file per call, not once per edit:\n" + r.stderr)

    def test_three_edit_multiedit_reports_each_line_violation_once(self):
        disk = '<div class="h-full">\n  AAA\n  BBB\n  CCC\n</div>\n'
        r = multi(HTML, [("AAA", '<p class="text-gray-500"></p>'),
                         ("BBB", '<p class="bg-gray-100"></p>'),
                         ("CCC", '<p class="border-gray-200"></p>')], disk)
        self.assertEqual(r.returncode, 2, r.stderr)
        rules = blocked_rules(r.stderr)
        for rule in ("gray-utility:text-gray", "gray-utility:bg-gray", "gray-utility:border-gray"):
            self.assertEqual(rules.count(rule), 1,
                             f"{rule} must be reported exactly once; got {rules}\n{r.stderr}")

    def test_three_edit_multiedit_reports_the_inline_template_once(self):
        disk = (
            "@Component({\n  selector: 'x-y',\n  templateUrl: './x.component.html',\n})\n"
            "export class X {\n  AAA\n  BBB\n}\n"
        )
        r = multi(TS, [("  templateUrl: './x.component.html',", "  template: '<p></p>',"),
                       ("AAA", "a = 1;"), ("BBB", "b = 2;")], disk)
        self.assertEqual(r.returncode, 2,
                         "the view has an inline template that the disk text did not\n" + r.stderr)
        self.assertEqual(blocked_rules(r.stderr).count("inline-component-template"), 1, r.stderr)

    # --- Inline template and styles --------------------------------------------------

    def test_edit_adding_template_inside_existing_decorator_blocks(self):
        r = edit(TS, "  templateUrl: './x.component.html',", "  template: '<p></p>',", TS_PLAIN)
        self.assertEqual(r.returncode, 2,
                         "the post-edit view holds an inline template that the disk text did not\n" + r.stderr)
        self.assertIn("[inline-component-template]", r.stderr)

    def test_edit_adding_styles_inside_existing_decorator_blocks(self):
        r = edit(TS, "  templateUrl: './x.component.html',",
                 "  templateUrl: './x.component.html',\n  styles: ['p{}'],", TS_PLAIN)
        self.assertEqual(r.returncode, 2,
                         "the post-edit view holds inline styles that the disk text did not\n" + r.stderr)
        self.assertIn("[inline-component-styles]", r.stderr)

    def test_edit_elsewhere_in_file_with_inline_template_gives_todays_result(self):
        r = edit(TS, "export class X {}", "export class Y {}", TS_WITH_TEMPLATE)
        self.assertEqual(r.returncode, 0,
                         "the inline template was already on disk and the edit did not introduce it\n" + r.stderr)

    def test_rewriting_an_existing_inline_template_line_gives_todays_result(self):
        r = edit(TS, "  template: '<p></p>',", "  template: '<b></b>',", TS_WITH_TEMPLATE)
        self.assertEqual(r.returncode, 0,
                         "not introduced by this edit: disk and view both hold the pattern\n" + r.stderr)

    def test_new_string_carrying_the_whole_decorator_still_blocks(self):
        r = edit(TS, "export class X {}",
                 "@Component({ template: '<p></p>' })\nexport class Y {}", TS_PLAIN)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("[inline-component-template]", r.stderr)

    def test_adding_template_to_a_missing_file_gives_todays_result(self):
        r = edit(TS, "x", "  template: '<p></p>',", disk=None)
        self.assertEqual(r.returncode, 0,
                         "no view: the fragment alone has no decorator, exactly as today\n" + r.stderr)

    # --- Accepted limits that the tests pin (W5, W6b, W8, W11) -----------------------

    def test_w5_relative_and_absolute_are_allowed(self):
        r = write(HTML, '<div class="relative"><span class="absolute top-0"></span></div>\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("BLOCKED", r.stderr)

    def test_w6b_two_edits_forming_a_gray_utility_pass(self):
        disk = '<div class="h-full">\n  <p class="AAA BBB"></p>\n</div>\n'
        r = multi(HTML, [("AAA", "text-gr"), ("BBB", "ay-500")], disk)
        self.assertEqual(r.returncode, 0,
                         "W6b is an accepted limit: line rules judge each edit's new text\n" + r.stderr)

    def test_w8_stylesheet_rules_only_warn(self):
        r = write(SCSS, ".a {\n  padding: 0;\n}\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(WARN_HEADER, r.stderr, "the stylesheet still warns about the raw property")

    def test_w11_edit_completing_a_violation_started_on_disk_passes(self):
        disk = '<div class="h-full">\n  <p class="text-gra"></p>\n</div>\n'
        r = edit(HTML, 'class="text-gra"', 'class="text-gray-500"', disk)
        self.assertEqual(r.returncode, 2,
                         "control: the new text itself holds the whole token, so it blocks\n" + r.stderr)
        disk2 = '<div class="h-full">\n  <p class="text-gra#"></p>\n</div>\n'
        r2 = edit(HTML, "#", "y-500", disk2)
        self.assertEqual(r2.returncode, 0,
                         "W11 is an accepted limit: new text 'y-500' alone has no violation\n" + r2.stderr)


class HexColorPrecisionTests(unittest.TestCase):
    """G-5: a template reference variable is not a colour."""

    def check_allowed(self, line: str):
        r = write(HTML, line + "\n")
        self.assertEqual(r.returncode, 0, f"{line!r} is a template reference variable\n" + r.stderr)
        self.assertNotIn("[hex-color]", r.stderr)

    def check_blocked(self, line: str):
        r = write(HTML, line + "\n")
        self.assertEqual(r.returncode, 2, f"{line!r} is a colour and must block\n" + r.stderr)
        self.assertIn("[hex-color]", r.stderr)

    def test_allowed_input_reference_add(self):
        self.check_allowed("<input #add>")

    def test_allowed_menu_reference_bed_with_export_as(self):
        self.check_allowed('<mat-menu #bed="matMenu">')

    def test_allowed_bare_reference_line_facade(self):
        self.check_allowed("  #facade")

    def test_blocked_attribute_value_fill_add(self):
        self.check_blocked('<rect fill="#add"></rect>')

    def test_blocked_quoted_in_binding(self):
        self.check_blocked("<div [style.color]=\"'#abc'\"></div>")

    def test_blocked_text_node_ff0000(self):
        self.check_blocked('<span class="x">#ff0000</span>')

    def test_blocked_bare_line_ff0000(self):
        self.check_blocked("  #ff0000")

    def test_blocked_inline_style_value(self):
        self.check_blocked('<div style="color:#fff"></div>')

    def test_pinned_limit_bare_fff_line_passes(self):
        r = write(HTML, "  #fff\n")
        self.assertEqual(r.returncode, 0,
                         "accepted G-5 limit: a 3-character digit-free token in reference "
                         "position is read as a reference variable\n" + r.stderr)

    def test_edit_path_applies_g5_too(self):
        r = edit(HTML, "PLACEHOLDER", "<input #add>", DISK_H_FULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("[hex-color]", r.stderr)


class FailClosedTests(unittest.TestCase):
    """V-2: each new step falls back to the stricter outcome when it raises."""

    def forced(self, step: str, result: Result):
        desc = STEPS[step][1]
        self.assertTrue(result.seams,
                        f"V-2 step '{step}' has no seam: the guard needs {desc}, so a test can "
                        "force it to raise")
        self.assertTrue(result.fired,
                        f"V-2 step '{step}': seams {result.seams} exist but none was called for "
                        "this input, so the step did not run")
        self.assertEqual(result.returncode, 2,
                         f"V-2 step '{step}' raised and the guard did not fail closed:\n" + result.stderr)

    def test_view_builder_raising_fails_closed(self):
        r = edit(HTML, "PLACEHOLDER", '<p class="text-gray-500"></p>', DISK_H_FULL,
                 step="view builder")
        self.forced("view builder", r)
        self.assertIn("[gray-utility:text-gray]", r.stderr)

    def test_whole_file_pass_raising_fails_closed(self):
        r = edit(HTML, "PLACEHOLDER", '<p class="text-gray-500"></p>', DISK_H_FULL,
                 step="whole-file pass")
        self.forced("whole-file pass", r)
        self.assertIn("[gray-utility:text-gray]", r.stderr)

    def test_view_against_disk_comparison_raising_counts_as_introduced(self):
        r = edit(TS, "  templateUrl: './x.component.html',", "  template: '<p></p>',",
                 TS_PLAIN, step="view-against-disk comparison")
        self.forced("view-against-disk comparison", r)
        self.assertIn("[inline-component-template]", r.stderr)

    def test_deduplication_raising_prints_every_finding(self):
        disk = '<div class="h-full">\n  AAA\n  BBB\n</div>\n'
        r = multi(HTML, [("AAA", '<p class="text-gray-500"></p>'),
                         ("BBB", '<p class="bg-gray-100"></p>')], disk, step="de-duplication")
        self.forced("de-duplication", r)
        rules = blocked_rules(r.stderr)
        self.assertIn("gray-utility:text-gray", rules)
        self.assertIn("gray-utility:bg-gray", rules)

    def test_g5_reference_test_raising_treats_the_token_as_a_colour(self):
        r = write_step(HTML, '<span class="x">#ff0000</span>\n', "G-5 reference test")
        self.forced("G-5 reference test", r)
        self.assertIn("[hex-color]", r.stderr)


def write_step(rel: str, content: str, step: str) -> Result:
    return run(rel, "Write", {"content": content}, step=step)


class KnownLimitsDocstringTests(unittest.TestCase):
    def test_docstring_has_a_known_limits_block(self):
        doc = ast.get_docstring(ast.parse(GUARD.read_text(encoding="utf-8"))) or ""
        self.assertIn("Known limits", doc, "the guard's docstring needs a 'Known limits' block")
        block = doc[doc.index("Known limits"):] if "Known limits" in doc else ""
        for token in ("W5", "W6b", "W8", "W11", "G-2", "G-5"):
            self.assertIn(token, block,
                          f"the 'Known limits' block must record the accepted limit {token}")


if __name__ == "__main__":
    unittest.main()
