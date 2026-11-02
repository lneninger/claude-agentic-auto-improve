# Google Cloud reference

Open this file only when `cloud.providers` names `gcp`. The rules live in `cross-cutting.md`; this file maps each topic to Google Cloud services and to non-mutating commands.

Commands need the `gcloud` CLI signed in, with the project set. Check with `gcloud config list`.

## Service map

| Topic | Google Cloud services |
|---|---|
| Networking | VPC networks, subnets, firewall rules and policies, Private Service Connect, Cloud NAT, Cloud Load Balancing, Cloud DNS |
| Identity and access | IAM, service accounts with workload identity, Workload Identity Federation, IAM Recommender, organization policies |
| Secrets | Secret Manager, Cloud KMS |
| Messaging | Pub/Sub (topics, subscriptions), Eventarc, Cloud Tasks, Dataflow for streams |
| Storage | Cloud Storage (uniform access, versioning, lifecycle), Cloud SQL, Spanner, Firestore, Backup and DR |
| Observability | Cloud Logging, Cloud Monitoring, Cloud Trace, Cloud Audit Logs |
| Cost | Cloud Billing budgets, labels, billing export to BigQuery, Recommender |
| Governance | Resource hierarchy (organization, folders, projects), organization policy constraints, Security Command Center |

## Networking

- Use private Google access and Private Service Connect for managed services.
- Prefer firewall policies at folder level, with deny rules for broad ranges.

## Identity and access

- Use one service account per workload and bind it with workload identity. Do not download service account keys.
- Review the IAM Recommender output for excess roles.

## Secrets

- Read secrets from Secret Manager at run time and pin a secret version only when needed.
- Grant `secretAccessor` on the single secret, not on the project.

## Messaging

- Give each Pub/Sub subscription a dead-letter topic and a retry policy.
- Make handlers idempotent, because delivery is at least once.

## Storage

- Enforce uniform bucket-level access and public access prevention.
- Use lifecycle rules to move objects to colder classes.

## Observability

- Route audit logs to a log bucket in a separate project through a sink.
- Create alerting policies on error rate and latency.

## Cost

- Label every resource with `owner`, `environment` and `cost-centre`.
- Create a budget with alerts and turn on billing export.

## Governance

- Enforce organization policy constraints, such as restricting external IP addresses.
- Keep one project per environment and workload.

## Validation steps

Ready `contractLanding.verification.steps` entries. All are non-mutating. Replace the angle-bracket values.

```json
[
  {
    "id": "gcp-config",
    "command": ["gcloud", "config", "list", "--format", "json"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 2
  },
  {
    "id": "gcp-iam-policy",
    "command": ["gcloud", "projects", "get-iam-policy", "<project-id>", "--format", "json"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "gcp-firewall-rules",
    "command": ["gcloud", "compute", "firewall-rules", "list", "--project", "<project-id>", "--format", "json"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "gcp-org-policies",
    "command": ["gcloud", "resource-manager", "org-policies", "list", "--project", "<project-id>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  }
]
```

For Terraform-managed projects, prefer the plan step in `terraform.md`.

## Troubleshooting

Read-only commands, in the order of `cross-cutting.md`:

- What changed: `gcloud logging read 'protoPayload.@type="type.googleapis.com/google.cloud.audit.AuditLog"' --limit 50 --freshness 1d`
- Who has access: `gcloud projects get-iam-policy <project-id>`
- Network rules: `gcloud compute firewall-rules list --project <project-id>`
- Quotas: `gcloud compute project-info describe --project <project-id>`
- Recommendations: `gcloud recommender recommendations list --project <project-id> --location global --recommender google.iam.policy.Recommender`

## Live changes

Mutating commands are never run from this skill. For example, a serverless release is written like this:

**For the user to run**

```bash
gcloud run deploy <service-name> --image <image> --region <region>
```
