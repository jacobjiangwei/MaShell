"""Permission prompt UI."""

import asyncio
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    from mashell.permissions.manager import PermissionRequest, PermissionResult


class PermissionUI:
    """UI for permission prompts."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    async def prompt(self, request: "PermissionRequest") -> "PermissionResult":
        """Display permission prompt and get user response."""
        from mashell.permissions.manager import PermissionResult

        self.console.print()

        # Format the action details
        details = self._format_request(request)

        # Display permission box
        self.console.print(
            Panel(
                details,
                title="🔐 Permission Request",
                border_style="yellow",
                padding=(1, 2),
            )
        )

        # Get user input
        self.console.print(
            "  [bold][y][/bold] Approve  "
            "[bold][n][/bold] Deny  "
            "[bold][e][/bold] Edit  "
            "[bold][a][/bold] Always approve this session"
        )

        choice = await self._get_input("Choice [y/n/e/a]: ")
        choice = choice.strip().lower()

        if choice == "y":
            return PermissionResult(approved=True)
        elif choice == "n":
            return PermissionResult(approved=False)
        elif choice == "a":
            return PermissionResult(approved=True, remember=True)
        elif choice == "e":
            modified = await self._edit_command(request.arguments)
            if modified:
                return PermissionResult(approved=True, modified_args=modified)
            else:
                return PermissionResult(approved=False)
        else:
            # Default to deny for safety
            self.console.print("[dim]Invalid choice, denying.[/dim]")
            return PermissionResult(approved=False)

    def _format_request(self, request: "PermissionRequest") -> str:
        """Format the permission request for display."""
        lines = [
            f"[bold]Tool:[/bold] {request.tool_name}",
        ]

        if "command" in request.arguments:
            cmd = request.arguments["command"]
            lines.append("\n[bold]Command:[/bold]")
            lines.append(f"[cyan]$ {cmd}[/cyan]")
        else:
            lines.append("\n[bold]Arguments:[/bold]")
            for key, value in request.arguments.items():
                lines.append(f"  {key}: {value}")

        if request.arguments.get("working_dir"):
            lines.append(f"\n[bold]Directory:[/bold] {request.arguments['working_dir']}")

        return "\n".join(lines)

    async def _get_input(self, prompt: str) -> str:
        """Get input from user."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt))

    async def _edit_command(self, args: dict[str, Any]) -> dict[str, Any] | None:
        """Let user edit the command."""
        if "command" not in args:
            self.console.print("[red]Cannot edit: no command in arguments[/red]")
            return None

        self.console.print("\n[bold]Edit command:[/bold]")
        self.console.print(f"[dim]Original: {args['command']}[/dim]")

        new_command = await self._get_input("New command: ")
        new_command = new_command.strip()

        if not new_command:
            self.console.print("[dim]Empty command, cancelling.[/dim]")
            return None

        new_args = args.copy()
        new_args["command"] = new_command
        return new_args
