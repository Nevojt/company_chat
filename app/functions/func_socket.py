
from datetime import datetime
import logging
from fastapi import HTTPException, status
from app.schemas import schemas
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, desc, update
from typing import List

from app.models import models

# Налаштування логування
logging.basicConfig(filename='_log/func_vote.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)







async def fetch_last_messages(rooms: str, session: AsyncSession) -> List[schemas.SocketModel]:
    """
    This function fetches the last 50 messages in a given room and returns them as a list of SocketModel objects.

    Parameters:
    rooms (str): The name of the room to fetch messages from.
    session (AsyncSession): The database session to use for querying the database.

    Returns:
    List[schemas.SocketModel]: A list of SocketModel objects representing the last 50 messages in the room.
    """
    query = select(
    models.Socket, 
    models.User, 
    func.coalesce(func.sum(models.Vote.dir), 0).label('votes')
    ).outerjoin(
        models.Vote, models.Socket.id == models.Vote.message_id
    ).outerjoin( 
        models.User, models.Socket.receiver_id == models.User.id
    ).filter(
        models.Socket.rooms == rooms
    ).group_by(
        models.Socket.id, models.User.id
    ).order_by(
        desc(models.Socket.created_at)
    )

    result = await session.execute(query)
    raw_messages = result.all()

    # Convert raw messages to SocketModel
    messages = [
        schemas.SocketModel(
            created_at=socket.created_at,
            receiver_id=socket.receiver_id,
            message=socket.message,
            fileUrl=socket.fileUrl,
            user_name=user.user_name if user is not None else "Unknown user",
            avatar=user.avatar if user is not None else "https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/boy_1.webp",
            verified=user.verified if user is not None else None,
            id=socket.id,
            vote=votes,
            id_return=socket.id_return,
            edited=socket.edited
        )
        for socket, user, votes in raw_messages
    ]
    messages.reverse()
    return messages



async def update_room_for_user(user_id: int, room: str, session: AsyncSession):
    try:
        # Отримати запис статусу користувача
        user_status_query = select(models.User_Status).where(models.User_Status.user_id == user_id)
        user_status_result = await session.execute(user_status_query)
        user_status = user_status_result.scalar()

        if user_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User status with user_id: {user_id} not found"
            )
        
        # Отримати ідентифікатор кімнати
        room_query = select(models.Rooms).where(models.Rooms.name_room == room)
        room_result = await session.execute(room_query)
        room_record = room_result.scalar()
        
        if room_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with name: {room} not found"
            )
        
        # Оновити дані статусу користувача
        user_status.name_room = room
        user_status.room_id = room_record.id
        await session.commit()

        return user_status
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        logging.error(f"Update user failed with error {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
    
    
async def update_room_for_user_live(user_id: int, session: AsyncSession):
    """
    Update the room name for a specific user.

    Args:
        user_id (int): The user ID.
        session (AsyncSession): The database session.

    Returns:
        models.User_Status: The updated user status.

    Raises:
        HTTPException: If the user status cannot be found or updated.
    """
    try:
        post_query = select(models.User_Status).where(models.User_Status.user_id == user_id)
        post_result = await session.execute(post_query)
        post = post_result.scalar()

        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User status with user_id: {user_id} not found"
            )

        post.name_room = 'Hell' 
        await session.commit()

        return post
    except Exception as e:
        logging.error(f"Error updating user status: {e}")
        raise



async def process_vote(vote: schemas.Vote, session: AsyncSession, current_user: models.User):
    """
    Process a vote submitted by a user.

    Args:
        vote (schemas.Vote): The vote submitted by the user.
        session (AsyncSession): The database session.
        current_user (models.User): The current user.

    Returns:
        Dict[str, Any]: A response indicating whether the vote was added or removed, and any errors that may have occurred.

    Raises:
        HTTPException: If an error occurs while processing the vote.
    """
    try:
        result = await session.execute(select(models.Socket).filter(models.Socket.id == vote.message_id))
        message = result.scalars().first()
        
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Message with id: {vote.message_id} does not exist")
        
        vote_result = await session.execute(select(models.Vote).filter(
            models.Vote.message_id == vote.message_id, 
            models.Vote.user_id == current_user.id
        ))
        found_vote = vote_result.scalars().first()
        
        if vote.dir == 1:
            if found_vote:
                await session.delete(found_vote)
                await session.commit()
                return {"message": "Successfully removed vote"}
            else:
                new_vote = models.Vote(message_id=vote.message_id, user_id=current_user.id, dir=vote.dir)
                session.add(new_vote)
                await session.commit()
                return {"message": "Successfully added vote"}

        else:
            if not found_vote:
                return {"message": "Vote does not exist or has already been removed"}
            
            await session.delete(found_vote)
            await session.commit()
            return {"message": "Successfully deleted vote"}

    except HTTPException as http_exc:
        logging.error(f"HTTP error occurred: {http_exc.detail}")
        raise http_exc
    
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An unexpected error occurred")

        
        
        
async def change_message(id_message: int, message_update: schemas.SocketUpdate,
                         session: AsyncSession, 
                         current_user: models.User):
    """
    This function updates a message in the database.

    Parameters:
        id_message (int): The ID of the message to update.
        message_update (schemas.SocketUpdate): The updated message information.
        session (AsyncSession): The database session.
        current_user (models.User): The current user.

    Returns:
        Dict[str, Any]: A response indicating whether the message was updated and any errors that may have occurred.

    Raises:
        HTTPException: If an error occurs while updating the message.
    """
    
    query = select(models.Socket).where(models.Socket.id == id_message, models.Socket.receiver_id == current_user.id)
    result = await session.execute(query)
    message = result.scalar()

    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found or you don't have permission to edit this message")

    message.message = message_update.message 
    message.edited = True
    session.add(message)
    await session.commit()

    return {"message": "Message updated successfully"}


async def delete_message(id_message: int,
                         session: AsyncSession, 
                         current_user: models.User):
    
    """
    Delete a message from the database.

    Args:
        id_message (int): The ID of the message to delete.
        session (AsyncSession): The database session.
        current_user (models.User): The current user.

    Returns:
        Dict[str, Any]: A response indicating whether the message was deleted and any errors that may have occurred.

    Raises:
        HTTPException: If an error occurs while deleting the message.
    """
    query = select(models.Socket).where(models.Socket.id == id_message, models.Socket.receiver_id == current_user.id)
    result = await session.execute(query)
    message = result.scalar()

    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found or you don't have permission to delete this message")

    await session.delete(message)
    await session.commit()

    return {"message": "Message deleted successfully"}



async def online(session: AsyncSession, user_id: int):
    online = await session.execute(select(models.User_Status).filter(models.User_Status.user_id == user_id, models.User_Status.status == True))
    online = online.scalars().all()
    return online

async def update_user_status(session: AsyncSession, user_id: int, is_online: bool):
    try:
        await session.execute(
            update(models.User_Status)
            .where(models.User_Status.user_id == user_id)
            .values(status=is_online)
        )
        await session.commit()
        logger.info(f"User status updated for user {user_id}: {is_online}")
    except Exception as e:
        logger.error(f"Error updating user status for user {user_id}: {e}", exc_info=True)
        
        
        
async def fetch_room_data(room: str, session: AsyncSession):
    
    room_query = select(models.Rooms).where(models.Rooms.name_room == room)
    room_result = await session.execute(room_query)
    room_record = room_result.scalar()
    
    if room_record is None:
        return None
    
    return room_record

async def send_message_blocking(room: str, manager: object):
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await manager.broadcast(
                                message="This chat is temporarily blocked.",
                                rooms=room,
                                created_at=current_time,
                                receiver_id=2,
                                user_name="System",
                                avatar="https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/girl_5.webp",
                                verified=True,
                                id_return=None,
                                add_to_db=False
        )