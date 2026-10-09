#!/usr/bin/env python3
"""
test_hook_data_files_project_first.py -- INV-O3 of the hook-server-modes contract's amendment
2026-10-09 ("Plugin is the source of its hooks; fewer gates"), sub-task 23.

THE RULE UNDER TEST
-------------------
A hook that Claude Code launches from the PLUGIN folder must read each of its data files from
<CLAUDE_PROJECT_DIR>/.claude/hooks/<name> first. Two kinds of data file, two fallbacks:

  advisory and pattern data   architecture-guard.rules.json, architecture-guard.exceptions.json,
                              plain-language-guard.rules.json, integration-check.rules.json
                              -> fall back to the plugin's template beside the script when the
                                 project has no such file.
  safety data                 db-destructive-guard.rules.json (read by BOTH database guards)
                              -> NEVER falls back. A project with no rules file, and an unset
                                 CLAUDE_PROJECT_DIR, both give today's fail-closed result: every
                                 database is protected (db-destructive-guard.py:375-380). The guards
                                 never read the plugin's template.

HOW IT IS TESTED (no mutation of the real plugin tree)
------------------------------------------------------
Each reader is run, as the real hook file, from a SCRATCH COPY of the plugin's hooks and scripts
folders. A different template is planted in the scratch copy, and a fixture project (a temporary
folder named by CLAUDE_PROJECT_DIR) holds a file that differs from it. So the template and the
project's file give DIFFERENT verdicts on the same payload, and the verdict says which file was read.
Control: with no project file the template decides (that is the order today's code already has, so
those cases pass today). The cases where the project's file must win fail today, on an assertion:
today's _project_paths.hook_file and the guards read the file beside the script first.

The real plugin tree is checked for one thing only: it ships the template of every advisory hook,
which includes integration-check.rules.json (it ships none today).

Run:
    py -3 .claude/hooks/tests/test_hook_data_files_project_first.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REAL_HOOKS = ROOT / ".claude" / "hooks"

_failures: list[str] = []
_passes = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passes
    if cond:
        _passes += 1
        print("  PASS  %s" % name)
    else:
        _failures.append(name)
        print("  FAIL  %s%s" % (name, ("\n        " + detail.replace("\n", "\n        ")) if detail else ""))


_TMP = tempfile.TemporaryDirectory(prefix="datafiles-")
BASE = Path(_TMP.name)
_counter = [0]


def fresh(label: str) -> Path:
    _counter[0] += 1
    path = BASE / ("%03d-%s" % (_counter[0], label))
    path.mkdir(parents=True)
    return path


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


# ---------------------------------------------------------------------------
# The scratch plugin: a copy of the plugin's code, so a template can be planted without touching the
# real tree. Never the plugin's main checkout, never the installed cache.
# ---------------------------------------------------------------------------
def make_scratch_plugin() -> Path:
    plugin = fresh("plugin")
    shutil.copytree(REAL_HOOKS, plugin / ".claude" / "hooks",
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    shutil.copytree(ROOT / ".claude" / "scripts", plugin / ".claude" / "scripts",
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
    return plugin


def make_project(rules_by_name: dict | None) -> Path:
    """A fixture project. rules_by_name maps data-file name -> JSON object, or None for 'no hooks folder'."""
    project = fresh("project")
    (project / ".claude" / "hooks").mkdir(parents=True)
    (project / ".claude" / "logs").mkdir(parents=True)
    for name, obj in (rules_by_name or {}).items():
        write_json(project / ".claude" / "hooks" / name, obj)
    return project


def run_hook(plugin: Path, hook: str, payload: dict, project: Path | None, extra_env: dict | None = None,
             args: list | None = None):
    """Launch <plugin>/.claude/hooks/<hook> as Claude Code would: stdin payload, plugin root variable."""
    home = fresh("home")
    temp = fresh("temp")
    cwd = fresh("cwd")  # neutral and empty: no .claude folder to pick up by accident
    env = dict(os.environ)
    for key in ("CLAUDE_ARCH_GUARD", "CLAUDE_PLAIN_LANGUAGE_GUARD", "CLAUDE_INTEGRATION_CHECK",
                "CLAUDE_DESTRUCTIVE_DB_OK", "CLAUDE_READONLY_GUARD", "CLAUDE_DB_RESEARCH_GUARD",
                "DB_GUARD_FAULT_INJECTION", "CLAUDE_PROJECT_DIR"):
        env.pop(key, None)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["TEMP"] = str(temp)
    env["TMP"] = str(temp)
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(plugin / ".claude" / "hooks" / hook)] + list(args or []),
                          input=json.dumps(payload).encode("utf-8"), capture_output=True,
                          cwd=str(cwd), env=env, timeout=60)


def err_of(proc) -> str:
    return (proc.stderr or b"").decode("utf-8", "replace")


def out_of(proc) -> str:
    return (proc.stdout or b"").decode("utf-8", "replace")


def detail_of(proc) -> str:
    return "rc=%s stderr=%r stdout=%r" % (proc.returncode, err_of(proc)[:400], out_of(proc)[:300])


# ---------------------------------------------------------------------------
# 0. The real plugin ships the template of every advisory hook.
# ---------------------------------------------------------------------------
print("\nINV-O3  the plugin ships a template for each advisory hook's data file")
for name in ("architecture-guard.rules.json", "architecture-guard.exceptions.json",
             "plain-language-guard.rules.json", "integration-check.rules.json"):
    check("the plugin ships .claude/hooks/%s (the fallback template)" % name,
          (REAL_HOOKS / name).is_file(), "missing: %s" % (REAL_HOOKS / name))
try:
    _ic_template = json.loads((REAL_HOOKS / "integration-check.rules.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    _ic_template = {}
check("the integration-check template names at least one backend marker and one frontend marker",
      bool(_ic_template.get("backend_markers")) and bool(_ic_template.get("frontend_markers")),
      "template content: %r" % (_ic_template,))
check("every template that exists parses as a JSON object",
      all(isinstance(json.loads((REAL_HOOKS / n).read_text(encoding="utf-8")), dict)
          for n in ("architecture-guard.rules.json", "architecture-guard.exceptions.json",
                    "plain-language-guard.rules.json", "db-destructive-guard.rules.json")
          if (REAL_HOOKS / n).is_file()))

# ---------------------------------------------------------------------------
# 1. architecture-guard.py, rules file
# ---------------------------------------------------------------------------
print("\nINV-O3  architecture-guard.py reads architecture-guard.rules.json project-first")
TEMPLATE_TOKEN = "TEMPLATE_ONLY_TOKEN_" + uuid.uuid4().hex[:8]
PROJECT_TOKEN = "PROJECT_ONLY_TOKEN_" + uuid.uuid4().hex[:8]


def arch_rule(token: str, rule_id: str) -> dict:
    return {"rules": [{"id": rule_id, "regex": token, "applies_to": "any", "scope": "all"}]}


def arch_payload(project: Path, token: str, name: str = "probe.component.ts") -> dict:
    target = project / "ClientApp" / "projects" / "app1" / "src" / "app" / name
    return {"tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "export const x = '%s';\n" % token}}


plugin = make_scratch_plugin()
write_json(plugin / ".claude" / "hooks" / "architecture-guard.rules.json", arch_rule(TEMPLATE_TOKEN, "tmpl-rule"))

no_file = make_project({})
proc = run_hook(plugin, "architecture-guard.py", arch_payload(no_file, TEMPLATE_TOKEN), no_file)
check("control: no project rules file -> the template's rule fires (exit 2)  [passes today]",
      proc.returncode == 2, detail_of(proc))
proc = run_hook(plugin, "architecture-guard.py", arch_payload(no_file, PROJECT_TOKEN), no_file)
check("control: no project rules file -> a token only the project's file would name is allowed",
      proc.returncode == 0, detail_of(proc))

with_file = make_project({"architecture-guard.rules.json": arch_rule(PROJECT_TOKEN, "proj-rule")})
proc = run_hook(plugin, "architecture-guard.py", arch_payload(with_file, PROJECT_TOKEN), with_file)
check("the project's rules file decides: its rule fires (exit 2)", proc.returncode == 2, detail_of(proc))
proc = run_hook(plugin, "architecture-guard.py", arch_payload(with_file, TEMPLATE_TOKEN), with_file)
check("the template is not read when the project has a file: the template's rule does not fire (exit 0)",
      proc.returncode == 0, detail_of(proc))

# ---------------------------------------------------------------------------
# 2. architecture-guard.py, exceptions file
# ---------------------------------------------------------------------------
print("\nINV-O3  architecture-guard.py reads architecture-guard.exceptions.json project-first")
SHARED_TOKEN = "SHARED_TOKEN_" + uuid.uuid4().hex[:8]
shared_rules = arch_rule(SHARED_TOKEN, "shared-rule")
plugin = make_scratch_plugin()
write_json(plugin / ".claude" / "hooks" / "architecture-guard.rules.json", shared_rules)
write_json(plugin / ".claude" / "hooks" / "architecture-guard.exceptions.json",
           {"ignored_files": ["template-ignored.component.ts"], "file_rule_exemptions": {}})

no_exc = make_project({"architecture-guard.rules.json": shared_rules})
proc = run_hook(plugin, "architecture-guard.py", arch_payload(no_exc, SHARED_TOKEN, "template-ignored.component.ts"), no_exc)
check("control: no project exceptions file -> the template's ignored file is let through (exit 0)  [passes today]",
      proc.returncode == 0, detail_of(proc))
proc = run_hook(plugin, "architecture-guard.py", arch_payload(no_exc, SHARED_TOKEN, "project-ignored.component.ts"), no_exc)
check("control: no project exceptions file -> a file only the project would ignore is blocked (exit 2)",
      proc.returncode == 2, detail_of(proc))

with_exc = make_project({
    "architecture-guard.rules.json": shared_rules,
    "architecture-guard.exceptions.json": {"ignored_files": ["project-ignored.component.ts"],
                                          "file_rule_exemptions": {}},
})
proc = run_hook(plugin, "architecture-guard.py", arch_payload(with_exc, SHARED_TOKEN, "project-ignored.component.ts"), with_exc)
check("the project's exceptions file decides: its ignored file is let through (exit 0)",
      proc.returncode == 0, detail_of(proc))
proc = run_hook(plugin, "architecture-guard.py", arch_payload(with_exc, SHARED_TOKEN, "template-ignored.component.ts"), with_exc)
check("the template's exceptions are not read when the project has a file: its ignored file is blocked (exit 2)",
      proc.returncode == 2, detail_of(proc))

# ---------------------------------------------------------------------------
# 3. plain-language-guard.py
# ---------------------------------------------------------------------------
print("\nINV-O3  plain-language-guard.py reads plain-language-guard.rules.json project-first")
SENTENCE = " ".join(["filler"] * 12) + "."  # 12 words, no digit, no listed short form, no dash


def transcript_for(text: str) -> Path:
    folder = fresh("transcript")
    path = folder / "t.jsonl"
    entries = [
        {"type": "user", "isSidechain": False,
         "message": {"role": "user", "content": [{"type": "text", "text": "go"}]}},
        {"type": "assistant", "isSidechain": False,
         "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}},
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return path


def stop_payload() -> dict:
    return {"session_id": "datafiles-" + uuid.uuid4().hex[:10],
            "transcript_path": str(transcript_for(SENTENCE)), "stop_hook_active": False}


STRICT = {"max_sentence_words": 5, "stop_threshold": 1}
LENIENT = {"max_sentence_words": 60, "stop_threshold": 50}
plugin = make_scratch_plugin()
write_json(plugin / ".claude" / "hooks" / "plain-language-guard.rules.json", STRICT)

none_pl = make_project({})
proc = run_hook(plugin, "plain-language-guard.py", stop_payload(), none_pl)
check("control: no project rules file -> the template's strict limit stops a 12-word sentence (exit 2)  [passes today]",
      proc.returncode == 2, detail_of(proc))
lenient_pl = make_project({"plain-language-guard.rules.json": LENIENT})
proc = run_hook(plugin, "plain-language-guard.py", stop_payload(), lenient_pl)
check("the project's lenient rules file decides: the same sentence lets the turn end (exit 0)",
      proc.returncode == 0, detail_of(proc))
plugin2 = make_scratch_plugin()
write_json(plugin2 / ".claude" / "hooks" / "plain-language-guard.rules.json", LENIENT)
strict_pl = make_project({"plain-language-guard.rules.json": STRICT})
proc = run_hook(plugin2, "plain-language-guard.py", stop_payload(), strict_pl)
check("the project's strict rules file decides even when the template is lenient: the sentence stops the turn (exit 2)",
      proc.returncode == 2, detail_of(proc))

# ---------------------------------------------------------------------------
# 4. integration-check.py
# ---------------------------------------------------------------------------
print("\nINV-O3  integration-check.py reads integration-check.rules.json project-first")


def ic_payload(project: Path, backend_marker: str) -> dict:
    target = project / backend_marker.rstrip("/") / "Api" / "Controllers" / "FooController.cs"
    return {"tool_name": "Edit", "tool_input": {"file_path": str(target).replace("\\", "/")}}


def warned(proc) -> bool:
    return proc.returncode == 0 and "[integration-check] WARNING" in out_of(proc)


plugin = make_scratch_plugin()
write_json(plugin / ".claude" / "hooks" / "integration-check.rules.json",
           {"backend_markers": ["tmplsrv/"], "frontend_markers": ["tmplweb/"]})

none_ic = make_project({})
proc = run_hook(plugin, "integration-check.py", ic_payload(none_ic, "tmplsrv/"), none_ic)
check("control: no project rules file -> the template's backend marker raises the warning  [passes today]",
      warned(proc), detail_of(proc))
proc = run_hook(plugin, "integration-check.py", ic_payload(none_ic, "projsrv/"), none_ic)
check("control: no project rules file -> a marker only the project's file names raises nothing",
      not warned(proc), detail_of(proc))
with_ic = make_project({"integration-check.rules.json": {"backend_markers": ["projsrv/"],
                                                         "frontend_markers": ["projweb/"]}})
proc = run_hook(plugin, "integration-check.py", ic_payload(with_ic, "projsrv/"), with_ic)
check("the project's rules file decides: its backend marker raises the warning", warned(proc), detail_of(proc))
proc = run_hook(plugin, "integration-check.py", ic_payload(with_ic, "tmplsrv/"), with_ic)
check("the template is not read when the project has a file: the template's marker raises nothing",
      not warned(proc), detail_of(proc))

# ---------------------------------------------------------------------------
# 5. both database guards, db-destructive-guard.rules.json (safety data: never a fallback)
# ---------------------------------------------------------------------------
print("\nINV-O3  both database guards read db-destructive-guard.rules.json project-first and never fall back")
_INSERT = "INS" + "ERT INTO"
_DELETE = "DEL" + "ETE"
TEMPLATE_DB = "TemplateDb"
PROJECT_DB = "ProjectDb"
OTHER_DB = "ZebraLedger"
RULES_NAME = "db-destructive-guard.rules.json"


def rules_for(name: str) -> dict:
    return {"protected_databases": [name], "production_path_allowlist": [".claude/", "docs/"]}


def db_write_payload(project: Path | None, db: str) -> dict:
    base = (project if project is not None else BASE) / "src" / "Probe.cs"
    content = ('const string cs = "Server=(localdb)\\\\m;Database=%s;Trusted_Connection=True;";\n'
               'await conn.ExecuteAsync("%s Users (Id) VALUES (1)");' % (db, _INSERT))
    return {"tool_name": "Write", "tool_input": {"file_path": str(base).replace("\\", "/"), "content": content}}


def readonly_payload(db: str) -> dict:
    # `-S` makes it an opened connection the guard looks at; `-d <db>` is the session context; the disposable
    # name in the comment is what the exemption looks for, so the verdict turns on whether <db> is protected.
    cmd = 'sqlcmd -S x -d %s -Q "%s FROM Users -- cleanup %s_Test_abc123def456"' % (db, _DELETE, db)
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def blocked(proc) -> bool:
    return proc.returncode == 2


plugin = make_scratch_plugin()
write_json(plugin / ".claude" / "hooks" / RULES_NAME, rules_for(TEMPLATE_DB))
with_rules = make_project({RULES_NAME: rules_for(PROJECT_DB)})
no_rules = make_project({})  # a project that names no rules file

# --- db-destructive-guard.py
proc = run_hook(plugin, "db-destructive-guard.py", db_write_payload(with_rules, PROJECT_DB), with_rules)
check("db-destructive-guard: the project's rules file decides: its protected database is blocked",
      blocked(proc) and "PROTECTED" in err_of(proc), detail_of(proc))
proc = run_hook(plugin, "db-destructive-guard.py", db_write_payload(with_rules, TEMPLATE_DB), with_rules)
check("db-destructive-guard: the template is not read when the project has a file: the template's database is allowed",
      proc.returncode == 0, detail_of(proc))
proc = run_hook(plugin, "db-destructive-guard.py", {"tool_name": "Bash", "tool_input": {"command": "git status --short"}}, with_rules)
check("control: db-destructive-guard allows a harmless command in the same project (it is not blocking everything)",
      proc.returncode == 0, detail_of(proc))
proc = run_hook(plugin, "db-destructive-guard.py", db_write_payload(no_rules, OTHER_DB), no_rules)
check("db-destructive-guard: a project with NO rules file protects every database (an unnamed one is blocked)",
      blocked(proc) and "PROTECTED" in err_of(proc), detail_of(proc))
proc = run_hook(plugin, "db-destructive-guard.py", db_write_payload(None, OTHER_DB), None)
check("db-destructive-guard: an UNSET CLAUDE_PROJECT_DIR protects every database (an unnamed one is blocked)",
      blocked(proc) and "PROTECTED" in err_of(proc), detail_of(proc))
proc = run_hook(plugin, "db-destructive-guard.py", {"tool_name": "Bash", "tool_input": {"command": "git status --short"}}, no_rules)
check("control: db-destructive-guard still allows a harmless command with no project rules file",
      proc.returncode == 0, detail_of(proc))

# --- db-research-readonly-guard.py
proc = run_hook(plugin, "db-research-readonly-guard.py", readonly_payload(PROJECT_DB), with_rules)
check("db-research-readonly-guard: the project's rules file decides: a write on its protected database is blocked",
      blocked(proc), detail_of(proc))
proc = run_hook(plugin, "db-research-readonly-guard.py", readonly_payload(TEMPLATE_DB), with_rules)
check("db-research-readonly-guard: the template is not read when the project has a file: the template's database "
      "is no longer protected, so its disposable-target write is exempt (exit 0)",
      proc.returncode == 0, detail_of(proc))
proc = run_hook(plugin, "db-research-readonly-guard.py", {"tool_name": "Bash", "tool_input": {"command": "git status --short"}}, with_rules)
check("control: db-research-readonly-guard allows a harmless command in the same project",
      proc.returncode == 0, detail_of(proc))
proc = run_hook(plugin, "db-research-readonly-guard.py", readonly_payload(OTHER_DB), no_rules)
check("db-research-readonly-guard: a project with NO rules file protects every database (an unnamed one is blocked)",
      blocked(proc), detail_of(proc))
proc = run_hook(plugin, "db-research-readonly-guard.py", readonly_payload(OTHER_DB), None)
check("db-research-readonly-guard: an UNSET CLAUDE_PROJECT_DIR protects every database (an unnamed one is blocked)",
      blocked(proc), detail_of(proc))

print("\n%s\n %d passed, %d failed\n%s" % ("-" * 60, _passes, len(_failures), "-" * 60))
_TMP.cleanup()
sys.exit(1 if _failures else 0)
