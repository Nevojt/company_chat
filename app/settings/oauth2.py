from _log_config.log_config import get_logger

from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from uuid import UUID

from app.settings import database
from app.models.models import User
from app.schemas.schemas import TokenData
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.settings.config import settings

oauth2_logger = get_logger('oauth2', 'oauth2log.log')

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


async def create_access_token(user_id: UUID, db: AsyncSession):
    try:
        user = await db.execute(select(User).where(User.id == user_id))
        user = user.scalar_one_or_none()

        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {
            "exp": int(expire.timestamp()),  # Convert datetime to string
            "user_id": str(user_id),  # Ensure UUID is converted to string
            "company": str(user.company_id),
            "password_changed": str(user.password_changed)
        }

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        oauth2_logger.error(f"Error creating access token: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error creating access token")



async def verify_access_token(token: str, credentials_exception, db: AsyncSession):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("user_id")
        company_id_str: str = payload.get("company")

        if user_id_str is None or company_id_str is None:
            raise credentials_exception

        user_id = UUID(user_id_str)
        company_id = UUID(company_id_str)
        user = await db.execute(select(User).where(User.id == user_id,
                                                               User.company_id == company_id))
        user = user.scalar_one_or_none()

        if user is None or str(user.password_changed) != payload['password_changed']:
            raise credentials_exception

        token_data = TokenData(id=user_id)
        return token_data

    except JWTError:
        oauth2_logger.error(f"Invalid JWT token: {token}")
    except Exception as e:
        oauth2_logger.error(f"Error verifying access token: {e}")

        raise credentials_exception




async def get_current_user(token: str = Depends(oauth2_scheme),
                           db: AsyncSession = Depends(database.get_async_session)):
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
    try:
        token = await verify_access_token(token, credentials_exception, db)

        user = await db.execute(select(User).where(User.id == token.id))
        user = user.scalar_one_or_none()
        if not user:
            oauth2_logger.error("Could not find user")

        return user
    except Exception as e:
        oauth2_logger.error(f"Error getting current user: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error getting current user")


# async def create_refresh_token(user_id: UUID, db: AsyncSession):
#     try:# Отримання користувача з бази даних
#         user = await db.execute(select(User).filter(User.id == user_id))
#         user = user.scalar()
#
#         if not user:
#             raise Exception("User not found")  # Помилка, якщо користувач не знайдений
#
#         expire = datetime.now(timezone.utc) + timedelta(days=10)
#         to_encode = {
#             "exp": int(expire.timestamp()),
#             "user_id": str(user_id),
#             "last_password_change":str(user.password_changed)
#         }
#
#         encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#         return encoded_jwt
#     except Exception as e:
#         oauth2_logger.error(f"Error creating refresh token: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                             detail="Error creating refresh token")