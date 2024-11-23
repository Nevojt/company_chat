from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import psycopg2
from psycopg2.extras import RealDictCursor
import time

from .config import settings

# URL налаштування для підключення до бази даних
ASYNC_SQLALCHEMY_DATABASE_URL = (
    f'postgresql+asyncpg://{settings.database_username}:'
    f'{settings.database_password}@{settings.database_hostname}:'
    f'{settings.database_port}/{settings.database_name}'
)

Base = declarative_base()

# Створення асинхронного двигуна
engine_async = create_async_engine(ASYNC_SQLALCHEMY_DATABASE_URL)
async_session_maker = async_sessionmaker(bind=engine_async, expire_on_commit=False)

# Асинхронна функція для отримання сесії
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


# test session database


while True:
    try:
        conn = psycopg2.connect(
            host=settings.database_hostname,
            database=settings.database_name,
            user=settings.database_username,
            password=settings.database_password,
            cursor_factory=RealDictCursor,
        )
        cursor = conn.cursor()
        print("Database connection was successful")
        break

    except Exception as error:
        print("Connection to database failed")
        print("Error:", error)
        time.sleep(2)