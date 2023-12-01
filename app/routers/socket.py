from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.connection_manager import ConnectionManager
from app.database import get_async_session
from app import oauth2
from .. import schemas
from sqlalchemy.ext.asyncio import AsyncSession

from .func_socket import fetch_last_messages, update_room_for_user, update_room_for_user_live, process_vote

router = APIRouter(
    tags=["Chat"]
)


            
manager = ConnectionManager()


@router.websocket("/ws/{rooms}")
async def websocket_endpoint(
    websocket: WebSocket,
    rooms: str,
    token: str,
    session: AsyncSession = Depends(get_async_session)
    ):
    
    user = await oauth2.get_current_user(token, session)

    await manager.connect(websocket, user.id, user.user_name, user.avatar, rooms)
    
    await update_room_for_user(user.id, rooms, session)
    
    # x_real_ip = websocket.headers.get('x-real-ip')
    # x_forwarded_for = websocket.headers.get('x-forwarded-for')

    # # Використання отриманих IP-адрес
    # print(f"X-Real-IP: {x_real_ip}")
    # print(f"X-Forwarded-For: {x_forwarded_for}")
    
    await manager.send_active_users(rooms)
    
    # Отримуємо останні повідомлення
    messages = await fetch_last_messages(rooms, session)

    # Відправляємо кожне повідомлення користувачеві
    for message in messages:  
        await websocket.send_text(message.model_dump_json()) 
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if 'vote' in data:
                try:
                    vote_data = schemas.Vote(**data['vote'])
                    await process_vote(vote_data, session, user)
                    
                    messages = await fetch_last_messages(rooms, session)
                    for message in messages:
                    
                        for connection in manager.active_connections:
                            await connection.send_text(message.model_dump_json())

                except Exception as e:
                    await websocket.send_json({"message": "This message already has like"})
            
            
            elif 'type' in data:   
                await manager.notify_users_typing(rooms, user.user_name, user.id)
                    
            else:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
                await manager.broadcast(f"{data['message']}",
                                        
                                        rooms=rooms,
                                        created_at=current_time,
                                        receiver_id=user.id,
                                        user_name=user.user_name,
                                        avatar=user.avatar,
                                        add_to_db=True)
                
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        await update_room_for_user_live(user.id, session)
        
        await manager.send_active_users(rooms)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await manager.broadcast(f"Користувач -> {user.user_name} пішов з чату {rooms}",
                                rooms=rooms,
                                created_at=current_time,
                                receiver_id=user.id,
                                user_name=user.user_name,
                                avatar=user.avatar,
                                add_to_db=False)
        
        
# @router.get('/ws/{rooms}/users')
# async def active_users(rooms: str):
#     active_users = [{"user_id": user_id, "user_name": user_info[1], "avatar": user_info[2]} for user_id, user_info in manager.user_connections.items()]
#     return {"rooms": rooms, "active_users": active_users}