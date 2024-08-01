from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_hostname: str
    database_hostname_company: str
    database_port: str
    database_password: str
    database_password_company: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    key_crypto: str
    openai_api_key: str

    model_config = SettingsConfigDict(env_file = ".env")


settings = Settings()