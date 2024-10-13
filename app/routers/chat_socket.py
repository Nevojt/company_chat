from datetime import datetime

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.settings.connection_manager import ConnectionManager
from app.settings.database import get_async_session
from app.settings import oauth2
from ..schemas import schemas
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.func_socket import update_user_status, change_message, fetch_last_messages, update_room_for_user, \
    update_room_for_user_live, process_vote, delete_message, fetch_one_message, send_messages_via_websocket
from app.functions.func_socket import fetch_room_data, send_message_blocking, ban_user, send_message_mute_user, \
    start_session, end_session, get_room, send_message_deleted_room, count_messages_in_room

from app.functions.moderator import censor_message, load_banned_words, tag_sayory
from app.AI import sayory


banned_words = load_banned_words("app/functions/banned_words.csv")

# Logging settings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Chat"]
)

manager = ConnectionManager()


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        room_id: int,
        limit: int = 20,
        token: str = '',
        session: AsyncSession = Depends(get_async_session)
):
    user = await oauth2.get_current_user(token, session)

    if user.blocked:
        await websocket.close(code=1008)
        return
    room_name = await get_room(room_id, session)
    await count_messages_in_room(room_name, session)
    # print(room)

    room_data = await fetch_room_data(room_name, session)
    user_baned = await ban_user(room_name, user, session)

    await manager.connect(websocket, user.id, user.user_name, user.avatar, room_name, user.verified)

    if room_data.block:
        if user.role != 'admin':
            await send_message_blocking(room_name, manager, session)
            await websocket.close(code=1008)
            return
        else:
            logger.info(f"Admin {user.user_name} has accessed the blocked room {room_name}.")

    await update_room_for_user(user.id, room_name, session)

    x_real_ip = websocket.headers.get('x-real-ip')
    x_forwarded_for = websocket.headers.get('x-forwarded-for')

    await start_session(user.id, session)

    # Use of received IP addresses
    print(f"X-Real-IP: {x_real_ip}")
    print(f"X-Forwarded-For: {x_forwarded_for}")

    await manager.send_active_users(room_name)

    # Get the latest notifications
    await update_user_status(session, user.id, True)

    messages = await fetch_last_messages(room_name, limit, session)

    await send_messages_via_websocket(messages, websocket)

    await send_message_deleted_room(room_id, manager, session)
    try:
        while True:
            data = await websocket.receive_json()

            if 'type' in data:
                if not user_baned:
                    await manager.notify_users_typing(room_name, user.user_name, user.id)
                continue

            if 'limit' in data:
                limit = data['limit']

                messages = await fetch_last_messages(room_name, limit, session)

                count_messages = await count_messages_in_room(room_name, session)
                limit = min(limit, count_messages)

                if limit < count_messages:
                    await websocket.send_json({"notice": "Load older messages"})
                else:
                    await websocket.send_json({"notice": "Loading all messages"})

                await send_messages_via_websocket(messages, websocket)

            if user_baned:
                await send_message_mute_user(room_name, user, manager, session)
                continue
            # Created likes
            if 'vote' in data:
                try:
                    vote_data = schemas.Vote(**data['vote'])
                    await process_vote(vote_data, session, user)

                    message_json = await fetch_one_message(vote_data.message_id, session)
                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_text(message_json)

                except Exception as e:
                    logger.error(f"Error processing vote: {e}", exc_info=True)
                    await websocket.send_json({"notice": f"Error processing vote: {e}"})

            # Block change message
            elif 'update' in data:
                try:
                    message_data = schemas.SocketUpdate(**data['update'])

                    censored_text = censor_message(message_data.message, banned_words)
                    await change_message(message_data.id, schemas.SocketUpdate(id=message_data.id,
                                                                               message=censored_text
                                                                               ), session, user)
                    update_message = await fetch_one_message(message_data.id, session)

                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_text(update_message)

                except Exception as e:
                    logger.error(f"Error processing change: {e}", exc_info=True)
                    await websocket.send_json({"notice": f"Error processing change: {e}"})

            # Block delete message
            elif 'delete' in data:
                try:
                    message_data = schemas.SocketDelete(**data['delete'])
                    message_id = await delete_message(message_data.id, session, user)

                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_json({"deleted": {"id": message_id}})



                except Exception as e:
                    logger.error(f"Error processing deleted: {e}", exc_info=True)
                    await websocket.send_json({"notice": f"Error processing deleted: {e}"})

            # Block send message
            elif 'send' in data:
                message_data = data['send']
                original_message_id = message_data['original_message_id']
                original_message = message_data['message']
                file_url = message_data['fileUrl']

                if original_message is not None:
                    censored_message = censor_message(original_message, banned_words)
                else:
                    censored_message = None

                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if censored_message != original_message:
                    warning_message = {
                        "type": "system_warning",
                        "content": "Your message has been modified because it contained obscene language."
                    }
                    await websocket.send_json(warning_message)

                await manager.broadcast_all(
                    message=censored_message,
                    file=file_url,
                    rooms=room_name,
                    created_at=current_time,
                    receiver_id=user.id,
                    user_name=user.user_name,
                    avatar=user.avatar,
                    verified=user.verified,
                    id_return=original_message_id,
                    room_id=room_id,
                    add_to_db=True
                )

                if censor_message is not None and tag_sayory(censored_message):
                    response_sayory = await sayory.ask_to_gpt(censored_message)
                    await manager.broadcast_all(
                        message=response_sayory,
                        file=file_url,
                        rooms=room_name,
                        created_at=current_time,
                        receiver_id=2,
                        user_name="SayOry",
                        avatar="https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/girl_5.webp",
                        verified=True,
                        id_return=original_message_id,
                        room_id=room_id,
                        add_to_db=True
                    )


    except WebSocketDisconnect:
        print("Couldn't connect to")
        manager.disconnect(websocket, user.id)
    finally:
        await end_session(user.id, session)
        await update_room_for_user(user.id, 'Hell', session)
        await update_user_status(session, user.id, False)
        await update_room_for_user_live(user.id, session)
        await manager.send_active_users(room_name)
        await session.close()
        print("Session closed")