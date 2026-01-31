"""Session persistence and management."""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from mashell.agent.context import ContextManager, TaskMemory
from mashell.providers.base import Message, ToolCall


def _serialize_message(msg: Message) -> dict[str, Any]:
    """Serialize a Message to a dict."""
    data: dict[str, Any] = {
        "role": msg.role,
        "content": msg.content,
    }
    if msg.tool_call_id:
        data["tool_call_id"] = msg.tool_call_id
    if msg.tool_calls:
        data["tool_calls"] = [
            {
                "id": tc.id,
                "name": tc.name,
                "arguments": tc.arguments,
            }
            for tc in msg.tool_calls
        ]
    return data


def _deserialize_message(data: dict[str, Any]) -> Message:
    """Deserialize a dict to a Message."""
    tool_calls = None
    if "tool_calls" in data:
        tool_calls = [
            ToolCall(
                id=tc["id"],
                name=tc["name"],
                arguments=tc["arguments"],
            )
            for tc in data["tool_calls"]
        ]
    return Message(
        role=data["role"],
        content=data.get("content"),
        tool_call_id=data.get("tool_call_id"),
        tool_calls=tool_calls,
    )


@dataclass
class CommandHistoryEntry:
    """A record of a command that was executed."""

    tool: str
    args: dict[str, Any]
    timestamp: str
    success: bool = True


@dataclass
class SessionData:
    """Persistent session data."""

    id: str
    name: str
    created: str
    updated: str
    workspace: str

    # Task information
    original_task: str = ""
    task_summary: str = ""
    progress: str = ""
    key_decisions: list[str] = field(default_factory=list)

    # Context state
    summary: str = ""  # Compressed history summary
    recent_messages: list[dict[str, Any]] = field(default_factory=list)

    # Command history (for audit)
    command_history: list[dict[str, Any]] = field(default_factory=list)

    # Stats
    total_turns: int = 0
    commands_run: int = 0
    files_modified: list[str] = field(default_factory=list)


class SessionManager:
    """Manages session persistence."""

    def __init__(self, sessions_dir: Path | None = None) -> None:
        self.sessions_dir = sessions_dir or (Path.home() / ".mashell" / "sessions")
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: SessionData | None = None

    def _generate_id(self) -> str:
        """Generate a unique session ID."""
        import uuid

        return f"sess_{uuid.uuid4().hex[:8]}"

    def _now_iso(self) -> str:
        """Get current time in ISO format."""
        return datetime.now().isoformat()

    def _session_path(self, name: str) -> Path:
        """Get the file path for a session."""
        # Sanitize name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return self.sessions_dir / f"{safe_name}.json"

    def create(self, name: str = "default", workspace: str | None = None) -> SessionData:
        """Create a new session."""
        now = self._now_iso()
        session = SessionData(
            id=self._generate_id(),
            name=name,
            created=now,
            updated=now,
            workspace=workspace or os.getcwd(),
        )
        self._current_session = session
        self.save()
        return session

    def save(self) -> None:
        """Save the current session to disk."""
        if self._current_session is None:
            return

        path = self._session_path(self._current_session.name)
        self._current_session.updated = self._now_iso()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self._current_session), f, indent=2, ensure_ascii=False)

    def load(self, name: str) -> SessionData | None:
        """Load a session by name."""
        path = self._session_path(name)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        session = SessionData(**data)
        self._current_session = session
        return session

    def load_most_recent(self) -> SessionData | None:
        """Load the most recently updated session."""
        sessions = self.list_sessions()
        if not sessions:
            return None

        # Sort by updated time, most recent first
        sessions.sort(key=lambda s: s.updated, reverse=True)
        return self.load(sessions[0].name)

    def list_sessions(self) -> list[SessionData]:
        """List all saved sessions."""
        sessions: list[SessionData] = []

        for path in self.sessions_dir.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append(SessionData(**data))
            except (json.JSONDecodeError, TypeError, KeyError):
                # Skip invalid session files
                continue

        return sessions

    def delete(self, name: str) -> bool:
        """Delete a session by name."""
        path = self._session_path(name)
        if path.exists():
            path.unlink()
            if self._current_session and self._current_session.name == name:
                self._current_session = None
            return True
        return False

    def clear_all(self) -> int:
        """Delete all sessions. Returns count of deleted sessions."""
        count = 0
        for path in self.sessions_dir.glob("*.json"):
            path.unlink()
            count += 1
        self._current_session = None
        return count

    @property
    def current(self) -> SessionData | None:
        """Get the current session."""
        return self._current_session

    # === Context Integration ===

    def update_from_context(
        self,
        context: ContextManager,
        user_input: str | None = None,
    ) -> None:
        """Update session from context manager state."""
        if self._current_session is None:
            return

        session = self._current_session

        # Update task memory
        task_mem = context.get_task_memory()
        if task_mem.original_task:
            session.original_task = task_mem.original_task
        if task_mem.key_decisions:
            session.key_decisions = task_mem.key_decisions.copy()
        if task_mem.progress:
            session.progress = ", ".join(task_mem.progress)

        # Store compressed summary
        session.summary = context.summary

        # Store recent messages (last N)
        max_recent = 10
        recent = context.messages[-max_recent:] if context.messages else []
        session.recent_messages = [_serialize_message(msg) for msg in recent]

        # Update stats
        session.total_turns += 1

        # Set initial task if this is first user input
        if user_input and not session.original_task:
            session.original_task = user_input[:500]  # Limit length

        self.save()

    def restore_to_context(self, context: ContextManager) -> None:
        """Restore session state into a context manager."""
        if self._current_session is None:
            return

        session = self._current_session

        # Restore task memory
        context.task_memory = TaskMemory(
            original_task=session.original_task,
            key_decisions=session.key_decisions.copy(),
            progress=session.progress.split(", ") if session.progress else [],
        )

        # Restore compressed summary
        context.summary = session.summary

        # Restore recent messages
        context.messages = [_deserialize_message(msg_data) for msg_data in session.recent_messages]

    def add_command(
        self,
        tool: str,
        args: dict[str, Any],
        success: bool = True,
    ) -> None:
        """Record a command execution in history."""
        if self._current_session is None:
            return

        entry = CommandHistoryEntry(
            tool=tool,
            args=args,
            timestamp=self._now_iso(),
            success=success,
        )

        self._current_session.command_history.append(asdict(entry))
        self._current_session.commands_run += 1

        # Track modified files
        if tool in ("write_file", "edit_docx") and success:
            path = args.get("path", "")
            if path and path not in self._current_session.files_modified:
                self._current_session.files_modified.append(path)

        # Keep history bounded
        max_history = 100
        if len(self._current_session.command_history) > max_history:
            self._current_session.command_history = self._current_session.command_history[
                -max_history:
            ]

    def get_resume_prompt(self) -> str | None:
        """Generate a prompt to resume the session."""
        if self._current_session is None:
            return None

        session = self._current_session

        if not session.original_task:
            return None

        parts = [
            "[Session Resumed]",
            f"Original task: {session.original_task}",
        ]

        if session.progress:
            parts.append(f"Progress: {session.progress}")

        if session.key_decisions:
            parts.append("Key decisions:")
            for decision in session.key_decisions[-5:]:  # Last 5 decisions
                parts.append(f"  - {decision}")

        parts.append("")
        parts.append("Please continue with the task, picking up where we left off.")

        return "\n".join(parts)
