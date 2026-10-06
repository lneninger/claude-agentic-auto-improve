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
  INV-8  Every command in hooks.json resolves to a real file, and every hook
         file is registered. Both directions: an unresolvable command is a
         crash, an unregistered hook is a file nothing runs.
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

print("\nINV-8  hook registration is complete in both directions")
hooks_field = loaded[".claude-plugin/plugin.json"].get("hooks", "")
rel_hooks = hooks_field[2:] if hooks_field.startswith("./") else hooks_field
check("the Claude manifest's hooks path exists: %s" % rel_hooks,
      bool(rel_hooks) and (ROOT / rel_hooks).is_file())

command_pattern = re.compile(r'\$\{CLAUDE_PLUGIN_ROOT\}/(\S+?)"')
commands = [entry["command"]
            for groups in loaded[".claude/hooks/hooks.json"]["hooks"].values()
            for group in groups
            for entry in group["hooks"]]
relatives = []
for command in commands:
    match = command_pattern.search(command)
    if match:
        relatives.append(match.group(1))
check("every hook command interpolates ${CLAUDE_PLUGIN_ROOT}",
      len(relatives) == len(commands),
      "%d of %d did not" % (len(commands) - len(relatives), len(commands)))
unresolved = [r for r in relatives if not (ROOT / r).is_file()]
check("all %d hook commands resolve to a real file" % len(relatives),
      not unresolved, str(unresolved))

registered = {pathlib.Path(r).name for r in relatives}
on_disk = {p.name for p in (ROOT / ".claude" / "hooks").glob("*.py")
           if not p.name.startswith("_")}
check("no hook file is left unregistered", registered == on_disk,
      "only on disk: %s / only registered: %s"
      % (sorted(on_disk - registered), sorted(registered - on_disk)))

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

print("\nINV-11c  working-agreements.py is registered on SessionStart, no matcher, no arguments")
_hooks_cfg = json.loads((ROOT / ".claude" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
_ss_groups = _hooks_cfg.get("hooks", {}).get("SessionStart", [])
_wa_regs = [(g, h) for g in _ss_groups for h in g.get("hooks", [])
            if "working-agreements.py" in str(h.get("command", ""))]
check("hooks.json registers working-agreements.py under the SessionStart event exactly once",
      len(_wa_regs) == 1, "found %d registration(s) under SessionStart" % len(_wa_regs))
check("that SessionStart group has no matcher key, or an empty one (so it runs on every start source)",
      bool(_wa_regs) and not _wa_regs[0][0].get("matcher"),
      "group was %r" % (_wa_regs[0][0] if _wa_regs else None))
check("the command has no arguments after the hook path",
      bool(_wa_regs) and re.fullmatch(r'py -3 "\$\{CLAUDE_PLUGIN_ROOT\}/\.claude/hooks/working-agreements\.py"',
                                      str(_wa_regs[0][1].get("command", ""))) is not None,
      "command was %r" % (_wa_regs[0][1].get("command") if _wa_regs else None))
check("working-agreements.py is registered under no other event",
      all("working-agreements.py" not in str(h.get("command", ""))
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

print("\n%s\n %d passed, %d failed\n%s"
      % ("-" * 60, _passes, len(_failures), "-" * 60))
sys.exit(1 if _failures else 0)
