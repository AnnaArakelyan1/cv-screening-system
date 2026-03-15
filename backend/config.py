from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    MAIL_EMAIL: str = ""
    MAIL_PASSWORD: str = ""

    class Config:
        env_file = ".env"

settings = Settings()