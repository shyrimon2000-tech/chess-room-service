import json

import redis

from app.config import settings


def publish_room_created(room_id: int, white_player_id: int) -> None:
    client = redis.from_url(settings.REDIS_URL)

    payload = json.dumps({
        "event": "room_created",
        "room_id": room_id,
        "white_player_id": white_player_id,
    })

    client.publish("room_events", payload)


def publish_room_activated(
    room_id: int, white_player_id: int, black_player_id: int
) -> None:
    client = redis.from_url(settings.REDIS_URL)

    payload = json.dumps({
        "event": "room_activated",
        "room_id": room_id,
        "white_player_id": white_player_id,
        "black_player_id": black_player_id,
    })

    client.publish("room_events", payload)
