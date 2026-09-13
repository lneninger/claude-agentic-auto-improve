#!/usr/bin/env python3
"""
Task Planner — generates task DAG from Contract specification.

Reads a Contract file and produces:
- task-map.yaml with task dependencies, scope, acceptance criteria
- Validates Contract structure
- Identifies parallelizable tasks
- Maps resources/conflicts
"""

import sys
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Set
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class Task:
    """Represents a single task in the Contract."""
    id: str
    title: str
    description: str = ""
    priority: str = "normal"  # normal | high | critical
    dependencies: List[str] = None
    parallelizable_with: List[str] = None

    scope_allowed: List[str] = None
    scope_forbidden: List[str] = None

    acceptance_criteria: List[str] = None
    tests: List[str] = None

    resources_files: List[str] = None
    resources_dirs: List[str] = None
    resources_architectural: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.parallelizable_with is None:
            self.parallelizable_with = []
        if self.scope_allowed is None:
            self.scope_allowed = []
        if self.scope_forbidden is None:
            self.scope_forbidden = []
        if self.acceptance_criteria is None:
            self.acceptance_criteria = []
        if self.tests is None:
            self.tests = []
        if self.resources_files is None:
            self.resources_files = []
        if self.resources_dirs is None:
            self.resources_dirs = []
        if self.resources_architectural is None:
            self.resources_architectural = []


class TaskPlanner:
    """Generates task DAG from Contract."""

    def __init__(self, contract_path: Path):
        self.contract_path = Path(contract_path)
        self.contract_data = self._load_contract()
        self.tasks: Dict[str, Task] = {}

    def _load_contract(self) -> Dict[str, Any]:
        """Load and parse Contract markdown file."""
        if not self.contract_path.exists():
            print(f"ERROR: Contract not found: {self.contract_path}", file=sys.stderr)
            sys.exit(1)

        # For now, return a placeholder
        # A real implementation would parse the markdown Contract
        return {
            "contract_id": self.contract_path.stem,
            "version": 1,
            "title": "Contract",
            "task_decomposition": []
        }

    def plan_tasks(self) -> Dict[str, Task]:
        """
        Parse Contract and generate task plan.

        Returns a dictionary of Task objects keyed by task ID.
        """
        # This is a placeholder implementation
        # A real implementation would:
        # 1. Parse Contract.md "Implementation Strategy" and "Task Decomposition" sections
        # 2. Extract task titles, dependencies, scope, acceptance criteria
        # 3. Build dependency graph
        # 4. Identify parallelizable groups
        # 5. Validate conflicts

        print(f"Planning tasks from Contract: {self.contract_path.name}")

        # Return empty for now; real implementation fills this
        return self.tasks

    def validate_dag(self) -> bool:
        """
        Validate the task DAG for cycles and conflicts.

        Returns True if valid, False otherwise.
        """
        if not self._check_cycles():
            print("ERROR: Circular dependency detected in task DAG", file=sys.stderr)
            return False

        if not self._check_resource_conflicts():
            print("WARNING: Potential resource conflicts detected", file=sys.stderr)
            # Don't fail on warnings; user should review

        return True

    def _check_cycles(self) -> bool:
        """Check for circular dependencies."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = self.tasks.get(task_id)
            if task:
                for dep in task.dependencies:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if has_cycle(task_id):
                    return False

        return True

    def _check_resource_conflicts(self) -> bool:
        """Check for resource conflicts between supposedly parallel tasks."""
        # This is a placeholder
        # Real implementation would check file/dir conflicts
        return True

    def identify_parallel_groups(self) -> List[List[str]]:
        """
        Identify tasks that can run in parallel.

        Returns a list of task groups where tasks in each group can run concurrently.
        """
        # Placeholder
        groups = []
        for task_id in self.tasks:
            groups.append([task_id])
        return groups

    def to_yaml(self) -> Dict[str, Any]:
        """Convert task plan to YAML-serializable format."""
        return {
            "contract_id": self.contract_data.get("contract_id", ""),
            "contract_version": self.contract_data.get("version", 1),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "tasks": [
                {
                    "id": task_id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "dependencies": task.dependencies,
                    "parallelizable_with": task.parallelizable_with,
                    "scope": {
                        "allowed": task.scope_allowed,
                        "forbidden": task.scope_forbidden,
                    },
                    "acceptance_criteria": task.acceptance_criteria,
                    "tests": task.tests,
                    "resources": {
                        "files": task.resources_files,
                        "directories": task.resources_dirs,
                        "architectural": task.resources_architectural,
                    }
                }
                for task_id, task in self.tasks.items()
            ]
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: orchestrator_task_planner.py <contract-path>", file=sys.stderr)
        sys.exit(1)

    contract_path = Path(sys.argv[1])
    planner = TaskPlanner(contract_path)

    # Plan tasks
    tasks = planner.plan_tasks()
    print(f"Planned {len(tasks)} tasks")

    # Validate DAG
    if not planner.validate_dag():
        sys.exit(1)

    # Output task map
    task_map = planner.to_yaml()
    print(json.dumps(task_map, indent=2))


if __name__ == "__main__":
    main()
