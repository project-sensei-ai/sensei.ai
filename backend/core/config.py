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
    # Encrypts source credentials at rest. Any long random string works.
    # Generate with: openssl rand -hex 32
    SECRET_ENCRYPTION_KEY: str = ""
    JWT_EXPIRE_DAYS: int = 7
    GOOGLE_CLIENT_ID: str = ""

    # Agent / Vector store
    # Paid and dependable: with an Anthropic key set, Claude answers first and
    # the free-tier chain below becomes the fallback instead of the only path.
    # Haiku 4.5 everywhere: fast, cheap, and enough for grounded answers.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_BACKGROUND_MODEL: str = "claude-haiku-4-5-20251001"
    GROQ_API_KEY: str = ""
    # Interactive chat gets the capable model. Background agents — the ones that
    # research briefs and audit for gaps — run a smaller one: they do bounded,
    # well-specified work and there are many more of them.
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_BACKGROUND_MODEL: str = "openai/gpt-oss-20b"
    # Tried in order when a model's daily quota is exhausted. Each Groq model
    # has its own quota, so the product keeps working through a demo day on a
    # free key rather than going dark at the first "tokens per day" error.
    GROQ_FALLBACK_MODELS: str = "openai/gpt-oss-120b,qwen/qwen3.8-27b,qwen/qwen3.6-27b,openai/gpt-oss-20b"
    # Extra OpenAI-compatible providers, tried after Groq's models when those
    # are capped. Any of these keys being set adds that provider to the chain.
    # All three have free tiers with no card and no local install.
    CEREBRAS_API_KEY: str = ""
    CEREBRAS_MODEL: str = "gpt-oss-120b"
    CEREBRAS_BACKGROUND_MODEL: str = "llama-3.3-70b"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_BACKGROUND_MODEL: str = "gemini-2.5-flash-lite"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-oss-120b:free"
    OPENROUTER_BACKGROUND_MODEL: str = "openai/gpt-oss-20b:free"
    # Slack as a place Sensei is spoken to, not only read from. The signing
    # secret (Slack app → Basic Information) lets the events endpoint prove a
    # request came from Slack; without it, only the team id is checked.
    SLACK_SIGNING_SECRET: str = ""
    # Answer questions nobody addressed to Sensei when the sources can cite an
    # answer. Off means it only speaks when mentioned or messaged directly.
    SLACK_PROACTIVE: bool = True
    # How long a project's research findings stay reusable before the agent
    # goes and looks again.
    RESEARCH_TTL_HOURS: int = 24
    # How often the agent re-reads connected sources looking for change.
    # 0 disables the loop; a manual check is always available.
    WATCH_INTERVAL_MINUTES: int = 0
    # How many granted (MCP) tools are offered to the model on one turn. Every
    # tool schema is re-sent on every call; a server like GitHub exposes fifty.
    # The most relevant ones are chosen per question.
    # Four covers "list the open issues and pull requests"; each schema from a
    # server like GitHub is 400–600 tokens, sent again on every model call.
    MAX_GRANT_TOOLS_PER_TURN: int = 4
    # Output ceiling per model response.
    MAX_OUTPUT_TOKENS: int = 8000
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # AWS / Bedrock AgentCore
    AWS_REGION: str = "us-east-1"
    # Declared so a .env carrying static keys loads; boto3 still reads them from the
    # environment itself. Prefer an IAM role in deployed environments.
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    # Cross-region inference profiles; the bare model ids for Claude 3.5 are
    # end-of-life on Bedrock and return ResourceNotFound.
    BEDROCK_MODEL_ID: str = "us.anthropic.claude-sonnet-4-6"
    BEDROCK_BACKGROUND_MODEL_ID: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    LLM_BACKEND: str = "groq"   # "bedrock" | "groq" | "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen3:4b"

    # Phase 2: S3 session storage (set when LLM_BACKEND=bedrock)
    S3_SESSION_BUCKET: str = ""

    # Phase 3: Bedrock Knowledge Bases
    S3_UPLOAD_BUCKET: str = ""
    BEDROCK_KB_ID: str = ""
    BEDROCK_KB_DATA_SOURCE_ID: str = ""  # required to trigger KB sync after upload

    # Outbound email — optional. Without it the invite link is returned to the
    # owner in the UI instead, which is also how reviewers test the flow.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True

    # Frontend (used for invite URL generation)
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    # Built SPA served by this app in single-origin deployments. Empty or missing
    # directory = API only (the local dev setup, where Vite serves the frontend).
    STATIC_DIR: str = "static"

    class Config:
        env_file = ".env"
        # Never crash on an unrecognised env var — a stale key in someone's .env
        # should not stop the app from booting.
        extra = "ignore"


settings = Settings()
