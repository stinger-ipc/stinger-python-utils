"""Stinger MCP server – plugin-based MCP interface to stinger-ipc services.

Public API re-exported here for convenience::

    from stinger_python_utils.mcp import StingerMCPPlugin, SignalDefinition, ...
"""

from .plugin import (
    MethodDefinition,
    PropertyDefinition,
    SignalDefinition,
    StingerMCPPlugin,
)

__all__ = [
    "MethodDefinition",
    "PropertyDefinition",
    "SignalDefinition",
    "StingerMCPPlugin",
]
