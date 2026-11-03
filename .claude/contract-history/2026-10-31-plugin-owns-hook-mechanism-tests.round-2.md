## Critique

(Round 1 moved to `.claude/contract-history/2026-10-31-plugin-owns-hook-mechanism-tests.round-1.md`.)

**Critic:** contract-critic (round 2)
**Date:** 2026-11-01
**Verdict:** warnings-only

### Round-1 findings, checked against the code

All ten are resolved in the body. B1: RP-1 and RP-2, and no time argument. B2: step units, but see WARN 1. W1: the import chain was checked at `auto_improve_finish_install.py:85-86` and `pr_merged.py:43`, and it is exactly the five files. W2: the whole-tree Settings shape, but see WARN 4. W3 and W4 were answered in Q2 and by the naming rule, but see NIT 1. W5: HR-, RP- and FA- collide with no ID series in `VOCABULARY.md` line 82. W6: RP-4 to RP-8. Both NITs are fixed (suffix match, exact Adjacent Areas line).

### Findings

- **[WARN] "The attribution list is never empty on NOT-READY" is false, and `outside_diff` is then vacuously true.**
  - **What is wrong:** `_p8_verify` sets NOT-READY from `reasons` alone (tree changed, forbidden paths, missing review coverage) even when every step reads `ok` (`land_contract.py:2556-2564`). That yields zero units. The note then says "no failure unit could be named", which is the wrong reason. "True only when every entry is `outside-diff`" is true over an empty list, so the Q1 advice would fire on a forbidden-path halt, which is the contract's own fault.
  - **Prior artifact ignored:** Work Item Brief line 33 (criterion 4); `land_contract.py:2556-2564`.
  - **Where in this contract:** `## Data Shapes → Failure units`: "So the attribution list is never empty on `NOT-READY`"; `## Extension Points`: "`outside_diff` (true only when every entry is `outside-diff`)".
- **[WARN] The seam that carries attribution into the Next Command is not named.**
  - **What is wrong:** `make_report` passes only an allow-listed set of facts to `next_command_for_outcome` (`land_contract.py:1739-1741`), and every other key goes into the report body. Block 3 can pass a unit test of `next_command_for_outcome` while a real P8 halt never shows the Q1 advice (criterion 5).
  - **Prior artifact ignored:** `land_contract.py:1736-1752`; `MECHANISMS.md` line 80 (Extend-by names its one seam; this contract names none).
  - **Where in this contract:** `## Extension Points`, the `land_contract.py` bullet; block 3, "adds the advice only when every entry is outside-diff".
- **[WARN] FA-1 says `in-diff` when both diffs touch the named file, but FA-5 says `undetermined` for the same case under `when_paths`.**
  - **What is wrong:** first match wins. A test file that the contract and the default branch both changed gets a confident "the contract changed <file>" reason, which is the confidently wrong reason line that round 1 warned about.
  - **Prior artifact ignored:** `.claude/contract-history/2026-10-31-plugin-owns-hook-mechanism-tests.round-1.md` line 41; this contract's Option D.
  - **Where in this contract:** `## Data Shapes → Failure attribution rules`: FA-1 "A named file is in the contract diff → `in-diff`" against FA-5 "`both diffs touch the step's paths`".
- **[WARN] The checker and the recorder judge settings with two different validators.**
  - **What is wrong:** `_parse_settings` refuses duplicate keys (`auto_improve_finish_install.py:1277-1290`). The checker's `settings-unreadable` does not, so a file the recorder refuses can be checked, with the last duplicate winning. `_parse_settings` also checks only down to group level (`:1303-1308`). Block 2's "every malformed level, tested" either adds a second handler-level validator or tightens a parser that the `hooks` and `addon` subcommands share, which would be an undeclared change to them.
  - **Prior artifact ignored:** this contract's Option E ("two readers of one shape drift"); `MECHANISMS.md` line 56, Guard rules file (fail closed).
  - **Where in this contract:** `## Data Shapes → Settings shape`; refusal row `settings-unreadable`; block 2: "Reuse malformed-settings, unexpected-settings-shape (every malformed level …)".
- **[WARN] In issue #148's own case, every unit is `undetermined`.**
  - **What is wrong:** the README step `check_hook_registrations.py --project .` names no diff path (`--project` starts with `-`, and `.` is not a path in either diff), and block 4 gives it no `when_paths`. So when the default branch changes `.claude/settings.json`, FA-1 to FA-4 never fire, and the split the brief asks for (line 27) is never made for the checker step.
  - **Prior artifact ignored:** Work Item Brief lines 27 and 33; `land_contract.py:1315-1334`.
  - **Where in this contract:** `## Data Shapes → Files a unit names` ("A `step` unit names every command argument …"); block 4: "add a landing step running check_hook_registrations.py --project .".
- **[WARN] Confidence is "High" on the import chain while two ASSUMED entries cover it, and one of them is literally false.**
  - **What is wrong:** importing `auto_improve_finish_install` sets `sys.dont_write_bytecode = True` and inserts into `sys.path` (`auto_improve_finish_install.py:80-83`). That is a side effect beyond importing its dependencies.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04, "A VERIFIED parser claim must be tested on the unfilled and the missing case" (check a claim against the code).
  - **Where in this contract:** `## Confidence`: "High on … reuse (the installer row readers and import chain were read)"; `## Uncertain Assumptions`: "importing `auto_improve_finish_install` has no side effect beyond importing its dependencies".
- **[NIT] The naming rule contradicts the contract's own identifiers.** It says "every refusal code … says 'hook registration profile' in full", yet the codes are `registration-profile-missing` and `registration-profile-unreadable`, the flag is `--registration-profile`, and the key is `registration_profile`.
- **[NIT] The FA-2 and FA-3 reason "the default branch changed <path>" can be false.** After P7b, `merge_diff` includes the landing's own version-raise commit (`land_contract.py:2175`) and paths resolved by hand.
- **[NIT] "Next Command" and "Landing Report" are listed as existing VOCABULARY.md terms, but no entry defines them.** "Project profile" is a `MECHANISMS.md` entry (line 62), not a vocabulary entry.
- **[NIT] Block 3's "put the step's named test file in the contract diff" cannot apply to `hook-tests`.** Its inline `-c` command names no file (`.claude/work-item-conventions.json:105-111`). Block 3 also has "Depends on: none" while it reads the real conventions file, whose step list block 1 changes.
- **[NIT] Block 4 reads the README `<version>` when its sub-task pull request opens.** P7b raises the version relative to `origin/<default>` at landing time (`VOCABULARY.md` line 71), so the two can differ if another landing goes in first.

### Applicable journal entries

- **2026-10-16 — "Missing project file" refusal, unset root and set-but-absent file:** heeded by `paths-not-given`, `settings-missing`, `registration-profile-missing` and `registration-settings-missing`.
- **2026-10-15 — A script that reads a project-owned file must be told which project:** heeded (explicit paths only).
- **2026-10-04 — Detect an install mode by what the sync actually delivers:** heeded by the five-file set and `checker-dependency-missing`.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case:** heeded for structure; the duplicate-key and side-effect gaps are in WARN 4 and WARN 6.
- **2026-10-04 — Check a documented guard behaviour against the guard's code:** heeded (exit 2, closed set).
- **2026-10-05 — A documented "missing file means the default" must read one named location only:** heeded (project layer only).
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam:** heeded (the recorder extends Preview-hash apply).
- **2026-10-28 — A new term's definition must be true against every existing member:** heeded. The Registration row identity covers the `hooks.json` rows, including the same file under three matchers.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out:** heeded (attribution adds no refusal).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body:** heeded. Every round-1 finding and Q1 to Q4 answer is in the body.
- **2026-10-04 — A root locator can return the consumer itself under vendoring:** not addressed. The checker never calls `find_plugin_root`.

### Requested checks

- **Acceptance criteria:** 1 is covered by block 1's five named classes; 2 by HR-1 to HR-5 and the exit codes; 3 by block 5's single-place check and the README; 5 by Q1 and block 4, subject to WARN 2; 6 by block 1's failure paths. Criterion 4 is covered for regression steps, and only partly for a NOT-READY verdict that comes from `reasons` (WARN 1).
- **Parent Branch Delivery Rule:** the `**Work Item Brief:**` header is at line 8, and the five blocks are numbered with the review as block 5. No Files to touch list names a `MANIFESTS` file (`check_version_bump.py:25-26`), and P7b raises the version once. No layout defect was found by reading.

### What the critic did not check

- `pr_merged.py --contract <slug> --status --json`, `derive_area.py` and the budget estimate were not run, because the critic has no shell. The layout and the area were checked by reading (`area-mapping.json` has no areas).
- `INTEGRATION.md`, the registry digest and `.claude/north-stars/` are absent, and no project tier exists, so only Universal-tier checks were applied.
