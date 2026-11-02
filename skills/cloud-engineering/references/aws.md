# AWS reference

Open this file only when `cloud.providers` names `aws`. The rules live in `cross-cutting.md`; this file maps each topic to AWS services and to non-mutating commands.

Commands need the AWS CLI (`aws`) with a profile for the right account. Check with `aws sts get-caller-identity`.

## Service map

| Topic | AWS services |
|---|---|
| Networking | VPC, subnets, security groups, network ACLs, VPC endpoints (PrivateLink), Route 53, Application Load Balancer, CloudFront |
| Identity and access | IAM roles, IAM Identity Center, instance and task roles, service control policies, IAM Access Analyzer |
| Secrets | Secrets Manager, Systems Manager Parameter Store, KMS keys |
| Messaging | SQS (queues), SNS (topics), EventBridge (events), Kinesis (streams), MSK |
| Storage | S3 (with Block Public Access, versioning, lifecycle rules), EBS, RDS and Aurora, DynamoDB, AWS Backup |
| Observability | CloudWatch Logs, metrics and alarms, X-Ray, CloudTrail |
| Cost | Cost Explorer, AWS Budgets, cost allocation tags, Compute Optimizer |
| Governance | AWS Organizations, service control policies, AWS Config rules, Control Tower, Security Hub |

## Networking

- Run workloads in private subnets and reach AWS services through VPC endpoints.
- Reference security groups from other security groups instead of wide address ranges.

## Identity and access

- Use roles with short-lived credentials. Do not create IAM user access keys for workloads.
- Run IAM Access Analyzer and treat external-access findings as defects.

## Secrets

- Read secrets at run time from Secrets Manager. Turn on rotation for database credentials.
- Encrypt with customer-managed KMS keys where policy requires it.

## Messaging

- Give each SQS queue a dead-letter queue and a redrive policy.
- Use FIFO queues only when ordering matters, because throughput is lower.

## Storage

- Turn on S3 Block Public Access at the account level.
- Enable versioning and a lifecycle rule on buckets that hold data you cannot recreate.

## Observability

- Enable an organization CloudTrail trail to a locked-down log archive account.
- Set log group retention on every log group.

## Cost

- Activate cost allocation tags and create a budget with alerts.
- Review Compute Optimizer findings each month.

## Governance

- Attach service control policies at the organizational unit level.
- Use AWS Config rules in detect mode first.

## Validation steps

Ready `contractLanding.verification.steps` entries. All are non-mutating. Replace the angle-bracket values.

```json
[
  {
    "id": "aws-identity",
    "command": ["aws", "sts", "get-caller-identity"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 2
  },
  {
    "id": "aws-template-validate",
    "command": ["aws", "cloudformation", "validate-template", "--template-body", "file://<template.yaml>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "aws-config-compliance",
    "command": ["aws", "configservice", "describe-compliance-by-config-rule", "--compliance-types", "NON_COMPLIANT"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "aws-access-analyzer",
    "command": ["aws", "accessanalyzer", "list-findings-v2", "--analyzer-arn", "<analyzer-arn>", "--max-results", "50"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  }
]
```

For Terraform-managed stacks, prefer the plan step in `terraform.md`.

## Troubleshooting

Read-only commands, in the order of `cross-cutting.md`:

- What changed: `aws cloudtrail lookup-events --max-results 50`
- Who is acting: `aws sts get-caller-identity`
- Network rules: `aws ec2 describe-security-groups --group-ids <group-id>`
- Quotas: `aws service-quotas list-service-quotas --service-code <service-code>`
- Spend by service: `aws ce get-cost-and-usage --time-period Start=<start>,End=<end> --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE`

## Live changes

Mutating commands are never run from this skill. For example, a stack release is written like this:

**For the user to run**

```bash
aws cloudformation deploy --template-file <template.yaml> --stack-name <stack-name> --capabilities CAPABILITY_IAM
```
