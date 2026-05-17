from pydantic import BaseModel, Field
from typing import Annotated

class UserSignup(BaseModel):
    display_name: Annotated[str, Field(min_length=3, max_length=50)] | None = None
    username: Annotated[str, Field(min_length=3, max_length=30)]
    email: Annotated [str, Field(min_length=10)]
    password: Annotated[str, Field(min_length=8)]
    bio: Annotated[str, Field(max_length=280)] | None = None

class UserPublic(BaseModel):
    username: str
    id: int