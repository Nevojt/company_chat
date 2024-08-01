
from openai import AsyncOpenAI
from app.settings.config import settings


sayori_key=settings.openai_api_key

client = AsyncOpenAI(
    api_key=sayori_key
)

async def ask_to_gpt(ask_to_chat: str) -> str:
    try:
        chat_completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                "role": "user",
                "content": ask_to_chat,
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