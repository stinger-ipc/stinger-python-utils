"""MCP server that dynamically exposes stinger-ipc services via plugins.

Plugins are discovered through stevedore entry-points registered under
the ``stinger_python_utils.mcp_plugins`` namespace.  Each plugin
supplies a discoverer, a client class, and metadata describing signals,
properties, and methods.  As service instances appear and disappear on
the MQTT bus the MCP tool and resource lists are updated accordingly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import uuid
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl
from pyqttier.connection import Mqtt5Connection
from pyqttier.transport import MqttTransport, MqttTransportType
from stevedore import ExtensionManager

from .plugin import (
    MethodDefinition,
    PropertyDefinition,
    SignalDefinition,
    StingerMCPPlugin,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Internal data structures
# ------------------------------------------------------------------

SIGNAL_MAILBOX_SIZE = 10


@dataclass
class SignalMailbox:
    """Bounded FIFO of the most recent signal payloads."""

    _entries: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=SIGNAL_MAILBOX_SIZE)
    )

    def append(self, data: dict[str, Any]) -> None:
        self._entries.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
        )

    def to_json(self) -> str:
        return json.dumps(list(self._entries), default=str)


@dataclass
class InstanceState:
    """Run-time bookkeeping for one discovered service instance."""

    plugin_name: str
    plugin: StingerMCPPlugin
    instance_id: str
    client: Any
    signal_mailboxes: dict[str, SignalMailbox] = field(default_factory=dict)
    property_cache: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _sanitize(value: str) -> str:
    """Turn an arbitrary string into a safe MCP identifier fragment."""
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def _instance_key(plugin_name: str, instance_id: str) -> str:
    return f"{_sanitize(plugin_name)}_{_sanitize(instance_id)}"


async def _resolve_future(future: Future[Any], timeout: float = 30.0) -> Any:
    """Bridge a :class:`concurrent.futures.Future` into *asyncio*."""
    return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)


# ------------------------------------------------------------------
# MQTT connection factory
# ------------------------------------------------------------------


def create_mqtt_connection() -> Mqtt5Connection:
    """Create an :class:`Mqtt5Connection` from environment variables.

    ==================  ===========  ===============================
    Variable            Default      Description
    ==================  ===========  ===============================
    ``MQTT_HOST``       localhost    Broker hostname
    ``MQTT_PORT``       1883         Broker port
    ``MQTT_TRANSPORT``  tcp          ``tcp`` | ``websocket`` | ``unix``
    ``MQTT_CLIENT_ID``  (random)     MQTT client identifier
    ==================  ===========  ===============================
    """
    host = os.environ.get("MQTT_HOST", "localhost")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    transport_str = os.environ.get("MQTT_TRANSPORT", "tcp").upper()
    transport_type = getattr(MqttTransportType, transport_str, MqttTransportType.TCP)
    client_id = os.environ.get(
        "MQTT_CLIENT_ID", f"stinger-mcp-{uuid.uuid4().hex[:8]}"
    )

    transport = MqttTransport(transport_type, host=host, port=port)
    return Mqtt5Connection(transport=transport, client_id=client_id)


# ------------------------------------------------------------------
# The server
# ------------------------------------------------------------------


class StingerMCPServer:
    """Loads stevedore plugins and serves them over MCP."""

    STEVEDORE_NAMESPACE = "stinger_python_utils.mcp_plugins"

    def __init__(self) -> None:
        self._server = Server("stinger-mcp")
        self._plugins: list[StingerMCPPlugin] = []
        self._instances: dict[str, InstanceState] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connection: Mqtt5Connection | None = None

        self._register_handlers()

    # ==================================================================
    # MCP handler registration
    # ==================================================================

    def _register_handlers(self) -> None:
        server = self._server

        @server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            return self._build_tool_list()

        @server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict[str, Any] | None
        ) -> list[types.TextContent]:
            return await self._dispatch_tool(name, arguments or {})

        @server.list_resources()
        async def handle_list_resources() -> list[types.Resource]:
            return self._build_resource_list()

        @server.read_resource()
        async def handle_read_resource(uri: AnyUrl) -> str:
            return self._read_resource(uri)

    # ==================================================================
    # Tools
    # ==================================================================

    def _build_tool_list(self) -> list[types.Tool]:
        tools: list[types.Tool] = []
        with self._lock:
            for state in self._instances.values():
                pn = _sanitize(state.plugin_name)
                iid = _sanitize(state.instance_id)

                for mdef in state.plugin.get_methods():
                    tools.append(
                        types.Tool(
                            name=f"{pn}_{iid}_{_sanitize(mdef.name)}",
                            description=(
                                mdef.description
                                or f"Call {mdef.name} on {state.plugin_name} "
                                f"instance {state.instance_id}"
                            ),
                            inputSchema=mdef.arguments_schema,
                        )
                    )

                for pdef in state.plugin.get_properties():
                    if not pdef.readonly:
                        tools.append(
                            types.Tool(
                                name=f"{pn}_{iid}_set_{_sanitize(pdef.name)}",
                                description=(
                                    pdef.description
                                    or f"Set {pdef.name} on {state.plugin_name} "
                                    f"instance {state.instance_id}"
                                ),
                                inputSchema=pdef.schema,
                            )
                        )
        return tools

    def _resolve_tool(
        self, name: str
    ) -> tuple[InstanceState, str, str] | None:
        """Map a tool *name* → ``(state, kind, item_name)``.

        *kind* is ``"method"`` or ``"property"``.  Methods are checked
        first so that a method named ``set_foo`` takes precedence over
        a property setter for ``foo``.
        """
        with self._lock:
            for state in self._instances.values():
                pn = _sanitize(state.plugin_name)
                iid = _sanitize(state.instance_id)
                prefix = f"{pn}_{iid}_"

                if not name.startswith(prefix):
                    continue

                remainder = name[len(prefix) :]

                # Methods take priority
                for mdef in state.plugin.get_methods():
                    if _sanitize(mdef.name) == remainder:
                        return state, "method", mdef.name

                # Property setters: set_<prop_name>
                if remainder.startswith("set_"):
                    prop_token = remainder[4:]
                    for pdef in state.plugin.get_properties():
                        if (
                            _sanitize(pdef.name) == prop_token
                            and not pdef.readonly
                        ):
                            return state, "property", pdef.name

        return None

    async def _dispatch_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        target = self._resolve_tool(name)
        if target is None:
            raise ValueError(f"Unknown tool: {name}")

        state, kind, item_name = target

        if kind == "property":
            try:
                state.plugin.write_property(state.client, item_name, arguments)
                text = json.dumps({"status": "ok", "property": item_name})
            except Exception as exc:
                logger.exception("Error setting property %s", item_name)
                text = json.dumps(
                    {"status": "error", "error": str(exc)}, default=str
                )
            return [types.TextContent(type="text", text=text)]

        # kind == "method"
        try:
            result = state.plugin.call_method(
                state.client, item_name, arguments
            )
            if isinstance(result, Future):
                result = await _resolve_future(result)

            if hasattr(result, "model_dump_json"):
                text = result.model_dump_json()
            elif result is None:
                text = json.dumps({"status": "ok"})
            else:
                text = json.dumps(result, default=str)
        except Exception as exc:
            logger.exception("Error calling method %s", item_name)
            text = json.dumps(
                {"status": "error", "error": str(exc)}, default=str
            )

        return [types.TextContent(type="text", text=text)]

    # ==================================================================
    # Resources
    # ==================================================================

    def _build_resource_list(self) -> list[types.Resource]:
        resources: list[types.Resource] = []
        with self._lock:
            for state in self._instances.values():
                pn = state.plugin_name
                iid = state.instance_id

                for pdef in state.plugin.get_properties():
                    resources.append(
                        types.Resource(
                            uri=AnyUrl(f"{pn}://{iid}/property/{pdef.name}"),
                            name=f"{pn} {iid} – {pdef.name}",
                            description=pdef.description
                            or f"Property {pdef.name}",
                            mimeType="application/json",
                        )
                    )

                for sdef in state.plugin.get_signals():
                    resources.append(
                        types.Resource(
                            uri=AnyUrl(f"{pn}://{iid}/signal/{sdef.name}"),
                            name=f"{pn} {iid} – {sdef.name} (signals)",
                            description=sdef.description
                            or f"Mailbox of the last {SIGNAL_MAILBOX_SIZE} "
                            f"'{sdef.name}' signals",
                            mimeType="application/json",
                        )
                    )
        return resources

    def _read_resource(self, uri: AnyUrl) -> str:
        parsed = urlparse(str(uri))
        plugin_name = parsed.scheme
        instance_id = parsed.netloc
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]

        if len(path_parts) < 2:
            raise ValueError(f"Invalid resource URI: {uri}")

        category, item_name = path_parts[0], path_parts[1]
        key = _instance_key(plugin_name, instance_id)

        with self._lock:
            state = self._instances.get(key)

        if state is None:
            raise ValueError(
                f"No active instance for {plugin_name}/{instance_id}"
            )

        if category == "property":
            value = state.plugin.read_property(state.client, item_name)
            return state.plugin.serialize_property(item_name, value)

        if category == "signal":
            mailbox = state.signal_mailboxes.get(item_name)
            if mailbox is None:
                return "[]"
            return mailbox.to_json()

        raise ValueError(f"Unknown resource category: {category}")

    # ==================================================================
    # Plugin loading & discovery wiring
    # ==================================================================

    def _load_plugins(self) -> None:
        def _on_failure(
            _mgr: ExtensionManager, entrypoint: Any, err: Exception
        ) -> None:
            logger.error("Failed to load plugin %s: %s", entrypoint, err)

        mgr = ExtensionManager(
            namespace=self.STEVEDORE_NAMESPACE,
            invoke_on_load=True,
            on_load_failure_callback=_on_failure,
        )
        for ext in mgr:
            plugin = ext.obj
            if isinstance(plugin, StingerMCPPlugin):
                self._plugins.append(plugin)
                logger.info(
                    "Loaded MCP plugin: %s", plugin.get_plugin_name()
                )
            else:
                logger.warning(
                    "Entry-point %s did not produce a StingerMCPPlugin "
                    "(got %s); skipping.",
                    ext.name,
                    type(plugin).__name__,
                )

    def _start_discovery(self) -> None:
        assert self._connection is not None
        for plugin in self._plugins:
            discoverer_cls = plugin.get_discovery_class()
            discoverer = discoverer_cls(self._connection)

            discoverer.add_discovered_service_callback(
                lambda inst, _p=plugin: self._on_discovered(inst, _p)
            )
            discoverer.add_removed_service_callback(
                lambda iid, _p=plugin: self._on_removed(iid, _p)
            )
            logger.info(
                "Discovery started for plugin '%s'",
                plugin.get_plugin_name(),
            )

    # ---- callbacks (called on the MQTT thread) -----------------------

    def _on_discovered(
        self, discovered_instance: Any, plugin: StingerMCPPlugin
    ) -> None:
        """Register a newly-discovered service instance."""
        plugin_name = plugin.get_plugin_name()
        instance_id: str = discovered_instance.instance_id
        key = _instance_key(plugin_name, instance_id)

        with self._lock:
            if key in self._instances:
                logger.debug(
                    "Instance %s/%s already tracked; ignoring.",
                    plugin_name,
                    instance_id,
                )
                return

        logger.info("Discovered %s / %s", plugin_name, instance_id)

        client_cls = plugin.get_client_class()
        client = client_cls(self._connection, discovered_instance)

        state = InstanceState(
            plugin_name=plugin_name,
            plugin=plugin,
            instance_id=instance_id,
            client=client,
        )

        # -- signals ---------------------------------------------------
        for sdef in plugin.get_signals():
            mailbox = SignalMailbox()
            state.signal_mailboxes[sdef.name] = mailbox

            recv_fn = getattr(client, f"receive_{sdef.name}", None)
            if recv_fn is not None:

                def _make_signal_cb(mb: SignalMailbox) -> Any:
                    def _cb(**kwargs: Any) -> None:
                        mb.append(kwargs)

                    return _cb

                recv_fn(_make_signal_cb(mailbox))

        # -- properties ------------------------------------------------
        for pdef in plugin.get_properties():
            try:
                state.property_cache[pdef.name] = plugin.read_property(
                    client, pdef.name
                )
            except Exception:
                state.property_cache[pdef.name] = None

            changed_fn = getattr(client, f"{pdef.name}_changed", None)
            if changed_fn is not None:

                def _make_prop_cb(
                    _state: InstanceState, _pname: str
                ) -> Any:
                    def _cb(value: Any = None, **kwargs: Any) -> None:
                        _state.property_cache[_pname] = value

                    return _cb

                changed_fn(_make_prop_cb(state, pdef.name))

        with self._lock:
            self._instances[key] = state

    def _on_removed(
        self, instance_id: str, plugin: StingerMCPPlugin
    ) -> None:
        """Deregister a departed service instance."""
        plugin_name = plugin.get_plugin_name()
        key = _instance_key(plugin_name, instance_id)

        logger.info("Removed %s / %s", plugin_name, instance_id)
        with self._lock:
            self._instances.pop(key, None)

    # ==================================================================
    # Transports
    # ==================================================================

    def _init_options(self) -> InitializationOptions:
        return InitializationOptions(
            server_name="stinger-mcp",
            server_version="0.1.0",
            capabilities=self._server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )

    async def run_stdio(self) -> None:
        """Run the MCP server over the *stdio* transport."""
        self._loop = asyncio.get_running_loop()
        self._connection = create_mqtt_connection()
        self._load_plugins()
        self._start_discovery()

        try:
            async with mcp.server.stdio.stdio_server() as (read, write):
                await self._server.run(read, write, self._init_options())
        finally:
            if self._connection is not None:
                logger.info("Shutting down MQTT connection")

    async def run_sse(
        self, host: str = "0.0.0.0", port: int = 8000
    ) -> None:
        """Run the MCP server over the *SSE* transport."""
        try:
            from mcp.server.sse import SseServerTransport
            from starlette.applications import Starlette
            from starlette.requests import Request
            from starlette.routing import Mount, Route
            import uvicorn
        except ImportError as exc:
            raise RuntimeError(
                "SSE transport requires additional packages. "
                "Install with:  pip install 'stinger-python-utils[mcp]'"
            ) from exc

        self._loop = asyncio.get_running_loop()
        self._connection = create_mqtt_connection()
        self._load_plugins()
        self._start_discovery()

        sse = SseServerTransport("/messages/")

        async def handle_sse(request: Request) -> None:
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as (read, write):
                await self._server.run(read, write, self._init_options())

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        config = uvicorn.Config(app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()
