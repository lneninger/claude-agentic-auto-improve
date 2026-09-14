# Project Profile

**TEMPLATE.** Copy this file to `.claude/project-profile.md` in a consuming repository and fill in
every slot. This is the only file a new project must author to make the vendored generic agents
correct.

## What this file is for

A generic agent must not carry a literal path from one project into another. Instead of writing
`src/AcmeApp.Persistence/Migrations/**`, a generic agent writes "the migration root named in the
project profile", and this file is where that root is named.

## Rules

- **Every slot below is present, even when empty.** An empty slot reads `none`, never a blank line.
  A blank line is indistinguishable from a slot somebody forgot.
- **An agent may cite only a slot this template declares.** If an agent needs a fact no slot covers,
  add the slot to this template **in the plugin**, in the same change, so every consuming project
  gains the slot at once. Never invent a local-only slot.
- **Slot names are the contract.** Rename a slot here and every agent citing it stops resolving.

## Slots

| Slot | Value |
|---|---|
| `project.name` | *(the repository name)* |
| `backend.roots` | *(one or more source roots for server-side code, or `none`)* |
| `frontend.roots` | *(one or more source roots for client-side code, or `none`)* |
| `frontend.theme-polarity` | *(per frontend root: `light`, `dark`, or `both`; or `none`)* |
| `test.roots` | *(one or more test project roots, or `none`)* |
| `migration.root` | *(the database migration directory, or `none`)* |
| `auth.roots` | *(the authentication and credential code roots, or `none`)* |
| `safety-critical.roots` | *(roots where a defect causes irreversible harm, or `none`)* |
| `review.documents` | *(the primary documents a reviewer must read, or `none`)* |
| `implementers` | *(the agents that may own a contract sub-task, or `none` to accept the plugin's own)* |
| `review-gates` | *(the agents that appear in a handoff block but open no pull request, or `none` to accept the plugin's own)* |

### A note on `implementers`

The contract sub-task loop reads this slot to decide which handoff blocks are sub-tasks. A block
naming an agent outside the list is treated as a review gate or a note, so nothing waits on it to
merge.

Leaving it `none` accepts the agents the plugin ships. Naming a wrong agent is worse than naming
none: the block silently stops being a sub-task and the loop reports work as unplanned.

`review-gates` is the companion slot. A reviewer opens no pull request, so a block naming one is a
step in the sequence rather than something to wait on for a merge. Declaring both lists is what
lets the loop report a name that is neither — almost always a typo or a shorthand — instead of
letting that block vanish from the plan with nothing to say it did.

## Worked shape

```
| `migration.root` | `src/AcmeApp.Persistence/Migrations/` |
| `safety-critical.roots` | `src/AcmeApp.Payments/`, `src/AcmeApp.Auth/` |
| `review.documents` | `CLAUDE.md`, `TESTING.md` |
| `implementers` | `acme-backend-dev`, `acme-frontend-dev` |
| `review-gates` | `acme-security-auditor` |
```