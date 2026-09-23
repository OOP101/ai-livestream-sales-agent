# backend/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用全局配置"""
    OPENAI_API_KEY: str = "sk-your-api-key"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4-turbo-preview"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
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
    DEBUG: bool = True
    BATCH_SIZE: int = 10
    ANALYSIS_INTERVAL: int = 5
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
