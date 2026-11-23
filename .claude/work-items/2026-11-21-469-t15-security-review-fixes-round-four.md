---
id: 469
issue_offer: opened
title: Security review fixes, round four
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/469
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t15-security-review-fixes-round-four
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/473
issue_link: deferred
status: shipped
created: 2026-11-21
---

# Security review fixes, round four

## Problem statement
Sub-task 15 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 15. Security review fixes, round four (`python-ai-developer`)

**Depends on:** 13 — it fixes the findings of the fourth security review (block 14), but does not name block 14, because the loop never releases a block whose dependency reads `blocked` (the same convention as blocks 8, 11 and 13, which name neither 4, 10 nor 12). It is not dispatched until the contract is re-approved with the amendment-4 answers.

**Files to touch:**
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_db_destructive_guard.py`

`db-research-readonly-guard.py` is listed for L2 only (its `_audit`). Its decision code is not changed (L1 stays accepted; it has no human-only class). It gets the comment-aware masker without an edit, because its Arm-write test loads the destructive guard's masker (`:501-518`). Its L2 row and its arm-write comment rows go in `test_database_override.py`, beside block 13's I2 rows and the destructive guard's arm-write comment rows. `test_db_destructive_guard.py` is listed for two things: the Q1 rows D1 to D6 and D8 and the masker exclusion rows, which are destructive-command detection rows and belong with that suite; and the retirement, by name, of a row that pins one of t14's shapes as allowed (see the constraints). `_switches.py` and `_shell_write_targets.py` are not listed and are not changed.

**What the rows prove, plainly.** As in blocks 11 and 13, the destructive guard is the deciding guard for B1, P1, P2, P3 and T1, and only its rows expect a block. This contract does not claim that the read-only guard blocks any of these shapes. Per t14, armed, the read-only guard asks and claims the arm on the shapes that hold a database write (A1, A1p, X1e, X3a, X3h, A4, A7, A10, A11, A13, A21, A41, A53; L1, accepted), and whether the host then shows a prompt rests on the ASSUMED "a block beats an ask". For Q1 the rows are the destructive guard's: D1 to D6 expect a block, and D8, armed, expects the normal armed ask with the arm claimed, because an EF removal is not human-only. The read-only guard's outcome on D1 and D3 (a block, from its own write check) is not changed and is not the evidence. For L2 both guards have a row, because each writes its own audit log. For the arm-write comment route both guards have rows, because each runs its own Arm-write test; each guard's refusal is its own evidence.

**Pre-written TASK block:**
```
TASK: Fix findings B1 (round four), P1, P2, P3, T1, L2 and Q1 of the fourth security review
  (Q1 and the inverted classifier by the user's answers of 2026-11-21, both yes), each with
  test rows, and nothing else.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the No-prompt
  classes rule: the mid-word quote clause, the Comment-aware masker, the command-start words,
  Mention positions and Name matching; the Audit-log rule's link-count check; Failure Modes;
  the amendment-4 Open Questions and the user's answers recorded there); the review
  .claude/reviews/2026-11-16-file-based-switches/t14-security-re-review-round-four-security-auditor.md
  (findings B1, P1, Q1, P2, P3, T1, L2, F1; the Evidence tables "New shapes at head" and "Q1 at
  head"; the Disposition). Read it in full. Its row ids, clause order, script paths, quotes,
  comment text and escape characters are exact; its destructive statements are named in
  words by the report's own rule, so rebuild each one from those words by string joining, as
  the existing rows do. Naming: t14's findings P1, P2 and P3 are not t4's probes P1 to P9;
  use the t14 row ids (X, A, D, V, W, CV, CW, M) for rows.
FILES: as listed.
CONSTRAINTS:
  - RED before GREEN, in this one block (the block 8, 11 and 13 convention): commit the new
    rows first, run them at the parent tip, and list in the pull request body each new row
    under its kind, with its outcome at the tip and at your head. The fix commit comes after.
    Every row is one of four kinds, and no other kind exists:
    (1) Copied rows, every row copied from t14. Each MUST fail at the tip. A copied row that
    passes at the tip has been mistranscribed (a lost backslash, backtick or apostrophe, the
    comment on the wrong line, a backslash path where t14 used forward slashes): fix it until
    it fails at the tip; never relabel it.
    (2) Class rows: the two class sets, the arm-write comment rows, the multi-hop pipe and
    substitution rows, and the constructed P2 and P3 rows with a separate value or word. Each
    is expected to fail at the tip. One that already has its expected outcome at the tip
    moves to kind (3), named so in the pull request body.
    (3) Mutation rows: a row whose expected outcome already holds at the tip, because the
    shape it guards only becomes dangerous with this fix. These are named here: the masker
    exclusion and escape rows, the here-document spelling rows, the cross-shell continuation
    rows, the P2 rows with the value after =, exception (a) written as a backtick or $(
    command, and any class row moved from kind (2). Such a row cannot fail at the tip, so its
    proof is a named mutation of your fix (for example "the comment rule uses the bash reading
    only", "the here-document start knows only <<WORD", "joining is applied to the whole
    text", "exception (b) looks at the next segment only", "the long option is skipped only
    with a separate value"). Apply the mutation in a scratch copy, show the row fails under
    it, do not commit it, and record the mutation and the result in the pull request body.
    (4) Controls: rows this TASK names as must stay allowed, or as already blocking at the tip
    (D0, D0e, D7). Each passes at the tip and at your head. Each allowed mention-word row is
    also shown to fail under the mutation "the mention list is empty".
  - Process lesson from t14 (each earlier round copied only the last report's shapes): besides
    the copied rows, write class rows for the two new classes, in bash AND PowerShell, each
    failing at the tip: (i) a # comment holding an apostrophe on the line before the script,
    on an echo / Write-Host, git commit -m, grep / Select-String and gh pr create line, and
    one with the comment at the end of a line that itself does something; (ii) a quote opened
    mid-word right before the script name, single and double quote, forward-slash and
    backslash prefix (backslash in bash only where bash keeps it), after a separator, after a
    command-start word (then, sudo) and inside a launcher's quoted argument. A class row that
    already blocks at the tip is a kind (3) mutation row, with its mutation named.
  - Script spelling: tools/db-protection/update-dev-database.cmd in bash rows and
    tools\db-protection\update-dev-database.cmd in PowerShell rows, except where t14 writes a
    forward-slash PowerShell row (X3f, X3g, X3h): copy each row exactly as t14 writes it. A row
    that exists in one shell only is written once, in that shell. Each row runs the
    destructive guard alone, in its own fresh temporary project with its own arm.
  - B1 and P1. (a) Mid-word quote: in each of the four readings, a quote opened inside the
    word that holds the name belongs to that word, so the word is judged by its position;
    the quote-blind reading also strips a quote after the folder prefix and quotes inside it.
    (b) Comment-aware masker, for all four consumers (user answer 2026-11-21: yes), as the
    No-prompt classes rule words it. The bash reading and the PowerShell reading, each with
    its own escape model and each recognising its own comments, here-documents or
    here-strings and block comments, decide whether a # is outside quotes and starts a word
    (start of text or line, unescaped space or tab, ; | & ( )); _skip_quoted's pairing never
    decides it. A line comment is blanked to the end of its physical line only where both
    readings start one at the same #, and is never scanned for quotes. Nothing is blanked in
    a here-document body (every delimiter spelling the rule names, to the exact end line or
    to the end of the text), after an unparsable << that is not <<<, in a PowerShell
    here-string, on a line after --%, or inside <# ... #>, where no quote opens a span.
    Arm-write comment rows, in test_database_override.py, per guard (destructive and
    read-only), each guard as a separate process, in bash (touch) and PowerShell (New-Item
    -ItemType File): a line echo "x"  # don't, then on the next line the arm write of the
    path .claude/database-override.once, then echo 'y'; expect the arm-write refusal, exit 2. Control: a line that only names the arm inside a comment both readings agree on
    is allowed. Copied rows, armed, default mode, expect exit 2, no ask JSON, the
    arm still in place, the human-only instruction in the block text: A1, A1p, X1e, X3a, X3h.
    No arm, expect exit 2: X1, X1c, X1d, X3, X3b, X3i (bash); X1p, X3f, X3g (PowerShell).
  - Q1 (user answer 2026-11-21: yes), in test_db_destructive_guard.py, each in
    t14's shell and also in the other shell: D1 and D3 (comment apostrophe, then a removal of
    a non-disposable database through sqlcmd), D2, D4 and D5 (the same with an EF removal,
    including after a git commit -m line), D6 (an empty-table statement on a protected
    database through sqlcmd -d): expect exit 2. D8 (armed, the EF removal after a comment
    apostrophe): expect the ask JSON, exit 0, the arm claimed. Controls that already block at
    the tip: D0, D0e, D7. Masker exclusion rows (kind 3), each expecting exit 2: a
    here-document fed to sqlcmd whose body line holds a #temp table name and then a removal
    of a non-disposable database, once per delimiter spelling (<<WORD, << WORD, <<'WORD',
    <<"WORD", <<\WORD, <<E"O"F, and <<-WORD with a tab-indented end line), once with no end
    line, and once after an unparsable <<; a PowerShell here-string (@" and @') holding the
    same line; a PowerShell line with --% then # then a removal; a # inside a word ($#,
    ${#x}, a#b) before a removal on the same line; a PowerShell <# block whose second line is
    a removal. Escape rows (kind 3), each expecting exit 2, each in three forms (an EF
    removal after it; the human-only script after it; an arm write after it, per guard, in
    test_database_override.py): bash echo "a\" # b"; then the form; PowerShell
    Write-Host "a`" # b"; then the form; bash echo a\ # ; then the form; PowerShell
    echo a` # ; then the form; a bash $'…' span holding \' before the #; a PowerShell
    doubled quote before the #. Masker controls that must stay allowed: a commit message, an echo text and a pull
    request body holding # and apostrophes inside their quotes; a # comment that names the
    script; a # comment that names a destructive statement.
  - P2: add the long spellings of every valued option block 13 lists (--signal, --kill-after,
    --user, --group, --host, --prompt, --close-from, --chdir, --role, --type, --other-user,
    --unset, --adjustment, --replace, --max-args, --max-procs, --max-lines, --delimiter,
    --arg-file, --eof, --max-chars), the value in the next word or after =. Copied rows, no
    arm, expect exit 2: X41, X42, X43, X44, X45; armed, as above: A41. Constructed rows, one
    per long option, no arm, expect exit 2: with the value in the next word (kind 2) and
    after = (kind 3; t14 records --signal=KILL as already blocking). Control that must stay
    allowed: nice --adjustment 10 cat <script> (a mention after a valued long option).
  - P3 (user answer 2026-11-21: yes, fail-closed inversion with the closed mention list):
    implement the Mention positions sentence in _human_only_script_hits and only what it
    needs from _in_command_position. Every visible occurrence is invoked unless EVERY reading
    that sees it places it in a mention position (the closed word list in the rule, without
    sed, less and more; rg and git grep only under their argument rules; git with the listed
    subcommands; command -v / -V), and never after an environment change in the same call
    (the Environment rule), with exceptions (a) inside any substitution that is not itself
    a mention argument, or after & / . , (b) output reaching any non-mention segment through
    any chain of pipes or a redirection into a process substitution, (c) a redirection target
    of a non-mention command. Copied rows, no arm, expect exit 2: X4 to X11, X16, X18, X19,
    X20 (bash); X13, X14, X53, X86, X87b, X88b, X89b (PowerShell). Armed, as above: A4, A7,
    A10, A11, A13, A53. Constructed rows, no arm, expect exit 2: X15 winpty, X17 setsid, X80
    to X84 (doas, unbuffer, watch -n 1, flock, ionice); exception (a): $(cat <script>) as a
    command, eval "$(cat <script>)", bash <(cat <script>), PowerShell & (Get-Item <script>),
    and the backtick form (kind 3 where it already blocks); exception (b): cat <script> |
    bash, cat <script> | grep . | cmd, cat <script> | grep . | head -n 99 | sh,
    cat <script> > >(bash), PowerShell Get-Content <script> | iex and Get-Content <script> |
    Out-String | iex; exception (c): bash < <script>; the argument and Environment rules:
    rg --pre <script> x ., rg --pre=<script> x ., git grep -O<script> x, git grep -nO x --
    <script>, git grep --open-files-in-pager x -- <script>, RIPGREP_CONFIG_PATH=cfg rg x
    <script>, GIT_EXTERNAL_DIFF=bash git diff -- <script>, export X=1; cat <script>,
    PowerShell $env:GIT_PAGER = 'x'; git log -- <script>; the removed words: sed -n 1p
    <script>, less <script>, more <script>; and find . -name <script> (an accepted false
    block, named so in the pull request body, as are the removed-word rows). Allowed rows,
    one per mention word of the rule, each with the bare script path as its argument, in the
    shell the word belongs to, and one per shell for a quoted assignment value ($x =
    "<script>", X="<script>"), plus echo $(cat <script>) and cat <script> | grep . | head. You
    may add a read-only word to the list only for an existing must-stay-allowed row; name the
    word and the row in the pull request body. Never add a word that can run a program from
    its arguments, its environment or its options; if an existing must-stay-allowed row needs
    sed, less, more or another such word, stop and report an AMENDMENT.
  - T1: implement the Name matching sentence: the stem with or without .cmd or .bat and with
    trailing dots, not followed by a word character, dot or hyphen. Joining is per reading and
    only adds readings: an added bash reading joins backslash-newline outside single quotes and
    outside a bash comment; an added PowerShell reading joins backtick-newline outside single
    quotes and outside a PowerShell comment; an added splice reading per shell removes an
    empty quote pair touching a non-space character. Recognise comments first in each reading;
    never join a continuation inside a comment; never join on the whole text and never drop
    the unjoined readings. The masker runs before this on the original text. Look for the
    recover flag on the physical line and in the rest of each joined reading's line.
    Cross-shell rows (kind 3), no arm, expect exit 2: PowerShell Write-Host a \ then the
    script on the next line; bash echo ` then a newline and the script followed by `; a bash
    # comment ending in \ then the script on the next line; a PowerShell # comment ending in
    a backtick then the script on the next line (mutation: "joining is applied to the whole
    text"). Copied rows, no arm, expect exit 2: X21 (PowerShell),
    X21b, X23, X24, X22 (bash), X22p (PowerShell); armed, as above: A21. Controls that must stay
    allowed: cat tools/db-protection/update-dev-database.md and
    cat tools/db-protection/update-dev-database-notes.txt (another file, not the script). X25
    (concatenation) is the named text-guard limit: no row.
  - L2: in each guard's _audit, after the fstat check, require a link count of one before any
    byte is written; otherwise close the descriptor unwritten, skip the record and write the
    one standard-error line, as the Audit-log rule says. Rows, per guard, the guard as a
    separate process: a hard link at the log (os.link) to a file outside .claude/logs; the
    guard gives its normal block, the record is skipped, the other file is unchanged.
    Controls: block 13's regular-log, missing-log and rotation rows stay green.
  - Controls that must stay green, unchanged: MENTION_ROWS and LAUNCHER_ROWS in
    test_database_override.py, every block 11 and block 13 row, O11, O12, O13b, O14, and the
    must-stay-allowed rows r4.7a.6 to r4.7a.13 (with r4.7a.7b and r4.7a.12b) and r4.16.1 to
    r4.16.9 in test_db_destructive_guard.py. Add as allowed rows t14's controls CV1, CV2, CW1
    to CW5, M1c, M2, M2p, M3, M3b and the # comment that names the script; add M1, M1b, M4
    and X49 as rows that expect a block (accepted false blocks, Failure Modes).
  - Older-test search, one question per change, before the fix commit, recorded in the pull
    request body with the patterns used: (1) comment blanking: which existing rows hold a #
    outside quotes; (2) the inverted classifier: which existing ALLOW rows name a human-only
    script outside a quoted prose span; (3) the stem match: which existing rows name the stem
    without its extension; (4) continuation joining and empty-pair removal: which rows hold a
    trailing backslash or backtick before a newline, or '' / "", and in which shell; (5) the
    link count: which audit rows use a log with more than one link; (6) the Arm-write tests:
    which existing arm-write rows, in either guard, hold a # outside quotes; (7) the shortened
    mention list and the Environment rule: which existing ALLOW rows name a human-only script
    after sed, less, more, rg, git grep or an environment change. Then run the full guard suites on the fix
    commit.
  - Existing guard suites unchanged and green: test_switches.py, test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_shell_write_targets.py, test_switch_env_scan.py, and the
    db-protection fixture suite. If a row there expects ALLOW for one of t14's B1, P1, P2, P3
    or T1 shapes, it pins the defect: retire it by name in test_db_destructive_guard.py,
    replace it with the blocking row, and name both in the pull request body. A row whose
    flipped text stands entirely inside a # comment as the masker rule defines it is retired
    the same way, as the one intended loosening. Any other row that changes outcome: stop and
    report an AMENDMENT; do not edit it, and do not drop or weaken a reading or a list entry to
    make a row pass.
  - Do not fix L1, the other hooks' plain opens, or the text-guard limit (concatenation, a
    variable, -EncodedCommand, a copy under another name). Do not change the human_only flag
    in _decide, the forward EF update class, _shell_write_targets.py or _switches.py. In the
    read-only guard change _audit only.
  - Name destructive statements in words in the pull request body, never as literal command
    text.
  - Plugin version (project CLAUDE.md, Parent Branch Delivery Rule): this sub-task pull request
    goes into feature/file-based-switches and does NOT raise the version. Do not touch
    plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. check_version_bump.py runs in parent mode on this pull
    request and requires the head's version to equal the base's. The landing raises it once.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

---

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md - dispatched by /advance
