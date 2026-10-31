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
  INV-O1 (hook-server-modes contract, amendment 2026-10-09, sub-task 23; widened by the
         dedupe contract, Revision 3, block 16) hooks.json registers exactly the thirteen
         entries of the contract's table, exec form; the version obeys the merge-base rule
         with origin/master.
  INV-O2 (dedupe contract, Revision 3, block 16) the three add-ons under .claude/addons/ each
         have a manifest that parses, names files that exist, writes exec-form rows, names no
         default hook, and whose hook files are in no dispatcher and not in hooks.json; the
         three install skills exist.
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
#: Both dispatchers (dedupe contract, Revision 3): a hook file named in either one's CHECKS list is run.
STOP_DISPATCHER_REL = ".claude/hooks/stop-dispatcher.py"
DISPATCHER_RELS = (DISPATCHER_REL, STOP_DISPATCHER_REL)


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
    """The members of a dispatcher's ``CHECKS`` list, read as a literal (never imported), helpers excluded.

    Read statically the way the drift check reads it: a dispatcher whose source declares no ``CHECKS`` list
    contributes nothing, so a hook it was supposed to run shows up as unregistered."""
    import ast
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "CHECKS" for t in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return set()
            return {n for n in value if isinstance(n, str) and not n.startswith("_")}
    return set()


def coverage_problems(on_disk: set, registered: set, dispatched: set, hooks_dir=None) -> list:
    """Every non-helper hook file is registered or dispatched; nothing registered or dispatched is missing from disk.

    RULE CHANGED (dedupe contract, Revision 8, I.3; block 27). A dispatcher member holding ``/`` is a path:
    it is resolved against ``hooks_dir`` (the hooks folder) and that file must exist. It is not a hooks-folder
    listing entry, so it is never compared with ``on_disk``. A bare name keeps the old rule: it is a file in
    the hooks folder and must be in ``on_disk``. With no ``hooks_dir`` a path member cannot be resolved, so it
    is reported."""
    bare = {m for m in dispatched if "/" not in m}
    paths = {m for m in dispatched if "/" in m}
    problems = []
    if on_disk - registered - bare:
        problems.append("on disk but neither registered nor named by the dispatcher: %s"
                        % sorted(on_disk - registered - bare))
    if (registered | bare) - on_disk:
        problems.append("registered or named by the dispatcher but absent from disk: %s"
                        % sorted((registered | bare) - on_disk))
    missing_paths = sorted(m for m in paths if hooks_dir is None or not (pathlib.Path(hooks_dir) / m).is_file())
    if missing_paths:
        problems.append("named by the dispatcher as a path, but no such file beside the hooks folder: %s"
                        % missing_paths)
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
# Consequence of the gate launcher (contract 2026-10-07-worktree-isolation-by-default, block 6): a gate it
# launches is named as the launcher entry's extra argument, so that name counts as registered too.
registered |= {pathlib.Path(a).name for _e, _m, h in _real_regs for a in (h.get("args") or [])[2:]
               if isinstance(a, str) and a.startswith(PLUGIN_ROOT_PREFIX) and a.endswith(".py")}
on_disk = {p.name for p in (ROOT / ".claude" / "hooks").glob("*.py")
           if not p.name.startswith("_")}
_dispatcher_file = ROOT / DISPATCHER_REL
check("the post-edit dispatcher exists (its CHECKS list names the trackers hooks.json does not)",
      _dispatcher_file.is_file(), "missing: %s" % DISPATCHER_REL)
_stop_dispatcher_file = ROOT / STOP_DISPATCHER_REL
check("the Stop dispatcher exists (its CHECKS list names the Stop members)",
      _stop_dispatcher_file.is_file(), "missing: %s" % STOP_DISPATCHER_REL)
dispatched = set()
for _d in (_dispatcher_file, _stop_dispatcher_file):
    if _d.is_file():
        dispatched |= dispatcher_names(_d.read_text(encoding="utf-8", errors="replace"))
check("the two dispatchers' CHECKS lists name at least the five members the contract assigns them",
      {"integration-check.py", "critic-verdict-tracker.py", "contract-status-watcher.py",
       "journal-post-approval-tracker.py",
       "../scripts/concept_changed_check.py"} <= dispatched,
      "read %s" % sorted(dispatched))
_cov = coverage_problems(on_disk, registered, dispatched, ROOT / ".claude" / "hooks")
check("no hook file is left unregistered: each is in hooks.json or in a dispatcher's CHECKS list",
      not _cov, "; ".join(_cov))
check("control: a tracker named neither in hooks.json nor in the dispatcher is reported",
      bool(coverage_problems({"a.py", "stray-tracker.py"}, {"a.py"}, set())))
check("control: a tracker named only in the dispatcher's list is accepted",
      coverage_problems({"a.py", "tracker.py"}, {"a.py"}, {"tracker.py"}) == [])
check("control: a tracker named only in hooks.json is accepted",
      coverage_problems({"a.py", "tracker.py"}, {"a.py", "tracker.py"}, set()) == [])
check("control: a file named but absent from disk is reported",
      bool(coverage_problems({"a.py"}, {"a.py", "ghost.py"}, set())))
import tempfile as _coverage_tempfile  # noqa: E402 - the controls below build a throwaway hooks/scripts pair

with _coverage_tempfile.TemporaryDirectory() as _cov_tmp_name:
    _cov_hooks = pathlib.Path(_cov_tmp_name) / "hooks"
    _cov_scripts = pathlib.Path(_cov_tmp_name) / "scripts"
    _cov_hooks.mkdir()
    _cov_scripts.mkdir()
    (_cov_scripts / "present.py").write_text("# stub\n", encoding="utf-8")
    check("control (rule change I.3): a path member naming a file beside the hooks folder is accepted, and "
          "is not asked to be in the hooks folder listing",
          coverage_problems({"a.py"}, {"a.py"}, {"../scripts/present.py"}, _cov_hooks) == [],
          "; ".join(coverage_problems({"a.py"}, {"a.py"}, {"../scripts/present.py"}, _cov_hooks)))
    _cov_missing = coverage_problems({"a.py"}, {"a.py"}, {"../scripts/ghost.py"}, _cov_hooks)
    check("control (rule change I.3): a path member naming a missing file is reported",
          any("ghost.py" in p for p in _cov_missing), "; ".join(_cov_missing) or "no problem reported")
    check("control (rule change I.3): a bare name is still a hooks-folder file (present.py lives in scripts, "
          "so the bare spelling is reported) while the path spelling resolves",
          bool(coverage_problems({"a.py"}, {"a.py"}, {"present.py"}, _cov_hooks))
          and coverage_problems({"a.py"}, {"a.py"}, {"../scripts/present.py"}, _cov_hooks) == [],
          "a bare name present.py must still be looked up in the hooks folder listing")
    check("control (rule change I.3): with no hooks folder to resolve against, a path member is reported",
          bool(coverage_problems({"a.py"}, {"a.py"}, {"../scripts/present.py"})))
check("control: a bare name in the dispatcher's list keeps the hooks-folder rule (absent from disk is reported)",
      bool(coverage_problems({"a.py"}, {"a.py"}, {"ghost-tracker.py"})))
check("control: the dispatcher scan reads the CHECKS literal and ignores helpers and other constants",
      dispatcher_names('CHECKS = ["one.py", "two-x.py", "_helper.py"]\nHELPER = "_inprocess_hook.py"\n'
                       'ME = "other-hook.py"') == {"one.py", "two-x.py"})
check("control: the dispatcher scan keeps a path member as written",
      dispatcher_names('CHECKS = ["one.py", "../scripts/two_x.py"]') == {"one.py", "../scripts/two_x.py"})
check("control: a dispatcher that declares no CHECKS list contributes nothing",
      dispatcher_names('MEMBERS = ["one.py"]') == set())

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

print("\nINV-O1  hooks.json registers exactly the thirteen entries of the contract's table, in exec form")
# Contract 2026-09-28-hook-server-modes (ScalpingMachine repository), amendment 2026-10-09 "Plugin is the
# source of its hooks; fewer gates", INV-O1 and sub-task 23. It REPLACES sub-task 1's "INV-P1 hooks.json
# registers one hook" block (plugin pull request #32), which pinned the dropped registration writer.
#
# The table (event, matcher, script, extras, async). The matchers are THIS repository's: the edit group
# includes NotebookEdit, and the database guards run on PowerShell too. "Stop" and "UserPromptSubmit"
# take no matcher in Claude Code; this repository writes ".*" there, so either spelling is accepted.
EDIT_GROUP = "Edit|Write|MultiEdit|NotebookEdit"
ANY_EVENT = "*any*"  # the matcher slot of an event that takes none: absent, empty or ".*"
STOP_STATUS = "Checking changed files against approved contracts..."
OWN = PLUGIN_ROOT_PREFIX + ".claude/hooks/"

SHELL_GROUP = "Bash|PowerShell"
EXPECTED_TABLE = [
    # event, matcher, script, extras, async
    ("SessionStart", None, "working-agreements.py", (), False),
    # Amended by contract 2026-10-07-worktree-isolation-by-default, block 6: the concept gate is launched
    # through the gate launcher, which takes the gate as its extra argument.
    ("PreToolUse", EDIT_GROUP, "gate-launch.py", (PLUGIN_ROOT_PREFIX + ".claude/hooks/concept-gate.py",), False),
    # Dedupe contract, Revision 3 (B) and Revision 4 (D): the default shell row. The launcher runs the
    # main-checkout guard and the merge-direction check; the gate half (concept-gate.py) allows any tool that
    # is not an edit. It is NOT paired with bash-gate.py: no installation registers that pair.
    ("PreToolUse", SHELL_GROUP, "gate-launch.py", (PLUGIN_ROOT_PREFIX + ".claude/hooks/concept-gate.py",), False),
    ("PreToolUse", EDIT_GROUP, "architecture-guard.py", (), False),
    ("PreToolUse", EDIT_GROUP, "db-destructive-guard.py", (), False),
    ("PreToolUse", "Bash", "db-destructive-guard.py", (), False),
    ("PreToolUse", "Bash", "db-research-readonly-guard.py", (), False),
    ("PreToolUse", "PowerShell", "db-destructive-guard.py", (), False),
    ("PreToolUse", "PowerShell", "db-research-readonly-guard.py", (), False),
    ("UserPromptSubmit", ANY_EVENT, "plan-question-advisor.py", (), False),
    ("PostToolUse", "Edit|Write|MultiEdit", "post-edit-dispatcher.py", (), True),
    # The Stop dispatcher (not async, keeps a status message) runs the Changed-file check, its one member.
    ("Stop", ANY_EVENT, "stop-dispatcher.py", (), False),
    ("Stop", ANY_EVENT, "memory-pager.py", (), True),
]
assert len(EXPECTED_TABLE) == 13


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
    if len(regs) != 13:
        problems.append("it registers %d entries, not thirteen" % len(regs))
    seen = {}
    for k in keys:
        if k[2] is not None:
            seen[(k[0], k[1], k[2])] = seen.get((k[0], k[1], k[2]), 0) + 1
    for k, n in seen.items():
        if n > 1:
            problems.append("%s registered %d times for the same event and matcher: %r" % (k[2], n, k[:2]))
    for (e, m, h), k in zip(regs, keys):
        if k[2] == "stop-dispatcher.py" and e == "Stop" and h.get("statusMessage") != STOP_STATUS:
            problems.append("the Stop dispatcher entry lost its statusMessage: %r" % h.get("statusMessage"))
    return problems


def good_cfg() -> dict:
    """A hooks.json dict that is exactly the table, built from EXPECTED_TABLE (for the controls)."""
    hooks: dict = {}
    for event, matcher, script, extras, is_async in EXPECTED_TABLE:
        entry = {"type": "command", "command": "py", "args": ["-3", OWN + script] + list(extras)}
        if is_async:
            entry["async"] = True
        if event == "Stop" and script == "stop-dispatcher.py":
            entry["statusMessage"] = STOP_STATUS
        group = {"hooks": [entry]}
        if matcher not in (None, ANY_EVENT):
            group["matcher"] = matcher
        hooks.setdefault(event, []).append(group)
    return {"hooks": hooks}


check("hooks.json is exactly the thirteen entries of the table (events, matchers, scripts, extras, async)",
      not table_problems(_hooks_cfg),
      "\n".join(table_problems(_hooks_cfg)))
check("hooks.json registers exactly thirteen entries in total", len(registrations_of(_hooks_cfg)) == 13,
      "it registers %d" % len(registrations_of(_hooks_cfg)))
# The hooks that must NEVER be in hooks.json: the five add-on hook files (a project gets them only through an
# install skill) and the old name of the advisor (renamed angular-tailwind-advisor.py when it became an add-on).
ADDON_HOOK_FILES = {"bash-gate.py", "codegraph-first-guard.py", "codegraph-turn-reset.py",
                    "codegraph-turn-tracker.py", "angular-tailwind-advisor.py"}
CUT_HOOKS = ADDON_HOOK_FILES | {"architecture-advisor.py"}
DB_GUARDS = (".claude/hooks/db-destructive-guard.py", ".claude/hooks/db-research-readonly-guard.py")


def fact_async(cfg) -> bool:
    return ({k[2] for k in (entry_key(e, m, h) for e, m, h in registrations_of(cfg)) if k[4]}
            == {"post-edit-dispatcher.py", "memory-pager.py"})


def fact_status_message(cfg) -> bool:
    return any(h.get("statusMessage") == STOP_STATUS and h.get("async") is not True
               for e, m, h in registrations_of(cfg)
               if e == "Stop" and exec_relative(h) == STOP_DISPATCHER_REL)


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


def fact_shell_row(cfg) -> bool:
    """Exactly one launcher row on Bash|PowerShell, and its gate is concept-gate.py."""
    rows = [(m, h.get("args")) for e, m, h in registrations_of(cfg)
            if e == "PreToolUse" and exec_relative(h) == ".claude/hooks/gate-launch.py" and m == SHELL_GROUP]
    return rows == [(SHELL_GROUP, ["-3", OWN + "gate-launch.py", OWN + "concept-gate.py"])]


FACTS = [
    ("the dispatcher and memory-pager.py carry async: true; nothing else does", fact_async),
    ("the Stop dispatcher entry is not async and keeps the statusMessage (%r)" % STOP_STATUS, fact_status_message),
    ("the dispatcher keeps today's matcher Edit|Write|MultiEdit", fact_dispatcher_matcher),
    ("each database guard is on the edit group (destructive only), Bash and PowerShell", fact_db_guard_places),
    ("no add-on hook is registered (bash-gate, codegraph-first-guard, codegraph-turn-reset, codegraph-turn-tracker, "
     "angular-tailwind-advisor) and neither is architecture-advisor", fact_no_cut_hook),
    ("the shell row launches the gate launcher with concept-gate.py, never with bash-gate.py", fact_shell_row),
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
_c["hooks"]["Stop"][0]["hooks"][0] = {"type": "command", "command": 'py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/memory-pager.py"'}
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
check("control: a Stop dispatcher entry without its statusMessage is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["Stop"][0]["hooks"][0]["async"] = True
check("control: a Stop dispatcher that is async is rejected", bool(table_problems(_c)) or not fact_status_message(_c))
_c = good_cfg()
_c["hooks"]["PreToolUse"] = [g for g in _c["hooks"]["PreToolUse"] if g.get("matcher") != SHELL_GROUP]
check("control: the table without the shell launcher row is rejected",
      bool(table_problems(_c)) and not fact_shell_row(_c))
_c = good_cfg()
for _g in _c["hooks"]["PreToolUse"]:
    if _g.get("matcher") == SHELL_GROUP:
        _g["hooks"][0]["args"][2] = OWN + "bash-gate.py"
check("control: the shell launcher row paired with bash-gate.py is rejected",
      bool(table_problems(_c)) and not fact_shell_row(_c) and not fact_no_cut_hook(_c))
_c = good_cfg()
for _g in _c["hooks"]["PreToolUse"]:
    if _g.get("matcher") == SHELL_GROUP:
        _g["matcher"] = "Bash"
check("control: a shell launcher row on Bash alone is rejected", bool(table_problems(_c)) and not fact_shell_row(_c))
_c = good_cfg()
_c["hooks"]["UserPromptSubmit"] = [g for g in _c["hooks"]["UserPromptSubmit"]
                                   if exec_relative(g["hooks"][0]) != ".claude/hooks/plan-question-advisor.py"]
check("control: the table without plan-question-advisor.py is rejected", bool(table_problems(_c)))
_c = good_cfg()
_c["hooks"]["PreToolUse"].append({"matcher": "Read|Grep|Glob", "hooks": [
    {"type": "command", "command": "py", "args": ["-3", OWN + "angular-tailwind-advisor.py"]}]})
check("control: a registered add-on hook is rejected by the cut-hook fact", not fact_no_cut_hook(_c))
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

print("\nINV-O2  the three add-ons: manifests parse, name real files, write exec-form rows, name no default hook")
# Dedupe contract, Revision 3 (B): an add-on is a hook file the plugin ships under .claude/addons/<add-on>/hooks/
# and does NOT register. addon.json is its manifest. The field names are read through _addon_fixture's
# constants (the one seam), so a change to them is made in one place.
sys.path.insert(0, str(ROOT / ".claude" / "hooks" / "tests"))
import _addon_fixture as af  # noqa: E402

ADDONS_DIR = ROOT / ".claude" / "addons"
EXPECTED_ADDON_HOOKS = {
    "angular-tailwind": [],
    "codegraph": ["codegraph-first-guard.py", "codegraph-turn-reset.py", "codegraph-turn-tracker.py"],
    "strict-shell-gate": ["bash-gate.py"],
}
#: The documents the angular-tailwind add-on ships, and the disabled hook it keeps (issue #84).
ANGULAR_DOCUMENTS = ["ANGULAR_CODE_RULES.md", "ANGULAR_MATERIAL_RULES.md", "TAILWINDCSS_RULES.md",
                     "UI-UX-PATTERNS.md"]
ANGULAR_DISABLED_HOOK = "angular-tailwind-advisor.py"
ANGULAR_FORMER_NAMES = ["architecture-advisor.py"]
#: Events that run once per prompt or per turn. No angular-tailwind row may sit on one (I-4).
PER_PROMPT_EVENTS = {"UserPromptSubmit", "UserPromptExpansion", "Stop", "SubagentStop"}
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
#: (event, matcher) of every registration row, per file. A matcher of None is an event that takes none.
EXPECTED_ADDON_ROWS = {
    "codegraph-first-guard.py": ("PreToolUse", "Read|Grep|Glob"),
    "codegraph-turn-reset.py": ("UserPromptSubmit", None),
    "codegraph-turn-tracker.py": ("PostToolUse", "mcp__codegraph__.*"),
    "bash-gate.py": ("PreToolUse", "Bash"),
}


def default_hook_names(root: pathlib.Path) -> set:
    return {p.name for p in (root / ".claude" / "hooks").glob("*.py") if not p.name.startswith("_")}


def _plain_name(value, suffix: str) -> bool:
    return (isinstance(value, str) and value.endswith(suffix) and value not in ("", ".", "..")
            and "/" not in value and "\\" not in value and not value.startswith("."))


def disabled_problems(name: str, entries, root: pathlib.Path, default_hooks: set, dispatched: set) -> list:
    """Every way the manifest's ``disabled`` list breaks the Disabled hook entry shape; [] means it holds."""
    if entries is None:
        return []
    if not isinstance(entries, list):
        return ["%s: %r is not a list of entries" % (name, af.KEY_DISABLED)]
    problems = []
    folder = root / ".claude" / "addons" / name
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append("%s: a disabled entry is not an object" % name)
            continue
        hook = entry.get(af.DISABLED_HOOK)
        if not _plain_name(hook, ".py"):
            problems.append("%s: a disabled entry has no plain .py %r" % (name, af.DISABLED_HOOK))
            continue
        if not (folder / "hooks" / hook).is_file():
            problems.append("%s: disabled hook %s does not exist under .claude/addons/%s/hooks/" % (name, hook, name))
        if hook in default_hooks or hook in dispatched:
            problems.append("%s: disabled hook %s is a default hook or a dispatcher member" % (name, hook))
        former = entry.get(af.DISABLED_FORMER, [])
        if not isinstance(former, list) or not all(_plain_name(f, ".py") for f in former):
            problems.append("%s: %r of %s is not a list of plain .py names" % (name, af.DISABLED_FORMER, hook))
        row = entry.get(af.DISABLED_ROW)
        if not (isinstance(row, dict) and isinstance(row.get(af.ROW_EVENT), str) and row[af.ROW_EVENT]
                and isinstance(row.get(af.ROW_ARGS, []), list)
                and all(isinstance(a, str) for a in row.get(af.ROW_ARGS, []))
                and isinstance(row.get(af.ROW_MATCHER, ""), str)):
            problems.append("%s: the registration of disabled hook %s needs an event, optional matcher and "
                            "args (the row older installs carry)" % (name, hook))
        note = entry.get(af.DISABLED_NOTE)
        if not _plain_name(note, ".md") or not (folder / note).is_file():
            problems.append("%s: the note %r of disabled hook %s is not a .md file in the add-on folder"
                            % (name, note, hook))
        hashes = entry.get(af.DISABLED_HASHES)
        if not (isinstance(hashes, list) and hashes and all(isinstance(h, str) and SHA256_HEX.match(h)
                                                            for h in hashes)):
            problems.append("%s: %r of disabled hook %s is not a non-empty list of lowercase hex SHA-256 values"
                            % (name, af.DISABLED_HASHES, hook))
    return problems


def addon_problems(name: str, data, root: pathlib.Path, default_hooks: set, dispatched: set) -> list:
    """Every way an add-on manifest breaks the contract's Add-on manifest invariants (I-1 to I-3); [] means
    it holds. ``kill_switches`` is optional."""
    problems = []
    if not isinstance(data, dict):
        return ["%s: the manifest is not a JSON object" % name]
    folder = root / ".claude" / "addons" / name
    hooks = data.get(af.KEY_HOOKS)
    if not isinstance(hooks, list) or not all(_plain_name(h, ".py") for h in hooks):
        return ["%s: %r is not a list of plain .py file names" % (name, af.KEY_HOOKS)]
    documents = data.get(af.KEY_DOCUMENTS, [])
    if not isinstance(documents, list) or not all(_plain_name(d, ".md") for d in documents):
        return ["%s: %r is not a list of plain .md file names" % (name, af.KEY_DOCUMENTS)]
    if not hooks and not documents:
        problems.append("%s: I-1: %r and %r are both empty; an add-on installs something" % (
            name, af.KEY_HOOKS, af.KEY_DOCUMENTS))
    for document in documents:
        if not (folder / "documents" / document).is_file():
            problems.append("%s: document %s does not exist under .claude/addons/%s/documents/"
                            % (name, document, name))
    for hook in hooks:
        if not (folder / "hooks" / hook).is_file():
            problems.append("%s: hook file %s does not exist under .claude/addons/%s/hooks/" % (name, hook, name))
        if hook in default_hooks:
            problems.append("%s: %s is a default hook of the plugin; a manifest names no default hook" % (name, hook))
        if hook in dispatched:
            problems.append("%s: %s is a dispatcher member; an add-on hook is in no dispatcher" % (name, hook))
    helpers = data.get(af.KEY_HELPERS)
    if not isinstance(helpers, list) or not all(isinstance(h, str) for h in helpers):
        problems.append("%s: %r is not a list of plugin paths" % (name, af.KEY_HELPERS))
    else:
        for helper in helpers:
            if not (root / helper).is_file():
                problems.append("%s: helper %s does not exist in the plugin's default tree" % (name, helper))
            if pathlib.PurePosixPath(helper).name in hooks or "/addons/" in helper.replace("\\", "/"):
                problems.append("%s: helper %s is not a default-tree file" % (name, helper))
    problems += disabled_problems(name, data.get(af.KEY_DISABLED), root, default_hooks, dispatched)
    # I-3: a file name appears in at most one of hooks, disabled[].hook and disabled[].former_names.
    claimed = list(hooks)
    for entry in data.get(af.KEY_DISABLED) or []:
        if isinstance(entry, dict):
            claimed.append(entry.get(af.DISABLED_HOOK))
            claimed += [f for f in entry.get(af.DISABLED_FORMER) or [] if isinstance(f, str)]
    for dup in sorted({c for c in claimed if isinstance(c, str) and claimed.count(c) > 1}):
        problems.append("%s: I-3: %s appears more than once across hooks, disabled hooks and former names"
                        % (name, dup))
    rows = data.get(af.KEY_ROWS)
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        problems.append("%s: %r is not a list of rows" % (name, af.KEY_ROWS))
        return problems
    row_hooks = []
    for row in rows:
        text = json.dumps(row)
        hook = row.get(af.ROW_HOOK)
        row_hooks.append(hook)
        if hook not in hooks:
            problems.append("%s: I-2: a row names %r, which is not one of the manifest's hook files" % (name, hook))
        if hook in default_hooks:
            problems.append("%s: a row names default hook %s" % (name, hook))
        if not isinstance(row.get(af.ROW_EVENT), str) or not row.get(af.ROW_EVENT):
            problems.append("%s: a row for %s has no event" % (name, hook))
        args = row.get(af.ROW_ARGS, [])
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            problems.append("%s: the row for %s has args that are not a list of strings (exec form)" % (name, hook))
        if "command" in row:
            problems.append("%s: the row for %s carries a command; the install writes it in exec form, so the "
                            "manifest holds the hook file and its extra arguments only" % (name, hook))
        if "py -3" in text or "&&" in text or "CLAUDE_PLUGIN_ROOT" in text:
            problems.append("%s: the row for %s is shell form or points into the plugin; a project row is exec "
                            "form on ${CLAUDE_PROJECT_DIR}/.claude/hooks/<file>" % (name, hook))
        if af.ROW_ASYNC in row and not isinstance(row[af.ROW_ASYNC], bool):
            problems.append("%s: the row for %s has a non-boolean async" % (name, hook))
    for hook in hooks:
        if hook not in row_hooks:
            problems.append("%s: I-2: hook file %s has no registration row" % (name, hook))
    if af.KEY_KILL_SWITCHES in data:
        switches = data[af.KEY_KILL_SWITCHES]
        if not isinstance(switches, list) or not all(isinstance(s, str) and s.startswith("CLAUDE_") for s in switches):
            problems.append("%s: %r is not a list of CLAUDE_* variable names" % (name, af.KEY_KILL_SWITCHES))
    if data.get(af.KEY_INSTALL_SKILL) != "auto-improve-%s-install" % name:
        problems.append("%s: %r is %r, not auto-improve-%s-install" % (name, af.KEY_INSTALL_SKILL,
                                                                        data.get(af.KEY_INSTALL_SKILL), name))
    if data.get(af.KEY_UNINSTALL_SKILL) != "auto-improve-%s-uninstall" % name:
        problems.append("%s: %r is %r, not auto-improve-%s-uninstall" % (name, af.KEY_UNINSTALL_SKILL,
                                                                          data.get(af.KEY_UNINSTALL_SKILL), name))
    if af.KEY_PREREQUISITES not in data or not isinstance(data.get(af.KEY_PREREQUISITES), list):
        problems.append("%s: %r is not a list" % (name, af.KEY_PREREQUISITES))
    return problems


def angular_tailwind_problems(data) -> list:
    """I-4 for angular-tailwind: no kill switch, no row on a per-prompt event, the documents and the disabled
    advisor with its former name."""
    problems = []
    if af.KEY_KILL_SWITCHES in data:
        problems.append("angular-tailwind declares kill_switches %r; it declares none" % (data[af.KEY_KILL_SWITCHES],))
    if data.get(af.KEY_ROWS):
        problems.append("angular-tailwind declares registration rows; it installs no hook")
    for row in data.get(af.KEY_ROWS) or []:
        if row.get(af.ROW_EVENT) in PER_PROMPT_EVENTS:
            problems.append("angular-tailwind has a row on %s, which runs per prompt" % row.get(af.ROW_EVENT))
    if data.get(af.KEY_DOCUMENTS) != ANGULAR_DOCUMENTS:
        problems.append("angular-tailwind documents are %r, not %r" % (data.get(af.KEY_DOCUMENTS), ANGULAR_DOCUMENTS))
    disabled = data.get(af.KEY_DISABLED) or []
    if [e.get(af.DISABLED_HOOK) for e in disabled if isinstance(e, dict)] != [ANGULAR_DISABLED_HOOK]:
        problems.append("angular-tailwind disables %r, not [%r]" % (disabled, ANGULAR_DISABLED_HOOK))
    elif disabled[0].get(af.DISABLED_FORMER) != ANGULAR_FORMER_NAMES:
        problems.append("the disabled advisor lists former names %r, not %r"
                        % (disabled[0].get(af.DISABLED_FORMER), ANGULAR_FORMER_NAMES))
    return problems


_default_hooks = default_hook_names(ROOT)
check("the add-on folder holds exactly the three add-ons",
      ADDONS_DIR.is_dir() and sorted(p.name for p in ADDONS_DIR.iterdir() if p.is_dir()) == sorted(EXPECTED_ADDON_HOOKS),
      "found %s" % (sorted(p.name for p in ADDONS_DIR.iterdir()) if ADDONS_DIR.is_dir() else "no .claude/addons folder"))
_all_addon_hook_files = set()
for _name, _expected_hooks in EXPECTED_ADDON_HOOKS.items():
    _manifest_path = ADDONS_DIR / _name / "addon.json"
    try:
        _data = json.loads(_manifest_path.read_text(encoding="utf-8"))
        check("%s: addon.json parses" % _name, True)
    except (OSError, ValueError) as _exc:
        check("%s: addon.json parses" % _name, False, "%s: %s" % (_manifest_path, _exc))
        continue
    check("%s: the manifest lists exactly the hook files %s" % (_name, _expected_hooks),
          isinstance(_data, dict) and _data.get(af.KEY_HOOKS) == _expected_hooks, "lists %r" % (
              _data.get(af.KEY_HOOKS) if isinstance(_data, dict) else _data))
    _problems = addon_problems(_name, _data, ROOT, _default_hooks, dispatched)
    check("%s: the manifest names real files, exec-form rows, no default hook, no dispatcher member" % _name,
          not _problems, "\n".join(_problems))
    if isinstance(_data, dict) and isinstance(_data.get(af.KEY_ROWS), list):
        _rows = {r.get(af.ROW_HOOK): (r.get(af.ROW_EVENT), r.get(af.ROW_MATCHER) or None)
                 for r in _data[af.KEY_ROWS] if isinstance(r, dict)}
        check("%s: the rows register each hook on the contract's event and matcher" % _name,
              _rows == {h: EXPECTED_ADDON_ROWS[h] for h in _expected_hooks}, "rows %r" % (_rows,))
        _all_addon_hook_files |= set(_data.get(af.KEY_HOOKS) or [])
        # Disabled hooks and their former names are add-on hook files too: hooks.json must never register them.
        for _entry in _data.get(af.KEY_DISABLED) or []:
            _all_addon_hook_files.add(_entry.get(af.DISABLED_HOOK))
            _all_addon_hook_files |= set(_entry.get(af.DISABLED_FORMER) or [])
    if _name == "angular-tailwind":
        _angular_problems = angular_tailwind_problems(_data)
        check("angular-tailwind: I-4, no kill switch, no row (so none on a per-prompt event), four documents, "
              "the advisor disabled with its former name", not _angular_problems, "\n".join(_angular_problems))
        _note = ADDONS_DIR / _name / "DISABLED.md"
        _note_text = _note.read_text(encoding="utf-8") if _note.is_file() else ""
        for _label, _needle in (("what it did", "UserPromptSubmit"),
                                ("its cost on every prompt", "every prompt"),
                                ("the measured median", "123 ms"), ("the bare start", "50 ms"),
                                ("the context it added", "400 words"), ("the dead keyword", '"ui"'),
                                ("how to turn it back on", "turn it back on")):
            check("angular-tailwind DISABLED.md states %s" % _label, _needle in _note_text,
                  "%r is not in %s" % (_needle, _note))
        check("angular-tailwind: the kept advisor script has no CLAUDE_ARCH_ADVISOR switch",
              "CLAUDE_ARCH_ADVISOR" not in (ADDONS_DIR / _name / "hooks" / ANGULAR_DISABLED_HOOK).read_text(
                  encoding="utf-8"))
    if _name == "codegraph":
        check("codegraph: the manifest names the CodeGraph MCP server as a prerequisite",
              "mcp-server" in json.dumps(_data.get(af.KEY_PREREQUISITES)) and
              "codegraph" in json.dumps(_data.get(af.KEY_PREREQUISITES)),
              "prerequisites: %r" % _data.get(af.KEY_PREREQUISITES))
    if _name == "strict-shell-gate":
        _helper_names = [pathlib.PurePosixPath(h.replace("\\", "/")).name for h in _data.get(af.KEY_HELPERS) or []]
        check("strict-shell-gate: the helpers are _project_paths.py, _shell_write_targets.py and "
              ".claude/scripts/_contract_index.py",
              sorted(h.replace("\\", "/") for h in _data.get(af.KEY_HELPERS) or []) == sorted([
                  ".claude/hooks/_project_paths.py", ".claude/hooks/_shell_write_targets.py",
                  ".claude/scripts/_contract_index.py"]), "helpers %r" % (_data.get(af.KEY_HELPERS),))

# K-1 to K-3 (angular-tailwind followups contract, Kill-switch removal). No shipped add-on has a kill switch.
REMOVED_SWITCHES = ("CLAUDE_SKIP_CG", "CLAUDE_BASH_GATE", "CLAUDE_CONCEPT_GATE")


def kill_switch_key_problems(folder: pathlib.Path) -> list:
    """K-1: every add-on manifest under ``folder`` that still has the ``kill_switches`` key."""
    problems = []
    for manifest_file in sorted(folder.glob("*/addon.json")):
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        if isinstance(data, dict) and af.KEY_KILL_SWITCHES in data:
            problems.append("%s declares %s %r" % (manifest_file.parent.name, af.KEY_KILL_SWITCHES,
                                                   data[af.KEY_KILL_SWITCHES]))
    return problems


def removed_switch_text_problems(folder: pathlib.Path) -> list:
    """K-2, text half: every add-on hook file under ``folder`` whose text names a removed switch."""
    problems = []
    for hook_file in sorted(folder.glob("*/hooks/*.py")):
        text = hook_file.read_text(encoding="utf-8")
        for switch in REMOVED_SWITCHES:
            if switch in text:
                problems.append("%s/%s names %s" % (hook_file.parent.parent.name, hook_file.name, switch))
    return problems


def removed_switch_read_problems(folder: pathlib.Path) -> list:
    """K-2, scan half: the CLAUDE_* variables the install's ``_scan_env_vars`` finds in the add-on hooks."""
    problems = []
    for hooks_folder in sorted(folder.glob("*/hooks")):
        for switch in finish_install._scan_env_vars(hooks_folder):
            if switch in REMOVED_SWITCHES:
                problems.append("the scan of %s/hooks finds %s" % (hooks_folder.parent.name, switch))
    return problems


check("K-1: no shipped add-on manifest has a kill_switches key",
      not kill_switch_key_problems(ADDONS_DIR), "\n".join(kill_switch_key_problems(ADDONS_DIR)))
check("K-2: no add-on hook file names CLAUDE_SKIP_CG, CLAUDE_BASH_GATE or CLAUDE_CONCEPT_GATE",
      not removed_switch_text_problems(ADDONS_DIR), "\n".join(removed_switch_text_problems(ADDONS_DIR)))
check("K-2: the env-var scan of the add-on hooks finds none of the removed switches",
      not removed_switch_read_problems(ADDONS_DIR), "\n".join(removed_switch_read_problems(ADDONS_DIR)))
with tempfile.TemporaryDirectory(prefix="k2-control-") as _k2_name:
    _k2 = pathlib.Path(_k2_name)
    (_k2 / "demo" / "hooks").mkdir(parents=True)
    (_k2 / "demo" / "hooks" / "planted.py").write_text(
        'import os\nos.environ.get("CLAUDE_SKIP_CG")\n', encoding="utf-8")
    (_k2 / "demo" / "addon.json").write_text(json.dumps({af.KEY_KILL_SWITCHES: ["CLAUDE_SKIP_CG"]}),
                                             encoding="utf-8")
    check("K-1 control: a manifest with a kill_switches key is caught", bool(kill_switch_key_problems(_k2)))
    check("K-2 control: a planted os.environ.get(\"CLAUDE_SKIP_CG\") is caught by the text check",
          bool(removed_switch_text_problems(_k2)))
    check("K-2 control: a planted os.environ.get(\"CLAUDE_SKIP_CG\") is caught by the env-var scan",
          bool(removed_switch_read_problems(_k2)))
_concept_gate_text = (ROOT / ".claude" / "hooks" / "concept-gate.py").read_text(encoding="utf-8")
check("K-3: concept-gate.py still reads CLAUDE_CONCEPT_GATE",
      re.search(r"environ\.get\(\s*[\"']CLAUDE_CONCEPT_GATE[\"']", _concept_gate_text) is not None)

check("the add-on manifests together name exactly the five add-on hook files and the advisor's former name "
      "(installed, disabled or former) that hooks.json must never register",
      _all_addon_hook_files == CUT_HOOKS, "named %s" % sorted(_all_addon_hook_files))
check("no add-on hook file sits in the default hooks folder (a project gets it only through an install skill)",
      not (ADDON_HOOK_FILES & default_hook_names(ROOT)),
      "found in .claude/hooks/: %s" % sorted(ADDON_HOOK_FILES & default_hook_names(ROOT)))

for _name in EXPECTED_ADDON_HOOKS:
    _skill = ROOT / "skills" / ("auto-improve-%s-install" % _name) / "SKILL.md"
    _fm = read_frontmatter(_skill) if _skill.is_file() else {}
    check("skill auto-improve-%s-install exists, its frontmatter name equals its folder and it is user-invocable"
          % _name,
          _skill.is_file() and _fm.get("name") == "auto-improve-%s-install" % _name
          and _fm.get("user_invocable") == "true", "frontmatter %r" % (_fm,))
    _skill = ROOT / "skills" / ("auto-improve-%s-uninstall" % _name) / "SKILL.md"
    _fm = read_frontmatter(_skill) if _skill.is_file() else {}
    check("skill auto-improve-%s-uninstall exists, its frontmatter name equals its folder and it is user-invocable"
          % _name,
          _skill.is_file() and _fm.get("name") == "auto-improve-%s-uninstall" % _name
          and _fm.get("user_invocable") == "true", "frontmatter %r" % (_fm,))
    _text = _skill.read_text(encoding="utf-8") if _skill.is_file() else ""
    check("skill auto-improve-%s-uninstall runs the addon-remove subcommand for %s" % (_name, _name),
          "addon-remove --name %s" % _name in _text, "no addon-remove --name %s in the skill" % _name)

# Controls: the problem finder must be able to fail. A throwaway plugin root holds one good add-on.
with tempfile.TemporaryDirectory(prefix="addon-controls-") as _ctl_name:
    _ctl = pathlib.Path(_ctl_name)
    (_ctl / ".claude" / "hooks").mkdir(parents=True)
    (_ctl / ".claude" / "hooks" / "_project_paths.py").write_text("", encoding="utf-8")
    (_ctl / ".claude" / "hooks" / "concept-gate.py").write_text("", encoding="utf-8")
    (_ctl / ".claude" / "addons" / "demo" / "hooks").mkdir(parents=True)
    (_ctl / ".claude" / "addons" / "demo" / "hooks" / "demo-hook.py").write_text("", encoding="utf-8")

    def _good() -> dict:
        return {af.KEY_HOOKS: ["demo-hook.py"], af.KEY_HELPERS: [".claude/hooks/_project_paths.py"],
                af.KEY_ROWS: [{af.ROW_EVENT: "PreToolUse", af.ROW_MATCHER: "Bash", af.ROW_HOOK: "demo-hook.py"}],
                af.KEY_PREREQUISITES: [], af.KEY_KILL_SWITCHES: ["CLAUDE_DEMO"],
                af.KEY_INSTALL_SKILL: "auto-improve-demo-install",
                af.KEY_UNINSTALL_SKILL: "auto-improve-demo-uninstall"}

    def _ctl_problems(data, dispatched_members=frozenset()):
        return addon_problems("demo", data, _ctl, default_hook_names(_ctl), set(dispatched_members))

    check("control: a well-formed manifest has no problem", _ctl_problems(_good()) == [], str(_ctl_problems(_good())))
    _m = _good()
    _m[af.KEY_HOOKS] = ["missing-hook.py"]
    _m[af.KEY_ROWS][0][af.ROW_HOOK] = "missing-hook.py"
    check("control: a hook file that does not exist is reported", bool(_ctl_problems(_m)))
    _m = _good()
    _m[af.KEY_HOOKS] = ["concept-gate.py"]
    _m[af.KEY_ROWS][0][af.ROW_HOOK] = "concept-gate.py"
    check("control: a manifest that names a default hook is reported", bool(_ctl_problems(_m)))
    check("control: a hook file that a dispatcher runs is reported", bool(_ctl_problems(_good(), {"demo-hook.py"})))
    _m = _good()
    _m[af.KEY_ROWS][0]["command"] = 'py -3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/demo-hook.py"'
    check("control: a shell-form row is reported", bool(_ctl_problems(_m)))
    _m = _good()
    _m[af.KEY_ROWS][0][af.ROW_ARGS] = ["-3", "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/demo-hook.py"]
    check("control: a row that points into the plugin is reported", bool(_ctl_problems(_m)))
    _m = _good()
    _m[af.KEY_HELPERS] = [".claude/hooks/_not_there.py"]
    check("control: a helper that is not in the default tree is reported", bool(_ctl_problems(_m)))
    _m = _good()
    _m[af.KEY_ROWS] = []
    check("control: a hook file with no registration row is reported", bool(_ctl_problems(_m)))
    _m = _good()
    _m[af.KEY_INSTALL_SKILL] = "something-else"
    check("control: a wrong install skill name is reported", bool(_ctl_problems(_m)))
    check("control: a manifest that is not an object is reported", bool(_ctl_problems(["not", "an", "object"])))

    # The invariants of the extended manifest (I-1 to I-3, optional kill_switches). The control add-on gets a
    # document and a disabled hook with a note, so each case below changes exactly one thing.
    (_ctl / ".claude" / "addons" / "demo" / "documents").mkdir()
    (_ctl / ".claude" / "addons" / "demo" / "documents" / "DEMO_RULES.md").write_text("# rules\n", encoding="utf-8")
    (_ctl / ".claude" / "addons" / "demo" / "hooks" / "old-hook.py").write_text("", encoding="utf-8")
    (_ctl / ".claude" / "addons" / "demo" / "DISABLED.md").write_text("# off\n", encoding="utf-8")

    def _docs_only() -> dict:
        data = _good()
        data.update({af.KEY_HOOKS: [], af.KEY_ROWS: [], af.KEY_DOCUMENTS: ["DEMO_RULES.md"]})
        data.pop(af.KEY_KILL_SWITCHES)
        return data

    def _disabled_entry() -> dict:
        return {af.DISABLED_HOOK: "old-hook.py", af.DISABLED_FORMER: ["older-hook.py"],
                af.DISABLED_ROW: {af.ROW_EVENT: "UserPromptSubmit", af.ROW_ARGS: []},
                af.DISABLED_NOTE: "DISABLED.md", af.DISABLED_HASHES: ["0" * 64]}

    check("control: a documents-only add-on with no hook, no row and no kill_switches key is well formed (I-1, "
          "optional kill_switches)", _ctl_problems(_docs_only()) == [], str(_ctl_problems(_docs_only())))
    _m = _docs_only()
    _m[af.KEY_DOCUMENTS] = []
    check("control I-1: hooks and documents both empty is reported", bool(_ctl_problems(_m)))
    _m = _docs_only()
    _m[af.KEY_ROWS] = [{af.ROW_EVENT: "PreToolUse", af.ROW_HOOK: "demo-hook.py"}]
    check("control I-2: a row that names a hook the manifest does not list is reported", bool(_ctl_problems(_m)))
    _m = _docs_only()
    _m[af.KEY_DOCUMENTS] = ["MISSING.md"]
    check("control: a document that does not exist is reported", bool(_ctl_problems(_m)))
    _m = _docs_only()
    _m[af.KEY_DOCUMENTS] = ["sub/DEMO_RULES.md"]
    check("control: a document name with a separator is reported", bool(_ctl_problems(_m)))
    _m = _good()
    _m[af.KEY_KILL_SWITCHES] = ["NOT_CLAUDE"]
    check("control: a kill switch that is not a CLAUDE_* name is reported", bool(_ctl_problems(_m)))
    _m = _good()
    _m.pop(af.KEY_KILL_SWITCHES)
    check("control: a manifest with no kill_switches key is well formed", _ctl_problems(_m) == [],
          str(_ctl_problems(_m)))
    _m = _docs_only()
    _m[af.KEY_DISABLED] = [_disabled_entry()]
    check("control: a well-formed disabled hook entry has no problem", _ctl_problems(_m) == [],
          str(_ctl_problems(_m)))
    _m = _docs_only()
    _m[af.KEY_DISABLED] = [dict(_disabled_entry(), **{af.DISABLED_HOOK: "gone.py"})]
    check("control I-3: a disabled hook whose file does not exist is reported", bool(_ctl_problems(_m)))
    _m = _good()
    _m[af.KEY_DISABLED] = [dict(_disabled_entry(), **{af.DISABLED_HOOK: "demo-hook.py"})]
    check("control I-3: a file in both hooks and disabled is reported", bool(_ctl_problems(_m)))
    _m = _docs_only()
    _m[af.KEY_DISABLED] = [dict(_disabled_entry(), **{af.DISABLED_FORMER: ["old-hook.py"]})]
    check("control I-3: a former name equal to the disabled hook is reported", bool(_ctl_problems(_m)))
    _m = _docs_only()
    _m[af.KEY_DISABLED] = [dict(_disabled_entry(), **{af.DISABLED_HASHES: ["abc"]})]
    check("control: a released hash that is not a SHA-256 is reported", bool(_ctl_problems(_m)))
    _m = _docs_only()
    _m[af.KEY_DISABLED] = [dict(_disabled_entry(), **{af.DISABLED_NOTE: "NOPE.md"})]
    check("control: a disabled hook whose note file does not exist is reported", bool(_ctl_problems(_m)))
    check("control I-4: angular-tailwind with a kill switch is reported",
          bool(angular_tailwind_problems(dict(_docs_only(), **{af.KEY_KILL_SWITCHES: ["CLAUDE_ARCH_ADVISOR"]}))))
    check("control I-4: angular-tailwind with a row on UserPromptSubmit is reported",
          bool(angular_tailwind_problems({af.KEY_ROWS: [{af.ROW_EVENT: "UserPromptSubmit",
                                                         af.ROW_HOOK: ANGULAR_DISABLED_HOOK}],
                                          af.KEY_DOCUMENTS: ANGULAR_DOCUMENTS,
                                          af.KEY_DISABLED: [{af.DISABLED_HOOK: ANGULAR_DISABLED_HOOK,
                                                             af.DISABLED_FORMER: ANGULAR_FORMER_NAMES}]})))

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
