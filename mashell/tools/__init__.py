"""Tools package - tool definitions and registry."""

from mashell.tools.background import BackgroundTaskManager, CheckBackgroundTool, RunBackgroundTool
from mashell.tools.base import BaseTool, ToolRegistry, ToolResult
from mashell.tools.shell import ShellTool
from mashell.tools.web import CrawlTool, FetchPageTool

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "ShellTool",
    "BackgroundTaskManager",
    "RunBackgroundTool",
    "CheckBackgroundTool",
    "CrawlTool",
    "FetchPageTool",
    "create_tool_registry",
]


def create_tool_registry() -> ToolRegistry:
    """Create and populate a tool registry with all available tools."""
    registry = ToolRegistry()
    bg_manager = BackgroundTaskManager()

    registry.register(ShellTool())
    registry.register(RunBackgroundTool(bg_manager))
    registry.register(CheckBackgroundTool(bg_manager))
    registry.register(CrawlTool())
    registry.register(FetchPageTool())

    return registry
