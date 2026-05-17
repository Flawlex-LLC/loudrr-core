from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from sqlalchemy import func
import sqlalchemy as sa

class Quest(Base):
    __tablename__="quests"
    id: Mapped[int] = mapped_column(primary_key=True) # this auto-creates pk ID.
    type: Mapped[str] = mapped_column()
    title: Mapped[str] = mapped_column()
    reward_points: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(),
                                                  onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(server_default=sa.text("0"))
    
