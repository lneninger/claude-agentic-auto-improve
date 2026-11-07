# Terraform reference

Open this file only when `cloud.iac` names `terraform`. The rules live in `cross-cutting.md`; this file maps each topic to Terraform practice and to non-mutating commands. OpenTofu accepts the same commands under the name `tofu`.

## Topic map

| Topic | Terraform practice |
|---|---|
| Networking | One network module per environment. Declare security rules as separate resources, not inline, so a review shows each one. |
| Identity and access | Declare roles and bindings as code. Run the plan with a read-only identity and the release with a separate identity. |
| Secrets | Mark variables and outputs `sensitive`. Reference a secret store with a data source. Never place a secret in a variable file or in state you cannot protect. |
| Messaging | Declare queues, topics and dead-letter settings in one module so every consumer gets them. |
| Storage | Set `prevent_destroy` in the lifecycle block of stateful resources. Declare encryption, versioning and lifecycle rules. |
| Observability | Create log sinks, alerts and dashboards in the same module as the workload. |
| Cost | Put `tags` or `labels` in provider default tags. Require them with a variable validation rule. |
| Governance | Pin the Terraform version and each provider with `required_version` and `required_providers`. Commit the lock file. Run a policy scan on the plan. |

## State

- Use a remote backend with locking, encryption and versioning. The state file can hold secrets, so limit who can read it.
- One state per environment and per blast radius. Avoid one state for everything.
- Never edit state by hand. State changes are a hand-off to the user.

## Review checklist

- A plan that replaces or removes a stateful resource is a stop-and-ask item.
- No provider block holds credentials.
- Modules are pinned to a version or a commit.
- Every variable has a type and a description.

## Validation steps

Ready `contractLanding.verification.steps` entries. All are non-mutating. The plan reads live state and writes nothing. Replace the angle-bracket values.

```json
[
  {
    "id": "terraform-fmt",
    "command": ["terraform", "fmt", "-check", "-recursive", "-no-color"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 2
  },
  {
    "id": "terraform-init-local",
    "command": ["terraform", "-chdir=<root-module>", "init", "-backend=false", "-input=false", "-no-color"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 10
  },
  {
    "id": "terraform-validate",
    "command": ["terraform", "-chdir=<root-module>", "validate", "-no-color"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "terraform-policy-scan",
    "command": ["checkov", "--directory", "<root-module>", "--quiet", "--compact"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 10
  },
  {
    "id": "terraform-plan",
    "command": ["terraform", "-chdir=<root-module>", "plan", "-input=false", "-lock=false", "-no-color"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 20
  }
]
```

The plan step needs a configured backend and read access. Run the local steps first, because they need no credentials.

## Troubleshooting

Read-only commands:

- Show what Terraform tracks: `terraform state list`
- Show one tracked resource: `terraform state show <address>`
- Show the saved plan: `terraform show <plan-file>`
- Check the lock file against providers: `terraform providers`
- For a drift question, read the plan output for resources it wants to change that nobody touched in code.

Common causes: a provider version moved, the backend lock is held, the identity lost a permission, or a resource was changed outside code.

## Live changes

Mutating commands are never run from this skill. Write the release like this, saving the plan first so the user reviews exactly what runs:

**For the user to run**

```bash
terraform -chdir=<root-module> plan -out=release.tfplan
terraform -chdir=<root-module> apply release.tfplan
```
