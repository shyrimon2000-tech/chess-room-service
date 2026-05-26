from datetime import datetime

from pydantic import BaseModel


class RoomResponse(BaseModel):
    id: int
    status: str
    white_player_id: int | None
    black_player_id: int | None
    game_id: int | None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class MessageResponse(BaseModel):
    message: str