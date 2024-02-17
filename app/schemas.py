from typing import Optional
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from datetime import datetime

        

    
        
class SocketModel(BaseModel):
    created_at: datetime
    receiver_id: int
    id: int
    message: str
    user_name: str
    avatar: str
    verified: bool
    vote: int
    id_return: Optional[int] = None 
    
    class Config:
        from_attributes = True
        
class SocketUpdate(BaseModel):
    id: int
    message: str
    
class SocketDelete(BaseModel):
    id: int
        
        
    
class TokenData(BaseModel):
    id: Optional[int] = None
    
class Vote(BaseModel):
    message_id: int
    dir: Annotated[int, Field(strict=True, le=1)]