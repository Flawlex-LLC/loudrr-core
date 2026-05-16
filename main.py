from pydantic import BaseModel, Field
from typing import Annotated
from fastapi import FastAPI, HTTPException, Path, Query
from http import HTTPStatus

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/greet")
def greeter():
    name = "moh"
    return {"greeting": f"Hello, {name}!",
            "language": "Eng"}

@app.get("/colors")
def colors():
    return ["red", "green", "blue"]

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/about")
def about():
    return {**greeter(), "project": "QuestKit", "author": "moh", "year": 2026}

# fastapi doesnt need urls.py because it has a powerful feature with decorator @app.get("/path") 
# which allows us to define that route directly.

@app.get("/users/{user_id}/quests/{quest_id}")
def read_user_quest(user_id: str, quest_id: Annotated[int, Path(ge=1, le=10000)]):
    return {"user_id": user_id,
            "quest_id":quest_id, 
            "title":"Follow @Moh"}

@app.get("/users/{user_id}")
def read_user(user_id: Annotated[str, Path(min_length=3, max_length=30, pattern=r"[a-zA-Z0-9_]+$")]):
    return {"user_id": user_id}

@app.get("/search")
def search_quests(
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1,le=100)]=20,
    ):
    return {"query": q, "limit": limit,"results":[]}

@app.get("/quests/filter")
def filter_quests(tag: list[str] | None = None):
    return {"tags": tag, "count": len(tag) if tag else 0}

class QuestConditions(BaseModel):
    min_tier: str = "bronze"
    min_claims_per_user: int = 1

class QuestCreate(BaseModel):
    type: str
    title: str
    reward_points: int
    twitter_handle: str | None = None
    conditions: QuestConditions = QuestConditions()

class UserSignup(BaseModel):
    display_name: Annotated[str, Field(min_length=3, max_length=50)] | None = None
    username: Annotated[str, Field(min_length=3, max_length=30)]
    email: Annotated [str, Field(min_length=10)]
    password: Annotated[str, Field(min_length=8)]
    bio: Annotated[str, Field(max_length=280)] | None = None

class UserPublic(BaseModel):
    username: str
    id: int

@app.post("/auth/signup", response_model=UserPublic)
def signup(user: UserSignup):
    return {
        "username": user.username,
        "id": 1,
        "password": user.password,}

@app.get("/users", response_model=list[UserPublic])
def list_users():
    return [
        {"username": "moh", "id": 1}
    ]

class QuestPublic(BaseModel):
    id: int
    type: str
    title: str
    reward_points: int

@app.get("/quests", response_model=list[QuestPublic])
def list_quests():
    return [
        {"id":1, "type": "social", "title": "Follow @Moh", "reward_points": 100, "created_by_admin_id": 7, "internal_notes": "flag for review"},
        {"id":2, "type": "social", "title": "Like @Moh's tweet", "reward_points": 50, "created_by_admin_id": 7, "internal_notes": "flag for review"},
        ]


@app.post("/quests", response_model=QuestPublic, status_code=HTTPStatus.CREATED)
def create_quest(quest: QuestCreate):
    return {
        "id": 1,
        "type": quest.type,
        "title": quest.title,
        "reward_points": quest.reward_points,
        "created_by_admin_id": 7,
        "internal_notes": "flag for review",
    }


@app.get("/quests/{quest_id}", response_model=QuestPublic)
def read_quest(quest_id: Annotated[int, Path(ge=1, le=100000)]):
    if quest_id > 100:
        raise HTTPException(status_code=404, detail="Quest not found")
    return {"id": quest_id, "type": "social", "title": "Follow @Moh", "reward_points": 100, "created_by_admin_id": 7, "internal_notes": "flag for review"}

