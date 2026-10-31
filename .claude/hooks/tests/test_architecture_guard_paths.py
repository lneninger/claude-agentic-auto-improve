"""RED suite for the guard's paths and file recognition (G-1, G-2, G-3, V-2 for G-1 and G-2, W2).

Contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md, sub-task t2
(ledger rows W1 W2 W3 W9, rules G-1 G-2 G-3, V-2).

Every behavioural case launches THIS worktree's ``architecture-guard.py`` in a subprocess, with a
JSON event on stdin and ``CLAUDE_PROJECT_DIR`` pointing at a fresh temp project, and asserts the exit
code and the printed stderr. Nothing is imported from the guard, so absent behaviour shows up as an
assertion failure. The G-3 and W2 cases read the guard's source text (ast); they never import it.

Forced-raise tests (V-2 for G-1 and G-2)
----------------------------------------
A step has to be forceable to raise, so the guard needs a module-level function for it. The tests find
the step by NAME, with a case-insensitive regex over the guard's own module-level functions. The names
the GREEN step must give its seams contain:

    G-1 root walk (finds the app's folder) ... "walk" or "rules_root" or "app_root"
                                               (e.g. walk_up_to_app_root, app_rules_root)
    G-2 checks (is this file Angular?) ....... "recogni" or "decorator"
                                               (e.g. is_recognised_template, sibling_has_decorator)

The names above are matched in ``STEPS`` below. A tiny runner (written into the temp project, so it is
removed with it) loads the guard, replaces every matching function with one that raises, then calls
``main()`` with the same outer catch as the guard's ``__main__`` block. A forced-raise test passes only
when (1) at least one seam was found, (2) at least one seam was called (the step ran), and (3) the guard
still exits 2 (fail closed).

Run:  py -3 .claude\\hooks\\tests\\test_architecture_guard_paths.py
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
SKILL = REPO_ROOT / "skills" / "promote-ui-rule" / "SKILL.md"

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
    "G-1 root walk": (r"walk|rules_root|app_root",
                      "a function whose name contains 'walk', 'rules_root' or 'app_root'"),
    "G-2 checks": (r"recogni|decorator",
                   "a function whose name contains 'recogni' or 'decorator'"),
}


class Result:
    def __init__(self, returncode: int, stderr: str, seams: list[str] | None = None,
                 fired: list[str] | None = None):
        self.returncode = returncode
        self.stderr = stderr
        self.seams = seams
        self.fired = fired


def run(files: dict[str, str | bytes], target: str, tool_name: str, tool_input: dict,
        step: str | None = None) -> Result:
    """Run the guard once. ``files`` pre-creates project files (relative paths); ``target`` is edited."""
    with tempfile.TemporaryDirectory(prefix="archguard_paths_") as tmp:
        project = Path(tmp).resolve()
        for rel, body in files.items():
            p = project / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
        tool_input = {"file_path": str(project / target), **tool_input}
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


def write(files: dict[str, str | bytes], target: str, content: str, step: str | None = None) -> Result:
    return run(files, target, "Write", {"content": content}, step)


def edit(files: dict[str, str | bytes], target: str, old: str, new: str,
         step: str | None = None) -> Result:
    return run(files, target, "Edit", {"old_string": old, "new_string": new}, step)


RULES_FILE = ".claude/hooks/architecture-guard.rules.json"
BANNED_HTML = '<div class="bg-banned">x</div>\n'


def settings(root: str | None) -> dict[str, str]:
    return {} if root is None else {RULES_FILE: json.dumps({"frontend_projects_root": root})}


def app_files(root: str, rules_name: str = ".app-rules.json", with_settings: bool = True) -> dict[str, str]:
    files = {f"{root}/shop/{rules_name}": json.dumps({"extraBannedClasses": ["bg-banned"]})}
    if with_settings:
        files.update(settings(root))
    return files


def assert_forced_raise(tc: unittest.TestCase, r: Result, step: str, expect_exit: int = 2) -> None:
    tc.assertTrue(r.seams, f"V-2: the guard needs a seam for the '{step}' step: {STEPS[step][1]}. "
                           "No module-level function with such a name was found.")
    tc.assertTrue(r.fired, f"V-2: the '{step}' seam(s) {r.seams} were never called, so the step "
                           f"did not run through them (stderr: {r.stderr!r})")
    tc.assertEqual(r.returncode, expect_exit,
                   f"V-2: a raising '{step}' step must fail closed (exit {expect_exit}); "
                   f"stderr: {r.stderr!r}")


# --- G-2 fixtures -----------------------------------------------------------------------------
TS_DECORATED = (
    "@Component({\n"
    "  selector: 'app-root',\n"
    "  templateUrl: './app.html',\n"
    "})\n"
    "export class App {}\n"
)
TS_SPACED = (
    "@Component ({\n"
    "  selector: 'app-root',\n"
    "  templateUrl: './app.html',\n"
    "})\n"
    "export class App {}\n"
)
TS_NO_DECORATOR = "export class App {}\n"
TS_NONE_ENCAPSULATION = (
    "import { Component, ViewEncapsulation } from '@angular/core';\n"
    "@Component({\n"
    "  selector: 'x-y',\n"
    "  templateUrl: './x.html',\n"
    "  encapsulation: ViewEncapsulation.None,\n"
    "})\n"
    "export class X {}\n"
)
TS_DEFAULT_ENCAPSULATION = (
    "@Component({\n"
    "  selector: 'x-y',\n"
    "  templateUrl: './x.html',\n"
    "})\n"
    "export class X {}\n"
)
STYLE_VIOLATION = '<div style="color: red">x</div>\n'
RAW_PROPERTY_CSS = ".card {\n  color: red;\n}\n"
DEAD_HOST_CSS = ":host {\n  display: block;\n}\n"
TS_INLINE_TEMPLATE = (
    "@Component({\n"
    "  selector: 'app-root',\n"
    "  template: '<p></p>',\n"
    "})\n"
    "export class App {}\n"
)


def blocked_rules(stderr: str) -> list[str]:
    return re.findall(r"^\s*\[([^\]]+)\]", stderr, flags=re.MULTILINE)


class AppRulesPathTests(unittest.TestCase):
    """G-1: .app-rules.json is found under the root that detect_app uses, not under 'projects'."""

    def test_control_default_root_projects_blocks_the_banned_class(self):
        r = write(app_files("projects", with_settings=False), "projects/shop/src/x.component.html", BANNED_HTML)
        self.assertEqual(r.returncode, 2, "control: the default root 'projects' must keep working\n" + r.stderr)
        self.assertIn("app-banned-class:bg-banned", r.stderr)

    def test_control_rules_file_renamed_away_allows_the_same_write(self):
        files = app_files("apps", rules_name=".app-rules.json.off")
        r = write(files, "apps/shop/src/x.component.html", BANNED_HTML)
        self.assertEqual(r.returncode, 0,
                         "control: with the rules file renamed away nothing bans bg-banned\n" + r.stderr)

    def test_root_apps_finds_the_rules_file(self):
        r = write(app_files("apps"), "apps/shop/src/x.component.html", BANNED_HTML)
        self.assertEqual(r.returncode, 2,
                         "G-1: with frontend_projects_root='apps' the rules file apps/shop/.app-rules.json "
                         "must be found; the guard still looks only under a folder named 'projects'.\n"
                         + r.stderr)
        self.assertIn("app-banned-class:bg-banned", r.stderr)

    def test_two_segment_root_finds_the_rules_file(self):
        r = write(app_files("frontend/apps"), "frontend/apps/shop/src/x.component.html", BANNED_HTML)
        self.assertEqual(r.returncode, 2,
                         "G-1: a two-segment root 'frontend/apps' must find "
                         "frontend/apps/shop/.app-rules.json.\n" + r.stderr)
        self.assertIn("app-banned-class:bg-banned", r.stderr)

    def test_root_apps_does_not_treat_a_projects_folder_as_an_application_root(self):
        files = app_files("projects", with_settings=False)
        files.update(settings("apps"))
        r = write(files, "projects/shop/src/x.component.html", BANNED_HTML)
        self.assertEqual(r.returncode, 0,
                         "G-1: the root is the configured one; 'projects/shop' is no application when "
                         "the root is 'apps'\n" + r.stderr)

    def test_forced_raise_in_the_root_walk_falls_back_to_the_default_root(self):
        r = write(app_files("projects", with_settings=False), "projects/shop/src/x.component.html",
                  BANNED_HTML, step="G-1 root walk")
        assert_forced_raise(self, r, "G-1 root walk")
        self.assertIn("app-banned-class:bg-banned", r.stderr,
                      "V-2: the walk raised, so it falls back to the default root 'projects' and the "
                      "banned class is still found")


class FileRecognitionTests(unittest.TestCase):
    """G-2: Angular 20 suffix-less names, recognised by the sibling .ts that carries the decorator."""

    def test_control_component_html_is_still_scanned(self):
        r = write({}, "src/x.component.html", STYLE_VIOLATION)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("inline-style", r.stderr)

    def test_suffixless_html_beside_decorated_ts_is_a_template(self):
        files = {"src/app/app.ts": TS_DECORATED}
        r = write(files, "src/app/app.html", STYLE_VIOLATION)
        self.assertEqual(r.returncode, 2,
                         "G-2: app.html beside an app.ts that carries @Component is a template and its "
                         "inline style must block.\n" + r.stderr)
        self.assertIn("inline-style", r.stderr)

    def test_sibling_written_with_a_space_before_the_brace_is_recognised(self):
        files = {"src/app/app.ts": TS_SPACED}
        r = write(files, "src/app/app.html", STYLE_VIOLATION)
        self.assertEqual(r.returncode, 2,
                         "G-2: the evidence is the pattern @Component\\s*\\(, so '@Component ({' counts.\n"
                         + r.stderr)

    def test_edit_of_a_suffixless_html_is_a_template(self):
        files = {"src/app/app.ts": TS_DECORATED, "src/app/app.html": "<p>old</p>\n"}
        r = edit(files, "src/app/app.html", "<p>old</p>", '<p class="text-gray-500">new</p>')
        self.assertEqual(r.returncode, 2, "G-2: an Edit of app.html is judged like a template\n" + r.stderr)
        self.assertIn("gray-utility", r.stderr)

    def test_suffixless_ts_with_the_decorator_is_component_code(self):
        content = TS_INLINE_TEMPLATE
        r = write({}, "src/app/app.ts", content)
        self.assertEqual(r.returncode, 2,
                         "G-2: app.ts whose text carries @Component is component code; an inline "
                         "template: must block (inline-component-template).\n" + r.stderr)
        self.assertIn("inline-component-template", r.stderr)

    def test_edit_that_adds_template_to_a_suffixless_ts_judges_the_post_edit_view(self):
        files = {"src/app/app.ts": TS_DECORATED}
        r = edit(files, "src/app/app.ts", "templateUrl: './app.html',", "template: '<p></p>',")
        self.assertEqual(r.returncode, 2,
                         "G-2: the post-edit view of app.ts carries the decorator, so the edit is "
                         "judged as component code.\n" + r.stderr)

    def test_gray_utility_in_a_suffixless_component_ts_blocks(self):
        content = TS_DECORATED + "export const CLS = 'text-gray-500';\n"
        r = write({}, "src/app/app.ts", content)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("gray-utility", r.stderr)

    def test_css_beside_decorated_ts_is_a_component_stylesheet(self):
        files = {"src/x/x.ts": TS_DEFAULT_ENCAPSULATION}
        r = write(files, "src/x/x.css", RAW_PROPERTY_CSS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("scss-warn:raw-property", r.stderr,
                      "G-2: x.css beside an x.ts that carries @Component is a component stylesheet and "
                      "its raw property rule is warned.")

    def test_scss_beside_decorated_ts_is_a_component_stylesheet(self):
        files = {"src/x/x.ts": TS_DEFAULT_ENCAPSULATION}
        r = write(files, "src/x/x.scss", RAW_PROPERTY_CSS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("scss-warn:raw-property", r.stderr,
                      "G-2: x.scss beside an x.ts that carries @Component is a component stylesheet.")

    def test_css_stem_is_derived_by_removing_the_actual_suffix(self):
        files = {"src/x/x.ts": TS_NONE_ENCAPSULATION}
        r = write(files, "src/x/x.css", DEAD_HOST_CSS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("scss-warn:dead-host", r.stderr,
                      "G-2: classify_sibling_component must cut '.css' (not len('.scss')) to find x.ts, "
                      "read ViewEncapsulation.None and report the dead :host.")

    def test_scss_stem_reads_the_plain_ts_when_there_is_no_component_ts(self):
        files = {"src/x/x.ts": TS_NONE_ENCAPSULATION}
        r = write(files, "src/x/x.scss", DEAD_HOST_CSS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("scss-warn:dead-host", r.stderr,
                      "G-2: x.scss falls back to <stem>.ts when <stem>.component.ts is absent.")

    def test_component_ts_is_read_before_the_plain_ts(self):
        files = {"src/x/x.component.ts": TS_NONE_ENCAPSULATION, "src/x/x.ts": TS_DEFAULT_ENCAPSULATION}
        r = write(files, "src/x/x.component.scss", DEAD_HOST_CSS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("scss-warn:dead-host", r.stderr,
                      "control: x.component.scss keeps reading x.component.ts first")

    # --- negatives ------------------------------------------------------------------------

    def test_index_html_is_not_a_template(self):
        r = write({"src/main.ts": TS_NO_DECORATOR}, "src/index.html", STYLE_VIOLATION)
        self.assertEqual(r.returncode, 0, "G-2: index.html has no decorated sibling\n" + r.stderr)

    def test_main_ts_without_the_decorator_is_not_component_code(self):
        content = "bootstrapApplication(App);\nexport const CLS = 'text-gray-500';\n"
        r = write({}, "src/main.ts", content)
        self.assertEqual(r.returncode, 0, "G-2: main.ts carries no @Component\n" + r.stderr)

    def test_spec_ts_is_never_component_code(self):
        r = write({}, "src/app/x.spec.ts", TS_INLINE_TEMPLATE)
        self.assertEqual(r.returncode, 0, "G-2: .spec.ts is never scanned, whatever its text\n" + r.stderr)

    def test_d_ts_is_never_component_code(self):
        r = write({}, "src/app/x.d.ts", TS_INLINE_TEMPLATE)
        self.assertEqual(r.returncode, 0, "G-2: .d.ts is never scanned, whatever its text\n" + r.stderr)

    def test_html_beside_a_ts_with_no_decorator_is_not_a_template(self):
        files = {"src/app/app.ts": TS_NO_DECORATOR}
        r = write(files, "src/app/app.html", STYLE_VIOLATION)
        self.assertEqual(r.returncode, 0,
                         "G-2: app.html beside an app.ts with no decorator is not Angular evidence\n"
                         + r.stderr)

    def test_css_beside_a_ts_with_no_decorator_is_not_a_stylesheet(self):
        files = {"src/x/x.ts": TS_NO_DECORATOR}
        r = write(files, "src/x/x.css", RAW_PROPERTY_CSS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("scss-warn", r.stderr, "G-2: no decorator, so the stylesheet is not scanned")

    def test_html_with_no_sibling_ts_is_not_a_template(self):
        r = write({}, "src/app/lonely.html", STYLE_VIOLATION)
        self.assertEqual(r.returncode, 0, r.stderr)

    # --- V-2 for G-2 ----------------------------------------------------------------------

    def test_forced_raise_in_the_recognition_check_counts_the_html_as_recognised(self):
        files = {"src/app/app.ts": TS_DECORATED}
        r = write(files, "src/app/app.html", STYLE_VIOLATION, step="G-2 checks")
        assert_forced_raise(self, r, "G-2 checks")
        self.assertIn("inline-style", r.stderr)

    def test_forced_raise_counts_an_undecorated_sibling_as_recognised(self):
        files = {"src/app/app.ts": TS_NO_DECORATOR}
        r = write(files, "src/app/app.html", STYLE_VIOLATION, step="G-2 checks")
        assert_forced_raise(self, r, "G-2 checks")
        self.assertIn("inline-style", r.stderr,
                      "V-2: when the check raises, the file counts as recognised (the stricter outcome)")

    def test_forced_raise_in_the_recognition_check_counts_the_ts_as_recognised(self):
        r = write({}, "src/app/app.ts", TS_INLINE_TEMPLATE, step="G-2 checks")
        assert_forced_raise(self, r, "G-2 checks")
        self.assertIn("inline-component-template", r.stderr)


def _guard_tree() -> ast.Module:
    return ast.parse(GUARD.read_text(encoding="utf-8"))


def _docstring_nodes(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


class HomeFolderTests(unittest.TestCase):
    """G-3: no code path in the guard builds a home-folder path."""

    def test_no_path_home_call_in_the_guard(self):
        calls = [n.lineno for n in ast.walk(_guard_tree())
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr in ("home", "expanduser")]
        self.assertEqual(calls, [],
                         f"G-3: the guard must not call Path.home() or expanduser(); found at lines {calls}")

    def test_no_HOME_name_in_the_guard_code(self):
        hits = []
        for n in ast.walk(_guard_tree()):
            if isinstance(n, ast.Name) and n.id == "HOME":
                hits.append(n.lineno)
            elif isinstance(n, ast.Attribute) and n.attr == "HOME":
                hits.append(n.lineno)
            elif isinstance(n, ast.Constant) and n.value in ("HOME", "USERPROFILE"):
                hits.append(n.lineno)
        self.assertEqual(hits, [], f"G-3: no HOME name may appear in the guard's code; lines {hits}")

    def test_home_claude_appears_in_no_string_outside_the_one_docstring_sentence(self):
        tree = _guard_tree()
        docs = _docstring_nodes(tree)
        bad = [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and id(n) not in docs and "~/.claude" in n.value]
        self.assertEqual(bad, [], f"G-3: '~/.claude' appears in a non-docstring string at lines {bad}")

    def test_the_docstrings_name_the_home_folder_at_most_once_and_only_to_describe_hook_file(self):
        tree = _guard_tree()
        docs = _docstring_nodes(tree)
        lines: list[str] = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and id(n) in docs:
                lines.extend(ln for ln in n.value.splitlines() if "~/.claude" in ln)
        self.assertLessEqual(len(lines), 1, f"G-3: at most one docstring sentence may name ~/.claude: {lines}")
        for ln in lines:
            self.assertIn("hook_file", ln,
                          "G-3: the one allowed mention describes hook_file's lookup order: " + ln)

    def test_the_fallback_without_project_paths_is_the_hooks_own_folder(self):
        text = GUARD.read_text(encoding="utf-8")
        self.assertNotRegex(text, r'(?m)^\s*else\s+HOME\b',
                            "G-3: the fallback when _project_paths is missing must not build a home path")


class PromoteUiRuleSkillTests(unittest.TestCase):
    """G-3 / W9: promote-ui-rule names the project copy and runs the guard through a lookup block."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.lines = cls.text.splitlines()

    def test_no_home_claude_pointer_remains(self):
        offenders = [i + 1 for i, ln in enumerate(self.lines)
                     if "~/.claude" in ln or "$HOME/.claude" in ln or "${HOME}/.claude" in ln]
        self.assertEqual(offenders, [], f"W9: the skill still points at the home .claude folder: lines {offenders}")

    def test_step_three_names_the_project_copy_of_the_rules_file(self):
        line = next((ln for ln in self.lines if "append the new rule object" in ln), "")
        self.assertIn(".claude/hooks/architecture-guard.rules.json", line)
        self.assertNotIn("~", line, "W9 (:58): the project copy, not the home folder")

    def _lookup_block(self) -> str:
        blocks, cur, inside = [], [], False
        for ln in self.lines:
            if ln.lstrip().startswith("```"):
                if inside:
                    blocks.append("\n".join(cur))
                    cur = []
                inside = not inside
            elif inside:
                cur.append(ln)
        return next((b for b in blocks if "architecture-guard.py" in b), "")

    def test_step_four_runs_the_guard_through_a_lookup_block(self):
        block = self._lookup_block()
        self.assertTrue(block, "W9 (:72): no fenced block runs architecture-guard.py")
        # (a) the plugin root and its guard path come first
        plugin = block.find("CLAUDE_PLUGIN_ROOT")
        self.assertGreaterEqual(plugin, 0, "(a) the lookup tries $CLAUDE_PLUGIN_ROOT first")
        plugin_guard = re.search(r"CLAUDE_PLUGIN_ROOT[^\n]*\.claude/hooks/architecture-guard\.py", block)
        self.assertIsNotNone(plugin_guard, "(a) ... and the guard path under it")
        # (b) then the project's own copy
        project = block.find(".claude/hooks/architecture-guard.py", plugin_guard.end() if plugin_guard else 0)
        self.assertGreater(project, plugin, "(b) then the project's .claude/hooks/architecture-guard.py")
        # (c) halt, with a message naming both paths, when neither exists
        self.assertRegex(block, r"\bexit\b", "(c) the lookup halts when neither path exists")
        halt = re.search(r"(?m)^.*\b(echo|printf)\b.*$", block[project:]) or re.search(
            r"(?m)^.*\b(echo|printf)\b.*$", block)
        self.assertIsNotNone(halt, "(c) a halt message is printed")
        message = " ".join(m.group(0) for m in re.finditer(r"(?m)^.*\b(?:echo|printf)\b.*$", block))
        self.assertRegex(message, r"architecture-guard\.py",
                         "(c) the halt message names the guard path")
        self.assertRegex(message, r"CLAUDE_PLUGIN_ROOT|PLUGIN|plugin",
                         "(c) the halt message names the plugin path")
        self.assertRegex(message, r"\.claude/hooks|PROJECT|project",
                         "(c) the halt message names the project path")
        # (d) then the guard runs with py -3
        self.assertRegex(block, r'(?m)^\s*.*\bpy\s+-3\s+"?\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"?',
                         "(d) the guard is run with py -3 on the found path")
        # (e) no home-folder path
        self.assertNotIn("$HOME", block, "(e) no home-folder path in the block")
        self.assertNotIn("~/.claude", block, "(e) no home-folder path in the block")
        # The contract has no plugin-cache search. This pattern is also what test_skill_script_lookup.py
        # scans for: a block holding it must run a .claude/scripts/<x>.py script, which a hook lookup cannot.
        self.assertNotIn("agentic-auto-improve/*/", block,
                         "no plugin-cache search: it would make test_skill_script_lookup.py scan this block")


class AlreadyResolvedTests(unittest.TestCase):
    """W2: the guard names neither 'ClientApp' nor a '/features/' folder (pinned absence)."""

    def test_no_clientapp_and_no_features_folder_in_the_guard(self):
        text = GUARD.read_text(encoding="utf-8")
        self.assertNotIn("clientapp", text.lower(), "W2: 'ClientApp' must not appear in the guard")
        self.assertNotIn("/features/", text, "W2: '/features/' must not appear in the guard")


# ---------------------------------------------------------------------------------------------
# Fix round (review WARN-3 to WARN-7, N1, N2)
# ---------------------------------------------------------------------------------------------

#: Faults injected INSIDE the G-1 walk (WARN-4). Technique: the runner patches ``pathlib.Path.exists``
#: so that the call on a ``.app-rules.json`` raises PermissionError (what Python 3.12 does for an
#: unreadable folder). argv: guard, fired_file, times (0 = every call raises; N = only the first N).
RUNNER_FS_SOURCE = '''\
import importlib.util
import pathlib
import sys

guard, fired_file, times = sys.argv[1], sys.argv[2], int(sys.argv[3])
spec = importlib.util.spec_from_file_location("architecture_guard_under_test", guard)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
open(fired_file, "w", encoding="utf-8").write("")

orig_exists = pathlib.Path.exists
state = {"n": 0}


def exists(self, *args, **kwargs):
    if self.name == ".app-rules.json" and (times == 0 or state["n"] < times):
        state["n"] += 1
        with open(fired_file, "a", encoding="utf-8") as fh:
            fh.write("exists\\n")
        raise PermissionError(13, "forced V-2 fault in the walk", str(self))
    return orig_exists(self, *args, **kwargs)


pathlib.Path.exists = exists
try:
    mod.main()
except SystemExit:
    raise
except Exception as e:  # same outer catch as the guard's __main__ block
    mod.log("internal error (failing open): %s" % e)
    sys.exit(0)
'''

#: Read spy (WARN-3). Technique: the runner wraps ``Path.read_bytes`` and ``Path.read_text`` and writes
#: one line ``read:<path>`` per call, so a test counts how often the guard read a given file.
RUNNER_SPY_SOURCE = '''\
import importlib.util
import pathlib
import sys

guard, fired_file = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("architecture_guard_under_test", guard)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
open(fired_file, "w", encoding="utf-8").write("")


def spy(orig):
    def wrapper(self, *args, **kwargs):
        with open(fired_file, "a", encoding="utf-8") as fh:
            fh.write("read:" + str(self) + "\\n")
        return orig(self, *args, **kwargs)
    return wrapper


pathlib.Path.read_bytes = spy(pathlib.Path.read_bytes)
pathlib.Path.read_text = spy(pathlib.Path.read_text)
try:
    mod.main()
except SystemExit:
    raise
except Exception as e:
    mod.log("internal error (failing open): %s" % e)
    sys.exit(0)
'''


def run_runner(files: dict[str, str | bytes], target: str, tool_name: str, tool_input: dict,
               runner_source: str, extra_args: list[str]) -> Result:
    """Like ``run`` but through a custom runner; ``fired`` holds the lines the runner wrote."""
    with tempfile.TemporaryDirectory(prefix="archguard_paths_") as tmp:
        project = Path(tmp).resolve()
        for rel, body in files.items():
            p = project / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
        payload = {"tool_name": tool_name, "tool_input": {"file_path": str(project / target), **tool_input}}
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_ARCH_GUARD"}
        env["CLAUDE_PROJECT_DIR"] = str(project)
        runner = project / "_runner.py"
        runner.write_text(runner_source, encoding="utf-8")
        fired_file = project / "_fired.txt"
        proc = subprocess.run(
            [sys.executable, "-I", str(runner), str(GUARD), str(fired_file), *extra_args],
            input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=str(REPO_ROOT), env=env, timeout=60,
        )
        fired = None
        if fired_file.exists():
            fired = [s for s in fired_file.read_text(encoding="utf-8").splitlines() if s]
        return Result(proc.returncode, proc.stderr, None, fired)


STYLE_AND_BANNED_HTML = '<div class="bg-banned" style="color: red">x</div>\n'


class WalkFailClosedTests(unittest.TestCase):
    """WARN-4: V-2 covers the walk's own filesystem calls, not only the root lookup."""

    def test_a_walk_that_always_raises_returns_no_rules_and_the_other_rules_still_block(self):
        r = run_runner(app_files("projects", with_settings=False), "projects/shop/src/x.component.html",
                       "Write", {"content": STYLE_AND_BANNED_HTML}, RUNNER_FS_SOURCE, ["0"])
        self.assertTrue(r.fired, "the fault was never injected: the walk never asked whether .app-rules.json exists")
        self.assertEqual(r.returncode, 2,
                         "WARN-4: Path.exists raising PermissionError inside the walk must not reach the "
                         "outer catch (exit 0); the walk returns no rules and inline-style still blocks.\n"
                         + r.stderr)
        self.assertIn("inline-style", r.stderr)
        self.assertNotIn("app-banned-class", r.stderr, "the walk failed, so no app rules were read")

    def test_a_walk_that_raises_once_is_retried_with_the_default_root(self):
        r = run_runner(app_files("projects", with_settings=False), "projects/shop/src/x.component.html",
                       "Write", {"content": STYLE_AND_BANNED_HTML}, RUNNER_FS_SOURCE, ["1"])
        self.assertEqual(r.fired, ["exists"], "exactly the first existence check must have been faulted")
        self.assertEqual(r.returncode, 2,
                         "WARN-4: the first walk raised; the guard must not exit 0 through the outer catch.\n"
                         + r.stderr)
        self.assertIn("app-banned-class:bg-banned", r.stderr,
                      "WARN-4: after the raise the walk is retried with the default root 'projects', "
                      "which finds the rules file")

    def test_a_walk_that_raises_under_a_configured_root_still_blocks_other_rules(self):
        r = run_runner(app_files("apps"), "apps/shop/src/x.component.html",
                       "Write", {"content": STYLE_AND_BANNED_HTML}, RUNNER_FS_SOURCE, ["0"])
        self.assertTrue(r.fired)
        self.assertEqual(r.returncode, 2, "WARN-4: no path reaches the outer catch\n" + r.stderr)
        self.assertIn("inline-style", r.stderr)


class RootNormalisationTests(unittest.TestCase):
    """WARN-5: the configured root is normalised, so these all behave like 'apps/web'."""

    def _blocked_with_root(self, configured: str):
        files = {"apps/web/shop/.app-rules.json": json.dumps({"extraBannedClasses": ["bg-banned"]}),
                 RULES_FILE: json.dumps({"frontend_projects_root": configured})}
        return write(files, "apps/web/shop/src/x.component.html", BANNED_HTML)

    def test_control_the_plain_two_segment_root(self):
        r = self._blocked_with_root("apps/web")
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_control_surrounding_slashes_and_upper_case_keep_working(self):
        r = self._blocked_with_root("/Apps/Web/")
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_backslash_separator(self):
        r = self._blocked_with_root("apps\\web")
        self.assertEqual(r.returncode, 2,
                         "WARN-5: 'apps\\\\web' must behave like 'apps/web'\n" + r.stderr)
        self.assertIn("app-banned-class:bg-banned", r.stderr)

    def test_padding_around_the_value(self):
        r = self._blocked_with_root(" apps/web ")
        self.assertEqual(r.returncode, 2, "WARN-5: ' apps/web ' must behave like 'apps/web'\n" + r.stderr)
        self.assertIn("app-banned-class:bg-banned", r.stderr)

    def test_doubled_slash(self):
        r = self._blocked_with_root("apps//web")
        self.assertEqual(r.returncode, 2, "WARN-5: 'apps//web' must behave like 'apps/web'\n" + r.stderr)
        self.assertIn("app-banned-class:bg-banned", r.stderr)


def reads_of(r: Result, name: str) -> int:
    return sum(1 for line in (r.fired or []) if line.startswith("read:") and Path(line[5:]).name == name)


def multi_edit(files, target, edits, source=RUNNER_SPY_SOURCE):
    return run_runner(files, target, "MultiEdit",
                      {"edits": [{"old_string": o, "new_string": n} for o, n in edits]}, source, [])


class CostTests(unittest.TestCase):
    """WARN-3: decide by file NAME first, and read each file once per call.

    Technique: a read spy (RUNNER_SPY_SOURCE) counts the guard's Path.read_bytes / read_text calls per
    file name. An unrelated non-component .ts is not pinned: its decision needs the text.
    """

    def test_editing_a_spec_ts_does_not_read_the_file(self):
        r = run_runner({"src/x.spec.ts": "const a = 1;\n"}, "src/x.spec.ts", "Edit",
                       {"old_string": "const a = 1;", "new_string": "const a = 2;"}, RUNNER_SPY_SOURCE, [])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(reads_of(r, "x.spec.ts"), 0,
                         "WARN-3: .spec.ts is decided by its name; no post-edit view may be built for it")

    def test_editing_a_d_ts_does_not_read_the_file(self):
        r = run_runner({"src/x.d.ts": "declare const a: 1;\n"}, "src/x.d.ts", "Edit",
                       {"old_string": "declare const a: 1;", "new_string": "declare const a: 2;"},
                       RUNNER_SPY_SOURCE, [])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(reads_of(r, "x.d.ts"), 0,
                         "WARN-3: .d.ts is decided by its name; no post-edit view may be built for it")

    def test_a_three_edit_multiedit_reads_a_component_ts_once(self):
        disk = "// A1\n// B1\n// C1\n" + TS_DECORATED
        r = multi_edit({"src/x.component.ts": disk}, "src/x.component.ts",
                       [("// A1", "// A2"), ("// B1", "// B2"), ("// C1", "// C2")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(reads_of(r, "x.component.ts"), 1,
                         "WARN-3: the post-edit view is built once per file per call, not once per edit "
                         "(and not again in the whole-file pass); reads: %s" % r.fired)

    def test_control_a_three_edit_multiedit_reads_a_component_html_once(self):
        disk = "<!-- A1 -->\n<!-- B1 -->\n<!-- C1 -->\n<p>x</p>\n"
        r = multi_edit({"src/x.component.html": disk}, "src/x.component.html",
                       [("<!-- A1 -->", "<!-- A2 -->"), ("<!-- B1 -->", "<!-- B2 -->"),
                        ("<!-- C1 -->", "<!-- C2 -->")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(reads_of(r, "x.component.html"), 1, "reads: %s" % r.fired)

    def test_a_multiedit_of_a_suffixless_html_reads_its_sibling_ts_once(self):
        disk = "<!-- A1 -->\n<!-- B1 -->\n<p>x</p>\n"
        r = multi_edit({"src/app/app.html": disk, "src/app/app.ts": TS_DECORATED}, "src/app/app.html",
                       [("<!-- A1 -->", "<!-- A2 -->"), ("<!-- B1 -->", "<!-- B2 -->")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(reads_of(r, "app.ts"), 1,
                         "WARN-3: the sibling's decorator check is cached for the call; reads: %s" % r.fired)
        self.assertEqual(reads_of(r, "app.html"), 1, "the view of app.html is built once; reads: %s" % r.fired)


class FixRoundSkillAndDocumentTests(unittest.TestCase):
    TAILWIND = REPO_ROOT / ".claude" / "addons" / "angular-tailwind" / "documents" / "TAILWINDCSS_RULES.md"

    def test_step_four_runs_the_guard_with_claude_project_dir_set(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertRegex(text, r'(?m)^[^\n]*CLAUDE_PROJECT_DIR="\$\{CLAUDE_PROJECT_DIR:-[^}]+\}"[^\n]*\bpy\s+-3\b',
                         "WARN-6: the guard invocation line must set CLAUDE_PROJECT_DIR, defaulting to the "
                         "current folder, so the project's rules file is the one the guard reads")

    def test_step_four_tests_the_project_guard_under_claude_project_dir(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn('"${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/architecture-guard.py"', text,
                      "WARN-6: the project lookup tests ${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/architecture-guard.py")

    def test_the_inline_style_rule_names_the_same_name_sibling(self):
        line = next((ln for ln in self.TAILWIND.read_text(encoding="utf-8").splitlines()
                     if ln.startswith("- Enforced by: guard blocks (`inline-style`)")), "")
        self.assertTrue(line, "the 'Enforced by' line of the inline-style rule was not found")
        self.assertRegex(line, r"(?i)same name|same-name|<name>\.ts|<stem>\.ts",
                         "WARN-7: the .html must be named as beside the .ts WITH THE SAME NAME, not 'a .ts file'")
        self.assertNotIn("beside a `.ts` file", line)


class DocstringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = ast.get_docstring(_guard_tree()) or ""

    def test_the_hook_file_order_includes_the_working_folder(self):
        start = self.doc.find("hook_file")
        self.assertGreaterEqual(start, 0, "the docstring describes hook_file's order")
        segment = self.doc[start:].split("\n\n", 1)[0]
        self.assertRegex(segment, r"(?i)working folder|working directory|current folder|current directory|cwd",
                         "N1: hook_file's order is project copy, template beside the hook, the working "
                         "folder's .claude/hooks, then the home folder")

    def test_the_hook_file_sentence_covers_the_rules_file_too(self):
        start = self.doc.find("Exception list")
        self.assertGreaterEqual(start, 0, "the docstring has an 'Exception list' paragraph")
        segment = self.doc[start:].split("\n\n", 1)[0]
        self.assertIn("rules", segment, "N1: the same order applies to architecture-guard.rules.json")

    def test_the_g2_known_limit_names_the_exclusions_and_the_written_text_fallback(self):
        start = self.doc.find("G-2 ")
        end = self.doc.find("G-5", start)
        self.assertGreaterEqual(start, 0, "the G-2 limit is in the docstring")
        block = self.doc[start:end]
        self.assertIn(".spec.ts", block, "N2: .spec.ts is never scanned")
        self.assertIn(".d.ts", block, "N2: .d.ts is never scanned")
        self.assertRegex(block, r"(?i)written (text|content)|text written|new text",
                         "N2: with no post-edit view the written text is used")


if __name__ == "__main__":
    unittest.main()
