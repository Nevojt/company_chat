from datetime import datetime
import pytz
import json
import logging
from fastapi import WebSocket
from app.settings.database import async_session_maker
from app.models import models
from sqlalchemy import insert
from typing import List, Dict, Tuple


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
        
    async def add_reply_to_database(self, user_id: int, room: str, reply_to_message_id: int, reply_message: str, session):
        """
        Adds a reply message to the database asynchronously.
        """
        try:
            # Якщо транзакція вже активна, просто додаємо повідомлення без початку нової транзакції
            new_reply = models.Socket(
                message=reply_message,
                receiver_id=user_id,
                rooms=room,
                id_return=reply_to_message_id
            )
            session.add(new_reply)
            await session.commit()

        except Exception as e:
            # Обробка можливих винятків
            logging.error(f"Error creating message to database, {e}")
            await session.rollback()
            raise

        return new_reply.id

        


    async def broadcast(self, message: str, rooms: str, receiver_id: int, 
                        user_name: str, avatar: str, created_at: str, 
                        id_return: int, verified: bool, add_to_db: bool):
        """
        Sends a message to all active WebSocket connections. If `add_to_db` is True, it also
        adds the message to the database.
        """
        

        # Встановіть часовий пояс UTC
        timezone = pytz.timezone('UTC')

        # Отримайте поточний час у форматі ISO 8601 з UTC часовим поясом
        current_time_utc = datetime.now(timezone).isoformat()
        message_id = None
        vote_count = 0
        imageUrl = None

        if add_to_db:
            message_id = await self.add_messages_to_database(message, rooms, receiver_id, id_return)

        message_data = {
            
            "created_at": current_time_utc,
            "receiver_id": receiver_id,
            "id": message_id,
            "message": message,
            "imageUrl": imageUrl,
            "user_name": user_name,
            "verified": verified,
            "avatar": avatar,
            "vote": vote_count,
            "id_return": id_return
                
        }

        message_json = json.dumps(message_data, ensure_ascii=False)

        # Send the message only to users in the specified room
        for user_id, (connection, _, _, user_room, _) in self.user_connections.items():
            if user_room == rooms:
                await connection.send_text(message_json)   

    @staticmethod
    async def add_messages_to_database(message: str, rooms: str, receiver_id: int, id_message: int):
        """
        Adds a message to the database asynchronously.
        """
        async with async_session_maker() as session:
            stmt = insert(models.Socket).values(message=message, rooms=rooms, receiver_id=receiver_id, id_return=id_message)
            result =  await session.execute(stmt)
            await session.commit()
            
            message_id = result.inserted_primary_key[0]
            return message_id
        
        
    async def broadcast_file(self, file: str, rooms: str, receiver_id: int, 
                        user_name: str, avatar: str, created_at: str, 
                        verified: bool, add_to_db: bool):
        """
        Sends a message to all active WebSocket connections. If `add_to_db` is True, it also
        adds the message to the database.
        """
        

        # Встановіть часовий пояс UTC
        timezone = pytz.timezone('UTC')

        # Отримайте поточний час у форматі ISO 8601 з UTC часовим поясом
        current_time_utc = datetime.now(timezone).isoformat()
        file_id = None
        vote_count = 0

        if add_to_db:
            file_id = await self.add_file_to_database(file, rooms, receiver_id)

        message_data = {
            
            "created_at": current_time_utc,
            "receiver_id": receiver_id,
            "id": file_id,
            "fileUrl": file,
            "user_name": user_name,
            "verified": verified,
            "avatar": avatar,
            "vote": vote_count,
                
        }

        message_json = json.dumps(message_data, ensure_ascii=False)

        # Send the message only to users in the specified room
        for user_id, (connection, _, _, user_room, _) in self.user_connections.items():
            if user_room == rooms:
                await connection.send_text(message_json)   

    @staticmethod
    async def add_file_to_database(fileUrl: str, rooms: str, receiver_id: int):
        """
        Adds a message to the database asynchronously.
        """
        async with async_session_maker() as session:
            stmt = insert(models.Socket).values(fileUrl=fileUrl, rooms=rooms, receiver_id=receiver_id)
            result =  await session.execute(stmt)
            await session.commit()
            
            message_id = result.inserted_primary_key[0]
            return message_id
            
             
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

    
    