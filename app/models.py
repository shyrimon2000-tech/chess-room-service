from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="waiting",
    )

    white_player_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    black_player_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    white_player_nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    black_player_nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)

    game_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )