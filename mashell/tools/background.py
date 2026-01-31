"""Background task management tools."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from mashell.tools.base import BaseTool, ToolResult


@dataclass
class BackgroundTask:
    """A background task."""

    id: str
    process: asyncio.subprocess.Process
    command: str
    output_buffer: list[str] = field(default_factory=list)

    @property
    def is_running(self) -> bool:
        """Check if the task is still running."""
        return self.process.returncode is None


class BackgroundTaskManager:
    """Manages long-running background tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._task_counter = 0

    async def start(self, command: str, working_dir: str | None = None) -> str:
        """Start a background task and return its ID."""
        self._task_counter += 1
        task_id = f"bg_{self._task_counter}"

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=working_dir,
        )

        task = BackgroundTask(
            id=task_id,
            process=process,
            command=command,
        )
        self._tasks[task_id] = task

        # Start output collector
        asyncio.create_task(self._collect_output(task_id))

        return task_id

    async def get_output(self, task_id: str, wait: bool = False, tail: int = 50) -> str:
        """Get output from a background task."""
        task = self._tasks.get(task_id)
        if not task:
            return f"Task {task_id} not found"

        if wait:
            await task.process.wait()

        # Return last N lines
        lines = task.output_buffer[-tail:] if len(task.output_buffer) > tail else task.output_buffer
        output = "\n".join(lines)

        status = "running" if task.is_running else f"exited (code {task.process.returncode})"
        return f"[Task {task_id}: {status}]\n{output}"

    async def stop(self, task_id: str) -> str:
        """Stop a background task."""
        task = self._tasks.get(task_id)
        if not task:
            return f"Task {task_id} not found"

        if task.is_running:
            task.process.terminate()
            try:
                await asyncio.wait_for(task.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                task.process.kill()
            return f"Task {task_id} stopped"
        else:
            return f"Task {task_id} already finished"

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all tasks."""
        return [
            {
                "id": task.id,
                "command": task.command,
                "running": task.is_running,
                "output_lines": len(task.output_buffer),
            }
            for task in self._tasks.values()
        ]

    async def _collect_output(self, task_id: str) -> None:
        """Collect output from a task's stdout."""
        task = self._tasks.get(task_id)
        if not task or not task.process.stdout:
            return

        try:
            async for line in task.process.stdout:
                task.output_buffer.append(line.decode("utf-8", errors="replace").rstrip())
                # Keep buffer manageable
                if len(task.output_buffer) > 1000:
                    task.output_buffer = task.output_buffer[-500:]
        except Exception:
            pass


class RunBackgroundTool(BaseTool):
    """Tool to start a long-running command in the background."""

    name = "run_background"
    description = """Start a long-running command in the background.

## When to Use
- Starting a dev server: `npm run dev`, `python -m http.server`
- Watch mode builds: `npm run watch`, `tsc --watch`
- Long-running processes: `tail -f /var/log/system.log`
- Any command that doesn't exit quickly

## How It Works
1. The command runs in background
2. Returns a task ID (e.g., "bg_1")
3. Use `check_background` with the task ID to see output

## Example
1. Start server: `run_background("npm run dev")`  → returns "bg_1"
2. Check output: `check_background("bg_1")` → shows server logs"""

    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to run in background"},
            "working_dir": {
                "type": "string",
                "description": "Working directory for the command (optional)",
            },
        },
        "required": ["command"],
    }

    requires_permission = True
    permission_level = "always_ask"

    def __init__(self, manager: BackgroundTaskManager) -> None:
        self.manager = manager

    async def execute(
        self,
        command: str,
        working_dir: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Start a background task."""
        task_id = await self.manager.start(command, working_dir)

        # Wait a moment to capture initial output
        await asyncio.sleep(0.5)
        initial_output = await self.manager.get_output(task_id, tail=10)

        return ToolResult(
            success=True,
            output=f"Started background task: {task_id}\n\n{initial_output}",
        )


class CheckBackgroundTool(BaseTool):
    """Tool to check output of a background task."""

    name = "check_background"
    description = """Check output and status of a background task.

## When to Use
- Check if a server started successfully
- View logs from a background process
- Wait for a long command to finish

## Parameters
- `task_id`: The ID returned by run_background (e.g., "bg_1")
- `wait`: If true, waits for the task to complete
- `tail`: Number of lines to show (default: 50)

## Example
`check_background("bg_1")` → Shows recent output and status"""

    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "The ID of the background task"},
            "wait": {
                "type": "boolean",
                "description": "Wait for task to complete (default: false)",
            },
            "tail": {
                "type": "integer",
                "description": "Number of output lines to return (default: 50)",
            },
        },
        "required": ["task_id"],
    }

    requires_permission = False  # Reading output doesn't need permission

    def __init__(self, manager: BackgroundTaskManager) -> None:
        self.manager = manager

    async def execute(
        self,
        task_id: str,
        wait: bool = False,
        tail: int = 50,
        **kwargs: Any,
    ) -> ToolResult:
        """Check a background task."""
        output = await self.manager.get_output(task_id, wait=wait, tail=tail)
        return ToolResult(success=True, output=output)
