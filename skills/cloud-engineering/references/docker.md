# Docker reference

Open this file only when `cloud.iac` names `docker`. The rules live in `cross-cutting.md`; this file maps each topic to container practice and to non-mutating commands. It covers Dockerfiles, Compose files and image handling.

## Topic map

| Topic | Docker practice |
|---|---|
| Networking | Publish only the ports a service needs. Use user-defined networks, and keep databases off published ports. |
| Identity and access | Run as a non-root `USER`. Drop capabilities. Use a read-only root file system where the app allows it. |
| Secrets | Never copy a secret into an image layer or an `ENV` line. Use build secrets for build time and the platform secret store at run time. |
| Messaging | Give broker containers a health check and a named volume. Pin the broker image. |
| Storage | Use named volumes for state. Keep containers disposable. Add a `.dockerignore` to keep the build context small. |
| Observability | Write logs to standard output. Add a `HEALTHCHECK`. Set labels for version and source. |
| Cost | Use small base images and multi-stage builds. Set CPU and memory limits in Compose or the orchestrator. |
| Governance | Pin base images by digest. Scan images for vulnerabilities. Sign and record the provenance of images. |

## Review checklist

- The base image is pinned, small and maintained.
- A multi-stage build leaves compilers and tests out of the final image.
- Layers are ordered so dependency files come before source files, for cache reuse.
- No `latest` tag in production references.
- The container does not run as root.

## Validation steps

Ready `contractLanding.verification.steps` entries. All are non-mutating. A local build writes only to the local image cache. Replace the angle-bracket values.

```json
[
  {
    "id": "docker-lint",
    "command": ["hadolint", "<Dockerfile>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 2
  },
  {
    "id": "docker-build-check",
    "command": ["docker", "build", "--check", "--file", "<Dockerfile>", "<context-dir>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 10
  },
  {
    "id": "docker-compose-config",
    "command": ["docker", "compose", "--file", "<compose.yaml>", "config", "--quiet"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 2
  },
  {
    "id": "docker-config-scan",
    "command": ["trivy", "config", "--exit-code", "1", "--severity", "HIGH,CRITICAL", "<context-dir>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 10
  },
  {
    "id": "docker-image-scan",
    "command": ["trivy", "image", "--exit-code", "1", "--severity", "HIGH,CRITICAL", "<image>:<tag>"],
    "results": { "format": "exit-code" },
    "timeout_minutes": 15
  }
]
```

## Troubleshooting

Read-only commands:

- Container state: `docker ps --all`
- Why it stopped: `docker inspect --format '{{.State.ExitCode}} {{.State.Error}}' <container>`
- Logs: `docker logs --tail 200 <container>`
- Resolved Compose model: `docker compose --file <compose.yaml> config`
- Image layers and size: `docker history <image>:<tag>`
- Resource use: `docker stats --no-stream`

Common causes: wrong entrypoint or command, a missing environment variable, a port already in use, a failing health check, or an out-of-memory kill (exit code 137).

## Live changes

Mutating commands are never run from this skill. Publishing an image is written like this:

**For the user to run**

```bash
docker push <registry>/<image>:<tag>
```
