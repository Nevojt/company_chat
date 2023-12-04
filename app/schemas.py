from typing import Optional
from pydantic import BaseModel
from pydantic.types import conint
from datetime import datetime

        
        



# class UserOut(BaseModel):
#     id: int
#     user_name: str
#     avatar: str
#     created_at: datetime
    
#     class Config:
#         from_attributes = True
    
        
class SocketModel(BaseModel):
    created_at: datetime
    receiver_id: int
    id: int
    message: str
    user_name: str
    avatar: str
    vote: int
    id_return: Optional[int] = None 
    
    class Config:
        from_attributes = True

        
        
# class UserCreate(BaseModel):
#     email: EmailStr
#     user_name: str
#     password: str
#     avatar: str
    
        
# class UserLogin(BaseModel):
#     email: EmailStr
#     password: str

# class Token(BaseModel):
#     access_token: str
#     token_type: str
    
class TokenData(BaseModel):
    id: Optional[int] = None
    
class Vote(BaseModel):
    message_id: int
    dir: conint(le=1)