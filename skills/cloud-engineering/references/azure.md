# Azure reference

Open this file only when `cloud.providers` names `azure`. The rules live in `cross-cutting.md`; this file maps each topic to Azure services and to non-mutating commands.

Commands need the Azure CLI (`az`) signed in to the right subscription. Check with `az account show`.

## Service map

| Topic | Azure services |
|---|---|
| Networking | Virtual Network, subnets, network security groups, Private Endpoint and Private DNS zones, Application Gateway or Front Door as the public entry |
| Identity and access | Microsoft Entra ID, managed identities (system or user assigned), Azure RBAC role assignments, Privileged Identity Management |
| Secrets | Key Vault with RBAC authorization, soft delete and purge protection on |
| Messaging | Service Bus (queues, topics), Event Grid (events), Event Hubs (streams) |
| Storage | Storage accounts (blob, with versioning and lifecycle rules), Azure SQL, Cosmos DB, Backup vaults |
| Observability | Azure Monitor, Log Analytics workspaces, Application Insights, Activity Log |
| Cost | Cost Management budgets, tags, Azure Advisor, reservations |
| Governance | Management groups, Azure Policy and initiatives, resource locks, Defender for Cloud |

## Networking

- Disable public network access on data services and use Private Endpoints.
- Attach a network security group to every subnet and end the rules with an explicit deny.

## Identity and access

- Give each workload a managed identity and assign it a built-in role at resource scope.
- Flag `Owner` and `Contributor` at subscription scope for workloads.

## Secrets

- Store secrets in Key Vault and reference them from app settings with Key Vault references.
- Enable purge protection so a deleted secret can be recovered.

## Messaging

- Use Service Bus with a dead-letter queue and set a maximum delivery count.
- Use managed identity authentication instead of connection strings.

## Storage

- Turn off shared key access and anonymous blob access on storage accounts.
- Use geo-redundant storage only for data that needs it.

## Observability

- Send diagnostic settings of every resource to a Log Analytics workspace.
- Set the workspace retention and a daily cap.

## Cost

- Require the `owner`, `environment` and `cost-centre` tags with a policy.
- Create a budget with alerts at 50, 80 and 100 percent.

## Governance

- Assign policy at management group scope, in audit mode first.
- Put a delete lock on stateful production resources.

## Validation steps

Ready `contractLanding.verification.steps` entries. All are non-mutating. Replace the angle-bracket values.

```json
[
  {
    "id": "azure-account",
    "command": ["az", "account", "show", "--output", "none"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 2
  },
  {
    "id": "azure-template-validate",
    "command": ["az", "deployment", "group", "validate", "--resource-group", "<resource-group>", "--template-file", "<main.bicep>", "--parameters", "<main.bicepparam>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 10
  },
  {
    "id": "azure-what-if",
    "command": ["az", "deployment", "group", "what-if", "--resource-group", "<resource-group>", "--template-file", "<main.bicep>", "--parameters", "<main.bicepparam>", "--no-pretty-print"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 15
  },
  {
    "id": "azure-policy-compliance",
    "command": ["az", "policy", "state", "summarize", "--resource-group", "<resource-group>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  }
]
```

## Troubleshooting

Read-only commands, in the order of `cross-cutting.md`:

- What changed: `az monitor activity-log list --resource-group <resource-group> --offset 1d`
- Who has access: `az role assignment list --scope <resource-id> --output table`
- Network rules: `az network nsg rule list --resource-group <resource-group> --nsg-name <nsg> --output table`
- Quotas: `az vm list-usage --location <region> --output table`
- Cost advice: `az advisor recommendation list --category Cost --output table`

## Live changes

Mutating commands are never run from this skill. For example, a group deployment is written like this:

**For the user to run**

```bash
az deployment group create --resource-group <resource-group> --template-file <main.bicep> --parameters <main.bicepparam>
```
