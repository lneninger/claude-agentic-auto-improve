# claude-agentic-auto-improve

A reusable plugin repository containing generic agents, skills, hooks, and registries for any Claude Code project following the Data-First Engineering Protocol.

## What's Included

### Agents (`.claude/agents/`)

Generic, project-agnostic agents that can be used in any Claude Code project:

- **data-architect.md** — Designs data shapes and reusable mechanisms before implementation
- **fullstack-code-reviewer.md** — Adversarial code review for correctness, security, performance
- **senior-test-engineer.md** — Writes RED tests first (TDD)
- **test-strategy-critic.md** — Reviews test suites for value vs over-mocking
- **migration-safety-reviewer.md** — Validates database migrations for production safety
- **security-auditor.md** — Focuses on auth, encryption, and user-data boundaries
- **sql-performance-reviewer.md** — Analyzes query plans and index coverage
- **ui-ux-designer.md** — Visual design, theming, and user experience

### Skills (`.claude/skills/`)

Skill implementations that orchestrate multi-step workflows:

- **design-first/** — Data-First Engineering Protocol entry point
- **tdd-first/** — Test-driven development cycle
- **debug/** — 4-phase systematic debugging (REPRODUCE → ISOLATE → HYPOTHESIZE → VERIFY)
- **verify-before-done/** — Pre-completion verification gauntlet
- **north-star/** — North-star problem statement and discovery
- **north-star-review/** — Review north-star against implementation
- **list-contracts/** — Inventory of concept contracts
- **task/** — Task assignment and worktree setup

### Hooks (`.claude/hooks/`)

Python validation and state-management hooks that enforce protocols:

- **concept-gate.py** — Blocks Edit/Write on non-trivial files without an approved contract
- **architecture-guard.py** — Prevents anti-patterns in templates and CSS
- **codegraph-first-guard.py** — Gates file-system investigation behind CodeGraph queries
- **plain-language-guard.py** — Enforces clear writing standards
- **db-destructive-guard.py** — Prevents accidental database destruction
- **db-research-readonly-guard.py** — Enforces read-only connections for forensic queries
- **codegraph-turn-tracker.py** / **codegraph-turn-reset.py** — Manages CodeGraph investigation gate state
- **integration-check.py** — Warns on backend/frontend contract drift
- **mark-models-dirty.py** — Triggers auto-regeneration of generated code
- Utilities: `_error_log.py`, `_memory_common.py`, `_project_paths.py`

### Registries (`.claude/registries/`)

Two-tier registries (Universal + per-project) that document reusable patterns:

- **MECHANISMS.md** — Reusable architectural patterns (Universal section only in plugin)
- **VOCABULARY.md** — Business domain terminology and entity definitions (Universal only)
- **JOURNAL.md** — Lessons learned from design contracts (Universal only)
- **INTEGRATION.md** — Cross-system integration patterns (entire file, project-independent)

### References (`.claude/references/`)

Decision tables and design guidance:

- **codegraph-decision-table.md** — When to use which CodeGraph tool
- **end-user-view-standard.md** — User-facing documentation patterns

## File Structure

```
.claude/
  agents/              → 8 generic agents (project-agnostic)
  skills/              → 8 generic skills
  hooks/               → 10 generic hooks + 3 utilities
    tests/             → Hook test suites (pytest)
  registries/
    MECHANISMS.md      → Universal Patterns section only
    VOCABULARY.md      → Universal section only
    JOURNAL.md         → Universal section only
    INTEGRATION.md     → Entire file
  references/          → Decision tables, design guidance
.gitignore
README.md
CONTRIBUTING.md
```

## Quick Start: Using This Plugin in a New Project

### 1. Clone the plugin

```bash
cd <your-new-project-dir>
git clone https://github.com/your-org/claude-agentic-auto-improve .claude-plugin
```

### 2. Copy the .claude structure

```bash
# Create .claude directory if needed
mkdir -p .claude

# Copy plugin assets to your project
cp -r .claude-plugin/.claude/* .claude/

# Keep plugin-specific items in .claude/plugin-managed/ (optional)
# or commit copied files directly
```

### 3. Extend with project-specific additions

Create project-local sections in your registries:

```bash
# Edit .claude/registries/MECHANISMS.md
# Add a new "## Project: MyProject" section after the Universal section

# Edit .claude/registries/VOCABULARY.md  
# Add project-specific terms

# Create project-specific agents in .claude/agents/
# (prefix trading-only agents, domain-specific agents, etc.)
```

### 4. Configure hooks in .claude/settings.json

Register hooks that apply to your project:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "run": "python",
        "with": [".claude/hooks/concept-gate.py"],
        "on": ["Edit", "Write"],
        "description": "Enforce Data-First protocol"
      },
      {
        "run": "python",
        "with": [".claude/hooks/architecture-guard.py"],
        "on": ["Edit", "Write"],
        "description": "Prevent CSS/template anti-patterns"
      }
    ]
  }
}
```

Full `.claude/settings.json` template: See the hook registration docs below.

### 5. Initialize CodeGraph

```bash
codegraph init -i
```

## Integration with Consuming Projects

Once your project has adopted this plugin, keep it synced:

### Syncing Changes

The main StockToolScalpingMachine repository uses `tools/sync-plugin.cmd` to keep the plugin updated:

```bash
# From the main repo
tools\sync-plugin.cmd
```

This bidirectional sync:
- Pushes generic agents/skills/hooks from main → plugin
- Pulls updates from plugin → main
- Preserves project-specific sections in registries
- Detects conflicts and requires manual resolution

See [CONTRIBUTING.md](CONTRIBUTING.md) for conflict resolution workflow.

### Adopting Updates in Your Project

When the plugin is updated:

1. Pull plugin updates into your project
2. Merge plugin-managed sections with your local customizations
3. Test that hooks, agents, and skills still work in your project

## Documentation

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Sync workflow, conflict resolution, and how to propose changes
- **Hook test suites** — `.claude/hooks/tests/test_*.py` — pytest-based validation
- **Each agent/skill** — see the `## When to Use` section in each `.md` file

## Status

First release extracted from StockToolScalpingMachine project (2026-09-10).

Cross-project adoption: This plugin is designed to be vendored into new Claude Code projects. See **Quick Start** above.
