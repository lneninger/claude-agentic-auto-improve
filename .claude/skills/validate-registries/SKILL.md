---
name: validate-registries
description: "Scan .claude/registries/MECHANISMS.md and .claude/registries/VOCABULARY.md for dead file references. Reports any backticked path entries whose files no longer exist. Use to prevent the reusable mechanism registry from rotting when files are renamed or deleted. Use when: user says /validate-registries, 'check the registry', 'find dead links in MECHANISMS', or as a weekly sanity check."
user_invocable: true
---

# /validate-registries -- Registry Dead-Link Check

When invoked, run the `validate_registries.py` script and present its output to the user.

## Step 1: Run the validator script

```bash
py -3 ".claude/scripts/validate_registries.py"
```

Optional flags the user may pass:
- `--root <path>` — an extra repo root to resolve paths against (can be repeated)
- `--json` — structured JSON output instead of the human report

Example with an explicit repo root:
```bash
py -3 ".claude/scripts/validate_registries.py" --root "<absolute path to the repository root>"
```

## Step 2: Present the report

The script's output already has the shape you want — pass it through verbatim. It lists:

- Candidate repo roots it checked
- For each registry file: total references / alive / dead
- For each dead reference: line number, path, surrounding context

The script exits with code `1` if any dead references were found, `0` otherwise.

## Step 3: If dead references exist, propose fixes

For each dead entry, ask the user:

- Was this file **renamed**? If yes, update the registry entry with the new path.
- Was this file **deleted** because the mechanism was removed? If yes, remove the entry from the registry.
- Was this file **moved to another project** or is it in a location the script's root hints don't cover? If yes, re-run the skill with `--root` pointing at the correct repo.

Use `AskUserQuestion` with the dead-link list pre-filled as options. Do NOT blindly update the registry without the user confirming the intent.

## Step 4: Apply the fixes

After the user confirms:

1. For renames: edit `.claude/registries/MECHANISMS.md` or `.claude/registries/VOCABULARY.md` to update the path (the concept-gate hook bypasses `.claude/` edits so this is a direct Edit).
2. For deletions: remove the entry entirely.
3. Re-run the validator to confirm no dead entries remain.

## Step 5: Archive stale follow-up stubs

After the registry pass, run the stub archiver as a dry-run first to show the user what would be archived:

```bash
py -3 ".claude/scripts/archive_stale_stubs.py"
```

Stubs older than 30 days that still have `Status: stub` are reported. If the dry-run lists any, ask the user:

> "Should I archive these stubs? They'll be renamed to `<slug>.followup.archived.md` but remain on disk for historical reference."

If the user confirms, re-run with `--apply`:

```bash
py -3 ".claude/scripts/archive_stale_stubs.py" --apply
```

## Step 6: Report done

Summarize for the user: "X dead entries found, Y fixed, Z stubs archived. Registry is now clean."

## Notes on the script's resolution logic

The script builds a candidate root list from:
- The current working directory
- Each folder under `.claude/concepts` with known install hints (`d:/Dev/HIPALANET/<project>`, `~/Dev/<project>`, etc.)
- Any `--root` passed on the command line

If a project lives in a non-standard location and the script can't find it, pass `--root`.
