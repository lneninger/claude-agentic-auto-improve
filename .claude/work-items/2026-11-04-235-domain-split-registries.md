---
id: 235
issue_offer: pending
title: Fix Domain-split registries and Jornal
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/235
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/235-domain-split-registries
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261104-bug-235-domain-split-registries
north_stars: none
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/337
issue_link: closes
status: shipped
created: 2026-11-04
---

# Fix Domain-split registries and Jornal

## Problem statement
The three registries (mechanisms, vocabulary, journal) were split by domain in a client repository
(StockToolScalpingMachine), but the plugin's tooling never learned the split. The layout has no
written specification. Writers still append to the flat root files. Several readers and checkers
only know the flat files. Nothing detects divergence. In the client this produced two diverging
journal copies and 266 journal titles with no lesson text. The registries are plugin-owned, so the
defect reaches every client. The fix is a plugin change plus a versioned migration that moves
existing clients onto the new layout. The issue was written without access to the plugin repo, so
plugin-side paths are inferred and several are marked "verify in plugin".

## Acceptance criteria
Taken from the issue's section 5 verbatim in substance. Criteria marked (scope?) depend on an
intake question below.
- [ ] A layout spec exists at `references/registry-layout.md`, and each root registry file carries `<!-- registry-layout: 2 -->` as its first line.
- [ ] `registry_append.py` is the only documented write path. The five writer instructions in the issue's 2.2-B are updated to use it. Each rejected-input case (bodiless, duplicate, malformed) has a test.
- [ ] Every reader in the issue's 2.2-C resolves root plus domain files through one shared resolver. `data-architect` and `contract-critic` name `general.md` explicitly.
- [ ] `validate_registries.py --check-structure` implements the six lint rules of the issue's 3.4 and is wired into `verify-before-done`. The digest generator fails on bodiless or duplicate entries.
- [ ] `journal-post-approval-tracker` fires for an entry written to any journal file or through the script.
- [ ] Migration `0001` passes dry-run, apply, idempotence and no-content-loss tests on a fixture reproducing the client's state (title-only entries, flat-only entries, split-only entries, project lines in the Universal tier).
- [ ] (scope?) The sync tool halts with a pending-migration exit code on a layout-1 client and syncs normally after migration. `plugin_doctor.py` reports the state.
- [ ] Skeleton domain files under `templates/` let a fresh client start compliant.
- [ ] The plugin version is bumped, release notes are written, and the documented client procedure (the issue's 4.3) is published.
- [ ] Failure-path criterion (added at intake): migration refuses on a conflict (same title, different bodies) and on uncommitted registry changes, writes a report, and leaves every file unchanged.

## Out of scope
- Recovering the 172 lost journal bodies in the client (issue 6.2): client-specific, not a plugin task.
- Running the migration in the client repository (issue rollout step 4).
- Editing the client repository's own registry files.

## Known context
- Parent / epic: none
- Related items: client-repo follow-ups named in the issue (journal-split-dropped-entry-bodies, registry-universal-tier-holds-project-content). They live in the client repo, not here.
- Intake facts verified in this worktree on 2026-11-04 (branch base equals fetched `origin/master`):
  - The plugin's own registries are three flat files only (`.claude/registries/{MECHANISMS,VOCABULARY,JOURNAL}.md`); there are no domain subfolders here. Answers the issue's open question 5 in part.
  - These files named by the issue exist: `.claude/scripts/{validate_registries,generate_registry_digest,cross_area_scan,north_star_review,plugin_doctor,accuracy_update}.py`, `.claude/hooks/{journal-post-approval-tracker,_project_paths}.py`.
  - Not present in this repo: `registry_append.py`, `registry_migrations/`, any `registry-layout` marker, any `registries.domains` profile slot, `tools/sync-plugin.ps1`, `.claude/.sync-config.json`. The sync tool named in the issue's section 4 is therefore not in this repo.
- Affected areas (best guess, to be confirmed by the contract): `.claude/scripts/`, `.claude/hooks/`, `.claude/registries/`, `agents/` (data-architect, contract-critic, ui-ux-designer, fullstack-code-reviewer), `skills/` (journal-add, design-first, ship, cross-impact, promote-ui-rule, verify-before-done), `.claude/templates/`, plugin manifest and release notes.

## North-star alignment
- none: the register holds no active thought

## Open questions from intake
Each carries a recommendation so it can be accepted with one word at the contract gate. None of
them blocks the contract draft.
- Is the split-files layout the canonical form? → **Recommendation:** yes, as the issue assumes. Root files keep the Universal tier plus a pointer; domain files hold project content.
- May legacy bodiless titles carry `Status: archived-title-only` so the lint can go green without inventing text? → **Recommendation:** yes. Never invent lesson text.
- Is `general` always a domain? → **Recommendation:** yes, always present and always read.
- Where does the layout-version gate live, given the sync tool is not in this repo? → **Recommendation:** this repo ships the layout marker, the migration script, the doctor check and a cross-platform Python gate. The PowerShell sync tool change is a linked follow-up in the repo that owns it. This changes the sync criterion above.
- Delivery shape: the issue proposes three plugin PRs. → **Recommendation:** treat as one contract with several sub-tasks (spec and resolver and lint; reader and writer updates; migration and doctor), delivered through a parent branch.
- Bug versus feature: the title carries `[BUG]` and is kept as filed, although the body describes new capability. → **Recommendation:** keep `[BUG]`; the shipped defect is that the split was never supported by the tooling.

## Size
XL — new layout spec, a new writer script, a shared resolver touching about ten readers, a structural lint, and a versioned migration framework with a new data shape (layout version).

## Routing
non-trivial → /design-first (mandatory; contract with parent branch expected)

## Run log
- 2026-11-10: merged and recorded (https://github.com/lneninger/claude-agentic-auto-improve/pull/250, https://github.com/lneninger/claude-agentic-auto-improve/pull/252, https://github.com/lneninger/claude-agentic-auto-improve/pull/254, https://github.com/lneninger/claude-agentic-auto-improve/pull/256, https://github.com/lneninger/claude-agentic-auto-improve/pull/258, https://github.com/lneninger/claude-agentic-auto-improve/pull/273, https://github.com/lneninger/claude-agentic-auto-improve/pull/278, https://github.com/lneninger/claude-agentic-auto-improve/pull/280, https://github.com/lneninger/claude-agentic-auto-improve/pull/285, https://github.com/lneninger/claude-agentic-auto-improve/pull/294, https://github.com/lneninger/claude-agentic-auto-improve/pull/299, https://github.com/lneninger/claude-agentic-auto-improve/pull/309, https://github.com/lneninger/claude-agentic-auto-improve/pull/312, https://github.com/lneninger/claude-agentic-auto-improve/pull/315, https://github.com/lneninger/claude-agentic-auto-improve/pull/321, https://github.com/lneninger/claude-agentic-auto-improve/pull/323, https://github.com/lneninger/claude-agentic-auto-improve/pull/329, https://github.com/lneninger/claude-agentic-auto-improve/pull/333, https://github.com/lneninger/claude-agentic-auto-improve/pull/337); contract 2026-11-04-domain-split-registries flipped to implemented by pr_merged.py; owner confirmed resolved: none; not performed and disclosed on #240: none
