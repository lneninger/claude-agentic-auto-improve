"""Tests for the Rule ID, document footer, C1(b) and sticky behaviour of architecture-guard.py.

Contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md, sub-task 6
(Guard rule map, Guard violation, C1, C4, Q11, Q13).

Each case launches THIS worktree's ``architecture-guard.py`` with a Write payload and
``CLAUDE_PROJECT_DIR`` pointing at a fresh temp project, then asserts the printed stderr.

Run:  py -3 .claude\\hooks\\tests\\test_architecture_guard_messages.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
GUARD = HOOKS_DIR / "architecture-guard.py"
REPO_ROOT = HOOKS_DIR.parent.parent
DOCS_DIR = REPO_ROOT / ".claude" / "addons" / "angular-tailwind" / "documents"

NOT_INSTALLED = (
    "Rule text not installed in this project: the angular-tailwind add-on installs it "
    "(/auto-improve-angular-tailwind-install)."
)


class Result:
    def __init__(self, returncode: int, stderr: str, project: Path):
        self.returncode = returncode
        self.stderr = stderr
        self.project = project


def doc_path(project: Path, name: str) -> Path:
    return project / ".claude" / "references" / "angular-tailwind" / name


def run(rel: str, content: str, installed: tuple[str, ...] = ()) -> Result:
    with tempfile.TemporaryDirectory(prefix="archguard_msg_") as tmp:
        project = Path(tmp).resolve()
        for name in installed:
            p = doc_path(project, name)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# doc\n", encoding="utf-8")
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": content}}
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_ARCH_GUARD"}
        env["CLAUDE_PROJECT_DIR"] = str(project)
        proc = subprocess.run(
            [sys.executable, str(GUARD)], input=json.dumps(payload), capture_output=True,
            text=True, encoding="utf-8", errors="replace", cwd=str(REPO_ROOT), env=env, timeout=60,
        )
        return Result(proc.returncode, proc.stderr, project)


def html(content: str, installed: tuple[str, ...] = ()) -> Result:
    return run("src/x.component.html", content, installed)


class RuleIdLineTests(unittest.TestCase):
    def test_inline_style_names_t001(self):
        r = html('<div style="color: red"></div>\n')
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("[inline-style] T-001 line 1", r.stderr)

    def test_hex_color_names_t004(self):
        r = html('<span class="x">#ff0000</span>\n')
        self.assertIn("[hex-color] T-004 line 1", r.stderr)

    def test_scroll_edge_names_t012(self):
        r = html('<div class="overflow-y-auto"></div>\n')
        self.assertIn("[scroll-edge] T-012 line 1", r.stderr)

    def test_gray_prefix_names_t003(self):
        r = html('<p class="text-gray-500"></p>\n')
        self.assertIn("[gray-utility:text-gray] T-003 line 1", r.stderr)

    def test_inline_component_template_and_styles_name_a003(self):
        ts = "@Component({\n  selector: 'x',\n  template: '<p></p>',\n  styles: ['p{}'],\n})\nexport class X {}\n"
        r = run("src/x.component.ts", ts)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("[inline-component-template] A-003 line 3", r.stderr)
        self.assertIn("[inline-component-styles] A-003 line 4", r.stderr)

    def test_app_banned_class_names_t022(self):
        with tempfile.TemporaryDirectory(prefix="archguard_app_") as tmp:
            project = Path(tmp).resolve()
            (project / ".claude" / "hooks").mkdir(parents=True)
            (project / ".claude" / "hooks" / "architecture-guard.rules.json").write_text(
                json.dumps({"frontend_projects_root": "projects"}), encoding="utf-8")
            app = project / "projects" / "demo"
            app.mkdir(parents=True)
            (app / ".app-rules.json").write_text(
                json.dumps({"extraBannedClasses": ["bg-white"]}), encoding="utf-8")
            target = app / "src" / "x.component.html"
            target.parent.mkdir(parents=True)
            payload = {"tool_name": "Write",
                       "tool_input": {"file_path": str(target), "content": '<div class="bg-white"></div>\n'}}
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project))
            proc = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                                  capture_output=True, text=True, encoding="utf-8",
                                  cwd=str(REPO_ROOT), env=env, timeout=60)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("[app-banned-class:bg-white] T-022 line 1", proc.stderr)

    def test_external_rule_uses_its_own_id_and_no_document(self):
        with tempfile.TemporaryDirectory(prefix="archguard_ext_") as tmp:
            project = Path(tmp).resolve()
            (project / ".claude" / "hooks").mkdir(parents=True)
            (project / ".claude" / "hooks" / "architecture-guard.rules.json").write_text(
                json.dumps({"rules": [{"id": "no-foo", "regex": "foo", "applies_to": "html",
                                       "suggestion": "no foo"}]}), encoding="utf-8")
            target = project / "src" / "x.component.html"
            target.parent.mkdir(parents=True)
            payload = {"tool_name": "Write",
                       "tool_input": {"file_path": str(target), "content": "<p>foo</p>\n"}}
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project))
            proc = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                                  capture_output=True, text=True, encoding="utf-8",
                                  cwd=str(REPO_ROOT), env=env, timeout=60)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("[external:no-foo] no-foo line 1", proc.stderr)
            self.assertNotIn("Rule text", proc.stderr)

    def test_scss_warnings_name_ids(self):
        scss = ".a {\n  padding: 0;\n}\n"
        r = run("src/x.component.scss", scss)
        self.assertEqual(r.returncode, 0)
        self.assertIn("[scss-warn:raw-property] T-010", r.stderr)
        ts = ("import { Component, ViewEncapsulation } from '@angular/core';\n"
              "@Component({\n  selector: 'my-w',\n  encapsulation: ViewEncapsulation.None\n})\nexport class X {}\n")
        with tempfile.TemporaryDirectory(prefix="archguard_dh_") as tmp:
            project = Path(tmp).resolve()
            (project / "x.component.ts").write_text(ts, encoding="utf-8")
            target = project / "x.component.scss"
            payload = {"tool_name": "Write",
                       "tool_input": {"file_path": str(target), "content": ":host {\n}\n"}}
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project))
            proc = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                                  capture_output=True, text=True, encoding="utf-8",
                                  cwd=str(REPO_ROOT), env=env, timeout=60)
            self.assertIn("[scss-warn:dead-host] T-011", proc.stderr)


class FooterTests(unittest.TestCase):
    def test_footer_names_document_when_installed(self):
        r = html('<div style="color: red"></div>\n', installed=("TAILWINDCSS_RULES.md",))
        expected = "Rule text: " + str(doc_path(r.project, "TAILWINDCSS_RULES.md"))
        self.assertIn(expected, r.stderr)
        self.assertNotIn("not installed", r.stderr)

    def test_footer_degrades_when_absent(self):
        r = html('<div style="color: red"></div>\n')
        self.assertIn(NOT_INSTALLED, r.stderr)
        self.assertNotIn("Rule text: ", r.stderr)
        self.assertNotIn("TAILWINDCSS_RULES.md", r.stderr)

    def test_a003_points_at_angular_code_rules(self):
        ts = "@Component({\n  template: '<p></p>',\n})\nexport class X {}\n"
        r = run("src/x.component.ts", ts, installed=("ANGULAR_CODE_RULES.md",))
        self.assertIn("Rule text: " + str(doc_path(r.project, "ANGULAR_CODE_RULES.md")), r.stderr)
        r = run("src/x.component.ts", ts, installed=("TAILWINDCSS_RULES.md",))
        self.assertIn(NOT_INSTALLED, r.stderr)

    def test_scss_warning_footer_both_states(self):
        scss = ".a {\n  padding: 0;\n}\n"
        r = run("src/x.component.scss", scss, installed=("TAILWINDCSS_RULES.md",))
        self.assertIn("Rule text: " + str(doc_path(r.project, "TAILWINDCSS_RULES.md")), r.stderr)
        r = run("src/x.component.scss", scss)
        self.assertIn(NOT_INSTALLED, r.stderr)

    def test_unknown_project_root_counts_as_not_installed(self):
        payload = {"tool_name": "Write", "tool_input": {
            "file_path": str(Path(tempfile.gettempdir()) / "zz" / "x.component.html"),
            "content": '<div style="color: red"></div>\n'}}
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        proc = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                              capture_output=True, text=True, encoding="utf-8",
                              cwd=str(REPO_ROOT), env=env, timeout=60)
        self.assertIn(NOT_INSTALLED, proc.stderr)


class C1bTests(unittest.TestCase):
    def blocked(self, content: str) -> bool:
        r = html(content)
        self.assertNotIn("internal error", r.stderr)
        return r.returncode == 2 and "[inline-style]" in r.stderr

    def test_svg_with_fill_blocks(self):
        self.assertTrue(self.blocked('<svg style="fill: red"></svg>\n'))

    def test_g_and_text_with_left_zero_are_allowed(self):
        self.assertFalse(self.blocked('<g style="left: 0"></g>\n'))
        self.assertFalse(self.blocked('<text style="left:0; top: 4px"></text>\n'))
        self.assertFalse(self.blocked('<g style="transform: translate(1px, 2px); transform-origin: 0 0"></g>\n'))

    def test_div_with_left_zero_blocks(self):
        self.assertTrue(self.blocked('<div style="left: 0"></div>\n'))

    def test_split_rect_tag_blocks(self):
        self.assertTrue(self.blocked('<rect\n  style="left: 0"></rect>\n'))

    def test_mixed_positioning_and_colour_blocks(self):
        self.assertTrue(self.blocked('<g style="left: 0; fill: red"></g>\n'))

    def test_canvas_positioning_allowed(self):
        self.assertFalse(self.blocked('<canvas style="position: absolute; top: 0"></canvas>\n'))

    def test_suggestion_no_longer_cites_w_200px(self):
        r = html('<div style="color: red"></div>\n')
        self.assertNotIn("w-[200px]", r.stderr)


class StickyTests(unittest.TestCase):
    def test_sticky_top_4_in_class_blocks(self):
        r = html('<div class="sticky top-4"></div>\n')
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("[scroll-edge] T-012 line 1", r.stderr)

    def test_word_sticky_in_text_does_not_block(self):
        r = html("<p>The sticky note says top-4 is fine</p>\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_sticky_with_variant_blocks(self):
        r = html('<div class="p-2 md:sticky top-4"></div>\n')
        self.assertEqual(r.returncode, 2, r.stderr)


class MapHeadingTests(unittest.TestCase):
    def test_every_mapped_id_is_a_heading_in_its_document(self):
        spec = importlib.util.spec_from_file_location("architecture_guard_under_test", GUARD)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(HOOKS_DIR))
        spec.loader.exec_module(mod)
        entries = list(mod.RULE_MAP_EXACT.values()) + list(mod.RULE_MAP_PREFIX.values())
        self.assertTrue(entries)
        for rule_id, document in entries:
            with self.subTest(rule_id=rule_id):
                text = (DOCS_DIR / document).read_text(encoding="utf-8")
                self.assertRegex(text, rf"(?m)^### {rule_id} ")


if __name__ == "__main__":
    unittest.main()
