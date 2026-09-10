# claude-agentic-auto-improve

A reusable plugin repository containing generic agents, skills, hooks, and registries for Claude Code projects.

## What's Included

- **Agents**: Data-Architect, Code Reviewers, Test Engineers, UI/UX Designer
- **Skills**: Design-First, TDD-First, Debug, Verify-Before-Done
- **Hooks**: Pre-tool validation, architecture guards, data-first enforcement
- **Registries**: Universal patterns and vocabulary

## File Structure

`
.claude/
  agents/              → Generic agent definitions (project-agnostic)
  skills/              → Skill implementations (generic)
  hooks/               → Python validation and state-management hooks
  registries/          → MECHANISMS.md and VOCABULARY.md (Universal sections only)
    templates/         → Contract and brief templates
  references/          → Decision tables, design guidance
.gitignore
.mcp.json
settings.json
`

## Integration

This plugin is designed to be synced into consuming projects via the sync-plugin.cmd script in the main StockToolScalpingMachine repository.

See CONTRIBUTING.md for sync workflow and conflict resolution.

## Status

Extracted from StockToolScalpingMachine (2026-09-10).
