import json
import uuid

import pytest
from pydantic import BaseModel, Field
from typing import Optional

from stinger_python_utils.message_creator import MessageCreator


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

class SimpleModel(BaseModel):
    name: str
    value: int


class AliasModel(BaseModel):
    model_config = {"populate_by_name": True}

    my_name: str = Field(alias="myName")


TOPIC = "test/topic"
RESPONSE_TOPIC = "test/response"
SIMPLE = SimpleModel(name="hello", value=42)
ALIAS = AliasModel(myName="world")
BINARY_PAYLOAD = b"\x00\x01\x02\x03"
CONTENT_TYPE = "application/octet-stream"


# ---------------------------------------------------------------------------
# signal_message
# ---------------------------------------------------------------------------

class TestSignalMessage:
    def test_topic(self):
        msg = MessageCreator.signal_message(TOPIC, SIMPLE)
        assert msg.topic == TOPIC

    def test_payload_is_json(self):
        msg = MessageCreator.signal_message(TOPIC, SIMPLE)
        data = json.loads(msg.payload)
        assert data == {"name": "hello", "value": 42}

    def test_payload_uses_alias(self):
        msg = MessageCreator.signal_message(TOPIC, ALIAS)
        data = json.loads(msg.payload)
        assert "myName" in data

    def test_qos(self):
        msg = MessageCreator.signal_message(TOPIC, SIMPLE)
        assert msg.qos == 1

    def test_not_retained(self):
        msg = MessageCreator.signal_message(TOPIC, SIMPLE)
        assert msg.retain is False

    def test_content_type(self):
        msg = MessageCreator.signal_message(TOPIC, SIMPLE)
        assert msg.content_type == "application/json"


# ---------------------------------------------------------------------------
# status_message
# ---------------------------------------------------------------------------

class TestStatusMessage:
    def test_topic(self):
        msg = MessageCreator.status_message(TOPIC, SIMPLE, expiry_seconds=60)
        assert msg.topic == TOPIC

    def test_payload_is_json(self):
        msg = MessageCreator.status_message(TOPIC, SIMPLE, expiry_seconds=60)
        data = json.loads(msg.payload)
        assert data == {"name": "hello", "value": 42}

    def test_retained(self):
        msg = MessageCreator.status_message(TOPIC, SIMPLE, expiry_seconds=60)
        assert msg.retain is True

    def test_expiry(self):
        msg = MessageCreator.status_message(TOPIC, SIMPLE, expiry_seconds=120)
        assert msg.message_expiry_interval == 120

    def test_content_type(self):
        msg = MessageCreator.status_message(TOPIC, SIMPLE, expiry_seconds=60)
        assert msg.content_type == "application/json"


# ---------------------------------------------------------------------------
# error_response_message
# ---------------------------------------------------------------------------

class TestErrorResponseMessage:
    def test_topic(self):
        msg = MessageCreator.error_response_message(TOPIC, return_code=500)
        assert msg.topic == TOPIC

    def test_payload_empty_json(self):
        msg = MessageCreator.error_response_message(TOPIC, return_code=500)
        assert msg.payload == b"{}"

    def test_return_code_in_user_properties(self):
        msg = MessageCreator.error_response_message(TOPIC, return_code=404)
        assert msg.user_properties is not None
        assert msg.user_properties["ReturnCode"] == "404"

    def test_correlation_id_as_string(self):
        msg = MessageCreator.error_response_message(TOPIC, return_code=500, correlation_id="abc-123")
        assert msg.correlation_data == b"abc-123"

    def test_correlation_id_as_bytes(self):
        cid = b"\xde\xad\xbe\xef"
        msg = MessageCreator.error_response_message(TOPIC, return_code=500, correlation_id=cid)
        assert msg.correlation_data == cid

    def test_correlation_id_none(self):
        msg = MessageCreator.error_response_message(TOPIC, return_code=500, correlation_id=None)
        assert msg.correlation_data is None

    def test_debug_info_added(self):
        msg = MessageCreator.error_response_message(
            TOPIC, return_code=500, debug_info="something went wrong"
        )
        assert msg.user_properties is not None
        assert msg.user_properties["DebugInfo"] == "something went wrong"

    def test_debug_info_absent_by_default(self):
        msg = MessageCreator.error_response_message(TOPIC, return_code=500)
        assert msg.user_properties is not None
        assert "DebugInfo" not in msg.user_properties


# ---------------------------------------------------------------------------
# response_message (BaseModel path)
# ---------------------------------------------------------------------------

class TestResponseMessage:
    def test_topic(self):
        msg = MessageCreator.response_message(RESPONSE_TOPIC, SIMPLE, return_code=200)
        assert msg.topic == RESPONSE_TOPIC

    def test_payload_is_json(self):
        msg = MessageCreator.response_message(RESPONSE_TOPIC, SIMPLE, return_code=200)
        data = json.loads(msg.payload)
        assert data == {"name": "hello", "value": 42}

    def test_content_type_for_basemodel(self):
        msg = MessageCreator.response_message(RESPONSE_TOPIC, SIMPLE, return_code=200)
        assert msg.content_type == "application/json"

    def test_return_code_in_user_properties(self):
        msg = MessageCreator.response_message(RESPONSE_TOPIC, SIMPLE, return_code=200)
        assert msg.user_properties is not None
        assert msg.user_properties["ReturnCode"] == "200"

    def test_correlation_id_as_string(self):
        msg = MessageCreator.response_message(
            RESPONSE_TOPIC, SIMPLE, return_code=200, correlation_id="corr-1"
        )
        assert msg.correlation_data == b"corr-1"

    def test_correlation_id_as_bytes(self):
        cid = b"\x01\x02"
        msg = MessageCreator.response_message(
            RESPONSE_TOPIC, SIMPLE, return_code=200, correlation_id=cid
        )
        assert msg.correlation_data == cid

    def test_not_retained(self):
        msg = MessageCreator.response_message(RESPONSE_TOPIC, SIMPLE, return_code=200)
        assert msg.retain is False


# ---------------------------------------------------------------------------
# property_state_message
# ---------------------------------------------------------------------------

class TestPropertyStateMessage:
    def test_topic(self):
        msg = MessageCreator.property_state_message(TOPIC, SIMPLE)
        assert msg.topic == TOPIC

    def test_payload_is_json(self):
        msg = MessageCreator.property_state_message(TOPIC, SIMPLE)
        data = json.loads(msg.payload)
        assert data == {"name": "hello", "value": 42}

    def test_retained(self):
        msg = MessageCreator.property_state_message(TOPIC, SIMPLE)
        assert msg.retain is True

    def test_content_type(self):
        msg = MessageCreator.property_state_message(TOPIC, SIMPLE)
        assert msg.content_type == "application/json"

    def test_state_version_set(self):
        msg = MessageCreator.property_state_message(TOPIC, SIMPLE, state_version=7)
        assert msg.user_properties is not None
        assert msg.user_properties["PropertyVersion"] == "7"

    def test_no_state_version_by_default(self):
        msg = MessageCreator.property_state_message(TOPIC, SIMPLE)
        assert msg.user_properties is None or "PropertyVersion" not in msg.user_properties


# ---------------------------------------------------------------------------
# property_update_request_message
# ---------------------------------------------------------------------------

class TestPropertyUpdateRequestMessage:
    def test_topic(self):
        msg = MessageCreator.property_update_request_message(
            TOPIC, SIMPLE, version="2", response_topic=RESPONSE_TOPIC
        )
        assert msg.topic == TOPIC

    def test_payload_is_json(self):
        msg = MessageCreator.property_update_request_message(
            TOPIC, SIMPLE, version="2", response_topic=RESPONSE_TOPIC
        )
        data = json.loads(msg.payload)
        assert data == {"name": "hello", "value": 42}

    def test_response_topic(self):
        msg = MessageCreator.property_update_request_message(
            TOPIC, SIMPLE, version="2", response_topic=RESPONSE_TOPIC
        )
        assert msg.response_topic == RESPONSE_TOPIC

    def test_version_in_user_properties(self):
        msg = MessageCreator.property_update_request_message(
            TOPIC, SIMPLE, version="3", response_topic=RESPONSE_TOPIC
        )
        assert msg.user_properties is not None
        assert msg.user_properties["PropertyVersion"] == "3"

    def test_correlation_id(self):
        msg = MessageCreator.property_update_request_message(
            TOPIC, SIMPLE, version="1", response_topic=RESPONSE_TOPIC, correlation_id="cid-99"
        )
        assert msg.correlation_data == b"cid-99"

    def test_content_type(self):
        msg = MessageCreator.property_update_request_message(
            TOPIC, SIMPLE, version="1", response_topic=RESPONSE_TOPIC
        )
        assert msg.content_type == "application/json"

    def test_not_retained(self):
        msg = MessageCreator.property_update_request_message(
            TOPIC, SIMPLE, version="1", response_topic=RESPONSE_TOPIC
        )
        assert msg.retain is False


# ---------------------------------------------------------------------------
# property_response_message
# ---------------------------------------------------------------------------

class TestPropertyResponseMessage:
    def test_topic(self):
        msg = MessageCreator.property_response_message(
            RESPONSE_TOPIC, SIMPLE, version="1", return_code=200
        )
        assert msg.topic == RESPONSE_TOPIC

    def test_payload_is_json(self):
        msg = MessageCreator.property_response_message(
            RESPONSE_TOPIC, SIMPLE, version="1", return_code=200
        )
        data = json.loads(msg.payload)
        assert data == {"name": "hello", "value": 42}

    def test_return_code_and_version_in_user_properties(self):
        msg = MessageCreator.property_response_message(
            RESPONSE_TOPIC, SIMPLE, version="5", return_code=200
        )
        assert msg.user_properties is not None
        assert msg.user_properties["ReturnCode"] == "200"
        assert msg.user_properties["PropertyVersion"] == "5"

    def test_debug_info_added(self):
        msg = MessageCreator.property_response_message(
            RESPONSE_TOPIC, SIMPLE, version="1", return_code=500, debug_info="oops"
        )
        assert msg.user_properties is not None
        assert msg.user_properties["DebugInfo"] == "oops"

    def test_content_type(self):
        msg = MessageCreator.property_response_message(
            RESPONSE_TOPIC, SIMPLE, version="1", return_code=200
        )
        assert msg.content_type == "application/json"

    def test_correlation_id(self):
        msg = MessageCreator.property_response_message(
            RESPONSE_TOPIC, SIMPLE, version="1", return_code=200, correlation_id="xyz"
        )
        assert msg.correlation_data == b"xyz"


# ---------------------------------------------------------------------------
# request_message
# ---------------------------------------------------------------------------

class TestRequestMessage:
    def test_topic(self):
        msg = MessageCreator.request_message(TOPIC, SIMPLE, response_topic=RESPONSE_TOPIC)
        assert msg.topic == TOPIC

    def test_payload_is_json(self):
        msg = MessageCreator.request_message(TOPIC, SIMPLE, response_topic=RESPONSE_TOPIC)
        data = json.loads(msg.payload)
        assert data == {"name": "hello", "value": 42}

    def test_response_topic(self):
        msg = MessageCreator.request_message(TOPIC, SIMPLE, response_topic=RESPONSE_TOPIC)
        assert msg.response_topic == RESPONSE_TOPIC

    def test_content_type(self):
        msg = MessageCreator.request_message(TOPIC, SIMPLE, response_topic=RESPONSE_TOPIC)
        assert msg.content_type == "application/json"

    def test_auto_generates_correlation_id(self):
        msg = MessageCreator.request_message(TOPIC, SIMPLE, response_topic=RESPONSE_TOPIC)
        assert msg.correlation_data is not None
        # Should be a valid UUID
        parsed = uuid.UUID(msg.correlation_data.decode("utf-8"))
        assert parsed.version == 4

    def test_explicit_correlation_id_string(self):
        msg = MessageCreator.request_message(
            TOPIC, SIMPLE, response_topic=RESPONSE_TOPIC, correlation_id="my-corr"
        )
        assert msg.correlation_data == b"my-corr"

    def test_explicit_correlation_id_bytes(self):
        cid = b"\xca\xfe"
        msg = MessageCreator.request_message(
            TOPIC, SIMPLE, response_topic=RESPONSE_TOPIC, correlation_id=cid
        )
        assert msg.correlation_data == cid

    def test_not_retained(self):
        msg = MessageCreator.request_message(TOPIC, SIMPLE, response_topic=RESPONSE_TOPIC)
        assert msg.retain is False


# ---------------------------------------------------------------------------
# binary_signal_message
# ---------------------------------------------------------------------------

class TestBinarySignalMessage:
    def test_topic(self):
        msg = MessageCreator.binary_signal_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE)
        assert msg.topic == TOPIC

    def test_payload(self):
        msg = MessageCreator.binary_signal_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE)
        assert msg.payload == BINARY_PAYLOAD

    def test_content_type(self):
        msg = MessageCreator.binary_signal_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE)
        assert msg.content_type == CONTENT_TYPE

    def test_not_retained(self):
        msg = MessageCreator.binary_signal_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE)
        assert msg.retain is False


# ---------------------------------------------------------------------------
# binary_status_message
# ---------------------------------------------------------------------------

class TestBinaryStatusMessage:
    def test_retained(self):
        msg = MessageCreator.binary_status_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, expiry_seconds=30)
        assert msg.retain is True

    def test_expiry(self):
        msg = MessageCreator.binary_status_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, expiry_seconds=30)
        assert msg.message_expiry_interval == 30

    def test_content_type(self):
        msg = MessageCreator.binary_status_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, expiry_seconds=30)
        assert msg.content_type == CONTENT_TYPE


# ---------------------------------------------------------------------------
# binary_response_message
# ---------------------------------------------------------------------------

class TestBinaryResponseMessage:
    def test_topic(self):
        msg = MessageCreator.binary_response_message(RESPONSE_TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, return_code=200)
        assert msg.topic == RESPONSE_TOPIC

    def test_payload(self):
        msg = MessageCreator.binary_response_message(RESPONSE_TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, return_code=200)
        assert msg.payload == BINARY_PAYLOAD

    def test_return_code(self):
        msg = MessageCreator.binary_response_message(RESPONSE_TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, return_code=404)
        assert msg.user_properties is not None
        assert msg.user_properties["ReturnCode"] == "404"

    def test_correlation_id(self):
        msg = MessageCreator.binary_response_message(
            RESPONSE_TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, return_code=200, correlation_id="c1"
        )
        assert msg.correlation_data == b"c1"


# ---------------------------------------------------------------------------
# binary_property_state_message
# ---------------------------------------------------------------------------

class TestBinaryPropertyStateMessage:
    def test_retained(self):
        msg = MessageCreator.binary_property_state_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE)
        assert msg.retain is True

    def test_state_version_set(self):
        msg = MessageCreator.binary_property_state_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, state_version=3)
        assert msg.user_properties is not None
        assert msg.user_properties["PropertyVersion"] == "3"

    def test_no_state_version_by_default(self):
        msg = MessageCreator.binary_property_state_message(TOPIC, BINARY_PAYLOAD, CONTENT_TYPE)
        assert msg.user_properties is None or "PropertyVersion" not in msg.user_properties


# ---------------------------------------------------------------------------
# binary_property_update_request_message
# ---------------------------------------------------------------------------

class TestBinaryPropertyUpdateRequestMessage:
    def test_response_topic(self):
        msg = MessageCreator.binary_property_update_request_message(
            TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, version="1", response_topic=RESPONSE_TOPIC
        )
        assert msg.response_topic == RESPONSE_TOPIC

    def test_version_in_user_properties(self):
        msg = MessageCreator.binary_property_update_request_message(
            TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, version="9", response_topic=RESPONSE_TOPIC
        )
        assert msg.user_properties is not None
        assert msg.user_properties["PropertyVersion"] == "9"

    def test_correlation_id(self):
        msg = MessageCreator.binary_property_update_request_message(
            TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, version="1",
            response_topic=RESPONSE_TOPIC, correlation_id="cid"
        )
        assert msg.correlation_data == b"cid"


# ---------------------------------------------------------------------------
# binary_property_response_message
# ---------------------------------------------------------------------------

class TestBinaryPropertyResponseMessage:
    def test_return_code_and_version(self):
        msg = MessageCreator.binary_property_response_message(
            RESPONSE_TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, version="2", return_code=200
        )
        assert msg.user_properties is not None
        assert msg.user_properties["ReturnCode"] == "200"
        assert msg.user_properties["PropertyVersion"] == "2"

    def test_debug_info(self):
        msg = MessageCreator.binary_property_response_message(
            RESPONSE_TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, version="1",
            return_code=500, debug_info="bad input"
        )
        assert msg.user_properties is not None
        assert msg.user_properties["DebugInfo"] == "bad input"

    def test_no_debug_info_by_default(self):
        msg = MessageCreator.binary_property_response_message(
            RESPONSE_TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, version="1", return_code=200
        )
        assert msg.user_properties is not None
        assert "DebugInfo" not in msg.user_properties


# ---------------------------------------------------------------------------
# binary_request_message
# ---------------------------------------------------------------------------

class TestBinaryRequestMessage:
    def test_response_topic(self):
        msg = MessageCreator.binary_request_message(
            TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, response_topic=RESPONSE_TOPIC
        )
        assert msg.response_topic == RESPONSE_TOPIC

    def test_auto_generates_correlation_id(self):
        msg = MessageCreator.binary_request_message(
            TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, response_topic=RESPONSE_TOPIC
        )
        assert msg.correlation_data is not None
        parsed = uuid.UUID(msg.correlation_data.decode("utf-8"))
        assert parsed.version == 4

    def test_explicit_correlation_id(self):
        msg = MessageCreator.binary_request_message(
            TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, response_topic=RESPONSE_TOPIC,
            correlation_id="explicit-cid"
        )
        assert msg.correlation_data == b"explicit-cid"

    def test_not_retained(self):
        msg = MessageCreator.binary_request_message(
            TOPIC, BINARY_PAYLOAD, CONTENT_TYPE, response_topic=RESPONSE_TOPIC
        )
        assert msg.retain is False
