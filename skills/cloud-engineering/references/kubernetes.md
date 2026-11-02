# Kubernetes reference

Open this file only when `cloud.iac` names `kubernetes`. The rules live in `cross-cutting.md`; this file maps each topic to Kubernetes objects and to non-mutating commands. It covers manifests, Kustomize and Helm charts.

Commands need `kubectl` pointed at the right cluster. Check with `kubectl config current-context` before any command that reads cluster state.

## Topic map

| Topic | Kubernetes objects |
|---|---|
| Networking | Services, Ingress or Gateway API routes, NetworkPolicy with default deny per namespace, DNS |
| Identity and access | ServiceAccounts per workload, Role and RoleBinding at namespace scope, workload identity annotations for cloud access, Pod Security Standards |
| Secrets | External secrets operator or a CSI secret store driver. Avoid plain Secret manifests in version control. |
| Messaging | Broker operators or managed brokers reached by Service name. Set a PodDisruptionBudget on consumers. |
| Storage | PersistentVolumeClaims with a StorageClass, StatefulSets for stateful workloads, volume snapshots |
| Observability | Liveness, readiness and startup probes, standard output logs, metrics endpoints, events |
| Cost | Resource requests and limits on every container, ResourceQuota and LimitRange per namespace, Horizontal Pod Autoscaler |
| Governance | Namespaces per team or environment, admission policy (Pod Security Admission, policy engine), labels, pinned image digests |

## Review checklist

- Every container sets requests, limits and probes.
- Pods run as non-root with a read-only root file system and no privilege escalation.
- No `latest` tag. Prefer image digests.
- Each namespace has a default-deny NetworkPolicy.
- Cluster-wide roles and `cluster-admin` bindings are stop-and-ask items.

## Validation steps

Ready `contractLanding.verification.steps` entries. All are non-mutating. The diff step compares files with the live cluster and changes nothing. Replace the angle-bracket values.

```json
[
  {
    "id": "k8s-schema",
    "command": ["kubeconform", "-strict", "-summary", "<manifests-dir>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "helm-lint",
    "command": ["helm", "lint", "<chart-dir>", "--strict"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "helm-template",
    "command": ["helm", "template", "<release-name>", "<chart-dir>", "--values", "<values.yaml>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 5
  },
  {
    "id": "k8s-policy-scan",
    "command": ["trivy", "config", "--exit-code", "1", "--severity", "HIGH,CRITICAL", "<manifests-dir>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 10
  },
  {
    "id": "k8s-diff",
    "command": ["kubectl", "diff", "--filename", "<manifests-dir>", "--recursive"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 10
  }
]
```

`kubectl diff` exits with 1 when there are differences and above 1 on errors. If differences are expected, ask the user whether to treat exit code 1 as a pass before adding that step.

## Troubleshooting

Read-only commands:

- Object state: `kubectl get pods --namespace <namespace> --output wide`
- Events, newest last: `kubectl get events --namespace <namespace> --sort-by=.lastTimestamp`
- Why a pod is not ready: `kubectl describe pod <pod> --namespace <namespace>`
- Logs, including the previous crash: `kubectl logs <pod> --namespace <namespace> --previous`
- Permission check: `kubectl auth can-i --list --namespace <namespace>`
- Resource use: `kubectl top pods --namespace <namespace>`
- Rollout state: `kubectl rollout status deployment/<name> --namespace <namespace>`

Common causes: an image that cannot be pulled, a failing probe, a request larger than any node, a missing Secret or ConfigMap, a NetworkPolicy that blocks traffic, or a quota limit.

## Live changes

Mutating commands are never run from this skill. A release is written like this:

**For the user to run**

```bash
kubectl apply --filename <manifests-dir> --recursive
helm upgrade --install <release-name> <chart-dir> --namespace <namespace> --values <values.yaml>
```
