from datetime import datetime
import pytz
import logging
from fastapi import WebSocket
from app.settings.database import async_session_maker
from app.models import models
from app.schemas import schemas
from sqlalchemy import insert
from typing import List, Dict, Optional, Tuple
from app.functions.func_socket import async_encrypt


logging.basicConfig(filename='_log/connect_manager.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)




class ConnectionManager:
    def __init__(self):
        # List to store active WebSocket connections
        self.active_connections: List[WebSocket] = []
        
        # Dictionary to map user IDs to their WebSocket connection, username, and avatar
        self.user_connections: Dict[int, Tuple[WebSocket, str, str, str, bool]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, user_name: str, avatar: str, room: str, verified: bool):
        """
        Accepts a new WebSocket connection and stores it in the list of active connections
        and the dictionary of user connections.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[user_id] = (websocket, user_name, avatar, room, verified)

    def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Removes a WebSocket connection from the list of active connections and the user
        connections dictionary when a user disconnects.
        """
        self.active_connections.remove(websocket)
        self.user_connections.pop(user_id, None)
        
            
    async def send_active_users(self, room: str):
            """
            Sends the list of active users in a specific room to all connected WebSocket clients in that room.
            """
            active_users = [
                {"user_id": user_id, "user_name": user_info[1], "avatar": user_info[2], "verified": user_info[4]}
                for user_id, user_info in self.user_connections.items()
                if user_info[3] == room  # Check if the user is in the specified room
            ]
            message_data = {"type": "active_users", "data": active_users}

            # Send the message only to users in the specified room
            for websocket, _, _, user_room, _ in self.user_connections.values():
                if user_room == room:
                    await websocket.send_json(message_data)
                    
                    
    async def notify_users_typing(self, room: str, user_name: str, typing_user_id: int):
        """
        Sends a message to all active WebSocket connections in a specific room 
        except for the user who is typing.
        """
        message_data = {"type": user_name}
 
        for user_id, (connection, _, _, user_room, _) in self.user_connections.items():
            if user_room == room and user_id != typing_user_id:
                await connection.send_json(message_data)

    
    async def broadcast_all(self, file: Optional[str], message: Optional[str],
                                rooms: str, receiver_id: int,
                                id_return: Optional[int], 
                                user_name: str, avatar: str, created_at: str, 
                                verified: bool, add_to_db: bool):
        """
        Sends a message to all active WebSocket connections. If `add_to_db` is True, it also
        adds the message to the database.
        """
        
        timezone = pytz.timezone('UTC')
        current_time_utc = datetime.now(timezone).isoformat()
        file_id = None
        vote_count = 0


        if add_to_db:
            file_id = await self.add_all_to_database(file, message, rooms, receiver_id, id_return)
            
        if file_id is not None:
            file_id = 0

        socket_message = schemas.SocketModel(
            id=file_id,
            created_at=current_time_utc,
            receiver_id=receiver_id,
            message=message,
            fileUrl=file,
            id_return=id_return,
            user_name=user_name,
            verified=verified,
            avatar=avatar,
            vote=0,
            edited=False
        )

        message_json = socket_message.model_dump_json()

        # Send the message only to users in the specified room
        for user_id, (connection, _, _, user_room, _) in self.user_connections.items():
            if user_room == rooms:
                await connection.send_text(message_json)

    @staticmethod
    async def add_all_to_database(fileUrl: Optional[str], message: Optional[str], 
                                    rooms: str, receiver_id: int, id_message: Optional[int]):
        """
        Adds a message to the database asynchronously.
        """
        encrypt_message = await async_encrypt(message)
        async with async_session_maker() as session:
            stmt = insert(models.Socket).values(fileUrl=fileUrl, message=encrypt_message, 
                                                rooms=rooms, receiver_id=receiver_id,
                                                id_return=id_message)
            result =  await session.execute(stmt)
            await session.commit()
            
            message_id = result.inserted_primary_key[0]
            return message_id
        
    async def send_message_to_user(self, user_id: int, file: Optional[str], message: Optional[str],
                                rooms: str, receiver_id: int,
                                id_return: Optional[int], 
                                user_name: str, avatar: str, created_at: str, 
                                verified: bool, add_to_db: bool):
        """
        Sends a message to all active WebSocket connections. If `add_to_db` is True, it also
        adds the message to the database.
        """
        
        timezone = pytz.timezone('UTC')
        current_time_utc = datetime.now(timezone).isoformat()
        file_id = None
        vote_count = 0


        if add_to_db:
            file_id = await self.add_all_to_database(file, message, rooms, receiver_id, id_return)

        socket_message = schemas.SocketModel(
            id=file_id,
            created_at=current_time_utc,
            receiver_id=receiver_id,
            message=message,
            fileUrl=file,
            id_return=id_return,
            user_name=user_name,
            verified=verified,
            avatar=avatar,
            vote=0,
            edited=False
        )

        message_json = socket_message.model_dump_json()
        
        # Send the message only to the specified user_id
        connection = self.user_connections.get(user_id)
        if connection:
            await connection[0].send_text(message_json) 