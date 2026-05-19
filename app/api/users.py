from fastapi import APIRouter, HTTPException, Query, status, Path
from app.schemas.user import UserPublic, UserSignup
from typing import Annotated

router = APIRouter(prefix="/users", tags=["users"])







# @router.get("", response_model=list[UserPublic])
# def list_users():
#     return [
#         {"username": "moh", "id": 1}
#     ]

# @router.get("/{user_id}")
# def read_user(user_id: Annotated[str, Path(min_length=3, max_length=30, pattern=r"[a-zA-Z0-9_]+$")]):
#     return {"user_id": user_id}

# @router.get("/search")
# def search_quests(
#     q: Annotated[str,Query(min_length=2, max_length=100)],
#     limit: Annotated[int, Query(ge=1,le=100)]=20,
#     ):
#     return {"query": q, "limit": limit,"results":[]}

# @router.post("/auth/signup", response_model=UserPublic)
# def signup(user: UserSignup):
#     return {
#         "username": user.username,
#         "id": 1,
#         "password": user.password,}

