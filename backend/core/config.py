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

    # AWS / Bedrock AgentCore
    AWS_REGION: str = "us-east-1"
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    LLM_BACKEND: str = "groq"   # "bedrock" | "groq" | "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen3:4b"

    # Phase 2: S3 session storage (set when LLM_BACKEND=bedrock)
    S3_SESSION_BUCKET: str = ""

    # Phase 3: Bedrock Knowledge Bases
    S3_UPLOAD_BUCKET: str = ""
    BEDROCK_KB_ID: str = ""
    BEDROCK_KB_DATA_SOURCE_ID: str = ""  # required to trigger KB sync after upload

    # Frontend (used for invite URL generation)
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
