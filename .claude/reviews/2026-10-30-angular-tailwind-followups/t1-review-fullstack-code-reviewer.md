# t1 review — fullstack-code-reviewer

- **Contract:** `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (approved), sub-task t1 (issue #86, sub-issue #117)
- **Branch:** `task/2026-10-30-angular-tailwind-followups/t1-guard-post-edit-view-and-matching-precision` against `feature/86-angular-tailwind-followups`
- **Commits:** `07dc849` (failing tests), `1a99344` (implementation)
- **Files:** `.claude/hooks/architecture-guard.py` (+254/-43), `.claude/addons/angular-tailwind/documents/TAILWINDCSS_RULES.md` (3 lines), `.claude/hooks/tests/test_architecture_guard_precision.py` (new, 478 lines)
- **Verdict:** **fix then ship**

## Scope and drift

- The diff touches exactly the three files listed under block 1's "Files to touch". Nothing off-area.
- No version file changed. That is correct: a sub-task into a parent branch is in `parent` mode, and the version is raised once at landing.
- No UI surface is touched, so the End-User View audit does not apply.
- Suites I ran on this worktree:
  - `test_architecture_guard_precision.py`: 40 OK
  - `test_architecture_guard_scss.py`: OK
  - `test_architecture_guard_messages.py`: OK
  - `test_hook_data_files_project_first.py`: 29 passed
  - `test_angular_rule_coverage.py`: OK
- I also ran a separate probe script, kept outside the repo, against the guard for the edge cases below.

## BLOCKER

None.

## WARN

### W-1: a whole-decorator Edit reports the same inline rule twice (G-4 "reported once" not met). `architecture-guard.py:1276-1277`, `:1297-1303`, `:714-723`

```python
findings.setdefault(file_path_str, []).extend(scan_component_ts(new_content, ...))  # fragment line numbers
...
extra, hw = scan_whole_file_rules(path, texts, view, rule_exemptions)              # view line numbers
findings.setdefault(file_path_str, []).extend(extra)
...
key = (v.rule, v.line_no, v.line_text)
```

**Problem.** I reproduced this. Disk holds `TS_PLAIN`. The edit replaces `export class X {}` with itself plus a new `@Component({ selector: 'b', template: '<p></p>' })` block. The guard exits 2 but prints `inline-component-template` twice: once at line 5, numbered within the fragment, and once at line 9, numbered within the view. Both point to the same physical line with the same text. The de-duplication key includes the line number, and that number is relative to the fragment on one side and to the view on the other, so it can never collapse the pair.

This is the implementer's open point. It is a real defect against the contract, not something its wording allows:
- G-4 says "A rule that fires twice on the same line is reported once".
- The failure-mode table names "a MultiEdit reports the same violation N times" as a failure to prevent.

It is cosmetic only, because the exit code is still 2. `test_new_string_carrying_the_whole_decorator_still_blocks` misses it because it uses `assertIn`, not a count.

**Fix.** The rule is an "or": one finding is enough. Drop a view finding when the fragments already reported the same rule.

```python
already = {v.rule for v in findings.get(file_path_str, [])}
findings.setdefault(file_path_str, []).extend(v for v in extra if v.rule not in already)
```

Then tighten the test to `assertEqual(blocked_rules(r.stderr).count("inline-component-template"), 1)`. Keep the filter outside `scan_whole_file_rules`, or guard it with V-2. An exception there means "keep every finding".

### W-2: the G-5 quote-parity rule blocks a legitimate reference variable next to an apostrophe or a `<` in an attribute. `architecture-guard.py:594-596`

```python
segment = line[line.rfind("<", 0, start) + 1: start]
if segment.count('"') % 2 or segment.count("'") % 2:
    return False
```

**Problem.** I reproduced both:
- `<button aria-label="Don't save" #add>` is blocked as `hex-color`. The `'` inside the `"..."` value makes the `'` count odd.
- `<div [title]="a < b" #add>` is blocked. The `<` inside the value resets the segment, which then holds one `"`.

Both cases are realistic: aria labels, i18n text, comparisons in bindings. The code matches the contract's condition 2 literally ("an even number of `"` and of `'`"), so the contract wording is the weak spot. This is not a regression, since today every `#add` is blocked. But `TAILWINDCSS_RULES.md:61` now says "The check skips a template reference variable such as `#add`", and in these cases it does not.

**Fix.** Use a quote state machine, which is never looser on the blocked rows: `fill="#add"` and `"'#abc'"` both stay inside an open quote.

```python
quote = None
for ch in line[line.rfind("<", 0, start) + 1: start]:
    if quote:
        if ch == quote:
            quote = None
    elif ch in "\"'":
        quote = ch
if quote:
    return False
```

Any change to condition 2 needs a one-line contract amendment. The other route is to record the apostrophe case as a pinned limit.

### W-3: the V-2 fallback of the whole-file pass is itself unguarded. `architecture-guard.py:1298-1302`

```python
except Exception as e:  # noqa: BLE001
    log(f"whole-file pass failed (judging fragments): {e}")
    extra = []
    hw = [w for t in texts for w in scan_height_chain_invariant(t, path, rule_exemptions)
          ] if is_template_html(path) else []
```

**Problem.** If `scan_height_chain_invariant` caused the first exception, the fallback calls it again on the fragments, unguarded. A second raise reaches the outer catch at `:1343-1345`, which exits 0. Line-rule findings that would block, such as a gray utility already collected in `findings`, are then thrown away.

Today's code would fail open on the same fragment too, so text that blocks today still blocks. But contract `:105` says "no new code path reaches the outer catch", and this line is a new code path. The forced-raise test does not cover it, because it patches only `scan_whole_file_rules`.

**Fix.** Wrap the fallback.

```python
try:
    hw = [...] if is_template_html(path) else []
except Exception as e2:  # noqa: BLE001 -- V-2: the warning is advisory; keep the block path alive
    log(f"height-chain fallback failed (no warning): {e2}")
    hw = []
```

## NIT

- **N-1: Data Shape divergence.** `architecture-guard.py:317-323`. `PostEditView` adds a `disk` field. The contract's Post-edit view value object (`:122`) lists path, text-or-unavailable, source and reason. The field is needed for the "introduced" comparison, but no HANDOFF explains it. Amend the value-object row, or note it in the t1 HANDOFF.
- **N-2: an empty `old_string` with `replace_all` blows up quadratically.** `architecture-guard.py:699-708`. `text.count("")` is `len+1`, and `text.replace("", new)` inserts `new` between every character. A 50 KB file with a 2 KB `new_string` builds a string of about 100 MB on a low-memory machine before the tool itself rejects the edit. A `MemoryError` is caught (fail closed), but only after the time and memory are spent. Fix: `if not old: return unavailable("old-string-missing")`.
- **N-3: wrong file patterns in the docstring.** `architecture-guard.py:44`. The G-2 Known-limits line says "(`*.component.html`, `.ts`, `.scss`)", but recognition is `*.component.ts` and `*.component.scss` (`:1127-1132`). t2 rewrites recognition, so correct the line there, or now.
- **N-4: the G-5 accepted limit is wider than the `  #fff` example suggests.** Two cases pass, both confirmed:
  - `  background: #fff !important`, on a continuation line of a multi-line `style` value, or the last declaration without `;`;
  - `<style> .x { color: #eee } </style>`.

  Both fall within the four conditions, so they are inside the contract. But `#fff`, `#eee`, `#ccc` and `#ffffff` are the most common hard-coded colours. A cheap follow-up: also require that the previous non-space character is not `:`. That closes the CSS-declaration shape without touching any allowed row.
- **N-5: two doc wording gaps.**
  - `TAILWINDCSS_RULES.md:148` lists the "cannot be built" reasons but leaves out that a guard error while building or in the pass also falls back to the fragment.
  - `:61` gives two of the four G-5 conditions.

  Neither line is false in direction, so they pass the journal 2026-10-04 check, with W-2 as the one caveat.

## INFO (no action required)

- **Height-chain warnings now fire on every edit to a file with a broken chain,** unrelated edits included, because the view is judged rather than the fragment. The contract intends this. It is a noise trade during the warning trial.
- **The de-duplication key is fragment-relative.** Two different edits that add the same violation text at line 1 of their own fragments collapse into one report, so a second location can be hidden. Acceptable under "each violation once", and the message is still a block.

## What checked out

- **G-4 construction:**
  - strict UTF-8 decode;
  - CRLF folded in the disk text, `old_string` and `new_string`;
  - exactly once unless `replace_all`;
  - MultiEdit edits applied in order, one view per file per call;
  - the reasons `file-unreadable`, `not-utf8`, `old-string-missing`, `old-string-ambiguous` and `builder-error`;
  - a Write keeps today's behaviour, with no disk text and the inline rules judged on the content.
- **Line rules stay on each edit's new text.** The whole-file rules run once per file per call.
- **V-2 steps:**

  | Step | Location | When it raises |
  |---|---|---|
  | builder | `:1291-1295` | view unavailable |
  | comparison | `:640-643` | counts as introduced |
  | de-duplication | `:1311-1314` | every finding is kept |
  | G-5 test | `:604-608` | the token is a colour |
  | whole-file pass | `:1296-1302` | falls back to the fragments; see W-3 for the residual gap |

- **Encoding on stderr.** With a cp1252 stderr and a warning line that holds a non-cp1252 character, the guard still exits 2. Python's stderr uses `backslashreplace`, so a print cannot fail open.
- **Injection and performance.** No shell, eval or dynamic import. The cost is one file read and a linear count and replace per edit. Windows paths compare as the same strings `extract_contents` produced.
- **`TAILWINDCSS_RULES.md`.** Only the "Enforced by" lines at `:61`, `:109` and `:148` changed, and they match the code (W-2 caveat for `:61`).
- **Known-limits docstring.** It covers W5, W6b, W8, W11, G-2 and G-5, and each limit is pinned by a test.

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 0 |
| WARN | 3 |
| NIT | 5 |

**Verdict: fix then ship.** First fix W-1, the duplicate inline report. W-3 is a four-line change. W-2 needs a contract decision: fix it with the quote state machine, or pin it as a limit.
