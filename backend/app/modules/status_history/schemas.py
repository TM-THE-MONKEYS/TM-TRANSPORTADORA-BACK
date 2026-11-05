"""Status history API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    from_status: str | None
    to_status: str
    changed_by_user_id: uuid.UUID | None
    changed_at: datetime
    source: str
    motivo: str | None
