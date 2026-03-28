"""
API Models — Pydantic models for REST API request/response validation.

The response validation is critical: LLMs occasionally produce malformed JSON,
markdown fences, or preamble text. The API layer catches all of this and
ensures clients always receive a parseable, schema-compliant envelope.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum

class AgentResponseEnvelope(BaseModel):
    """
    The guaranteed response shape from every API call.
    Clients can always parse this — even when the LLM misbehaves,
    the API layer synthesizes a valid envelope.
    """
    conversation_id: Optional[str] = None
    response_type: str
    user_name: Optional[str] = None
    agent_message: str
    payload: dict[str, Any] = Field(default_factory=dict)

    # API-level metadata (not from agents — added by the API layer)
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="API-level metadata: responding_agent, latency_ms, session state snapshot.",
    )