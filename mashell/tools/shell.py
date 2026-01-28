"""Universal shell tool for command execution."""

import asyncio
from typing import Any

from mashell.tools.base import BaseTool, ToolResult


class ShellTool(BaseTool):
    """
    Universal shell tool - executes any command.
    
    AI uses appropriate commands for different tasks:
    - Read file: cat, head, tail
    - Write file: echo > , cat >, tee
    - Edit file: sed, awk, or write full content
    - List dir: ls, find, tree
    - Search: grep, find, rg (ripgrep)
    - Install: pip, npm, brew, apt
    - Any other shell command
    """
    
    name = "shell"
    description = """Execute any shell command. Use this for all operations:
- Read files: cat file.txt, head -n 20 file.txt
- Write files: echo 'content' > file.txt, cat << 'EOF' > file.txt ... EOF
- List directories: ls -la, find . -name "*.py", tree
- Search content: grep -r "pattern" ., rg "pattern"
- Run programs: python script.py, node app.js, npm start
- Install tools: pip install package, brew install tool
- Git operations: git status, git diff, git commit
- Any other shell operation the task requires"""
    
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute"
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for the command (optional)"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 120)"
            }
        },
        "required": ["command"]
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
        
        return (
            f"{first_part}\n\n"
            f"[... {total_lines - max_lines} lines omitted ...]\n\n"
            f"{last_part}"
        )
