from uuid import UUID
import uuid
from datetime import datetime
import pytz
from _log_config.log_config import get_logger
from fastapi import WebSocket

from app.settings.database import async_session_maker
from app.models import models
from app.schemas import schemas
from sqlalchemy import insert
from typing import List, Dict, Optional, Tuple
from app.functions.func_socket import async_encrypt

logger = get_logger('connect_manager', 'connect_manager.log')




class ConnectionManager:
    def __init__(self):
        # List to store active WebSocket connections
        self.active_connections: List[WebSocket] = []
        
        # Dictionary to map user IDs to their WebSocket connection, username, and avatar
        self.user_connections: Dict[UUID, Tuple[WebSocket, str, str, UUID, bool]] = {}

    async def connect(self, websocket: WebSocket, user_id: UUID,
                      user_name: str, avatar: str, room_id: UUID, verified: bool):
        """
        Accepts a new WebSocket connection and stores it in the list of active connections
        and the dictionary of user connections.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[user_id] = (websocket, user_name, avatar, room_id, verified)

    def disconnect(self, websocket: WebSocket, user_id: UUID):
        """
        Removes a WebSocket connection from the list of active connections and the user
        connections dictionary when a user disconnects.
        """
        self.active_connections.remove(websocket)
        self.user_connections.pop(user_id, None)
        
            
    async def send_active_users(self, room_id: UUID):
            """
            Sends the list of active users in a specific room to all connected WebSocket clients in that room.
            """
            active_users = [
                {"user_id": str(user_id), "user_name": user_info[1], "avatar": user_info[2], "verified": user_info[4]}
                for user_id, user_info in self.user_connections.items()
                if user_info[3] == room_id  # Check if the user is in the specified room
            ]
            message_data = {"active_users": active_users}

            # Send the message only to users in the specified room
            for websocket, _, _, user_room_id, _ in self.user_connections.values():
                if user_room_id == room_id:
                    await websocket.send_json(message_data)
                    
                    
    async def notify_users_typing(self, room_id: UUID, user_name: str, typing_user_id: UUID):
        """
        Sends a message to all active WebSocket connections in a specific room 
        except for the user who is typing.
        """
        message_data = {"type": user_name}
 
        for user_id, (connection, _, _, user_room_id, _) in self.user_connections.items():
            if user_room_id == room_id and user_id != typing_user_id:
                await connection.send_json(message_data)

    async def broadcast_all(self, message: Optional[str], fileUrl: Optional[str],
                            voiceUrl: Optional[str], videoUrl: Optional[str],
                            room: str, receiver_id: UUID,
                            id_return: Optional[UUID],
                            user_name: str, avatar: str,
                            verified: bool, room_id: UUID, add_to_db: bool):
        """
        Sends a message to all active WebSocket connections. If `add_to_db` is True, it also
        adds the message to the database.
        """
        try:
            timezone = pytz.timezone('UTC')
            current_time_utc = datetime.now(timezone).isoformat()
            file_id = None

            if add_to_db:
                file_id = await self.add_all_to_database(message, fileUrl, voiceUrl,
                                                         videoUrl, room, receiver_id, id_return, room_id)

            if file_id is None:
                file_id = uuid.uuid4()

            socket_message = schemas.ChatMessagesSchema(
                id=file_id,
                created_at=current_time_utc,
                receiver_id=receiver_id,
                message=message,
                fileUrl=fileUrl,
                voiceUrl=voiceUrl,
                videoUrl=videoUrl,
                id_return=id_return,
                user_name=user_name,
                verified=verified,
                avatar=avatar,
                vote=0,
                edited=False,
                deleted=False,
                room_id=room_id
            )

            wrapped_message = await schemas.wrap_message(socket_message)
            message_json = wrapped_message.model_dump_json()

            # Send the message only to users in the specified room
            for user_id, (connection, _, _, user_room, _) in self.user_connections.items():
                if user_room == room_id:
                    await connection.send_text(message_json)
        except Exception as e:
            logger.error(f"Failed to broadcast message: {str(e)}")


    @staticmethod
    async def add_all_to_database(message: Optional[str], fileUrl: Optional[str], voiceUrl: Optional[str],
                                  videoUrl: Optional[str], room: str, receiver_id: UUID,
                                  id_message: Optional[UUID], room_id: Optional[UUID]):
        """
        Adds a message to the database asynchronously.
        """
        try:
            encrypt_message = await async_encrypt(message)
            async with async_session_maker() as session:
                stmt = insert(models.ChatMessages).values(message=encrypt_message,
                                                          fileUrl=fileUrl, voiceUrl=voiceUrl, videoUrl=videoUrl,
                                                          rooms=room, receiver_id=receiver_id,
                                                          id_return=id_message, room_id=room_id)
                result = await session.execute(stmt)
                await session.commit()

                message_id = result.inserted_primary_key[0]
                return message_id
        except Exception as e:
            logger.error(f"Failed to add message to database: {str(e)}")

    async def send_message_to_user(self, message: Optional[str], fileUrl: Optional[str],
                            voiceUrl: Optional[str], videoUrl: Optional[str],
                            room: str, receiver_id: UUID,
                            id_return: Optional[UUID],
                            user_name: str, avatar: str,
                            verified: bool, room_id: UUID, add_to_db: bool):
        """
        Sends a message to all active WebSocket connections. If `add_to_db` is True, it also
        adds the message to the database.
        """
        try:
            timezone = pytz.timezone('UTC')
            current_time_utc = datetime.now(timezone).isoformat()
            file_id = None

            if add_to_db:
                file_id = await self.add_all_to_database(message, fileUrl, voiceUrl,
                                                         videoUrl, room, receiver_id, id_return, room_id)

            if file_id is None:
                file_id = uuid.uuid4()

            socket_message = schemas.ChatMessagesSchema(
                id=file_id,
                created_at=current_time_utc,
                receiver_id=receiver_id,
                message=message,
                fileUrl=fileUrl,
                voiceUrl=voiceUrl,
                videoUrl=videoUrl,
                id_return=id_return,
                user_name=user_name,
                verified=verified,
                avatar=avatar,
                vote=0,
                edited=False,
                deleted=False,
                room_id=room_id
            )

            message_json = socket_message.model_dump_json()

            # Send the message only to the specified user_id
            connection = self.user_connections.get(user_id)
            if connection:
                await connection[0].send_text(message_json)
        except Exception as e:
            logger.error(f"Failed to send message to user: {str(e)}")