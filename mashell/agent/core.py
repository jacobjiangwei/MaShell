"""Core agent implementation."""


from rich.console import Console
from rich.status import Status

from mashell.agent.context import ContextManager
from mashell.agent.prompt import get_system_prompt
from mashell.config import Config
from mashell.permissions import PermissionManager, PermissionRequest
from mashell.providers import create_provider
from mashell.providers.base import BaseProvider, Message, ToolCall
from mashell.tools import create_tool_registry
from mashell.tools.base import ToolRegistry, ToolResult


class Agent:
    """The main MaShell agent."""

    def __init__(self, config: Config, console: Console | None = None) -> None:
        self.config = config
        self.console = console or Console()

        # Create provider
        self.provider: BaseProvider = create_provider(
            config.provider.provider,
            config.provider.url,
            config.provider.key,
            config.provider.model,
        )

        # Create tools
        self.tools: ToolRegistry = create_tool_registry()

        # Create permission manager
        self.permissions = PermissionManager(
            config.permissions,
            config.auto_approve_all,
        )

        # Create context manager
        self.context = ContextManager()

        # Verbose mode
        self.verbose = config.verbose

        # Loading spinner
        self._spinner: Status | None = None

    def _start_thinking(self) -> None:
        """Show thinking indicator."""
        if self._spinner is None:
            self._spinner = self.console.status(
                "[bold cyan]🤔 Thinking...[/bold cyan]", spinner="dots"
            )
            self._spinner.start()

    def _stop_thinking(self) -> None:
        """Hide thinking indicator."""
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None

    async def run(self, user_input: str) -> str | None:
        """Run the agent with user input."""

        # Build messages
        messages = self._build_messages(user_input)

        # Add user message to context
        self.context.add_message(Message(role="user", content=user_input))

        # Run agent loop
        iteration = 0
        max_iterations = 20  # Safety limit

        while iteration < max_iterations:
            iteration += 1

            if self.verbose:
                self._stop_thinking()
                self.console.print(f"[dim]Iteration {iteration}...[/dim]")

            try:
                # Show thinking indicator while waiting for LLM
                self._start_thinking()

                # Get LLM response
                response = await self.provider.chat(
                    messages,
                    tools=self.tools.all_schemas(),
                )

                # Stop thinking indicator
                self._stop_thinking()

                if self.verbose:
                    self.console.print(f"[dim]Finish reason: {response.finish_reason}[/dim]")
                    if response.usage:
                        self.console.print(f"[dim]Tokens: {response.usage}[/dim]")

                # If no tool calls, we're done
                if not response.tool_calls:
                    if response.content:
                        self.console.print()
                        self.console.print(
                            f"[bold green]MaShell:[/bold green] {response.content}"
                        )
                        self.context.add_message(
                            Message(role="assistant", content=response.content)
                        )
                    return response.content

                # Add assistant message with tool calls
                assistant_msg = Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
                messages.append(assistant_msg)
                self.context.add_message(assistant_msg)

                # Show thinking if any
                if response.content:
                    self.console.print()
                    self.console.print(f"[bold cyan]💭[/bold cyan] {response.content}")

                # Execute tool calls
                for tool_call in response.tool_calls:
                    result = await self._execute_tool(tool_call)

                    # Add tool result
                    tool_msg = Message(
                        role="tool",
                        content=result.output if result.success else f"Error: {result.error}",
                        tool_call_id=tool_call.id,
                    )
                    messages.append(tool_msg)
                    self.context.add_message(tool_msg)

            except Exception as e:
                self._stop_thinking()
                self.console.print(f"[red]Error: {e}[/red]")
                if self.verbose:
                    import traceback
                    self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
                return None

        self._stop_thinking()
        self.console.print("[yellow]Reached maximum iterations[/yellow]")
        return None

    def _build_messages(self, user_input: str) -> list[Message]:
        """Build the message list for the LLM."""
        messages: list[Message] = []

        # System prompt
        system_prompt = get_system_prompt(self.config.working_dir)
        messages.append(Message(role="system", content=system_prompt))

        # Get context messages (includes any compressed history)
        context_messages = self.context.get_messages()

        # Filter out any existing system messages from context
        for msg in context_messages:
            if msg.role != "system":
                messages.append(msg)

        # Add new user input
        messages.append(Message(role="user", content=user_input))

        return messages

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call with permission checking."""
        tool = self.tools.get(tool_call.name)

        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_call.name}",
            )

        # Get command for display
        cmd_display = self._get_command_display(tool_call)

        # Check permission
        if tool.requires_permission:
            request = PermissionRequest(
                tool_name=tool.name,
                arguments=tool_call.arguments,
                description=self._describe_tool_call(tool_call),
            )

            permission = await self.permissions.check(request)

            if not permission.approved:
                self.console.print("[yellow]⏹ Cancelled[/yellow]")
                return ToolResult(
                    success=False,
                    output="",
                    error="Permission denied by user",
                )

            # Use modified args if user edited
            args = permission.modified_args or tool_call.arguments
            # Update command display if args were modified
            if permission.modified_args:
                cmd_display = permission.modified_args.get("command", cmd_display)
        else:
            args = tool_call.arguments

        # Show execution start
        self.console.print()
        self.console.print("[bold yellow]▶ Run:[/bold yellow]")
        self.console.print(f"  [cyan]$ {cmd_display}[/cyan]")

        # Execute
        result = await tool.execute(**args)

        # Show result
        if result.success:
            if result.output.strip():
                # Truncate long output
                lines = result.output.strip().split('\n')
                if len(lines) > 15:
                    display_lines = lines[:12] + [f"  ... ({len(lines) - 12} more lines)"]
                    output_display = '\n'.join(display_lines)
                else:
                    output_display = result.output.strip()

                self.console.print("[bold blue]📋 Output:[/bold blue]")
                self.console.print(f"[dim]{output_display}[/dim]")
            else:
                self.console.print("[green]✓ Done[/green]")
        else:
            self.console.print(f"[bold red]✗ Failed:[/bold red] {result.error}")

        return result

    def _get_command_display(self, tool_call: ToolCall) -> str:
        """Get the command string for display."""
        if tool_call.name == "shell":
            return str(tool_call.arguments.get("command", ""))
        elif tool_call.name == "run_background":
            return str(tool_call.arguments.get("command", ""))
        elif tool_call.name == "check_background":
            return f"check_background({tool_call.arguments.get('task_id', '')})"
        else:
            return str(tool_call.arguments)

    def _describe_tool_call(self, tool_call: ToolCall) -> str:
        """Generate a human-readable description of a tool call."""
        if tool_call.name == "shell":
            cmd = tool_call.arguments.get("command", "")
            return f"Execute shell command: {cmd}"
        elif tool_call.name == "run_background":
            cmd = tool_call.arguments.get("command", "")
            return f"Run in background: {cmd}"
        elif tool_call.name == "check_background":
            task_id = tool_call.arguments.get("task_id", "")
            return f"Check background task: {task_id}"
        else:
            return f"{tool_call.name}: {tool_call.arguments}"
