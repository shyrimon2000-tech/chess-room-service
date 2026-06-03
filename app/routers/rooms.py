from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MessageResponse, RoomResponse
from app.services.auth_dependencies import CurrentUser, get_current_user, require_admin
from app.services.room_service import (
    close_room,
    create_new_room,
    get_room,
    leave_room,
    quick_join_or_create_room,
)


router = APIRouter(
    prefix="/rooms",
    tags=["rooms"],
)


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room_endpoint(
    response: Response,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    room, created = create_new_room(db, current_user.id)
    if not created:
        response.status_code = status.HTTP_200_OK
    return room


@router.post("/quick", response_model=RoomResponse)
def quick_room_endpoint(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return quick_join_or_create_room(db, current_user.id)


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


@router.post("/{room_id}/leave", response_model=MessageResponse)
def leave_room_endpoint(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        message = leave_room(db, room_id, current_user.id)
        return MessageResponse(message=message)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


@router.delete("/{room_id}", response_model=RoomResponse)
def admin_close_room_endpoint(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    try:
        return close_room(db, room_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )