---
id: 87
issue_offer: opened
title: Rule documents
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/87
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-28-angular-tailwind-rule-documents/t1-rule-documents
worktree: none
north_stars: inherited from .claude/work-items/2026-10-28-84-angular-tailwind-rule-documents.md
parent_issue: 84
base: feature/84-angular-tailwind-rule-documents
contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
pr: none
issue_link: unknown
status: implementing
created: 2026-10-28
---

# Rule documents

## Problem statement
Sub-task 1 of the approved contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (parent issue #84). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 1. Rule documents (`ui-ux-designer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/angular-tailwind/documents/ANGULAR_CODE_RULES.md`
- `.claude/addons/angular-tailwind/documents/ANGULAR_MATERIAL_RULES.md`
- `.claude/addons/angular-tailwind/documents/TAILWINDCSS_RULES.md`
- `.claude/addons/angular-tailwind/documents/UI-UX-PATTERNS.md`
- `.claude/addons/angular-tailwind/snippets/scroll-edge.scss`
- `skills/website-design/references/foundation.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Write the four rule documents and the scroll-edge snippet from issue #84 companion 1, and bump the version.
CONTEXT: concept contract at .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md; the full issue text is quoted in its brief.
FILES: as listed.
CONSTRAINTS:
  - One "### <ID> — <title>" heading per catalogue ID, in the Rule entry shape.
  - A-025 (with the states markup) goes in UI-UX-PATTERNS.md. P-001 is the error banner. No P rule restates a catalogue rule.
  - A-002, A-004, A-006, A-011 and A-012 read "not enforced" (the pattern enforcer does not ship).
  - Use C1-C6 in meaning, including the C1(b) tag and property lists, and the precedence paragraph word for word.
  - TAILWINDCSS_RULES.md holds the snippet, where it goes, the table and plain-list usage markup, the height rule
    (T-014), the Ionic note (nested regions only; ion-content scrolls the page) and the install step.
  - foundation.md: reword only the "Inline Style Elimination" paragraph (C1) and the !important line (C3).
  - Version 0.9.22 in the four manifest files (Q10).
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md — dispatched by /advance
