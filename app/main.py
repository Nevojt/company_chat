
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat_socket

import sentry_sdk
from .settings.config import settings

# sentry_sdk.init(
#     dsn=settings.sentry_url,
#     # Set traces_sample_rate to 1.0 to capture 100%
#     # of transactions for tracing.
#     traces_sample_rate=1.0,
#     # Set profiles_sample_rate to 1.0 to profile 100%
#     # of sampled transactions.
#     # We recommend adjusting this value in production.
#     profiles_sample_rate=1.0,
# )
app = FastAPI(
    docs_url="/docs",
    title="Chat",
    version="0.1.0",
    description="Chat API",
    
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat_socket.router)
