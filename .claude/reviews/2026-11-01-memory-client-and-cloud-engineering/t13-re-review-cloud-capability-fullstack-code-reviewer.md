# t13 re-review cloud capability — fullstack-code-reviewer

**Verdict:** pass-with-findings

## Scope and range

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t13-re-review-cloud-capability (issue #192, parent #161)
- **Contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md` (approved, Revision 6)
- **Reviewed on:** 2026-11-02
- **Commit range reviewed:** `19c89c5..65fed3b` on the parent branch `feature/memory-client-and-cloud-engineering`. `19c89c5` is the merge of t2 (#179), the last commit before block 6. `65fed3b` is the merge of t12 (#194) and equals `origin/feature/memory-client-and-cloud-engineering`.
- **Blocks covered:** block 6 (`506128f`, merged in `e9c0dbf`, #181), block 7 (`64a1a38`, merged in `effa0b8`, #184), block 12 (`fa0cab1`, merged in `65fed3b`, #194).
- **Supersedes:** `t8-review-cloud-capability-fullstack-code-reviewer.md` (verdict `blocked`).
- **Method:** cold context. The findings below were formed before the block 8 review was opened. It was read afterwards only to confirm that its B1 and W3 are cleared (see the end of "What was checked").

## What was checked

- **Capability off while `cloud.providers` is unset.** Met. `skills/cloud-engineering/SKILL.md:26-28` treats a placeholder or `none` as unset and stops with one fixed line. `agents/cloud-engineer.md:22` (refusal 2) prints the same line. `agents/security-auditor.md:101` skips its infrastructure section when the slot is unset (see I3 for a wording gap). `skills/debug/SKILL.md:200` marks the route as active only when the slot is set, and the agent refuses otherwise. `DEFAULT_IMPLEMENTERS` (`pr_merged.py:56`) only classifies contract blocks and switches nothing on. The profile seed ships all four `cloud.*` slots as placeholders (`.claude/project-profile.md:42-45`), and line 47 says a placeholder or `none` means off.
- **Only selected references load, on the skill path.** Met. `SKILL.md:32-48` always opens `cross-cutting.md`, then one file per profile value, and opens no reference for a provider the profile does not name (line 48). `cross-cutting.md:4` repeats the rule.
- **Only selected references load, on the agent path.** Met. `agents/cloud-engineer.md:4` now reads `tools: Read, Edit, Write, Grep, Glob, Bash, Skill, mcp__codegraph__*`, which matches the block 12 TASK character for character. Line 29 invokes the skill with the Skill tool, and adds "If the skill cannot be loaded, stop and say so. Do not continue from memory." The agent therefore reaches the reference selection of `SKILL.md` and does not work from general knowledge.
- **Cloud scope rule stated in both the skill and the agent.** Met. `SKILL.md:9-15` and `cloud-engineer.md:11-17` each state: design, review, validation and troubleshooting; non-mutating validation only; never a deploy, apply, create, update or destroy against a live environment; the command is written out for the user to run; prompts and guards apply unchanged; no settings file. Both have a matching hand-off section (`SKILL.md:57-63`, `cloud-engineer.md:40-46`).
- **No shipped cloud text instructs a mutating command.** Met. `test_cloud_text_scans.py` runs 11 tests, all OK, including four in-file controls. I planted `Run terraform apply -auto-approve now` (built from parts) into the real text of each of the ten scanned files in memory. Each clean file returned 0 violations and each planted copy returned 1. Every live-change block (`terraform.md:88-93`, `kubernetes.md:87-92`, `azure.md:107-111`, `aws.md:109-113`, `gcp.md:109-113`, `bicep.md:77-81`, `docker.md:82-86`) has the label line directly above its fence. A manual grep for verbs outside the scanner's list (`rm`, `patch`, `scale`, `restart`, `purge`, `import`, `drain` and others) found only prose and read-only commands. The scanner limits recorded in the block 8 review are out of scope by Revision 6 (I1).
- **Every validation step is non-mutating.** Met. I read every JSON step in the seven provider and tool files. Each one is a format, lint, schema, policy scan, validate, plan (`-lock=false`, no `-out`), what-if, diff, describe, list or show command. `docker build --check` runs the checks without building. Two steps have quality problems that do not touch the non-mutating property (W1, W2).
- **No settings file, permission row, hook or finish-install change.** Met. `git diff --name-only 19c89c5..65fed3b` lists 18 non-brief files: the block 6 and block 7 lists, the block 12 list (a subset of block 7's) and the t8 review artefacts. None is a settings file, a hook, `auto_improve_finish_install.py` or `skills/auto-improve-finish-install/`. The last commit that touched `.claude/hooks/` is `469f51f` (t2), which is an ancestor of `19c89c5`.
- **Database guards untouched.** Met. Neither `db-destructive-guard.py` nor `db-research-readonly-guard.py` appears in the range.
- **Appendix A.6 Cloud coverage table is true.** Met, row by row:
  - Azure, AWS and GCP references exist and are selected per profile.
  - Terraform has `validate` and `plan` steps. Bicep has `bicep build` and `what-if` steps, plus `lint` and `validate`.
  - Docker has a reference, and `/debug` routes container work to `cloud-engineer`.
  - Kubernetes has schema validation (`kubeconform`). Its server-side dry-run is present in substance through `kubectl diff`, but the reference never names it (I6).
  - `cross-cutting.md` covers all ten topics, and the auditor checklist covers networking, identity, secrets, storage, containers, Kubernetes, logging, pinning and deletion protection.
  - The deployment validation steps are ready runner entries and are non-mutating.
  - The troubleshooting order is at `cross-cutting.md:90-102`.
  - Deploy and destructive operations are a hand-off, with no new mechanism.
  - The cloud-management MCP is a slot only. The skill (`:69`) and the agent (`:53`) both say they do not call it.
- **Block constraints.** Met.
  - Block 6: provider choice comes from the profile only (`SKILL.md:30`). No project is named.
  - Block 7: `cloud-engineer` is in `DEFAULT_IMPLEMENTERS`, with a test. The subagent_type literal rule holds (`test_plugin_text_scans.py`, 13 OK).
  - Block 12: only the listed three files changed (`fa0cab1`). `/debug` changed in one line only. The new test `test_every_agent_that_invokes_a_skill_can_load_it` covers every file under `agents/`. The pinned tool line was updated.
  - No block raised the version: `check_version_bump.py` in parent mode keeps 0.12.4.
- **Data-first audit, off-area drift.** Met. Every changed shipped file is in its block's `Files to touch`. No area outside the contract was touched. No UI surface is involved, so the End-User View audit does not apply.
- **Block 8 findings B1 and W3, confirmed after my own findings were written.**
  - **B1 is cleared.** The tool line includes `Skill`, the stop-if-unloadable line is present, the pinned test string matches, and the new all-agents test passes.
  - **W3 is cleared.** It took option (a). `skills/debug/SKILL.md:200` passes `contract_path` with `contract_status: approved` when a contract exists. When none exists, it says a contract is required first and points to `/design-first` instead of invoking the agent.
  - Block 8 findings W1, W2 and N1 to N4 are still open. Revision 6 put W1 and W2 out of scope. N1 to N4 are carried below as I1, I5, I6 and I3.

## Findings

### W1 (warning) — The Terraform plan step fails after the documented init when the module declares a backend. `skills/cloud-engineering/references/terraform.md:44-66`, `:70`

The steps run `terraform init -backend=false`, then `validate`, then `plan`. With `-backend=false`, Terraform skips backend initialisation. When the root module has a `backend` block, as almost every shared Terraform project does, the next `terraform plan` stops with "Backend initialization required, please run terraform init" and a non-zero exit. A project that copies the five steps in order gets a landing that fails every time. Line 70 says the plan "needs a configured backend and read access", but no step initialises the backend.

Fix: add a backend init step between `terraform-policy-scan` and `terraform-plan`:

```json
{
  "id": "terraform-init-backend",
  "command": ["terraform", "-chdir=<root-module>", "init", "-input=false", "-lock=false", "-no-color"],
  "results": { "format": "exit-code" },
  "timeout_minutes": 10
}
```

Reword line 70 to say that the backend init and the plan need credentials and read access to the state, and the earlier steps do not.

### W2 (warning) — Several "validation steps" pass whatever they find. `azure.md:85-89`, `aws.md:78-89`, `gcp.md:72-89`

`cross-cutting.md:84` says "A step passes on exit code zero". The following steps exit 0 whenever the call succeeds, including when they report non-compliance:
- `az policy state summarize`
- `aws configservice describe-compliance-by-config-rule --compliance-types NON_COMPLIANT`
- `aws accessanalyzer list-findings-v2`
- `gcloud projects get-iam-policy`
- `gcloud compute firewall-rules list`
- `gcloud resource-manager org-policies list`

A project that adds `aws-config-compliance` as a landing gate expects it to block on non-compliant rules, but it never does. The identity checks (`az account show`, `aws sts get-caller-identity`, `gcloud config list`) are fine as credential checks. The GCP file has no step that can fail on an infrastructure defect at all; it relies on the Terraform plan.

Fix: in each provider file, split the list into "Gate steps" (they fail on a defect) and "Report steps (always exit 0; read the output)". Alternatively, remove the report steps from the JSON and list them under Troubleshooting. Change `cross-cutting.md:84` to say that only gate steps belong in `contractLanding.verification.steps`.

### I1 (info) — Scanner limits from the block 8 review remain, out of scope by Revision 6. `.claude/scripts/tests/test_cloud_text_scans.py:35-41`, `:68-70`

My own probes reached the same two classes before I read block 8.
- Any line containing the label phrase arms the exemption for the next fence. `cross-cutting.md:86` and `SKILL.md:13` are prose lines of that kind.
- The verb list is the contract's ten verbs. Commands such as `rm`, `scale`, `restart` and `purge` are not matched.

The shipped text contains no command of either class today (manual grep). Block 9's Known limitations should state the verb list, as block 8 proposed.

### I2 (info) — "The plan writes nothing" is true for live resources but not for side effects. `terraform.md:33`

`terraform init` downloads provider executables. `terraform plan` runs them, and it runs any `external` data source program and fetches `http` data sources. The agent runs plan through Bash with the user's credentials. One sentence would close this: "Before running a plan on code you did not write, check `data "external"` and `data "http"` blocks."

### I3 (info) — The auditor's off condition and empty-roots case are underspecified. `agents/security-auditor.md:101`

The skill and the agent say that a placeholder or `none` counts as unset. The auditor says only "unset". The placeholder text itself lists `azure`, `aws` and `gcp`. Add "(a placeholder or `none` counts as unset)". Block 8 N4 is also still open: when `cloud.roots` is unset, the section has no target.

### I4 (info) — The new all-agents Skill test keys on one literal phrase. `.claude/scripts/tests/test_agent_skill_preloads.py` (`test_every_agent_that_invokes_a_skill_can_load_it`)

The test checks only bodies containing "with the Skill tool". An agent that writes "use the Skill tool to load …" escapes it. A grep of `agents/` finds no other phrasing today. Matching `\bSkill tool\b` would be sturdier.

### I5 (info) — Contract Appendix A.5 still says permission rows close the cloud database delete gap. Contract line 1237

Revision 5 removed those rows. The database guards do not match `az sql db delete` or `aws rds delete-db-instance`. Only the text rule and the user's prompts cover them. This is the same as block 8 N1, and it belongs in block 9's Known limitations.

### I6 (info) — Kubernetes wording. `kubernetes.md:30`, `:58-67`

Block 8 N2 and N3 are still open:
- The reference never says that `kubectl diff` performs the server-side dry-run that A.6 promises.
- The `k8s-diff` step exits 1 whenever a release is pending, so it suits a drift check better than a landing gate.

## What was NOT checked

- Live runs of any provider command. No cloud account or cluster was used. I checked the non-mutating claims and W1 and W2 by reading each command against its documented behaviour.
- A run-time launch of `cloud-engineer` to prove the Skill tool now binds. That was inferred from the tool line and from the two shipped agents that use the same pattern.
- The full test tree. Only the suites of the touched files and the plugin text scans were run (see Evidence).
- Blocks 1 to 5 and the memory adapter, which have their own gate.
- Manifest description counts, which Open Question 15 gives to the landing.
- The reviewer-verdict JSONL log and the JOURNAL.md append. This gate may write only its two artefact files, so both are proposed under Disposition.

## Evidence

Every command ran from the t13 worktree root on 2026-11-02.

| Command | Exit | Result |
|---|---|---|
| `git rev-parse --short HEAD` / `origin/feature/memory-client-and-cloud-engineering` | 0 | both `65fed3b` |
| `git diff --stat 19c89c5..65fed3b` (excluding briefs and contract) | 0 | 18 files, +1372 / -1: block 6, 7 and 12 lists plus the t8 review artefacts |
| `git show --stat fa0cab1` | 0 | block 12: `test_agent_skill_preloads.py`, `agents/cloud-engineer.md`, `skills/debug/SKILL.md` only |
| `git diff --name-only 19c89c5..65fed3b \| grep -iE "hook\|settings\|finish\|guard\|db-"` | 1 | no match |
| `git merge-base --is-ancestor 469f51f 19c89c5` | 0 | the last hook change predates the range |
| `py -3 .claude/scripts/tests/test_cloud_text_scans.py` | 0 | Ran 11, OK |
| `py -3 .claude/scripts/tests/test_agent_skill_preloads.py` | 0 | Ran 9, OK |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | Ran 13, OK |
| `py -3 .claude/scripts/tests/test_pr_merged.py TestPortability` | 0 | Ran 8, OK |
| `py -3 .claude/scripts/tests/test_pr_merged.py` (full) | 0 | Ran 652 in 484.6s, OK |
| `py -3 -c "…mutating_violations(file text) vs (file text + planted terraform apply line)…"` over the 10 scanned files | 0 | each file: 0 clean, 1 planted |
| Grep `\b(rm\|patch\|scale\|restart\|rollout\|set\|put\|import\|taint\|up\|run\|publish\|start\|stop\|drain\|purge\|…)\b` over `skills/cloud-engineering/` | 0 | prose and read-only commands only; `docker push` and `gcloud run deploy` sit inside labelled blocks |
| `grep -rn "with the Skill tool" agents/` | 0 | `cloud-engineer.md:29`, `senior-test-engineer.md:15`, `ui-ux-designer.md:32`; no other phrasing |
| `py -3 .claude/scripts/check_version_bump.py --base origin/feature/memory-client-and-cloud-engineering --default-branch master --head-ref task/2026-11-01-memory-client-and-cloud-engineering/t13-re-review-cloud-capability` | 0 | "sub-task pull request keeps version 0.12.4; the landing raises it" |

Files read in full: `skills/cloud-engineering/SKILL.md`, `cross-cutting.md`, `terraform.md`, `kubernetes.md`, `docker.md`, `bicep.md`, `agents/cloud-engineer.md` and `test_cloud_text_scans.py`. The validation, troubleshooting and live-change sections of `azure.md`, `aws.md` and `gcp.md` were also read. So were the range diffs of `security-auditor.md`, `debug/SKILL.md`, `pr_merged.py`, `test_pr_merged.py` and `test_agent_skill_preloads.py`, plus `debug/SKILL.md:172-201`. From the contract: Reused Mechanisms, New Mechanisms, Extension Points, blocks 6 to 13, Revision 6, A.5 and A.6. From the work item: the t13 brief.

## Disposition

No blocking finding. The gate releases its dependents (block 9).

1. **W1, W2:** fix in a follow-up, or fold them into block 9 if the contract owner prefers. Each is a few lines in the reference files and needs no new mechanism.
2. **I1, I3, I5:** block 9's Known limitations names the scanner's verb list and the open cloud database delete gap. The auditor wording in I3 can ride with W1 and W2.
3. **I2, I4, I6:** one sentence or one regex each, optional.
4. **Journal entry for block 8 B1** (proposed there, not yet in `JOURNAL.md`): append it with block 9, which already touches the registries and is batched before the landing raise:

   ```markdown
   ### 2026-11-02 — An agent told to invoke a skill must list the Skill tool
   - **Trigger:** post-impl divergence
   - **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
   - **Lesson:** When a contract spells out an agent's tool line and the agent body says "invoke … with the Skill tool", include `Skill` in that line (or preload with `skills:`); block 7 omitted it and the test pinned the omission.
   - **Apply when:** a handoff block fixes a `tools:` line for a new agent that loads a plugin skill.
   - **Tags:** agent-tools, skill-tool, subagent, preload, contract-defect
   ```

5. **Registries:** the cloud blocks add no new mechanism (the contract says the skill and agent are assets) and no vocabulary beyond the Business Concept list that block 9 appends.
6. Append the reviewer-verdict line to `~/.claude/logs/reviewer-verdicts.jsonl`. It is outside this gate's write scope:

   ```json
   {"ts":"2026-11-02T00:00:00Z","contract_path":"D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md","divergence":false,"drift_summary":"none; block 8 B1 and W3 cleared by block 12","critical_count":0,"warn_count":2}
   ```
