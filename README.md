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

