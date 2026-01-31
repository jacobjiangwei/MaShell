"""Core agent implementation."""

import signal
import threading
from typing import Any

from rich.console import Console
from rich.markup import escape as rich_escape
from rich.prompt import Prompt
from rich.status import Status

from mashell.agent.context import ContextManager
from mashell.agent.prompt import get_system_prompt
from mashell.config import Config
from mashell.permissions import PermissionManager, PermissionRequest
from mashell.providers import create_provider
from mashell.providers.base import BaseProvider, Message, ToolCall
from mashell.tools import create_tool_registry
from mashell.tools.base import ToolRegistry, ToolResult


class InterruptError(Exception):
    """Raised when user interrupts the agent."""

    pass


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

        # Interrupt flag
        self._interrupted = False
        self._original_sigint_handler: Any = None

    def _start_status(self, message: str, emoji: str = "🤔") -> None:
        """Show status indicator with custom message."""
        if self._spinner is not None:
            self._spinner.stop()
        self._spinner = self.console.status(
            f"[bold cyan]{emoji} {message}[/bold cyan]", spinner="dots"
        )
        self._spinner.start()

    def _update_status(self, message: str, emoji: str = "⚡") -> None:
        """Update the status message without stopping/starting."""
        if self._spinner is not None:
            self._spinner.update(f"[bold cyan]{emoji} {message}[/bold cyan]")
        else:
            self._start_status(message, emoji)

    def _start_thinking(self) -> None:
        """Show thinking indicator."""
        self._start_status("Thinking...", "🤔")

    def _stop_thinking(self) -> None:
        """Hide thinking indicator."""
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner = None

    def _setup_interrupt_handler(self) -> None:
        """Setup Ctrl+C handler to allow interruption."""
        # Only setup signal handler in main thread
        if threading.current_thread() is not threading.main_thread():
            return

        def handler(signum: int, frame: object) -> None:
            self._interrupted = True
            self._stop_thinking()
            # Don't print here - let _check_interrupted handle the prompt

        self._original_sigint_handler = signal.signal(signal.SIGINT, handler)

    def _restore_interrupt_handler(self) -> None:
        """Restore original Ctrl+C handler."""
        # Only restore if we're in main thread
        if threading.current_thread() is not threading.main_thread():
            return

        if self._original_sigint_handler is not None:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
            self._original_sigint_handler = None

    def _check_interrupted(self) -> str | None:
        """Check if interrupted and get new user input if so."""
        if not self._interrupted:
            return None

        self._interrupted = False
        self.console.print()
        self.console.print("[yellow]⚡ Interrupted![/yellow]")

        try:
            new_input = Prompt.ask(
                "[bold yellow]▶[/bold yellow] New instruction (Enter=continue, 'stop'=abort)"
            )
            new_input = new_input.strip()

            if new_input.lower() == "stop":
                return "__STOP__"
            elif new_input:
                return new_input
            else:
                return None  # Continue with current task
        except (KeyboardInterrupt, EOFError):
            return "__STOP__"

    async def run(self, user_input: str) -> str | None:
        """Run the agent with user input."""

        # Setup interrupt handler
        self._setup_interrupt_handler()
        self._interrupted = False

        try:
            return await self._run_loop(user_input)
        finally:
            self._restore_interrupt_handler()

    async def _run_loop(self, user_input: str) -> str | None:
        """Internal run loop with interrupt support."""
        # Build messages
        messages = self._build_messages(user_input)

        # Add user message to context
        self.context.add_message(Message(role="user", content=user_input))

        # Run agent loop
        iteration = 0
        max_iterations = 20  # Safety limit

        while True:
            # Check for interrupt at start of each iteration
            new_instruction = self._check_interrupted()
            if new_instruction == "__STOP__":
                self.console.print("[yellow]Stopped by user.[/yellow]")
                return None
            elif new_instruction:
                # User provided new instruction - add it and continue
                self.console.print(f"[bold blue]📝 New instruction:[/bold blue] {new_instruction}")
                messages.append(Message(role="user", content=new_instruction))
                self.context.add_message(Message(role="user", content=new_instruction))
                iteration = 0  # Reset iteration count for new instruction

            iteration += 1

            # Check iteration limit
            if iteration > max_iterations:
                self._stop_thinking()
                self.console.print(f"\n[yellow]⚠️ Reached {max_iterations} iterations.[/yellow]")

                try:
                    choice = Prompt.ask(
                        "[bold]Continue?[/bold]", choices=["y", "n", "more"], default="y"
                    )

                    if choice == "n":
                        self.console.print("[dim]Stopped.[/dim]")
                        return None
                    elif choice == "more":
                        # Let user add more context
                        extra = Prompt.ask("[bold yellow]Add instruction[/bold yellow]")
                        if extra.strip():
                            messages.append(Message(role="user", content=extra.strip()))
                            self.context.add_message(Message(role="user", content=extra.strip()))

                    # Reset counter and continue
                    iteration = 1
                    max_iterations = 20

                except (KeyboardInterrupt, EOFError):
                    self.console.print("\n[dim]Stopped.[/dim]")
                    return None

            if self.verbose:
                self._stop_thinking()
                self.console.print(f"[dim]Iteration {iteration}/{max_iterations}...[/dim]")

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
                        self.console.print(f"[bold green]MaShell:[/bold green] {response.content}")
                        self.context.add_message(
                            Message(role="assistant", content=response.content)
                        )
                    else:
                        # LLM returned empty response (possibly refused)
                        self.console.print()
                        self.console.print(
                            "[yellow]MaShell:[/yellow] "
                            "[dim](No response - model may have declined)[/dim]"
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
                tool_calls_list = list(response.tool_calls)
                for i, tool_call in enumerate(tool_calls_list):
                    # Check interrupt before each tool execution
                    new_instruction = self._check_interrupted()
                    if new_instruction == "__STOP__":
                        self.console.print("[yellow]Stopped by user.[/yellow]")
                        return None
                    elif new_instruction:
                        # Add cancelled results for remaining tool calls
                        # (API requires all tool_calls have results)
                        for remaining_call in tool_calls_list[i:]:
                            cancelled_msg = Message(
                                role="tool",
                                content="[Cancelled by user]",
                                tool_call_id=remaining_call.id,
                            )
                            messages.append(cancelled_msg)
                            self.context.add_message(cancelled_msg)

                        self.console.print(
                            f"[bold blue]📝 New instruction:[/bold blue] {new_instruction}"
                        )
                        messages.append(Message(role="user", content=new_instruction))
                        self.context.add_message(Message(role="user", content=new_instruction))
                        break  # Exit tool loop to process new instruction

                    result = await self._execute_tool(tool_call)

                    # Check interrupt AFTER tool execution (user may have pressed Ctrl+C during)
                    new_instruction = self._check_interrupted()
                    if new_instruction == "__STOP__":
                        self.console.print("[yellow]Stopped by user.[/yellow]")
                        return None
                    elif new_instruction:
                        # Add tool result first
                        tool_msg = Message(
                            role="tool",
                            content=result.output if result.success else f"Error: {result.error}",
                            tool_call_id=tool_call.id,
                        )
                        messages.append(tool_msg)
                        self.context.add_message(tool_msg)

                        # Add cancelled results for remaining tool calls
                        for remaining_call in tool_calls_list[i + 1 :]:
                            cancelled_msg = Message(
                                role="tool",
                                content="[Cancelled by user]",
                                tool_call_id=remaining_call.id,
                            )
                            messages.append(cancelled_msg)
                            self.context.add_message(cancelled_msg)

                        self.console.print(
                            f"[bold blue]📝 New instruction:[/bold blue] {new_instruction}"
                        )
                        messages.append(Message(role="user", content=new_instruction))
                        self.context.add_message(Message(role="user", content=new_instruction))
                        break  # Exit tool loop to process new instruction

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
                self.console.print(f"[red]Error: {rich_escape(str(e))}[/red]")
                if self.verbose:
                    import traceback

                    self.console.print(f"[dim]{rich_escape(traceback.format_exc())}[/dim]")
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
        self.console.print(f"  [cyan]$ {rich_escape(cmd_display)}[/cyan]")

        # Get tool-specific status message
        status_msg = self._get_tool_status_message(tool_call.name)

        # Execute with status indicator
        self._start_status(status_msg, "⚡")
        try:
            result = await tool.execute(**args)
        finally:
            self._stop_thinking()

        # Show result
        if result.success:
            if result.output.strip():
                # Truncate long output
                lines = result.output.strip().split("\n")
                if len(lines) > 15:
                    more = len(lines) - 12
                    display_lines = lines[:12] + [f"  ... ({more} more lines)"]
                    output_display = "\n".join(display_lines)
                else:
                    output_display = result.output.strip()

                self.console.print("[bold blue]📋 Output:[/bold blue]")
                self.console.print(f"[dim]{rich_escape(output_display)}[/dim]")
            else:
                self.console.print("[green]✓ Done[/green]")
        else:
            err_msg = rich_escape(result.error or "Unknown error")
            self.console.print(f"[bold red]✗ Failed:[/bold red] {err_msg}")

        return result

    def _get_command_display(self, tool_call: ToolCall) -> str:
        """Get the command string for display."""
        if tool_call.name == "shell":
            return str(tool_call.arguments.get("command", ""))
        elif tool_call.name == "run_background":
            return str(tool_call.arguments.get("command", ""))
        elif tool_call.name == "check_background":
            return f"check_background({tool_call.arguments.get('task_id', '')})"
        elif tool_call.name == "read_file":
            path = tool_call.arguments.get("path", "")
            start = tool_call.arguments.get("start_line")
            end = tool_call.arguments.get("end_line")
            if start or end:
                return f"read_file({path!r}, lines={start or 1}-{end or 'end'})"
            return f"read_file({path!r})"
        elif tool_call.name == "list_dir":
            path = tool_call.arguments.get("path", ".")
            pattern = tool_call.arguments.get("pattern")
            if pattern:
                return f"list_dir({path!r}, pattern={pattern!r})"
            return f"list_dir({path!r})"
        elif tool_call.name == "search_files":
            pattern = tool_call.arguments.get("pattern", "")
            path = tool_call.arguments.get("path", ".")
            return f"search_files({pattern!r}, path={path!r})"
        elif tool_call.name == "write_file":
            path = tool_call.arguments.get("path", "")
            content = tool_call.arguments.get("content", "")
            return f"write_file({path!r}, {len(content)} chars)"
        elif tool_call.name == "crawl":
            query = tool_call.arguments.get("query", "")
            return f"crawl({query!r})"
        elif tool_call.name == "fetch_page":
            url = tool_call.arguments.get("url", "")
            return f"fetch_page({url!r})"
        elif tool_call.name == "edit_docx":
            path = tool_call.arguments.get("path", "")
            ops = tool_call.arguments.get("operations", [])
            save_as = tool_call.arguments.get("save_as")
            if save_as:
                return f"edit_docx({path!r}, {len(ops)} ops, save_as={save_as!r})"
            return f"edit_docx({path!r}, {len(ops)} ops)"
        else:
            return f"{tool_call.name}({tool_call.arguments})"

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
        elif tool_call.name == "read_file":
            path = tool_call.arguments.get("path", "")
            return f"Read file: {path}"
        elif tool_call.name == "list_dir":
            path = tool_call.arguments.get("path", ".")
            return f"List directory: {path}"
        elif tool_call.name == "search_files":
            pattern = tool_call.arguments.get("pattern", "")
            path = tool_call.arguments.get("path", ".")
            return f"Search for '{pattern}' in {path}"
        elif tool_call.name == "write_file":
            path = tool_call.arguments.get("path", "")
            return f"Write to file: {path}"
        elif tool_call.name == "crawl":
            query = tool_call.arguments.get("query", "")
            return f"Web search: {query}"
        elif tool_call.name == "fetch_page":
            url = tool_call.arguments.get("url", "")
            return f"Fetch page: {url}"
        elif tool_call.name == "edit_docx":
            path = tool_call.arguments.get("path", "")
            return f"Edit Word document: {path}"
        else:
            return f"{tool_call.name}: {tool_call.arguments}"

    def _get_tool_status_message(self, tool_name: str) -> str:
        """Get a status message for the tool execution."""
        status_messages = {
            "shell": "Executing command...",
            "run_background": "Starting background task...",
            "check_background": "Checking task status...",
            "read_file": "Reading file...",
            "list_dir": "Listing directory...",
            "search_files": "Searching files...",
            "write_file": "Writing file...",
            "crawl": "Crawling web...",
            "fetch_page": "Fetching page...",
            "edit_docx": "Editing Word document...",
        }
        return status_messages.get(tool_name, f"Running {tool_name}...")
