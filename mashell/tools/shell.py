"""Universal shell tool for command execution."""

import asyncio
from typing import Any

from mashell.tools.base import BaseTool, ToolResult


class ShellTool(BaseTool):
    """Universal shell tool - executes any command."""
    
    name = "shell"
    description = """Execute a shell command. This is your primary tool for ALL operations.

## When to Use
- Read files: `cat file.txt`, `head -n 20 file.txt`, `tail -f log.txt`
- Write files: `echo 'content' > file.txt`, `cat << 'EOF' > file.txt`
- List/find: `ls -la`, `find . -name "*.py"`, `tree`
- Search: `grep -r "pattern" .`, `rg "pattern"`
- Run programs: `python script.py`, `node app.js`
- Install: `pip install pkg`, `brew install tool`
- Git: `git status`, `git diff`, `git commit -m "msg"`
- Any other shell command

## Best Practices
1. Run ONE simple command at a time
2. Use human-readable flags: `ls -lh` (not raw bytes)
3. Limit output: `head -20`, `| head -10`
4. Suppress errors when exploring: `2>/dev/null`
5. Prefer simple commands over complex pipelines

## Examples
✅ Good: `ls -lhS ~/Downloads/*.mp4 | head -10`
✅ Good: `find ~/Movies -name "*.mp4" -type f`
✅ Good: `du -sh ~/Documents/*`
❌ Avoid: Long pipelines with xargs, awk, complex logic"""
    
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
