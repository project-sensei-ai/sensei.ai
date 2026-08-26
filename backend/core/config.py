from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Sensei"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    # MongoDB
    MONGO_DB: str = ""
    MONGO_DB_NAME: str = "sensei"

    # Auth
    JWT_SECRET: str = ""
    JWT_EXPIRE_DAYS: int = 7
    GOOGLE_CLIENT_ID: str = ""

    # Agent / Vector store
    GROQ_API_KEY: str = ""
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # Frontend (used for invite URL generation)
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
