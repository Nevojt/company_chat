from datetime import datetime
import json
from fastapi import WebSocket
from app.database import async_session_maker
from app import models
from sqlalchemy import insert
from typing import List, Dict, Tuple








class ConnectionManager:
    def __init__(self):
        # List to store active WebSocket connections
        self.active_connections: List[WebSocket] = []
        
        # Dictionary to map user IDs to their WebSocket connection, username, and avatar
        self.user_connections: Dict[int, Tuple[WebSocket, str, str, str]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, user_name: str, avatar: str, room: str):
        """
        Accepts a new WebSocket connection and stores it in the list of active connections
        and the dictionary of user connections.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[user_id] = (websocket, user_name, avatar, room)

    def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Removes a WebSocket connection from the list of active connections and the user
        connections dictionary when a user disconnects.
        """
        self.active_connections.remove(websocket)
        self.user_connections.pop(user_id, None)
        


    async def broadcast(self, message: str, rooms: str, receiver_id: int, user_name: str, avatar: str, created_at: str, add_to_db: bool):
        """
        Sends a message to all active WebSocket connections. If `add_to_db` is True, it also
        adds the message to the database.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_id = None

        if add_to_db:
            message_id = await self.add_messages_to_database(message, rooms, receiver_id)

        message_data = {
            
            "created_at": current_time,
            "receiver_id": receiver_id,
            "id": message_id,
            "message": message,
            "user_name": user_name,
            "avatar": avatar,         
        }

        message_json = json.dumps(message_data, ensure_ascii=False)

        # Send the message only to users in the specified room
        for user_id, (connection, _, _, user_room) in self.user_connections.items():
            if user_room == rooms:
                await connection.send_text(message_json)

    @staticmethod
    async def add_messages_to_database(message: str, rooms: str, receiver_id: int):
        """
        Adds a message to the database asynchronously.
        """
        async with async_session_maker() as session:
            stmt = insert(models.Socket).values(message=message, rooms=rooms, receiver_id=receiver_id)
            result =  await session.execute(stmt)
            await session.commit()
            
            message_id = result.inserted_primary_key[0]
            return message_id
            
             
    async def send_active_users(self, room: str):
            """
            Sends the list of active users in a specific room to all connected WebSocket clients in that room.
            """
            active_users = [
                {"user_id": user_id, "user_name": user_info[1], "avatar": user_info[2]}
                for user_id, user_info in self.user_connections.items()
                if user_info[3] == room  # Check if the user is in the specified room
            ]
            message_data = {"type": "active_users", "data": active_users}

            # Send the message only to users in the specified room
            for websocket, _, _, user_room in self.user_connections.values():
                if user_room == room:
                    await websocket.send_json(message_data)
                    
                    
    async def notify_users_typing(self, room: str, user_name: str, typing_user_id: int):
        """
        Sends a message to all active WebSocket connections in a specific room 
        except for the user who is typing.
        """
        message_data = {"type": f"User {user_name} is typing"}
 
        for user_id, (connection, _, _, user_room) in self.user_connections.items():
            if user_room == room and user_id != typing_user_id:
                await connection.send_json(message_data)
