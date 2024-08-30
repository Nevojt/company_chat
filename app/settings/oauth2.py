
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..schemas.schemas import TokenData

from ..models import models
from ..settings.database import get_async_session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


async def create_access_token(data: dict, db: AsyncSession):
    user_id = data.get("user_id")
    user = await db.execute(select(models.User).filter(models.User.id == user_id))
    user = user.scalar()

    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update({
        "exp": expire,
        "password_changed": str(user.password_changed)
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



async def verify_access_token(token: str, credentials_exception, db: AsyncSession):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception

        user = await db.execute(select(models.User).filter(models.User.id == user_id))
        user = user.scalar()

        if user is None or str(user.password_changed) != payload['password_changed']:
            raise credentials_exception 

        token_data = TokenData(id=user_id)
    except JWTError:
        raise credentials_exception

    return token_data

    
async def get_current_user(token: str = Depends(oauth2_scheme),
                           db: AsyncSession = Depends(get_async_session)):
    """
    Get the currently authenticated user.

    Args:
        token (str): The access token.
        db (AsyncSession): The database session.

    Returns:
        user_model.User: The currently authenticated user.

    Raises:
        HTTPException: If the credentials are invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="Could not validate credentials", 
        headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = await verify_access_token(token, credentials_exception, db)
    
    
    user = await db.execute(select(models.User).filter(models.User.id == token.id))
    user = user.scalar()
    
    return user