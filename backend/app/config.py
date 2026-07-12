import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret(secret_name: str, env_var: str | None = None, default: str = "") -> str:
    """
    优先级读取敏感配置：
    1. Docker secrets 文件（/run/secrets/ 或 SECRETS_DIR）
    2. 项目本地 secrets/ 目录（开发环境直连时使用）
    3. 系统环境变量
    4. 默认值
    """
    # Docker / 自定义 secrets 目录
    secrets_dirs = [os.getenv("SECRETS_DIR", ""), "/run/secrets", str(Path(__file__).resolve().parent.parent / "secrets")]

    for secrets_dir in secrets_dirs:
        if not secrets_dir:
            continue
        # Docker 挂载时无后缀，本地文件可能是 secret.txt
        for name in (secret_name, f"{secret_name}.txt"):
            secret_path = Path(secrets_dir) / name
            if secret_path.is_file():
                return secret_path.read_text(encoding="utf-8").strip()

    # 系统环境变量
    if env_var:
        env_value = os.getenv(env_var)
        if env_value:
            return env_value

    return default


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略 .env 中的旧字段名（DATABASE_URL 等已改为 @property）
    )

    # 应用
    APP_NAME: str = "qingyun-zhixue"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    @property
    def SECRET_KEY(self) -> str:
        return _read_secret("secret_key", "SECRET_KEY", "change-me")

    # 数据库
    DATABASE_USER: str = "postgres"
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "qingyun"
    DATABASE_POOL_SIZE: int = 20

    @property
    def DATABASE_URL(self) -> str:
        password = _read_secret("postgres_password", "POSTGRES_PASSWORD", "postgres")
        return (
            f"postgresql+asyncpg://{self.DATABASE_USER}:{password}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @property
    def REDIS_URL(self) -> str:
        password = _read_secret("redis_password", "REDIS_PASSWORD", "")
        if password:
            return f"redis://:{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # Meilisearch
    MEILISEARCH_URL: str = "http://localhost:7700"

    @property
    def MEILISEARCH_MASTER_KEY(self) -> str:
        return _read_secret("meilisearch_master_key", "MEILISEARCH_MASTER_KEY", "masterKey_dev")

    # JWT
    @property
    def JWT_SECRET_KEY(self) -> str:
        return _read_secret("jwt_secret_key", "JWT_SECRET_KEY", "change-me")

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"

    @property
    def DEEPSEEK_API_KEY(self) -> str | None:
        val = _read_secret("deepseek_api_key", "DEEPSEEK_API_KEY", "")
        return val if val else None

    @property
    def QWEN_API_KEY(self) -> str | None:
        val = os.getenv("QWEN_API_KEY", "")
        return val if val else None

    @property
    def ANTHROPIC_API_KEY(self) -> str | None:
        val = os.getenv("ANTHROPIC_API_KEY", "")
        return val if val else None

    @property
    def OPENAI_API_KEY(self) -> str | None:
        val = os.getenv("OPENAI_API_KEY", "")
        return val if val else None

    # 嵌入模型
    EMBEDDING_MODEL: str = "bge-small-zh-v1.5"
    EMBEDDING_DIM: int = 512
    HF_ENDPOINT: str = "https://hf-mirror.com"

    # 搜索API
    @property
    def BING_SEARCH_API_KEY(self) -> str | None:
        val = os.getenv("BING_SEARCH_API_KEY", "") or _read_secret("bing_search_api_key", "", "")
        return val if val else None

    # 对象存储
    @property
    def OSS_ACCESS_KEY(self) -> str | None:
        val = os.getenv("OSS_ACCESS_KEY", "") or _read_secret("oss_access_key", "", "")
        return val if val else None

    @property
    def OSS_SECRET_KEY(self) -> str | None:
        val = os.getenv("OSS_SECRET_KEY", "") or _read_secret("oss_secret_key", "", "")
        return val if val else None

    OSS_BUCKET: str = "qingyun-zhixue"
    OSS_ENDPOINT: str | None = None

    # Celery
    @property
    def CELERY_BROKER_URL(self) -> str:
        password = _read_secret("redis_password", "REDIS_PASSWORD", "")
        if password:
            return f"redis://:{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/1"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        password = _read_secret("redis_password", "REDIS_PASSWORD", "")
        if password:
            return f"redis://:{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/2"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/2"

    # Agent
    AGENT_MAX_STEPS: int = 6
    AGENT_TOKEN_BUDGET: int = 16000

    # Agent 对话历史
    AGENT_MAX_CONVERSATION_TURNS: int = 10
    AGENT_AUTO_TITLE: bool = True

    # 搜索增强
    SEARCH_HIGHLIGHT_ENABLED: bool = True
    SEARCH_SEMANTIC_WEIGHT: float = 0.3
    SEARCH_MEILISEARCH_TIMEOUT: int = 5000

    # 用户记忆
    MEMORY_HABIT_SUMMARY_MAX_TOKENS: int = 300
    MEMORY_RECALL_MAX_TOKENS: int = 800
    MEMORY_INDEX_CACHE_TTL: int = 3600

    # Cancel Token
    AGENT_CANCEL_TTL: int = 300

    # [Sprint 9] AI 整理笔记配置
    ORGANIZE_MAX_NOTES: int = 20
    ORGANIZE_MAX_PROMPT_LENGTH: int = 2000
    ORGANIZE_LLM_TEMPERATURE: float = 0.7
    ORGANIZE_LLM_MAX_TOKENS: int = 4096


settings = Settings()
