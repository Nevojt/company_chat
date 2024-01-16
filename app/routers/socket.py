from datetime import datetime
import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.connection_manager import ConnectionManager
from app.database import get_async_session
from app import oauth2
from .. import schemas
from sqlalchemy.ext.asyncio import AsyncSession

from .func_socket import change_message, fetch_last_messages, update_room_for_user, update_room_for_user_live, process_vote, delete_message

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Chat"]
)


            
manager = ConnectionManager()


@router.websocket("/ws/{room}")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str,
    token: str,
    session: AsyncSession = Depends(get_async_session)
    ):
    
    user = await oauth2.get_current_user(token, session)

    await manager.connect(websocket, user.id, user.user_name, user.avatar, room, user.verified)
    
    await update_room_for_user(user.id, room, session)
    
    x_real_ip = websocket.headers.get('x-real-ip')
    x_forwarded_for = websocket.headers.get('x-forwarded-for')

    # Використання отриманих IP-адрес
    print(f"X-Real-IP: {x_real_ip}")
    print(f"X-Forwarded-For: {x_forwarded_for}")
    
    await manager.send_active_users(room)
    
    # Отримуємо останні повідомлення
    messages = await fetch_last_messages(room, session)

    # Відправляємо кожне повідомлення користувачеві
    for message in messages:  
        await websocket.send_text(message.model_dump_json()) 
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Created likes
            if 'vote' in data:
                try:
                    vote_data = schemas.Vote(**data['vote'])
                    await process_vote(vote_data, session, user)
                 
                    messages = await fetch_last_messages(room, session)
                    
                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_json({"message": "Vote posted "})
                        if user_room == room:
                            for message in messages:
                                await connection.send_text(message.model_dump_json())
                                

                except Exception as e:
                    logger.error(f"Error processing vote: {e}", exc_info=True)  # Запис помилки
                    await websocket.send_json({"message": f"Error processing vote: {e}"})
                    
            # Block change message 
            elif 'change_message' in data:
                try:
                    message_data = schemas.SocketUpdate(**data['change_message'])
                    await change_message(message_data.id, message_data, session, user)
                    
                    messages = await fetch_last_messages(room, session)
                    
                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_json({"message": "Message updated "})
                        if user_room == room:
                            for message in messages:
                                await connection.send_text(message.model_dump_json())
                                
                except Exception as e:
                    logger.error(f"Error processing change: {e}", exc_info=True)  # Запис помилки
                    await websocket.send_json({"message": f"Error processing change: {e}"})
            
            # Block delete message       
            elif 'delete_message' in data:
                try:
                    message_data = schemas.SocketDelete(**data['delete_message'])
                    await delete_message(message_data.id, session, user)
                    
                    messages = await fetch_last_messages(room, session)
                    
                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_json({"message": "Message delete"})
                        if user_room == room:
                            for message in messages:
                                await connection.send_text(message.model_dump_json())
                                
                except Exception as e:
                    logger.error(f"Error processing delete: {e}", exc_info=True)  # Запис помилки
                    await websocket.send_json({"message": f"Error processing deleted: {e}"})
                    
            # Block reply message     
            elif 'reply' in data:
                # Обробка відповіді на повідомлення
                reply_data = data['reply']
                original_message_id = reply_data['original_message_id']
                reply_message = reply_data['message']

                # await websocket.send_json({"message": "Reload"})
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await manager.broadcast(
                                    message=reply_message,
                                    rooms=room,
                                    created_at=current_time,
                                    receiver_id=user.id,
                                    user_name=user.user_name,
                                    avatar=user.avatar,
                                    verified=user.verified,
                                    id_message=original_message_id,
                                    add_to_db=True) 
                
            # Blok following typing message
            elif 'type' in data:   
                await manager.notify_users_typing(room, user.user_name, user.id)
            
            # Block send message     
            else:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
                await manager.broadcast(f"{data['message']}",
                                        rooms=room,
                                        created_at=current_time,
                                        receiver_id=user.id,
                                        user_name=user.user_name,
                                        avatar=user.avatar,
                                        verified=user.verified,
                                        id_message=None,
                                        add_to_db=True)
                
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        await update_room_for_user_live(user.id, session)
        
        await manager.send_active_users(room)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await manager.broadcast(f"Користувач -> {user.user_name} пішов з чату {room}",
                                rooms=room,
                                created_at=current_time,
                                receiver_id=user.id,
                                user_name=user.user_name,
                                avatar=user.avatar,
                                verified=user.verified,
                                id_message=None,
                                add_to_db=False)
        
        
# @router.get('/ws/{room}/users')
# async def active_users(room: str):
#     active_users = [{"user_id": user_id, "user_name": user_info[1], "avatar": user_info[2]} for user_id, user_info in manager.user_connections.items()]
#     return {"room": room, "active_users": active_users}