---
id: none
issue_offer: pending
title: Fix the codegraph text-scan failure and add the four codegraph vocabulary terms
type: BUG
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/codegraph-text-scan-and-vocab
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261106-bug-codegraph-text-scan-and-vocab
north_stars: none
contract: none
pr: none
issue_link: unknown
status: implementing
created: 2026-11-06
---

# Fix the codegraph text-scan failure and add the four codegraph vocabulary terms

## Problem statement
The codegraph hooks redesign (parent issue #261, contract `2026-11-05-codegraph-hooks-redesign`) landed in pull request 289. Its fail-open review (`.claude/reviews/2026-11-05-codegraph-hooks-redesign/t5-fail-open-review-fullstack-code-reviewer.md`) found two things the landing did not fix. Master fails `test_plugin_text_scans.py::test_no_shipped_file_names_an_individual_codegraph_tool` on seven files (finding F4). The four accepted vocabulary terms are missing from `VOCABULARY.md` (finding F1).

## Acceptance criteria
- [x] `test_plugin_text_scans.py` passes: the five recorded-transcript fixtures, the fixtures `README.md` and `test_codegraph_shadow.py` are exempt, and nothing else is.
- [x] A control test proves the exemption is narrow: a neighbouring file, a sibling folder and a look-alike folder name are still caught.
- [x] `VOCABULARY.md` carries Transcript turn state, Live plan, Shadow decision and Shadow record, with the text the review proposed.
- [x] The plugin version is raised by a patch (0.16.0 to 0.16.1) in all five places, and `check_version_bump.py` and the manifest suite pass.

## Out of scope
- The informational review findings (F2, F3, F6, F8), which go to the cut-over follow-up.
- Promoting the Shadow decision log mechanism: only one guard uses it, so the review decided not to.

## Known context
- Parent / epic: #261 (closed, landed in pull request 289).
- Related items: pull request 284 (the fail-open review), records pull request 291.
- Affected areas: `.claude/scripts/tests/test_plugin_text_scans.py`, `.claude/registries/VOCABULARY.md`, the five manifest files.

## North-star alignment
- none: the register holds no active thought.

## Open questions from intake
- Exempt the fixtures or reword them? → **Assumed:** exempt. The fixtures are recorded real transcripts, and rewording them would stop them being recordings. The replaying test file is exempt for the same reason.
- Open a GitHub issue for this? → **Assumed:** not now. `issue_offer` stays `pending`, and `/ship` asks once before the pull request.

## Size
S: one test exemption, four registry lines and a version bump, with no new data shape.

## Routing
Direct to the implementer, no contract. Every changed file is a test, a registry or a manifest.
