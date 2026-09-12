# Contributing to claude-agentic-auto-improve

This document describes the sync workflow, conflict resolution procedure, and how to propose changes to the plugin.

## Sync Workflow

The plugin repository is kept in sync with the main StockToolScalpingMachine repository via the `sync-plugin.cmd` script. Synced assets include:

- **Agents** (`.claude/agents/`): Generic agents only; trading-specific agents stay in the main repo
- **Skills** (`.claude/skills/`): Generic skills only; trading/domain-specific skills stay in the main repo  
- **Hooks** (`.claude/hooks/`): Generic validation and state-management hooks
- **Registries** (`.claude/registries/`):
  - `MECHANISMS.md`: Universal patterns section only
  - `VOCABULARY.md`: Universal section only
  - `JOURNAL.md`: Universal section only
  - `INTEGRATION.md`: Entire file (project-independent)

## Making Changes

### From the main repo (StockToolScalpingMachine)

1. Edit the file in the main repo under `.claude/`
2. Run the sync script (from the main repo root):
   ```bash
   tools\sync-plugin.cmd
   ```
3. The script will automatically push changes to the plugin repository

### From the plugin repo (claude-agentic-auto-improve)

1. Edit the file in the plugin repo
2. Changes flow back to the main repo on the next sync
3. **For agents**: flow is **one-way plugin → main only** (plugin is authoritative for generic agents)
4. **For other assets**: bidirectional, with conflict detection

## Conflict Resolution

Conflicts occur when both repositories have modified the same file since the last sync.

### Detecting Conflicts

Run the sync script:

```bash
tools\sync-plugin.cmd
```

On conflict, the script exits with code 2 and creates:
```
.claude\.sync-state\conflicts.json
```

The marker file contains:
- Timestamp of conflict detection
- List of conflicting files
- Hash and modification time for each version
- Resolution status

### Resolving Conflicts

1. **Read the conflict marker:**
   ```bash
   type .claude\.sync-state\conflicts.json
   ```

2. **Decide which version wins:**
   - Check modification times
   - Review changes on both sides
   - Manually merge if needed (prefer combining changes)

3. **Apply resolution:**
   - Edit the conflict file in whichever repo should be authoritative
   - For agents: resolve in the plugin repo (one-way semantics)
   - For other assets: edit in main repo (it's the canonical source)

4. **Re-run sync to clear the marker:**
   ```bash
   tools\sync-plugin.cmd
   ```

On success, the marker is deleted and the working copy is updated.

### Force Override (caution!)

To force-sync without conflict detection:
```bash
tools\sync-plugin.cmd --force
```

**Use this only when you are certain of the resolution.** It skips conflict detection entirely.

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | No action needed |
| 2 | Conflict | Resolve conflicts and re-run |
| 3 | Marker exists | Run with `--resolve` or delete the marker |
| 4 | Script error | Check error message and fix environment |

## Updating Registries (MECHANISMS.md, VOCABULARY.md)

The sync script handles registry files specially:

- **Universal section** (before `## Project:`) is synced bidirectionally
- **Project sections** (after `## Project:`) stay local to each repo

When editing MECHANISMS.md or VOCABULARY.md:

1. Edit only the Universal section in the plugin (lines before `## Project:`)
2. Or edit in the main repo and sync back to plugin
3. The sync script automatically preserves project-specific sections

## Testing Before Sync

Before syncing changes that affect agents or skills:

1. Test the change locally in the main repo
2. Verify `/design-first`, `/tdd-first`, or other skills still work
3. Verify agents still launch and behave correctly
4. Then run `sync-plugin.cmd` to push to plugin

## Proposing New Generic Assets

If you've created a new agent, skill, or hook that should be part of the plugin:

1. **Get approval** from the team that this is truly generic (not domain-specific)
2. **Place it in the main repo** (e.g., `.claude/agents/my-new-agent.md`)
3. **Run sync** to push it to the plugin:
   ```bash
   tools\sync-plugin.cmd
   ```
4. **Update this doc** to list the new asset in the Synced section above

## Troubleshooting

### Marker file won't clear

If `conflicts.json` persists:

```bash
REM Delete the marker file
del .claude\.sync-state\conflicts.json

REM Re-run sync
tools\sync-plugin.cmd
```

### Script gives "path not found" errors

Verify plugin repo exists one level up:
```bash
dir ..\claude-agentic-auto-improve\.claude\agents
```

If missing, clone it:
```bash
cd ..
git clone <plugin-repo-url>
cd <main-repo>
```

### Changes aren't syncing

Run the sync script with verbose output:
```bash
powershell -NoProfile -Command ". .\tools\sync-plugin.ps1 -MainRepoPath (Get-Location) -PluginRepoPath '..\claude-agentic-auto-improve' -SyncStateDir '.\.claude\.sync-state' -ConflictMarkerPath '.\.claude\.sync-state\conflicts.json' -Verbose"
```

## Questions?

Refer to:
- Plugin structure: [`README.md`](README.md)
- Main repo sync docs: `<main-repo>/tools/README.md`
- Plugin contract: `.claude/concepts/2026-09-10-plugin-sync-extraction.md`
