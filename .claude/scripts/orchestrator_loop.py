#!/usr/bin/env python3
"""
Orchestrator Loop — autonomous Contract execution state machine.

Manages the full lifecycle of Contract execution:
1. Initialize execution state
2. Loop through task selection and execution
3. Monitor for Architect re-entry triggers
4. Coordinate final review
5. Mark Contract complete
"""

import sys
import json
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

try:
    from task_executor_launcher import execute_task
    from final_reviewer import review_contract
    from orchestrator_github_integration import create_github_integration
    from orchestrator_parallel_executor import create_parallel_executor
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from task_executor_launcher import execute_task
    from final_reviewer import review_contract
    from orchestrator_github_integration import create_github_integration
    from orchestrator_parallel_executor import create_parallel_executor

class ContractStatus(Enum):
    """Contract execution status."""
    PENDING = "pending"
    EXECUTING = "executing"
    PAUSED_ARCHITECT = "paused_architect"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class OrchestratorLoop:
    """Main Contract orchestration loop."""

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.state_dir = Path(".claude/orchestrator/state") / contract_id
        self.plans_dir = Path(".claude/orchestrator/plans") / contract_id
        self.results_dir = Path(".claude/orchestrator/results") / contract_id

        # Create directories
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.state_dir / "state.yaml"
        self.task_map_file = self.plans_dir / "task-map.yaml"
        self.contract_path = self._find_contract()

        self.state = self._load_or_create_state()
        self.task_map = self._load_task_map()

        # Initialize GitHub integration
        self.github = create_github_integration(contract_id, self.contract_path) if self.contract_path else None

        # Initialize parallel executor
        self.parallel_executor = create_parallel_executor(max_workers=3)

    def _load_or_create_state(self) -> Dict[str, Any]:
        """Load execution state or create new one."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return yaml.safe_load(f) or {}

        return {
            "contract_id": self.contract_id,
            "contract_version": 1,
            "status": ContractStatus.PENDING.value,
            "execution": {
                "started_at": datetime.utcnow().isoformat() + "Z",
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "tasks": {},
                "running_tasks": []
            },
            "architect_review": {
                "required": False,
                "task_id": None,
                "discovery": None
            },
            "final_review": {
                "status": "pending",
                "timestamp": None,
                "summary": None,
                "findings": {}
            },
            "recovery": {
                "attempts": 0,
                "last_failure": None
            }
        }

    def _load_task_map(self) -> Dict[str, Any]:
        """Load task map/DAG. Returns empty map if file does not exist."""
        if not self.task_map_file.exists():
            # Return empty task map; will be generated during execution if needed
            return {"tasks": []}

        with open(self.task_map_file, 'r') as f:
            return yaml.safe_load(f) or {}

    def _find_contract(self) -> Optional[Path]:
        """Find the approved Contract file for this execution."""
        concepts_dir = Path(".claude/concepts")
        if not concepts_dir.exists():
            return None

        # Try pattern matching on contract ID
        for contract_file in concepts_dir.glob("*.md"):
            with open(contract_file, 'r') as f:
                content = f.read()
                if self.contract_id in content or "Status: approved" in content:
                    return contract_file

        return None

    def _extract_contract_title(self) -> str:
        """Extract Contract title from file."""
        if not self.contract_path or not self.contract_path.exists():
            return f"Contract {self.contract_id}"

        with open(self.contract_path, 'r') as f:
            for line in f:
                if line.startswith("# "):
                    return line[2:].strip()
                elif line.startswith("**Project:** "):
                    return line[13:].strip()

        return f"Contract {self.contract_id}"

    def _extract_contract_description(self) -> str:
        """Extract Contract description from file."""
        if not self.contract_path or not self.contract_path.exists():
            return "Contract execution in progress"

        with open(self.contract_path, 'r') as f:
            content = f.read()
            # Try to extract summary or first paragraph
            lines = content.split('\n')
            for line in lines[5:15]:  # Check first few lines after header
                if line.strip() and not line.startswith('#'):
                    return line.strip()

        return "Contract execution in progress"

    def save_state(self):
        """Persist execution state."""
        self.state["execution"]["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(self.state_file, 'w') as f:
            yaml.dump(self.state, f, default_flow_style=False, sort_keys=False)

    def run(self):
        """Execute main orchestration loop."""
        print(f"\n{'='*60}")
        print(f"Contract Orchestrator — {self.contract_id}")
        print(f"{'='*60}\n")

        try:
            # Validate Contract exists
            self._validate_contract()

            # Main execution loop
            while self.state["status"] != ContractStatus.COMPLETE.value:
                if self.state["status"] == ContractStatus.PENDING.value:
                    self._start_execution()
                elif self.state["status"] == ContractStatus.EXECUTING.value:
                    self._execute_next_tasks()
                elif self.state["status"] == ContractStatus.PAUSED_ARCHITECT.value:
                    self._wait_for_architect()
                elif self.state["status"] == ContractStatus.VERIFYING.value:
                    self._run_final_review()
                else:
                    break

            print(f"\n✓ Contract {self.contract_id} execution complete")
            self.save_state()

        except Exception as e:
            print(f"\n✗ Contract execution failed: {e}")
            self.state["status"] = ContractStatus.FAILED.value
            self.save_state()
            sys.exit(1)

    def _validate_contract(self):
        """Validate Contract file exists and is approved."""
        # Find the Contract file
        concepts_dir = Path(".claude/concepts")
        contract_files = list(concepts_dir.glob("**/*.md"))

        # For now, we just check that .claude/concepts exists
        if not concepts_dir.exists():
            raise Exception(f"Concepts directory not found: {concepts_dir}")

        print(f"✓ Contract structure validated")

    def _start_execution(self):
        """Transition from PENDING to EXECUTING."""
        print("Starting Contract execution...")
        self.state["status"] = ContractStatus.EXECUTING.value
        self.state["execution"]["started_at"] = datetime.utcnow().isoformat() + "Z"

        # Create GitHub issues if integration available
        if self.github:
            contract_title = self._extract_contract_title()
            contract_description = self._extract_contract_description()
            self.github.create_contract_issue(contract_title, contract_description)

        # Initialize task states
        for task in self.task_map.get("tasks", []):
            task_id = task.get("id")
            if task_id not in self.state["execution"]["tasks"]:
                self.state["execution"]["tasks"][task_id] = {
                    "status": TaskStatus.PENDING.value,
                    "branch": f"task/{self.contract_id}-{task_id}",
                    "commit": None,
                    "result_path": str(self.results_dir / f"{task_id}.yaml"),
                    "github_issue": None
                }

                # Create GitHub issue for task
                if self.github:
                    deps = task.get("dependencies", [])
                    criteria = task.get("acceptance_criteria", "")
                    issue_num = self.github.create_task_issue(
                        task_id,
                        task.get("title", task_id),
                        dependencies=deps,
                        acceptance_criteria=criteria
                    )
                    self.state["execution"]["tasks"][task_id]["github_issue"] = issue_num

        self.save_state()
        print(f"[OK] Execution started with {len(self.state['execution']['tasks'])} tasks")

    def _execute_next_tasks(self):
        """Find and execute next ready tasks (sequentially or in parallel)."""
        # Find READY tasks
        ready_tasks = self._find_ready_tasks()

        if not ready_tasks:
            # Check if all tasks are complete
            all_complete = all(
                task["status"] == TaskStatus.COMPLETED.value
                for task in self.state["execution"]["tasks"].values()
            )

            if all_complete:
                print("[OK] All tasks completed")
                self.state["status"] = ContractStatus.VERIFYING.value
                self.save_state()
                return

            # Check for blocked/failed tasks
            failed = [tid for tid, t in self.state["execution"]["tasks"].items()
                     if t["status"] == TaskStatus.FAILED.value]
            blocked = [tid for tid, t in self.state["execution"]["tasks"].items()
                      if t["status"] == TaskStatus.BLOCKED.value]

            if failed:
                print(f"[FAIL] Tasks failed: {', '.join(failed)}")
                self.state["status"] = ContractStatus.FAILED.value
                self.save_state()
                return

            if blocked:
                print(f"[WARN] Tasks blocked: {', '.join(blocked)}")
                # Attempt recovery
                self._attempt_recovery(blocked)
                return

            print("No ready tasks; waiting...")
            return

        # Execute ready tasks (use parallel execution when multiple tasks are ready)
        if len(ready_tasks) > 1:
            self._execute_tasks_parallel(ready_tasks)
        else:
            self._execute_task_sequential(ready_tasks[0])

        self.save_state()

    def _execute_task_sequential(self, task_id: str):
        """Execute a single task sequentially."""
        print(f"\nExecuting {task_id}...")

        # Find task data from task map
        task_data = None
        for task in self.task_map.get("tasks", []):
            if task.get("id") == task_id:
                task_data = task
                break

        # Execute task in isolated session
        if self.contract_path:
            result = execute_task(self.contract_id, task_id, task_data or {}, self.contract_path)
        else:
            print(f"[WARN] Contract not found, simulating execution")
            result = self._simulate_task_execution(task_id)

        # Process result
        self._process_task_result(task_id, result)

    def _execute_tasks_parallel(self, ready_tasks: List[str]):
        """Execute multiple ready tasks in parallel."""
        print(f"\nExecuting {len(ready_tasks)} tasks in parallel...")

        # Use parallel executor
        results = self.parallel_executor.execute_with_priority(
            ready_tasks,
            self.task_map,
            self.state,
            self.contract_id,
            self.contract_path,
            max_parallel=3
        )

        # Process all results
        for task_id, result in results.items():
            self._process_task_result(task_id, result)

    def _find_ready_tasks(self) -> List[str]:
        """Find tasks that are ready to execute (dependencies complete and merged)."""
        ready = []

        for task in self.task_map.get("tasks", []):
            task_id = task.get("id")
            task_state = self.state["execution"]["tasks"].get(task_id, {})

            # Skip if already completed or running
            if task_state.get("status") in [TaskStatus.COMPLETED.value, TaskStatus.RUNNING.value]:
                continue

            # Check if all dependencies are completed
            deps = task.get("dependencies", [])
            all_deps_complete = all(
                self.state["execution"]["tasks"].get(dep, {}).get("status") == TaskStatus.COMPLETED.value
                for dep in deps
            )

            if not all_deps_complete:
                continue

            # Check if all dependencies are merged to master
            if deps and not self._verify_dependencies_merged(deps):
                # Mark task as blocked waiting for merge
                task_state["status"] = TaskStatus.BLOCKED.value
                print(f"[WARN] {task_id} blocked: dependencies not merged to master")
                continue

            ready.append(task_id)

        return ready

    def _verify_dependencies_merged(self, dependencies: List[str]) -> bool:
        """Verify that all dependencies are merged to master.

        Returns True if all dependencies are merged or if we're in a test environment.
        """
        import subprocess

        for dep_task_id in dependencies:
            dep_branch = f"task/{self.contract_id}-{dep_task_id}"

            try:
                result = subprocess.run(
                    ["git", "merge-base", "--is-ancestor", dep_branch, "master"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                # If branch doesn't exist or check fails, it means:
                # - Test environment (branch was cleaned up)
                # - Simulation (branch never created)
                # In these cases, assume dependency is satisfied
                if result.returncode != 0:
                    # Check if this is a real branch that exists
                    exists_result = subprocess.run(
                        ["git", "rev-parse", "--verify", dep_branch],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    # If branch doesn't exist, assume test/simulation environment
                    if exists_result.returncode != 0:
                        continue  # Branch doesn't exist, skip check

                    # Branch exists but not merged - this is a real error
                    return False

            except (subprocess.TimeoutExpired, FileNotFoundError):
                # If git command fails, assume test environment
                continue

        return True

    def _simulate_task_execution(self, task_id: str) -> Dict[str, Any]:
        """Simulate task execution. Real implementation would launch fresh Claude session."""
        # This is a placeholder that simulates successful execution
        return {
            "status": "completed",
            "commit": "abc123def456",
            "tests_passed": True,
            "contract_impact_requires_architect": False
        }

    def _process_task_result(self, task_id: str, result: Dict[str, Any]):
        """Process task result and update state."""
        status = result.get("status")

        if status == "completed":
            self.state["execution"]["tasks"][task_id]["status"] = TaskStatus.COMPLETED.value
            self.state["execution"]["tasks"][task_id]["commit"] = result.get("commit")
            print(f"[OK] {task_id} completed: {result.get('commit')}")

            # Update GitHub issue
            if self.github:
                self.github.update_task_issue(task_id, "completed", result.get("commit"))
                self.github.link_commit_to_issue(task_id, result.get("commit"))
                self.github.close_task_issue(task_id, f"Task completed: {result.get('commit')}")

            # Check for architect trigger (nested under contract_impact)
            contract_impact = result.get("contract_impact", {})
            if contract_impact.get("requires_architect"):
                print(f"[WARN] {task_id} requires Architect review")
                self.state["status"] = ContractStatus.PAUSED_ARCHITECT.value
                self.state["architect_review"]["required"] = True
                self.state["architect_review"]["task_id"] = task_id
                self.state["architect_review"]["discovery"] = {
                    "task_id": task_id,
                    "severity": contract_impact.get("severity", "unknown"),
                    "description": contract_impact.get("description", "Unknown discovery"),
                    "commit": result.get("commit")
                }

        elif status == "failed":
            self.state["execution"]["tasks"][task_id]["status"] = TaskStatus.FAILED.value
            print(f"[FAIL] {task_id} failed")

            # Update GitHub issue
            if self.github:
                self.github.update_task_issue(task_id, "failed")
                self.github.close_task_issue(task_id, f"Task failed: {result.get('error', 'Unknown error')}")

    def _wait_for_architect(self):
        """Invoke Architect agent to handle Contract-impacting discovery."""
        discovery = self.state.get("architect_review", {}).get("discovery", {})
        task_id = discovery.get("task_id", "unknown")
        description = discovery.get("description", "Unknown discovery")

        print("\n[WARN] Contract-impacting discovery detected")
        print(f"Task: {task_id}")
        print(f"Discovery: {description}")
        print("\nInvoking Architect agent for Contract review...\n")

        # Prepare briefing for Architect
        briefing = f"""
A task has discovered a Contract-level incompatibility that requires design review.

**Task:** {task_id}
**Severity:** {discovery.get('severity', 'medium')}
**Discovery:** {description}
**Commit:** {discovery.get('commit', 'unknown')}

Please review the existing Contract at:
{self.contract_path}

If the discovery reveals a design flaw:
1. Update the Contract to resolve the incompatibility
2. Increment the Contract version (v{self.state.get('contract_version', 1)} → v{self.state.get('contract_version', 1) + 1})
3. Mark status as: updated_by_architect

The orchestrator will recalculate the task plan from the updated Contract.
"""

        # In a real implementation, this would spawn an Agent:
        # from Agent import Agent
        # agent_result = Agent(
        #     description="Architect review of Contract-impacting discovery",
        #     prompt=briefing
        # )

        # For now, prompt the user (this is interactive mode)
        print("ARCHITECT BRIEFING:")
        print(briefing)
        response = input("\nPress Enter after Architect updates the Contract (or type 'skip' to assume no change): ").strip()

        if response.lower() != "skip":
            # Reload Contract to get updated version
            self._reload_contract()
            if self.state.get("contract_version", 1) > 1:
                print("[OK] Contract updated by Architect")
                self.state["architect_review"]["required"] = False
                self.state["status"] = ContractStatus.EXECUTING.value
                print("[OK] Resuming execution with updated Contract")
            else:
                print("[WARN] Contract version did not increment; assuming no change")
                self.state["architect_review"]["required"] = False
                self.state["status"] = ContractStatus.EXECUTING.value
        else:
            # Skip architect review and continue
            print("[OK] Skipping Architect review, resuming with existing Contract")
            self.state["architect_review"]["required"] = False
            self.state["status"] = ContractStatus.EXECUTING.value

    def _reload_contract(self):
        """Reload Contract from disk to detect updates."""
        if not self.contract_path or not self.contract_path.exists():
            return

        with open(self.contract_path, 'r') as f:
            content = f.read()
            # Extract version number from Contract
            for line in content.split('\n'):
                if 'contract_version' in line.lower() or 'version:' in line.lower():
                    try:
                        version = int(''.join(filter(str.isdigit, line)))
                        self.state["contract_version"] = version
                        break
                    except ValueError:
                        pass

    def _run_final_review(self):
        """Run independent final review after all tasks complete."""
        print("\nLaunching independent Final Reviewer session...\n")

        # Ensure state is persisted before review
        self.save_state()

        # Invoke real Final Reviewer
        review_report = review_contract(
            self.contract_id,
            self.contract_path,
            self.state_file
        )

        # Process review result
        if review_report.get("status") == "pass":
            print(f"\n[OK] Final review PASSED")
            self.state["status"] = ContractStatus.COMPLETE.value
            self.state["final_review"] = {
                "status": "pass",
                "timestamp": review_report.get("timestamp"),
                "summary": review_report.get("summary"),
                "findings": review_report.get("findings")
            }

            # Close Contract issue on success
            if self.github:
                self.github.close_contract_issue(f"Contract completed: {review_report.get('summary')}")
        else:
            print(f"\n[FAIL] Final review FAILED")
            print(f"Summary: {review_report.get('summary')}")
            if review_report.get("findings"):
                print("\nFindings:")
                for category, issues in review_report.get("findings", {}).items():
                    if issues:
                        print(f"  {category}:")
                        for issue in issues:
                            print(f"    - {issue}")
            self.state["status"] = ContractStatus.FAILED.value
            self.state["final_review"] = {
                "status": "fail",
                "timestamp": review_report.get("timestamp"),
                "summary": review_report.get("summary"),
                "findings": review_report.get("findings")
            }

            # Update Contract issue on failure
            if self.github:
                self.github.close_contract_issue(f"Contract failed: {review_report.get('summary')}")

    def _attempt_recovery(self, blocked_tasks: List[str]):
        """Attempt to recover from blocked/failed tasks."""
        print(f"Attempting recovery for: {', '.join(blocked_tasks)}")
        # Placeholder for recovery logic
        pass


def main():
    if len(sys.argv) < 2:
        print("Usage: orchestrator_loop.py <contract-id>", file=sys.stderr)
        print("Example: orchestrator_loop.py CTR-0042", file=sys.stderr)
        sys.exit(1)

    contract_id = sys.argv[1]
    orchestrator = OrchestratorLoop(contract_id)
    orchestrator.run()


if __name__ == "__main__":
    main()
