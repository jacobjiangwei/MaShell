"""Permissions package - permission management."""

from mashell.permissions.manager import PermissionManager, PermissionRequest, PermissionResult
from mashell.permissions.ui import PermissionUI

__all__ = [
    "PermissionManager",
    "PermissionRequest",
    "PermissionResult",
    "PermissionUI",
]
