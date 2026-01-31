"""Context management and compression."""

from dataclasses import dataclass, field

from mashell.providers.base import Message


@dataclass
class TaskMemory:
    """Persistent memory of the current task."""

    original_task: str = ""
    current_step: int = 0
    total_steps: int = 0
    progress: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)


class ContextManager:
    """Manages conversation context and compression."""

    def __init__(
        self,
        max_messages: int = 50,
        max_recent: int = 10,
    ) -> None:
        self.messages: list[Message] = []
        self.summary: str = ""
        self.task_memory = TaskMemory()
        self.max_messages = max_messages
        self.max_recent = max_recent

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)

        # Compress if needed
        if len(self.messages) > self.max_messages:
            self._compress()

    def get_messages(self) -> list[Message]:
        """Get all messages including any summary."""
        result: list[Message] = []

        # Add summary as first user message if we have compressed history
        if self.summary:
            result.append(
                Message(
                    role="user",
                    content=f"[Previous conversation summary]\n{self.summary}\n[End summary]",
                )
            )

        # Add recent messages
        result.extend(self.messages)

        return result

    def set_task(self, task: str, steps: list[str] | None = None) -> None:
        """Set the current task being worked on."""
        self.task_memory.original_task = task
        if steps:
            self.task_memory.progress = steps
            self.task_memory.total_steps = len(steps)
        self.task_memory.current_step = 0

    def update_progress(self, step: int) -> None:
        """Update task progress."""
        self.task_memory.current_step = step

    def add_decision(self, decision: str) -> None:
        """Record a key decision."""
        self.task_memory.key_decisions.append(decision)

    def get_task_memory(self) -> TaskMemory:
        """Get current task memory."""
        return self.task_memory

    def clear(self) -> None:
        """Clear all context."""
        self.messages = []
        self.summary = ""
        self.task_memory = TaskMemory()

    def _compress(self) -> None:
        """Compress old messages into a summary."""
        if len(self.messages) <= self.max_recent:
            return

        # Keep only recent messages
        old_messages = self.messages[: -self.max_recent]
        self.messages = self.messages[-self.max_recent :]

        # Generate summary from old messages
        new_summary_parts = []

        for msg in old_messages:
            if msg.role == "user":
                # Summarize user requests
                content = msg.content or ""
                if len(content) > 100:
                    content = content[:100] + "..."
                new_summary_parts.append(f"User asked: {content}")

            elif msg.role == "assistant":
                # Summarize assistant actions
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.name == "shell":
                            cmd = tc.arguments.get("command", "")
                            if len(cmd) > 50:
                                cmd = cmd[:50] + "..."
                            new_summary_parts.append(f"Executed: {cmd}")
                elif msg.content:
                    content = msg.content
                    if len(content) > 100:
                        content = content[:100] + "..."
                    new_summary_parts.append(f"Response: {content}")

            elif msg.role == "tool":
                # Summarize tool results briefly
                content = msg.content or ""
                if "error" in content.lower() or "failed" in content.lower():
                    if len(content) > 100:
                        content = content[:100] + "..."
                    new_summary_parts.append(f"Error: {content}")
                else:
                    # Just note success
                    new_summary_parts.append("Command succeeded")

        # Combine with existing summary
        if self.summary:
            self.summary += "\n\n"
        self.summary += "\n".join(new_summary_parts)

        # Truncate summary if too long
        if len(self.summary) > 2000:
            self.summary = self.summary[-2000:]
