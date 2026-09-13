#!/usr/bin/env python3
"""
Task Execution Packet Generator — creates minimal context for task executor.

Generates a YAML packet containing only the information needed for a task
executor to implement a single task, minimizing token consumption and context
bloat.
"""

import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class TaskExecutionPacketGenerator:
    """Generates task execution packets."""

    def __init__(self, contract_id: str, task_id: str, contract_path: Path, task_map_path: Path):
        self.contract_id = contract_id
        self.task_id = task_id
        self.contract_path = Path(contract_path)
        self.task_map_path = Path(task_map_path)

        self.contract_data = self._load_contract()
        self.task_map_data = self._load_task_map()
        self.task_data = self._find_task()

    def _load_contract(self) -> Dict[str, Any]:
        """Load Contract file."""
        if not self.contract_path.exists():
            raise FileNotFoundError(f"Contract not found: {self.contract_path}")

        with open(self.contract_path, 'r') as f:
            # Real implementation would parse markdown Contract
            return {
                "contract_id": self.contract_id,
                "title": "Contract",
                "objective": "Implement feature",
                "architecture": {}
            }

    def _load_task_map(self) -> Dict[str, Any]:
        """Load task map/DAG."""
        if not self.task_map_path.exists():
            raise FileNotFoundError(f"Task map not found: {self.task_map_path}")

        with open(self.task_map_path, 'r') as f:
            return yaml.safe_load(f) or {}

    def _find_task(self) -> Optional[Dict[str, Any]]:
        """Find task in task map."""
        for task in self.task_map_data.get("tasks", []):
            if task.get("id") == self.task_id:
                return task
        return None

    def generate_packet(self) -> Dict[str, Any]:
        """Generate execution packet for this task."""
        if not self.task_data:
            raise ValueError(f"Task not found in map: {self.task_id}")

        packet = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "execution_metadata": {
                "contract_id": self.contract_id,
                "contract_version": self.task_map_data.get("contract_version", 1),
                "task_id": self.task_id,
                "task_title": self.task_data.get("title", ""),
            },
            "contract_objective": self.contract_data.get("objective", ""),
            "task_description": self.task_data.get("description", ""),

            "relevant_requirements": self.task_data.get("acceptance_criteria", []),

            "relevant_architecture_decisions": self._extract_relevant_architecture(),

            "accepted_scope": {
                "allowed": self.task_data.get("scope", {}).get("allowed", []),
                "forbidden": self.task_data.get("scope", {}).get("forbidden", []),
            },

            "completed_dependencies": self._get_completed_dependencies(),

            "tests_required": self.task_data.get("tests", []),

            "acceptance_criteria": self.task_data.get("acceptance_criteria", []),

            "completion_checklist": [
                "Tests written and passing",
                "Code reviewed internally for scope compliance",
                f"Commit created with message: {self.contract_id} {self.task_id}: {self.task_data.get('title', '')}",
                f"Result file written to: .claude/orchestrator/results/{self.contract_id}/{self.task_id}.yaml"
            ],

            "resources": self.task_data.get("resources", {}),

            "git_info": {
                "branch": f"task/{self.contract_id}-{self.task_id}",
                "base_branch": f"contract/{self.contract_id}",
            }
        }

        return packet

    def _extract_relevant_architecture(self) -> List[str]:
        """Extract architecture decisions relevant to this task."""
        # Placeholder; real implementation would map task resources to arch decisions
        resources = self.task_data.get("resources", {})
        architectural = resources.get("architectural", [])
        return architectural

    def _get_completed_dependencies(self) -> List[Dict[str, Any]]:
        """Get information about completed dependencies."""
        dependencies = self.task_data.get("dependencies", [])
        if not dependencies:
            return []

        results = []
        results_dir = Path(f".claude/orchestrator/results/{self.contract_id}")

        for dep_id in dependencies:
            result_file = results_dir / f"{dep_id}.yaml"
            if result_file.exists():
                with open(result_file, 'r') as f:
                    dep_result = yaml.safe_load(f) or {}
                results.append({
                    "task_id": dep_id,
                    "status": dep_result.get("status", "unknown"),
                    "commit": dep_result.get("commit", {}).get("hash"),
                })

        return results


def main():
    if len(sys.argv) < 5:
        print("Usage: generate_task_execution_packet.py <contract-id> <task-id> <contract-path> <task-map-path>",
              file=sys.stderr)
        print("Example: generate_task_execution_packet.py CTR-0042 TASK-001 \\")
        print("  .claude/concepts/2026-09-09-feature.md \\")
        print("  .claude/orchestrator/plans/CTR-0042/task-map.yaml", file=sys.stderr)
        sys.exit(1)

    contract_id = sys.argv[1]
    task_id = sys.argv[2]
    contract_path = sys.argv[3]
    task_map_path = sys.argv[4]

    generator = TaskExecutionPacketGenerator(contract_id, task_id, contract_path, task_map_path)
    packet = generator.generate_packet()

    # Output as YAML
    print(yaml.dump(packet, default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    main()
