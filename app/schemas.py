from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RoomResponse(BaseModel):
    id: int
    status: str
    white_player_id: int | None
    black_player_id: int | None
    white_player_nickname: str | None
    black_player_nickname: str | None
    game_id: int | None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class JoinRoomResponse(RoomResponse):
    role: Literal["player", "spectator"]


class MessageResponse(BaseModel):
    message: str