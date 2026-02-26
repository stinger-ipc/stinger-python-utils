# stinger-python-utils

Shared utilities for Stinger Python services, providing convenient message creation for MQTT communication.



## Installation

```bash
uv add stinger-python-utils
```

## MessageCreator

`MessageCreator` is a utility class for creating MQTT messages with standardized properties and payloads.

### Basic Usage

```python
from pydantic import BaseModel
from stinger_python_utils.message_creator import MessageCreator

class MyPayload(BaseModel):
    name: str
    value: int

payload = MyPayload(name="test", value=42)
message = MessageCreator.signal_message("my/topic", payload)
```

### Methods

| Method | Purpose | Return Code |
|--------|---------|-------------|
| `signal_message(topic, payload)` | Send a signal with one-time delivery | QoS 1, no retain |
| `status_message(topic, payload, expiry_seconds)` | Send status that expires | QoS 1, retained, with expiry |
| `error_response_message(topic, return_code, correlation_id, debug_info)` | Error response to a request | QoS 1, user properties: `ReturnCode` |
| `response_message(topic, payload, return_code, correlation_id)` | Successful response to a request | QoS 1, user properties: `ReturnCode` |
| `property_state_message(topic, payload, state_version)` | Publish property state | QoS 1, retained, JSON content type |
| `property_update_request_message(topic, payload, version, response_topic, correlation_id)` | Request property update | QoS 1, user property: `PropertyVersion` |
| `property_response_message(topic, payload, version, return_code, correlation_id, debug_info)` | Respond to property update | QoS 1, user properties: `ReturnCode`, `PropertyVersion` |
| `request_message(topic, payload, response_topic, correlation_id)` | Send a request (auto-generates UUID if no correlation_id) | QoS 1, auto correlation ID |

### Example: Request/Response Pattern

```python
from pydantic import BaseModel
from stinger_python_utils.message_creator import MessageCreator

class Request(BaseModel):
    action: str

request = Request(action="start")
msg = MessageCreator.request_message(
    "devices/cmd",
    request,
    response_topic="devices/response"
)
# Returns a Message with auto-generated correlation ID
```

### Example: Error Response

```python
msg = MessageCreator.error_response_message(
    "devices/response",
    return_code=500,
    correlation_id="req-123",
    debug_info="Device not found"
)
# User properties include: ReturnCode=500, DebugInfo=Device not found
```

---

## MCP Server

`stinger-python-utils` includes an optional **Model Context Protocol (MCP) server** that exposes stinger-ipc services to AI coding assistants such as GitHub Copilot in VS Code.

The server discovers live stinger-ipc service instances over MQTT and dynamically registers them as MCP **resources** (properties and signal mailboxes) and **tools** (methods and writable property setters).  Functionality is provided by plugins — third-party packages that register against the `stinger_python_utils.mcp_plugins` stevedore entry-point namespace.

### Installation

Install with the `mcp` extra to pull in the MCP SDK, stevedore, and uvicorn:

```bash
pip install 'stinger-python-utils[mcp]'
# or with uv:
uv add 'stinger-python-utils[mcp]'
```

### MQTT Connection Configuration

The server connects to an MQTT broker using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_HOST` | `localhost` | Broker hostname or IP |
| `MQTT_PORT` | `1883` | Broker port |
| `MQTT_TRANSPORT` | `tcp` | `tcp`, `websocket`, or `unix` |
| `MQTT_CLIENT_ID` | *(random)* | MQTT client identifier |

### Running the Server

**stdio transport** (recommended for VS Code / Copilot):

```bash
stinger-mcp-server --transport stdio
```

**SSE transport** (for browser-based or remote clients):

```bash
stinger-mcp-server --transport sse --host 0.0.0.0 --port 8000
```

### Adding to VS Code (GitHub Copilot)

Add the server to your VS Code user or workspace MCP configuration.

**Option 1 — User settings** (`~/.vscode/mcp.json` or via *Settings → MCP*):

```json
{
  "servers": {
    "stinger": {
      "type": "stdio",
      "command": "stinger-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
        "MQTT_HOST": "localhost",
        "MQTT_PORT": "1883"
      }
    }
  }
}
```

**Option 2 — Workspace settings** (`.vscode/mcp.json` in your repo, checked into source control so the whole team shares the same configuration):

```json
{
  "servers": {
    "stinger": {
      "type": "stdio",
      "command": "stinger-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
        "MQTT_HOST": "localhost",
        "MQTT_PORT": "1883"
      }
    }
  }
}
```

Once saved, open the Copilot Chat panel, switch to **Agent** mode, and the stinger service tools and resources will be available.

> **Tip:** If `stinger-mcp-server` is installed inside a virtual environment rather than globally, use the full path to the executable, e.g. `"/path/to/.venv/bin/stinger-mcp-server"`.

**Option 3 — SSE transport** (connect to a server already running elsewhere, e.g. on a remote device or in a container):

First start the server with the SSE transport:

```bash
MQTT_HOST=192.168.1.100 stinger-mcp-server --transport sse --host 0.0.0.0 --port 8000
```

Then point VS Code at it in `.vscode/mcp.json`:

```json
{
  "servers": {
    "stinger": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

Replace `localhost` with the hostname or IP of the machine running the server.

### Writing a Plugin

Plugins provide the actual service-type knowledge to the MCP server.  Create a class that extends `StingerMCPPlugin` and register it as a stevedore entry-point:

**`my_service/mcp_plugin.py`**:

```python
from stinger_python_utils.mcp import (
    StingerMCPPlugin,
    SignalDefinition,
    PropertyDefinition,
    MethodDefinition,
)
from .client import MyServiceClient
from .discoverer import MyServiceDiscoverer

class MyServicePlugin(StingerMCPPlugin):

    def get_plugin_name(self) -> str:
        return "my_service"  # used as URI scheme: my_service://instance/...

    def get_discovery_class(self) -> type:
        return MyServiceDiscoverer

    def get_client_class(self) -> type:
        return MyServiceClient

    def get_signals(self) -> list[SignalDefinition]:
        return [
            SignalDefinition(name="status_changed", description="Emitted when device status changes"),
        ]

    def get_properties(self) -> list[PropertyDefinition]:
        return [
            PropertyDefinition(
                name="brightness",
                schema={
                    "type": "object",
                    "properties": {"value": {"type": "integer", "minimum": 0, "maximum": 100}},
                    "required": ["value"],
                },
                readonly=False,
                description="Brightness level (0–100)",
            ),
        ]

    def get_methods(self) -> list[MethodDefinition]:
        return [
            MethodDefinition(
                name="restart",
                arguments_schema={"type": "object", "properties": {}},
                description="Restart the device",
            ),
        ]
```

**`pyproject.toml`** of the plugin package:

```toml
[project.entry-points."stinger_python_utils.mcp_plugins"]
my_service = "my_service.mcp_plugin:MyServicePlugin"
```

Install the plugin package into the same environment as `stinger-python-utils[mcp]` and the server will discover it automatically on next start.

### MCP Resource and Tool Naming

For each discovered service instance the server exposes:

| MCP primitive | Name / URI pattern | Description |
|---------------|--------------------|-------------|
| Resource | `{plugin}://{instance_id}/property/{name}` | Current property value (JSON) |
| Resource | `{plugin}://{instance_id}/signal/{name}` | Mailbox of the last 10 signals (JSON array with timestamps) |
| Tool | `{plugin}_{instance_id}_{method_name}` | Calls a method on the instance |
| Tool | `{plugin}_{instance_id}_set_{property_name}` | Sets a writable property |

As instances come and go the tool and resource lists update automatically.

