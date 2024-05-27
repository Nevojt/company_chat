import asyncio
import websockets
import json

async def simulate_user(room, user_id, user_name, token):
    uri = f"wss://cool-chat.club/ws/{room}?token={token}"
    try:
        async with websockets.connect(uri) as websocket:
            # Підключення до чату
            print(f"{user_name} connected to {room}")
            
            # Симуляція надсилання повідомлень
            message = {
                "type": "send",
                "send": {
                    "original_message_id": 1,
                    "message": "Hello from {user_name}!",
                    "fileUrl": ""
                }
            }
            await websocket.send(json.dumps(message))

            # Отримання і виведення повідомлень
            response = await websocket.recv()
            print(f"Response to {user_name}: {response}")

            # Симуляція інших дій, наприклад, голосування або зміни повідомлення
            # Ваш код тут

            # Закриття підключення після завершення тесту
            await asyncio.sleep(5)
            print("Active")# Припустимо, кожен користувач активний 5 секунд
    except Exception as e:
        print(f"Error for user {user_name}: {e}")

async def main():
    # Створення кількох користувачів
    users = [
        {"room": "Hlam", "user_id": 23, "user_name": "Test", "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoyMywiZXhwIjoxNzE2ODQzNjMzfQ.dgIxHMAgkUaVBKevxRufyxVuHnY1_ichRzYCxf8F7qc"},
        {"room": "Hlam", "user_id": 3, "user_name": "Dima", "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjozLCJleHAiOjE3MTY4NDM3MjF9.WskG-SgusyT521HDuKtYyvW5T651kSj5YOFb83WJgyc"},
        # Додайте більше користувачів за потреби
    ]
    
    # Виконання асинхронних завдань для кожного користувача
    await asyncio.gather(*(simulate_user(user['room'], user['user_id'], user['user_name'], user['token']) for user in users))

if __name__ == "__main__":
    asyncio.run(main())
