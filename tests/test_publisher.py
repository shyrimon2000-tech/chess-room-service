from unittest.mock import patch

from app.events.publisher import publish_room_activated, publish_room_created


def test_publish_room_created_swallows_redis_error():
    with patch("app.events.publisher._client") as mock_client:
        mock_client.publish.side_effect = ConnectionError("Redis unavailable")
        publish_room_created(room_id=1, white_player_id=7)


def test_publish_room_activated_swallows_redis_error():
    with patch("app.events.publisher._client") as mock_client:
        mock_client.publish.side_effect = ConnectionError("Redis unavailable")
        publish_room_activated(room_id=1, white_player_id=7, black_player_id=12)
