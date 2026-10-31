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
        plugin = block.find("CLAUDE_PLUGIN_ROOT")
        project = block.find(".claude/hooks/architecture-guard.py")
        self.assertGreaterEqual(plugin, 0, "the lookup tries the plugin root first (CLAUDE_PLUGIN_ROOT)")
        self.assertGreater(project, plugin, "then the project's .claude/hooks/architecture-guard.py")
        self.assertIn("agentic-auto-improve/*/", block, "the lookup also searches the plugin cache")
        self.assertRegex(block, r"\bexit\b", "the lookup halts when neither path exists")
        self.assertRegex(block, r"(?m)^.*\b(echo|printf)\b.*architecture-guard\.py.*$",
                         "the halt message names the guard's paths")
        self.assertNotIn("$HOME", block, "no home-folder path in the block")


class AlreadyResolvedTests(unittest.TestCase):
    """W2: the guard names neither 'ClientApp' nor a '/features/' folder (pinned absence)."""

    def test_no_clientapp_and_no_features_folder_in_the_guard(self):
        text = GUARD.read_text(encoding="utf-8")
        self.assertNotIn("clientapp", text.lower(), "W2: 'ClientApp' must not appear in the guard")
        self.assertNotIn("/features/", text, "W2: '/features/' must not appear in the guard")


if __name__ == "__main__":
    unittest.main()
