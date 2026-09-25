# backend/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用全局配置

    所有字段都应有 .env 覆盖；这里的默认值只保证「不配也能起服务」，
    因此凭据类字段一律留空，避免误当成可用配置。
    """
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    LLM_MODEL: str = ""
    EMBEDDING_MODEL: str = ""
    # 本地适配：Embedding 可与对话模型走不同供应商
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    # api | local_bge | chroma_default
    EMBEDDING_PROVIDER: str = "api"
    EMBEDDING_LOCAL_MODEL: str = ""
    MAX_TOKENS: int = 500
    TEMPERATURE: float = 0.7
    DATABASE_URL: str = "sqlite+aiosqlite:///./livestream_agent.db"
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    CHROMA_COLLECTION_NAME: str = "livestream_knowledge"
    APP_NAME: str = "直播带货AI Agent"
    # 默认关闭：生产环境若忘记覆盖会把 SQL 语句和堆栈打到日志里
    DEBUG: bool = False
    BATCH_SIZE: int = 10
    ANALYSIS_INTERVAL: int = 5
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # 拼进 prompt 的检索上下文长度上限（字符），防止文档变多后 prompt 与成本失控
    RAG_CONTEXT_MAX_CHARS: int = 4000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
