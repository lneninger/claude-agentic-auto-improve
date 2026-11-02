# t8 review cloud capability — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t8-review-cloud-capability (issue #173, parent #161)
- **Contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md` (approved, Revision 5)
- **Reviewed on:** 2026-11-02
- **Commit range reviewed:** `19c89c5..effa0b8` (parent branch `feature/memory-client-and-cloud-engineering`. The range starts at the merge of t2, #179, and ends at the merge of t7, #184. `effa0b8` equals `origin/feature/memory-client-and-cloud-engineering`.)
- **Sub-task merges in the range (first parent):** t6 `e9c0dbf` (#181, commit `506128f`), t7 `effa0b8` (#184, commits `64a1a38`, `60601e0`)

**Verdict:** blocked

## What was checked

- **Capability off while `cloud.providers` is unset.** Met in the text. `skills/cloud-engineering/SKILL.md:26-28` reads a placeholder or `none` as unset and stops with one fixed line. `agents/cloud-engineer.md:22` gives the same line as refusal 2. `agents/security-auditor.md:101` skips the infrastructure section. `skills/debug/SKILL.md:200` says the route is active only when the slot is set. `DEFAULT_IMPLEMENTERS` names `cloud-engineer` unconditionally (`pr_merged.py:56`). That list only classifies contract blocks, so it does not switch anything on. The profile seed keeps all four `cloud.*` slots as placeholders (`.claude/project-profile.md:42-45`), so this repository stays off.
- **Only selected references load.** Partly met. On the skill path it is met: `SKILL.md:32-48` always opens `cross-cutting.md`, then one file per profile value, and opens no reference for a provider the profile does not name. `cross-cutting.md:4` repeats "Open only the provider files the profile names." On the agent path it is not met: the agent cannot load the skill at all. See B1.
- **The cloud scope rule is stated in both the skill and the agent.** Met. `SKILL.md:9-15` and `cloud-engineer.md:11-17` each say: design, review, validation and troubleshooting; validation is non-mutating only; it never runs a deploy, apply, create, update or destroy command against a live environment; the command is written out for the user to run; prompts and guards apply unchanged; no settings file. Both have a matching "Live changes" hand-off (`SKILL.md:57-63`, `cloud-engineer.md:40-46`).
- **No shipped cloud text instructs a mutating command (`test_cloud_text_scans.py`, control fails when planted).** Met for the shipped text, with gaps in the scanner. The suite runs 11 tests, all OK. Every mutating command in the nine skill files and the agent sits in a labelled block. The four in-file controls pass. I planted a line into the real `aws.md` text and into the agent text, and the scanner reported each one. Two classes of bypass exist, though: W1 (the label phrase exempts its own line) and W2 (unlisted verbs and tools). A grep shows the shipped text holds no command of either class today.
- **No settings file, permission row, hook or finish-install change (Decision note, Revision 5).** Met. `git diff --name-only 19c89c5..effa0b8` lists 17 files. None is a settings file, a hook, `auto_improve_finish_install.py` or `skills/auto-improve-finish-install/`. Across the whole parent branch (`6d1ca0c..effa0b8`), the only hook change is `journal-post-approval-tracker.py`, in t2 (`469f51f`). That change belongs to the memory adapter, not the cloud capability. A `git grep` for `permissions.ask`, `cloud-permissions` and `settings.json` under the skill and the agent finds nothing.
- **Database guards untouched.** Met. `.claude/hooks/db-destructive-guard.py` and `db-research-readonly-guard.py` do not appear in `git diff --name-only 6d1ca0c..effa0b8`.
- **Appendix A.6 Cloud coverage table is now true.** Met, row by row, with one wording gap (N3):
  - Azure, AWS and GCP references exist and are selected per profile.
  - Terraform has `validate` and `plan` steps. Bicep has `bicep build` and `what-if` steps, plus `lint` and `validate`.
  - Docker has a reference, and `/debug` routes to `cloud-engineer`.
  - Kubernetes has schema validation (`kubeconform`). Its server-side dry-run exists only implicitly, through `kubectl diff` (N3).
  - The cross-cutting file covers all ten topics (the test checks the headings). The auditor checklist covers networking, identity, secrets, storage, logging and pinning.
  - The runner steps are non-mutating, and each provider and tool file has them.
  - The troubleshooting order is in `cross-cutting.md:90-100`.
  - Deploy is a hand-off, and no new mechanism exists.
  - The cloud-management MCP is a slot only; both the skill and the agent say they do not call it.
- **Block constraints.** Met. The "for the user to run" block rule holds. Provider choice comes only from the profile (`SKILL.md:30`). The subagent_type literal rule holds (`test_plugin_text_scans.py`, 13 OK). Only the docker-master-goat line changed in `/debug`; the diff is one line. `cloud-engineer` was added to `DEFAULT_IMPLEMENTERS`, with a test.
- **Data-first audit, off-list files.** Met. t6 touched exactly its ten listed files. t7 touched its six listed files plus its own brief. Nothing touched an area outside the contract.
- **Non-mutating claims of the validation steps.** Met. I read every JSON step in the seven provider and tool files. Each is a format, lint, schema, policy-scan, validate, plan, what-if, diff, describe, list or show command. `terraform plan` has no `-out` and uses `-lock=false`. `docker build --check` runs the build checks only and builds nothing.
- **Version (Rule V).** Met. `check_version_bump.py` in parent mode keeps 0.12.4.

## Findings

### B1 (blocking) — The cloud-engineer agent cannot load its own skill. `agents/cloud-engineer.md:4`, `:29`; `.claude/scripts/tests/test_agent_skill_preloads.py` (`test_cloud_engineer_ships_with_its_tools_and_scope_rule`)

The agent body says: "Invoke the `cloud-engineering` skill (`agentic-auto-improve:cloud-engineering`) with the Skill tool, and follow it exactly." Its tool line is `Read, Edit, Write, Grep, Glob, Bash, mcp__codegraph__*`. That line does not include `Skill`, and the agent has no `skills:` preload either. A subagent can call only the tools on its line. So the agent can neither load `SKILL.md` nor learn which reference to open. It works from general knowledge instead. That means "only selected references load" fails on the agent path. The provider service maps, the ready verification steps and the hand-off wording never reach it. The two other shipped agents that say "with the Skill tool" list `Skill` on their tool lines: `senior-test-engineer.md:4` and `ui-ux-designer.md:5`. The cause is upstream. The contract's block 7 TASK spells out the tool line without `Skill`, and the new test pins that exact string, so the defect is locked in.

Fix:
- Change `agents/cloud-engineer.md:4` to `tools: Read, Edit, Write, Grep, Glob, Bash, Skill, mcp__codegraph__*`.
- Update the expected string in `test_cloud_engineer_ships_with_its_tools_and_scope_rule` to match.
- Add a line after `:29` in the same style as `senior-test-engineer.md:15`: "If the skill cannot be loaded, stop and say so; do not continue from memory."
- Record the divergence from the block 7 TASK in the fix pull request, and add the journal entry under Disposition.

### W1 (warning) — The scanner skips any line that contains the label phrase, and treats any such line as a label. `.claude/scripts/tests/test_cloud_text_scans.py:68-70`

`mutating_violations` hits `continue` on every line where `LABEL_RE` matches, before the verb check runs. A sentence like "Run `terraform destroy` now, not for the user to run later." returns `[]`. Any line that contains the phrase also makes the next fence exempt. A bullet `- for the user to run` followed by a fenced `terraform destroy` returns `[]`. The shipped text does not exploit either path today. The scan is still weaker than its docstring, which says a block must be "introduced by a label line".

Fix: treat a line as a label only when the whole line is the label, for example `^\s*\**\s*for the user to run\s*:?\s*\**\s*$` with `re.I`. Run the verb check on every other line. Add both strings above as negative controls.

### W2 (warning) — The verb and tool lists miss common live-changing commands. `.claude/scripts/tests/test_cloud_text_scans.py:35-41`

All of these return `[]`:
- `aws s3 rm … --recursive`
- `terraform state rm …`
- `kubectl scale … --replicas=0`
- `kubectl rollout restart …`
- `az vm deallocate …` / `az keyvault purge …`
- `pulumi destroy`
- `cdk deploy`
- `Terraform apply` (`TOOL_RE` is case-sensitive)

The verb list matches the contract's block 6 constraint word for word, so this is a limit of the contract, not a departure from it. The scope rule is about live changes, though, and the scan is its only automated check (Revision 5). A grep of the shipped text found no such command today.

Fix: either widen the lists, or record the limit. To widen them:
- add the tools `pulumi`, `cdk`, `sam`, `oc`, `podman`, `azcopy`, `bq` and `firebase`;
- add the verbs `rm`, `remove`, `purge`, `scale`, `restart`, `deallocate`, `stop`, `import`, `taint`, `rollback`, `patch`, `replace`, `drain` and `cordon`;
- make `TOOL_RE` case-insensitive.

To record the limit instead, block 9's Known limitations states that the scan matches only the listed verbs.

### W3 (warning) — The `/debug` route hands work to an agent that refuses the `/debug` hand-off. `skills/debug/SKILL.md:187-200`; `agents/cloud-engineer.md:21`

The `/debug` fix hand-off passes `PRIOR_FINDINGS` with `debug_notes_path`, `root_cause` and `verification_type`, and no `contract_path`. Refusal 1 in `cloud-engineer` returns "No concept contract provided…" whenever `contract_path` with `contract_status: approved` is missing. So every container or infrastructure bug that `/debug` routes there is refused, and the A.6 row "routed to `cloud-engineer`" never produces a fix. Other implementers inherit the same tension from the workstation doctrine. `cloud-engineer` is the first shipped agent to write the refusal literally, with no exception. `ui-ux-designer` has a `TRIVIAL` escape (`ui-ux-designer.md:45`).

Fix (choose one):
- (a) Let `/debug` say that cloud fixes need a contract and route through `/design-first`.
- (b) Accept a `/debug` hand-off with `debug_notes_path` and `root_cause` for a minimal fix, stated as a third accepted form in refusal 1.

### N1 (nit) — Contract Appendix A.5 still says the permission rows close the cloud-database-delete gap. Contract line 1172

The A.5 line reads "The permissions rows close that gap without touching the guards." Revision 5 removed those rows. The gap is open: the database guards match no `az sql db delete` or `aws rds delete-db-instance`. Only the text rule and the user's prompts cover it. Block 9's Known limitations should name this gap, and the contract line should carry a "removed in Revision 5" note.

### N2 (nit) — The `k8s-diff` step fails by design before every release. `skills/cloud-engineering/references/kubernetes.md:58-67`

At a landing, the manifests are new and not yet applied, so `kubectl diff` exits 1 every time. The note after the block tells the agent to ask the user first. Even so, listing it among the "ready" steps invites a gate that always fails. Moving it to the troubleshooting list, or marking it "optional, drift check only", would be clearer.

### N3 (nit) — A.6 promises a Kubernetes server-side dry-run that the reference never names. `kubernetes.md:30`

`kubectl diff` performs a server-side dry-run, so the substance is there, but the words are not. One sentence would fix it: "`kubectl diff` runs a server-side dry-run of each object."

### N4 (nit) — The auditor's infrastructure section does not say what to do when `cloud.roots` is unset. `agents/security-auditor.md:101`

When `cloud.providers` is set but `cloud.roots` is unset, "Review the files under `cloud.roots`" has no target. Add: "When `cloud.roots` is unset, say so and review the files the caller names."

## What was NOT checked

- Live runs of any provider command. No cloud account or cluster was used. The non-mutating claims were checked by reading each command against its documented behaviour.
- Whether Claude Code really refuses the Skill tool to `cloud-engineer` at run time (B1). This was inferred from the tool line, from the platform rule that a subagent gets only the tools on its line, and from two shipped agents that add `Skill` for the same instruction. No subagent was launched.
- Manifest description counts. `.claude-plugin/plugin.json:6` says 28 skills and 14 agents. The tree has 33 `skills/*/SKILL.md` files and 15 agents. Open Question 15 gives this correction to the landing, so it is not a finding here.
- Blocks 1 to 5 and the memory adapter, including the t2 hook change. Those have their own gate (t5).
- The reviewer-verdict JSONL log and the JOURNAL.md append. This gate may write only its two artefact files, so both are proposed under Disposition and were not written.
- The full test tree. Only the suites of the touched files and the plugin text scans were run (see Evidence).

## Evidence

Every command ran from the t8 worktree root on 2026-11-02.

| Command | Exit | Result |
|---|---|---|
| `git log --first-parent --format="%h %p %s" -5 HEAD` | 0 | `effa0b8` (t7 #184), `e9c0dbf` (t6 #181), `19c89c5` (t2 #179) |
| `git rev-parse --short origin/feature/memory-client-and-cloud-engineering` | 0 | `effa0b8` (= HEAD) |
| `git diff --stat 19c89c5..effa0b8` | 0 | 17 files, +1193 / -4; only the block 6 and block 7 lists plus the t7 brief |
| `git diff --name-only 6d1ca0c..effa0b8 -- .claude/hooks .claude/settings.json .claude/settings.local.json hooks .claude/scripts/auto_improve_finish_install.py skills/auto-improve-finish-install` | 0 | only `.claude/hooks/journal-post-approval-tracker.py` (t2, `469f51f`) |
| `git grep -n -i -E "permissions\.ask\|cloud-permissions\|settings\.json" -- skills/cloud-engineering agents/cloud-engineer.md` | 1 | no match |
| `py -3 .claude/scripts/tests/test_cloud_text_scans.py` | 0 | Ran 11, OK |
| `py -3 .claude/scripts/tests/test_agent_skill_preloads.py` | 0 | Ran 7, OK |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | Ran 13, OK |
| `py -3 .claude/scripts/tests/test_pr_merged.py TestPortability -v` | 0 | Ran 8, OK (includes `test_the_default_includes_the_cloud_engineer_and_it_ships`) |
| `py -3 .claude/scripts/tests/test_pr_merged.py` (full) | 0 | Ran 652 in 398.7s, OK |
| `py -3 .claude/scripts/check_version_bump.py --base origin/feature/memory-client-and-cloud-engineering --default-branch master --head-ref task/2026-11-01-memory-client-and-cloud-engineering/t8-review-cloud-capability` | 0 | "sub-task pull request keeps version 0.12.4; the landing raises it" |
| `py -3 -c "…mutating_violations(aws.md text + planted delete-stack line); (agent text + planted kubectl apply line)"` | 0 | clean file `[]`; each planted line reported (positive control on real text) |
| `py -3 -c "…mutating_violations('Run terraform destroy now, not for the user to run later.')"` | 0 | `[]` (W1) |
| `py -3 -c "…17 probe strings…"` | 0 | MISSED: capitalised `Terraform apply`, `aws s3 rm`, `terraform state rm`, `kubectl scale`, `kubectl rollout restart`, `pulumi destroy`, `cdk deploy`, `az vm deallocate`/`az keyvault purge`, bullet label before fence. CAUGHT: `kubectl delete`, `gcloud … delete`, tilde-fence mismatch, indented block, JSON-array `terraform destroy`, `helm uninstall`, `kubectl apply --dry-run=server` |
| Grep `` `(terraform\|…\|bicep)…(rm\|scale\|restart\|purge\|…)…` `` over `skills/cloud-engineering/**` and `agents/cloud-engineer.md` | 0 | 2 hits, both read-only (`aws ce get-cost-and-usage … Start=`, `docker history`) |
| Grep `^tools:\|^skills:\|Skill tool` over `agents/` | 0 | `senior-test-engineer.md:4` and `ui-ux-designer.md:5` list `Skill`; `cloud-engineer.md:4` does not, yet `:29` says "with the Skill tool" (B1) |

Files read in full: `skills/cloud-engineering/SKILL.md` and all eight references, `agents/cloud-engineer.md`, `test_cloud_text_scans.py`. Also read: the block 7 diffs of `security-auditor.md`, `debug/SKILL.md`, `pr_merged.py`, `test_pr_merged.py` and `test_agent_skill_preloads.py`; `debug/SKILL.md:170-204`; contract Business Concept, blocks 6 to 11, A.5 and A.6; and the t10 review of 2026-10-30 for the artefact shape.

## Disposition

The contract cannot move past this gate until B1 is fixed. B1 is a one-token change, plus its test and a note recording the divergence. The rest is optional or belongs to block 9.

1. **B1:** add `Skill` to `agents/cloud-engineer.md:4`, update the pinned string in `test_agent_skill_preloads.py`, add the "if the skill cannot be loaded, stop" line, and re-run `test_agent_skill_preloads.py`, `test_cloud_text_scans.py` and `test_plugin_text_scans.py`. Append this JOURNAL.md entry under the project section, with a change that already raises the version (this gate may not write it):

   ```markdown
   ### 2026-11-02 — An agent told to invoke a skill must list the Skill tool
   - **Trigger:** post-impl divergence
   - **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
   - **Lesson:** When a contract spells out an agent's tool line and the agent body says "invoke … with the Skill tool", include `Skill` in that line (or preload with `skills:`); block 7 omitted it and the test pinned the omission.
   - **Apply when:** a handoff block fixes a `tools:` line for a new agent that loads a plugin skill.
   - **Tags:** agent-tools, skill-tool, subagent, preload, contract-defect
   ```

2. **W1, W2:** tighten the label match and widen the verb and tool lists in `test_cloud_text_scans.py`, with the probe strings above as controls. If they are not widened, block 9's Known limitations states the scan's verb list.
3. **W3:** pick option (a) or (b), in the B1 fix or a follow-up stub.
4. **N1:** block 9 names the open cloud-database-delete gap under Known limitations. **N2 to N4:** one sentence each.
5. Append the reviewer-verdict line to `~/.claude/logs/reviewer-verdicts.jsonl` (outside this gate's write scope): `{"ts":"2026-11-02T00:00:00Z","contract_path":"D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md","divergence":true,"drift_summary":"block 7 tool line omits Skill, so cloud-engineer cannot load its skill; contract-induced","critical_count":1,"warn_count":3}`.

This gate does not release its dependents until B1 is fixed and re-checked.
