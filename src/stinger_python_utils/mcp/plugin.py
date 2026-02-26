"""ABC interface and data models for stinger MCP plugins.

Third-party packages implement :class:`StingerMCPPlugin` and register it
as a stevedore entry-point under the
``stinger_python_utils.mcp_plugins`` namespace.

Example ``pyproject.toml`` of a *plugin* package::

    [project.entry-points."stinger_python_utils.mcp_plugins"]
    my_service = "my_package.mcp_plugin:MyServicePlugin"
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


# ------------------------------------------------------------------
# Data models
# ------------------------------------------------------------------


@dataclass(frozen=True)
class SignalDefinition:
    """Describes a signal emitted by a stinger-ipc client.

    The MCP server calls ``client.receive_{name}(callback)`` and stores
    received payloads in a per-instance mailbox exposed as an MCP
    resource.
    """

    name: str
    description: str = ""


@dataclass(frozen=True)
class PropertyDefinition:
    """Describes a property on a stinger-ipc client.

    Every property is exposed as an MCP **resource**.  Writable
    properties (``readonly=False``) additionally get an MCP **tool**
    whose ``inputSchema`` is *schema*.

    *schema* must be a valid `JSON Schema`_ object.

    .. _JSON Schema: https://json-schema.org/
    """

    name: str
    schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {"value": {}},
            "required": ["value"],
        }
    )
    readonly: bool = True
    description: str = ""


@dataclass(frozen=True)
class MethodDefinition:
    """Describes a callable method on a stinger-ipc client.

    Each method is exposed as an MCP **tool** whose ``inputSchema`` is
    derived from *arguments_model* via ``model_json_schema()``.

    *arguments_model* must be a :class:`pydantic.BaseModel` subclass.
    When the tool is invoked, the raw JSON arguments are loaded into
    an instance of this model and the model is passed to
    ``call_{method_name}`` on the client.

    If *arguments_model* is ``None`` the tool accepts no arguments.
    """

    name: str
    arguments_model: type[BaseModel] | None = None
    description: str = ""


# ------------------------------------------------------------------
# Plugin ABC
# ------------------------------------------------------------------


class StingerMCPPlugin(ABC):
    """ABC that stevedore plugins must implement.

    Register concrete subclasses as entry-points under the namespace
    ``stinger_python_utils.mcp_plugins``::

        # pyproject.toml of the *plugin* package
        [project.entry-points."stinger_python_utils.mcp_plugins"]
        my_service = "my_package.plugin:MyPlugin"

    The MCP server loads all registered plugins at startup and:

    1. Instantiates the **discoverer** (from :meth:`get_discovery_class`)
       with a shared ``pyqttier`` ``IBrokerConnection``.
    2. On each discovered instance, instantiates the **client** (from
       :meth:`get_client_class`) with ``(connection, discovered_instance)``.
    3. Wires signals, properties, and methods into the MCP protocol.
    """

    # ------------------------------------------------------------------
    # Required – every plugin must implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def get_plugin_name(self) -> str:
        """Return a unique, short identifier for this plugin.

        Used as the scheme/prefix in MCP resource URIs and tool names
        (e.g. ``"lights"`` → ``lights://instance123/property/brightness``).
        """
        ...

    @abstractmethod
    def get_discovery_class(self) -> type:
        """Return the *Discoverer* class for this service type.

        The MCP server instantiates it as::

            discoverer = DiscovererClass(connection)

        The class **must** expose:

        * ``add_discovered_service_callback(cb)`` – *cb* receives a
          ``DiscoveredInstance`` (opaque pydantic model with at minimum
          an ``instance_id: str`` attribute).
        * ``add_removed_service_callback(cb)`` – *cb* receives the
          ``instance_id: str`` of the departed instance.
        """
        ...

    @abstractmethod
    def get_client_class(self) -> type:
        """Return the *Client* class for this service type.

        The MCP server instantiates it as::

            client = ClientClass(connection, discovered_instance)
        """
        ...

    @abstractmethod
    def get_signals(self) -> list[SignalDefinition]:
        """Return the list of signals the client can emit."""
        ...

    @abstractmethod
    def get_properties(self) -> list[PropertyDefinition]:
        """Return the list of properties the client exposes."""
        ...

    @abstractmethod
    def get_methods(self) -> list[MethodDefinition]:
        """Return the list of callable methods the client exposes."""
        ...

    # ------------------------------------------------------------------
    # Defaults – override for non-standard behaviour
    # ------------------------------------------------------------------

    def read_property(self, client: Any, prop_name: str) -> Any:
        """Read a property value from *client*.

        The default implementation returns ``getattr(client, prop_name)``.
        """
        return getattr(client, prop_name)

    def write_property(
        self, client: Any, prop_name: str, arguments: dict[str, Any]
    ) -> None:
        """Set a property on *client* from MCP tool *arguments*.

        *arguments* is the dict parsed from the tool's JSON Schema
        input.  The default implementation does::

            setattr(client, prop_name, arguments["value"])

        Override when the property value is a composite type that must
        be reconstructed from several arguments.
        """
        setattr(client, prop_name, list(arguments.values())[0])

    def call_method(
        self, client: Any, method_name: str, arguments: BaseModel | None
    ) -> Any:
        """Invoke *method_name* on *client* with *arguments*.

        *arguments* is a validated :class:`pydantic.BaseModel` instance
        (or ``None`` when the method takes no parameters).

        The default implementation calls::

            getattr(client, f"call_{method_name}")(arguments)

        and returns whatever the method returns (typically a
        ``concurrent.futures.Future``).
        """
        method = getattr(client, f"call_{method_name}")
        if arguments is None:
            return method()
        return method(arguments)

    def serialize_property(self, prop_name: str, value: Any) -> str:
        """Serialize a property *value* to a JSON string for the MCP resource.

        The default implementation handles pydantic ``BaseModel``
        instances and falls back to :func:`json.dumps`.
        """
        if hasattr(value, "model_dump_json"):
            return value.model_dump_json()
        return json.dumps(value, default=str)
