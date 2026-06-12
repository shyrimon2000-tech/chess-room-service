import json
import logging

import redis
from tenacity import retry, stop_after_attempt, wait_fixed

from app.config import settings

logger = logging.getLogger(__name__)

_client = redis.from_url(settings.REDIS_URL)


@retry(wait=wait_fixed(2), stop=stop_after_attempt(30))
def wait_for_redis() -> None:
    _client.ping()


def publish_room_created(room_id: int, white_player_id: int) -> None:
    payload = json.dumps({
        "event": "room_created",
        "room_id": room_id,
        "white_player_id": white_player_id,
    })
    try:
        _client.publish("room_events", payload)
    except Exception:
        logger.exception("Failed to publish room_created for room %s", room_id)


def publish_room_activated(
    room_id: int, white_player_id: int, black_player_id: int
) -> None:
    payload = json.dumps({
        "event": "room_activated",
        "room_id": room_id,
        "white_player_id": white_player_id,
        "black_player_id": black_player_id,
    })
    try:
        _client.publish("room_events", payload)
    except Exception:
        logger.exception("Failed to publish room_activated for room %s", room_id)
