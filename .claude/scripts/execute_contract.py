#!/usr/bin/env python3
"""
Execute Contract — Entry point for Contract-driven orchestration.

Usage:
    execute_contract.py <contract-id>

This script:
1. Validates the Contract exists and is approved
2. Initializes execution state
3. Generates task plan if needed
4. Enters the orchestration loop
"""

import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

# Import orchestration components
try:
    from orchestrator_loop import OrchestratorLoop
    from orchestrator_task_planner import TaskPlanner
except ImportError:
    # Add current script dir to path
    sys.path.insert(0, str(Path(__file__).parent))
    from orchestrator_loop import OrchestratorLoop
    from orchestrator_task_planner import TaskPlanner


def find_contract(contract_id: str) -> Optional[Path]:
    """Find Contract file by ID."""
    concepts_dir = Path(".claude/concepts")

    # Try exact match
    exact_match = concepts_dir / f"{contract_id}.md"
    if exact_match.exists():
        return exact_match

    # Try pattern matching
    for pattern in [f"*{contract_id}*.md", f"*-{contract_id}*.md"]:
        matches = list(concepts_dir.glob(pattern))
        if matches:
            return matches[0]

    # Try to find any contract and search by ID within it
    for contract_file in concepts_dir.glob("*.md"):
        with open(contract_file, 'r') as f:
            content = f.read()
            if contract_id in content:
                return contract_file

    return None


def validate_contract(contract_path: Path) -> bool:
    """Validate that Contract exists and is approved."""
    if not contract_path.exists():
        print(f"ERROR: Contract not found: {contract_path}")
        return False

    with open(contract_path, 'r') as f:
        content = f.read()

        # Check for approval marker
        if "Status: approved" not in content and "status: approved" not in content.lower():
            print(f"ERROR: Contract is not approved: {contract_path}")
            print("Approve the Contract in /design-first before executing")
            return False

        # Check for basic structure
        if "# Concept Contract" not in content and "Concept Contract" not in content:
            print(f"WARNING: Contract may not be a valid Concept Contract: {contract_path}")

    return True


def check_existing_execution(contract_id: str) -> bool:
    """Check if execution is already in progress."""
    state_file = Path(f".claude/orchestrator/state/{contract_id}/state.yaml")

    if state_file.exists():
        with open(state_file, 'r') as f:
            state = yaml.safe_load(f) or {}

        status = state.get("status")
        print(f"Execution already in progress: {status}")
        print(f"State file: {state_file}")

        # Offer to resume
        response = input("Resume execution? (yes/no): ").strip().lower()
        return response == "yes" or response == "y"

    return True


def generate_task_map_if_needed(contract_id: str, contract_path: Path) -> Path:
    """Generate task map if it doesn't exist."""
    task_map_file = Path(f".claude/orchestrator/plans/{contract_id}/task-map.yaml")

    if task_map_file.exists():
        print(f"[OK] Task map exists: {task_map_file}")
        return task_map_file

    print("\nGenerating task map from Contract...")
    planner = TaskPlanner(contract_path)

    # Plan tasks
    tasks = planner.plan_tasks()
    if not tasks:
        print("WARNING: No tasks found in Contract")
        print("Contract may not have a 'Task Decomposition' section")

    # Validate DAG
    if not planner.validate_dag():
        print("ERROR: Task DAG validation failed")
        return None

    # Generate and save task map
    task_map_file.parent.mkdir(parents=True, exist_ok=True)
    task_map = planner.to_yaml()

    with open(task_map_file, 'w') as f:
        yaml.dump(task_map, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Task map saved: {task_map_file}")
    return task_map_file


def main():
    if len(sys.argv) < 2:
        print("Usage: execute_contract.py <contract-id>")
        print("Example: execute_contract.py CTR-0042")
        sys.exit(1)

    contract_id = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"Contract Execution Initialization")
    print(f"Contract ID: {contract_id}")
    print(f"{'='*60}\n")

    # Step 1: Find Contract
    print(f"1. Finding Contract: {contract_id}")
    contract_path = find_contract(contract_id)
    if not contract_path:
        print(f"ERROR: Could not find Contract for ID: {contract_id}")
        print(f"Search locations: .claude/concepts/")
        sys.exit(1)

    print(f"   Found: {contract_path}")

    # Step 2: Validate Contract
    print(f"\n2. Validating Contract")
    if not validate_contract(contract_path):
        sys.exit(1)

    print(f"   [OK] Contract is valid and approved")

    # Step 3: Check for existing execution
    print(f"\n3. Checking for existing execution")
    if not check_existing_execution(contract_id):
        print("Execution cancelled")
        sys.exit(0)

    # Step 4: Generate task map if needed
    print(f"\n4. Preparing task plan")
    task_map_file = generate_task_map_if_needed(contract_id, contract_path)
    if not task_map_file:
        print("ERROR: Could not generate task map")
        sys.exit(1)

    # Step 5: Enter orchestrator loop
    print(f"\n5. Starting orchestrator loop\n")
    orchestrator = OrchestratorLoop(contract_id)
    orchestrator.run()


if __name__ == "__main__":
    main()
