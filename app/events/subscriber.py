import json
import logging
import threading
import time

import redis

from app.config import settings
from app.database import SessionLocal
from app.repositories.room_repo import delete_room, get_room_by_id, save_room

logger = logging.getLogger(__name__)


def _handle_message(message):
    if message["type"] != "message":
        return

    try:
        data = json.loads(message["data"])
    except (json.JSONDecodeError, TypeError):
        logger.error("Failed to parse game event: %s", message)
        return

    event = data.get("event")
    room_id = data.get("room_id")

    if event == "game_created":
        if room_id is None:
            return
        db = SessionLocal()
        try:
            room = get_room_by_id(db, room_id)
            if room is None:
                return
            game_id = data.get("game_id")
            if game_id is not None:
                room.game_id = game_id
                save_room(db, room)
                logger.info("Room %s linked to game %s", room_id, game_id)
        except Exception:
            logger.exception("Failed to handle game_created for room %s", room_id)
        finally:
            db.close()
        return

    if event not in ("game_over", "game_abandoned"):
        return

    if room_id is None:
        logger.error("Received %s event without room_id", event)
        return

    db = SessionLocal()
    try:
        room = get_room_by_id(db, room_id)
        if room is None:
            logger.warning("Received %s for unknown room %s", event, room_id)
            return

        delete_room(db, room)
        logger.info("Room %s deleted (event: %s)", room_id, event)
    except Exception:
        logger.exception("Failed to handle %s for room %s", event, room_id)
    finally:
        db.close()


def _subscriber_loop():
    while True:
        try:
            client = redis.from_url(settings.REDIS_URL)
            pubsub = client.pubsub()
            pubsub.subscribe("game_events")
            for message in pubsub.listen():
                _handle_message(message)
        except Exception:
            logger.exception("Subscriber connection lost, reconnecting in 5s")
            time.sleep(5)


def start_subscriber():
    threading.Thread(target=_subscriber_loop, daemon=True).start()
