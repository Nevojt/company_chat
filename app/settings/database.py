import time
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from typing import AsyncGenerator
from .config import settings
import psycopg2
from psycopg2.extras import RealDictCursor


Base = declarative_base()
          
ASINC_SQLALCHEMY_DATABASE_URL = f'postgresql+asyncpg://{settings.database_name}:{settings.database_password_company}@{settings.database_hostname_company}:{settings.database_port}/{settings.database_username}'

engine_asinc = create_async_engine(ASINC_SQLALCHEMY_DATABASE_URL)
async_session_maker = sessionmaker(engine_asinc, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


while True:   
    try:
        conn = psycopg2.connect(host=settings.database_hostname_company, database=settings.database_name, user=settings.database_username,
                                password=settings.database_password_company, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        print("Database connection was successful")
        break

    except Exception as error:
            print('Connection to database failed')
            print("Error:",  error)
            time.sleep(2)