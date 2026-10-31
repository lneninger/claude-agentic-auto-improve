# t2 review: guard paths and file recognition (fullstack-code-reviewer)

- **Contract:** `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (approved), block 2 of the Implementation Handoff
- **Branch:** `task/2026-10-30-angular-tailwind-followups/t2-guard-paths-and-file-recognition` against `feature/86-angular-tailwind-followups`
- **Production files reviewed:** `.claude/hooks/architecture-guard.py`, `TAILWINDCSS_RULES.md:29,54`, `ANGULAR_CODE_RULES.md:37`, `skills/promote-ui-rule/SKILL.md`
- **Tests (read, not run as suites):** `.claude/hooks/tests/test_architecture_guard_paths.py`, `.claude/scripts/tests/test_design_document_paths.py`
- **Evidence:** one short probe script (outside the repo) ran the guard in a subprocess against temporary projects. Its results are quoted under each finding. No long suites were run.

## Verdict: FIX THEN SHIP

No blockers. The code does what G-1, G-2, G-3 and V-2 say, with no divergence that needs a contract change. The six files changed are exactly block 2's `Files to touch`, there is no off-area drift, and no version file changed (Rule V; parent-branch delivery). The warnings below are real costs in a hook that runs on every edit in every install. WARN-1 and WARN-2 are contract-level questions for the user. WARN-3 to WARN-7 are cheap code or text fixes.

---

## BLOCKER

None.

---

## WARN

### WARN-1: G-2 now blocks Angular test and story files that use inline host components (contract gap, escalate). `architecture-guard.py:1173-1179`

`is_component_ts` leaves out only `.spec.ts` and `.d.ts`, as G-2 says. Angular Storybook stories, Cypress component tests and Jest `.test.ts` files nearly always declare host components with inline `template:`. Before t2 these files were never scanned. Now a Write of any of them is blocked by `inline-component-template` (A-003). Probe:

```
stories.ts inline tpl -> exit 2 [inline-component-template]
test.ts    inline tpl -> exit 2 [inline-component-template]
cy.ts      inline tpl -> exit 2 [inline-component-template]
spec.ts    inline tpl -> exit 0
```

The implementation follows the contract. The exclusion list in the contract is too short. Recommendation for the user: widen G-2's exclusion to test and story suffixes (`.test.ts`, `.cy.ts`, `.stories.ts`, and possibly `.harness.ts`), or say in the contract that blocking them is intended.

### WARN-2: the evidence pattern is not specific to Angular. Non-Angular decorators and mere mentions count. `architecture-guard.py:1144-1155`

`RX_COMPONENT_DECORATOR` runs on raw text, with comments and strings left in. Probe:

```
plain util.ts whose comment says "@Component(" + 'text-gray-500'  -> exit 2 [gray-utility:text-gray]
doc.html beside doc.ts holding the string 'use @Component( here' -> exit 2 [inline-style]
Vue class component (vue-class-component @Component({...})) foo.ts + foo.html with style= -> exit 2 [inline-style]
```

The contract's mitigation for "G-2 blocks a project that is not Angular" is this evidence rule. Vue 2 class components (`vue-class-component` / `vue-property-decorator`) use the same `@Component(` decorator with the same `<stem>.ts` + `<stem>.html` layout, so that mitigation fails for them. The guard is a default hook in every install.
- Cheap and within the contract: match on `strip_ts_comments(text)` (already in the guard, `:881`), so comments stop counting.
- Contract question (escalate): also require an `@angular/core` import in the same file before a suffix-less file counts as recognised.

### WARN-3: extra reads and view builds on every `.ts` edit, quadratic for MultiEdit. `architecture-guard.py:1338-1339`, `:1188-1195`, `:1147-1150`

- `is_component_ts(path, post_edit_text(...))` builds its argument before the name check runs. So every Edit of a `.ts` file builds a full post-edit view (a full disk read plus every edit applied), even for `*.component.ts`, `.spec.ts` and `.d.ts`, where the answer does not depend on the text. This happens in every project, Angular or not.
- `extract_contents` gives one pair per MultiEdit edit (`:1131-1139`), and each pair builds the view again with all N edits. That is O(N²·size) per call. The whole-file pass then builds it once more (`:1356`).
- `sibling_has_decorator` reads the sibling `.ts` with no size limit, once in the main loop and again in the whole-file pass (`:721`). The non-UTF-8 probe prints the "file check failed" line twice, which confirms the double read.

Fix (behaviour unchanged):
- In `main`, check the name before building the view: `.component.ts` gives true; `.spec.ts` and `.d.ts` give false.
- Keep the view in a dict keyed by file for each call, and reuse it in the whole-file pass.
- Cache `sibling_has_decorator` by path for the call.

### WARN-4: V-2 for "G-1's root walk" protects only the root lookup, not the walk. `architecture-guard.py:261-281`

The `try` covers only `app_root_segments()`. The walk itself stays outside it: `file_path.resolve()` / `Path.cwd()` at `:267` and `rules_file.exists()` at `:272`. On Python 3.12, which this machine runs, `Path.exists` raises `PermissionError` and does not return False. `load_app_rules` is called first, unguarded, at `scan_template_html:743` and `scan_component_ts:820`. If the walk raises there, the guard reaches the outer catch (`:1413-1415`, exit 0) with an `inline-style` violation in the same text, which blocks today. The lines that can raise predate t2, but the contract names the whole walk as the V-2 step, and V-2 says no path may reach the outer catch.

Fix: wrap the walk. On a raise, retry with `[_DEFAULT_FRONTEND_PROJECTS_ROOT]`. If that also raises, return `None`, so the other rules still run. Add a forced-raise test on a seam inside the walk itself.

### WARN-5: G-1 does not normalise the configured root, so Windows separators or padding silently turn app rules off. `architecture-guard.py:116-122`

G-1 brings in multi-segment roots, and Windows users will write `"frontend\\apps"`. Probe, with a matching `.app-rules.json` present:

```
"apps\\web"   -> exit 0 (app-banned-class not found)
" apps "      -> exit 0
"apps//web"   -> exit 0
"/Apps/Web/"  -> exit 2 (works: slashes stripped, case folded)
```

`detect_app` and the walk fail together, so the failure is consistent but silent. Fix in `load_project_settings`: `str(root).strip().replace("\\", "/")`, drop empty segments, then join with `/`.

### WARN-6: promote-ui-rule Step 4 can read the plugin's template rules file instead of the project copy that Step 3 just wrote. `skills/promote-ui-rule/SKILL.md:71-78`

The block prefers `$CLAUDE_PLUGIN_ROOT/.claude/hooks/architecture-guard.py`. That guard finds its rules through `hook_file`. When `CLAUDE_PROJECT_DIR` is not set, the plugin's template beside the hook comes first (`_project_paths.py:130-140`), and the plugin ships `architecture-guard.rules.json` there. `_project_paths.py:40` notes that `CLAUDE_PROJECT_DIR` is unset in a plain shell. In that case the new rule is not seen, the guard exits 0, and the skill reverts a correct rule as its Step 4 failure handling tells it to. The project fallback `.claude/hooks/architecture-guard.py` also depends on the working folder.

Fix: run it as `CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}" py -3 "$GUARD" <<'EOF'`, and test `"${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/architecture-guard.py"`. Both forms still satisfy `test_step_four_runs_the_guard_through_a_lookup_block` (its regex (d) allows a prefix before `py -3`).
- Correct as written: lookup order (plugin root, then project), no `$HOME`, a halt message naming both paths, `exit 1`, and the quoted heredoc (no `$` or backtick expansion inside the snippet, so it is safer than the old `echo '...'`).

### WARN-7: TAILWINDCSS_RULES.md:29 describes a looser rule than the guard enforces (journal 2026-10-04: check a documented guard behaviour against the code)

"or a `.html` file beside a `.ts` file that carries `@Component(`" suggests that any decorated `.ts` in the folder is enough. The guard requires the `.ts` with the same name (`sibling_has_decorator`, `:1149`). `:54` relies on the same definition of a template. Reword it: "or a `<name>.html` whose `<name>.ts` carries `@Component(`". `ANGULAR_CODE_RULES.md:37` matches the code.

---

## NIT

- **N1. Docstring line 26** (`architecture-guard.py:26`): the stated `hook_file` order leaves out the working-folder rank. The real order is: the project copy, then the template beside the hook, then `<cwd>/.claude/hooks`, then `~/.claude/hooks` (`_project_paths.py:62-82,130-136`). The same order applies to the rules file, which the sentence does not mention.
- **N2. Docstring known limit for G-2** (`:44-46`): it leaves out the `.spec.ts` / `.d.ts` exclusion and the fallback to the written text when no view can be built (G-2, third bullet).
- **N3.** `classify_sibling_component:939` searches for the literal `"@Component("`, while G-2 recognises `@Component (`. For a sibling spelled with a space, recognition succeeds but the selector scope comes out empty. This predates t2, but suffix-less recognition now makes it reachable.
- **N4.** A sibling `.ts` that is not UTF-8 (for example UTF-16 from a PowerShell 5 `>` redirect) makes any `.html`, `.scss` or `.css` with the same name count as recognised in any project (probe: exit 2). This is consistent with V-2's rule ("counts as recognised"), but a decode failure is an expected outcome, not a fault. Decide on purpose: either keep it and log the failure once, or treat a file that cannot be decoded as "no evidence".
- **N5.** The suffix tests are case-sensitive (`foo.HTML` is not scanned, probe exit 0), as before t2. Fine; noted only.
- **N6. G-3 fallback.** `HOOK_DIR` is used only when importing `_project_paths` fails. For a guard installed in the home hooks folder, `HOOK_DIR` is that same folder, so nothing changes. For a plugin-run guard with a broken `_project_paths`, the guard now reads the plugin template instead of `~/.claude/hooks`. Home-only exceptions are then lost (the guard becomes stricter), and so are home-only external rules (it becomes looser). This is a broken-install corner, so it is acceptable.

---

## Checks that came out clean

- **(1) Code against the contract.** G-1 matches root segments exactly, case-folded, for one or more segments (`:242-269`). G-2 follows the template, stylesheet and code definitions, with the post-edit view falling back to the written text (`:1167-1195`). `classify_sibling_component` cuts off the real suffix and reads `<stem>.component.ts` before `<stem>.ts` (`:929-932`). G-3 has no `Path.home`, no `HOME` and no `expanduser` in the code; the only `~/.claude` is the docstring sentence that names `hook_file`. No divergence.
- **(2) Fail closed.** Every new G-2 call sits behind `counts_as_found` or `post_edit_text`. `scan_whole_file_rules` stays inside its `try` (`:1360`). The only path that can still reach the outer catch is the pre-existing walk I/O (WARN-4).
- **(3) G-1 edge values.** A trailing slash and upper case work (probe). Traversal is impossible: `project_root` is always an ancestor of the edited file's resolved path. `..` never matches a resolved part. A root equal to an app folder behaves the same way as `detect_app`. Empty or blank values fall back to `projects`.
- **(4) G-2 cases.** `@Component ({` is recognised. `.css` and `.scss` stems are correct. `.spec.ts` and `.d.ts` are never recognised (probe: spec exit 0). A non-Angular `app.html` beside an `app.ts` with no decorator gives exit 0 (probe).
- **(8) Rule V.** No `plugin.json` or marketplace file in the diff.
- **Data-first.** The contract is approved. `Files to touch` matches the diff exactly. No new mechanism, no new vocabulary, no integration surface. Registry janitor: nothing to append.

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 0 |
| WARN | 7 |
| NIT | 6 |

**Top priority fix:** WARN-1 and WARN-2 need the user's decision on G-2's scope (test and story suffixes, and the Angular-specific evidence). After that, WARN-3 (build the view only when it is needed, once per file per call) and WARN-4 (wrap the walk).
