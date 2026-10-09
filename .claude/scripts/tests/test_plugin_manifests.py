#!/usr/bin/env python3
"""
test_plugin_manifests.py -- suite for the three provider plugin mechanisms.

House style: plain runnable script, NO pytest -- matches
test_script_path_resolution.py and the hooks suites. check(name, cond, detail)
accumulator, printed PASS/FAIL summary, non-zero exit on any failure.

    py -3 .claude/scripts/tests/test_plugin_manifests.py

--------------------------------------------------------------------------
WHAT THIS PINS DOWN
--------------------------------------------------------------------------
This repository is installable three ways, and every one of them is a set of
declarations that can drift away from the tree without anything complaining:

  * Claude Code       .claude-plugin/plugin.json  + .claude-plugin/marketplace.json
  * Cursor            plugin.json (Agent Plugins) + .cursor-plugin/plugin.json
  * OpenAI Codex      plugin.json (Agent Plugins) + .agents/plugins/marketplace.json

A manifest that names a directory which was later renamed, a hook added to
.claude/hooks/ but never registered in hooks.json, or a plugin name that differs
between two manifests, all produce the SAME observable outcome: the install
reports success and the component silently does not load. That is the exact
failure mode CONTRIBUTING.md records for the sync tooling -- "a wrapper script
that returns 0 having done nothing looks exactly like a clean sync" -- so it
gets a suite rather than a convention.

THE INVARIANTS

  INV-1  Every manifest is syntactically valid JSON.
  INV-2  The plugin name is byte-identical in all five places it is declared.
         A mismatch breaks the `<plugin>@<marketplace>` install string.
  INV-3  The install command README tells a user to type actually resolves
         against the marketplace and plugin names as declared.
  INV-4  The name obeys the Agent Plugins rules (lowercase, starts and ends
         alphanumeric, no consecutive '-' or '.').
  INV-5  skills/ is at the PLUGIN ROOT. This is not style. The portable Agent
         Plugins manifest has no component-path fields, so a skill anywhere
         else is invisible to OpenAI Codex.
  INV-6  Every skill directory holds a SKILL.md. A directory without one is
         not a skill to any of the three providers.
  INV-7  hooks/ is NOT at the repository root, and _project_paths.py is still
         two levels below it. SELF_ROOT is Path(__file__).parent.parent, so a
         hook at <root>/hooks/ resolves SELF_ROOT to the repository root and
         every registry, area-map and contract lookup misses -- silently, at
         exit 0. This invariant is why the hooks did not move with the skills.
  INV-8  Every entry in hooks.json (exec form) resolves to a real file, and every hook
         file is registered in hooks.json or named in the post-edit dispatcher's
         constant list. Both directions: an unresolvable command is a
         crash, an unregistered hook is a file nothing runs.
  INV-O1 (hook-server-modes contract, amendment 2026-10-09, sub-task 23) hooks.json
         registers exactly the twelve entries of the contract's table, exec form;
         the version obeys the merge-base rule with origin/master.
  INV-9  A LICENSE exists and every manifest that declares one agrees with it.
         The repository is public; without this it is legally unreusable and
         Cursor's marketplace will not review it.
  INV-10 README.md does not still claim the repository is not installable.
  INV-14 every --flag skills/auto-improve-finish-install/SKILL.md names exists in the
         script's argparse parser, and the skill mentions plan-sha256.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

_failures: list[str] = []
_passes = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passes
    if cond:
        _passes += 1
        print("  PASS  %s" % name)
    else:
        _failures.append(name)
        print("  FAIL  %s%s" % (name, ("  -- " + detail) if detail else ""))


MANIFESTS = {
    "plugin.json": "Agent Plugins -- Cursor and OpenAI Codex",
    ".claude-plugin/plugin.json": "Claude Code",
    ".claude-plugin/marketplace.json": "Claude Code marketplace",
    ".cursor-plugin/plugin.json": "Cursor",
    ".agents/plugins/marketplace.json": "OpenAI Codex marketplace",
    ".claude/hooks/hooks.json": "Claude hook registration",
}

loaded: dict[str, dict] = {}

print("\nINV-1  every manifest is valid JSON")
for rel, why in MANIFESTS.items():
    path = ROOT / rel
    if not path.is_file():
        check("%s exists (%s)" % (rel, why), False, "missing")
        continue
    try:
        loaded[rel] = json.loads(path.read_text(encoding="utf-8"))
        check("%s parses (%s)" % (rel, why), True)
    except json.JSONDecodeError as exc:
        check("%s parses (%s)" % (rel, why), False, str(exc))

if len(loaded) != len(MANIFESTS):
    print("\nabort: a manifest is missing or unparseable; later invariants "
          "would report noise rather than signal")
    print("\n%s\n %d passed, %d failed\n%s" % ("-" * 60, _passes, len(_failures), "-" * 60))
    sys.exit(1)

print("\nINV-2  the plugin name is identical everywhere it is declared")
declared_names = {
    "plugin.json": loaded["plugin.json"]["name"],
    ".claude-plugin/plugin.json": loaded[".claude-plugin/plugin.json"]["name"],
    ".cursor-plugin/plugin.json": loaded[".cursor-plugin/plugin.json"]["name"],
    "claude marketplace entry": loaded[".claude-plugin/marketplace.json"]["plugins"][0]["name"],
    "openai marketplace entry": loaded[".agents/plugins/marketplace.json"]["plugins"][0]["name"],
}
check("all five declarations agree", len(set(declared_names.values())) == 1,
      repr(declared_names))

PLUGIN = loaded[".claude-plugin/plugin.json"]["name"]
MARKET = loaded[".claude-plugin/marketplace.json"]["name"]
readme = (ROOT / "README.md").read_text(encoding="utf-8")

print("\nINV-3  the documented install command resolves")
check("README contains '/plugin install %s@%s'" % (PLUGIN, MARKET),
      ("/plugin install %s@%s" % (PLUGIN, MARKET)) in readme)

print("\nINV-4  the name obeys the Agent Plugins rules")
check("lowercase, alphanumeric at both ends",
      bool(re.fullmatch(r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?", PLUGIN)), PLUGIN)
check("no consecutive '-' or '.'", "--" not in PLUGIN and ".." not in PLUGIN, PLUGIN)

print("\nINV-5 / INV-6  components sit where each provider looks")
check("skills/ is at the plugin root (required by OpenAI Codex)",
      (ROOT / "skills").is_dir())
check("agents/ is at the plugin root (Claude and Cursor default)",
      (ROOT / "agents").is_dir())
skill_dirs = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir()) \
    if (ROOT / "skills").is_dir() else []
without = [p.name for p in skill_dirs if not (p / "SKILL.md").is_file()]
check("every one of the %d skill directories holds a SKILL.md" % len(skill_dirs),
      not without, "missing in: %s" % without)
check("at least one agent is shipped",
      bool(list((ROOT / "agents").glob("*.md")) if (ROOT / "agents").is_dir() else []))

print("\nINV-7  hooks did NOT move to the repository root")
check("no <root>/hooks/ directory exists", not (ROOT / "hooks").exists(),
      "a hook there resolves SELF_ROOT to the repo root and misses every registry")
check(".claude/hooks/_project_paths.py is still in place",
      (ROOT / ".claude" / "hooks" / "_project_paths.py").is_file())

print("\nINV-8  hook registration is complete in both directions (exec form; the dispatcher's list counts)")
# Amended by sub-task 23 (hook-server-modes contract, amendment 2026-10-09, INV-O1): the entries are
# exec form (command "py", args "-3" then ${CLAUDE_PLUGIN_ROOT}/.claude/hooks/<script>), and a hook file
# counts as registered when hooks.json names it OR the post-edit dispatcher's constant list does.
hooks_field = loaded[".claude-plugin/plugin.json"].get("hooks", "")
rel_hooks = hooks_field[2:] if hooks_field.startswith("./") else hooks_field
check("the Claude manifest's hooks path exists: %s" % rel_hooks,
      bool(rel_hooks) and (ROOT / rel_hooks).is_file())

PLUGIN_ROOT_PREFIX = "${CLAUDE_PLUGIN_ROOT}/"
DISPATCHER_REL = ".claude/hooks/post-edit-dispatcher.py"


def registrations_of(cfg: dict) -> list:
    """[(event, matcher, hook dict)] for every hook a hooks.json dict registers."""
    return [(event, group.get("matcher"), hook)
            for event, groups in cfg.get("hooks", {}).items()
            for group in groups
            for hook in group.get("hooks", [])]


def exec_relative(hook: dict):
    """The plugin-relative script path of an EXEC-FORM entry (command "py", args "-3" then the path), else None."""
    args = hook.get("args")
    if (hook.get("type") == "command" and hook.get("command") == "py" and isinstance(args, list)
            and len(args) >= 2 and args[0] == "-3" and isinstance(args[1], str)
            and args[1].startswith(PLUGIN_ROOT_PREFIX)):
        return args[1][len(PLUGIN_ROOT_PREFIX):]
    return None


def dispatcher_names(source: str) -> set:
    """Hook file names the dispatcher's source names as quoted literals (its constant list), helpers excluded."""
    return {n for n in re.findall(r"""["']([\w][\w-]*\.py)["']""", source)
            if not n.startswith("_") and n != "post-edit-dispatcher.py"}


def coverage_problems(on_disk: set, registered: set, dispatched: set) -> list:
    """Every non-helper hook file is registered or dispatched; nothing registered or dispatched is missing from disk."""
    problems = []
    if on_disk - registered - dispatched:
        problems.append("on disk but neither registered nor named by the dispatcher: %s"
                        % sorted(on_disk - registered - dispatched))
    if (registered | dispatched) - on_disk:
        problems.append("registered or named by the dispatcher but absent from disk: %s"
                        % sorted((registered | dispatched) - on_disk))
    return problems


_real_regs = registrations_of(loaded[".claude/hooks/hooks.json"])
relatives = [exec_relative(h) for _e, _m, h in _real_regs]
check("every hook entry is exec form: command 'py', args '-3' then ${CLAUDE_PLUGIN_ROOT}/<path>",
      all(r is not None for r in relatives),
      "%d of %d entries are not: %s" % (sum(r is None for r in relatives), len(relatives),
                                         [h.get("command") for _e, _m, h in _real_regs if exec_relative(h) is None]))
relatives = [r for r in relatives if r is not None]
unresolved = [r for r in relatives if not (ROOT / r).is_file()]
check("all %d hook entries resolve to a real file" % len(relatives), not unresolved, str(unresolved))

registered = {pathlib.Path(r).name for r in relatives}
on_disk = {p.name for p in (ROOT / ".claude" / "hooks").glob("*.py")
           if not p.name.startswith("_")}
_dispatcher_file = ROOT / DISPATCHER_REL
check("the post-edit dispatcher exists (its constant list names the trackers hooks.json does not)",
      _dispatcher_file.is_file(), "missing: %s" % DISPATCHER_REL)
dispatched = (dispatcher_names(_dispatcher_file.read_text(encoding="utf-8", errors="replace"))
              if _dispatcher_file.is_file() else set())
_cov = coverage_problems(on_disk, registered, dispatched)
check("no hook file is left unregistered: each is in hooks.json or in the dispatcher's constant list",
      not _cov, "; ".join(_cov))
check("control: a tracker named neither in hooks.json nor in the dispatcher is reported",
      bool(coverage_problems({"a.py", "stray-tracker.py"}, {"a.py"}, set())))
check("control: a tracker named only in the dispatcher's list is accepted",
      coverage_problems({"a.py", "tracker.py"}, {"a.py"}, {"tracker.py"}) == [])
check("control: a tracker named only in hooks.json is accepted",
      coverage_problems({"a.py", "tracker.py"}, {"a.py", "tracker.py"}, set()) == [])
check("control: a file named but absent from disk is reported",
      bool(coverage_problems({"a.py"}, {"a.py", "ghost.py"}, set())))
check("control: the dispatcher scan reads quoted names and ignores helpers and its own name",
      dispatcher_names('CHECKS = ["one.py", "two-x.py"]\nHELPER = "_inprocess_hook.py"\nME = "post-edit-dispatcher.py"')
      == {"one.py", "two-x.py"})

print("\nINV-9  the licence is present and consistent")
license_path = ROOT / "LICENSE"
check("LICENSE exists at the repository root", license_path.is_file())
if license_path.is_file():
    spdx = {rel: m["license"] for rel, m in loaded.items() if "license" in m}
    check("every manifest declaring a licence declares the same one",
          len(set(spdx.values())) == 1, repr(spdx))
    if spdx:
        name = next(iter(set(spdx.values())))
        check("the LICENSE file matches the declared '%s'" % name,
              name.split("-")[0].lower()
              in license_path.read_text(encoding="utf-8").lower())

print("\nINV-10  the README no longer contradicts what ships")
check("the 'not a plugin the editor can load' claim is gone",
      "not** a plugin the editor can load" not in readme)
for needle, provider in (("/plugin marketplace add", "Claude Code"),
                         ("codex plugin marketplace add", "OpenAI Codex"),
                         ("/add-plugin", "Cursor")):
    check("README documents how to install on %s" % provider, needle in readme)

print("\nINV-11  one version, declared five times, identical everywhere")
VERSION_FILES = ("plugin.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                 ".cursor-plugin/plugin.json")


def collect_versions(root: pathlib.Path) -> dict:
    """Every "version" value under `root`, keyed by 'file#path', so a marketplace file
    that declares it twice contributes two entries."""
    found: dict = {}

    def walk(node, rel, trail):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "version" and isinstance(value, str):
                    found["%s#%s" % (rel, trail or "root")] = value
                walk(value, rel, "%s.%s" % (trail, key) if trail else key)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, rel, "%s[%d]" % (trail, i))

    for rel in VERSION_FILES:
        walk(json.loads((root / rel).read_text(encoding="utf-8")), rel, "")
    return found


def versions_agree(found: dict) -> bool:
    return len(found) == 5 and len(set(found.values())) == 1


declared_versions = collect_versions(ROOT)
check("the version is declared in exactly five places", len(declared_versions) == 5,
      "found %d: %r" % (len(declared_versions), declared_versions))
check("all five version declarations are identical", versions_agree(declared_versions),
      repr(declared_versions))

# Positive control: a copy of the tree where ONE declaration differs must be caught,
# or the check above would pass against any five values.
import shutil
import tempfile

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = pathlib.Path(tmp_name)
    for rel in VERSION_FILES:
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp / rel)
    check("control: the untouched copy agrees", versions_agree(collect_versions(tmp)))
    victim = tmp / ".cursor-plugin/plugin.json"
    data = json.loads(victim.read_text(encoding="utf-8"))
    data["version"] = data["version"] + ".drift"
    victim.write_text(json.dumps(data), encoding="utf-8")
    check("control: one differing declaration is detected",
          not versions_agree(collect_versions(tmp)))

print("\nINV-11b  the declared version has reached 0.4.0 (the working-agreements hook is a feature)")


def version_tuple(text: str):
    parts = text.split("-")[0].split(".")
    return tuple(int(x) for x in parts)


try:
    current = version_tuple(next(iter(declared_versions.values())))
except (StopIteration, ValueError):
    current = ()
check("the declared version is at least 0.4.0 (compared as integer tuples)",
      bool(current) and current >= (0, 4, 0),
      "declared %s" % ".".join(str(x) for x in current))

print("\nINV-11c  working-agreements.py is registered on SessionStart, no matcher, no arguments (exec form)")
_hooks_cfg = json.loads((ROOT / ".claude" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
_ss_groups = _hooks_cfg.get("hooks", {}).get("SessionStart", [])


def _names_working_agreements(hook: dict) -> bool:
    return "working-agreements.py" in (str(hook.get("command", "")) + " " + " ".join(map(str, hook.get("args") or [])))


_wa_regs = [(g, h) for g in _ss_groups for h in g.get("hooks", []) if _names_working_agreements(h)]
check("hooks.json registers working-agreements.py under the SessionStart event exactly once",
      len(_wa_regs) == 1, "found %d registration(s) under SessionStart" % len(_wa_regs))
check("that SessionStart group has no matcher key, or an empty one (so it runs on every start source)",
      bool(_wa_regs) and not _wa_regs[0][0].get("matcher"),
      "group was %r" % (_wa_regs[0][0] if _wa_regs else None))
check("the entry is exec form with no arguments after the hook path: command 'py', args ['-3', '<plugin root>/.claude/hooks/working-agreements.py']",
      bool(_wa_regs) and _wa_regs[0][1].get("command") == "py"
      and _wa_regs[0][1].get("args") == ["-3", "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/working-agreements.py"],
      "entry was %r" % (_wa_regs[0][1] if _wa_regs else None))
check("working-agreements.py is registered under no other event",
      all(not _names_working_agreements(h)
          for ev, groups in _hooks_cfg.get("hooks", {}).items() if ev != "SessionStart"
          for g in groups for h in g.get("hooks", [])))
check("control: the registration matcher is read from the group, not guessed (a matcher would be seen)",
      bool({"matcher": "x", "hooks": []}.get("matcher")) and not {"hooks": []}.get("matcher"))

print("\nINV-12  the README's environment-variable table matches what the hooks read")
EXCLUDED_ENV = {"CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT"}
env_read = re.compile(
    r"""(?:environ\.get\(\s*|environ\[\s*|getenv\(\s*)["'](CLAUDE_[A-Z0-9_]+)["']""")
read_by_hooks = set()
for hook in sorted((ROOT / ".claude" / "hooks").glob("*.py")):
    read_by_hooks.update(env_read.findall(hook.read_text(encoding="utf-8", errors="replace")))
read_by_hooks -= EXCLUDED_ENV

documented = set()
for line in readme.splitlines():
    cell = re.match(r"^\|\s*`(CLAUDE_[A-Z0-9_]+)(?:[=`])", line)
    if cell:
        documented.add(cell.group(1))
documented -= EXCLUDED_ENV

check("the hook sources read at least one CLAUDE_* variable (the scan found something)",
      len(read_by_hooks) > 0)
check("every variable a hook reads is in the README table", read_by_hooks <= documented,
      "missing from the README: %s" % sorted(read_by_hooks - documented))
check("the README table lists no variable a hook does not read", documented <= read_by_hooks,
      "documented but never read: %s" % sorted(documented - read_by_hooks))

print("\nINV-13  the finish-install skill ships with valid frontmatter")
skill_file = ROOT / "skills" / "auto-improve-finish-install" / "SKILL.md"
check("skills/auto-improve-finish-install/SKILL.md exists", skill_file.is_file())


def read_frontmatter(path: pathlib.Path) -> dict:
    """The key: value pairs of a leading --- block; {} when there is none."""
    text = path.read_text(encoding="utf-8").lstrip("﻿").replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    out = {}
    for line in match.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if kv:
            out[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return out


front = read_frontmatter(skill_file) if skill_file.is_file() else {}
check("it opens with a YAML frontmatter block", bool(front),
      "no frontmatter found" if skill_file.is_file() else "file missing")
check("frontmatter name is 'auto-improve-finish-install'",
      front.get("name") == "auto-improve-finish-install", "name=%r" % front.get("name"))
check("frontmatter description is non-empty", bool(front.get("description")),
      "description=%r" % front.get("description"))

print("\nINV-14  every flag the finish-install skill names exists in the script's parser")
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))
import argparse  # noqa: E402
import auto_improve_finish_install as finish_install  # noqa: E402


def parser_flags(parser: argparse.ArgumentParser) -> set:
    """Every --long option the parser and its subparsers accept."""
    flags = set()
    for action in parser._actions:  # noqa: SLF001 - the only way to enumerate a parser's options
        flags.update(o for o in action.option_strings if o.startswith("--"))
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            for sub in action.choices.values():
                flags |= parser_flags(sub)
    return flags


def flags_named_by(text: str) -> set:
    """--flags the skill text names, leaving out lines that run a different script (the doctor)."""
    found = set()
    for line in text.splitlines():
        if "plugin_doctor" in line:
            continue
        found.update(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", line))
    return found


script_flags = parser_flags(finish_install.build_parser())
skill_text = skill_file.read_text(encoding="utf-8") if skill_file.is_file() else ""
named = flags_named_by(skill_text)
check("the parser exposes the contract flags (the scan of the parser found something)",
      {"--project", "--json", "--apply", "--expect-sha256", "--set", "--skip", "--platform",
       "--provider", "--claude-home"} <= script_flags, "found %s" % sorted(script_flags))
check("the skill names at least the flags of both steps", {"--apply", "--expect-sha256", "--set"} <= named,
      "named %s" % sorted(named))
check("every --flag the skill names exists in the script's parser", named <= script_flags,
      "named by the skill but not accepted: %s" % sorted(named - script_flags))
check("control: the flag scan sees a flag that is not in the parser",
      flags_named_by("run it with --no-such-flag") - script_flags == {"--no-such-flag"})
check("control: the flag scan ignores a line that runs the doctor",
      flags_named_by("py plugin_doctor.py --fix") == set())
check("the skill tells the operator the hash a hooks apply needs: it mentions plan-sha256",
      "plan-sha256" in skill_text)

print("\nINV-15  the README states the real case count of the finish-install suite")
_suite_file = ROOT / ".claude" / "scripts" / "tests" / "test_auto_improve_finish_install.py"
_real_cases = (len(re.findall(r"^\s*def test_\w+", _suite_file.read_text(encoding="utf-8"), re.M))
               if _suite_file.is_file() else 0)
_readme_text = (ROOT / "README.md").read_text(encoding="utf-8")


def stated_case_count(text: str):
    """The N in a phrase like "test_auto_improve_finish_install.py` holds its N cases"; None when absent."""
    m = re.search(r"test_auto_improve_finish_install\.py`?\s+(?:holds|has|contains|carries)\s+(?:its\s+)?"
                  r"(\d+)\s+(?:cases|tests)", text)
    return int(m.group(1)) if m else None


check("the suite file exists and holds test methods (the count scan found something)", _real_cases > 0,
      "found %d" % _real_cases)
check("README does not state a case count for test_auto_improve_finish_install.py that differs from the suite's",
      stated_case_count(_readme_text) in (None, _real_cases),
      "README says %r, the suite has %d `def test_` methods" % (stated_case_count(_readme_text), _real_cases))
check("control: the count scan reads a stated number",
      stated_case_count("and `test_auto_improve_finish_install.py` holds its 7 cases.") == 7)
check("control: the count scan treats a README without a count as nothing stated",
      stated_case_count("no count is given here") is None)

print("\nINV-O1  hooks.json registers exactly the twelve entries of the contract's table, in exec form")
# Contract 2026-09-28-hook-server-modes (ScalpingMachine repository), amendment 2026-10-09 "Plugin is the
# source of its hooks; fewer gates", INV-O1 and sub-task 23. It REPLACES sub-task 1's "INV-P1 hooks.json
# registers one hook" block (plugin pull request #32), which pinned the dropped registration writer.
#
# The table (event, matcher, script, extras, async). The matchers are THIS repository's: the edit group
# includes NotebookEdit, and the database guards run on PowerShell too. "Stop" and "UserPromptSubmit"
# take no matcher in Claude Code; this repository writes ".*" there, so either spelling is accepted.
EDIT_GROUP = "Edit|Write|MultiEdit|NotebookEdit"
ANY_EVENT = "*any*"  # the matcher slot of an event that takes none: absent, empty or ".*"
STOP_STATUS = "Checking the message reads plainly..."
OWN = PLUGIN_ROOT_PREFIX + ".claude/hooks/"

EXPECTED_TABLE = [
    # event, matcher, script, extras, async
    ("SessionStart", None, "working-agreements.py", (), False),
    ("PreToolUse", EDIT_GROUP, "concept-gate.py", (), False),
    ("PreToolUse", EDIT_GROUP, "architecture-guard.py", (), False),
    ("PreToolUse", EDIT_GROUP, "db-destructive-guard.py", (), False),
    ("PreToolUse", "Bash", "db-destructive-guard.py", (), False),
    ("PreToolUse", "Bash", "db-research-readonly-guard.py", (), False),
    ("PreToolUse", "PowerShell", "db-destructive-guard.py", (), False),
    ("PreToolUse", "PowerShell", "db-research-readonly-guard.py", (), False),
    ("UserPromptSubmit", ANY_EVENT, "plain-language-guard.py", ("--carry-forward",), False),
    ("PostToolUse", "Edit|Write|MultiEdit", "post-edit-dispatcher.py", (), True),
    ("Stop", ANY_EVENT, "plain-language-guard.py", (), False),
    ("Stop", ANY_EVENT, "memory-pager.py", (), True),
]
assert len(EXPECTED_TABLE) == 12


def entry_key(event, group_matcher, hook):
    """(event, matcher, script, extras, async) of one registered hook; script is None for a non-exec-form entry."""
    rel = exec_relative(hook)
    script = pathlib.Path(rel).name if rel is not None and rel.startswith(".claude/hooks/") else None
    args = hook.get("args") or []
    extras = tuple(args[2:]) if rel is not None else ()
    matcher = group_matcher
    if event in ("SessionStart",):
        matcher = None if not group_matcher else group_matcher
    elif event in ("Stop", "UserPromptSubmit"):
        matcher = ANY_EVENT if group_matcher in (None, "", ".*") else group_matcher
    return (event, matcher, script, extras, hook.get("async") is True)


def table_problems(cfg: dict) -> list:
    """Every way a hooks.json dict departs from the contract's table; [] means it is exactly the table."""
    problems = []
    regs = registrations_of(cfg)
    keys = [entry_key(e, m, h) for e, m, h in regs]
    for (e, m, h), k in zip(regs, keys):
        if k[2] is None:
            problems.append("not exec form (command 'py', args '-3' then ${CLAUDE_PLUGIN_ROOT}/.claude/hooks/<script>): "
                            "%s %s %r" % (e, m, h.get("command")))
    for want in EXPECTED_TABLE:
        count = keys.count(want)
        if count != 1:
            problems.append("expected exactly one %r, found %d" % (want, count))
    for k in keys:
        if k not in EXPECTED_TABLE and k[2] is not None:
            problems.append("an entry outside the table: %r" % (k,))
    if len(regs) != 12:
        problems.append("it registers %d entries, not twelve" % len(regs))
    seen = {}
    for k in keys:
        if k[2] is not None:
            seen[(k[0], k[1], k[2])] = seen.get((k[0], k[1], k[2]), 0) + 1
    for k, n in seen.items():
        if n > 1:
            problems.append("%s registered %d times for the same event and matcher: %r" % (k[2], n, k[:2]))
    for (e, m, h), k in zip(regs, keys):
        if k[2] == "plain-language-guard.py" and e == "Stop" and h.get("statusMessage") != STOP_STATUS:
            problems.append("the Stop plain-language entry lost its statusMessage: %r" % h.get("statusMessage"))
    return problems


def good_cfg() -> dict:
    """A hooks.json dict that is exactly the table, built from EXPECTED_TABLE (for the controls)."""
    hooks: dict = {}
    for event, matcher, script, extras, is_async in EXPECTED_TABLE:
        entry = {"type": "command", "command": "py", "args": ["-3", OWN + script] + list(extras)}
        if is_async:
            entry["async"] = True
        if event == "Stop" and script == "plain-language-guard.py":
            entry["statusMessage"] = STOP_STATUS
        group = {"hooks": [entry]}
        if matcher not in (None, ANY_EVENT):
            group["matcher"] = matcher
        hooks.setdefault(event, []).append(group)
    return {"hooks": hooks}


check("hooks.json is exactly the twelve entries of the table (events, matchers, scripts, extras, async)",
      not table_problems(_hooks_cfg),
      "\n".join(table_problems(_hooks_cfg)))
check("hooks.json registers exactly twelve entries in total", len(registrations_of(_hooks_cfg)) == 12,
      "it registers %d" % len(registrations_of(_hooks_cfg)))
CUT_HOOKS = {"bash-gate.py", "codegraph-first-guard.py", "codegraph-turn-reset.py", "codegraph-turn-tracker.py",
             "architecture-advisor.py", "plan-question-advisor.py"}
DB_GUARDS = (".claude/hooks/db-destructive-guard.py", ".claude/hooks/db-research-readonly-guard.py")


def fact_async(cfg) -> bool:
    return ({k[2] for k in (entry_key(e, m, h) for e, m, h in registrations_of(cfg)) if k[4]}
            == {"post-edit-dispatcher.py", "memory-pager.py"})


def fact_status_message(cfg) -> bool:
    return any(h.get("statusMessage") == STOP_STATUS for e, m, h in registrations_of(cfg)
               if e == "Stop" and exec_relative(h) == ".claude/hooks/plain-language-guard.py")


def fact_dispatcher_matcher(cfg) -> bool:
    return any(m == "Edit|Write|MultiEdit" and exec_relative(h) == DISPATCHER_REL
               for _e, m, h in registrations_of(cfg))


def fact_db_guard_places(cfg) -> bool:
    return ({(m, exec_relative(h)) for e, m, h in registrations_of(cfg)
             if e == "PreToolUse" and exec_relative(h) in DB_GUARDS}
            == {(EDIT_GROUP, DB_GUARDS[0]), ("Bash", DB_GUARDS[0]), ("Bash", DB_GUARDS[1]),
                ("PowerShell", DB_GUARDS[0]), ("PowerShell", DB_GUARDS[1])})


def fact_no_cut_hook(cfg) -> bool:
    """Reads the command and args TEXT, so a string-form or exec-form entry for a cut hook is both seen."""
    text = " ".join(str(h.get("command", "")) + " " + " ".join(map(str, h.get("args") or []))
                    for _e, _m, h in registrations_of(cfg))
    return not any(name in text for name in CUT_HOOKS)


FACTS = [
    ("the dispatcher and memory-pager.py carry async: true; nothing else does", fact_async),
    ("the Stop plain-language-guard.py entry keeps its statusMessage (%r)" % STOP_STATUS, fact_status_message),
    ("the dispatcher keeps today's matcher Edit|Write|MultiEdit", fact_dispatcher_matcher),
    ("each database guard is on the edit group (destructive only), Bash and PowerShell", fact_db_guard_places),
    ("no cut hook is registered (bash-gate, codegraph-first-guard, codegraph-turn-reset, codegraph-turn-tracker, "
     "architecture-advisor, plan-question-advisor)", fact_no_cut_hook),
]
for _label, _fact in FACTS:
    check(_label, _fact(_hooks_cfg))
check("control: each of those facts holds for a hooks.json built from the table",
      all(_fact(good_cfg()) for _l, _fact in FACTS), str([_l for _l, _fact in FACTS if not _fact(good_cfg())]))
_c = good_cfg()
_c["hooks"]["PreToolUse"].append({"matcher": "Read|Grep|Glob", "hooks": [
    {"type": "command", "command": 'py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/codegraph-first-guard.py"'}]})
check("control: a string-form entry for a cut hook is seen by the cut-hook fact", not fact_no_cut_hook(_c))

check("control: a hooks.json built from the table is accepted", table_problems(good_cfg()) == [],
      "\n".join(table_problems(good_cfg())))
_c = good_cfg()
_c["hooks"]["Stop"][0]["hooks"][0] = {"type": "command", "command": 'py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/plain-language-guard.py"'}
check("control: a string-form entry is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["PreToolUse"].append({"matcher": "Bash", "hooks": [
    {"type": "command", "command": "py", "args": ["-3", OWN + "bash-gate.py"]}]})
check("control: an added bash-gate.py is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["PostToolUse"] = []
check("control: a missing dispatcher is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["PreToolUse"] = [g for g in _c["hooks"]["PreToolUse"] if g.get("matcher") != "PowerShell"]
check("control: the guards without their PowerShell entries are rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["PreToolUse"] = [g for g in _c["hooks"]["PreToolUse"]
                             if not (g.get("matcher") == "PowerShell"
                                     and exec_relative(g["hooks"][0]) == ".claude/hooks/db-destructive-guard.py")]
check("control: one guard without its PowerShell entry is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["PostToolUse"][0]["hooks"][0].pop("async")
check("control: a dispatcher that is not async is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["Stop"][0]["hooks"][0].pop("statusMessage")
check("control: a Stop plain-language entry without its statusMessage is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["PreToolUse"][0]["matcher"] = "Edit|Write|MultiEdit"
check("control: an edit group without NotebookEdit is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["PostToolUse"].append(json.loads(json.dumps(_c["hooks"]["PostToolUse"][0])))
check("control: a script registered twice for one event and matcher is rejected", bool(table_problems(_c)))
check("control: the matcher '.*' on Stop is read as no matcher (Claude Code ignores it there)",
      table_problems({"hooks": {**good_cfg()["hooks"],
                                "Stop": [{**g, "matcher": ".*"} for g in good_cfg()["hooks"]["Stop"]]}}) == [],
      "\n".join(table_problems({"hooks": {**good_cfg()["hooks"],
                                          "Stop": [{**g, "matcher": ".*"} for g in good_cfg()["hooks"]["Stop"]]}})))

print("\nINV-O1  the version is bumped exactly when the tree differs from its merge base with origin/master")
# Amended from sub-task 1's "every version declaration exceeds origin's version": a branch whose tree
# equals its merge base (nothing changed) must equal the merge base's version, a branch whose tree differs
# must exceed it. When git or origin/master cannot be read the check FAILS, naming the cause. It never skips:
# a skipped check looks exactly like a passed one.
import subprocess  # noqa: E402


def _git(root: pathlib.Path, *args: str):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60)


def read_merge_base_state(root: pathlib.Path):
    """(base_version tuple, tree_differs bool, cause str). On any failure: (None, None, the cause)."""
    try:
        head = _git(root, "rev-parse", "--verify", "HEAD")
        if head.returncode != 0:
            return None, None, "git cannot read HEAD in %s: %s" % (root, (head.stderr or head.stdout).strip()[:200])
        base = _git(root, "merge-base", "HEAD", "origin/master")
        if base.returncode != 0 or not base.stdout.strip():
            return None, None, ("git cannot find a merge base with origin/master (no remote-tracking ref, or no "
                                "common history): %s" % (base.stderr or base.stdout).strip()[:200])
        mb = base.stdout.strip()
        shown = _git(root, "show", "%s:.claude-plugin/plugin.json" % mb)
        if shown.returncode != 0:
            return None, None, "git cannot read .claude-plugin/plugin.json at the merge base %s: %s" % (
                mb[:12], (shown.stderr or "").strip()[:200])
        base_version = version_tuple(json.loads(shown.stdout)["version"])
        tracked = _git(root, "diff", "--quiet", mb)
        if tracked.returncode not in (0, 1):
            return None, None, "git diff against the merge base failed: %s" % (tracked.stderr or "").strip()[:200]
        untracked = _git(root, "ls-files", "--others", "--exclude-standard")
        if untracked.returncode != 0:
            return None, None, "git ls-files failed: %s" % (untracked.stderr or "").strip()[:200]
        differs = tracked.returncode == 1 or bool(untracked.stdout.strip())
        return base_version, differs, ""
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        return None, None, "reading the merge base failed: %s: %s" % (type(exc).__name__, exc)


def version_matches_tree(found: dict, base: tuple, tree_differs: bool) -> bool:
    """A differing tree must exceed the merge base's version in all five declarations; an equal tree must equal it."""
    if not found:
        return False
    if tree_differs:
        return all(version_tuple(v) > base for v in found.values())
    return all(version_tuple(v) == base for v in found.values())


_base, _differs, _cause = read_merge_base_state(ROOT)
if _cause:
    check("the merge base with origin/master can be read through git", False, _cause)
else:
    _shown = ".".join(str(x) for x in _base)
    _bumped = ".".join(str(x) for x in _base[:-1] + (_base[-1] + 1,))
    check("the version obeys the merge-base rule: tree %s the merge base (%s), so all five declarations %s it"
          % ("differs from" if _differs else "equals", _shown, "exceed" if _differs else "equal"),
          version_matches_tree(declared_versions, _base, _differs),
          "declared %r; merge-base version %s; tree differs: %s" % (declared_versions, _shown, _differs))
    check("control: on a differing tree a declaration equal to the merge base's version is rejected",
          not version_matches_tree({"x#root": _shown}, _base, True))
    check("control: on a differing tree a declaration one patch above the merge base's is accepted",
          version_matches_tree({"x#root": _bumped}, _base, True))
    check("control: on an equal tree a declaration equal to the merge base's version is accepted",
          version_matches_tree({"x#root": _shown}, _base, False))
    check("control: on an equal tree a bumped declaration is rejected",
          not version_matches_tree({"x#root": _bumped}, _base, False))
    check("control: on an equal tree a lowered declaration is rejected",
          not version_matches_tree({"x#root": "0.0.0"}, _base, False))

# The reader itself, against throwaway repositories (never this one): it must read the equal case, the
# differing case (tracked change and untracked file), and FAIL, naming the cause, when it cannot read.
with tempfile.TemporaryDirectory(prefix="mb-controls-") as _tmp_name:
    _tmp = pathlib.Path(_tmp_name)

    def _make_repo(name: str, with_origin: bool) -> pathlib.Path:
        repo = _tmp / name
        (repo / ".claude-plugin").mkdir(parents=True)
        (repo / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")
        for args in (("init", "-q"), ("config", "user.email", "t@example.invalid"), ("config", "user.name", "t"),
                     ("add", "-A"), ("commit", "-q", "-m", "base")):
            _git(repo, *args)
        if with_origin:
            _git(repo, "update-ref", "refs/remotes/origin/master", "HEAD")
        return repo

    _equal_repo = _make_repo("equal", True)
    _v, _d, _c = read_merge_base_state(_equal_repo)
    check("control: the reader reads an unchanged tree as equal to its merge base (version 1.2.3)",
          _c == "" and _v == (1, 2, 3) and _d is False, "got %r" % ((_v, _d, _c),))
    (_equal_repo / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": "1.2.4"}), encoding="utf-8")
    _v, _d, _c = read_merge_base_state(_equal_repo)
    check("control: the reader reads a tracked change as a differing tree", _c == "" and _d is True,
          "got %r" % ((_v, _d, _c),))
    _fresh = _make_repo("untracked", True)
    (_fresh / "new-file.txt").write_text("x", encoding="utf-8")
    _v, _d, _c = read_merge_base_state(_fresh)
    check("control: the reader reads an untracked file as a differing tree", _c == "" and _d is True,
          "got %r" % ((_v, _d, _c),))
    _no_origin = _make_repo("no-origin", False)
    _v, _d, _c = read_merge_base_state(_no_origin)
    check("control: with no origin/master the reader fails and names the cause (it never skips)",
          _v is None and "origin/master" in _c, "got %r" % ((_v, _d, _c),))
    _not_repo = _tmp / "not-a-repo"
    _not_repo.mkdir()
    _v, _d, _c = read_merge_base_state(_not_repo)
    check("control: outside a repository the reader fails and names the cause",
          _v is None and bool(_c), "got %r" % ((_v, _d, _c),))

print("\n%s\n %d passed, %d failed\n%s"
      % ("-" * 60, _passes, len(_failures), "-" * 60))
sys.exit(1 if _failures else 0)
