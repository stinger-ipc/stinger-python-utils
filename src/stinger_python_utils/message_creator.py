from pystingerconniface import Message
from pydantic import BaseModel
from typing import Union, Optional
import uuid
from .return_codes import MethodReturnCode


class MessageCreator:

    @staticmethod
    def _validate_topic(topic: str, param_name: str = "topic") -> None:
        if "+" in topic:
            raise ValueError(
                f"{param_name} must not contain '+', got: {topic!r}"
            )

    @classmethod
    def signal_message(cls, topic: str, payload: BaseModel) -> Message:
        return cls.binary_signal_message(
            topic,
            payload.model_dump_json(by_alias=True).encode("utf-8"),
            "application/json",
        )

    @classmethod
    def binary_signal_message(cls, topic: str, payload: bytes, content_type: str) -> Message:
        cls._validate_topic(topic)
        return Message(
            topic=topic,
            payload=payload,
            qos=1,
            retain=False,
            content_type=content_type,
        )

    @classmethod
    def command_message(cls, topic: str, payload: BaseModel, qos: int = 2) -> Message:
        return cls.binary_command_message(
            topic,
            payload.model_dump_json(by_alias=True).encode("utf-8"),
            "application/json",
            qos=qos,
        )

    @classmethod
    def binary_command_message(
        cls, topic: str, payload: bytes, content_type: str, qos: int = 2
    ) -> Message:
        """
        A command is a signal in reverse: the client publishes it to the server and never
        learns whether it was acted on.  There is therefore no response topic and no
        correlation data on the message.
        """
        cls._validate_topic(topic)
        return Message(
            topic=topic,
            payload=payload,
            qos=qos,
            retain=False,
            content_type=content_type,
        )

    @classmethod
    def status_message(
        cls, topic: str, status_message: BaseModel, expiry_seconds: int
    ) -> Message:
        return cls.binary_status_message(
            topic,
            status_message.model_dump_json(by_alias=True).encode("utf-8"),
            "application/json",
            expiry_seconds=expiry_seconds,
        )

    @classmethod
    def binary_status_message(
        cls, topic: str, payload: bytes, content_type: str, expiry_seconds: int
    ) -> Message:
        cls._validate_topic(topic)
        return Message(
            topic=topic,
            payload=payload,
            qos=1,
            retain=True,
            message_expiry_interval=expiry_seconds,
            content_type=content_type,
        )

    @classmethod
    def error_response_message(
        cls,
        topic: str,
        return_code: Union[int, MethodReturnCode],
        correlation_id: Union[str, bytes, None] = None,
        debug_info: Optional[str] = None,
        content_type: str = "application/json",
    ) -> Message:
        """
        This could be used for a response to a request, but where there was an error fulfilling the request.

        An error carries no data -- the return code and any debug info travel in MQTT user
        properties -- so the body is an empty JSON object for a JSON response and empty
        bytes for any other content type, since a protobuf consumer would reject "{}".
        """
        cls._validate_topic(topic)
        rc = (
            return_code.value
            if isinstance(return_code, MethodReturnCode)
            else return_code
        )
        msg_obj = Message(
            topic=topic,
            payload=b"{}" if content_type == "application/json" else b"",
            qos=1,
            retain=False,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
            user_properties={"ReturnCode": str(rc)},
            content_type=content_type,
        )
        if (
            debug_info is not None and msg_obj.user_properties is not None
        ):  # user_properties should never be None here, but checking to satisfy type checker
            msg_obj.user_properties["DebugInfo"] = debug_info
        return msg_obj

    @classmethod
    def response_message(
        cls,
        response_topic: str,
        response_obj: Union[BaseModel, str, bytes],
        return_code: Union[int, MethodReturnCode],
        correlation_id: Union[str, bytes, None] = None,
    ) -> Message:
        """
        This could be used for a successful response to a request.
        """
        if isinstance(response_obj, BaseModel):
            payload = response_obj.model_dump_json(by_alias=True).encode("utf-8")
        elif isinstance(response_obj, str):
            payload = response_obj.encode("utf-8")
        else:
            payload = response_obj
        return cls.binary_response_message(
            response_topic, payload, "application/json", return_code, correlation_id
        )

    @classmethod
    def binary_response_message(
        cls,
        response_topic: str,
        payload: bytes,
        content_type: str,
        return_code: Union[int, MethodReturnCode],
        correlation_id: Union[str, bytes, None] = None,
    ) -> Message:
        cls._validate_topic(response_topic, "response_topic")
        rc = (
            return_code.value
            if isinstance(return_code, MethodReturnCode)
            else return_code
        )
        return Message(
            topic=response_topic,
            payload=payload,
            qos=1,
            retain=False,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
            user_properties={"ReturnCode": str(rc)},
            content_type=content_type,
        )

    @classmethod
    def property_state_message(
        cls, topic: str, state_obj: BaseModel, state_version: Optional[int] = None
    ) -> Message:
        """
        Creates a retained message representing the state/value of a property.
        """
        return cls.binary_property_state_message(
            topic,
            state_obj.model_dump_json(by_alias=True).encode("utf-8"),
            "application/json",
            state_version,
        )

    @classmethod
    def binary_property_state_message(
        cls, topic: str, payload: bytes, content_type: str, state_version: Optional[int] = None
    ) -> Message:
        cls._validate_topic(topic)
        msg_obj = Message(
            topic=topic,
            payload=payload,
            qos=1,
            retain=True,
            content_type=content_type,
        )
        if state_version is not None:
            msg_obj.user_properties = {"PropertyVersion": str(state_version)}
        return msg_obj

    @classmethod
    def property_update_request_message(
        cls,
        topic: str,
        property_obj: BaseModel,
        version: Optional[int],
        response_topic: str,
        correlation_id: Union[str, bytes, None] = None,
    ) -> Message:
        """
        Creates a message representing a request to update a property.
        """
        return cls.binary_property_update_request_message(
            topic,
            property_obj.model_dump_json(by_alias=True).encode("utf-8"),
            "application/json",
            version,
            response_topic,
            correlation_id,
        )

    @classmethod
    def binary_property_update_request_message(
        cls,
        topic: str,
        payload: bytes,
        content_type: str,
        version: Optional[int],
        response_topic: str,
        correlation_id: Union[str, bytes, None] = None,
    ) -> Message:
        cls._validate_topic(topic)
        cls._validate_topic(response_topic, "response_topic")
        msg = Message(
            topic=topic,
            payload=payload,
            qos=1,
            retain=False,
            content_type=content_type,
            response_topic=response_topic,
            message_expiry_interval=5,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
        )
        if version is not None:
            msg.user_properties = {"PropertyVersion": str(version)}
        return msg

    @classmethod
    def property_response_message(
        cls,
        response_topic: str,
        property_obj: BaseModel,
        version: Optional[int],
        return_code: Union[int, MethodReturnCode],
        correlation_id: Union[str, bytes, None] = None,
        debug_info: Optional[str] = None,
    ) -> Message:
        """
        Creates a message representing a response to a property update request.
        """
        return cls.binary_property_response_message(
            response_topic,
            property_obj.model_dump_json(by_alias=True).encode("utf-8"),
            "application/json",
            version,
            return_code,
            correlation_id,
            debug_info,
        )

    @classmethod
    def binary_property_response_message(
        cls,
        response_topic: str,
        payload: bytes,
        content_type: str,
        version: Optional[int],
        return_code: Union[int, MethodReturnCode],
        correlation_id: Union[str, bytes, None] = None,
        debug_info: Optional[str] = None,
    ) -> Message:
        cls._validate_topic(response_topic, "response_topic")
        rc = (
            return_code.value
            if isinstance(return_code, MethodReturnCode)
            else return_code
        )
        msg_obj = Message(
            topic=response_topic,
            payload=payload,
            qos=1,
            retain=False,
            content_type=content_type,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
            user_properties={
                "ReturnCode": str(rc),
            },
        )
        if msg_obj.user_properties is not None:  # user_properties should never be None here, but checking to satisfy type checker
            if version is not None:
                msg_obj.user_properties["PropertyVersion"] = str(version)
            if debug_info is not None: 
                msg_obj.user_properties["DebugInfo"] = debug_info
        return msg_obj

    @classmethod
    def request_message(
        cls,
        topic: str,
        request_obj: BaseModel,
        response_topic: str,
        correlation_id: Union[str, bytes, None] = None,
        expiry_seconds: Optional[int] = None,
    ) -> Message:
        return cls.binary_request_message(
            topic,
            request_obj.model_dump_json(by_alias=True).encode("utf-8"),
            "application/json",
            response_topic,
            correlation_id,
            expiry_seconds,
        )

    @classmethod
    def binary_request_message(
        cls,
        topic: str,
        payload: bytes,
        content_type: str,
        response_topic: str,
        correlation_id: Union[str, bytes, None] = None,
        expiry_seconds: Optional[int] = None,
    ) -> Message:
        cls._validate_topic(topic)
        cls._validate_topic(response_topic, "response_topic")
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        msg = Message(
            topic=topic,
            payload=payload,
            qos=1,
            retain=False,
            response_topic=response_topic,
            content_type=content_type,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
        )
        if expiry_seconds is not None:
            msg.message_expiry_interval = expiry_seconds
        return msg
