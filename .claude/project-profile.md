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
| `review-gates` | *(the agents that review rather than implement, or `none` to accept the plugin's own)* |

### A note on `implementers`

The contract sub-task loop reads this slot **together with** `review-gates` to resolve the agent a
handoff block names. What makes a block a sub-task is its `Files to touch` list, never which of the
two slots its agent came from.

Leaving it `none` accepts the agents the plugin ships. Naming a wrong agent is worse than naming
none: the name resolves in neither slot, so the block becomes a contract defect that halts the whole
plan until the contract is amended.

`review-gates` is the companion slot. **A review gate writes a review artefact, so it opens a pull
request exactly as an implementer does**, and a block naming a gate is waited on for its merge like
any other. That artefact lives at `.claude/reviews/<contract-slug>/<sub-task-id>-<gate-agent>.md`
and carries a fixed `**Verdict:**` header, which the loop parses to decide whether to release what
depends on it. The architect declares that path and never creates the file, because a pre-created
stub makes *reviewed* and *never ran* indistinguishable under a file-exists check.

Declaring both lists is what lets the loop report a name that is neither — almost always a typo or
a shorthand — instead of letting that block vanish from the plan with nothing to say it did.

## Worked shape

```
| `migration.root` | `src/AcmeApp.Persistence/Migrations/` |
| `safety-critical.roots` | `src/AcmeApp.Payments/`, `src/AcmeApp.Auth/` |
| `review.documents` | `CLAUDE.md`, `TESTING.md` |
| `implementers` | `acme-backend-dev`, `acme-frontend-dev` |
| `review-gates` | `acme-security-auditor` |
```