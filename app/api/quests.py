from fastapi import APIRouter, status, Path, Depends, HTTPException
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.models import quest
from app.schemas.quest import QuestCreate, QuestPublic
from typing import Annotated
from app.models.quest import Quest

router = APIRouter(prefix="/quests", tags=["quests"])

#1st endpoint: list all quests
@router.get("", response_model=list[QuestPublic])
async def list_quests(db: Annotated[AsyncSession, Depends(get_session)]):
    # This is a simple example of how to query the database for all quests.
    query = select(Quest)
    # The result of the query is a list of Quest objects, which we can return directly.
    result = await db.execute(query)
    # The scalars() method extracts the Quest objects from the result, and all() converts it to a list.
    return result.scalars().all()

#2nd endpoint: create a new quest
@router.post("", response_model=QuestPublic, 
             status_code=status.HTTP_201_CREATED)
async def create_quest(quest: QuestCreate,
                       db: Annotated[AsyncSession, Depends(get_session)],):
    new_quest = Quest(
        type=quest.type,
        title=quest.title,
        reward_points=quest.reward_points
    )
    db.add(new_quest)
    await db.commit()
    # await db.refresh(new_quest)
    return new_quest


#3rd endpoint: list all quests
@router.get("/filter")
def filter_quests(tag: list[str] | None = None):
    return {"tags": tag, "count": len(tag) if tag else 0}


#4th endpoint: read a quest by id
@router.get("/{quest_id}", response_model=QuestPublic)
async def read_quest(quest_id: Annotated[int, Path(ge=1)],
                     db: Annotated[AsyncSession, Depends(get_session)]):
        # We use the get() method of the database session to retrieve the quest with the given ID.
        quest = await db.get(Quest, quest_id)
        # If the quest with the given ID does not exist, we raise a 404 Not Found error.
        if quest is None:
            raise HTTPException(status_code=404, detail="Quest not found")
        return quest