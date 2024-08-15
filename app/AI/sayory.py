
from openai import AsyncOpenAI
from app.settings.config import settings


sayori_key=settings.openai_api_key

client = AsyncOpenAI(
    api_key=sayori_key
)

instruction_1 = "Ти асистент в менеджері і твоє ім'я Sayory далі буде повідомлення від користувача:  "
instruction_2 = " Твоя відповідь не повинна перевищувати 600 символів."

async def ask_to_gpt(ask_to_chat: str) -> str:
    try:
        chat_completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                "role": "user",
                "content": instruction_1 + ask_to_chat + instruction_2,
                }
            ],
            temperature=1,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
            )
        response = chat_completion.choices[0].model_dump()
        return response["message"]["content"]
    except Exception as e:
        return "Sorry, I couldn't process your request."