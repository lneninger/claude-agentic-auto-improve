---
id: 171
issue_offer: opened
title: Cloud skill and provider references
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/171
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t6-cloud-skill-and-provider-references
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/181
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Cloud skill and provider references

## Problem statement
Sub-task 6 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 6. Cloud skill and provider references (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `skills/cloud-engineering/SKILL.md`
- `skills/cloud-engineering/references/cross-cutting.md`
- `skills/cloud-engineering/references/azure.md`
- `skills/cloud-engineering/references/aws.md`
- `skills/cloud-engineering/references/gcp.md`
- `skills/cloud-engineering/references/terraform.md`
- `skills/cloud-engineering/references/bicep.md`
- `skills/cloud-engineering/references/docker.md`
- `skills/cloud-engineering/references/kubernetes.md`
- `.claude/scripts/tests/test_cloud_text_scans.py`

**Pre-written TASK block:**
```
TASK: Write the cloud-engineering skill. It reads cloud.providers and cloud.iac and opens ONLY the
  matching references, halting with one line when cloud.providers is unset. cross-cutting.md covers
  networking, identity and access, secrets, messaging, storage, observability, cost, governance,
  deployment validation and troubleshooting, each as a provider-neutral rule plus a pointer to the
  provider file. Each provider and tool file maps those topics to concrete services and to
  NON-MUTATING validation commands, written as ready contractLanding.verification.steps entries.
CONTEXT: concept contract (Cloud profile, Reused Mechanisms rows for cloud).
FILES: the ten listed.
CONSTRAINTS:
  - Provider choice comes only from the profile, never from where an MCP server runs.
  - State the cloud scope rule near the top of SKILL.md: this skill does design, review, validation
    (non-mutating commands only) and troubleshooting. It never runs a deploy, apply, create, update or
    destroy command against a live environment; it writes the command out for the user to run, and the
    user's normal Claude Code permission prompts and the existing destructive-operation guards apply
    unchanged. No settings file is written and no permission check is run.
  - Mutating commands appear only inside a block labelled "for the user to run".
  - test_cloud_text_scans.py: over agents/cloud-engineer.md (when present) and skills/cloud-engineering/,
    every line carrying apply, create, update, destroy, delete, deploy, install, upgrade, uninstall or push
    as a command sits inside a "for the user to run" block; a planted line is the positive control.
  - Names no project; passes the project-name check.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```


## Out of scope
- Everything outside this sub-task's handoff block; see the other sub-tasks of the contract.

## Known context
- Parent / epic: #161 (https://github.com/lneninger/claude-agentic-auto-improve/issues/161)
- Related items: the other sub-tasks of `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
- Affected areas: the files named in the handoff block

## North-star alignment
- inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md

## Open questions from intake
- none; the sub-task's criteria were approved at the contract gate.

## Size
Task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md.

## Routing
task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md - dispatched by /advance
