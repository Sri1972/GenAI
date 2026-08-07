"""
A2A (Agent-to-Agent) Protocol

Defines the message format and agent card structure for cross-organization
agent communication. This simulates a standardized protocol that agents
from different companies would use to interoperate.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
import uuid


class AgentCard(BaseModel):
    """Public identity card that an agent exposes for discovery."""
    agent_id: str
    organization: str
    name: str
    description: str
    capabilities: list[str]
    endpoint: str
    protocol_version: str = "1.0"


class A2AMessage(BaseModel):
    """Standard message format for agent-to-agent communication."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    sender_agent_id: str
    receiver_agent_id: str
    message_type: Literal[
        "service_request",
        "proposal",
        "counter_proposal",
        "accept",
        "reject",
        "info_request",
        "info_response",
        "escalate"
    ]
    subject: str
    body: str
    metadata: dict = Field(default_factory=dict)
    in_reply_to: Optional[str] = None


class NegotiationState(BaseModel):
    """Tracks the state of an ongoing negotiation between agents."""
    conversation_id: str
    status: Literal["active", "agreed", "rejected", "escalated"] = "active"
    messages: list[A2AMessage] = Field(default_factory=list)
    rounds: int = 0
    max_rounds: int = 6
