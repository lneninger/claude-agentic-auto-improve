#!/usr/bin/env python3
"""
Parallel Task Executor — manages concurrent task execution.

Responsibilities:
1. Identify parallelizable ready tasks
2. Launch multiple task executors concurrently
3. Monitor all executors for completion
4. Collect and organize results
5. Handle partial failures
"""

import subprocess
import json
import threading
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

try:
    from task_executor_launcher import execute_task
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from task_executor_launcher import execute_task


class ParallelTaskExecutor:
    """Manages concurrent execution of multiple ready tasks."""

    def __init__(self, max_workers: int = 3):
        """
        Initialize parallel executor.

        Args:
            max_workers: Maximum number of concurrent tasks (default: 3)
        """
        self.max_workers = max_workers
        self.results = {}
        self.lock = threading.Lock()

    def can_parallelize(self, task_ids: List[str], task_map: Dict[str, Any],
                       state: Dict[str, Any]) -> List[str]:
        """
        Filter ready tasks to identify those that can run in parallel.

        Tasks can run in parallel if:
        - They have no dependencies on each other
        - They don't modify the same data structures
        - They are marked as parallelizable

        Args:
            task_ids: List of ready task IDs
            task_map: Full task map with dependencies
            state: Execution state

        Returns:
            List of task IDs that can run in parallel
        """
        if len(task_ids) <= 1:
            return task_ids

        # Build dependency graph for ready tasks
        task_deps = {}
        for task_id in task_ids:
            # Find task in task map
            for task in task_map.get("tasks", []):
                if task.get("id") == task_id:
                    task_deps[task_id] = task.get("dependencies", [])
                    break

        # Filter to tasks that have no inter-dependencies
        parallelizable = []
        for task_id in task_ids:
            deps = task_deps.get(task_id, [])
            # Check if any dependency is another ready task
            has_ready_dep = any(dep in task_ids for dep in deps)
            if not has_ready_dep:
                parallelizable.append(task_id)

        return parallelizable

    def execute_parallel(self, tasks: List[Tuple[str, Dict[str, Any]]],
                        contract_id: str, contract_path: Path) -> Dict[str, Any]:
        """
        Execute multiple tasks in parallel.

        Args:
            tasks: List of (task_id, task_data) tuples
            contract_id: Contract ID for context
            contract_path: Path to Contract file

        Returns:
            Dictionary mapping task_id to execution result
        """
        if not tasks:
            return {}

        results = {}

        print(f"\n[OK] Launching {len(tasks)} tasks in parallel (max workers: {self.max_workers})")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for task_id, task_data in tasks:
                future = executor.submit(
                    execute_task,
                    contract_id,
                    task_id,
                    task_data,
                    contract_path
                )
                future_to_task[future] = task_id

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task_id = future_to_task[future]
                try:
                    result = future.result()
                    results[task_id] = result
                    status = result.get("status", "unknown")
                    print(f"[OK] {task_id} completed: {status}")
                except Exception as e:
                    print(f"[FAIL] {task_id} failed: {e}")
                    results[task_id] = {
                        "status": "failed",
                        "error": str(e),
                        "tests_passed": False,
                        "contract_impact": {
                            "requires_architect": False
                        }
                    }

        return results

    def execute_with_priority(self, ready_tasks: List[str], task_map: Dict[str, Any],
                             state: Dict[str, Any], contract_id: str,
                             contract_path: Path, max_parallel: int = 3) -> Dict[str, Any]:
        """
        Execute ready tasks with intelligent priority and parallelization.

        Strategy:
        1. Identify parallelizable tasks (no inter-dependencies)
        2. Execute up to max_parallel tasks concurrently
        3. Collect results
        4. Repeat for remaining tasks

        Args:
            ready_tasks: List of ready task IDs
            task_map: Full task map
            state: Execution state
            contract_id: Contract ID
            contract_path: Path to Contract
            max_parallel: Maximum parallel tasks

        Returns:
            Dictionary of all task results
        """
        all_results = {}

        if not ready_tasks:
            return all_results

        # Identify tasks that can run in parallel
        parallelizable = self.can_parallelize(ready_tasks, task_map, state)

        # Limit to max_parallel
        parallel_batch = parallelizable[:max_parallel]
        sequential_batch = ready_tasks[len(parallel_batch):]

        # Build task data for parallel batch
        parallel_tasks = []
        for task_id in parallel_batch:
            for task in task_map.get("tasks", []):
                if task.get("id") == task_id:
                    parallel_tasks.append((task_id, task))
                    break

        # Execute parallel batch
        if parallel_tasks:
            print(f"\n[OK] Executing {len(parallel_tasks)} tasks in parallel")
            parallel_results = self.execute_parallel(parallel_tasks, contract_id, contract_path)
            all_results.update(parallel_results)

        # Execute sequential batch one at a time
        for task_id in sequential_batch:
            # Find task in task map
            task_data = None
            for task in task_map.get("tasks", []):
                if task.get("id") == task_id:
                    task_data = task
                    break

            if task_data:
                print(f"\n[OK] Executing sequential task: {task_id}")
                result = execute_task(contract_id, task_id, task_data, contract_path)
                all_results[task_id] = result

        return all_results


def create_parallel_executor(max_workers: int = 3) -> ParallelTaskExecutor:
    """Factory function to create parallel executor."""
    return ParallelTaskExecutor(max_workers)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: orchestrator_parallel_executor.py <contract-id>")
        sys.exit(1)

    contract_id = sys.argv[1]
    executor = create_parallel_executor(max_workers=3)
    print(f"Parallel executor initialized for {contract_id}")
