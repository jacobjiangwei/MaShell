"""Universal shell tool for command execution."""

import asyncio
from typing import Any

from mashell.tools.base import BaseTool, ToolResult


class ShellTool(BaseTool):
    """Shell tool for executing commands (not for file reading)."""

    name = "shell"
    description = """Execute a shell command.

## ⚠️ IMPORTANT: Use the RIGHT Tool
- To READ files → use `read_file` (faster, no permission needed)
- To LIST directories → use `list_dir` (faster, no permission needed)
- To SEARCH in files → use `search_files` (faster, no permission needed)
- To WRITE files → use `write_file` (cleaner)

## When to Use Shell
- Run programs: `python script.py`, `node app.js`, `cargo run`
- Install packages: `pip install pkg`, `npm install`, `brew install tool`
- Git operations: `git status`, `git diff`, `git commit -m "msg"`
- Build/compile: `make`, `npm run build`, `cargo build`
- Network: `curl`, `wget`, `ssh`
- System: `ps`, `top`, `df -h`
- Any command that DOES something (not just reads)

## Best Practices
1. Run ONE simple command at a time
2. Avoid using cat/ls/grep - use native tools instead
3. Limit output: `| head -10` if needed
4. Prefer simple commands over complex pipelines

## Examples
✅ Good: `python main.py`
✅ Good: `git status`
✅ Good: `pip install requests`
❌ Don't: `cat file.txt` → use read_file instead
❌ Don't: `ls -la` → use list_dir instead
❌ Don't: `grep pattern .` → use search_files instead"""

    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute"},
            "working_dir": {
                "type": "string",
                "description": "Working directory for the command (optional)",
            },
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 120)"},
        },
        "required": ["command"],
    }

    requires_permission = True
    permission_level = "always_ask"

    async def execute(
        self,
        command: str,
        working_dir: str | None = None,
        timeout: int = 120,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a shell command."""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            output = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace") if stderr else ""

            # Combine stdout and stderr for full picture
            full_output = output
            if err:
                full_output += f"\n[stderr]:\n{err}"

            # Truncate very long output
            full_output = self._truncate_output(full_output)

            return ToolResult(
                success=process.returncode == 0,
                output=full_output,
                error=err if process.returncode != 0 else None,
            )

        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )

    def _truncate_output(self, output: str, max_lines: int = 200, max_chars: int = 10000) -> str:
        """Truncate long output while preserving useful information."""
        if len(output) <= max_chars:
            lines = output.split("\n")
            if len(lines) <= max_lines:
                return output

        lines = output.split("\n")
        total_lines = len(lines)

        if total_lines <= max_lines:
            # Just char limit exceeded
            return output[:max_chars] + f"\n\n[Output truncated: {len(output)} chars total]"

        # Keep first and last portions
        keep_lines = max_lines // 2
        first_part = "\n".join(lines[:keep_lines])
        last_part = "\n".join(lines[-keep_lines:])

        return f"{first_part}\n\n[... {total_lines - max_lines} lines omitted ...]\n\n{last_part}"
