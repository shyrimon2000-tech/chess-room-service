import json

import redis

from app.config import settings

_client = redis.from_url(settings.REDIS_URL)


def publish_room_created(room_id: int, white_player_id: int) -> None:
    payload = json.dumps({
        "event": "room_created",
        "room_id": room_id,
        "white_player_id": white_player_id,
    })
    _client.publish("room_events", payload)


def publish_room_activated(
    room_id: int, white_player_id: int, black_player_id: int
) -> None:
    payload = json.dumps({
        "event": "room_activated",
        "room_id": room_id,
        "white_player_id": white_player_id,
        "black_player_id": black_player_id,
    })
    _client.publish("room_events", payload)
