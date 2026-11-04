# Bicep reference

Open this file only when `cloud.iac` names `bicep`. Bicep targets Azure, so it is normally used with `azure.md`. The rules live in `cross-cutting.md`; this file maps each topic to Bicep practice and to non-mutating commands.

Commands need the Azure CLI (`az`) with its Bicep tooling already present. Check with `az bicep version`.

## Topic map

| Topic | Bicep practice |
|---|---|
| Networking | A network module that outputs subnet ids. Declare security rules as child resources so a review shows each one. |
| Identity and access | Declare role assignments with a deterministic name from `guid()`. Use managed identities and pass the principal id as a parameter. |
| Secrets | Mark parameters `@secure()`. Reference Key Vault from a parameter file with a `reference` entry. Never place a secret in an output. |
| Messaging | One module for namespace, queues, topics and dead-letter settings. |
| Storage | Declare encryption, soft delete, versioning and public access settings explicitly. |
| Observability | Declare diagnostic settings next to the resource they cover. |
| Cost | Pass a shared `tags` object into every module. Add `@allowed` and `@minLength` decorators to limit costly sizes. |
| Governance | Use `targetScope` deliberately. Keep policy definitions in a module deployed at management group scope. Use a `bicepconfig.json` to set linter rules to error. |

## Review checklist

- Every parameter has a type, a `@description` and, where useful, `@allowed`.
- API versions are explicit and not older than needed.
- Modules come from a registry with a pinned version, or from a local path.
- Deployment mode `Complete` is a stop-and-ask item, because it removes resources not in the template.

## Validation steps

Ready `contractLanding.verification.steps` entries. All are non-mutating. The what-if step reads live state and writes nothing. Replace the angle-bracket values.

```json
[
  {
    "id": "bicep-lint",
    "command": ["az", "bicep", "lint", "--file", "<main.bicep>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "bicep-build",
    "command": ["az", "bicep", "build", "--file", "<main.bicep>", "--stdout"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "bicep-validate",
    "command": ["az", "deployment", "group", "validate", "--resource-group", "<resource-group>", "--template-file", "<main.bicep>", "--parameters", "<main.bicepparam>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 10
  },
  {
    "id": "bicep-what-if",
    "command": ["az", "deployment", "group", "what-if", "--resource-group", "<resource-group>", "--template-file", "<main.bicep>", "--parameters", "<main.bicepparam>", "--no-pretty-print"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 15
  }
]
```

For subscription-scope templates, use `az deployment sub what-if --location <region> --template-file <main.bicep>`.

## Troubleshooting

Read-only commands:

- List past deployments: `az deployment group list --resource-group <resource-group> --output table`
- Read a failed deployment: `az deployment group show --resource-group <resource-group> --name <deployment-name>`
- Read operation errors: `az deployment operation group list --resource-group <resource-group> --name <deployment-name>`
- Read the compiled template: `az bicep build --file <main.bicep> --stdout`

Common causes: a missing resource provider registration, a quota limit, a policy denial, or a name that is not unique.

## Live changes

Mutating commands are never run from this skill. Write the release like this:

**For the user to run**

```bash
az deployment group create --resource-group <resource-group> --template-file <main.bicep> --parameters <main.bicepparam>
```
