# backend/rag/embedding.py
"""Embedding 后端适配层

支持三种后端，通过 .env 的 EMBEDDING_PROVIDER 切换：
- api          ：OpenAI 兼容接口（默认，需 EMBEDDING_API_KEY/BASE_URL 可用）
- local_bge    ：本地 sentence-transformers 模型（EMBEDDING_LOCAL_MODEL 指向模型目录）
- chroma_default：ChromaDB 内置 ONNX 模型（onnxruntime 离线推理，无需额外依赖）
"""
from typing import List
from core.config import settings


class _ApiEmbedding:
    """OpenAI 兼容接口"""

    def __init__(self):
        from core.llm_client import get_embedding_model
        self._model = get_embedding_model()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._model.embed_query(text)


class _LocalBgeEmbedding:
    """本地 sentence-transformers 模型"""

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        model_path = settings.EMBEDDING_LOCAL_MODEL or "BAAI/bge-small-zh-v1.5"
        self._model = SentenceTransformer(model_path)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [v.tolist() for v in self._model.encode(texts, normalize_embeddings=True)]

    def embed_query(self, text: str) -> List[float]:
        return self._model.encode([text], normalize_embeddings=True)[0].tolist()


class _ChromaDefaultEmbedding:
    """ChromaDB 内置 ONNX 模型（离线可用）"""

    def __init__(self):
        from chromadb.utils import embedding_functions
        self._fn = embedding_functions.ONNXMiniLM_L6_V2()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [list(map(float, v)) for v in self._fn(texts)]

    def embed_query(self, text: str) -> List[float]:
        return list(map(float, self._fn([text])[0]))


def get_embedding_backend():
    """按配置返回 embedding 后端实例"""
    provider = (settings.EMBEDDING_PROVIDER or "api").lower()
    if provider == "local_bge":
        return _LocalBgeEmbedding()
    if provider == "chroma_default":
        return _ChromaDefaultEmbedding()
    return _ApiEmbedding()
