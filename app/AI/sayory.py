
from openai import AsyncOpenAI
from app.settings.config import settings
from _log_config.log_config import get_logger


logger = get_logger('sayory', 'sayory.log')
sayori_key=settings.openai_api_key

client = AsyncOpenAI(
    api_key=sayori_key
)

instruction = "Ти асистент в мессенджері, твоє ім'я Sayory, відповідь не повинна перевищувати 600 символів."


async def ask_to_gpt(ask_to_chat: str) -> str:
    try:
        chat_completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                "role": "system",
                "content": [
                    {
                    "type": "text",
                    "text": instruction
                    }
                ]
                },
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
        logger.error(f"Error occurred while generating response: {e}")
        return "Sorry, I couldn't process your request."