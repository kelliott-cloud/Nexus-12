"""Nexus Pydantic Models — Request/Response models.
Extracted from server.py for maintainability.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class SessionExchange(BaseModel):
    session_id: str

class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""
    kg_enabled: bool = False
    kg_share_with_org: bool = True

class ChannelCreate(BaseModel):
    name: str
    description: str = ""
    ai_agents: List[str] = ["claude", "chatgpt", "deepseek", "grok"]

class MessageCreate(BaseModel):
    content: str
    mentions: Optional[List[str]] = None

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ai_agents: Optional[List[str]] = None

class CheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str
