"""Tests for MessageCreator class"""
import pytest
from pydantic import BaseModel
from stinger_python_utils.message_creator import MessageCreator


class SamplePayload(BaseModel):
    """Sample payload for testing"""
    name: str
    value: int


class TestSignalMessage:
    def test_signal_message_creates_message(self):
        """Test that signal_message creates a message with correct properties"""
        payload = SamplePayload(name="test", value=42)
        message = MessageCreator.signal_message("test/topic", payload)
        
        assert message.topic == "test/topic"
        assert message.qos == 1
        assert message.retain is False
        assert b'"name":"test"' in message.payload


class TestStatusMessage:
    def test_status_message_creates_retained_message(self):
        """Test that status_message creates a retained message with expiry"""
        payload = SamplePayload(name="status", value=100)
        message = MessageCreator.status_message("status/topic", payload, 3600)
        
        assert message.topic == "status/topic"
        assert message.qos == 1
        assert message.retain is True
        assert message.message_expiry_interval == 3600


class TestErrorResponseMessage:
    def test_error_response_with_string_correlation_id(self):
        """Test error response with string correlation ID"""
        message = MessageCreator.error_response_message(
            "error/topic",
            return_code=500,
            correlation_id="abc-123"
        )
        
        assert message.topic == "error/topic"
        assert message.qos == 1
        assert message.retain is False
        assert message.user_properties["ReturnCode"] == "500"
        assert message.correlation_data == b"abc-123"

    def test_error_response_with_bytes_correlation_id(self):
        """Test error response with bytes correlation ID"""
        message = MessageCreator.error_response_message(
            "error/topic",
            return_code=400,
            correlation_id=b"xyz-789"
        )
        
        assert message.correlation_data == b"xyz-789"
        assert message.user_properties["ReturnCode"] == "400"

    def test_error_response_with_debug_info(self):
        """Test error response includes debug info"""
        message = MessageCreator.error_response_message(
            "error/topic",
            return_code=500,
            debug_info="Something went wrong"
        )
        
        assert message.user_properties["DebugInfo"] == "Something went wrong"


class TestResponseMessage:
    def test_response_message_with_pydantic_model(self):
        """Test response message with Pydantic model"""
        payload = SamplePayload(name="response", value=200)
        message = MessageCreator.response_message(
            "response/topic",
            payload,
            return_code=200,
            correlation_id="req-123"
        )
        
        assert message.topic == "response/topic"
        assert message.qos == 1
        assert message.user_properties["ReturnCode"] == "200"
        assert message.correlation_data == b"req-123"

    def test_response_message_with_string(self):
        """Test response message with string payload"""
        message = MessageCreator.response_message(
            "response/topic",
            "success",
            return_code=200
        )
        
        assert message.payload == b"success"

    def test_response_message_with_bytes(self):
        """Test response message with bytes payload"""
        message = MessageCreator.response_message(
            "response/topic",
            b"binary data",
            return_code=200
        )
        
        assert message.payload == b"binary data"


class TestPropertyStateMessage:
    def test_property_state_message_basic(self):
        """Test property state message creation"""
        payload = SamplePayload(name="property", value=42)
        message = MessageCreator.property_state_message("property/state", payload)
        
        assert message.topic == "property/state"
        assert message.qos == 1
        assert message.retain is True
        assert message.content_type == "application/json"

    def test_property_state_message_with_version(self):
        """Test property state message with version"""
        payload = SamplePayload(name="property", value=42)
        message = MessageCreator.property_state_message(
            "property/state",
            payload,
            state_version=5
        )
        
        assert message.user_properties["PropertyVersion"] == "5"


class TestPropertyUpdateRequestMessage:
    def test_property_update_request_message(self):
        """Test property update request message"""
        payload = SamplePayload(name="new_value", value=99)
        message = MessageCreator.property_update_request_message(
            "property/update",
            payload,
            version="1.0",
            response_topic="property/response",
            correlation_id="update-123"
        )
        
        assert message.topic == "property/update"
        assert message.response_topic == "property/response"
        assert message.user_properties["PropertyVersion"] == "1.0"
        assert message.correlation_data == b"update-123"


class TestPropertyResponseMessage:
    def test_property_response_message(self):
        """Test property response message"""
        payload = SamplePayload(name="updated", value=99)
        message = MessageCreator.property_response_message(
            "property/response",
            payload,
            version="1.0",
            return_code=200,
            correlation_id="update-123"
        )
        
        assert message.topic == "property/response"
        assert message.user_properties["ReturnCode"] == "200"
        assert message.user_properties["PropertyVersion"] == "1.0"
        assert message.correlation_data == b"update-123"

    def test_property_response_message_with_debug_info(self):
        """Test property response message with debug info"""
        payload = SamplePayload(name="updated", value=99)
        message = MessageCreator.property_response_message(
            "property/response",
            payload,
            version="1.0",
            return_code=500,
            debug_info="Update failed"
        )
        
        assert message.user_properties["DebugInfo"] == "Update failed"


class TestRequestMessage:
    def test_request_message_auto_correlation_id(self):
        """Test request message generates correlation ID if not provided"""
        payload = SamplePayload(name="request", value=1)
        message = MessageCreator.request_message(
            "request/topic",
            payload,
            response_topic="response/topic"
        )
        
        assert message.topic == "request/topic"
        assert message.response_topic == "response/topic"
        assert message.correlation_data is not None
        assert len(message.correlation_data) > 0

    def test_request_message_with_correlation_id(self):
        """Test request message with provided correlation ID"""
        payload = SamplePayload(name="request", value=1)
        message = MessageCreator.request_message(
            "request/topic",
            payload,
            response_topic="response/topic",
            correlation_id="req-456"
        )
        
        assert message.correlation_data == b"req-456"
