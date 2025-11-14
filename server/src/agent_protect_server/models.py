import datetime as dt
import uuid as _uuid
from typing import Any

from agent_protect_models.base import BaseModel
from agent_protect_models.protection import AgentTool
from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class AgentVersionedTool(BaseModel):
    version: int
    tool: AgentTool

class AgentData(BaseModel):
    agent_metadata: dict
    tools: list[AgentVersionedTool]

class Agent(Base):
    __tablename__ = "agents"

    agent_uuid: Mapped[_uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

