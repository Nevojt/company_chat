from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from app.connection_manager import ConnectionManager
from app.database import get_async_session
from app import models, schemas, oauth2
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, func, desc
from typing import List

router = APIRouter(
    tags=["Chat"]
)


            
manager = ConnectionManager()


async def fetch_last_messages(rooms: str, session: AsyncSession) -> List[schemas.SocketModel]:
    query = select(
        models.Socket, 
        models.User, 
        func.coalesce(func.sum(models.Vote.dir), 0).label('votes')
    ).outerjoin(
        models.Vote, models.Socket.id == models.Vote.message_id
    ).join(
        models.User, models.Socket.receiver_id == models.User.id
    ).filter(
        models.Socket.rooms == rooms
    ).group_by(
        models.Socket.id, models.User.id
    ).order_by(
        desc(models.Socket.created_at)
    ).limit(50)

    result = await session.execute(query)
    raw_messages = result.all()

    # Convert raw messages to SocketModel
    messages = [
        schemas.SocketModel(
            created_at=socket.created_at,
            receiver_id=socket.receiver_id,
            message=socket.message,
            user_name=user.user_name,
            avatar=user.avatar,
            id=socket.id,
            vote=votes  # Додавання кількості голосів
        )
        for socket, user, votes in raw_messages
    ]
    messages.reverse()
    return messages



@router.websocket("/ws/{rooms}")
async def websocket_endpoint(
    websocket: WebSocket,
    rooms: str,
    token: str,
    session: AsyncSession = Depends(get_async_session)
    ):
    
    user = await oauth2.get_current_user(token, session)

    await manager.connect(websocket, user.id, user.user_name, user.avatar)
    
    x_real_ip = websocket.headers.get('x-real-ip')
    x_forwarded_for = websocket.headers.get('x-forwarded-for')

    # Використання отриманих IP-адрес
    print(f"X-Real-IP: {x_real_ip}")
    print(f"X-Forwarded-For: {x_forwarded_for}")
    
    await manager.send_active_users()
    
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
                    await websocket.send_json({"error": str(e)})
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
        
        await manager.send_active_users()
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await manager.broadcast(f"Цей користувач -> {user.user_name} пішов з чату 🏃",
                                rooms=rooms,
                                created_at=current_time,
                                receiver_id=user.id,
                                user_name=user.user_name,
                                avatar=user.avatar,
                                
                                add_to_db=False)


async def process_vote(vote: schemas.Vote, session: AsyncSession, current_user: models.User):
    
    # Виконання запиту і отримання першого результату
    result = await session.execute(select(models.Socket).filter(models.Socket.id == vote.message_id))
    message = result.scalars().first()
    
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Message with id: {vote.message_id} does not exist")
    
    # Перевірка наявності голосу
    vote_result = await session.execute(select(models.Vote).filter(
        models.Vote.message_id == vote.message_id, 
        models.Vote.user_id == current_user.id
    ))
    found_vote = vote_result.scalars().first()
    
    if vote.dir == 1:
        if found_vote:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"User {current_user.id} has already voted on post {vote.message_id}")
            
        new_vote = models.Vote(message_id=vote.message_id, user_id=current_user.id, dir=vote.dir)
        session.add(new_vote)
        await session.commit()
        return {"message": "Successfully added vote"}

    else:
        if not found_vote:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Vote does not exist")
        
        await session.delete(found_vote)
        await session.commit()
        
        return {"message" : "Successfully deleted vote"}









@router.get('/ws/{rooms}/users')
async def active_users(rooms: str):
    active_users = [{"user_id": user_id, "user_name": user_info[1], "avatar": user_info[2]} for user_id, user_info in manager.user_connections.items()]
    return {"rooms": rooms, "active_users": active_users}