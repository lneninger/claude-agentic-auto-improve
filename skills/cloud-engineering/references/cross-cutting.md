# Cross-cutting cloud rules

Provider-neutral rules. Each topic gives the rule, then points at the provider file for services and commands.
Open only the provider files the profile names.

Provider files: `azure.md`, `aws.md`, `gcp.md`. Tool files: `terraform.md`, `bicep.md`, `docker.md`, `kubernetes.md`.

## Networking

- Put workloads in private networks. Expose only what must be public, behind a managed entry point.
- Default to deny between subnets; open the narrowest port and source range that works.
- Reach platform services over private endpoints, not the public internet.
- Keep environments in separate networks and accounts.

See each provider file, section "Networking".

## Identity and access

- Use workload identities (managed identities, roles, service accounts). Do not create long-lived keys.
- Grant least privilege at the smallest scope. Prefer role assignments to groups, not people.
- Separate the identity that deploys from the identity that runs the workload.
- Review wildcard actions and wildcard resources as defects.

See each provider file, section "Identity and access".

## Secrets

- Keep secrets in a managed secret store. Code and configuration hold only a reference.
- Never commit a secret, even to a private repository. Rotate any secret that was committed.
- Scope each secret to the one workload that reads it, and enable rotation where the service supports it.
- Do not print secret values in logs or validation output.

See each provider file, section "Secrets".

## Messaging

- Choose queues for work hand-off and topics for fan-out. Choose streams only for ordered, high-volume data.
- Design consumers to be idempotent, because delivery is at least once.
- Configure a dead-letter destination and an alert on its depth.
- Encrypt in transit and at rest, and authenticate with workload identity.

See each provider file, section "Messaging".

## Storage

- Block public access by default. Turn on encryption at rest and versioning for data you cannot recreate.
- Set lifecycle rules so cold data moves to cheaper tiers and temporary data expires.
- Back up databases with a tested restore, and state the recovery point and recovery time targets.
- Pick the storage class from the access pattern, not from habit.

See each provider file, section "Storage".

## Observability

- Collect logs, metrics and traces for every workload, with one correlation id across services.
- Alert on symptoms users feel (errors, latency, saturation), then on causes.
- Set retention on logs so cost stays bounded.
- Record audit logs for control-plane activity in a place the workload cannot edit.

See each provider file, section "Observability".

## Cost

- Tag every resource with owner, environment and cost centre.
- Set budgets with alerts before the first resource exists.
- Size from measured use. Prefer autoscaling and scale-to-zero for spiky load.
- Delete idle resources through code review, so the change is visible.

See each provider file, section "Cost".

## Governance

- Enforce rules with policy as code, not with documents. Start in audit mode, then enforce.
- Organise accounts or subscriptions or projects by environment and ownership.
- Keep infrastructure in version control. Every change goes through review and a plan or what-if preview.
- Pin versions of providers, modules, images and charts.

See each provider file, section "Governance".

## Deployment validation

- Validate in this order: format and lint, schema validation, policy scan, plan or what-if preview, then a human review of the preview.
- Use only non-mutating commands for validation. They read state and write nothing to a live environment.
- Each provider and tool file lists ready `contractLanding.verification.steps` entries. A step passes on exit code zero.
- Treat any planned deletion or replacement of stateful resources as a stop-and-ask item.
- A live change is a hand-off. Write it in a block labelled "for the user to run" and let the user decide.

See each provider and tool file, section "Validation steps".

## Troubleshooting

Follow this order and use read-only commands:

1. State the symptom and the time it began.
2. Check what changed: recent deployments, policy changes, certificate and secret expiry.
3. Check identity: which principal acted, and which permission was denied.
4. Check networking: name resolution, routes, rules, private endpoints.
5. Check capacity and quotas.
6. Read workload logs and platform events.
7. Propose the smallest fix, and hand any live change to the user.

See each provider file, section "Troubleshooting".
