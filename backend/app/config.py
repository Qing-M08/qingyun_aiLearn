from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用
    APP_NAME: str = "qingyun-zhixue"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    SECRET_KEY: str = "change-me"

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/qingyun"
    DATABASE_POOL_SIZE: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Meilisearch
    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_MASTER_KEY: str = "masterKey_dev"

    # JWT
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM API Keys
    DEEPSEEK_API_KEY: str | None = None
    QWEN_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    # 嵌入模型
    EMBEDDING_MODEL: str = "bge-m3"
    EMBEDDING_DIM: int = 1024

    # 搜索API
    BING_SEARCH_API_KEY: str | None = None

    # 对象存储
    OSS_ACCESS_KEY: str | None = None
    OSS_SECRET_KEY: str | None = None
    OSS_BUCKET: str = "qingyun-zhixue"
    OSS_ENDPOINT: str | None = None

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Agent
    AGENT_MAX_STEPS: int = 6
    AGENT_TOKEN_BUDGET: int = 4000

    # 用户记忆
    MEMORY_HABIT_SUMMARY_MAX_TOKENS: int = 300
    MEMORY_RECALL_MAX_TOKENS: int = 800
    MEMORY_INDEX_CACHE_TTL: int = 3600


settings = Settings()
