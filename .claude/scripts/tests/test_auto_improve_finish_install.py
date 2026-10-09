#!/usr/bin/env python3
"""
Tests for auto_improve_finish_install.py -- finish Quick start steps 4 (profile) and 5 (hooks).

RED suite written from the approved contract
.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md (design decision 8).

Every test runs against a throwaway directory and a fake Claude home. No test reads the real
home directory, the real settings or the real plugin cache, runs a real hook, or uses the network.

Run: py -3 .claude/scripts/tests/test_auto_improve_finish_install.py

---------------------------------------------------------------------------------------
SHAPE ASSUMPTIONS (the skeleton returns only a status dict, so the result shapes are pinned
HERE, using the contract's own wording; the implementer satisfies them)
---------------------------------------------------------------------------------------
Every public function returns a dict.

Refusal   {"status": "refused", "code": <in REFUSAL_CODES>, "message": <non-empty str naming the
          reason>, "path": <str>}. A refusal always means nothing was changed. The process exit
          code is EXIT_CLASS[code]; main() returns it and, with --json, prints the same dict.
Success   plan results carry "status": "plan"; a profile or hooks apply that wrote carries
          "status": "applied" (a hooks apply also carries "backup": <path of the backup file>);
          an apply with nothing to change carries "status": "nothing-to-do" and writes nothing.
          main() returns 0 for all of these and, with --json, prints the dict.

InstallModeVerdict (detect_install_mode)
          {"mode": one of INSTALL_MODES, "enabled": True|False|None,
           "facts": [{"name", "observed", "path"}, ...]}  every fact names the path it read.
          enabled is None when no installation entry applies. A plugin that is installed but
          switched off is mode "plugin" with enabled False (plan_hooks then refuses it as
          plugin-disabled). A present but unreadable or unrecognised record is returned as the
          install-record-unreadable Refusal, never as a verdict.

ProfilePlan (propose_profile)
          {"status": "plan", "target": str, "existed": bool,
           "source-sha256": <hex sha256 of the profile bytes the preview read, or "absent">,
           "proposals": [SlotProposal], "rows-to-fill": [slot], "rows-to-add": [slot],
           "unified-diff": str, "local-agents": [agent name],
           "missing-row-detection": "available" | "unavailable"}
          SlotProposal {"slot", "values": list of str (the string "none" is accepted for none),
           "basis": inferred|needs-answer|kept-authored|none-found, "evidence": [Evidence],
           "note": str};  Evidence {"path" (project-relative), "reason" (closed set)}.
          Roots are written project-relative with forward slashes.
          apply_profile(project, sets, ...) takes sets as {slot: "v1,v2"} (raw text after the
          first "=" of --set); success is {"status": "applied"} or {"status": "nothing-to-do"}.

SettingsPlan (plan_hooks on a vendored project)
          {"status": "plan", "target": str, "source-sha256": hex sha256 | "absent",
           "to-add": [HookRegistration], "already-present": [{"registration-key", "layer":
           user|project|local, "different-matcher": bool, "foreign-path": bool}],
           "interpreter": "py -3" | "python3", "disable-all-hooks": bool, "unified-diff": str}
          HookRegistration {"event", "matcher" (or None), "command", "registration-key"}; the
          registration key is a string that contains the event, the hook file name and any
          argument after it. Hooks are skipped by hook FILE NAME ("memory-pager.py").

ReadinessReport (plan_hooks / readiness_report on a plugin install)
          {"status": "plan", "ready": bool, "install-path", "installed-version",
           "marketplace-version", "hooks-registered": int, "unresolved-commands": [str],
           "manifest-hooks-resolves": bool,   (TEST ASSUMPTION: the install path's
                                               .claude-plugin/plugin.json "hooks" field resolves)
           "interpreter-found": bool, "hooks-compile": bool, "compile-failures": [str],
           "disable-all-hooks": bool, "duplicate-vendored-registration": bool,
           "kill-switches": [env var names], "database-guard-rules":
           "absent-fail-closed"|"template-placeholders"|"configured",
           "not-verifiable": [str], "code-search-first-note": str,
           "mode": "plugin", "verdict": str,
           "platform-note": str}              (TEST ASSUMPTION: this dedicated key is present and
                                               non-empty when the platform is linux or darwin,
                                               explaining that the cached hooks.json launches
                                               py -3 and this command cannot fix it; on win32 it
                                               is merely absent or empty)

          SettingsPlan also carries "plan-sha256" (round two): a SHA-256 over the settings file
          bytes (or "absent"), the planned output bytes and the sorted --skip list. A hooks apply
          takes THAT hash as --expect-sha256; "source-sha256" stays the input-bytes hash only.
          Round three (W3): the ProfilePlan carries "plan-sha256" too (a SHA-256 over the profile
          bytes or "absent", and the planned output bytes); a PROFILE apply takes THAT hash as
          --expect-sha256 and "source-sha256" stays the input-bytes hash only. The plan also names the
          template root it read as "plugin-root" (None when no template was found).

Implementation seams the tests rely on (all stated by the contract or the repository rules):
  * the script uses `import shutil` and calls `shutil.which(name)` at CALL time, NOT
    `from shutil import which`, so patching "shutil.which" reaches it; the name looked up is
    "python3" on linux and darwin and "py" on win32 (the suite's stub records every name);
  * the script uses `os.replace` (not `Path.replace`/`shutil.move`) for the atomic rename, so
    patching "os.replace" reaches it;
  * `plugin_root=` is a HARD override, exactly like plugin_doctor.find_plugin_root(explicit):
    no lookup is tried when it is given. The script still applies the template-source rule to it:
    the project itself, or a project that is itself the plugin's own checkout (its
    .claude-plugin/plugin.json names agentic-auto-improve), is never the template source, while a
    separate plugin root (which carries that same manifest) is accepted;
  * the refusal for `hooks --apply` under a plugin install is `plugin-install-needs-no-registration`;
  * the Claude home is the claude_home argument / --claude-home, else CLAUDE_CONFIG_DIR, else
    ~/.claude;
  * the marketplace clone is <claude-home>/plugins/marketplaces/<marketplace>/
    .claude-plugin/marketplace.json, whose plugins[] entry named agentic-auto-improve carries
    the declared "version";
  * the database rules file of a plugin install is
    <installPath>/.claude/hooks/db-destructive-guard.rules.json.
"""

import contextlib
import datetime
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auto_improve_finish_install as fi  # noqa: E402
from auto_improve_finish_install import (  # noqa: E402
    EXIT_CLASS,
    INSTALL_MODES,
    PROVIDERS,
    REFUSAL_CODES,
)
from pr_merged import (  # noqa: E402
    DEFAULT_IMPLEMENTERS,
    DEFAULT_REVIEW_GATES,
    load_implementers,
    load_slot,
)

SCRIPT_ROOT = Path(fi.__file__).resolve().parents[2]

# The contract's own copy of the exit-code split, independent of EXIT_CLASS. Exit codes are
# asserted as the LITERALS 0, 2 and 3 everywhere; a constant imported from the module under
# test would agree with a wrong implementation.
ENVIRONMENT_CODES = {"project-unreadable", "template-missing", "hooks-json-missing"}

EVIDENCE_REASONS = {"manifest", "folder-name", "config-entry", "file-exists", "git-remote", "agent-file"}

PLUGIN_NAME = "agentic-auto-improve"

# --------------------------------------------------------------------------------------
# The fake plugin: a small template, 16 hook files and a hooks.json of 17 registrations.
# --------------------------------------------------------------------------------------

SLOTS = (
    "project.name", "backend.roots", "frontend.roots", "frontend.theme-polarity", "test.roots",
    "migration.root", "auth.roots", "safety-critical.roots", "review.documents", "implementers",
    "review-gates",
)

_PLACEHOLDERS = {
    "project.name": "*(the repository name)*",
    "backend.roots": "*(one or more source roots for server-side code, or `none`)*",
    "frontend.roots": "*(one or more source roots for client-side code, or `none`)*",
    "frontend.theme-polarity": "*(per frontend root: `light`, `dark`, or `both`; or `none`)*",
    "test.roots": "*(one or more test project roots, or `none`)*",
    "migration.root": "*(the database migration directory, or `none`)*",
    "auth.roots": "*(the authentication and credential code roots, or `none`)*",
    "safety-critical.roots": "*(roots where a defect causes irreversible harm, or `none`)*",
    "review.documents": "*(the primary documents a reviewer must read, or `none`)*",
    "implementers": "*(the agents that may own a contract sub-task, or `none` to accept the plugin's own)*",
    "review-gates": "*(the agents that review rather than implement, or `none` to accept the plugin's own)*",
}


def template_row(slot, value=None):
    return "| `%s` | %s |" % (slot, value if value is not None else _PLACEHOLDERS[slot])


EXTRA_SLOT = "ops.runbooks"
EXTRA_PLACEHOLDER = "*(the folder holding the operational runbooks, or `none`)*"


def template_text(overrides=None, drop=(), extra=None):
    """The plugin's profile template; overrides replaces a row's value, drop removes a row,
    extra={slot: placeholder prose} appends slots the standard eleven do not include."""
    overrides = overrides or {}
    rows = [template_row(s, overrides.get(s)) for s in SLOTS if s not in drop]
    rows += ["| `%s` | %s |" % (slot, prose) for slot, prose in (extra or {}).items()]
    return (
        "# Project Profile\n\n"
        "**TEMPLATE.** Copy this file to `.claude/project-profile.md` in a consuming repository and fill in\n"
        "every slot. This is the only file a new project must author to make the vendored generic agents\n"
        "correct.\n\n"
        "## What this file is for\n\n"
        "A generic agent must not carry a literal path from one project into another.\n\n"
        "## Slots\n\n"
        "| Slot | Value |\n|---|---|\n" + "\n".join(rows) + "\n\n"
        "### A note on `implementers`\n\n"
        "Leaving it `none` accepts the agents the plugin ships.\n\n"
        "## Worked shape\n\n"
        "```\n"
        "| `migration.root` | `src/AcmeApp.Persistence/Migrations/` |\n"
        "```\n"
    )


# (event, matcher, [hook file or (hook file, extra argument)])  -> 17 registrations, 16 files.
REGISTRATIONS = [
    ("PreToolUse", "Edit|Write|MultiEdit", ["concept-gate.py", "architecture-guard.py"]),
    ("PreToolUse", "Bash", ["bash-gate.py"]),
    ("PreToolUse", "Bash|Edit|Write|MultiEdit", ["db-destructive-guard.py", "db-research-readonly-guard.py"]),
    ("PreToolUse", "Read|Grep|Glob", ["codegraph-first-guard.py"]),
    ("PostToolUse", "Edit|Write|MultiEdit", [
        "contract-status-watcher.py", "critic-verdict-tracker.py",
        "journal-post-approval-tracker.py", "integration-check.py"]),
    ("PostToolUse", "mcp__codegraph__.*", ["codegraph-turn-tracker.py"]),
    ("UserPromptSubmit", None, [
        "codegraph-turn-reset.py", "architecture-advisor.py", "plan-question-advisor.py",
        ("plain-language-guard.py", "--carry-forward")]),
    ("Stop", None, ["plain-language-guard.py", "memory-pager.py"]),
]


def _entries():
    for event, matcher, hooks in REGISTRATIONS:
        for h in hooks:
            name, extra = (h, None) if isinstance(h, str) else h
            yield event, matcher, name, extra


HOOK_FILES = sorted({name for _e, _m, name, _x in _entries()})
EXPECTED_KEYS = {(e, n, (x,) if x else ()) for e, _m, n, x in _entries()}
assert len(list(_entries())) == 17 and len(HOOK_FILES) == 16

_HOOK_SOURCES = {
    "concept-gate.py": 'import os\nos.environ.get("CLAUDE_CONCEPT_GATE", "")\nos.environ.get("CLAUDE_PROJECT_DIR")\n',
    "bash-gate.py": 'import os\nos.environ.get("CLAUDE_BASH_GATE", "")\n',
    "architecture-guard.py": 'import os\nos.environ.get("CLAUDE_ARCH_GUARD", "")\n',
}


def build_plugin(root):
    """A fake plugin root: template, agents, hook files, hooks.json, rules file, plugin.json."""
    root = Path(root)
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": PLUGIN_NAME, "version": "0.3.0", "hooks": "./.claude/hooks/hooks.json"}),
        encoding="utf-8")
    (root / ".claude/templates").mkdir(parents=True)
    (root / ".claude/templates/concept-contract.md").write_text("# Concept Contract\n", encoding="utf-8")
    (root / ".claude/project-profile.md").write_text(template_text(), encoding="utf-8")
    (root / "agents").mkdir()
    (root / ".claude/agents").mkdir()
    names = list(DEFAULT_IMPLEMENTERS) + list(DEFAULT_REVIEW_GATES)
    for i, name in enumerate(names):
        folder = root / "agents" if i % 2 == 0 else root / ".claude/agents"
        (folder / (name + ".md")).write_text("# " + name + "\n", encoding="utf-8")
    (root / "agents/plug-agent-a.md").write_text("# a\n", encoding="utf-8")
    (root / ".claude/agents/plug-agent-b.md").write_text("# b\n", encoding="utf-8")
    hooks = root / ".claude/hooks"
    hooks.mkdir(parents=True)
    for name in HOOK_FILES:
        (hooks / name).write_text(_HOOK_SOURCES.get(name, "import sys\nsys.exit(0)\n"), encoding="utf-8")
    (hooks / "db-destructive-guard.rules.json").write_text(
        json.dumps({"protected_databases": ["AcmeApp", "AcmeApp_Testing"]}), encoding="utf-8")
    (hooks / "hooks.json").write_text(json.dumps(hooks_json_obj(), indent=2), encoding="utf-8")
    return root


def hooks_json_obj(only=None):
    """hooks.json in the plugin's string form; only= limits it to the named hook files."""
    events = {}
    for event, matcher, name, extra in _entries():
        if only is not None and name not in only:
            continue
        cmd = 'py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/%s"%s' % (name, (" " + extra) if extra else "")
        groups = events.setdefault(event, [])
        group = next((g for g in groups if g.get("matcher") == matcher), None)
        if group is None:
            group = {"hooks": []}
            if matcher is not None:
                group["matcher"] = matcher
            groups.append(group)
        group["hooks"].append({"type": "command", "command": cmd})
    return {"$comment": ["uses ${CLAUDE_PLUGIN_ROOT} and py -3 in prose"], "hooks": events}


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

def rmtree_force(path):
    def _fix(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=_fix)


def snapshot(root):
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(Path(root).rglob("*"))}


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_files(root, files):
    for rel, content in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def write_json(path, obj, indent=2, newline="\n", bom=False):
    text = json.dumps(obj, indent=indent, ensure_ascii=False).replace("\n", newline) + newline
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def tokens_of(hook):
    """Command tokens of one registration, whether in string form or command + args form."""
    cmd = hook.get("command", "")
    if hook.get("args") is not None:
        return [cmd] + [str(a) for a in hook["args"]]
    return shlex.split(cmd, posix=True)


def key_of(hook):
    """(hook file name, arguments after it) of a registration, or None when it names no .py."""
    toks = tokens_of(hook)
    for i, t in enumerate(toks):
        if t.endswith(".py"):
            return (t.replace("\\", "/").rsplit("/", 1)[-1], tuple(toks[i + 1:]))
    return None


def flat_registrations(settings):
    """[(event, matcher, hook file, extras, hook dict)] for every registration in a settings dict."""
    out = []
    for event, groups in (settings.get("hooks") or {}).items():
        for g in groups:
            for h in g.get("hooks", []):
                k = key_of(h)
                if k:
                    out.append((event, g.get("matcher"), k[0], k[1], h))
    return out


def has_plugin_root_variable(text):
    return "CLAUDE_PLUGIN_ROOT" in text


# INV-12's scan, re-implemented (test_plugin_manifests.py): the variables the hook sources read.
_ENV_READ = re.compile(
    r"""(?:environ\.get\(\s*|environ\[\s*|getenv\(\s*)["'](CLAUDE_[A-Z0-9_]+)["']""")
_ENV_EXCLUDED = {"CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT"}


def env_vars_read_by(sources):
    """CLAUDE_* names read through environ.get / environ[] / getenv in the given source texts."""
    found = set()
    for text in sources:
        found.update(_ENV_READ.findall(text))
    return found - _ENV_EXCLUDED


def parse_registration_key(key):
    """(hook file name, arguments after it) from a registration-key string."""
    m = re.search(r"([\w.-]+\.py)(.*)$", key)
    return (m.group(1), tuple(re.findall(r"--?[\w-]+", m.group(2)))) if m else None


def authored_rows_intact(old_text, new_text, slots):
    """True when each authored slot's row line is present, byte for byte, in the new text."""
    new_lines = new_text.splitlines()
    for line in old_text.splitlines():
        for slot in slots:
            if line.startswith("| `%s` |" % slot) and line not in new_lines:
                return False
    return True


def outside_slot_table(text):
    """The text with the TEMPLATE paragraph and the slot table removed (what must survive)."""
    head, _, rest = text.partition("## Slots")
    _table, _, tail = rest.partition("### A note")
    head = head.split("## What this file is for", 1)[-1]
    return head + "\x00" + tail


def norm(v):
    return v if v == "none" else str(v).replace("\\", "/").strip("/")


def git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")  # ceiling: see Base.setUp
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), check=True, capture_output=True, env=env)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aifi-")).resolve()
        self.addCleanup(rmtree_force, self.tmp)
        self.home = self.tmp / "claudehome"
        self.home.mkdir()
        self.plugin = build_plugin(self.tmp / "plugin")
        self.project = self.tmp / "proj"
        self.project.mkdir()
        fake_user = self.tmp / "fakeuser"
        fake_user.mkdir()
        env = mock.patch.dict(os.environ, {
            "HOME": str(fake_user), "USERPROFILE": str(fake_user),
            "CLAUDE_CONFIG_DIR": str(self.home), "CLAUDE_PLUGIN_ROOT": str(self.plugin),
            # git must never walk above the temp dir into a real repository
            "GIT_CEILING_DIRECTORIES": str(self.tmp)})
        env.start()
        self.addCleanup(env.stop)
        # The suite-wide shutil.which stub RECORDS every name asked for and reports "found" for
        # every name except those in self.which_missing, so a lookup of the WRONG name is visible.
        self.which_calls = []
        self.which_missing = set()
        which = mock.patch("shutil.which", side_effect=self._which)
        self.which = which.start()
        self.addCleanup(which.stop)

    def _which(self, name, *args, **kwargs):
        self.which_calls.append(name)
        return None if name in self.which_missing else str(self.tmp / "launcher.exe")

    def set_template(self, text):
        """Replace the fake plugin's profile template."""
        (self.plugin / ".claude/project-profile.md").write_text(text, encoding="utf-8", newline="")

    # --- assertions ---------------------------------------------------------------
    def need(self, d, key, why=""):
        self.assertIsInstance(d, dict, msg="a result must be a dict (%s)" % why)
        self.assertIn(key, d, msg="result must carry %r (%s); got %r" % (key, why, d))
        return d[key]

    def assertRefused(self, result, code, why):
        self.assertIsInstance(result, dict, msg=why)
        self.assertEqual(result.get("code"), code, msg="refusal code: " + why + "; got %r" % (result,))
        self.assertIn(code, REFUSAL_CODES, msg="the code must belong to the closed set")
        self.assertTrue(str(result.get("message", "")).strip(),
                        msg="a refusal must carry a message naming the reason: " + why)
        expected_exit = 3 if code in ENVIRONMENT_CODES else 2  # literals, never the module's constants
        self.assertEqual(EXIT_CLASS.get(code), expected_exit,
                         msg="exit class of %s must be %d (contract: 3 environment, 2 correctable)"
                             % (code, expected_exit))

    def assertTreeSame(self, before, why, root=None):
        after = snapshot(root or self.tmp)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        self.assertEqual(changed, [], msg="the tree must be byte-identical (%s); changed: %s" % (why, changed))

    # --- fixtures -------------------------------------------------------------------
    def make_files(self, files):
        write_files(self.project, files)

    def put_profile(self, text=None):
        p = self.project / ".claude/project-profile.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if text is not None else template_text(), encoding="utf-8", newline="")
        return p

    def propose(self, files=None, profile=True):
        if files:
            self.make_files(files)
        if profile and not (self.project / ".claude/project-profile.md").exists():
            self.put_profile()
        plan = fi.propose_profile(self.project, claude_home=self.home, plugin_root=self.plugin)
        self.need(plan, "proposals", "ProposeProfile must return a ProfilePlan")
        return plan

    def proposal(self, plan, slot):
        found = [p for p in self.need(plan, "proposals") if p.get("slot") == slot]
        self.assertEqual(len(found), 1, msg="exactly one proposal for slot %s; plan has %r"
                         % (slot, [p.get("slot") for p in plan["proposals"]]))
        return found[0]

    def values(self, plan, slot):
        v = self.need(self.proposal(plan, slot), "values", "SlotProposal.values")
        v = [v] if isinstance(v, str) else list(v)
        return [norm(x) for x in v]

    def preview_profile_sha(self, **kw):
        """The hash a PROFILE apply must present: plan-sha256 of a fresh preview (round three, W3).
        When the preview itself is refused there is no plan hash, so the old input hash stands in
        and the apply is expected to refuse for the same reason."""
        plan = fi.propose_profile(self.project, claude_home=self.home,
                                  plugin_root=kw.get("plugin_root", self.plugin))
        if plan.get("status") == "plan":
            return plan.get("plan-sha256")
        p = self.project / ".claude/project-profile.md"
        return sha_of(p) if p.exists() else "absent"

    def apply_profile(self, sets, sha=None, **kw):
        sha = sha if sha is not None else self.preview_profile_sha(**kw)
        return fi.apply_profile(self.project, sets, sha, claude_home=self.home,
                                plugin_root=kw.get("plugin_root", self.plugin))

    def make_vendored(self, own_hooks_json=None):
        hooks = self.project / ".claude/hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        for name in HOOK_FILES:
            (hooks / name).write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        if own_hooks_json is not None:
            (hooks / "hooks.json").write_text(json.dumps(own_hooks_json), encoding="utf-8")

    def write_record(self, entries, version=2):
        d = self.home / "plugins"
        d.mkdir(parents=True, exist_ok=True)
        (d / "installed_plugins.json").write_text(
            json.dumps({"version": version, "plugins": entries}, indent=2), encoding="utf-8")

    def set_enabled(self, layer, key, value):
        path = {"user": self.home / "settings.json",
                "project": self.project / ".claude/settings.json",
                "local": self.project / ".claude/settings.local.json"}[layer]
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        data.setdefault("enabledPlugins", {})[key] = value
        write_json(path, data)

    def install_plugin(self, scope="user", mkt="auto-improve", version="0.3.0",
                       marketplace_version="0.3.0", enabled=True, install_path=None):
        key = "%s@%s" % (PLUGIN_NAME, mkt)
        entry = {"scope": scope, "installPath": str(install_path or self.plugin), "version": version}
        if scope != "user":
            entry["projectPath"] = str(self.project)
        self.write_record({key: [entry]})
        if enabled is not None:
            self.set_enabled("user", key, enabled)
        clone = self.home / "plugins/marketplaces" / mkt / ".claude-plugin"
        clone.mkdir(parents=True, exist_ok=True)
        (clone / "marketplace.json").write_text(json.dumps(
            {"name": mkt, "plugins": [{"name": PLUGIN_NAME, "version": marketplace_version}]}),
            encoding="utf-8")
        return key

    def mode(self):
        return fi.detect_install_mode(self.project, claude_home=self.home, plugin_root=self.plugin)

    def plan(self, platform="win32", provider="claude", skip=None):
        return fi.plan_hooks(self.project, platform, provider=provider,
                             claude_home=self.home, plugin_root=self.plugin, skip=skip)

    def apply(self, sha, skip=None, platform="win32", provider="claude"):
        return fi.apply_hooks(self.project, sha, skip=skip, platform=platform, provider=provider,
                              claude_home=self.home, plugin_root=self.plugin)

    def preview_sha(self, platform="win32", skip=None):
        """The hash a hooks apply must present: plan-sha256 (round two), computed for the same
        platform and --skip list the apply will use."""
        return self.need(self.plan(platform, skip=skip), "plan-sha256", "the preview must report the plan hash")

    def settings_path(self):
        return self.project / ".claude/settings.json"

    def read_settings(self):
        return json.loads(self.settings_path().read_bytes().decode("utf-8-sig"))

    def apply_to_fresh(self, settings=None, platform="win32", skip=None, **fmt):
        """Vendored project, optional settings.json, a preview, then an apply. Returns (plan, result)."""
        self.make_vendored()
        if settings is not None:
            write_json(self.settings_path(), settings, **fmt)
        plan = self.plan(platform, skip=skip)
        sha = self.need(plan, "plan-sha256", "the preview must report the plan hash")
        return plan, self.apply(sha, skip=skip, platform=platform)

    def cli(self, argv, plugin_root=None):
        """Run main() with the fake home and plugin root; returns (rc, stdout, parsed json or None)."""
        out, err = io.StringIO(), io.StringIO()
        rc = None
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(plugin_root or self.plugin)}):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    rc = fi.main(argv)
                except SystemExit as exc:  # argparse rejection
                    rc = exc.code
        try:
            parsed = json.loads(out.getvalue())
        except ValueError:
            parsed = None
        return rc, out.getvalue(), parsed


# ======================================================================================
# 1. Inference
# ======================================================================================
class TestInference(Base):
    def test_every_template_slot_gets_exactly_one_proposal(self):
        plan = self.propose()
        got = [p.get("slot") for p in self.need(plan, "proposals")]
        self.assertEqual(sorted(got), sorted(SLOTS),
                         msg="one SlotProposal per slot the PLUGIN TEMPLATE declares, none invented")

    def test_an_empty_repository_finds_nothing_and_never_guesses(self):
        plan = self.propose()
        for slot in ("backend.roots", "frontend.roots", "test.roots", "migration.root",
                     "auth.roots", "review.documents"):
            p = self.proposal(plan, slot)
            self.assertEqual(self.values(plan, slot), ["none"], msg="%s: nothing to find means none" % slot)
            self.assertEqual(p.get("basis"), "none-found", msg="%s: an empty repo is none-found" % slot)
        self.assertEqual(self.proposal(plan, "project.name").get("basis"), "needs-answer",
                         msg="no remote and no git: the name must be asked, never guessed from a folder")
        self.assertEqual(self.proposal(plan, "safety-critical.roots").get("basis"), "needs-answer",
                         msg="safety-critical roots are never inferred")

    def test_backend_roots_come_from_manifests(self):
        cases = {
            "src/Api/Api.csproj": "src/Api",
            "services/go-svc/go.mod": "services/go-svc",
            "java/app/pom.xml": "java/app",
            "gradle/app/build.gradle.kts": "gradle/app",
            "rust/core/Cargo.toml": "rust/core",
            "py/svc/pyproject.toml": "py/svc",
            "py2/svc/setup.py": "py2/svc",
        }
        for marker, root in cases.items():
            with self.subTest(marker=marker):
                if (self.project / ".claude").exists():
                    rmtree_force(self.project / ".claude")
                self.project.joinpath(marker).parent.mkdir(parents=True, exist_ok=True)
                plan = self.propose({marker: "<Project/>"})
                self.assertIn(root, self.values(plan, "backend.roots"),
                              msg="%s must make %s a backend root" % (marker, root))
                p = self.proposal(plan, "backend.roots")
                self.assertEqual(p.get("basis"), "inferred", msg="a manifest is evidence enough")
                ev = self.need(p, "evidence", "the citation beside a proposal")
                self.assertTrue(any(norm(e.get("path", "")).startswith(root) for e in ev),
                                msg="the evidence must cite the marker under %s; got %r" % (root, ev))
                for e in ev:
                    self.assertIn(e.get("reason"), EVIDENCE_REASONS, msg="reason is a closed set")
                rmtree_force(self.project / Path(marker).parts[0])

    def test_a_test_project_is_not_a_backend_root_but_is_a_test_root(self):
        plan = self.propose({
            "src/Api/Api.csproj": "<Project/>",
            "src/Api.Tests/Api.Tests.csproj": "<Project/>",
            "src/Core/CoreTests.csproj": "<Project/>",
        })
        self.assertEqual(self.values(plan, "backend.roots"), ["src/Api"],
                         msg="test projects never count as backend roots")
        self.assertEqual(sorted(self.values(plan, "test.roots")), ["src/Api.Tests", "src/Core"],
                         msg="*.Tests.csproj and *Tests.csproj folders are test roots")

    def test_a_dot_test_csproj_folder_is_a_test_project_not_a_backend_root(self):
        plan = self.propose({
            "src/Api/Api.csproj": "<Project/>",
            "src/Foo.Test/Foo.Test.csproj": "<Project/>",
        })
        self.assertEqual(self.values(plan, "backend.roots"), ["src/Api"],
                         msg="Foo.Test.csproj names a test project; its folder is never a backend root")
        self.assertIn("src/Foo.Test", self.values(plan, "test.roots"),
                      msg="and a test project's folder is a test root")

    def test_test_roots_from_named_folders_that_hold_source_and_from_testpaths(self):
        plan = self.propose({
            "tests/test_a.py": "x = 1\n",
            "spec/empty_note.md": "no source here\n",
            "web/__tests__/a.test.ts": "export {}\n",
            "pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["checks"]\n',
            "checks/test_b.py": "x = 2\n",
        })
        got = set(self.values(plan, "test.roots"))
        self.assertTrue({"tests", "web/__tests__", "checks"} <= got,
                        msg="named folders with source and pyproject testpaths are test roots; got %s" % got)
        self.assertNotIn("spec", got, msg="a folder named spec that holds no source file is not a test root")

    def test_a_root_level_pyproject_does_not_make_the_repository_a_backend_root(self):
        plan = self.propose({"pyproject.toml": "[project]\nname='x'\n", "README.md": "x"})
        self.assertEqual(self.values(plan, "backend.roots"), ["none"],
                         msg="a pyproject at the repository root would make the whole repo a backend root")
        self.assertEqual(self.proposal(plan, "backend.roots").get("basis"), "none-found",
                         msg="the dropped rule stays dropped")

    def test_an_express_dependency_does_not_make_a_backend_root(self):
        plan = self.propose({"web/package.json": json.dumps({"dependencies": {"express": "4.0.0"}})})
        self.assertEqual(self.values(plan, "backend.roots"), ["none"],
                         msg="a server-rendered front end carries express too; the rule was dropped")
        self.assertEqual(self.proposal(plan, "backend.roots").get("basis"), "none-found",
                         msg="express alone is no evidence")

    def test_frontend_roots_from_angular_json_and_bundler_configs(self):
        plan = self.propose({
            "angular.json": json.dumps({"projects": {"app": {"root": "projects/app"},
                                                     "lib": {"root": "projects/lib"}}}),
            "projects/app/src/main.ts": "export {}\n",
            "web/vite.config.ts": "export default {}\n",
            "site/next.config.js": "module.exports = {}\n",
            "docs/nuxt.config.ts": "export default {}\n",
            "ui/svelte.config.js": "export default {}\n",
        })
        self.assertEqual(sorted(self.values(plan, "frontend.roots")),
                         ["docs", "projects/app", "projects/lib", "site", "ui", "web"],
                         msg="angular.json projects.*.root and each bundler config folder are frontend roots")
        ev = self.proposal(plan, "frontend.roots").get("evidence", [])
        self.assertTrue(any(e.get("reason") == "config-entry" for e in ev),
                        msg="an angular.json entry is cited as config-entry; got %r" % ev)

    def test_theme_polarity_is_never_inferred(self):
        plan = self.propose({"web/vite.config.ts": "x"})
        p = self.proposal(plan, "frontend.theme-polarity")
        self.assertEqual(p.get("basis"), "needs-answer", msg="polarity cannot be read from a repository")
        self.assertIn("web", json.dumps(p), msg="the question is asked per frontend root")

    def test_theme_polarity_is_none_when_there_is_no_frontend(self):
        plan = self.propose()
        self.assertEqual(self.values(plan, "frontend.theme-polarity"), ["none"],
                         msg="no frontend root means no polarity to ask")

    def test_migration_root_single_candidates(self):
        cases = {
            "src/Data/Migrations/001_Init.cs": "src/Data/Migrations",
            "alembic/versions/a1.py": "alembic/versions",
            "prisma/migrations/20240101/migration.sql": "prisma/migrations",
            "db/migrate/1_create.rb": "db/migrate",
            "src/main/resources/db/migration/V1__init.sql": "src/main/resources/db/migration",
            "web/manage.py": None,
        }
        for marker, root in cases.items():
            if root is None:
                continue
            with self.subTest(marker=marker):
                if (self.project / ".claude").exists():
                    rmtree_force(self.project / ".claude")
                plan = self.propose({marker: "x"})
                self.assertEqual(self.values(plan, "migration.root"), [root],
                                 msg="%s identifies the migration root %s" % (marker, root))
                self.assertEqual(self.proposal(plan, "migration.root").get("basis"), "inferred",
                                 msg="a single candidate is inferred")
                rmtree_force(self.project / Path(marker).parts[0])

    def test_django_migrations_beside_manage_py(self):
        plan = self.propose({"web/manage.py": "x", "web/migrations/0001_initial.py": "x"})
        self.assertEqual(self.values(plan, "migration.root"), ["web/migrations"],
                         msg="a migrations folder beside a Django manage.py is the migration root")

    def test_several_migration_candidates_are_asked_not_picked(self):
        plan = self.propose({"src/Data/Migrations/001.cs": "x", "alembic/versions/a1.py": "x"})
        p = self.proposal(plan, "migration.root")
        self.assertEqual(p.get("basis"), "needs-answer", msg="two candidates: the operator chooses")
        self.assertTrue({"src/Data/Migrations", "alembic/versions"} <= set(self.values(plan, "migration.root")),
                        msg="both candidates must be listed")

    def test_an_empty_migrations_folder_is_not_a_migration_root(self):
        plan = self.propose({"src/Data/Migrations/notes.md": "no cs here"})
        self.assertEqual(self.values(plan, "migration.root"), ["none"],
                         msg="a Migrations folder holding no *.cs is not evidence")

    def test_auth_folders_are_candidates_never_inferred(self):
        plan = self.propose({"src/Auth/Login.cs": "x", "src/Identity/User.cs": "x", "src/Billing/Pay.cs": "x"})
        p = self.proposal(plan, "auth.roots")
        self.assertEqual(p.get("basis"), "needs-answer",
                         msg="a folder name is a guess; it is offered, never inferred")
        self.assertTrue({"src/Auth", "src/Identity"} <= set(self.values(plan, "auth.roots")),
                        msg="the candidates are listed for the operator")
        self.assertNotIn("src/Billing", self.values(plan, "auth.roots"), msg="only auth-named folders")

    def test_review_documents_are_the_root_files_that_exist(self):
        plan = self.propose({"CLAUDE.md": "x", "CONTRIBUTING.md": "x", "TESTING_STANDARDS.md": "x",
                             "ARCHITECTURE.md": "x", "README.md": "x"})
        self.assertEqual(sorted(self.values(plan, "review.documents")),
                         ["ARCHITECTURE.md", "CLAUDE.md", "CONTRIBUTING.md", "TESTING_STANDARDS.md"],
                         msg="CLAUDE/AGENTS/CONTRIBUTING/TESTING*/ARCHITECTURE only; README is not listed")

    def test_roles_accept_the_plugin_set_when_no_local_agent_exists(self):
        plan = self.propose()
        self.assertEqual(self.values(plan, "implementers"), ["none"], msg="accept the plugin's own")
        self.assertEqual(self.values(plan, "review-gates"), ["none"], msg="accept the plugin's own")
        self.assertEqual(plan.get("local-agents"), [], msg="no agent outside the plugin set exists")

    def test_a_local_agent_is_asked_about_and_plugin_defaults_stay_in_the_proposal(self):
        self.make_files({".claude/agents/acme-dev.md": "# a\n",
                         ".claude/agents/senior-test-engineer.md": "# same name as a plugin agent\n"})
        plan = self.propose()
        self.assertEqual(plan.get("local-agents"), ["acme-dev"],
                         msg="only agents absent from the plugin set are local")
        for slot, defaults in (("implementers", DEFAULT_IMPLEMENTERS), ("review-gates", DEFAULT_REVIEW_GATES)):
            p = self.proposal(plan, slot)
            self.assertEqual(p.get("basis"), "needs-answer", msg="%s: a local agent has no role yet" % slot)
            self.assertTrue(set(defaults) <= set(self.values(plan, slot)),
                            msg="%s: filling a role slot REPLACES the defaults, so the proposal keeps them" % slot)

    def test_project_name_from_the_origin_remote(self):
        urls = ("https://github.com/acme/widget-shop.git", "git@github.com:acme/widget-shop.git",
                "https://github.com/acme/widget-shop")
        for index, url in enumerate(urls):
            with self.subTest(url=url):
                repo = self.tmp / ("r%d" % index)
                repo.mkdir()
                git(repo, "init")
                git(repo, "remote", "add", "origin", url)
                self.project = repo
                plan = self.propose()
                self.assertEqual(self.values(plan, "project.name"), ["widget-shop"],
                                 msg="the repository name comes from the origin URL")
                p = self.proposal(plan, "project.name")
                self.assertEqual(p.get("basis"), "inferred", msg="a remote is evidence")
                self.assertTrue(any(e.get("reason") == "git-remote" for e in p.get("evidence", [])),
                                msg="the citation is git-remote")

    def test_worktree_folder_name_is_never_the_project_name(self):
        main = self.tmp / "widget-main"
        main.mkdir()
        git(main, "init")
        git(main, "commit", "--allow-empty", "-m", "x")
        wt = self.tmp / "20261004-feature-add-thing"
        git(main, "worktree", "add", str(wt), "-b", "feature-x")
        self.project = wt
        plan = self.propose()
        self.assertEqual(self.values(plan, "project.name"), ["widget-main"],
                         msg="the main checkout's folder is read through the git common directory")
        self.assertNotIn("20261004-feature-add-thing", json.dumps(plan.get("proposals")),
                         msg="a worktree folder name must never appear as the project name")
        self.assertTrue(any(e.get("reason") == "folder-name"
                            for e in self.proposal(plan, "project.name").get("evidence", [])),
                        msg="the main checkout's folder name is cited as folder-name")

    def test_a_dated_folder_outside_git_is_not_used_as_the_project_name(self):
        dated = self.tmp / "20261004-feature-add-thing"
        dated.mkdir()
        self.project = dated
        plan = self.propose()
        self.assertEqual(self.proposal(plan, "project.name").get("basis"), "needs-answer",
                         msg="with no remote and no git, the name is asked")
        self.assertNotIn("20261004-feature", json.dumps(self.proposal(plan, "project.name")),
                         msg="a worktree-style folder name is not a project name")

    def test_excluded_folders_are_skipped(self):
        files = {"src/Real/Real.csproj": "<Project/>"}
        for d in (".git", ".claude", "node_modules", "bin", "obj", "dist", "build", "vendor",
                  "venv", ".venv", "__pycache__"):
            files["%s/svc/go.mod" % d] = "module x\n"
            files["%s/Lib.csproj" % d] = "<Project/>"
        plan = self.propose(files)
        self.assertEqual(self.values(plan, "backend.roots"), ["src/Real"],
                         msg="markers under excluded folders must be ignored, the real one found")

    def test_the_walk_stops_at_depth_six(self):
        # ASSUMPTION: depth is the number of folder levels between the project root and the
        # folder that holds the marker. Six levels down is found; seven is not.
        plan = self.propose({"a/b/c/d/e/f/go.mod": "x", "m/n/o/p/q/r/s/go.mod": "x"})
        self.assertEqual(self.values(plan, "backend.roots"), ["a/b/c/d/e/f"],
                         msg="a marker in a folder six levels down is found; the one seven levels "
                             "down (m/n/o/p/q/r/s) is beyond the walk's depth limit of 6")

    def test_two_runs_give_identical_output_and_write_nothing(self):
        self.propose({"z/Z.csproj": "x", "a/A.csproj": "x", "m/go.mod": "x", "CLAUDE.md": "x",
                      "src/Auth/a.cs": "x", "src/Identity/b.cs": "x"})
        before = snapshot(self.tmp)
        first = fi.propose_profile(self.project, claude_home=self.home, plugin_root=self.plugin)
        second = fi.propose_profile(self.project, claude_home=self.home, plugin_root=self.plugin)
        self.need(first, "proposals")
        self.assertEqual(first, second, msg="the output is sorted so two runs agree")
        self.assertEqual(self.values(first, "backend.roots"), sorted(self.values(first, "backend.roots")),
                         msg="roots are listed in sorted order")
        self.assertTreeSame(before, "ProposeProfile never writes")

    def test_the_plan_reports_hash_target_and_diff(self):
        self.make_files({"src/Api/Api.csproj": "x"})
        p = self.put_profile()
        plan = self.propose()
        self.assertEqual(plan.get("source-sha256"), sha_of(p), msg="the hash is of the bytes the preview read")
        self.assertIs(plan.get("existed"), True, msg="the profile existed")
        self.assertEqual(Path(self.need(plan, "target")), p, msg="the target is the project's profile")
        self.assertIn("backend.roots", self.need(plan, "unified-diff"), msg="the diff shows what would be filled")
        self.assertEqual(sorted(self.need(plan, "rows-to-fill")), sorted(SLOTS),
                         msg="every slot is still a placeholder")

    def test_no_profile_yet_is_reported_as_absent(self):
        plan = self.propose(profile=False)
        self.assertIs(plan.get("existed"), False, msg="there is no profile to read")
        self.assertEqual(plan.get("source-sha256"), "absent", msg="an absent file has no hash")

    def test_an_authored_slot_is_kept_and_the_difference_is_advice_only(self):
        self.put_profile(template_text({"backend.roots": "`src/Other`"}))
        plan = self.propose({"src/Api/Api.csproj": "x"})
        p = self.proposal(plan, "backend.roots")
        self.assertEqual(p.get("basis"), "kept-authored", msg="an authored slot is never proposed over")
        self.assertEqual(self.values(plan, "backend.roots"), ["src/Other"], msg="the authored value is shown")
        self.assertIn("src/Api", str(p.get("note")), msg="the differing inference is advice, in the note")
        self.assertNotIn("backend.roots", plan.get("rows-to-fill"), msg="an authored row is not filled")

    def test_a_missing_row_is_listed_for_adding(self):
        self.put_profile(template_text(drop=("review-gates",)))
        plan = self.propose()
        self.assertEqual(plan.get("rows-to-add"), ["review-gates"],
                         msg="slot names come from the plugin template, so a missing row is detected")

    def test_a_hard_override_naming_the_project_is_never_the_template_source(self):
        self.put_profile(template_text(drop=("review-gates",)))
        plan = fi.propose_profile(self.project, claude_home=self.home, plugin_root=self.project)
        self.need(plan, "proposals", "the project's own table is used when no separate plugin root exists")
        self.assertEqual(plan.get("missing-row-detection"), "unavailable",
                         msg="with the project as its own template, a missing row cannot be detected")
        self.assertEqual(plan.get("rows-to-add"), [], msg="nothing can be claimed missing")

    # --- the real wrapper path: a VENDORED consumer runs its own copy of the script ----------
    # Under a vendored install the script lives in <project>/.claude/scripts, so
    # plugin_doctor.find_plugin_root()'s first candidate (the script's own grandparent) IS the
    # project. The test runs a real copy of the scripts inside a temp project, with
    # CLAUDE_PLUGIN_ROOT removed and no plugin_root argument, so that candidate is the only one
    # and the wrapper must reject it. (In-process the script's own folder is the real worktree,
    # which is a SEPARATE plugin root carrying the manifest and would be legitimately accepted,
    # so only a vendored copy exercises the "project itself" rule through the real lookup.)
    def vendored_copy(self):
        proj = self.tmp / "vendored-proj"
        scripts = proj / ".claude/scripts"
        scripts.mkdir(parents=True)
        for src in (SCRIPT_ROOT / ".claude/scripts").glob("*.py"):
            shutil.copy2(src, scripts / src.name)
        (proj / ".claude/templates").mkdir()
        (proj / ".claude/templates/concept-contract.md").write_text("# Concept Contract\n", encoding="utf-8")
        (proj / ".claude/project-profile.md").write_text(
            template_text(drop=("review-gates",)), encoding="utf-8", newline="")
        return proj

    def run_copy(self, proj, *args):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        return subprocess.run([sys.executable, str(proj / ".claude/scripts") + os.sep + args[0], *args[1:]],
                              capture_output=True, text=True, env=env, timeout=120)

    def test_a_vendored_copy_resolves_its_own_project_as_the_root_positive_control(self):
        proj = self.vendored_copy()
        probe = ("import sys; sys.path.insert(0, %r); import plugin_doctor; "
                 "print(plugin_doctor.find_plugin_root())" % str(proj / ".claude/scripts"))
        r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                           env={k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}, timeout=120)
        self.assertEqual(Path(r.stdout.strip()).resolve(), proj.resolve(),
                         msg="POSITIVE CONTROL: with no env and no explicit root the lookup returns the "
                             "vendored project itself, so the test below really exercises the rule; stderr %r"
                             % r.stderr)

    def test_the_project_itself_is_never_the_template_source(self):
        proj = self.vendored_copy()
        before = snapshot(proj)
        r = self.run_copy(proj, "auto_improve_finish_install.py", "profile", "--project", str(proj),
                          "--json", "--claude-home", str(self.home))
        try:
            plan = json.loads(r.stdout)
        except ValueError:
            plan = None
        self.assertIsNotNone(plan, msg="the script must print a ProfilePlan; stdout %r stderr %r"
                                       % (r.stdout, r.stderr))
        self.assertEqual(r.returncode, 0, msg="a plan is exit 0")
        self.assertEqual(plan.get("missing-row-detection"), "unavailable",
                         msg="the project is its own only template: a missing row cannot be detected")
        self.assertEqual(plan.get("rows-to-add"), [], msg="so nothing can be claimed missing")
        self.assertEqual(sorted(p.get("slot") for p in plan.get("proposals", [])),
                         sorted(s for s in SLOTS if s != "review-gates"),
                         msg="slot names then come from the project's own table (which lacks review-gates)")
        self.assertEqual(snapshot(proj), before, msg="a plan writes nothing")

    # --- B1: slot names are READ FROM THE TEMPLATE -------------------------------------------
    def test_a_twelfth_template_slot_is_proposed_and_can_be_set(self):
        self.set_template(template_text(extra={EXTRA_SLOT: EXTRA_PLACEHOLDER}))
        p = self.put_profile()  # the project still has the standard eleven rows
        plan = self.propose()
        self.assertEqual(sorted(x.get("slot") for x in self.need(plan, "proposals")),
                         sorted(SLOTS + (EXTRA_SLOT,)),
                         msg="one proposal per slot the TEMPLATE declares, including the twelfth")
        self.assertIn(self.proposal(plan, EXTRA_SLOT).get("basis"),
                      ("inferred", "needs-answer", "kept-authored", "none-found"),
                      msg="the new slot's proposal carries a basis from the closed set")
        self.assertIn(EXTRA_SLOT, plan.get("rows-to-add", []),
                      msg="the project's profile lacks the new row, so it is listed for adding")
        before = snapshot(self.tmp)
        unanswered = self.apply_profile(dict(FULL_ANSWERS))
        self.assertRefused(unanswered, "slot-unanswered", "the twelfth slot is a placeholder nobody answered")
        self.assertIn(EXTRA_SLOT, unanswered.get("message", ""), msg="the message names the slot")
        self.assertTreeSame(before, "a refusal writes nothing")
        sets = dict(FULL_ANSWERS)
        sets[EXTRA_SLOT] = "docs/runbooks"
        result = self.apply_profile(sets)
        self.assertEqual(result.get("status"), "applied",
                         msg="--set on the template's twelfth slot is accepted; got %r" % result)
        self.assertEqual(load_slot(p.read_text(encoding="utf-8"), EXTRA_SLOT), ("docs/runbooks",),
                         msg="the new row was written and re-reads through load_slot")

    def test_a_slot_removed_from_the_template_is_not_proposed_and_set_is_refused(self):
        self.set_template(template_text(drop=("auth.roots",)))
        self.put_profile()  # the project's profile still carries an auth.roots placeholder row
        plan = self.propose()
        self.assertEqual(sorted(x.get("slot") for x in self.need(plan, "proposals")),
                         sorted(s for s in SLOTS if s != "auth.roots"),
                         msg="proposals follow the TEMPLATE: the removed slot is gone")
        before = snapshot(self.tmp)
        result = self.apply_profile(dict(FULL_ANSWERS))  # carries an auth.roots answer
        self.assertRefused(result, "unknown-slot", "the template no longer declares auth.roots")
        self.assertIn("auth.roots", result.get("message", ""), msg="the message names the slot")
        self.assertTreeSame(before, "a refusal writes nothing, so the profile is untouched")


# ======================================================================================
# 1b. A vendored consumer reaches the plugin's own sources (round-two blocker B1)
# ======================================================================================
# The sync never delivers .claude/hooks/hooks.json to a consumer, and the consumer's own copy of
# the scripts makes plugin_doctor.find_plugin_root()'s FIRST candidate the project itself. After
# rejecting the project the lookup must fall through to CLAUDE_PLUGIN_ROOT, then to the provider
# cache under the Claude home. Each case runs a REAL COPY of the scripts inside a temp project, in
# a subprocess, with HOME and the Claude home redirected into the temp tree.
class TestVendoredConsumerReachesThePluginSources(Base):
    def consumer(self, with_profile_row_dropped=True):
        proj = self.tmp / "consumer"
        scripts = proj / ".claude/scripts"
        scripts.mkdir(parents=True)
        for src in (SCRIPT_ROOT / ".claude/scripts").glob("*.py"):
            shutil.copy2(src, scripts / src.name)
        (proj / ".claude/templates").mkdir()
        (proj / ".claude/templates/concept-contract.md").write_text("# Concept Contract\n", encoding="utf-8")
        hooks = proj / ".claude/hooks"
        hooks.mkdir()
        for name in HOOK_FILES:  # the vendored copy; NO hooks.json (the sync never delivers it)
            (hooks / name).write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (proj / ".claude/project-profile.md").write_text(
            template_text(drop=("review-gates",) if with_profile_row_dropped else ()),
            encoding="utf-8", newline="")
        return proj

    def cache_home(self):
        """A Claude home (= <fake user home>/.claude, so the cache glob agrees whichever way the
        script locates it) holding the fake plugin in its provider cache."""
        home = Path(os.environ["USERPROFILE"]) / ".claude"
        build_plugin(home / "plugins/cache/mkt/agentic-auto-improve/0.3.0")
        return home

    def run_script(self, proj, argv, home, plugin_root=None):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        env.update({"CLAUDE_CONFIG_DIR": str(home), "PYTHONDONTWRITEBYTECODE": "1"})
        if plugin_root is not None:
            env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
        r = subprocess.run(
            [sys.executable, str(proj / ".claude/scripts/auto_improve_finish_install.py")] + argv
            + ["--project", str(proj), "--json", "--claude-home", str(home)],
            capture_output=True, text=True, env=env, timeout=120)
        try:
            parsed = json.loads(r.stdout)
        except ValueError:
            parsed = None
        return r, parsed

    def assert_hooks_plan(self, r, parsed):
        self.assertIsNotNone(parsed, msg="the script must print JSON; stdout %r stderr %r" % (r.stdout, r.stderr))
        self.assertNotEqual(parsed.get("code"), "hooks-json-missing",
                            msg="the sync never delivers hooks.json, so the plugin's must be found: %r" % parsed)
        self.assertEqual(parsed.get("status"), "plan", msg="a plan, not a refusal; got %r" % parsed)
        self.assertEqual(len(parsed.get("to-add", [])), 17,
                         msg="all 17 registrations of the PLUGIN's hooks.json are to be added")
        self.assertEqual(r.returncode, 0, msg="a plan is exit 0; stderr %r" % r.stderr)

    def test_hooks_found_in_the_provider_cache_when_the_project_has_no_hooks_json(self):
        proj = self.consumer()
        home = self.cache_home()
        before = snapshot(proj)
        r, parsed = self.run_script(proj, ["hooks", "--platform", "win32"], home)
        self.assert_hooks_plan(r, parsed)
        self.assertEqual(snapshot(proj), before, msg="a plan writes nothing")

    def test_hooks_found_through_claude_plugin_root_when_the_project_has_no_hooks_json(self):
        proj = self.consumer()
        r, parsed = self.run_script(proj, ["hooks", "--platform", "win32"], self.home, plugin_root=self.plugin)
        self.assert_hooks_plan(r, parsed)

    def test_a_plugin_root_variable_naming_no_plugin_falls_through_to_the_cache(self):
        proj = self.consumer()
        home = self.cache_home()
        empty = self.tmp / "not-a-plugin"
        empty.mkdir()
        r, parsed = self.run_script(proj, ["hooks", "--platform", "win32"], home, plugin_root=empty)
        self.assert_hooks_plan(r, parsed)

    def assert_profile_plan(self, r, parsed):
        self.assertIsNotNone(parsed, msg="the script must print JSON; stdout %r stderr %r" % (r.stdout, r.stderr))
        self.assertEqual(parsed.get("status"), "plan", msg="a plan; got %r" % parsed)
        self.assertEqual(parsed.get("missing-row-detection"), "available",
                         msg="the template is found through the lookup, so a missing row CAN be detected")
        self.assertEqual(parsed.get("rows-to-add"), ["review-gates"],
                         msg="the project's table lacks review-gates, which the plugin template declares")

    def test_profile_template_found_in_the_provider_cache(self):
        proj = self.consumer()
        home = self.cache_home()
        r, parsed = self.run_script(proj, ["profile"], home)
        self.assert_profile_plan(r, parsed)

    def test_profile_template_found_through_claude_plugin_root(self):
        proj = self.consumer()
        r, parsed = self.run_script(proj, ["profile"], self.home, plugin_root=self.plugin)
        self.assert_profile_plan(r, parsed)


# ======================================================================================
# 2. Profile apply
# ======================================================================================
FULL_ANSWERS = {
    "project.name": "widget", "backend.roots": "src/Api", "frontend.roots": "web",
    "frontend.theme-polarity": "web=dark", "test.roots": "src/Api.Tests",
    "migration.root": "src/Api/Migrations", "auth.roots": "none", "safety-critical.roots": "none",
    "review.documents": "CLAUDE.md,README.md", "implementers": "none", "review-gates": "none",
}


class TestProfileApply(Base):
    def full(self, **over):
        d = dict(FULL_ANSWERS)
        d.update(over)
        return d

    def test_placeholder_rows_are_filled_and_read_back_through_load_slot(self):
        p = self.put_profile()
        result = self.apply_profile(self.full())
        self.assertEqual(result.get("status"), "applied", msg="a full set of answers applies; got %r" % result)
        text = p.read_text(encoding="utf-8")
        expect = {"project.name": ("widget",), "backend.roots": ("src/Api",), "frontend.roots": ("web",),
                  "frontend.theme-polarity": ("web=dark",), "test.roots": ("src/Api.Tests",),
                  "migration.root": ("src/Api/Migrations",), "auth.roots": (), "safety-critical.roots": (),
                  "review.documents": ("CLAUDE.md", "README.md"), "implementers": (), "review-gates": ()}
        for slot, want in expect.items():
            self.assertEqual(load_slot(text, slot), want,
                             msg="%s must re-read through pr_merged.load_slot to the confirmed value" % slot)
        self.assertEqual(load_implementers(text), DEFAULT_IMPLEMENTERS,
                         msg="a role slot written as none keeps the plugin defaults")

    def test_written_form_is_a_backticked_list_or_the_word_none(self):
        p = self.put_profile()
        self.apply_profile(self.full(**{"backend.roots": "src/Api,src/Web", "auth.roots": "none"}))
        text = p.read_text(encoding="utf-8")
        row = re.search(r"^\| `backend\.roots` \|\s*(.*?)\s*\|\s*$", text, re.M)
        self.assertIsNotNone(row, msg="the backend.roots row must still exist")
        self.assertEqual(re.sub(r"\s*,\s*", ",", row.group(1)), "`src/Api`,`src/Web`",
                         msg="backticked entries separated by commas (spacing around the comma is free)")
        none_row = re.search(r"^\| `auth\.roots` \|\s*(.*?)\s*\|\s*$", text, re.M)
        self.assertEqual(none_row.group(1) if none_row else None, "none", msg="an empty slot is the word none")

    def test_theme_polarity_is_written_one_entry_per_root(self):
        p = self.put_profile()
        self.apply_profile(self.full(**{"frontend.roots": "web,admin",
                                        "frontend.theme-polarity": "web=dark,admin=light"}))
        self.assertEqual(load_slot(p.read_text(encoding="utf-8"), "frontend.theme-polarity"),
                         ("web=dark", "admin=light"),
                         msg="<root>=<polarity> entries survive load_slot's flat list")

    def test_authored_rows_are_kept_byte_for_byte(self):
        authored = {"backend.roots": "   `src/Other` ,   `src/More`   ", "test.roots": "none"}
        old = template_text(authored).replace("| `backend.roots` |", "|  `backend.roots`  |")
        p = self.put_profile(old)
        sets = {k: v for k, v in self.full().items() if k not in authored}
        result = self.apply_profile(sets)
        self.assertEqual(result.get("status"), "applied", msg="only placeholders are answered; got %r" % result)
        new = p.read_text(encoding="utf-8")
        self.assertTrue(authored_rows_intact(old, new, list(authored)),
                        msg="the authored rows must survive byte for byte")
        self.assertEqual(load_slot(new, "project.name"), ("widget",),
                         msg="the placeholder rows were filled, so the apply did run")

    def test_the_byte_comparison_catches_a_hand_edited_authored_row_positive_control(self):
        old = template_text({"backend.roots": "`src/Other`"})
        edited = old.replace("| `backend.roots` | `src/Other` |", "| `backend.roots` | `src/Other`  |")
        self.assertNotEqual(old, edited, msg="the control must really edit the row")
        self.assertTrue(authored_rows_intact(old, old, ["backend.roots"]), msg="unchanged text passes")
        self.assertFalse(authored_rows_intact(old, edited, ["backend.roots"]),
                         msg="POSITIVE CONTROL: a one-space edit to an authored row must be caught")

    def test_text_outside_the_slot_table_is_untouched_and_provenance_replaces_the_template_paragraph(self):
        old = template_text()
        p = self.put_profile(old)
        self.assertEqual(self.apply_profile(self.full()).get("status"), "applied", msg="the apply must run")
        new = p.read_text(encoding="utf-8")
        self.assertEqual(outside_slot_table(new), outside_slot_table(old),
                         msg="everything outside the slot table survives")
        self.assertNotIn("**TEMPLATE.**", new, msg="the template paragraph is replaced")
        self.assertNotIn("Copy this file to", new, msg="the whole paragraph is replaced, not only its marker")
        lead = new.split("## What this file is for")[0]
        self.assertIn("auto-improve-finish-install", lead,
                      msg="one provenance line, naming the skill, takes the paragraph's place")

    def test_a_missing_row_is_appended_to_the_table(self):
        old = template_text(drop=("review-gates",))
        p = self.put_profile(old)
        sets = self.full(**{"review-gates": "plug-agent-a"})
        result = self.apply_profile(sets)
        self.assertEqual(result.get("status"), "applied", msg="got %r" % result)
        new = p.read_text(encoding="utf-8")
        rows = re.findall(r"^\| `review-gates` \|.*\|$", new, re.M)
        self.assertEqual(len(rows), 1,
                         msg="exactly one review-gates row after the apply")
        self.assertEqual(load_slot(new, "review-gates"), ("plug-agent-a",), msg="the new row holds the answer")
        self.assertLess(new.index("| `review-gates` |"), new.index("### A note"),
                        msg="the row joins the table, not the text after it")

    def test_a_role_slot_with_a_valid_agent_from_each_source_is_accepted(self):
        self.make_files({".claude/agents/acme-dev.md": "# a\n"})
        for agent in ("acme-dev", "plug-agent-a", "plug-agent-b"):
            with self.subTest(agent=agent):
                p = self.put_profile()
                value = ",".join(list(DEFAULT_IMPLEMENTERS) + [agent])
                result = self.apply_profile(self.full(implementers=value))
                self.assertEqual(result.get("status"), "applied",
                                 msg="%s exists in the project or plugin agents; got %r" % (agent, result))
                self.assertEqual(load_implementers(p.read_text(encoding="utf-8")),
                                 tuple(DEFAULT_IMPLEMENTERS) + (agent,),
                                 msg="the plugin defaults and the new agent are all written")

    def _refuse(self, text, sets, code, why, sha=None):
        p = self.put_profile(text)
        before = snapshot(self.tmp)
        result = self.apply_profile(sets, sha=sha)
        self.assertRefused(result, code, why)
        self.assertTreeSame(before, why)
        return result

    def test_unknown_agent_is_refused_before_anything_is_written(self):
        result = self._refuse(None, self.full(implementers="ghost-agent"), "unknown-agent",
                              "ghost-agent.md exists nowhere")
        self.assertIn("ghost-agent", result.get("message", ""), msg="the message names the agent")

    def test_unknown_agent_in_review_gates_is_refused(self):
        self._refuse(None, self.full(**{"review-gates": "ghost-agent"}), "unknown-agent",
                     "a review gate must exist too")

    def test_unknown_slot_is_refused(self):
        self._refuse(None, self.full(**{"bogus.slot": "x"}), "unknown-slot", "the template declares no such slot")

    def test_an_unanswered_placeholder_is_refused(self):
        sets = self.full()
        del sets["migration.root"]
        result = self._refuse(None, sets, "slot-unanswered", "migration.root was left without an answer")
        self.assertIn("migration.root", result.get("message", ""), msg="the message names the slot")

    def test_setting_an_authored_slot_is_refused(self):
        text = template_text({"backend.roots": "`src/Other`"})
        self._refuse(text, self.full(), "slot-already-authored", "backend.roots is authored")

    def test_a_slot_reading_none_is_authored_too(self):
        text = template_text({"auth.roots": "none"})
        self._refuse(text, self.full(**{"auth.roots": "src/Auth"}), "slot-already-authored",
                     "a deliberate none is an authored value")

    def test_a_changed_profile_is_refused_on_the_profile_apply(self):
        p = self.put_profile()
        stale = self.preview_profile_sha()  # plan-sha256, not source-sha256 (round three, W3)
        p.write_text(p.read_text(encoding="utf-8") + "\nAdded by someone.\n", encoding="utf-8")
        before = snapshot(self.tmp)
        result = self.apply_profile(self.full(), sha=stale)
        self.assertRefused(result, "changed-since-preview", "the profile changed after the preview")
        self.assertTreeSame(before, "a stale preview must not be applied")

    def test_a_failed_rename_is_write_failed_and_leaves_the_tree_untouched(self):
        self.put_profile()
        before = snapshot(self.tmp)
        with mock.patch("os.replace", side_effect=PermissionError("locked")):
            result = self.apply_profile(self.full())
        self.assertRefused(result, "write-failed", "the atomic rename failed")
        self.assertTreeSame(before, "the temporary file is removed and the original is untouched")

    def test_a_second_apply_has_nothing_to_do_and_changes_nothing(self):
        p = self.put_profile()
        self.assertEqual(self.apply_profile(self.full()).get("status"), "applied", msg="the first apply writes")
        bytes_after, mtime = p.read_bytes(), p.stat().st_mtime_ns
        before = snapshot(self.tmp)
        result = self.apply_profile({})
        self.assertEqual(result.get("status"), "nothing-to-do", msg="no placeholder is left")
        self.assertEqual(p.read_bytes(), bytes_after, msg="the file is not rewritten")
        self.assertEqual(p.stat().st_mtime_ns, mtime, msg="not even touched")
        self.assertTreeSame(before, "an idempotent re-run")

    # --- round two: W1 invalid values, W2 exact-case agents, M21 absent profile, CRLF ----------------
    def test_set_values_with_a_newline_a_pipe_or_a_backtick_are_refused(self):
        self.assertIn("invalid-slot-value", REFUSAL_CODES,
                      msg="the closed refusal set must list invalid-slot-value")
        for label, bad in (("newline", "src/Api\n| `auth.roots` | injected |"), ("pipe", "src/A|B"),
                           ("backtick", "src/`x`")):
            with self.subTest(value=label):
                p = self.put_profile()
                before = snapshot(self.tmp)
                result = self.apply_profile(self.full(**{"backend.roots": bad}))
                self.assertIsInstance(result, dict, msg="a refusal dict")
                self.assertEqual(result.get("code"), "invalid-slot-value",
                                 msg="a %s would break the table row or the backticked-list form; got %r"
                                     % (label, result))
                self.assertRefused(result, "invalid-slot-value", "a value that cannot be written as one table cell")
                self.assertIn("backend.roots", result.get("message", ""), msg="the message names the slot")
                self.assertTreeSame(before, "nothing is written")
                self.assertEqual(p.read_text(encoding="utf-8"), template_text(), msg="the profile is untouched")

    def test_agent_names_are_matched_with_exact_case(self):
        # On a case-insensitive file system Path.is_file() says yes to the wrong case, so the
        # script itself must compare the name exactly.
        self.make_files({".claude/agents/acme-dev.md": "# a\n"})
        for label, wrong in (("a plugin agent", "Python-AI-Developer"), ("a project agent", "Acme-Dev"),
                             ("a plugin agent, upper case", "SENIOR-TEST-ENGINEER")):
            with self.subTest(agent=label):
                self.put_profile()
                before = snapshot(self.tmp)
                result = self.apply_profile(self.full(implementers=wrong))
                self.assertRefused(result, "unknown-agent",
                                   "%s is not the name of any agent file, only its case differs" % wrong)
                self.assertIn(wrong, result.get("message", ""), msg="the message names the agent")
                self.assertTreeSame(before, "nothing is written")
        self.put_profile()
        ok = self.apply_profile(self.full(implementers="python-ai-developer,acme-dev"))
        self.assertEqual(ok.get("status"), "applied",
                         msg="POSITIVE CONTROL: the exact-case names are accepted; got %r" % ok)

    def test_an_absent_profile_starts_from_the_plugin_template_and_keeps_its_text(self):
        p = self.project / ".claude/project-profile.md"
        self.assertFalse(p.exists(), msg="fixture sanity: no profile yet")
        result = self.apply_profile(self.full(), sha=self.preview_profile_sha())  # plan-sha256 of the absent preview
        self.assertEqual(result.get("status"), "applied", msg="an absent profile is created; got %r" % result)
        self.assertTrue(p.is_file(), msg="the profile now exists")
        new = p.read_text(encoding="utf-8")
        self.assertEqual(outside_slot_table(new), outside_slot_table(template_text()),
                         msg="everything outside the slot table comes from the plugin template, unchanged")
        self.assertNotIn("**TEMPLATE.**", new, msg="the template paragraph is replaced by the provenance line")
        self.assertIn("auto-improve-finish-install", new.split("## What this file is for")[0],
                      msg="and the provenance line names the skill")
        for slot, want in (("project.name", ("widget",)), ("backend.roots", ("src/Api",)),
                           ("review.documents", ("CLAUDE.md", "README.md"))):
            self.assertEqual(load_slot(new, slot), want, msg="%s re-reads through load_slot" % slot)

    def test_a_profile_that_appeared_after_an_absent_preview_is_refused(self):
        p = self.project / ".claude/project-profile.md"
        stale = fi.propose_profile(self.project, claude_home=self.home, plugin_root=self.plugin)
        self.assertEqual(stale.get("source-sha256"), "absent", msg="fixture sanity: the preview saw no profile")
        self.put_profile(template_text({"backend.roots": "`src/Other`"}))
        before = snapshot(self.tmp)
        result = self.apply_profile(self.full(**{"backend.roots": "src/Api"}), sha=stale.get("plan-sha256"))
        self.assertRefused(result, "changed-since-preview", "a profile exists now that the preview never saw")
        self.assertTreeSame(before, "nothing is written")
        self.assertTrue(p.is_file(), msg="and the file someone wrote is still there")

    def test_a_crlf_profile_stays_all_crlf_after_an_apply(self):
        old = template_text(drop=("review-gates",)).replace("\n", "\r\n")  # also needs a row appended
        p = self.project / ".claude/project-profile.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(old.encode("utf-8"))
        result = self.apply_profile(self.full())
        self.assertEqual(result.get("status"), "applied", msg="got %r" % result)
        data = p.read_bytes()
        self.assertEqual(re.findall(rb"(?<!\r)\n", data), [],
                         msg="no bare LF anywhere: header, provenance line, filled rows and the appended row")
        self.assertGreater(data.count(b"\r\n"), 10, msg="and the file really is CRLF")
        self.assertEqual(load_slot(data.decode("utf-8"), "review-gates"), (),
                         msg="the appended row re-reads (it was written as none)")

    def test_the_project_that_is_the_plugin_checkout_is_refused_for_both_profile_commands(self):
        self.put_profile()
        write_files(self.project, {".claude-plugin/plugin.json": json.dumps({"name": PLUGIN_NAME})})
        before = snapshot(self.tmp)
        plan = fi.propose_profile(self.project, claude_home=self.home, plugin_root=self.plugin)
        self.assertRefused(plan, "plugin-source-checkout", "running here would overwrite the shipped template")
        result = self.apply_profile(self.full())
        self.assertRefused(result, "plugin-source-checkout", "the apply refuses the plugin's own checkout too")
        self.assertTreeSame(before, "the shipped template is never rewritten")

    def test_a_project_that_cannot_be_read_is_an_environment_problem(self):
        before = snapshot(self.tmp)
        for target in (self.tmp / "does-not-exist", self.tmp / "plugin/.claude-plugin/plugin.json"):
            with self.subTest(target=str(target.name)):
                result = fi.propose_profile(target, claude_home=self.home, plugin_root=self.plugin)
                self.assertRefused(result, "project-unreadable", "not a readable project directory")
        self.assertTreeSame(before, "a refusal writes nothing")

    def test_no_template_anywhere_is_template_missing(self):
        empty_plugin = self.tmp / "empty-plugin"
        empty_plugin.mkdir()
        before = snapshot(self.tmp)
        result = fi.propose_profile(self.project, claude_home=self.home, plugin_root=empty_plugin)
        self.assertRefused(result, "template-missing", "neither the plugin nor the project has a profile")
        self.assertTreeSame(before, "a refusal writes nothing")


# ======================================================================================
# 3. Install mode
# ======================================================================================
class TestInstallMode(Base):
    def vendor_marker(self):
        write_files(self.project, {".claude/hooks/concept-gate.py": "import sys\n"})

    def plugin_source_marker(self, name=PLUGIN_NAME):
        write_files(self.project, {".claude-plugin/plugin.json": json.dumps({"name": name})})

    def assertFacts(self, verdict):
        facts = self.need(verdict, "facts", "each verdict reports its evidence")
        self.assertTrue(facts, msg="a verdict with no facts cannot be checked")
        for f in facts:
            self.assertTrue(f.get("name") and "observed" in f and f.get("path"),
                            msg="each fact has a name, an observed value and the path read; got %r" % f)

    def test_plugin(self):
        self.install_plugin()
        v = self.mode()
        self.assertEqual(v.get("mode"), "plugin", msg="a user-scope entry with an existing installPath")
        self.assertIs(v.get("enabled"), True, msg="enabledPlugins says true")
        self.assertFacts(v)

    def test_vendored_by_concept_gate_alone_without_a_project_hooks_json(self):
        self.vendor_marker()
        self.assertFalse((self.project / ".claude/hooks/hooks.json").exists(), msg="fixture sanity")
        v = self.mode()
        self.assertEqual(v.get("mode"), "vendored",
                         msg="concept-gate.py in the project's hooks folder is enough; the sync never "
                             "delivers hooks.json to a consumer")
        self.assertIsNone(v.get("enabled"), msg="no installation entry applies")
        self.assertFacts(v)

    def test_both(self):
        self.install_plugin()
        self.vendor_marker()
        v = self.mode()
        self.assertEqual(v.get("mode"), "both", msg="the plugin is installed and the hooks are vendored")
        self.assertFacts(v)

    def test_none(self):
        v = self.mode()
        self.assertEqual(v.get("mode"), "none", msg="no record and no vendored hook")
        self.assertFacts(v)

    def test_plugin_source_wins_over_everything(self):
        self.install_plugin()
        self.vendor_marker()
        self.plugin_source_marker()
        v = self.mode()
        self.assertEqual(v.get("mode"), "plugin-source", msg="precedence: plugin-source is tested first")
        self.assertIn(v.get("mode"), INSTALL_MODES, msg="a member of the closed set")
        self.assertFacts(v)

    def test_another_plugins_manifest_is_not_plugin_source(self):
        self.plugin_source_marker("some-other-plugin")
        self.vendor_marker()
        self.assertEqual(self.mode().get("mode"), "vendored",
                         msg="only a plugin.json naming agentic-auto-improve marks the plugin's own checkout")

    def test_project_scope_covers_only_its_own_project(self):
        self.install_plugin(scope="project")
        self.assertEqual(self.mode().get("mode"), "plugin", msg="projectPath matches this project")
        other = self.tmp / "other-project"
        other.mkdir()
        entry = json.loads((self.home / "plugins/installed_plugins.json").read_text())
        for entries in entry["plugins"].values():
            entries[0]["projectPath"] = str(other)
        (self.home / "plugins/installed_plugins.json").write_text(json.dumps(entry), encoding="utf-8")
        self.assertEqual(self.mode().get("mode"), "none",
                         msg="a project-scope entry for another project does not cover this one")

    def test_local_scope_covers_its_own_project(self):
        self.install_plugin(scope="local")
        self.assertEqual(self.mode().get("mode"), "plugin", msg="scope local with a matching projectPath")

    # --- round two: B2 a disabled plugin plus a vendored copy -----------------------------------
    def test_a_disabled_plugin_plus_a_vendored_copy_is_vendored_and_gets_a_plan(self):
        self.install_plugin(enabled=False)
        self.vendor_marker()
        v = self.mode()
        self.assertEqual(v.get("mode"), "vendored",
                         msg="a plugin switched off for this project cannot duplicate the vendored hooks")
        self.assertFacts(v)
        before = snapshot(self.tmp)
        plan = self.plan()
        self.assertNotEqual(plan.get("code"), "install-mode-both", msg="never 'both' for a disabled plugin")
        self.assertEqual(plan.get("status"), "plan", msg="a SettingsPlan; got %r" % plan)
        self.assertEqual(len(plan.get("to-add", [])), 17, msg="the vendored project is merged as usual")
        self.assertTreeSame(before, "a plan writes nothing")

    def test_a_plugin_with_no_enabled_entry_plus_a_vendored_copy_is_vendored(self):
        self.install_plugin(enabled=None)  # installed, and no enabledPlugins entry in any readable layer
        self.vendor_marker()
        self.assertEqual(self.mode().get("mode"), "vendored",
                         msg="not enabled in any readable layer is a plugin that is off: vendored, not both")

    def test_a_project_layer_switch_off_plus_a_vendored_copy_is_vendored(self):
        key = self.install_plugin(enabled=True)
        self.set_enabled("project", key, False)
        self.vendor_marker()
        self.assertEqual(self.mode().get("mode"), "vendored", msg="the more specific layer wins: off")

    def test_a_disabled_plugin_plus_a_vendored_copy_can_be_applied(self):
        self.install_plugin(enabled=False)
        self.make_vendored()
        sha = self.need(self.plan(), "plan-sha256", "a vendored plan carries the plan hash")
        result = self.apply(sha)
        self.assertEqual(result.get("status"), "applied", msg="the vendored apply runs; got %r" % result)
        self.assertEqual(len(flat_registrations(self.read_settings())), 17, msg="and 17 registrations are written")

    def test_enabled_plus_vendored_stays_both_and_disabled_alone_stays_plugin_disabled(self):
        self.install_plugin(enabled=True)
        self.vendor_marker()
        self.assertEqual(self.mode().get("mode"), "both", msg="enabled and vendored: every hook would run twice")
        rmtree_force(self.project / ".claude")
        self.set_enabled("user", "%s@auto-improve" % PLUGIN_NAME, False)
        v = self.mode()
        self.assertEqual((v.get("mode"), v.get("enabled")), ("plugin", False),
                         msg="disabled with no vendored copy is still the plugin mode, switched off")
        self.assertRefused(self.plan(), "plugin-disabled", "nothing vendored to merge into")

    # --- round two: M17, M11b, installPath "" -----------------------------------------------------
    def test_another_hook_in_the_hooks_folder_is_not_a_vendored_copy(self):
        write_files(self.project, {".claude/hooks/some-other-hook.py": "import sys\n"})
        self.assertEqual(self.mode().get("mode"), "none",
                         msg="only concept-gate.py marks a vendored copy; any other hook file does not")
        self.install_plugin()
        self.assertEqual(self.mode().get("mode"), "plugin",
                         msg="an enabled plugin plus a folder with only another hook is the plugin mode, never both")

    def test_an_entry_for_a_plugin_whose_name_merely_starts_with_ours_changes_no_verdict(self):
        key = "%s-lite@x" % PLUGIN_NAME
        self.write_record({key: [{"scope": "user", "installPath": str(self.plugin), "version": "1"}]})
        self.set_enabled("user", key, True)
        self.assertEqual(self.mode().get("mode"), "none",
                         msg="the key must be this plugin's name followed by '@', not merely start with it")
        self.vendor_marker()
        self.assertEqual(self.mode().get("mode"), "vendored", msg="and it never makes this plugin 'both'")

    def test_an_entry_with_an_empty_install_path_is_not_installed(self):
        key = "%s@auto-improve" % PLUGIN_NAME
        self.write_record({key: [{"scope": "user", "installPath": "", "version": "0.3.0"}]})
        self.set_enabled("user", key, True)
        self.assertEqual(self.mode().get("mode"), "none",
                         msg="an empty installPath names nothing (Path('') is the current directory)")

    def test_project_path_is_compared_normalised_and_case_insensitive_on_windows(self):
        if sys.platform != "win32":
            self.skipTest("case-insensitive path comparison is a Windows rule")
        self.install_plugin(scope="project")
        record = json.loads((self.home / "plugins/installed_plugins.json").read_text())
        for entries in record["plugins"].values():
            entries[0]["projectPath"] = str(self.project).swapcase().replace("\\", "/")
        (self.home / "plugins/installed_plugins.json").write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(self.mode().get("mode"), "plugin",
                         msg="a case-different, slash-different projectPath is the same Windows folder")

    def test_an_entry_whose_install_path_is_gone_is_not_installed(self):
        self.install_plugin(install_path=self.tmp / "gone")
        self.assertEqual(self.mode().get("mode"), "none", msg="the installPath must exist")

    def test_a_more_specific_layer_can_switch_the_plugin_off(self):
        key = self.install_plugin(enabled=True)
        self.set_enabled("project", key, False)
        v = self.mode()
        self.assertEqual(v.get("mode"), "plugin", msg="it is installed")
        self.assertIs(v.get("enabled"), False, msg="the project layer overrides the user layer")
        before = snapshot(self.tmp)
        self.assertRefused(self.plan(), "plugin-disabled", "an installed but disabled plugin runs no hook")
        self.assertTreeSame(before, "a refusal writes nothing")

    def test_local_layer_overrides_project_layer(self):
        key = self.install_plugin(enabled=True)
        self.set_enabled("project", key, False)
        self.set_enabled("local", key, True)
        self.assertIs(self.mode().get("enabled"), True, msg="local is the most specific layer")

    def test_an_unreadable_or_unrecognised_record_is_never_reported_as_none(self):
        self.vendor_marker()
        d = self.home / "plugins"
        d.mkdir(parents=True)
        for text in ("{not json", '["a"]', '{"version": 2, "plugins": "nope"}', '{"unexpected": true}',
                     '{"version": 3, "plugins": {}}'):
            with self.subTest(record=text):
                (d / "installed_plugins.json").write_text(text, encoding="utf-8")
                before = snapshot(self.tmp)
                v = self.mode()
                self.assertRefused(v, "install-record-unreadable", "the record exists but cannot be understood")
                self.assertNotIn("mode", v, msg="no verdict may be reported from a record nobody could read")
                self.assertRefused(self.plan(), "install-record-unreadable", "plan_hooks stops the same way")
                self.assertTreeSame(before, "a refusal writes nothing")

    # --- Claude-home precedence: --claude-home, then CLAUDE_CONFIG_DIR, then ~/.claude ---------
    def test_the_claude_home_argument_wins_over_claude_config_dir(self):
        key = self.install_plugin(enabled=True)  # the REAL fake home: installed and enabled
        decoy = self.tmp / "decoy-home"
        (decoy / "plugins").mkdir(parents=True)
        (decoy / "settings.json").write_text(
            json.dumps({"enabledPlugins": {key: False}}), encoding="utf-8")  # would flip the flag
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(decoy)}):
            v = fi.detect_install_mode(self.project, claude_home=self.home, plugin_root=self.plugin)
        self.assertEqual(v.get("mode"), "plugin",
                         msg="the decoy home has no installation record, so using it would give 'none'")
        self.assertIs(v.get("enabled"), True,
                      msg="--claude-home wins: the decoy's enabledPlugins=false was never read")

    def test_claude_config_dir_wins_over_dot_claude_in_the_user_home(self):
        key = self.install_plugin(enabled=True)  # CLAUDE_CONFIG_DIR (Base) points at this home
        decoy = Path(os.environ["USERPROFILE"]) / ".claude"
        (decoy / "plugins").mkdir(parents=True)
        (decoy / "settings.json").write_text(
            json.dumps({"enabledPlugins": {key: False}}), encoding="utf-8")
        v = fi.detect_install_mode(self.project, claude_home=None, plugin_root=self.plugin)
        self.assertEqual(v.get("mode"), "plugin",
                         msg="~/.claude holds no installation record, so using it would give 'none'")
        self.assertIs(v.get("enabled"), True,
                      msg="CLAUDE_CONFIG_DIR wins over ~/.claude: its enabledPlugins=false was never read")

    def test_two_other_plugins_change_no_verdict(self):
        others = {"other-tool@mkt": [{"scope": "user", "installPath": str(self.plugin), "version": "1"}],
                  "third@mkt": [{"scope": "user", "installPath": str(self.plugin), "version": "1"}]}
        self.write_record(others)
        self.set_enabled("user", "other-tool@mkt", True)
        self.assertEqual(self.mode().get("mode"), "none", msg="no entry for this plugin, whatever the others do")
        self.vendor_marker()
        self.assertEqual(self.mode().get("mode"), "vendored", msg="other plugins never make this one 'both'")
        key = "%s@auto-improve" % PLUGIN_NAME
        others[key] = [{"scope": "user", "installPath": str(self.plugin), "version": "0.3.0"}]
        self.write_record(others)
        self.set_enabled("user", key, True)
        self.set_enabled("user", "other-tool@mkt", False)
        v = self.mode()
        self.assertEqual(v.get("mode"), "both", msg="this plugin plus the vendored hooks")
        self.assertIs(v.get("enabled"), True, msg="another plugin being disabled is not this plugin's flag")

    def test_a_second_marketplace_copy_is_resolved_by_the_scripts_own_location(self):
        key_a, key_b = "%s@mkt-a" % PLUGIN_NAME, "%s@mkt-b" % PLUGIN_NAME
        decoy = self.tmp / "decoy-install"
        decoy.mkdir()
        self.write_record({
            key_a: [{"scope": "user", "installPath": str(decoy), "version": "0.3.0"}],
            key_b: [{"scope": "user", "installPath": str(SCRIPT_ROOT), "version": "0.3.0"}],
        })
        self.set_enabled("user", key_a, True)
        self.set_enabled("user", key_b, False)
        v = self.mode()
        self.assertEqual(v.get("mode"), "plugin", msg="the copy that holds the running script is this install")
        self.assertIs(v.get("enabled"), False, msg="mkt-b's flag was read, so mkt-b was the entry chosen")

    def test_two_copies_and_none_holding_the_script_is_a_record_problem(self):
        decoy_a, decoy_b = self.tmp / "da", self.tmp / "db"
        decoy_a.mkdir()
        decoy_b.mkdir()
        self.write_record({
            "%s@mkt-a" % PLUGIN_NAME: [{"scope": "user", "installPath": str(decoy_a)}],
            "%s@mkt-b" % PLUGIN_NAME: [{"scope": "user", "installPath": str(decoy_b)}],
        })
        result = self.mode()
        self.assertRefused(result, "install-record-unreadable", "ambiguous: neither copy holds the script")
        self.assertTrue("mkt-a" in result.get("message", "") and "mkt-b" in result.get("message", ""),
                        msg="the message names both entries")


# ======================================================================================
# 4 and 5. Merge and interpreter swap
# ======================================================================================
class TestMerge(Base):
    def test_first_run_adds_seventeen_registrations_in_command_plus_args_form(self):
        plan, result = self.apply_to_fresh()
        self.assertEqual(len(self.need(plan, "to-add", "the preview lists what will be added")), 17,
                         msg="16 hook files, plain-language-guard twice")
        self.assertEqual(result.get("status"), "applied", msg="got %r" % result)
        regs = flat_registrations(self.read_settings())
        self.assertEqual(len(regs), 17, msg="17 registrations were written")
        self.assertEqual({(e, n, x) for e, _m, n, x, _h in regs}, EXPECTED_KEYS,
                         msg="every source registration, with its event and arguments")
        for event, _matcher, name, extras, hook in regs:
            self.assertEqual(hook.get("type"), "command", msg="a command hook")
            self.assertEqual(hook.get("command"), "py", msg="command + args form: the launcher alone")
            args = hook.get("args")
            self.assertEqual(args[:2], ["-3", "${CLAUDE_PROJECT_DIR}/.claude/hooks/" + name],
                             msg="-3 first, then the braced project path of %s" % name)
            self.assertEqual(tuple(args[2:]), extras, msg="arguments after the file are kept")

    def test_each_registration_keeps_its_matcher(self):
        self.apply_to_fresh()
        got = {(e, n, x): m for e, m, n, x, _h in flat_registrations(self.read_settings())}
        want = {(e, n, (x,) if x else ()): m for e, m, n, x in _entries()}
        self.assertEqual(got, want, msg="matchers travel with their registrations")

    def test_the_plain_language_guard_pair_stays_two_distinct_keys(self):
        plan, _ = self.apply_to_fresh()
        keys = [r.get("registration-key") for r in plan["to-add"]
                if "plain-language-guard.py" in str(r.get("registration-key"))]
        self.assertEqual(len(keys), 2, msg="one registration on Stop, one on UserPromptSubmit")
        self.assertEqual(len(set(keys)), 2, msg="the keys differ: event and --carry-forward")
        self.assertTrue(any("--carry-forward" in k for k in keys), msg="arguments are part of the key")
        pairs = [(e, x) for e, _m, n, x, _h in flat_registrations(self.read_settings())
                 if n == "plain-language-guard.py"]
        self.assertEqual(sorted(pairs), [("Stop", ()), ("UserPromptSubmit", ("--carry-forward",))],
                         msg="both were written")

    def test_only_one_of_the_pair_present_leaves_the_other_to_add(self):
        self.make_vendored()
        write_json(self.settings_path(), {"hooks": {"Stop": [{"hooks": [{
            "type": "command", "command": 'py -3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/plain-language-guard.py"'}]}]}})
        plan = self.plan()
        added = [r.get("registration-key") for r in self.need(plan, "to-add")]
        self.assertEqual(len(added), 16, msg="the Stop registration is present; the other 16 are missing")
        self.assertTrue(any("--carry-forward" in k for k in added),
                        msg="the UserPromptSubmit registration with its argument is NOT the same key")

    def test_second_run_writes_nothing(self):
        plan, first = self.apply_to_fresh()
        self.assertEqual(first.get("status"), "applied", msg="the first run writes")
        path = self.settings_path()
        data, mtime = path.read_bytes(), path.stat().st_mtime_ns
        backups = sorted(p.name for p in path.parent.glob("settings.json.bak-*"))
        before = snapshot(self.tmp)
        plan2 = self.plan()
        self.assertEqual(plan2.get("to-add"), [], msg="everything is present now")
        result = self.apply(self.need(plan2, "plan-sha256"))
        self.assertEqual(result.get("status"), "nothing-to-do", msg="nothing missing means nothing to do")
        self.assertFalse(result.get("backup"), msg="no backup is reported when nothing is written")
        self.assertEqual(path.read_bytes(), data, msg="the file is byte-identical")
        self.assertEqual(path.stat().st_mtime_ns, mtime, msg="the file was not even rewritten")
        self.assertEqual(sorted(p.name for p in path.parent.glob("settings.json.bak-*")), backups,
                         msg="no new backup")
        self.assertTreeSame(before, "an idempotent re-run")

    def test_unrelated_keys_and_a_users_own_hook_survive(self):
        mine = {"type": "command", "command": "my-own-check.sh"}
        original = {
            "model": "opus", "permissions": {"allow": ["Bash(ls)"], "deny": []},
            "env": {"X": "1"},
            "hooks": {"Notification": [{"hooks": [{"type": "command", "command": "notify.sh"}]}],
                      "PreToolUse": [{"matcher": "Bash", "hooks": [mine]}]},
        }
        _, result = self.apply_to_fresh(original)
        self.assertEqual(result.get("status"), "applied", msg="got %r" % result)
        new = self.read_settings()
        for k in ("model", "permissions", "env"):
            self.assertEqual(new.get(k), original[k], msg="unrelated key %s survives" % k)
        self.assertEqual(list(new)[:3], ["model", "permissions", "env"], msg="key order is preserved")
        self.assertEqual(new["hooks"]["Notification"], original["hooks"]["Notification"],
                         msg="an unrelated event is untouched")
        bash = next(g for g in new["hooks"]["PreToolUse"] if g.get("matcher") == "Bash")
        self.assertEqual(bash["hooks"][0], mine, msg="the user's hook keeps its position")
        self.assertTrue(any(key_of(h) == ("bash-gate.py", ()) for h in bash["hooks"][1:]),
                        msg="a missing registration joins the group with the identical matcher")

    def test_a_registration_under_a_different_matcher_is_reported_not_duplicated(self):
        existing = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "py", "args": ["-3", "${CLAUDE_PROJECT_DIR}/.claude/hooks/concept-gate.py"]}]}]}}
        plan, result = self.apply_to_fresh(existing)
        present = [p for p in self.need(plan, "already-present") if "concept-gate.py" in str(p.get("registration-key"))]
        self.assertEqual(len(present), 1, msg="concept-gate is reported present")
        self.assertIs(present[0].get("different-matcher"), True, msg="its matcher differs from the source's")
        self.assertIs(present[0].get("foreign-path"), False,
                      msg="a ${CLAUDE_PROJECT_DIR}/.claude/hooks path is the project's own, not foreign")
        self.assertEqual(present[0].get("layer"), "project", msg="it is in the project layer")
        self.assertNotIn("concept-gate.py", json.dumps(plan["to-add"]), msg="it is never added again")
        self.assertEqual(result.get("status"), "applied", msg="the other 16 are added")
        count = sum(1 for _e, _m, n, _x, _h in flat_registrations(self.read_settings()) if n == "concept-gate.py")
        self.assertEqual(count, 1, msg="still exactly one concept-gate registration")

    def test_a_registration_in_another_layer_is_reported_with_its_layer(self):
        for layer, path in (("local", self.project / ".claude/settings.local.json"),
                            ("user", self.home / "settings.json")):
            with self.subTest(layer=layer):
                if (self.project / ".claude").exists():
                    rmtree_force(self.project / ".claude")
                write_json(path, {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                    {"type": "command", "command": "py", "args": ["-3", "/x/hooks/bash-gate.py"]}]}]}})
                self.make_vendored()
                plan = self.plan()
                self.assertNotIn("bash-gate.py", json.dumps(self.need(plan, "to-add")),
                                 msg="a registration in the %s layer counts as present" % layer)
                hits = [p for p in plan.get("already-present", []) if "bash-gate.py" in str(p.get("registration-key"))]
                self.assertEqual([h.get("layer") for h in hits], [layer], msg="reported with its layer")
                path.unlink()

    def test_string_form_and_command_plus_args_form_are_both_recognised(self):
        existing = {"hooks": {"PreToolUse": [{"matcher": "Edit|Write|MultiEdit", "hooks": [
            {"type": "command", "command": 'py -3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/concept-gate.py"'},
            {"type": "command", "command": "python3",
             "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/architecture-guard.py"]}]}]}}
        self.make_vendored()
        write_json(self.settings_path(), existing)
        plan = self.plan()
        added = json.dumps(self.need(plan, "to-add"))
        self.assertNotIn("concept-gate.py", added, msg="string form is recognised")
        self.assertNotIn("architecture-guard.py", added, msg="command + args form is recognised")
        self.assertEqual(len(plan["to-add"]), 15, msg="the other 15 are missing")
        pres = plan.get("already-present", [])
        self.assertEqual(len(pres), 2, msg="both are reported present")
        self.assertTrue(all(p.get("different-matcher") is False for p in pres),
                        msg="same matcher as the source, so no gap is reported")

    def test_another_plugins_registration_counts_only_on_an_exact_key_match(self):
        existing = {"hooks": {"PreToolUse": [{"matcher": "Edit|Write|MultiEdit", "hooks": [
            {"type": "command", "command": "py -3 /opt/other-plugin/hooks/concept-gate.py"},
            {"type": "command", "command": "py -3 /opt/other-plugin/hooks/architecture-guard-lite.py"}]},
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "py -3 /opt/other-plugin/hooks/bash-gate.py --strict"}]}]}}
        self.make_vendored()
        write_json(self.settings_path(), existing)
        plan = self.plan()
        added = json.dumps(self.need(plan, "to-add"))
        self.assertNotIn("concept-gate.py", added, msg="same event, file and arguments: present")
        hit = [p for p in plan.get("already-present", []) if "concept-gate.py" in str(p.get("registration-key"))]
        self.assertEqual([h.get("foreign-path") for h in hit], [True], msg="reported as a foreign path")
        self.assertIn("architecture-guard.py", added, msg="a different file name is not a match")
        self.assertIn("bash-gate.py", added, msg="different arguments are a different key")

    def test_existing_duplicate_registrations_are_left_alone_and_reported(self):
        dup = {"type": "command", "command": "py", "args": ["-3", "/x/db-destructive-guard.py"]}
        existing = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [dup]},
                                             {"matcher": "PowerShell", "hooks": [dup]}]}}
        plan, result = self.apply_to_fresh(existing)
        hits = [p for p in self.need(plan, "already-present") if "db-destructive-guard.py" in str(p.get("registration-key"))]
        self.assertGreaterEqual(len(hits), 2, msg="the existing duplicate is reported, not merged")
        new = self.read_settings()
        count = sum(1 for _e, _m, n, _x, _h in flat_registrations(new) if n == "db-destructive-guard.py")
        self.assertEqual(count, 2, msg="and left exactly as it was")
        self.assertEqual(result.get("status"), "applied", msg="the remaining registrations are added")

    def test_skip_leaves_named_hooks_out(self):
        plan, result = self.apply_to_fresh(skip=["memory-pager.py", "plain-language-guard.py"])
        self.assertEqual(result.get("status"), "applied", msg="got %r" % result)
        names = [n for _e, _m, n, _x, _h in flat_registrations(self.read_settings())]
        self.assertNotIn("memory-pager.py", names, msg="skipped")
        self.assertNotIn("plain-language-guard.py", names, msg="a skipped file leaves every registration of it out")
        self.assertEqual(len(names), 14, msg="17 minus memory-pager and both plain-language-guard entries")

    # --- round two: M22/M27 coverage gaps, M29 disable-all-hooks -----------------------------------
    @staticmethod
    def narrative(plan):
        """Everything the plan SAYS (its notes), not the registrations it lists."""
        return json.dumps({k: v for k, v in plan.items()
                           if k not in ("to-add", "already-present", "unified-diff", "target", "hooks-json")})

    def test_the_plan_names_the_powershell_coverage_gap_on_windows_only(self):
        self.make_vendored()
        win = self.plan("win32")
        self.assertIn("PowerShell", self.narrative(win),
                      msg="on win32 the database guard's matcher names no PowerShell tool, and the plan must say so")
        self.assertNotIn("PowerShell", self.narrative(self.plan("linux")),
                         msg="on linux there is no PowerShell tool to be left uncovered")

    def test_a_guard_registered_only_for_powershell_is_present_with_a_different_matcher(self):
        existing = {"hooks": {"PreToolUse": [{"matcher": "PowerShell", "hooks": [
            {"type": "command", "command": "py", "args": ["-3", "${CLAUDE_PROJECT_DIR}/.claude/hooks/db-destructive-guard.py"]}]}]}}
        self.make_vendored()
        write_json(self.settings_path(), existing)
        plan = self.plan("win32")
        hits = [p for p in plan.get("already-present", []) if "db-destructive-guard.py" in str(p.get("registration-key"))]
        self.assertEqual(len(hits), 1, msg="the existing PowerShell registration counts as present")
        self.assertIs(hits[0].get("different-matcher"), True,
                      msg="its matcher (PowerShell) differs from the source's (Bash|Edit|Write|MultiEdit)")
        self.assertNotIn("db-destructive-guard.py", json.dumps(plan.get("to-add")),
                         msg="a different matcher is reported, never added")

    def test_the_vendored_plan_carries_disable_all_hooks(self):
        self.make_vendored()
        self.assertIs(self.plan().get("disable-all-hooks"), False, msg="no layer disables the hooks")
        write_json(self.project / ".claude/settings.local.json", {"disableAllHooks": True})
        plan = self.plan()
        self.assertIn("disable-all-hooks", plan, msg="the SettingsPlan always carries the key")
        self.assertIs(plan.get("disable-all-hooks"), True, msg="the local layer disables every hook: say so")

    def test_the_source_is_the_projects_own_hooks_json_when_it_exists(self):
        self.make_vendored(own_hooks_json=hooks_json_obj(only={"concept-gate.py", "bash-gate.py"}))
        plan = self.plan()
        self.assertEqual(len(self.need(plan, "to-add")), 2,
                         msg="the project's own hooks.json is the source, not the plugin's 17")

    def test_the_plugins_hooks_json_is_the_source_when_the_project_has_none(self):
        self.make_vendored()
        self.assertEqual(len(self.need(self.plan(), "to-add")), 17,
                         msg="found through the plugin root, never a guessed path")

    def test_the_real_plugin_hooks_json_yields_exactly_its_twelve_registrations(self):
        # Amended by sub-task 23 (hook-server-modes amendment 2026-10-09, INV-O1): the real hooks.json now
        # registers twelve entries, in exec form. The matcher is part of the comparison, because the
        # database guards appear on several matchers of one event and must stay distinct entries.
        real = json.loads((SCRIPT_ROOT / ".claude/hooks/hooks.json").read_text(encoding="utf-8"))
        expected = sorted((event, g.get("matcher") or "", key_of(h)[0], key_of(h)[1])
                          for event, groups in real["hooks"].items()
                          for g in groups for h in g.get("hooks", []))
        self.assertEqual(len(expected), 12,
                         msg="independent parse of the REAL hooks.json: 12 registrations")
        self.make_vendored()  # every hook file named by the real hooks.json exists in the project
        # the fake plugin holds 16 hook files; the real one also holds the session-start hook and the dispatcher
        for extra_hook in ("working-agreements.py", "post-edit-dispatcher.py"):
            (self.project / ".claude/hooks" / extra_hook).write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        for _e, _m, name, _x in expected:
            self.assertTrue((self.project / ".claude/hooks" / name).is_file(),
                            msg="fixture sanity: the temp project holds %s" % name)
        plan = fi.plan_hooks(self.project, "win32", claude_home=self.home, plugin_root=SCRIPT_ROOT)
        added = self.need(plan, "to-add", "registrations read from the real plugin's hooks.json")
        self.assertEqual(len(added), 12, msg="all 12 real registrations are missing and to be added")
        got = []
        for r in added:
            parsed = parse_registration_key(str(r.get("registration-key")))
            self.assertIsNotNone(parsed, msg="the key names a hook file; got %r" % r)
            got.append((r.get("event"), r.get("matcher") or "", parsed[0], parsed[1]))
        self.assertEqual(sorted(got), expected,
                         msg="the event, matcher and hook file of each entry equal those parsed from the real hooks.json")

    def test_the_independent_key_parsers_agree_on_a_known_registration_positive_control(self):
        hook = {"type": "command", "command": 'py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/plain-language-guard.py" --carry-forward'}
        self.assertEqual(key_of(hook), ("plain-language-guard.py", ("--carry-forward",)),
                         msg="POSITIVE CONTROL: the helper reads a file name and its arguments")
        self.assertEqual(parse_registration_key("UserPromptSubmit|plain-language-guard.py|--carry-forward"),
                         ("plain-language-guard.py", ("--carry-forward",)),
                         msg="POSITIVE CONTROL: the key parser reads the same pair out of a key string")
        self.assertEqual(parse_registration_key("Stop|plain-language-guard.py"),
                         ("plain-language-guard.py", ()), msg="and no arguments when there are none")

    def test_a_missing_file_in_the_settings_preview_shows_in_the_diff(self):
        self.make_vendored()
        plan = self.plan()
        self.assertEqual(plan.get("source-sha256"), "absent", msg="no settings.json yet")
        self.assertIn("concept-gate.py", self.need(plan, "unified-diff"), msg="the diff shows the change")
        self.assertEqual(plan.get("interpreter"), "py -3", msg="win32 launcher")


class TestInterpreterSwap(Base):
    def test_posix_platforms_use_python3_and_win32_keeps_py(self):
        for platform, command, first_arg_is_path in (("linux", "python3", True), ("darwin", "python3", True),
                                                     ("win32", "py", False)):
            with self.subTest(platform=platform):
                if (self.project / ".claude").exists():
                    rmtree_force(self.project / ".claude")
                del self.which_calls[:]
                plan, result = self.apply_to_fresh(platform=platform)
                self.assertEqual(plan.get("interpreter"), "python3" if first_arg_is_path else "py -3",
                                 msg="the preview names the interpreter")
                self.assertEqual(result.get("status"), "applied", msg="got %r" % result)
                wanted = "python3" if first_arg_is_path else "py"
                self.which.assert_any_call(wanted)
                self.assertIn(wanted, self.which_calls,
                              msg="the interpreter is looked up by the platform's own name (%s on %s); "
                                  "recorded lookups: %r" % (wanted, platform, self.which_calls))
                regs = flat_registrations(self.read_settings())
                self.assertEqual(len(regs), 17, msg="all registrations written")
                for _e, _m, name, _x, hook in regs:
                    self.assertEqual(hook.get("command"), command, msg="%s on %s" % (name, platform))
                    args = hook.get("args")
                    if first_arg_is_path:
                        self.assertEqual(args[0], "${CLAUDE_PROJECT_DIR}/.claude/hooks/" + name,
                                         msg="python3 takes the path first, with no -3")
                    else:
                        self.assertEqual(args[:2], ["-3", "${CLAUDE_PROJECT_DIR}/.claude/hooks/" + name],
                                         msg="py keeps -3 as its first argument")

    def test_the_plugin_root_variable_never_survives(self):
        _, result = self.apply_to_fresh()
        self.assertEqual(result.get("status"), "applied", msg="the apply must run")
        text = self.settings_path().read_text(encoding="utf-8")
        self.assertFalse(has_plugin_root_variable(text),
                         msg="${CLAUDE_PLUGIN_ROOT} means nothing in a project's settings.json")
        self.assertNotIn("$comment", text, msg="the source's comment block is not copied")

    def test_the_plugin_root_check_fails_when_one_is_planted_positive_control(self):
        planted = json.dumps({"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": 'py -3 "${CLAUDE_PLUGIN_ROOT}/x.py"'}]}]}})
        self.assertTrue(has_plugin_root_variable(planted),
                        msg="POSITIVE CONTROL: the check must see a planted ${CLAUDE_PLUGIN_ROOT}")
        self.assertFalse(has_plugin_root_variable('{"a": "${CLAUDE_PROJECT_DIR}"}'),
                         msg="and must not flag the project variable")


# ======================================================================================
# 6. Safety
# ======================================================================================
class TestSafety(Base):
    ORIGINAL = {"model": "opus", "permissions": {"allow": ["Bash(ls)"]}}

    def settings_bytes(self, **fmt):
        write_json(self.settings_path(), self.ORIGINAL, **fmt)
        return self.settings_path().read_bytes()

    def test_a_backup_exists_before_the_write_and_equals_the_old_bytes(self):
        self.make_vendored()
        old = self.settings_bytes()
        sha = self.preview_sha()
        seen = []  # what the backups held at each rename whose TARGET is settings.json
        real = os.replace
        target = self.settings_path().resolve()

        def spy(src, dst, *a, **k):
            if Path(dst).resolve() == target:
                backups = sorted(self.settings_path().parent.glob("settings.json.bak-*"))
                seen.append([b.read_bytes() for b in backups])
            return real(src, dst, *a, **k)

        with mock.patch("os.replace", side_effect=spy):
            result = self.apply(sha)
        self.assertEqual(result.get("status"), "applied", msg="got %r" % result)
        self.assertTrue(seen, msg="the new settings.json was put in place through os.replace")
        self.assertEqual(seen[0], [old],
                         msg="at the moment of the rename onto settings.json one backup existed and "
                             "held the old bytes")
        backups = list(self.settings_path().parent.glob("settings.json.bak-*"))
        self.assertEqual(len(backups), 1, msg="one backup")
        self.assertRegex(backups[0].name, r"^settings\.json\.bak-\d{8}T\d{6}Z", msg="UTC timestamped name")
        self.assertEqual(backups[0].read_bytes(), old, msg="the backup equals the old bytes")
        self.assertNotEqual(self.settings_path().read_bytes(), old, msg="and the file really changed")

    def test_an_existing_backup_is_never_overwritten_whatever_the_clock_says(self):
        self.make_vendored()
        old = self.settings_bytes()
        sha = self.preview_sha()
        # Plant backups named for the current second and the next two, so whichever second the
        # script's own timestamp lands in, its first-choice name is already taken.
        now = datetime.datetime.now(datetime.timezone.utc)
        planted = {}
        for offset in (0, 1, 2):
            stamp = (now + datetime.timedelta(seconds=offset)).strftime("%Y%m%dT%H%M%SZ")
            path = self.settings_path().parent / ("settings.json.bak-" + stamp)
            path.write_bytes(b"planted backup %d" % offset)
            planted[path.name] = path.read_bytes()
        result = self.apply(sha)
        self.assertEqual(result.get("status"), "applied", msg="got %r" % result)
        for name, content in planted.items():
            self.assertEqual((self.settings_path().parent / name).read_bytes(), content,
                             msg="%s existed before the apply and must be byte-unchanged" % name)
        fresh = [p for p in self.settings_path().parent.glob("settings.json.bak-*") if p.name not in planted]
        self.assertEqual(len(fresh), 1, msg="exactly one new, distinct backup was made")
        self.assertEqual(fresh[0].read_bytes(), old, msg="and it holds the bytes the file had before")

    def test_a_byte_order_mark_is_tolerated_and_written_back(self):
        self.make_vendored()
        self.settings_bytes(bom=True)
        self.assertTrue(self.settings_path().read_bytes().startswith(b"\xef\xbb\xbf"), msg="fixture sanity")
        result = self.apply(self.preview_sha())
        self.assertEqual(result.get("status"), "applied", msg="a BOM is not a malformed file; got %r" % result)
        data = self.settings_path().read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"), msg="the byte order mark is written back")
        self.assertFalse(data.startswith(b"\xef\xbb\xbf\xef\xbb\xbf"), msg="once, not twice")
        self.assertEqual(len(flat_registrations(self.read_settings())), 17, msg="and the content merged")

    def test_line_ending_and_indent_are_detected_and_reused(self):
        self.make_vendored()
        self.settings_bytes(indent=4, newline="\r\n")
        plan = self.plan()
        removed = [l for l in self.need(plan, "unified-diff").splitlines() if l.startswith("-") and not l.startswith("---")]
        self.assertLessEqual(len(removed), 3, msg="the diff shows only changed lines, not the whole file")
        self.assertTrue(any(l.startswith("+") for l in plan["unified-diff"].splitlines()), msg="and some additions")
        self.assertEqual(self.apply(self.need(plan, "plan-sha256")).get("status"), "applied", msg="the apply must run")
        data = self.settings_path().read_bytes()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""), msg="every line ending is CRLF")
        self.assertIn(b'\r\n    "hooks": {', data, msg="four-space indent reused")
        self.assertTrue(data.endswith(b"\r\n"), msg="trailing newline in the file's own style")

    def test_a_new_file_uses_two_spaces_a_line_feed_and_a_trailing_newline(self):
        self.apply_to_fresh()
        data = self.settings_path().read_bytes()
        self.assertNotIn(b"\r", data, msg="line feed only")
        self.assertIn(b'\n  "hooks": {', data, msg="two-space indent")
        self.assertTrue(data.endswith(b"\n"), msg="trailing newline")

    def test_non_ascii_text_and_key_order_are_kept(self):
        self.make_vendored()
        write_json(self.settings_path(), {"zeta": "café", "alpha": 1})
        self.assertEqual(self.apply(self.preview_sha()).get("status"), "applied", msg="must apply")
        data = self.settings_path().read_bytes()
        self.assertIn("café".encode("utf-8"), data, msg="non-ASCII is not escaped")
        self.assertLess(data.index(b'"zeta"'), data.index(b'"alpha"'), msg="insertion order is kept")

    # --- refusals: each pairs an unchanged tree with the code and the exit class ----------
    def refused_plan(self, content, code, why):
        self.make_vendored()
        self.settings_path().write_bytes(content)
        before = snapshot(self.tmp)
        result = self.plan()
        self.assertRefused(result, code, why)
        self.assertTreeSame(before, why)
        return result

    def test_malformed_settings_names_the_line_and_column(self):
        result = self.refused_plan(b'{\n  "hooks": {\n    "Stop": [,]\n  }\n}\n', "malformed-settings",
                                   "a parse failure")
        self.assertRegex(result.get("message", ""), r"(?i)line\s*\d+", msg="the message names the line")
        self.assertRegex(result.get("message", ""), r"(?i)col(umn)?\s*\d+", msg="and the column")

    def test_duplicate_keys_are_malformed_settings(self):
        self.refused_plan(b'{"hooks": {}, "hooks": {}}', "malformed-settings", "a duplicate top-level key")
        self.setUp_again()
        self.refused_plan(b'{"a": {"x": 1, "x": 2}}', "malformed-settings", "a duplicate nested key")

    def setUp_again(self):
        rmtree_force(self.project / ".claude")

    def test_unexpected_shapes_are_refused(self):
        for content in (b"[]", b'{"hooks": []}', b'{"hooks": {"PreToolUse": {}}}', b'"text"'):
            with self.subTest(content=content):
                self.setUp_again() if (self.project / ".claude").exists() else None
                self.refused_plan(content, "unexpected-settings-shape", "the shape is not hooks -> event -> list")

    def test_hooks_json_missing_when_neither_the_project_nor_the_plugin_has_one(self):
        self.make_vendored()
        bare = self.tmp / "bare-plugin"
        bare.mkdir()
        before = snapshot(self.tmp)
        result = fi.plan_hooks(self.project, "win32", claude_home=self.home, plugin_root=bare)
        self.assertRefused(result, "hooks-json-missing", "no source of registrations anywhere")
        self.assertTreeSame(before, "a refusal writes nothing")

    def test_a_missing_hook_file_is_refused_on_apply(self):
        self.make_vendored()
        sha = self.preview_sha()
        (self.project / ".claude/hooks/db-destructive-guard.py").unlink()
        before = snapshot(self.tmp)
        result = self.apply(sha)
        self.assertRefused(result, "hook-file-missing", "a missing script exits 2 and blocks every tool call")
        self.assertIn("db-destructive-guard.py", result.get("message", ""), msg="the message names the file")
        self.assertTreeSame(before, "nothing is written")

    def test_only_the_expected_interpreter_name_being_missing_is_refused_on_apply(self):
        # (platform, the name that must be looked up, the name that is present but irrelevant)
        for platform, expected, other in (("linux", "python3", "py"), ("darwin", "python3", "py"),
                                          ("win32", "py", "python3")):
            with self.subTest(platform=platform):
                if (self.project / ".claude").exists():
                    rmtree_force(self.project / ".claude")
                self.make_vendored()
                sha = self.preview_sha(platform=platform)
                self.which_missing = {expected}  # every OTHER name, including `other`, is found
                del self.which_calls[:]
                before = snapshot(self.tmp)
                result = self.apply(sha, platform=platform)
                self.assertRefused(result, "interpreter-not-found",
                                   "%s is missing on %s although %s is found: a missing program fails "
                                   "open silently" % (expected, platform, other))
                self.assertIn(expected, self.which_calls,
                              msg="the lookup was for %r; recorded: %r" % (expected, self.which_calls))
                self.assertTreeSame(before, "nothing is written")

    def test_a_missing_other_name_does_not_block_the_expected_interpreter_positive_control(self):
        for platform, expected, other in (("linux", "python3", "py"), ("win32", "py", "python3")):
            with self.subTest(platform=platform):
                if (self.project / ".claude").exists():
                    rmtree_force(self.project / ".claude")
                self.which_missing = {other}
                plan, result = self.apply_to_fresh(platform=platform)
                self.assertEqual(result.get("status"), "applied",
                                 msg="POSITIVE CONTROL: %s is found on %s, so %s being absent is "
                                     "irrelevant; got %r" % (expected, platform, other, result))

    def test_a_changed_settings_file_is_refused_on_apply(self):
        self.make_vendored()
        self.settings_bytes()
        stale = self.preview_sha()
        self.settings_path().write_bytes(self.settings_path().read_bytes() + b"\n")
        before = snapshot(self.tmp)
        result = self.apply(stale)
        self.assertRefused(result, "changed-since-preview", "the file changed between preview and yes")
        self.assertTreeSame(before, "the stale preview is not applied")

    def test_a_file_that_appeared_after_an_absent_preview_is_refused(self):
        self.make_vendored()
        plan = self.plan()
        self.assertEqual(plan.get("source-sha256"), "absent", msg="fixture sanity: no settings.json at preview")
        stale = self.need(plan, "plan-sha256", "the preview must report the plan hash")
        self.settings_bytes()
        before = snapshot(self.tmp)
        self.assertRefused(self.apply(stale), "changed-since-preview", "the file exists now")
        self.assertTreeSame(before, "nothing is written")

    def test_a_failed_rename_is_write_failed_and_the_original_is_untouched(self):
        self.make_vendored()
        old = self.settings_bytes()
        sha = self.preview_sha()
        before = snapshot(self.tmp)
        with mock.patch("os.replace", side_effect=PermissionError("held by another program")):
            result = self.apply(sha)
        self.assertRefused(result, "write-failed", "the rename failed")
        self.assertEqual(self.settings_path().read_bytes(), old, msg="the original is untouched")
        self.assertTreeSame(before, "write-failed removes the temporary file AND the backup this run created")

    def test_declining_writes_nothing_and_applying_the_same_plan_changes_the_tree(self):
        self.make_vendored()
        before = snapshot(self.tmp)
        plan = self.plan()
        self.assertEqual(plan.get("status"), "plan", msg="a plan without --apply")
        self.assertEqual(len(plan.get("to-add", [])), 17, msg="and it has something to propose")
        self.assertTreeSame(before, "declining writes nothing")
        result = self.apply(self.need(plan, "plan-sha256"))
        self.assertEqual(result.get("status"), "applied", msg="POSITIVE CONTROL: the same command with apply writes")
        self.assertNotEqual(snapshot(self.tmp), before, msg="POSITIVE CONTROL: the tree changed")

    def test_cursor_and_codex_have_no_hooks(self):
        self.make_vendored()
        before = snapshot(self.tmp)
        for provider in ("cursor", "codex"):
            self.assertIn(provider, PROVIDERS, msg="a known provider")
            self.assertRefused(self.plan(provider=provider), "provider-has-no-hooks",
                               "hooks are Claude-only in this release")
        self.assertTreeSame(before, "nothing is written")

    def test_a_both_install_stops_naming_the_two_facts(self):
        self.install_plugin()
        self.make_vendored()
        before = snapshot(self.tmp)
        result = self.plan()
        self.assertRefused(result, "install-mode-both", "every hook would run twice")
        message = result.get("message", "")
        self.assertRegex(message, r"installed_plugins|enabledPlugins|installation record",
                         msg="the message names the plugin fact (the installation record or "
                             "enabledPlugins); got %r" % message)
        self.assertIn("concept-gate.py", message, msg="and the vendored fact; got %r" % message)
        self.assertRegex(message.lower(), r"remove", msg="and says to remove one of the two; got %r" % message)
        self.assertTreeSame(before, "nothing is written")

    def test_no_install_at_all_stops(self):
        before = snapshot(self.tmp)
        self.assertRefused(self.plan(), "install-mode-none", "nothing to merge into and nothing installed")
        self.assertTreeSame(before, "nothing is written")

    def test_the_plugin_checkout_stops(self):
        write_files(self.project, {".claude-plugin/plugin.json": json.dumps({"name": PLUGIN_NAME})})
        before = snapshot(self.tmp)
        self.assertRefused(self.plan(), "plugin-source-checkout", "the plugin's own checkout")
        self.assertTreeSame(before, "nothing is written")

    def test_a_hooks_apply_under_a_plugin_install_is_refused_outright(self):
        self.install_plugin()
        before = snapshot(self.tmp)
        result = self.apply("absent")
        self.assertIn("plugin-install-needs-no-registration", REFUSAL_CODES,
                      msg="the closed set must list the new refusal code")
        self.assertIsInstance(result, dict, msg="a refusal dict")
        self.assertEqual(result.get("code"), "plugin-install-needs-no-registration",
                         msg="an apply under a plugin install is refused with exactly this code; got %r" % result)
        self.assertRefused(result, "plugin-install-needs-no-registration",
                           "an apply is allowed only for a vendored project")
        self.assertIn("plugin", result.get("message", "").lower(), msg="the message says why: a plugin install")
        self.assertFalse(self.settings_path().exists(), msg="no settings.json is created")
        self.assertTreeSame(before, "the tree (project, claude home and plugin) is byte-identical")

    # --- round two M19/M20: the APPLY path refuses too, with the tree byte-identical ----------------
    def test_apply_under_both_refuses_with_the_tree_unchanged(self):
        self.install_plugin()
        self.make_vendored()
        for sha in ("0" * 64, "absent"):
            with self.subTest(sha=sha[:6]):
                before = snapshot(self.tmp)
                self.assertRefused(self.apply(sha), "install-mode-both", "an apply would double every hook")
                self.assertTreeSame(before, "nothing is written")
        self.assertFalse(self.settings_path().exists(), msg="no settings.json was created")

    def test_apply_under_none_refuses_with_the_tree_unchanged(self):
        before = snapshot(self.tmp)
        self.assertRefused(self.apply("absent"), "install-mode-none", "nothing installed, nothing to merge into")
        self.assertTreeSame(before, "nothing is written")

    def test_apply_in_the_plugins_own_checkout_refuses_with_the_tree_unchanged(self):
        write_files(self.project, {".claude-plugin/plugin.json": json.dumps({"name": PLUGIN_NAME})})
        before = snapshot(self.tmp)
        self.assertRefused(self.apply("absent"), "plugin-source-checkout", "the plugin's own checkout")
        self.assertTreeSame(before, "nothing is written")

    def test_apply_under_a_plugin_install_refuses_even_with_a_real_looking_hash(self):
        self.install_plugin()
        real = self.plan().get("plan-sha256") or hashlib.sha256(b"x").hexdigest()
        before = snapshot(self.tmp)
        self.assertRefused(self.apply(real), "plugin-install-needs-no-registration",
                           "a plugin install registers its own hooks")
        self.assertTreeSame(before, "nothing is written")

    def test_apply_for_cursor_and_codex_refuses_with_the_tree_unchanged(self):
        self.make_vendored()
        write_json(self.settings_path(), {"model": "opus"})
        for provider in ("cursor", "codex"):
            with self.subTest(provider=provider):
                before = snapshot(self.tmp)
                result = self.apply("0" * 64, provider=provider)
                self.assertRefused(result, "provider-has-no-hooks", "hooks are Claude-only in this release")
                self.assertTreeSame(before, "nothing is written")

    # --- round two W4: an unreadable settings file is a named refusal, never a crash ----------------
    def unreadable(self, target, write_names=()):
        """Patch every way a file is opened so that reading `target` (and creating any path whose
        name contains one of `write_names`) raises OSError; everything else behaves normally."""
        target = Path(target)
        real_read_bytes, real_read_text = Path.read_bytes, Path.read_text
        real_path_open, real_open = Path.open, open

        def same(path):
            try:
                return Path(os.fspath(path)).resolve() == target.resolve()
            except (OSError, TypeError, ValueError):
                return False

        def blocked(path, mode="r"):
            if same(path) and not any(m in mode for m in "wax+"):
                return True
            return any(n in Path(os.fspath(path)).name for n in write_names) if write_names else False

        def read_bytes(self_, *a, **k):
            if same(self_):
                raise PermissionError(13, "access denied (test)")
            return real_read_bytes(self_, *a, **k)

        def read_text(self_, *a, **k):
            if same(self_):
                raise PermissionError(13, "access denied (test)")
            return real_read_text(self_, *a, **k)

        def path_open(self_, mode="r", *a, **k):
            if blocked(self_, mode):
                raise PermissionError(13, "access denied (test)")
            return real_path_open(self_, mode, *a, **k)

        def opener(file, mode="r", *a, **k):
            if isinstance(file, (str, bytes, os.PathLike)) and blocked(file, mode):
                raise PermissionError(13, "access denied (test)")
            return real_open(file, mode, *a, **k)

        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(Path, "read_bytes", read_bytes))
        stack.enter_context(mock.patch.object(Path, "read_text", read_text))
        stack.enter_context(mock.patch.object(Path, "open", path_open))
        stack.enter_context(mock.patch("builtins.open", opener))
        return stack

    def call(self, fn, *a, **k):
        """Call fn; a raised exception is a test FAILURE (the contract says: a refusal, never a crash)."""
        try:
            return fn(*a, **k)
        except Exception as exc:  # noqa: BLE001 - any escape is the defect under test
            self.fail("the function raised %s: %s instead of returning a refusal dict" % (type(exc).__name__, exc))

    def test_an_unreadable_settings_file_is_project_unreadable_on_plan_and_apply(self):
        self.make_vendored()
        self.settings_bytes()
        sha = self.preview_sha()  # a real hash, taken while the file is still readable
        before = snapshot(self.tmp)
        with self.unreadable(self.settings_path()):
            planned = self.call(self.plan)
            applied = self.call(self.apply, sha)
        self.assertRefused(planned, "project-unreadable", "the preview could not read settings.json")
        self.assertRefused(applied, "project-unreadable", "the apply could not read settings.json")
        self.assertIn("settings.json", planned.get("message", "") + planned.get("path", ""),
                      msg="the refusal names the file")
        self.assertTreeSame(before, "nothing is written")

    def test_an_unwritable_backup_or_temporary_file_is_write_failed_with_the_tree_unchanged(self):
        self.make_vendored()
        self.settings_bytes()
        sha = self.preview_sha()
        for label, names in (("backup", (".bak-",)), ("temporary file", (".tmp-",))):
            with self.subTest(blocked=label):
                before = snapshot(self.tmp)
                with self.unreadable(self.tmp / "nothing-is-read-blocked-here", write_names=names):
                    result = self.call(self.apply, sha)
                self.assertRefused(result, "write-failed", "the %s could not be created" % label)
                self.assertTreeSame(before, "write-failed leaves the tree byte-identical (no stray backup)")

    # --- round two W5: a malformed user or local settings file is refused, not read as empty --------
    def test_a_malformed_user_or_local_settings_file_is_refused_naming_that_file(self):
        for layer, path in (("user", self.home / "settings.json"),
                            ("local", self.project / ".claude/settings.local.json")):
            with self.subTest(layer=layer):
                if (self.project / ".claude").exists():
                    rmtree_force(self.project / ".claude")
                self.make_vendored()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"{not json")
                before = snapshot(self.tmp)
                result = self.call(self.plan)
                self.assertRefused(result, "malformed-settings",
                                   "its registrations would be invisible, so duplicates would be added")
                self.assertIn(path.name, result.get("message", "") + result.get("path", ""),
                              msg="the refusal names the %s layer's file; got %r" % (layer, result))
                if layer == "local":
                    self.assertNotEqual(Path(result.get("path", "")).name, "settings.json",
                                        msg="and it is not mistaken for the project's own settings.json")
                self.assertRefused(self.call(self.apply, "0" * 64), "malformed-settings",
                                   "the apply refuses the same way")
                self.assertTreeSame(before, "nothing is written")
                path.unlink()

    def test_the_user_layer_file_is_not_mistaken_for_the_project_file_in_the_refusal(self):
        self.make_vendored()
        (self.home / "settings.json").write_bytes(b"[1,")
        result = self.call(self.plan)
        self.assertRefused(result, "malformed-settings", "a malformed user settings file")
        self.assertEqual(Path(result.get("path", "")).resolve(), (self.home / "settings.json").resolve(),
                         msg="the path is the user file that failed to parse")


# ======================================================================================
# 6b. The plan hash binds the planned change (round-two blocker B3)
# ======================================================================================
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class TestPlanHash(Base):
    def test_the_plan_carries_a_plan_hash_beside_the_input_hash(self):
        self.make_vendored()
        plan = self.plan()
        self.assertEqual(plan.get("source-sha256"), "absent", msg="no settings.json yet: the input hash stays 'absent'")
        self.assertRegex(str(plan.get("plan-sha256")), HEX64, msg="plan-sha256 is a SHA-256 hex digest")
        write_json(self.settings_path(), {"model": "opus"})
        plan = self.plan()
        self.assertEqual(plan.get("source-sha256"), sha_of(self.settings_path()),
                         msg="source-sha256 is still the hash of the input bytes")
        self.assertRegex(str(plan.get("plan-sha256")), HEX64, msg="plan-sha256 is a SHA-256 hex digest")
        self.assertNotEqual(plan.get("plan-sha256"), plan.get("source-sha256"),
                            msg="the plan hash binds more than the input bytes")

    def test_the_plan_hash_moves_with_the_skip_list_and_ignores_its_order(self):
        self.make_vendored()
        plain = self.preview_sha()
        one = self.preview_sha(skip=["memory-pager.py"])
        two_a = self.preview_sha(skip=["memory-pager.py", "bash-gate.py"])
        two_b = self.preview_sha(skip=["bash-gate.py", "memory-pager.py"])
        self.assertNotEqual(plain, one, msg="a skip changes the planned change, so it changes the hash")
        self.assertNotEqual(one, two_a, msg="a longer skip list changes it again")
        self.assertEqual(two_a, two_b, msg="the skip list is sorted before it is hashed")

    def test_a_skip_given_only_at_apply_time_is_refused(self):
        self.make_vendored()
        sha = self.preview_sha()
        before = snapshot(self.tmp)
        result = self.apply(sha, skip=["concept-gate.py"])
        self.assertRefused(result, "changed-since-preview", "the operator confirmed 17 registrations, not 16")
        self.assertTreeSame(before, "nothing is written")

    def test_a_skip_at_preview_that_is_dropped_at_apply_time_is_refused(self):
        self.make_vendored()
        sha = self.preview_sha(skip=["concept-gate.py"])
        before = snapshot(self.tmp)
        self.assertRefused(self.apply(sha), "changed-since-preview", "the operator confirmed 16, not 17")
        self.assertTreeSame(before, "nothing is written")

    def test_the_same_skip_at_preview_and_apply_succeeds_in_either_order(self):
        self.make_vendored()
        sha = self.preview_sha(skip=["concept-gate.py", "memory-pager.py"])
        result = self.apply(sha, skip=["memory-pager.py", "concept-gate.py"])
        self.assertEqual(result.get("status"), "applied", msg="POSITIVE CONTROL: same flags, same hash; got %r" % result)
        names = [n for _e, _m, n, _x, _h in flat_registrations(self.read_settings())]
        self.assertEqual(len(names), 15, msg="17 minus two skipped hooks")
        self.assertNotIn("concept-gate.py", names, msg="the skipped hook is left out")

    def test_a_user_or_local_layer_change_between_preview_and_apply_is_refused(self):
        registers_bash_gate = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "py", "args": ["-3", "/x/hooks/bash-gate.py"]}]}]}}
        for layer, path in (("user", self.home / "settings.json"),
                            ("local", self.project / ".claude/settings.local.json")):
            with self.subTest(layer=layer):
                if (self.project / ".claude").exists():
                    rmtree_force(self.project / ".claude")
                for leftover in (self.home / "settings.json", self.project / ".claude/settings.local.json"):
                    if leftover.exists():
                        leftover.unlink()
                self.make_vendored()
                sha = self.preview_sha()
                write_json(path, registers_bash_gate)  # the plan the operator saw would now add one fewer
                before = snapshot(self.tmp)
                result = self.apply(sha)
                self.assertRefused(result, "changed-since-preview",
                                   "the %s layer changed what would be written" % layer)
                self.assertTreeSame(before, "nothing is written")
                fresh = self.apply(self.preview_sha())
                self.assertEqual(fresh.get("status"), "applied",
                                 msg="POSITIVE CONTROL: a fresh preview of the changed state applies; got %r" % fresh)
                self.assertEqual(len(flat_registrations(self.read_settings())), 16,
                                 msg="16: the user-registered bash-gate.py is not added again")

    def test_a_source_hooks_json_change_between_preview_and_apply_is_refused(self):
        self.make_vendored(own_hooks_json=hooks_json_obj(only={"concept-gate.py", "bash-gate.py"}))
        sha = self.preview_sha()
        (self.project / ".claude/hooks/hooks.json").write_text(
            json.dumps(hooks_json_obj(only={"concept-gate.py"})), encoding="utf-8")
        before = snapshot(self.tmp)
        self.assertRefused(self.apply(sha), "changed-since-preview", "the source of the registrations changed")
        self.assertTreeSame(before, "nothing is written")
        fresh = self.apply(self.preview_sha())
        self.assertEqual(fresh.get("status"), "applied", msg="POSITIVE CONTROL: the fresh preview applies; got %r" % fresh)
        self.assertEqual(len(flat_registrations(self.read_settings())), 1, msg="only the one source registration")

    def test_a_project_settings_change_between_preview_and_apply_is_still_refused(self):
        self.make_vendored()
        write_json(self.settings_path(), {"model": "opus"})
        sha = self.preview_sha()
        write_json(self.settings_path(), {"model": "sonnet"})
        before = snapshot(self.tmp)
        self.assertRefused(self.apply(sha), "changed-since-preview", "the project settings changed")
        self.assertTreeSame(before, "nothing is written")

    def test_a_hooks_apply_given_the_input_hash_instead_of_the_plan_hash_is_refused(self):
        self.make_vendored()
        write_json(self.settings_path(), {"model": "opus"})
        plan = self.plan()
        self.assertRegex(str(plan.get("plan-sha256")), HEX64, msg="the preview must offer a plan hash")
        before = snapshot(self.tmp)
        result = self.apply(self.need(plan, "source-sha256"))
        self.assertRefused(result, "changed-since-preview",
                           "--expect-sha256 for a hooks apply is plan-sha256, never source-sha256")
        self.assertTreeSame(before, "nothing is written")


# ======================================================================================
# 7. Readiness (plugin install)
# ======================================================================================
class TestReadiness(Base):
    def report(self, platform="win32"):
        r = fi.readiness_report(self.project, claude_home=self.home, plugin_root=self.plugin, platform=platform)
        self.need(r, "ready", "a ReadinessReport always says ready or not")
        return r

    def test_a_healthy_install_is_ready_to_load(self):
        self.install_plugin()
        r = self.report()
        self.assertIs(r["ready"], True, msg="installed, enabled, resolvable, compiling, launcher found; %r" % r)
        self.assertEqual(r.get("hooks-registered"), 17, msg="17 registrations in the plugin's hooks.json")
        self.assertEqual(r.get("unresolved-commands"), [], msg="every command resolves to a file")
        self.assertIs(r.get("interpreter-found"), True, msg="the launcher is on PATH")
        self.assertIs(r.get("manifest-hooks-resolves"), True,
                      msg="the install path's plugin.json hooks field resolves to a file")
        self.assertIs(r.get("hooks-compile"), True, msg="every hook compiles")
        self.assertIs(r.get("disable-all-hooks"), False, msg="no layer disables the hooks")
        self.assertEqual(r.get("installed-version"), "0.3.0", msg="read from the record")
        self.assertEqual(r.get("marketplace-version"), "0.3.0", msg="read from the marketplace clone")
        self.assertEqual(Path(self.need(r, "install-path")), self.plugin, msg="the install path")

    def test_plan_hooks_on_a_plugin_install_returns_the_report_and_writes_nothing(self):
        self.install_plugin()
        before = snapshot(self.tmp)
        r = self.plan()
        self.assertIn("ready", r, msg="the hooks step of a plugin install is a ReadinessReport")
        self.assertIn("not-verifiable", r, msg="with its fixed list")
        self.assertTreeSame(before, "a plugin install touches no file (and compiling leaves no .pyc)")

    def test_an_unresolved_command_is_reported(self):
        self.install_plugin()
        (self.plugin / ".claude/hooks/memory-pager.py").unlink()
        r = self.report()
        self.assertTrue(any("memory-pager.py" in c for c in self.need(r, "unresolved-commands")),
                        msg="the command whose file is gone is named")
        self.assertIs(r["ready"], False, msg="an unresolved command is not ready")

    def test_a_hook_that_does_not_compile_is_reported_and_leaves_no_pyc(self):
        self.install_plugin()
        (self.plugin / ".claude/hooks/bash-gate.py").write_text("def (:\n", encoding="utf-8")
        before = snapshot(self.plugin)
        r = self.report()
        self.assertIs(r.get("hooks-compile"), False, msg="a syntax error")
        self.assertTrue(any("bash-gate.py" in f for f in self.need(r, "compile-failures")),
                        msg="the failing file is named")
        self.assertIs(r["ready"], False, msg="not ready")
        self.assertEqual(snapshot(self.plugin), before, msg="compiled in memory: no __pycache__ written")

    def test_disable_all_hooks_in_any_layer_is_reported(self):
        self.install_plugin()
        write_json(self.project / ".claude/settings.local.json", {"disableAllHooks": True})
        r = self.report()
        self.assertIs(r.get("disable-all-hooks"), True, msg="the local layer disables every hook")
        self.assertIs(r["ready"], False, msg="not ready")

    def test_a_version_mismatch_is_reported(self):
        self.install_plugin(version="0.2.0", marketplace_version="0.3.0")
        r = self.report()
        self.assertEqual(r.get("installed-version"), "0.2.0", msg="the installed copy is behind")
        self.assertEqual(r.get("marketplace-version"), "0.3.0", msg="what the marketplace clone declares")
        self.assertIs(r["ready"], False, msg="drift means not ready")

    def test_a_missing_launcher_is_reported(self):
        self.install_plugin()
        self.which_missing = {"py"}  # every other name is found: only the launcher the commands name matters
        r = self.report()
        self.assertIn("py", self.which_calls, msg="the launcher named by the commands (py) was looked up")
        self.assertIs(r.get("interpreter-found"), False, msg="py is not on PATH")
        self.assertIs(r["ready"], False, msg="no launcher means every hook fails open")

    def test_a_plugin_manifest_hooks_field_that_does_not_resolve_is_reported(self):
        self.install_plugin()
        manifest = self.plugin / ".claude-plugin/plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["hooks"] = "./.claude/hooks/no-such-hooks.json"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        r = self.report()
        self.assertIs(r.get("manifest-hooks-resolves"), False,
                      msg="plugin.json points at a hooks file that does not exist")
        self.assertIs(r["ready"], False, msg="Claude Code would load no hook from it: not ready")

    def test_a_posix_host_under_a_plugin_install_is_not_ready_and_carries_a_platform_note(self):
        self.install_plugin()
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform):
                r = self.report(platform=platform)
                self.assertIs(r["ready"], False, msg="the cached hooks.json launches py -3")
                note = r.get("platform-note")
                self.assertIsInstance(note, str, msg="a dedicated platform-note field is present")
                self.assertTrue(note.strip(), msg="and it is not empty")
        windows = self.report(platform="win32")
        self.assertIs(windows["ready"], True, msg="the same healthy install is ready on win32")
        self.assertFalse(windows.get("platform-note"),
                         msg="the platform-note is absent or empty on win32 (None, '' or missing)")

    def test_a_second_registration_in_the_project_is_reported_as_duplicate(self):
        self.install_plugin()
        self.assertIs(self.report().get("duplicate-vendored-registration"), False, msg="none yet")
        write_json(self.settings_path(), {"hooks": {"PreToolUse": [{"matcher": "Edit|Write|MultiEdit", "hooks": [
            {"type": "command", "command": "py", "args": ["-3", "/x/hooks/concept-gate.py"]}]}]}})
        r = self.report()
        self.assertIs(r.get("duplicate-vendored-registration"), True, msg="the same key registered twice")

    # --- round two: W6 mode, M16 'ready to load' and never 'live', M25/M26, M23 ----------------------
    def test_the_report_carries_the_install_mode(self):
        self.install_plugin()
        self.assertEqual(self.report().get("mode"), "plugin", msg="a readiness report is for a plugin install")
        self.assertEqual(self.plan().get("mode"), "plugin", msg="and plan_hooks hands back the same report")

    @staticmethod
    def strings_in(node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for key, value in node.items():
                yield str(key)
                yield from TestReadiness.strings_in(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                yield from TestReadiness.strings_in(item)

    def test_a_healthy_report_says_ready_to_load_and_nothing_in_it_says_live(self):
        self.install_plugin()
        r = self.report()
        self.assertIs(r["ready"], True, msg="fixture sanity: a healthy install")
        self.assertIn("ready to load", str(r.get("verdict")).lower(),
                      msg="the verdict claims 'ready to load', which is all a script can know")
        live = [s for s in self.strings_in(r) if re.search(r"\blive\b", s, re.I)]
        self.assertEqual(live, [], msg="no string anywhere in the report may claim 'live'; found %r" % live)
        for platform in ("linux", "darwin"):
            live = [s for s in self.strings_in(self.report(platform=platform)) if re.search(r"\blive\b", s, re.I)]
            self.assertEqual(live, [], msg="nor on %s" % platform)

    def test_a_report_that_is_not_ready_does_not_say_ready_to_load(self):
        self.install_plugin()
        write_json(self.project / ".claude/settings.local.json", {"disableAllHooks": True})
        r = self.report()
        self.assertIs(r["ready"], False, msg="fixture sanity")
        self.assertNotIn("ready to load", str(r.get("verdict")).lower(), msg="a not-ready report must not claim it")

    def test_disable_all_hooks_in_the_user_layer_is_reported(self):
        self.install_plugin()
        user = self.home / "settings.json"
        data = json.loads(user.read_text(encoding="utf-8"))
        data["disableAllHooks"] = True
        write_json(user, data)
        r = self.report()
        self.assertIs(r.get("disable-all-hooks"), True, msg="the USER layer disables every hook")
        self.assertIs(r["ready"], False, msg="not ready")

    def test_a_duplicate_registration_in_the_local_layer_is_reported(self):
        self.install_plugin()
        write_json(self.project / ".claude/settings.local.json", {"hooks": {"PreToolUse": [{
            "matcher": "Edit|Write|MultiEdit", "hooks": [
                {"type": "command", "command": "py", "args": ["-3", "/x/hooks/concept-gate.py"]}]}]}})
        r = self.report()
        self.assertIs(r.get("duplicate-vendored-registration"), True,
                      msg="the same key registered in the LOCAL layer runs every hook twice")
        self.assertIs(r["ready"], False, msg="not ready")

    def test_a_template_name_beside_a_real_one_reads_as_configured(self):
        self.install_plugin()
        rules = self.plugin / ".claude/hooks/db-destructive-guard.rules.json"
        rules.write_text(json.dumps({"protected_databases": ["AcmeApp", "RealDb"]}), encoding="utf-8")
        self.assertEqual(self.report().get("database-guard-rules"), "configured",
                         msg="one real database name is enough: the rules are the project's own")

    def test_kill_switches_are_read_from_the_hook_sources_without_the_project_dir(self):
        self.install_plugin()
        names = self.need(self.report(), "kill-switches")
        self.assertEqual(set(names), {"CLAUDE_CONCEPT_GATE", "CLAUDE_BASH_GATE", "CLAUDE_ARCH_GUARD"},
                         msg="environ.get(CLAUDE_...) in the hook sources, CLAUDE_PROJECT_DIR excluded")

    def test_the_env_scan_finds_a_planted_variable_and_skips_the_excluded_ones_positive_control(self):
        planted = 'import os\nos.environ.get("CLAUDE_PLANTED_X")\nos.getenv("CLAUDE_PROJECT_DIR")\n'
        self.assertEqual(env_vars_read_by([planted]), {"CLAUDE_PLANTED_X"},
                         msg="POSITIVE CONTROL: the INV-12 scan re-implementation sees a planted "
                             "variable and drops CLAUDE_PROJECT_DIR")
        self.assertEqual(env_vars_read_by(["x = 1\n"]), set(), msg="and finds nothing where there is nothing")

    def test_the_reported_environment_variables_equal_the_inv12_scan_of_the_real_hook_sources(self):
        self.install_plugin(install_path=SCRIPT_ROOT)
        sources = [p.read_text(encoding="utf-8", errors="replace")
                   for p in sorted((SCRIPT_ROOT / ".claude/hooks").glob("*.py"))]
        expected = env_vars_read_by(sources)
        self.assertGreater(len(expected), 5, msg="the real hooks read many CLAUDE_* variables")
        r = fi.readiness_report(self.project, claude_home=self.home, plugin_root=SCRIPT_ROOT, platform="win32")
        self.assertEqual(set(self.need(r, "kill-switches", "the variables read from the hook sources")),
                         expected,
                         msg="the report agrees with the scan test_plugin_manifests.py INV-12 runs")

    def test_database_guard_rules_state_takes_all_three_values(self):
        self.install_plugin()
        rules = self.plugin / ".claude/hooks/db-destructive-guard.rules.json"
        seen = {}
        for state, content in (("template-placeholders", {"protected_databases": ["AcmeApp", "AcmeApp_Testing"]}),
                               ("configured", {"protected_databases": ["RealDb"]}),
                               ("absent-fail-closed", {"protected_databases": []})):
            rules.write_text(json.dumps(content), encoding="utf-8")
            seen[state] = self.report().get("database-guard-rules")
        rules.unlink()
        seen["absent-fail-closed (file gone)"] = self.report().get("database-guard-rules")
        self.assertEqual(seen, {"template-placeholders": "template-placeholders", "configured": "configured",
                                "absent-fail-closed": "absent-fail-closed",
                                "absent-fail-closed (file gone)": "absent-fail-closed"},
                         msg="the real state is reported, never a slogan")

    def test_the_not_verifiable_list_and_the_code_search_note_are_always_present(self):
        self.install_plugin()
        healthy = self.report()
        write_json(self.project / ".claude/settings.json", {"disableAllHooks": True})
        not_ready = self.report()
        self.assertIs(healthy["ready"], True, msg="fixture sanity: the first report is a healthy one")
        self.assertIs(not_ready["ready"], False, msg="fixture sanity: the second report is not ready")
        for label, report in (("healthy", healthy), ("not-ready", not_ready)):
            text = " ".join(self.need(report, "not-verifiable")).lower()
            self.assertEqual(len(report["not-verifiable"]), 3,
                             msg="%s: ready is not live, so a fixed list of three is always printed" % label)
            for word in ("session", "trust", "import"):
                self.assertIn(word, text, msg="%s: the list names the session load, the trust prompt "
                                              "and the imports" % label)
            note = self.need(report, "code-search-first-note")
            # Amended by sub-task 24 (hook-server-modes contract, amendment 2026-10-09): the code-search-first
            # check is cut from the plugin, so the note says it was retired and no longer names its bypass.
            for needle in ("CodeGraph", "retired", "block"):
                self.assertIn(needle, note, msg="%s: the code-search-first note must mention %s" % (label, needle))
            self.assertNotIn("CLAUDE_SKIP_CG", note,
                             msg="%s: the retired check's switch is no longer a thing to tell the operator" % label)
            self.assertRegex(note.lower(), r"no longer blocks|nothing to bypass",
                             msg="%s: and say the plugin no longer blocks source reads" % label)


# ======================================================================================
# 8. Command line
# ======================================================================================
class TestCli(Base):
    def test_both_subcommands_exist_with_the_contract_flags(self):
        parser = fi.build_parser()
        ns = parser.parse_args(["profile", "--project", "p", "--json", "--apply", "--expect-sha256", "h",
                                "--claude-home", "c", "--set", "a=b", "--set", "c=d,e"])
        self.assertEqual((ns.command, ns.set, ns.apply, ns.json, ns.expect_sha256),
                         ("profile", ["a=b", "c=d,e"], True, True, "h"),
                         msg="profile: --project --json --apply --expect-sha256 --claude-home --set (repeatable)")
        ns = parser.parse_args(["hooks", "--skip", "x.py", "--skip", "y.py", "--platform", "linux",
                                "--provider", "cursor"])
        self.assertEqual((ns.command, ns.skip, ns.platform, ns.provider), ("hooks", ["x.py", "y.py"], "linux", "cursor"),
                         msg="hooks: --skip (repeatable) --platform --provider")

    def test_json_prints_the_profile_plan_read_from_the_fake_plugins_template(self):
        # The fake template carries a twelfth slot that no real template has, so a lookup that
        # silently read the real worktree's template would not produce it.
        self.set_template(template_text(extra={EXTRA_SLOT: EXTRA_PLACEHOLDER}))
        write_files(self.project, {"src/Api/Api.csproj": "x"})
        self.put_profile()
        rc, out, parsed = self.cli(["profile", "--project", str(self.project), "--json",
                                    "--claude-home", str(self.home)])
        self.assertIsNotNone(parsed, msg="--json prints machine-readable output; got %r" % out)
        self.assertEqual(rc, 0, msg="a plan is exit 0")
        self.assertIn("proposals", parsed, msg="the ProfilePlan is the document")
        self.assertIn("source-sha256", parsed, msg="with the input hash")
        self.assertIn("plan-sha256", parsed, msg="and with plan-sha256, the hash the profile apply needs (W3)")
        self.assertIn(EXTRA_SLOT, [p.get("slot") for p in parsed["proposals"]],
                      msg="the proposal contains the distinguishing slot of CLAUDE_PLUGIN_ROOT's template")

    def test_profile_apply_through_the_command_line_splits_on_the_first_equals_and_on_commas(self):
        self.set_template(template_text(extra={EXTRA_SLOT: EXTRA_PLACEHOLDER}))  # see the plan test above
        p = self.put_profile()
        preview = fi.propose_profile(self.project, claude_home=self.home, plugin_root=self.plugin)
        argv = ["profile", "--project", str(self.project), "--apply", "--json", "--claude-home", str(self.home),
                "--expect-sha256", str(preview.get("plan-sha256"))]  # plan-sha256, not source-sha256 (W3)
        for slot, value in FULL_ANSWERS.items():
            argv += ["--set", "%s=%s" % (slot, value)]
        argv += ["--set", "frontend.roots=web,admin", "--set", "frontend.theme-polarity=web=dark,admin=light",
                 "--set", EXTRA_SLOT + "=docs/runbooks"]
        rc, out, parsed = self.cli(argv)
        self.assertEqual(rc, 0, msg="an apply that wrote is exit 0; output %r" % out)
        self.assertEqual((parsed or {}).get("status"), "applied", msg="reported as applied")
        text = p.read_text(encoding="utf-8")
        self.assertEqual(load_slot(text, EXTRA_SLOT), ("docs/runbooks",),
                         msg="--set on the distinguishing slot was accepted, so the fake template was the source")
        self.assertEqual(load_slot(text, "frontend.theme-polarity"), ("web=dark", "admin=light"),
                         msg="the value keeps its own '=' and splits on commas")
        self.assertEqual(load_slot(text, "frontend.roots"), ("web", "admin"), msg="the later --set wins")

    def test_main_returns_exit_two_for_each_correctable_refusal_and_prints_the_code(self):
        self.make_vendored()
        malformed = self.settings_path()
        base = ["--project", str(self.project), "--json", "--claude-home", str(self.home)]
        cases = (
            ("malformed-settings", lambda: malformed.write_text("{not json", encoding="utf-8"),
             ["hooks", "--platform", "win32"] + base),
            ("provider-has-no-hooks", lambda: malformed.unlink(),
             ["hooks", "--platform", "win32", "--provider", "cursor"] + base),
        )
        for code, prepare, argv in cases:
            with self.subTest(code=code):
                prepare()
                before = snapshot(self.tmp)
                rc, out, parsed = self.cli(argv)
                self.assertIsNotNone(parsed, msg="a refusal is printed as JSON too; got %r" % out)
                self.assertEqual(parsed.get("code"), code, msg="the refusal code")
                self.assertEqual(rc, 2, msg="a correctable refusal is exit 2")
                self.assertTreeSame(before, "nothing is written")

    def test_main_returns_the_exit_code_of_an_environment_refusal(self):
        before = snapshot(self.tmp)
        rc, out, parsed = self.cli(["profile", "--project", str(self.tmp / "nope"), "--json",
                                    "--claude-home", str(self.home)])
        self.assertIsNotNone(parsed, msg="a refusal is printed as JSON; got %r" % out)
        self.assertEqual(parsed.get("code"), "project-unreadable", msg="the refusal code")
        self.assertEqual(rc, 3, msg="an environment problem is exit 3")
        self.assertTreeSame(before, "nothing is written")

    def test_a_hooks_plan_prints_json_and_returns_zero(self):
        self.make_vendored()
        rc, out, parsed = self.cli(["hooks", "--project", str(self.project), "--platform", "linux", "--json",
                                    "--claude-home", str(self.home)])
        self.assertIsNotNone(parsed, msg="--json prints the SettingsPlan; got %r" % out)
        self.assertEqual(rc, 0, msg="a plan is exit 0")
        self.assertEqual(parsed.get("interpreter"), "python3", msg="--platform linux swaps the interpreter")
        self.assertGreater(len(parsed.get("to-add", [])), 0, msg="and lists what would be added")

    def test_a_hooks_apply_through_the_command_line_writes_and_returns_zero(self):
        self.make_vendored()
        plan = self.plan(skip=["memory-pager.py"])  # the plan hash binds --skip, so preview with it
        rc, out, parsed = self.cli(["hooks", "--project", str(self.project), "--platform", "win32", "--apply",
                                    "--json", "--claude-home", str(self.home),
                                    "--expect-sha256", self.need(plan, "plan-sha256"), "--skip", "memory-pager.py"])
        self.assertEqual(rc, 0, msg="an apply that wrote is exit 0; output %r" % out)
        self.assertEqual(len(flat_registrations(self.read_settings())), 16,
                         msg="17 minus the skipped hook, so the apply really ran with --skip")


# ======================================================================================
# 10. Round three (second review pass): W1 cache confinement, W2 this-plugin identity,
#     W3 profile plan hash, W4 symbolic link, W5 strict reads on the plugin path
# ======================================================================================
def make_foreign_plugin(root, manifest_name="some-other-plugin", with_manifest=True):
    """A plugin tree that is NOT agentic-auto-improve (or carries no manifest at all): its hooks.json
    registers concept-gate.py with an extra --evil argument and its template declares one more slot."""
    if Path(root).exists():
        rmtree_force(root)
    root = build_plugin(root)
    manifest = root / ".claude-plugin/plugin.json"
    if with_manifest:
        manifest.write_text(json.dumps({"name": manifest_name, "version": "9.9.9",
                                        "hooks": "./.claude/hooks/hooks.json"}), encoding="utf-8")
    else:
        manifest.unlink()
    hooks_json = root / ".claude/hooks/hooks.json"
    obj = json.loads(hooks_json.read_text(encoding="utf-8"))
    for groups in obj["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                if hook["command"].endswith('concept-gate.py"'):
                    hook["command"] += " --evil"
    hooks_json.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    (root / ".claude/project-profile.md").write_text(
        template_text(extra={EXTRA_SLOT: EXTRA_PLACEHOLDER}), encoding="utf-8")
    return root


class TestRoundThreeRootLookup(Base):
    """W1 and W2: runs the script from a copied-in consumer project in a subprocess, because the
    script's own location is a lookup candidate and in-process that is this very worktree."""

    def consumer(self, with_profile=True):
        if (self.tmp / "consumer").exists():
            rmtree_force(self.tmp / "consumer")
        proj = TestVendoredConsumerReachesThePluginSources.consumer(self)
        if not with_profile:
            (proj / ".claude/project-profile.md").unlink()
        return proj

    def user_cache(self, name="decoy"):
        """A complete, valid plugin in the cache under the REDIRECTED ~/.claude (HOME/USERPROFILE)."""
        return build_plugin(Path(os.environ["USERPROFILE"]) / ".claude/plugins/cache/mkt" / PLUGIN_NAME / "0.3.0")

    def run_consumer(self, proj, argv, home_arg=None, config_dir=None, plugin_root=None):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_CONFIG_DIR")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if config_dir is not None:
            env["CLAUDE_CONFIG_DIR"] = str(config_dir)
        if plugin_root is not None:
            env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
        cmd = [sys.executable, str(proj / ".claude/scripts/auto_improve_finish_install.py")] + argv + [
            "--project", str(proj), "--json"]
        if home_arg is not None:
            cmd += ["--claude-home", str(home_arg)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
        try:
            parsed = json.loads(r.stdout)
        except ValueError:
            parsed = None
        self.assertIsNotNone(parsed, msg="the script must print JSON; stdout %r stderr %r" % (r.stdout, r.stderr))
        return r, parsed

    def assert_within(self, path_text, root, why):
        self.assertTrue(path_text, msg="%s: the result names no path" % why)
        self.assertTrue(fi._is_within(Path(path_text), Path(root)) if hasattr(fi, "_is_within")
                        else str(Path(path_text).resolve()).startswith(str(Path(root).resolve())),
                        msg="%s: %s must lie under %s" % (why, path_text, root))

    # --- W1: the cache lookup stays inside the named Claude home ---------------------------------
    def test_w1_hooks_json_is_not_taken_from_the_real_home_cache_when_another_home_is_named(self):
        proj = self.consumer()
        decoy = self.user_cache()
        self.assertTrue((decoy / ".claude/hooks/hooks.json").is_file(), msg="fixture sanity: the decoy has hooks.json")
        self.assertFalse(list(self.home.glob("plugins/cache/*")), msg="fixture sanity: the named home has no cache")
        for label, home_arg, config_dir in (("--claude-home", self.home, None),
                                            ("CLAUDE_CONFIG_DIR", None, self.home),
                                            ("both", self.home, self.home)):
            with self.subTest(named_by=label):
                before = snapshot(proj)
                r, parsed = self.run_consumer(proj, ["hooks", "--platform", "win32"], home_arg, config_dir)
                self.assertEqual(parsed.get("code"), "hooks-json-missing",
                                 msg="W1: the decoy under ~/.claude must not be read when %s names a home with "
                                     "no cache; got %r" % (label, parsed))
                self.assertEqual(r.returncode, 3, msg="an environment problem is exit 3")
                self.assertNotIn("to-add", parsed, msg="never a plan sourced from the decoy")
                self.assertEqual(snapshot(proj), before, msg="a refusal writes nothing")

    def test_w1_the_profile_template_is_not_taken_from_the_real_home_cache_when_another_home_is_named(self):
        decoy = self.user_cache()
        for label, home_arg, config_dir in (("--claude-home", self.home, None),
                                            ("CLAUDE_CONFIG_DIR", None, self.home)):
            with self.subTest(named_by=label):
                proj = self.consumer()
                r, parsed = self.run_consumer(proj, ["profile"], home_arg, config_dir)
                self.assertEqual(parsed.get("status"), "plan", msg="the project's own profile is still planned")
                self.assertEqual(parsed.get("missing-row-detection"), "unavailable",
                                 msg="W1: no template may come from the decoy, so missing rows cannot be "
                                     "detected; got %r" % parsed)
                self.assertEqual(parsed.get("rows-to-add"), [], msg="nothing is detected as missing")
                self.assertNotIn(str(decoy), json.dumps(parsed), msg="the decoy is named nowhere in the plan")
                rmtree_force(proj)
        proj = self.consumer(with_profile=False)
        r, parsed = self.run_consumer(proj, ["profile"], self.home, None)
        self.assertEqual(parsed.get("code"), "template-missing",
                         msg="W1: no profile and no template in the named home is template-missing, not a "
                             "plan from the decoy; got %r" % parsed)
        self.assertEqual(r.returncode, 3, msg="an environment problem is exit 3")

    def test_w1_control_without_a_named_home_the_default_cache_is_searched_and_the_root_is_named(self):
        decoy = self.user_cache()
        proj = self.consumer()
        r, parsed = self.run_consumer(proj, ["hooks", "--platform", "win32"])
        self.assertEqual(parsed.get("status"), "plan",
                         msg="POSITIVE CONTROL: with no --claude-home and no CLAUDE_CONFIG_DIR, ~/.claude is "
                             "the Claude home and its cache is searched; got %r" % parsed)
        self.assertEqual(len(parsed.get("to-add", [])), 17, msg="all 17 registrations come from the cached copy")
        self.assert_within(parsed.get("hooks-json"), decoy, "the hooks.json that was read")
        r, parsed = self.run_consumer(proj, ["profile"])
        self.assertEqual(parsed.get("missing-row-detection"), "available", msg="the cached template is found")
        self.assertEqual(Path(str(parsed.get("plugin-root"))).resolve(), decoy.resolve(),
                         msg="the result names the chosen root under the plugin-root key")

    # --- W2: a candidate must be THIS plugin ---------------------------------------------------------
    FOREIGN_CASES = (("a manifest naming another plugin", dict(manifest_name="some-other-plugin")),
                     ("no manifest file at all", dict(with_manifest=False)))

    def test_w2_a_claude_plugin_root_that_is_another_plugin_is_skipped_for_the_cache(self):
        proj = self.consumer()
        cached = self.user_cache()
        for label, kwargs in self.FOREIGN_CASES:
            with self.subTest(foreign=label):
                foreign = make_foreign_plugin(self.tmp / "foreign", **kwargs)
                r, parsed = self.run_consumer(proj, ["hooks", "--platform", "win32"], plugin_root=foreign)
                self.assertEqual(parsed.get("status"), "plan",
                                 msg="the lookup falls through to the cache; got %r" % parsed)
                self.assertFalse(any("--evil" in json.dumps(reg) for reg in parsed.get("to-add", [])),
                                 msg="W2: the other plugin's --evil registration must never reach the plan")
                self.assert_within(parsed.get("hooks-json"), cached, "hooks.json comes from the cached copy")
                r, parsed = self.run_consumer(proj, ["profile"], plugin_root=foreign)
                self.assertNotIn(EXTRA_SLOT, [p.get("slot") for p in parsed.get("proposals", [])],
                                 msg="W2: the other plugin's template must not be the source")
                self.assertEqual(Path(str(parsed.get("plugin-root"))).resolve(), cached.resolve(),
                                 msg="the chosen root is the cached copy, named in the result")
                rmtree_force(foreign)

    def test_w2_a_claude_plugin_root_that_is_another_plugin_gives_hooks_json_missing_when_nothing_follows(self):
        proj = self.consumer()
        for label, kwargs in self.FOREIGN_CASES:
            with self.subTest(foreign=label):
                foreign = make_foreign_plugin(self.tmp / "foreign", **kwargs)
                before = snapshot(proj)
                r, parsed = self.run_consumer(proj, ["hooks", "--platform", "win32"], home_arg=self.home,
                                              config_dir=self.home, plugin_root=foreign)
                self.assertEqual(parsed.get("code"), "hooks-json-missing",
                                 msg="W2: with no other candidate the foreign hooks.json must not be used; "
                                     "got %r" % parsed)
                self.assertNotIn("--evil", json.dumps(parsed), msg="the --evil registration reaches nothing")
                self.assertEqual(snapshot(proj), before, msg="a refusal writes nothing")
                rmtree_force(foreign)

    def test_w2_control_the_same_tree_naming_this_plugin_is_accepted(self):
        proj = self.consumer()
        foreign = make_foreign_plugin(self.tmp / "same-tree", manifest_name=PLUGIN_NAME)
        r, parsed = self.run_consumer(proj, ["hooks", "--platform", "win32"], home_arg=self.home,
                                      config_dir=self.home, plugin_root=foreign)
        self.assertEqual(parsed.get("status"), "plan",
                         msg="POSITIVE CONTROL: a manifest naming agentic-auto-improve is accepted; got %r" % parsed)
        self.assertTrue(any("--evil" in json.dumps(reg) for reg in parsed.get("to-add", [])),
                        msg="so its registrations (the --evil one included) are the source")
        self.assert_within(parsed.get("hooks-json"), foreign, "hooks.json comes from that root")
        r, parsed = self.run_consumer(proj, ["profile"], home_arg=self.home, config_dir=self.home,
                                      plugin_root=foreign)
        self.assertIn(EXTRA_SLOT, [p.get("slot") for p in parsed.get("proposals", [])],
                      msg="and its template is the source")
        self.assertEqual(Path(str(parsed.get("plugin-root"))).resolve(), foreign.resolve(),
                         msg="the result names the chosen root")


class TestRoundThreeProfilePlanHash(Base):
    """W3: a profile apply is bound to the whole planned output, so a template that moves between
    preview and apply is caught."""

    def preview(self, **kw):
        return fi.propose_profile(self.project, claude_home=self.home, plugin_root=self.plugin)

    def test_w3_the_profile_plan_carries_plan_sha256_beside_source_sha256(self):
        p = self.put_profile()
        plan = self.preview()
        self.assertRegex(str(plan.get("plan-sha256")), HEX64, msg="plan-sha256 is a SHA-256 hex digest")
        self.assertEqual(plan.get("source-sha256"), sha_of(p), msg="source-sha256 stays the input-bytes hash")
        self.assertNotEqual(plan.get("plan-sha256"), plan.get("source-sha256"),
                            msg="the plan hash binds more than the profile bytes")
        p.unlink()
        absent = self.preview()
        self.assertEqual(absent.get("source-sha256"), "absent", msg="no profile: the input hash is 'absent'")
        self.assertRegex(str(absent.get("plan-sha256")), HEX64, msg="an absent profile has a plan hash too")

    def test_w3_the_input_hash_is_no_longer_accepted_by_a_profile_apply(self):
        p = self.put_profile()
        plan = self.preview()
        self.need(plan, "plan-sha256", "the preview reports the hash the apply needs")
        before = snapshot(self.tmp)
        result = fi.apply_profile(self.project, dict(FULL_ANSWERS), plan.get("source-sha256"),
                                  claude_home=self.home, plugin_root=self.plugin)
        self.assertRefused(result, "changed-since-preview",
                           "--expect-sha256 for a profile apply must equal plan-sha256, not source-sha256")
        self.assertTreeSame(before, "nothing is written")
        self.assertEqual(sha_of(p), plan.get("source-sha256"), msg="the profile is untouched")

    def test_w3_the_same_preview_and_apply_pair_succeeds(self):
        p = self.put_profile()
        plan = self.preview()
        result = fi.apply_profile(self.project, dict(FULL_ANSWERS), self.need(plan, "plan-sha256"),
                                  claude_home=self.home, plugin_root=self.plugin)
        self.assertEqual(result.get("status"), "applied",
                         msg="POSITIVE CONTROL: the hash of an unchanged preview is accepted; got %r" % result)
        self.assertEqual(load_slot(p.read_text(encoding="utf-8"), "project.name"), ("widget",),
                         msg="and the answers were written")

    def test_w3_a_template_that_changes_between_preview_and_apply_is_refused(self):
        target = self.project / ".claude/project-profile.md"
        self.assertFalse(target.exists(), msg="fixture sanity: no profile, so the template is the base text")
        plan = self.preview()
        stale = self.need(plan, "plan-sha256", "the preview reports the plan hash")
        self.set_template(template_text() + "\nA paragraph a newer plugin version added about runbooks.\n")
        before = snapshot(self.tmp)
        result = fi.apply_profile(self.project, dict(FULL_ANSWERS), stale, claude_home=self.home,
                                  plugin_root=self.plugin)
        self.assertRefused(result, "changed-since-preview",
                           "the template the operator previewed is not the template the apply would start from")
        self.assertTreeSame(before, "nothing is written")
        self.assertFalse(target.exists(), msg="the profile was not created from the changed template")

    def test_w3_for_an_absent_profile_the_plan_hash_moves_with_the_template(self):
        first = self.need(self.preview(), "plan-sha256")
        self.assertRegex(str(first), HEX64, msg="a SHA-256 hex digest")
        self.set_template(template_text() + "\nExtra prose.\n")
        second = self.need(self.preview(), "plan-sha256")
        self.assertNotEqual(first, second, msg="W3: the plan hash is not a constant for an absent profile")
        self.set_template(template_text())
        self.assertEqual(self.need(self.preview(), "plan-sha256"), first,
                         msg="and it is deterministic: the original template gives the original hash")

    def test_w3_a_changed_existing_profile_moves_the_plan_hash_and_is_refused(self):
        p = self.put_profile()
        plan = self.preview()
        stale = self.need(plan, "plan-sha256")
        self.put_profile(template_text({"backend.roots": "`src/Other`"}))
        moved = self.preview()
        self.assertNotEqual(moved.get("plan-sha256"), stale, msg="the plan hash binds the profile bytes")
        before = snapshot(self.tmp)
        result = fi.apply_profile(self.project, {k: v for k, v in FULL_ANSWERS.items() if k != "backend.roots"},
                                  stale, claude_home=self.home, plugin_root=self.plugin)
        self.assertRefused(result, "changed-since-preview", "the profile changed after the preview")
        self.assertTreeSame(before, "nothing is written")
        self.assertTrue(p.is_file(), msg="the edited profile is still there")

    def test_w3_the_command_line_profile_apply_takes_plan_sha256(self):
        self.put_profile()
        base = ["profile", "--project", str(self.project), "--json", "--claude-home", str(self.home)]
        rc, out, plan = self.cli(base)
        self.assertEqual(rc, 0, msg="a plan is exit 0")
        self.assertRegex(str((plan or {}).get("plan-sha256")), HEX64, msg="the CLI plan prints plan-sha256")
        sets = []
        for slot, value in FULL_ANSWERS.items():
            sets += ["--set", "%s=%s" % (slot, value)]
        before = snapshot(self.tmp)
        rc, out, parsed = self.cli(base + ["--apply", "--expect-sha256", plan.get("source-sha256")] + sets)
        self.assertEqual(rc, 2, msg="the input hash is a correctable refusal; output %r" % out)
        self.assertEqual((parsed or {}).get("code"), "changed-since-preview", msg="the profile apply wants plan-sha256")
        self.assertTreeSame(before, "nothing is written")
        rc, out, parsed = self.cli(base + ["--apply", "--expect-sha256", plan.get("plan-sha256")] + sets)
        self.assertEqual(rc, 0, msg="the plan hash is accepted; output %r" % out)
        self.assertEqual((parsed or {}).get("status"), "applied", msg="reported as applied")


class TestRoundThreeSymbolicLinkSettings(Base):
    """W4: settings.json that is a symbolic link is never written through or over."""

    def linked_settings(self):
        self.make_vendored()
        real = self.tmp / "elsewhere" / "real-settings.json"
        write_json(real, {"model": "opus"})
        link = self.settings_path()
        try:
            os.symlink(str(real), str(link))
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest("this account cannot create symbolic links: %s" % exc)
        self.assertTrue(os.path.islink(str(link)), msg="fixture sanity: settings.json is a symbolic link")
        return real, link

    def test_w4_a_plan_through_a_symbolic_link_still_works_and_writes_nothing(self):
        real, link = self.linked_settings()
        before = snapshot(self.tmp)
        plan = self.plan()
        self.assertEqual(plan.get("status"), "plan", msg="a plan is read-only, so a link is fine; got %r" % plan)
        self.assertEqual(plan.get("source-sha256"), sha_of(real), msg="it read the file the link points to")
        self.assertRegex(str(plan.get("plan-sha256")), HEX64, msg="with its plan hash")
        self.assertTreeSame(before, "a plan writes nothing")
        self.assertTrue(os.path.islink(str(link)), msg="and the link is still a link")

    def test_w4_an_apply_over_a_symbolic_link_is_write_failed_and_changes_nothing(self):
        real, link = self.linked_settings()
        sha = self.preview_sha()
        real_bytes, target_text = real.read_bytes(), os.readlink(str(link))
        before = snapshot(self.tmp)
        result = self.apply(sha)
        self.assertRefused(result, "write-failed", "a link must not be written through or replaced")
        self.assertRegex(result.get("message", ""), r"(?i)symbolic link",
                         msg="W4: the message says why: it is a symbolic link")
        self.assertTrue(os.path.islink(str(link)), msg="the link is still a link, not a regular file")
        self.assertEqual(os.readlink(str(link)), target_text, msg="and still points to the same target")
        self.assertEqual(real.read_bytes(), real_bytes, msg="the target is byte-identical")
        self.assertTreeSame(before, "no backup and no temporary file is left")
        leftovers = [n for n in os.listdir(str(self.project / ".claude")) if ".bak-" in n or ".tmp-" in n]
        self.assertEqual(leftovers, [], msg="no stray backup or temporary file beside the link")


class TestRoundThreeStrictReadsOnThePluginPath(Base):
    """W5: under a plugin install every settings layer is read strictly by mode detection, the
    readiness report and the hooks plan."""

    def fresh_install(self):
        if (self.project / ".claude").exists():
            rmtree_force(self.project / ".claude")
        (self.home / "settings.json").unlink() if (self.home / "settings.json").exists() else None
        return self.install_plugin()

    def layer_paths(self):
        return {"user": self.home / "settings.json", "project": self.project / ".claude/settings.json",
                "local": self.project / ".claude/settings.local.json"}

    def entry_points(self):
        return (("detect_install_mode", self.mode),
                ("readiness_report", lambda: fi.readiness_report(
                    self.project, claude_home=self.home, plugin_root=self.plugin, platform="win32")),
                ("plan_hooks", self.plan))

    def assert_all_refuse(self, path, code, why):
        before = snapshot(self.tmp)
        for label, call in self.entry_points():
            result = call()
            self.assertRefused(result, code, "%s (%s)" % (why, label))
            self.assertEqual(Path(result.get("path", "")).resolve(), path.resolve(),
                             msg="%s names the file that failed (%s); got %r" % (label, path, result))
        self.assertTreeSame(before, why)

    def test_w5_a_malformed_settings_layer_is_refused_naming_that_file(self):
        for layer in ("user", "project", "local"):
            with self.subTest(layer=layer):
                self.fresh_install()
                path = self.layer_paths()[layer]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"{not json")
                self.assert_all_refuse(path, "malformed-settings",
                                       "a malformed %s layer must not be read as 'nothing enabled' or 'ready'" % layer)

    def test_w5_a_settings_layer_of_the_wrong_shape_is_refused(self):
        for layer in ("user", "project", "local"):
            with self.subTest(layer=layer):
                key = self.fresh_install()
                path = self.layer_paths()[layer]
                data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                data["hooks"] = {"PreToolUse": {}}
                write_json(path, data)
                self.assertIn(key, json.dumps(json.loads((self.home / "settings.json").read_text(encoding="utf-8"))),
                              msg="fixture sanity: the plugin is still enabled in the user layer")
                self.assert_all_refuse(path, "unexpected-settings-shape",
                                       "a %s layer whose hooks are not event -> list of groups" % layer)

    def test_w5_control_valid_layers_give_the_normal_verdicts(self):
        key = self.fresh_install()
        write_json(self.project / ".claude/settings.json", {"model": "opus", "hooks": {"Stop": []}})
        write_json(self.project / ".claude/settings.local.json", {"hooks": {}})
        user = json.loads((self.home / "settings.json").read_text(encoding="utf-8"))
        user["hooks"] = {"Stop": [{"hooks": []}]}
        write_json(self.home / "settings.json", user)
        verdict = self.mode()
        self.assertEqual(verdict.get("mode"), "plugin", msg="POSITIVE CONTROL: valid layers, a plugin install")
        self.assertIs(verdict.get("enabled"), True, msg="enabledPlugins[%s] is true" % key)
        report = fi.readiness_report(self.project, claude_home=self.home, plugin_root=self.plugin, platform="win32")
        self.assertIs(report.get("ready"), True, msg="and the report is ready; got %r" % report)


if __name__ == "__main__":
    unittest.main(verbosity=1)
