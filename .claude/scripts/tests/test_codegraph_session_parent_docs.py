#!/usr/bin/env python3
"""
Wording checks for issue #271 (contract 2026-11-06-session-folder-owner-and-tool-named, "Shipped text the reversal
makes false"): every shipped sentence the move to the Per-user session parent and the fail-closed reversal makes false is
edited where it stands, and the two exception sentences E1 and E2 sit at every site the contract lists.

Plain unittest, read-only: it only reads shipped text. Run:

    py -3 -m unittest .claude/scripts/tests/test_codegraph_session_parent_docs.py
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

INSTALL_SKILL = ROOT / "skills" / "auto-improve-codegraph-install" / "SKILL.md"
UNINSTALL_SKILL = ROOT / "skills" / "auto-improve-codegraph-uninstall" / "SKILL.md"
FINISH_SKILL = ROOT / "skills" / "auto-improve-finish-install" / "SKILL.md"
README = ROOT / "README.md"
DECISION_TABLE = ROOT / ".claude" / "references" / "codegraph-decision-table.md"
HOOKS_JSON = ROOT / ".claude" / "hooks" / "hooks.json"
MECHANISMS = ROOT / ".claude" / "registries" / "MECHANISMS.md"
VOCABULARY = ROOT / ".claude" / "registries" / "VOCABULARY.md"
ADDON_HOOKS = ROOT / ".claude" / "addons" / "codegraph" / "hooks"

#: E1, the retry exception sentence (contract, Value Objects), whitespace folded for the comparison.
E1_HEAD = "Not after a `session-state-unusable` block, which offers no retry."
E1_TAIL = ("After a `retry-ticket-unwritten` block the retry was not recorded, so the repeat is blocked once more "
           "(as `source-target` or `ambiguous-target`) and the identical call after it is allowed.")
#: How many times each shipped file carries the retry exception sentence E1 (one per retry sentence the contract lists).
E1_SITES = [("skills/auto-improve-codegraph-install/SKILL.md", 3), ("skills/auto-improve-codegraph-uninstall/SKILL.md", 1),
            ("README.md", 2), (".claude/references/codegraph-decision-table.md", 1),
            (".claude/registries/VOCABULARY.md", 1), (".claude/registries/MECHANISMS.md", 1)]
#: E2, the logging exception sentence.
E2 = "While the session folder cannot be used, these lines print on every call and nothing is logged."


def read(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


class WordingCase(unittest.TestCase):
    def assertHas(self, path: Path, needle: str, why: str) -> None:
        self.assertIn(re.sub(r"\s+", " ", needle), read(path), msg="%s must contain %r (%s)" % (path.name, needle, why))

    def assertLacks(self, path: Path, needle: str, why: str) -> None:
        self.assertNotIn(needle, read(path), msg="%s must no longer contain %r (%s)" % (path.name, needle, why))


class TestInstallSkill(WordingCase):
    def test_the_session_folder_location_is_the_per_user_parent_not_the_temp_folder(self):
        self.assertHas(INSTALL_SKILL, "Per-user session parent", "the marker and tickets live there")
        self.assertHas(INSTALL_SKILL, "%LOCALAPPDATA%\\auto-improve-codegraph\\", "the Windows location")
        self.assertLacks(INSTALL_SKILL, "under the system temp folder", "the old location of the tracker's marker")

    def test_the_guard_is_not_called_a_nudge_and_the_unusable_folder_block_is_described(self):
        self.assertLacks(INSTALL_SKILL, "nudge, never a wall", "the guard now blocks on an unusable session folder")
        self.assertHas(INSTALL_SKILL, "The guard lets reads through when CodeGraph is provably unavailable.", "new heading")
        self.assertHas(INSTALL_SKILL, "An unusable session folder blocks (`session-state-unusable`), says why and how to fix it.",
                       "fail closed")

    def test_both_exception_sentences_are_present(self):
        self.assertHas(INSTALL_SKILL, E1_HEAD, "E1 after the retry escape")
        self.assertHas(INSTALL_SKILL, E1_TAIL, "E1, the retry-ticket-unwritten half")
        self.assertHas(INSTALL_SKILL, E2, "E2 after 'and logs it'")

    def test_the_refusals_list_names_both_new_reasons(self):
        self.assertHas(INSTALL_SKILL, "session-state-unusable", "refusals list")
        self.assertHas(INSTALL_SKILL, "retry-ticket-unwritten", "refusals list")

    def test_old_temp_folders_are_documented_as_inert_and_deletable_by_hand(self):
        self.assertHas(INSTALL_SKILL, "left in the system temp folder by 0.15.2 are no longer read; delete them by hand",
                       "Q3: old folders are left alone")


class TestUninstallAndFinishSkills(WordingCase):
    def test_the_uninstall_skill_points_at_the_per_user_parent_and_carries_e1(self):
        self.assertHas(UNINSTALL_SKILL, "Per-user session parent", "the leftover folder's new place")
        self.assertLacks(UNINSTALL_SKILL, "in the system temp folder: that is a leftover", "the old location")
        self.assertHas(UNINSTALL_SKILL, E1_HEAD, "E1 at the uninstall skill's retry sentence")

    def test_the_finish_install_skill_no_longer_calls_the_guard_a_nudge(self):
        self.assertLacks(FINISH_SKILL, "the guard is a nudge", "reversed")
        self.assertHas(FINISH_SKILL, "unless its session folder cannot be used, when it blocks and says why", "fail closed")


class TestReadme(WordingCase):
    def test_the_nudge_and_state_unwritable_sentences_are_gone(self):
        self.assertLacks(README, "the guard is a nudge, never a wall", "reversed")
        self.assertLacks(README, "`state-unwritable` is the sixth line", "the reason is removed")
        self.assertLacks(README, "`<system temp folder>/auto-improve-codegraph-<session id>/`", "moved")

    def test_it_carries_e1_e2_and_a_changed_in_0_16_3_block(self):
        self.assertHas(README, E1_HEAD, "E1 at the README retry sentences")
        self.assertHas(README, E2, "E2 after 'logged once per session per reason'")
        self.assertHas(README, "Changed in 0.16.3", "the new block (this change ships in 0.16.3)")
        self.assertHas(README, "session-state-unusable", "the new reason")
        self.assertHas(README, "retry-ticket-unwritten", "the new reason")
        self.assertHas(README, "index-other-tree", "the upgraded-project row (a 0.15.2 helper passes the Hop proof)")


class TestDecisionTableAndHooksJson(WordingCase):
    def test_the_decision_table_names_the_new_location_and_reasons(self):
        self.assertLacks(DECISION_TABLE, "`state-unwritable` covers an unusable session folder", "reversed")
        self.assertLacks(DECISION_TABLE, "<system temp folder>/auto-improve-codegraph", "moved")
        self.assertHas(DECISION_TABLE, "session-state-unusable", "an unusable session folder blocks")
        self.assertHas(DECISION_TABLE, E1_HEAD, "E1")
        self.assertHas(DECISION_TABLE, E2, "E2")

    def test_the_hooks_json_comment_lists_the_per_user_session_parent(self):
        self.assertLacks(HOOKS_JSON, "lists the system temp folder", "the reset hook prunes the parent now")
        self.assertHas(HOOKS_JSON, "lists the per-user session parent", "the comment is edited where it stands")


class TestRegistries(WordingCase):
    def test_mechanisms_names_the_hop_proof_and_six_copies(self):
        self.assertHas(MECHANISMS, "TREE_HOP_REFUSAL", "the capability constant")
        self.assertHas(MECHANISMS, "exist as six", "_remote_host and _own_spellings: six copies")

    def test_vocabulary_holds_the_new_terms(self):
        self.assertHas(VOCABULARY, "Per-user session parent", "new term")
        self.assertHas(VOCABULARY, "Foreign marker", "new term")


class TestRetryExceptionAtEverySite(WordingCase):
    """Review fix round (test-strategy M4, code-review C-W1): E1 is checked at EACH site, not once per file, and its tail
    names both reasons a repeat can get (a pattern-only Grep or a generic Glob is `ambiguous-target`, not `source-target`)."""

    def test_every_e1_site_has_the_head_followed_by_the_full_two_reason_tail(self):
        for rel, expected in E1_SITES:
            text = read(ROOT / rel)
            starts = [m.start() for m in re.finditer(re.escape(E1_HEAD), text)]
            self.assertEqual(len(starts), expected, msg="%s must carry E1 at %d sites, found %d" % (rel, expected, len(starts)))
            for number, start in enumerate(starts, 1):
                after = text[start + len(E1_HEAD):start + len(E1_HEAD) + len(E1_TAIL) + 4]
                self.assertTrue(after.strip().startswith(E1_TAIL),
                                msg="%s site %d: E1 head must be followed by the tail naming `source-target` or "
                                    "`ambiguous-target`, got %r" % (rel, number, after))

    def test_no_site_still_promises_only_source_target(self):
        for rel, _ in E1_SITES:
            self.assertNotIn("once more (as `source-target`) and", read(ROOT / rel),
                             msg="%s: the repeat after retry-ticket-unwritten may also be ambiguous-target" % rel)

    def test_every_repeat_the_blocked_call_sentence_is_followed_by_e1_within_a_paragraph(self):
        for rel in ("skills/auto-improve-codegraph-install/SKILL.md", "skills/auto-improve-codegraph-uninstall/SKILL.md",
                    "README.md", ".claude/references/codegraph-decision-table.md"):
            text = read(ROOT / rel)
            for m in re.finditer(r"repeat the blocked call once", text):
                self.assertIn(E1_HEAD, text[m.end():m.end() + 400],
                              msg="%s: a retry sentence at offset %d is not followed by E1" % (rel, m.start()))

    def test_the_guard_banner_names_both_reasons_too(self):
        text = re.sub(r"\s+", " ", (ADDON_HOOKS / "codegraph-first-guard.py").read_text(encoding="utf-8"))
        text = text.replace('", "', " ").replace('"', "")
        self.assertIn("`source-target` or `ambiguous-target`", text,
                      msg="the retry-ticket-unwritten banner must say the repeat blocks as source-target or ambiguous-target")


class TestRetryExceptionHasAReferent(WordingCase):
    """Review pass 2 (round 3, code-review WARN): E1 is an exception to a retry sentence, so it stands only where one comes
    right before it. A copy with no retry sentence in front (the README 0.16.3 'It fails closed' bullet) reads as a limit on
    what the guard lets through, which is false: a subagent, a project with no index and one with no server still pass."""

    RETRY = re.compile(r"repeat the (?:identical )?blocked call once", re.IGNORECASE)

    def test_every_e1_is_preceded_by_a_retry_sentence_in_the_400_characters_before_it(self):
        for rel in ("skills/auto-improve-codegraph-install/SKILL.md", "skills/auto-improve-codegraph-uninstall/SKILL.md",
                    "README.md", ".claude/references/codegraph-decision-table.md"):
            text = read(ROOT / rel)
            for m in re.finditer(re.escape(E1_HEAD), text):
                self.assertIsNotNone(self.RETRY.search(text[max(0, m.start() - 400):m.start()]),
                                     msg="%s: the E1 sentence at offset %d has no retry sentence before it (it has nothing "
                                         "to be an exception to): %r" % (rel, m.start(), text[max(0, m.start() - 160):m.start()]))

    def test_the_readme_fails_closed_bullet_does_not_read_as_stopping_the_fail_open_reads(self):
        text = read(README)
        start = text.index("- **It fails closed.**")
        end = text.index("- **", start + 5)
        bullet = text[start:end]
        self.assertIn("still let through", bullet, msg="the bullet keeps saying subagent / no-index / no-server reads pass")
        self.assertIsNone(re.search(r"let through\.?\s*Not after", bullet),
                          msg="'Not after a `session-state-unusable` block' directly after 'still let through' reads as: "
                              "those reads are blocked after an unusable-folder block. Steps 4-6 still run there.")
        self.assertNotIn(E1_HEAD, bullet, msg="E1 has no retry sentence in this bullet to be an exception to")


class TestReviewFixRoundWording(WordingCase):
    """Review fix round: C-W3 (upgrade paragraph), C-I (grammar, dangling E2)."""

    def test_install_skill_upgrade_paragraph_updates_a_0_15_2_install_in_place(self):
        # Merge with the in-place upgrade (#266, 0.16.0): the paragraph "Upgrading an install from before 0.15.3" (uninstall
        # first) is gone; a 0.15.2 and a 0.16.0-0.16.2 install are updated by re-running the install.
        self.assertHas(INSTALL_SKILL, "Upgrading an older install: re-run this skill.", "an unedited older install is updated in place")
        self.assertHas(INSTALL_SKILL, "**0.15.2 (the fail-open guard):**", "the 0.15.2 entry")
        self.assertHas(INSTALL_SKILL, "**0.16.0 to 0.16.2 (the shadow measurement):**", "the 0.16.x entry")
        self.assertLacks(INSTALL_SKILL, "Upgrading an install from before 0.15.2.", "stale version")

    def test_mechanisms_has_no_is_fails_grammar_break(self):
        self.assertLacks(MECHANISMS, "guard is fails open", "grammar")
        self.assertHas(MECHANISMS, "guard fails open only on proof", "grammar")

    def test_vocabulary_sentence_does_not_start_lowercase(self):
        self.assertLacks(VOCABULARY, ". an unusable session folder", "a sentence starts with a capital")
        self.assertHas(VOCABULARY, ". An unusable session folder", "a sentence starts with a capital")

    def test_readme_fails_closed_bullet_has_no_dangling_e2(self):
        text = read(README)
        start = text.index("- **It fails closed.**")
        end = text.index("- **", start + 5)
        self.assertNotIn(E2, text[start:end], msg="'these lines' has nothing to refer to in the 'It fails closed' bullet")
        self.assertIn(E2, text, msg="E2 stays where 'lines' has a referent (the fail-open lines)")


class TestReviewPass3Wording(WordingCase):
    """Review pass 3 (round 4), info items: the unusable-folder causes are listed exactly as the code decides them, and the
    bridge comment says which implementation the export selects."""

    OLD_CAUSE = "an unset or relative `LOCALAPPDATA` / `XDG_CACHE_HOME`"

    def regions(self):
        readme = read(README)
        start = readme.index("- **It fails closed.**")
        skill = read(INSTALL_SKILL)
        s_start = skill.index("`session-state-unusable`: the Per-user session parent")
        return (("README.md", readme[start:readme.index("- **", start + 5)]),
                ("install SKILL.md", skill[s_start:skill.index("- `retry-ticket-unwritten`", s_start)]))

    def test_an_unset_xdg_cache_home_is_not_listed_as_a_failure(self):
        for label, region in self.regions():
            self.assertNotIn(self.OLD_CAUSE, region,
                             msg="%s: an unset XDG_CACHE_HOME falls back to HOME/.cache; only both unset fails" % label)
            self.assertRegex(region, r"`XDG_CACHE_HOME` nor `HOME`",
                             msg="%s: it must say that the failure is neither XDG_CACHE_HOME nor HOME being set" % label)
            self.assertRegex(region, r"relative `XDG_CACHE_HOME`|`XDG_CACHE_HOME`[^.;)]{0,12}relative",
                             msg="%s: and that a relative XDG_CACHE_HOME fails" % label)

    def test_the_network_path_check_is_said_to_be_windows_only(self):
        for label, region in self.regions():
            self.assertRegex(region, r"network path[^.;)]{0,30}Windows|Windows[^.;)]{0,40}network path",
                             msg="%s: the network-path check runs on Windows only; the text must say so" % label)

    def test_the_bridge_comment_says_which_implementation_is_used(self):
        text = (ROOT / ".claude" / "scripts" / "_claude_paths.py").read_text(encoding="utf-8")
        start = text.index("# worktree_own_root is looked up with getattr")
        block = re.sub(r"\s+", " ", re.sub(r"(?m)^#\s?", "", text[start:text.index("_native_own_root = getattr", start)]))
        self.assertNotIn("True means this bridge uses the helper's native tree functions", block,
                         msg="a helper that declares the constant but has no worktree_own_root gives True with the inline copy")
        self.assertRegex(block, r"worktree_own_root[^.]*\b(?:else|otherwise|unless|only when|when the helper)\b[^.]*inline",
                         msg="the comment must say worktree_own_root is native only when the helper has it, else the inline copy")


class TestShippedCodeCarriesNoRemovedNames(unittest.TestCase):
    def test_no_shipped_script_or_hook_still_names_the_removed_constant_or_reason(self):
        offenders = []
        for folder in (ROOT / ".claude" / "scripts", ROOT / ".claude" / "hooks", ADDON_HOOKS):
            for path in sorted(folder.glob("*.py")):
                text = path.read_text(encoding="utf-8")
                for needle in ("WORKTREE_OWN_ROOT_NATIVE", "fail-open:state-unwritable"):
                    if needle in text:
                        offenders.append("%s names %s" % (path.relative_to(ROOT), needle))
        self.assertEqual(offenders, [], msg="removed in issue #271: " + "; ".join(offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
