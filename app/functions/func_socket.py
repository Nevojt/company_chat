
from datetime import datetime, timedelta

import pytz
import logging
from fastapi import HTTPException, status
from app.schemas import schemas
from app.settings.config import settings
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func, desc, update
from typing import List

from app.models import models

import base64
from cryptography.fernet import Fernet, InvalidToken


# Key for symmetric encryption
key = settings.key_crypto
cipher = Fernet(key)


logging.basicConfig(filename='_log/func_vote.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_base64(s):
    try:
        return base64.b64encode(base64.b64decode(s)).decode('utf-8') == s
    except Exception:
        return False

async def async_encrypt(data: str):
    if data is None:
        return None
    encrypted = cipher.encrypt(data.encode())
    encoded_string = base64.b64encode(encrypted).decode('utf-8')
    return encoded_string

async def async_decrypt(encoded_data: str):
    """
    Decrypts a base64 encoded string using a symmetric encryption algorithm.

    Parameters:
    encoded_data (str): The base64 encoded string to decrypt.

    Returns:
    Optional[str]: The decrypted string if decryption is successful.
    None: If decryption fails due to an invalid token or key mismatch.

    This function first checks if the input data is a valid base64 encoded string.
    If not, it logs an error message and returns the original encoded data.
    Then, it attempts to decrypt the encoded data using a symmetric encryption algorithm.
    If decryption is successful, it returns the decrypted string.
    If decryption fails due to an invalid token or key mismatch, it logs an error message and returns None.
    """
    if not is_base64(encoded_data):
        # logger.error(f"Data is not valid base64, returning original data: {encoded_data}")
        return encoded_data

    try:
        encrypted = base64.b64decode(encoded_data.encode('utf-8'))
        decrypted = cipher.decrypt(encrypted).decode('utf-8')
        return decrypted
    except InvalidToken as e:
        logger.error(f"Failed to decrypt, possibly due to key mismatch or data corruption: {str(e)}")
        return None


async def fetch_last_messages(rooms: str, limit: int, session: AsyncSession) -> List[schemas.SocketModel]:
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
    ).limit(limit)

    result = await session.execute(query)
    raw_messages = result.all()

    # Convert raw messages to SocketModel
    messages = []
    for socket, user, votes in raw_messages:
        decrypted_message = await async_decrypt(socket.message)
        messages.append(
            schemas.SocketModel(
                created_at=socket.created_at,
                receiver_id=socket.receiver_id,
                message=decrypted_message,
                fileUrl=socket.fileUrl,
                user_name=user.user_name if user is not None else "Unknown user",
                avatar=user.avatar if user is not None else "https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/photo_2024-06-14_19-20-40.jpg",
                verified=user.verified if user is not None else None,
                id=socket.id,
                vote=votes,
                id_return=socket.id_return,
                edited=socket.edited,
                return_message=socket.return_message,
                delete=socket.delete
            )
        )
    messages.reverse()
    return messages


async def fetch_message_by_id(session: AsyncSession, message_id: int):
    """
    Fetches a message by its ID along with user information and returns it as a SocketReturnMessage object.

    Parameters:
    session (AsyncSession): The database session to use for querying the database.
    message_id (int): The ID of the message to fetch.

    Returns:
    Optional[SocketReturnMessage]: A SocketReturnMessage object representing the message, or None if no message is found.
    """
    # Formulate the query
    message_query = select(
        models.Socket, 
        models.User
    ).outerjoin(
        models.User, models.Socket.receiver_id == models.User.id
    ).filter(
        models.Socket.id == message_id
    ).group_by(
        models.Socket.id, models.User.id
    )

    # Execute the query
    result = await session.execute(message_query)
    message_data = result.first()

    if message_data:
        socket, user = message_data
        decrypted_message = await async_decrypt(socket.message) if socket.message else None

        # Create a SocketReturnMessage instance
        return_message = schemas.SocketReturnMessage(
            created_at=socket.created_at,
            receiver_id=socket.receiver_id,
            id=socket.id,
            message=decrypted_message,
            fileUrl=socket.fileUrl,
            user_name=user.user_name if user else "USER DELETE",
            avatar=user.avatar if user else "https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/boy_1.webp",
            delete=socket.delete
        )

        return return_message.model_dump_json()
    else:
        return None
    
    
    

async def update_room_for_user(user_id: int, room: str, session: AsyncSession):
    """
    Update the room for a user in the database.

    Parameters:
    user_id (int): The unique identifier of the user.
    room (str): The name of the room to update.
    session (AsyncSession): The database session.

    Returns:
    models.User_Status: The updated user status record.

    This function updates the room for a user in the database.
    It first retrieves the user's status record from the database using the provided user_id.
    If the user status record is not found, it raises a 404 Not Found HTTPException.
    Then, it retrieves the room record from the database using the provided room name.
    If the room record is not found, it raises a 404 Not Found HTTPException.
    Finally, it updates the user's status record with the new room information and commits the changes to the database.
    """
    try:
        user_status_query = select(models.User_Status).where(models.User_Status.user_id == user_id)
        user_status_result = await session.execute(user_status_query)
        user_status = user_status_result.scalar()

        if user_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User status with user_id: {user_id} not found"
            )
        
        room_query = select(models.Rooms).where(models.Rooms.name_room == room)
        room_result = await session.execute(room_query)
        room_record = room_result.scalar()
        
        if room_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with name: {room} not found"
            )

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
        if vote.message_id == 0:
            return
        
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
    
    if message.delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message has been deleted")
    
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
    query = select(models.Socket).where(models.Socket.id == id_message, 
                                        models.Socket.receiver_id == current_user.id)
    result = await session.execute(query)
    message = result.scalar()

    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                            detail="Message not found or you don't have permission to delete this message")

    message.message = None
    message.fileUrl = None
    message.delete = True

    
    session.add(message)
    await session.commit()

    return {"message": "Message deleted successfully"}



async def online(session: AsyncSession, user_id: int):
    online = await session.execute(select(models.User_Status).filter(models.User_Status.user_id == user_id,
                                                                     models.User_Status.status == True))
    online = online.scalars().all()
    return online

async def update_user_status(session: AsyncSession, 
                             user_id: int, is_online: bool):
    """
    Update a user's online status in the database.

    Parameters:
    session (AsyncSession): The database session.
    user_id (int): The unique identifier of the user.
    is_online (bool): The new online status for the user.

    Returns:
    None

    This function updates the online status of a user in the database.
    It uses the provided database session to execute an update query on the User_Status table.
    The query filters the records based on the user_id and updates the status column with the provided is_online value.
    If an exception occurs during the update process, it logs the error using the logger.
    """
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
    """
    Fetch room data from the database.

    Parameters:
    room (str): The name of the room.
    session (AsyncSession): The database session.

    Returns:
    models.Rooms: The room data if the room exists in the database.
    None: If the room does not exist in the database.

    This function retrieves the room data from the database using the provided room name.
    If the room exists, it returns the room data.
    If the room does not exist, it returns None.
    """
    room_query = select(models.Rooms).where(models.Rooms.name_room == room)
    room_result = await session.execute(room_query)
    room_record = room_result.scalar()
    
    if room_record is None:
        return None
    
    return room_record

async def send_message_deleted_room(room_id: int, manager: object, session: AsyncSession):
    """
    This function sends a message to all users in a specific room, indicating that the room will be deleted in a certain number of days.

    Parameters:
    room_id (int): The unique identifier of the room.
    manager (object): The object responsible for managing messages and broadcasting them.
    session (AsyncSession): The database session object for executing database queries.

    Returns:
    None

    This function first retrieves the user object with id 2 from the database.
    If the user object is not found, the function returns without sending a message.
    Then, it retrieves the room object with the given room_id from the database.
    If the room object is not found or the room's delete_at attribute is None, the function returns without sending a message.
    If the room will be deleted in more than 0 days, the function constructs a message indicating the remaining days.
    The message is sent to all users in the specified room using the manager's broadcast_all method.
    """
    user_query = select(models.User).where(models.User.id == 2)
    user_result = await session.execute(user_query)
    user = user_result.scalar_one() 
    
    if not user:
        return
    room_query = select(models.Rooms).where(models.Rooms.id == room_id)
    room_result = await session.execute(room_query)
    room = room_result.scalar_one()
    
    if room.delete_at:
        days_to_deletion = room.delete_at + timedelta(days=30) - datetime.now(pytz.utc)
        if days_to_deletion.days > 0:
            current_time = datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
            await manager.broadcast_all(
                message=f"😑 This room will be DELETED in {days_to_deletion.days} days. 😑",
                file=None,
                rooms=room.name_room,
                created_at=current_time,
                receiver_id=user.id,
                user_name=user.user_name,
                avatar=user.avatar,
                verified=user.verified,
                id_return=None,
                add_to_db=False
            )


async def send_message_blocking(room: str, manager: object, session: AsyncSession):
    """
    This function sends a message to all users in a specific room, indicating that the chat is temporarily blocked.

    Parameters:
    room (str): The name of the room where the message should be sent.
    manager (object): The object responsible for managing messages and broadcasting them.
    session (AsyncSession): The database session object for executing database queries.

    Returns:
    None

    This function first retrieves the user object with id 2 from the database.
    If the user object is not found, the function returns without sending a message.
    Then, it constructs a message indicating that the chat is temporarily blocked.
    The message is sent to all users in the specified room using the manager's broadcast_all method.
    """
    user_query = select(models.User).where(models.User.id == 2)
    user_result = await session.execute(user_query)
    user = user_result.scalar_one() 
    
    if not user:
        return
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await manager.broadcast_all(
                            message="This chat is temporarily blocked.",
                            file=None,
                            rooms=room,
                            created_at=current_time,
                            receiver_id=user.id,
                            user_name=user.user_name,
                            avatar=user.avatar,
                            verified=user.verified,
                            id_return=None,
                            add_to_db=False
                        )
    
async def send_message_mute_user(room: str, current_user: models.User, manager: object, session: AsyncSession):
    """
    This function sends a message to a user when they are muted in a specific room.

    Parameters:
    room (str): The name of the room where the user is muted.
    current_user (models.User): The user object representing the muted user.
    manager (object): The object responsible for managing messages and broadcasting them.
    session (AsyncSession): The database session object for executing database queries.

    Returns:
    None
    """

    # Query to retrieve the user object with id 2
    user_query = select(models.User).where(models.User.id == 2)
    user_result = await session.execute(user_query)
    user = user_result.scalar_one()

    # Query to retrieve the room object with the given name
    room_query = select(models.Rooms).where(models.Rooms.name_room == room)
    room_result = await session.execute(room_query)
    room_record = room_result.scalar()

    # Get the current time in UTC and convert it to naive datetime
    current_time_utc = datetime.now(pytz.timezone('UTC'))
    current_time_naive = current_time_utc.replace(tzinfo=None)

    # Query to retrieve the ban record for the muted user in the given room
    ban = select(models.Ban).where(
        models.Ban.user_id == current_user.id,
        models.Ban.room_id == room_record.id,
        models.Ban.end_time > current_time_naive  # Filter banned
    )
    ban_result = await session.execute(ban)
    ban_record = ban_result.scalar()

    # If a ban record is found, calculate the remaining minutes and send a message to the user
    if ban_record:
        minutes = (ban_record.end_time - current_time_naive).total_seconds() / 60
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await manager.send_message_to_user(
            message=f"Sorry, but the owner of the room has blocked you. Until the end of the block remained {minutes:.0f} minutes.",
            file=None,
            rooms=room,
            created_at=current_time,
            receiver_id=user.id,
            user_id=current_user.id,
            user_name=user.user_name,
            avatar=user.avatar,
            verified=user.verified,
            id_return=None,
            add_to_db=False
        )


async def ban_user(room: str, current_user: models.User, session: AsyncSession):
    room_query = select(models.Rooms).where(models.Rooms.name_room == room)
    room_result = await session.execute(room_query)
    room_record = room_result.scalar_one_or_none()
    
    if not room_record:
        return

    ban_query = select(models.Ban).where(models.Ban.user_id == current_user.id,
                                         models.Ban.room_id == room_record.id)
    ban_result = await session.execute(ban_query)
    ban_record = ban_result.scalar()
    
    current_time_utc = datetime.now(pytz.timezone('UTC'))
    current_time_naive = current_time_utc.replace(tzinfo=None)
    # print(current_time_naive)
    # print(ban_record.end_time)
    
    if ban_record:
        if current_time_naive > ban_record.end_time:
            await session.delete(ban_record)
            await session.commit()
            return False
        else:
            return True
    else:
        return False
        
        
        
async def get_room(room_id: int, session: AsyncSession):
    """
    Retrieve the name of a room given its unique identifier.

    Args:
        room_id (int): The unique identifier of the room.
        session (AsyncSession): The database session.

    Returns:
        str: The name of the room.

    This function retrieves the room's name from the database using the provided room_id.
    If the room does not exist, it returns None.
    """
    room = select(models.Rooms).where(models.Rooms.id == room_id)
    result = await session.execute(room)
    existing_room = result.scalar_one_or_none()
    return existing_room.name_room




async def count_messages_in_room(room_name: str, session: AsyncSession):
    """
    Count the number of messages in a specific room.

    Args:
        room_name (int): The unique identifier of the room.
        session (AsyncSession): The database session.

    Returns:
        int: The total number of messages in the specified room.

    This function retrieves all messages from the specified room in the database.
    It then counts the number of messages and returns the total count.
    """
    
    count_messages_in_rooms = select(models.Socket).where(models.Socket.rooms == room_name)
    result = await session.execute(count_messages_in_rooms)
    raw_messages = result.all()
    
    count_messages_in_rooms = len(raw_messages)
    
    return count_messages_in_rooms





async def start_session(user_id: int, db: AsyncSession):
    """
    Start a user's online session.

    Args:
        user_id (int): The unique identifier of the user.
        db (AsyncSession): The database session.

    Returns:
        models.UserOnlineTime: The record of the user's online time.

    This function retrieves the user's online time record from the database.
    If the record does not exist, it creates a new record with the current time as the session start time.
    If the record exists, it updates the session start time to the current time.
    """
    result = await db.execute(select(models.UserOnlineTime).where(models.UserOnlineTime.user_id == user_id))
    user_time_record = result.scalar_one_or_none()

    if user_time_record is None:
        user_time_record = models.UserOnlineTime(user_id=user_id, session_start=datetime.now(pytz.utc), total_online_time=timedelta())
        db.add(user_time_record)
    else:
        user_time_record.session_start = datetime.now(pytz.utc)
        user_time_record.session_end = None
    
    await db.commit()
    await db.refresh(user_time_record)
    return user_time_record

async def end_session(user_id: int, db: AsyncSession):
    """
    End a user's online session and update the total online time.

    Args:
        user_id (int): The unique identifier of the user.
        db (AsyncSession): The database session.

    Returns:
        models.UserOnlineTime: The updated record of the user's online time.

    This function retrieves the user's online time record from the database.
    If the record exists and the session start time is not None, it calculates the session duration by subtracting the session start time from the current time.
    It then updates the session end time to the current time and adds the session duration to the total online time.
    Finally, it commits the changes to the database and refreshes the user_time_record.
    """
    result = await db.execute(select(models.UserOnlineTime).where(models.UserOnlineTime.user_id == user_id))
    user_time_record = result.scalar_one_or_none()

    if user_time_record and user_time_record.session_start:
        session_end_time = datetime.now(pytz.utc)
        session_duration = session_end_time - user_time_record.session_start
        user_time_record.session_end = session_end_time
        user_time_record.total_online_time += session_duration

        await db.commit()
        await db.refresh(user_time_record)
    return user_time_record

