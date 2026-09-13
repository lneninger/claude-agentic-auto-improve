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

print("\n%s\n %d passed, %d failed\n%s"
      % ("-" * 60, _passes, len(_failures), "-" * 60))
sys.exit(1 if _failures else 0)
