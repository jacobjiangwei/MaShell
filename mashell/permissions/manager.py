"""Permission manager."""

from dataclasses import dataclass
from typing import Any

from mashell.config import PermissionConfig, add_auto_approve_tool
from mashell.permissions.ui import PermissionUI


@dataclass
class PermissionRequest:
    """A request for permission to perform an action."""

    tool_name: str
    arguments: dict[str, Any]
    description: str


@dataclass
class PermissionResult:
    """Result of a permission check."""

    approved: bool
    modified_args: dict[str, Any] | None = None  # If user edited
    remember: bool = False  # "Always approve" selected


class PermissionManager:
    """Manages permission checking and prompting."""

    def __init__(
        self,
        config: PermissionConfig,
        auto_approve_all: bool = False,
    ) -> None:
        self.config = config
        self.auto_approve_all = auto_approve_all
        self.session_approved: set[str] = set()  # Tools approved for session
        self.ui = PermissionUI()

    async def check(self, request: PermissionRequest) -> PermissionResult:
        """Check if permission is granted for an action."""
        # Auto-approve if -y flag
        if self.auto_approve_all:
            return PermissionResult(approved=True)

        # Check if in auto-approve list (from config file)
        if request.tool_name in self.config.auto_approve:
            return PermissionResult(approved=True)

        # Check if user said "always approve" this session
        if request.tool_name in self.session_approved:
            return PermissionResult(approved=True)

        # Prompt user
        result = await self.ui.prompt(request)

        # Remember if user said "always"
        if result.remember and result.approved:
            self.session_approved.add(request.tool_name)
            # Also persist to config file for future sessions
            try:
                add_auto_approve_tool(request.tool_name)
            except Exception:
                pass  # Silently fail if can't write config

        return result
