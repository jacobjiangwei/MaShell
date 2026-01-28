"""Core agent implementation."""

from typing import Any

from rich.console import Console

from mashell.config import Config
from mashell.providers import create_provider
from mashell.providers.base import BaseProvider, Message, ToolCall
from mashell.tools import create_tool_registry
from mashell.tools.base import ToolRegistry, ToolResult
from mashell.permissions import PermissionManager, PermissionRequest
from mashell.agent.context import ContextManager
from mashell.agent.prompt import get_system_prompt


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
                self.console.print(f"[dim]Iteration {iteration}...[/dim]")
            
            try:
                # Get LLM response
                response = await self.provider.chat(
                    messages,
                    tools=self.tools.all_schemas(),
                )
                
                if self.verbose:
                    self.console.print(f"[dim]Finish reason: {response.finish_reason}[/dim]")
                    if response.usage:
                        self.console.print(f"[dim]Tokens: {response.usage}[/dim]")
                
                # If no tool calls, we're done
                if not response.tool_calls:
                    if response.content:
                        self.console.print(f"\n[bold green]MaShell:[/bold green] {response.content}")
                        self.context.add_message(Message(role="assistant", content=response.content))
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
                    self.console.print(f"\n[dim]{response.content}[/dim]")
                
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
                self.console.print(f"[red]Error: {e}[/red]")
                if self.verbose:
                    import traceback
                    self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
                return None
        
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
        
        # Check permission
        if tool.requires_permission:
            request = PermissionRequest(
                tool_name=tool.name,
                arguments=tool_call.arguments,
                description=self._describe_tool_call(tool_call),
            )
            
            permission = await self.permissions.check(request)
            
            if not permission.approved:
                self.console.print("[yellow]Permission denied[/yellow]")
                return ToolResult(
                    success=False,
                    output="",
                    error="Permission denied by user",
                )
            
            # Use modified args if user edited
            args = permission.modified_args or tool_call.arguments
        else:
            args = tool_call.arguments
        
        # Execute
        if self.verbose:
            self.console.print(f"[dim]Executing: {tool.name}({args})[/dim]")
        
        result = await tool.execute(**args)
        
        # Show brief result
        if result.success:
            output_preview = result.output[:200] + "..." if len(result.output) > 200 else result.output
            if output_preview.strip():
                self.console.print(f"[dim]{output_preview}[/dim]")
        else:
            self.console.print(f"[red]Command failed: {result.error}[/red]")
        
        return result
    
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
