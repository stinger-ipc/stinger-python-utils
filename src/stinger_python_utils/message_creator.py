from pyqttier.message import Message
from pydantic import BaseModel
from typing import Union, Optional
import uuid


class MessageCreator:

    @classmethod
    def signal_message(cls, topic: str, payload: BaseModel) -> Message:
        return Message(
            topic=topic,
            payload=payload.model_dump_json(by_alias=True).encode("utf-8"),
            qos=1,
            retain=False,
        )

    @classmethod
    def status_message(
        cls, topic, status_message: BaseModel, expiry_seconds: int
    ) -> Message:
        return Message(
            topic=topic,
            payload=status_message.model_dump_json(by_alias=True).encode("utf-8"),
            qos=1,
            retain=True,
            message_expiry_interval=expiry_seconds,
        )

    @classmethod
    def error_response_message(
        cls,
        topic: str,
        return_code: int,
        correlation_id: Union[str, bytes, None] = None,
        debug_info: Optional[str] = None,
    ) -> Message:
        """
        This could be used for a response to a request, but where there was an error fulfilling the request.
        """
        msg_obj = Message(
            topic=topic,
            payload=b"{}",
            qos=1,
            retain=False,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
            user_properties={"ReturnCode": str(return_code)},
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
        response_obj: BaseModel | str | bytes,
        return_code: int,
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
        msg_obj = Message(
            topic=response_topic,
            payload=payload,
            qos=1,
            retain=False,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
            user_properties={"ReturnCode": str(return_code)},
        )
        return msg_obj

    @classmethod
    def property_state_message(
        cls, topic: str, state_obj: BaseModel, state_version: Optional[int] = None
    ) -> Message:
        """
        Creates a retained message representing the state/value of a property.
        """
        msg_obj = Message(
            topic=topic,
            payload=state_obj.model_dump_json(by_alias=True).encode("utf-8"),
            qos=1,
            retain=True,
        )
        if state_version is not None:
            msg_obj.user_properties = {"PropertyVersion": str(state_version)}
        return msg_obj

    @classmethod
    def property_update_request_message(
        cls,
        topic: str,
        property_obj: BaseModel,
        version: str,
        response_topic: str,
        correlation_id: Union[str, bytes, None] = None,
    ) -> Message:
        """
        Creates a message representing a request to update a property.
        """
        msg_obj = Message(
            topic=topic,
            payload=property_obj.model_dump_json(by_alias=True).encode("utf-8"),
            qos=1,
            retain=False,
            response_topic=response_topic,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
            user_properties={"PropertyVersion": str(version)},
        )
        return msg_obj

    @classmethod
    def property_response_message(
        cls,
        response_topic: str,
        property_obj: BaseModel,
        version: str,
        return_code: int,
        correlation_id: Union[str, bytes, None] = None,
        debug_info: Optional[str] = None,
    ) -> Message:
        """
        Creates a message representing a response to a property update request.
        """
        msg_obj = Message(
            topic=response_topic,
            payload=property_obj.model_dump_json(by_alias=True).encode("utf-8"),
            qos=1,
            retain=False,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
            user_properties={
                "ReturnCode": str(return_code),
                "PropertyVersion": str(version),
            },
        )
        if (
            debug_info is not None and msg_obj.user_properties is not None
        ):  # user_properties should never be None here, but checking to satisfy type checker
            msg_obj.user_properties["DebugInfo"] = debug_info
        return msg_obj

    @classmethod
    def request_message(
        cls,
        topic: str,
        request_obj: BaseModel,
        response_topic: str,
        correlation_id: Union[str, bytes, None] = None,
    ) -> Message:
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        msg_obj = Message(
            topic=topic,
            payload=request_obj.model_dump_json(by_alias=True).encode("utf-8"),
            qos=1,
            retain=False,
            response_topic=response_topic,
            correlation_data=(
                correlation_id.encode("utf-8")
                if isinstance(correlation_id, str)
                else correlation_id
            ),
        )
        return msg_obj
