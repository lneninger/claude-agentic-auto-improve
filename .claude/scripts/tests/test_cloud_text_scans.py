#!/usr/bin/env python3
"""
Cloud text scans over agents/cloud-engineer.md (when present) and skills/cloud-engineering/.

Contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md, Reused Mechanisms row "Live cloud
changes" and sub-task 6. The cloud skill and agent never run a deploy, apply, create, update or destroy command
against a live environment. They write the command out for the user to run. This scan pins that rule in the
shipped text:

  (1) Every line that carries one of the mutating verbs (apply, create, update, destroy, delete, deploy,
      install, upgrade, uninstall, push) as a command sits inside a fenced block that is introduced by a label
      line saying "for the user to run". A line is a command when it names a cloud or container tool before the
      verb, or when it sits inside any code fence.
  (2) The skill states the scope rule, halts with one line when cloud.providers is unset, and ships one
      reference per provider and tool.
  (3) Prose sentences are 35 words or fewer.

Every scan has a POSITIVE CONTROL: a planted line the scan must report. Mutating phrases in this file are built
from parts so this file never holds a command line literally.

Run: py -3 .claude/scripts/tests/test_cloud_text_scans.py
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = PLUGIN_ROOT / "skills" / "cloud-engineering"
AGENT_FILE = PLUGIN_ROOT / "agents" / "cloud-engineer.md"

REFERENCES = ("cross-cutting", "azure", "aws", "gcp", "terraform", "bicep", "docker", "kubernetes")
TOOLS = ("terraform", "tofu", "az", "azd", "aws", "gcloud", "gsutil", "kubectl", "helm", "kustomize",
         "docker", "bicep", "eksctl", "npm", "pip", "git", "gh")
VERBS = ("app" + "ly", "cre" + "ate", "upd" + "ate", "des" + "troy", "del" + "ete", "dep" + "loy",
         "inst" + "all", "upg" + "rade", "unin" + "stall", "pu" + "sh")

VERB_RE = re.compile(r"(?<![\w-])(?:%s)(?![a-z])" % "|".join(VERBS), re.I)
TOOL_RE = re.compile(r"(?<![\w-])(?:%s)(?![\w-])" % "|".join(TOOLS))
FENCE_RE = re.compile(r"^\s*(```|~~~)")
LABEL_RE = re.compile(r"for the user to run", re.I)
SENTENCE_LIMIT = 35


def mutating_violations(text: str) -> list[str]:
    """Lines that present a mutating command outside a block labelled "for the user to run"."""
    lines = text.splitlines()
    bad: list[str] = []
    in_fence = False
    in_user_block = False
    pending_label = False
    for line in lines:
        if FENCE_RE.match(line):
            if in_fence:
                in_fence = False
                in_user_block = False
            else:
                in_fence = True
                in_user_block = pending_label
            pending_label = False
            continue
        if in_fence:
            if not in_user_block and VERB_RE.search(line):
                bad.append(line.strip())
            continue
        if LABEL_RE.search(line):
            pending_label = True
            continue
        if line.strip():
            pending_label = False
        m = VERB_RE.search(line)
        if m:
            tool = TOOL_RE.search(line)
            if tool and tool.start() < m.start():
                bad.append(line.strip())
    return bad


def long_sentences(text: str) -> list[str]:
    """Prose sentences longer than the limit. Fenced blocks, tables and front matter are skipped."""
    found: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or line.lstrip().startswith("|") or line.startswith("---"):
            continue
        for sentence in re.split(r"(?<=[.!?:;])\s+", re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line)):
            if len(sentence.split()) > SENTENCE_LIMIT:
                found.append(sentence.strip())
    return found


def scanned_files() -> list[Path]:
    files = sorted(p for p in SKILL_DIR.rglob("*.md") if p.is_file())
    if AGENT_FILE.is_file():
        files.append(AGENT_FILE)
    return files


def rel(path: Path) -> str:
    return path.relative_to(PLUGIN_ROOT).as_posix()


class TestMutatingCommandsOnlyInUserBlocks(unittest.TestCase):
    PLANTED = "terraform " + VERBS[0]
    LABEL = "**For the user to run**"

    def test_control_a_planted_line_outside_a_block_is_caught(self):
        self.assertTrue(mutating_violations("Run %s now" % self.PLANTED), "control: prose command must be reported")
        self.assertTrue(mutating_violations("aws cloudformation %s-stack --stack-name x" % VERBS[4]),
                        "control: hyphenated verb form must be reported")
        self.assertTrue(mutating_violations("```bash\n%s\n```" % self.PLANTED),
                        "control: an unlabelled fenced command must be reported")
        self.assertTrue(mutating_violations("%s\n\nSome prose.\n```bash\n%s\n```" % (self.LABEL, self.PLANTED)),
                        "control: a label separated from the fence by prose does not exempt it")

    def test_control_a_labelled_block_is_exempt_and_other_text_is_spared(self):
        self.assertEqual(mutating_violations("%s\n\n```bash\n%s\n```" % (self.LABEL, self.PLANTED)), [])
        self.assertEqual(mutating_violations("It never runs a %s or %s command." % (VERBS[5], VERBS[0])), [],
                         "control: prose without a tool name is not a command")
        self.assertEqual(mutating_violations("terraform plan -lock=false\nkubectl diff -f x.yaml"), [],
                         "control: non-mutating commands are spared")
        self.assertEqual(mutating_violations("az deployment group what-if"), [],
                         "control: 'deployment' is not the deploy verb")

    def test_control_the_block_ends_at_the_closing_fence(self):
        text = "%s\n```bash\n%s\n```\n```bash\n%s\n```" % (self.LABEL, self.PLANTED, self.PLANTED)
        self.assertEqual(len(mutating_violations(text)), 1, "control: only the second, unlabelled block is reported")

    def test_shipped_cloud_text_never_presents_a_mutating_command_as_something_to_run(self):
        files = scanned_files()
        self.assertGreater(len(files), 0, "the scan must have read at least one cloud file")
        offenders = []
        for path in files:
            for line in mutating_violations(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append("%s: %s" % (rel(path), line))
        self.assertEqual(offenders, [],
                         "mutating commands may appear only inside a block labelled 'for the user to run'")


class TestSkillShape(unittest.TestCase):
    def skill(self) -> str:
        path = SKILL_DIR / "SKILL.md"
        self.assertTrue(path.is_file(), "skills/cloud-engineering/SKILL.md must exist")
        return path.read_text(encoding="utf-8")

    def test_every_reference_exists(self):
        for name in REFERENCES:
            self.assertTrue((SKILL_DIR / "references" / (name + ".md")).is_file(), "missing reference " + name)

    def test_scope_rule_and_halt_line_are_stated(self):
        text = self.skill()
        for needle in ("cloud.providers", "cloud.iac", "for the user to run", "never runs", "permission prompts"):
            self.assertIn(needle, text, "SKILL.md must mention %r" % needle)
        head = "\n".join(text.splitlines()[:40])
        self.assertIn("never runs", head, "the scope rule must sit near the top of SKILL.md")

    def test_skill_names_each_reference_it_may_open(self):
        text = self.skill()
        for name in REFERENCES:
            self.assertIn("references/%s.md" % name, text, "SKILL.md must route to references/%s.md" % name)

    def test_provider_and_tool_references_carry_ready_verification_steps(self):
        for name in REFERENCES[1:]:
            text = (SKILL_DIR / "references" / (name + ".md")).read_text(encoding="utf-8")
            self.assertIn('"results"', text, "%s.md must carry ready verification step entries" % name)
            self.assertIn("exit-code", text, "%s.md steps must read the exit code" % name)

    def test_cross_cutting_covers_every_topic(self):
        text = (SKILL_DIR / "references" / "cross-cutting.md").read_text(encoding="utf-8").lower()
        for topic in ("networking", "identity and access", "secrets", "messaging", "storage", "observability",
                      "cost", "governance", "deployment validation", "troubleshooting"):
            self.assertIn("## " + topic, text, "cross-cutting.md must have a section on " + topic)


class TestPlainLanguage(unittest.TestCase):
    def test_control_a_long_sentence_is_caught(self):
        self.assertTrue(long_sentences(" ".join(["word"] * 40) + "."))
        self.assertFalse(long_sentences("Short sentence. Another short one."))

    def test_sentences_are_35_words_or_fewer(self):
        files = scanned_files()
        self.assertGreater(len(files), 0)
        offenders = ["%s: %s" % (rel(p), s) for p in files
                     for s in long_sentences(p.read_text(encoding="utf-8", errors="replace"))]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
