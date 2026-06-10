from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import JoinRoomResponse, MessageResponse, RoomResponse
from app.services.auth_dependencies import CurrentUser, get_current_user, require_admin
from app.services.room_service import (
    close_room,
    create_new_room,
    get_room,
    get_rooms,
    join_room,
    quick_join_or_create_room,
)

router = APIRouter(
    prefix="/rooms",
    tags=["rooms"],
)


@router.get("", response_model=list[RoomResponse])
def get_rooms_endpoint(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return get_rooms(db)


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room_endpoint(
    response: Response,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    room, created = create_new_room(db, current_user.id, current_user.username)
    if not created:
        response.status_code = status.HTTP_200_OK
    return room


@router.post("/quick", response_model=RoomResponse)
def quick_room_endpoint(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return quick_join_or_create_room(db, current_user.id, current_user.username)


@router.get("/{room_id}", response_model=RoomResponse)
def get_room_endpoint(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        return get_room(db, room_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )


@router.post("/{room_id}/join", response_model=JoinRoomResponse)
def join_room_endpoint(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        room, role = join_room(db, room_id, current_user.id, current_user.username)
        return JoinRoomResponse.model_validate({**room.__dict__, "role": role})
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )



@router.delete("/{room_id}", response_model=MessageResponse)
def admin_close_room_endpoint(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    try:
        return MessageResponse(message=close_room(db, room_id))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )