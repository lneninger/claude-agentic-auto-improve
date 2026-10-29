---
id: 84
issue_offer: pending
title: Replace the angular-tailwind prompt hook with rule documents and a skill
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/84
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/84-angular-tailwind-rule-documents
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261028-feature-84-replace-angular-tailwind-prompt-hook
north_stars: none
contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/109
issue_link: closes
status: shipped
created: 2026-10-28
---

# Replace the angular-tailwind prompt hook with rule documents and a skill

Raw invocation: `https://github.com/lneninger/claude-agentic-auto-improve/issues/84` (title on GitHub: `[FEATURE] Replace the angular-tailwind prompt hook with rule documents and a skill`). Two companion comments on the issue carry the rule catalogue (65 rules, IDs A-, M-, T-) and the hook's verbatim printed text with a coverage map. Read the issue and both comments in full before designing; they are part of the requirements.

## Problem statement
The `angular-tailwind` add-on delivers its rules through one hook, `angular-tailwind-advisor.py`, that runs on every prompt. It costs about 123 milliseconds per prompt against a 50 millisecond bare Python start, fires on about twenty common words so it triggers on prompts unrelated to interface work, adds roughly 400 words of context each time, keeps the rule text only inside the script, and may never reach the subagent that writes the code. The edit-time guard `architecture-guard.py` is the real enforcement. The maintainer decided to stop using the prompt hook and to deliver the rules as documents plus a skill that agents load on demand.

## Acceptance criteria
- [ ] The add-on manifest `addon.json` lists its documents, and the install skill copies them into the project and registers them in the project profile's `review.documents` slot.
- [ ] A project that never runs the install skill gets neither the hook nor the documents.
- [ ] Every rule the old hook printed appears in the shipped documents, proven by a test that fails when a rule is missing (use the coverage map in the issue's second companion comment).
- [ ] The hook is a disabled add-on: its script is kept, its settings row is gone, and a documentation entry says what it did, what it cost, why it is off and how to turn it back on.
- [ ] No environment-variable switch exists for this add-on, and the manifest drops its `kill_switches` entry. First check whether a manifest checker requires the field.
- [ ] An uninstall skill removes the settings rows and the copied files, and is safe to run twice.
- [ ] The scroll container snippet, usage markup (table and plain list), height rule, Ionic note and install step are shipped, and a test confirms the class definitions exist after install.
- [ ] The guard's block and warn messages name the rule and the document (the guard ships in this plugin, so this item does the work and does not move it to the project).
- [ ] The Angular developer agent receives the rules without any hook. The mechanism is chosen and tested (agent `skills` preload first; the subagent-start hook event is the fallback).
- [ ] Each conflict the issue lists (inline-style scope, Material overrides location, `!important` against Tailwind `!`, pixel values against arbitrary values, response envelope success-flag name, theme polarity) is settled in the shipped text, and the guard honours the inline-style exceptions.
- [ ] Before and after timing is recorded: no per-prompt program start is spent on Angular rules.
- [ ] Release notes and the plugin version are updated in the same pull request, and the registry mirrors stay in step.
- [ ] Failure path: running the install or uninstall skill twice, on a project with a missing profile slot, or with the stylesheet snippet already present, changes nothing and reports plainly.
- [ ] Upgrade path: a project that installed the old hook gets an upgrade note or a migration step. Project tests that pin the add-on's rows are updated to the disabled state.

## Out of scope
- The look and feel of any particular product: colours, class names, product wording, chart libraries, domain sample names. These stay in the consuming project and appear in the documents as placeholders.
- The adoption work in the consuming project repository (`StockToolScalpingMachine`): installing the documents, removing its local rule copies, disabling the hook there, renaming its design document. That is step 3 of the issue's order of work and is a separate task.
- Fixing the guard's other weak spots beyond what the acceptance criteria name (for example the hard-coded `/ClientApp/` folder names, the multi-edit gap), unless the contract decides one is needed to honour a settled rule. Record the rest in the brief for the maintainer.
- Rules that are project-specific. The "other candidates" patterns (status badge, error banner, states, table rules, card surface) are decided per pattern in the contract, one at a time.

## Known context
- Parent / epic: none. Origin: `lneninger/StockToolScalpingMachine#611` (cross-repo reference only).
- Related items: PR #72 (the `application-design` and `website-design` skills the layout nudge names), `.claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md`.
- Affected areas (best guess, to be confirmed by the contract): `.claude/addons/angular-tailwind/` (manifest, hook), `skills/auto-improve-angular-tailwind-install/`, a new uninstall skill, new documents and an Angular rules skill, `agents/angular-senior-dev.md`, `.claude/hooks/architecture-guard.py` and its rules file, `.claude/hooks/hooks.json`, `.claude/hooks/tests/test_addons.py`, `.claude/scripts/tests/test_auto_improve_finish_install.py`, `test_plugin_doctor.py`, `test_plugin_manifests.py`, `README.md`, `plugin.json`, release notes.
- The guard `architecture-guard.py` and `_project_paths.py` already live in this repository's `.claude/hooks/`, so the issue's question "does the add-on ship the guard" is answered: it does.

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
Run is unattended and the maintainer's standing preference is to state the call and keep delivering, so each gap below carries a stated assumption. The contract gate puts the real choices to the maintainer.
- Does a prompt hook's output reach a subagent, and can an agent preload a skill from its frontmatter? → **Answer (assumption):** both are unverified. The contract must make the choice and the tests must prove it, with the preload as the primary route and the subagent-start hook as the documented fallback.
- Which of the "other candidate" patterns are generic? → **Answer (assumption):** decided in the contract, using the issue's own test (would another project reuse it unchanged with only colour values swapped?). Anything uncertain stays out of the shipped documents and is listed as a follow-up.
- Where is the line on the guard's weak spots? → **Answer (assumption):** only the weak spots that block honouring a settled conflict (inline-style exceptions, `sticky` and scroll classes named in acceptance criteria) are in scope.
- Does the manifest checker require `kill_switches`? → **Answer:** not yet known; first check in the contract's reuse phase.

## Size
XL — a new set of shipped documents, a new skill, a new uninstall skill, a manifest and install-script change, a hook-to-disabled-add-on state, guard message changes, an agent change, a drift test, timing evidence, and a version bump with release notes. It touches several mechanisms, so it is a candidate for sub-tasks.

## Routing
non-trivial → /design-first (mandatory)

## Run log
- 2026-10-29: merged and recorded (https://github.com/lneninger/claude-agentic-auto-improve/pull/97, https://github.com/lneninger/claude-agentic-auto-improve/pull/99, https://github.com/lneninger/claude-agentic-auto-improve/pull/101, https://github.com/lneninger/claude-agentic-auto-improve/pull/102, https://github.com/lneninger/claude-agentic-auto-improve/pull/103, https://github.com/lneninger/claude-agentic-auto-improve/pull/104, https://github.com/lneninger/claude-agentic-auto-improve/pull/105, https://github.com/lneninger/claude-agentic-auto-improve/pull/106, https://github.com/lneninger/claude-agentic-auto-improve/pull/107, https://github.com/lneninger/claude-agentic-auto-improve/pull/109); contract 2026-10-28-angular-tailwind-rule-documents flipped to implemented by pr_merged.py; owner confirmed resolved: none; not performed and disclosed on #86: Implementation matches Data Shapes exactly | New Mechanisms (if any) promoted to `MECHANISMS.md` | New vocabulary terms promoted to `VOCABULARY.md`
