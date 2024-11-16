
from pydantic import BaseModel, Field, UUID4, Strict
from typing import Annotated, Optional
from datetime import datetime

        

    
        
class ChatMessagesSchema(BaseModel):
    created_at: datetime
    receiver_id:  Annotated[UUID4, Strict(False)] = None
    id: Annotated[UUID4, Strict(False)]
    message: Optional[str] = None
    fileUrl: Optional[str] = None
    voiceUrl: Optional[str] = None
    videoUrl: Optional[str] = None
    user_name: Optional[str] = "USER DELETE"
    avatar: Optional[str] = "https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/boy_1.webp"
    verified: Optional[bool] = None
    vote: int
    id_return: Optional[UUID4] = None
    edited: bool
    deleted: bool
    room_id: Annotated[UUID4, Strict(False)] = None


# Send message to chat
class WrappedSocketMessage(BaseModel):
    message: ChatMessagesSchema


async def wrap_message(chat_model_instance: ChatMessagesSchema) -> WrappedSocketMessage:
    return WrappedSocketMessage(message=chat_model_instance)


# Update message in chat
class WrappedUpdateMessage(BaseModel):
    update: ChatMessagesSchema
        
async def wrap_message_update(socket_model_update: ChatMessagesSchema) -> WrappedUpdateMessage:
    return WrappedUpdateMessage(update=socket_model_update)


class ChatUpdateMessage(BaseModel):
    id: Annotated[UUID4, Strict(False)]
    message: str
    
class ChatMessageDelete(BaseModel):
    id: Annotated[UUID4, Strict(False)]
        
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Annotated[UUID4, Strict(False)]
    
class Vote(BaseModel):
    message_id: Annotated[UUID4, Strict(False)]
    dir: Annotated[int, Field(strict=True, le=1)]