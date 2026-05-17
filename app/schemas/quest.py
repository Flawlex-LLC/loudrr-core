from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field

class QuestConditions(BaseModel):
    min_tier: str = "bronze"
    min_claims_per_user: int = 1

class QuestCreate(BaseModel):
    type: str
    title: str
    reward_points: int
    conditions: QuestConditions = QuestConditions()

class QuestPublic(BaseModel):
    id: int
    type: str
    title: str
    reward_points: int
    created_at: datetime
    updated_at: datetime
