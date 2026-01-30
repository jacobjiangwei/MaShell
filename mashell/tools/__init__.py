"""Tools package - tool definitions and registry."""

from mashell.tools.background import BackgroundTaskManager, CheckBackgroundTool, RunBackgroundTool
from mashell.tools.base import BaseTool, ToolRegistry, ToolResult
from mashell.tools.filesystem import (
    EditDocxTool,
    ListDirTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
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
    "ReadFileTool",
    "ListDirTool",
    "SearchFilesTool",
    "WriteFileTool",
    "EditDocxTool",
    "create_tool_registry",
]


def create_tool_registry() -> ToolRegistry:
    """Create and populate a tool registry with all available tools."""
    registry = ToolRegistry()
    bg_manager = BackgroundTaskManager()

    # Native filesystem tools (no permission needed for reads)
    registry.register(ReadFileTool())
    registry.register(ListDirTool())
    registry.register(SearchFilesTool())
    registry.register(WriteFileTool())
    registry.register(EditDocxTool())

    # Execution tools (permission required)
    registry.register(ShellTool())
    registry.register(RunBackgroundTool(bg_manager))
    registry.register(CheckBackgroundTool(bg_manager))

    # Web tools
    registry.register(CrawlTool())
    registry.register(FetchPageTool())

    return registry
