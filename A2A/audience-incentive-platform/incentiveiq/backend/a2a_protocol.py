"""
A2A Protocol for AutoAudience <-> IncentiveIQ communication.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
import uuid


class AgentCard(BaseModel):
    agent_id: str
    organization: str
    name: str
    description: str
    capabilities: list[str]
    endpoint: str
    protocol_version: str = "1.0"


class A2AMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    sender_agent_id: str
    receiver_agent_id: str
    message_type: Literal[
        "data_request",
        "data_response",
        "info_request",
        "info_response",
        "incentive_request",
        "incentive_response",
        "error",
    ]
    subject: str
    body: str
    metadata: dict = Field(default_factory=dict)
    in_reply_to: Optional[str] = None


class ConversationState(BaseModel):
    conversation_id: str
    status: Literal["active", "complete", "error"] = "active"
    messages: list[A2AMessage] = Field(default_factory=list)
    workflow_type: str = ""
