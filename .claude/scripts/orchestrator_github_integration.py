#!/usr/bin/env python3
"""
GitHub Integration for Contract Orchestration — create and track issues.

Responsibilities:
1. Create parent issue for Contract
2. Create child issues for each task
3. Update task issues with execution status
4. Link commits to issues
5. Close issues on completion
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime


class GitHubIntegration:
    """Manages GitHub issue creation and updates for Contract execution."""

    def __init__(self, contract_id: str, contract_path: Path):
        self.contract_id = contract_id
        self.contract_path = contract_path
        self.parent_issue = None
        self.task_issues = {}
        self.repo = self._detect_repo()

    def _detect_repo(self) -> Optional[str]:
        """Detect GitHub repository from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip()

            # Parse: git@github.com:owner/repo.git or https://github.com/owner/repo.git
            if "github.com" in remote_url:
                if remote_url.startswith("git@"):
                    # git@github.com:owner/repo.git
                    parts = remote_url.replace("git@github.com:", "").replace(".git", "").split("/")
                else:
                    # https://github.com/owner/repo.git
                    parts = remote_url.rstrip("/").replace(".git", "").split("/")[-2:]

                if len(parts) >= 2:
                    return f"{parts[0]}/{parts[1]}"
        except Exception:
            pass

        return None

    def create_contract_issue(self, title: str, description: str) -> Optional[int]:
        """Create parent GitHub issue for Contract."""
        if not self.repo:
            print("[WARN] GitHub repo not detected; skipping issue creation")
            return None

        print(f"Creating GitHub issue for Contract: {self.contract_id}")

        # Build issue body
        body = f"""# Contract: {title}

{description}

**Contract ID:** {self.contract_id}
**Status:** In Progress
**Started:** {datetime.utcnow().isoformat()}Z

## Tasks

(Tasks will be linked below as they are created)

## Execution Log

- Contract orchestration started
"""

        try:
            result = subprocess.run(
                ["gh", "issue", "create",
                 "--repo", self.repo,
                 "--title", f"Contract: {title}",
                 "--body", body],
                capture_output=True,
                text=True,
                check=True
            )

            # Extract issue number from output (e.g., "https://github.com/owner/repo/issues/42")
            issue_url = result.stdout.strip()
            issue_number = int(issue_url.split("/")[-1])
            self.parent_issue = issue_number

            print(f"[OK] Contract issue created: #{issue_number}")
            return issue_number

        except subprocess.CalledProcessError as e:
            print(f"[WARN] Failed to create Contract issue: {e.stderr}")
            return None

    def create_task_issue(self, task_id: str, task_title: str,
                         dependencies: list = None, acceptance_criteria: str = "") -> Optional[int]:
        """Create GitHub issue for individual task."""
        if not self.repo or not self.parent_issue:
            return None

        print(f"Creating GitHub issue for task: {task_id}")

        # Build issue body
        deps_text = ""
        if dependencies:
            deps_text = f"**Dependencies:** {', '.join(dependencies)}\n\n"

        body = f"""# Task: {task_title}

**Task ID:** {task_id}
**Status:** Pending
**Parent Contract:** #{self.parent_issue}

{deps_text}## Acceptance Criteria

{acceptance_criteria or 'No specific criteria defined'}

## Execution Status

- [ ] In Progress
- [ ] Tests Passed
- [ ] Completed
"""

        try:
            result = subprocess.run(
                ["gh", "issue", "create",
                 "--repo", self.repo,
                 "--title", f"Task: {task_title}",
                 "--body", body],
                capture_output=True,
                text=True,
                check=True
            )

            issue_url = result.stdout.strip()
            issue_number = int(issue_url.split("/")[-1])
            self.task_issues[task_id] = issue_number

            print(f"[OK] Task issue created: #{issue_number}")
            return issue_number

        except subprocess.CalledProcessError as e:
            print(f"[WARN] Failed to create task issue: {e.stderr}")
            return None

    def update_task_issue(self, task_id: str, status: str, commit: str = None) -> bool:
        """Update task issue with execution status."""
        if task_id not in self.task_issues or not self.repo:
            return False

        issue_number = self.task_issues[task_id]

        # Build status update comment
        status_map = {
            "running": "Task execution started",
            "completed": f"Task completed: {commit or 'unknown commit'}",
            "failed": "Task execution failed"
        }

        comment = f"**Status Update:** {status_map.get(status, status)}\n\n"
        if status == "completed" and commit:
            comment += f"**Commit:** {commit}"

        try:
            subprocess.run(
                ["gh", "issue", "comment", str(issue_number),
                 "--repo", self.repo,
                 "--body", comment],
                capture_output=True,
                text=True,
                check=True
            )

            print(f"[OK] Task issue updated: #{issue_number}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"[WARN] Failed to update task issue: {e.stderr}")
            return False

    def close_task_issue(self, task_id: str, reason: str = "Task completed") -> bool:
        """Close task GitHub issue."""
        if task_id not in self.task_issues or not self.repo:
            return False

        issue_number = self.task_issues[task_id]

        try:
            subprocess.run(
                ["gh", "issue", "close", str(issue_number),
                 "--repo", self.repo,
                 "--comment", reason],
                capture_output=True,
                text=True,
                check=True
            )

            print(f"[OK] Task issue closed: #{issue_number}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"[WARN] Failed to close task issue: {e.stderr}")
            return False

    def close_contract_issue(self, reason: str = "Contract completed") -> bool:
        """Close parent Contract GitHub issue."""
        if not self.parent_issue or not self.repo:
            return False

        try:
            subprocess.run(
                ["gh", "issue", "close", str(self.parent_issue),
                 "--repo", self.repo,
                 "--comment", reason],
                capture_output=True,
                text=True,
                check=True
            )

            print(f"[OK] Contract issue closed: #{self.parent_issue}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"[WARN] Failed to close Contract issue: {e.stderr}")
            return False

    def link_commit_to_issue(self, task_id: str, commit: str) -> bool:
        """Link git commit to task issue (via branch/PR)."""
        if task_id not in self.task_issues:
            return False

        issue_number = self.task_issues[task_id]

        # Create reference in issue body or comment
        comment = f"Linked commit: `{commit}`\n\n" \
                  f"Fixed by commit in task/{self.contract_id}-{task_id} branch"

        try:
            subprocess.run(
                ["gh", "issue", "comment", str(issue_number),
                 "--repo", self.repo,
                 "--body", comment],
                capture_output=True,
                text=True,
                check=True
            )

            print(f"[OK] Commit linked to issue: #{issue_number}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"[WARN] Failed to link commit: {e.stderr}")
            return False


def create_github_integration(contract_id: str, contract_path: Path) -> GitHubIntegration:
    """Factory function to create GitHub integration instance."""
    return GitHubIntegration(contract_id, contract_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: orchestrator_github_integration.py <contract-id>")
        sys.exit(1)

    contract_id = sys.argv[1]
    contract_path = Path(f".claude/concepts/{contract_id}.md")

    integration = create_github_integration(contract_id, contract_path)
    print(f"GitHub integration for {contract_id}: {integration.repo}")
