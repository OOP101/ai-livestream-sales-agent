# backend/rag/embedding.py
"""Embedding 后端适配层

支持三种后端，通过 .env 的 EMBEDDING_PROVIDER 切换：
- api          ：OpenAI 兼容接口（默认，需 EMBEDDING_API_KEY/BASE_URL 可用）
- local_bge    ：本地 sentence-transformers 模型（EMBEDDING_LOCAL_MODEL 指向模型目录）
- chroma_default：ChromaDB 内置 ONNX 模型（onnxruntime 离线推理，无需额外依赖）
"""
from typing import List
from core.config import settings

# 各后端初始化失败时的排查提示（维度不同，切 provider 需重建向量库）
_PROVIDER_HINT = {
    "api": "检查 EMBEDDING_API_KEY / EMBEDDING_BASE_URL / EMBEDDING_MODEL 是否可用",
    "local_bge": "检查 EMBEDDING_LOCAL_MODEL 指向的模型目录是否存在，或先下载该模型",
    "chroma_default": "检查 chromadb 与 onnxruntime 是否安装完整（首次运行需联网下载 ONNX 模型）",
}


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
    """按配置返回 embedding 后端实例

    初始化失败时抛出带「怎么修」的明确错误，而不是让 transformers / openai
    的原始堆栈把真正原因埋掉。

    注意：不同后端的向量维度不同（API 通常 1536 维，chroma_default 384 维），
    切换 EMBEDDING_PROVIDER 后必须重建向量库，否则检索结果无意义。
    """
    provider = (settings.EMBEDDING_PROVIDER or "api").lower()
    builders = {
        "api": _ApiEmbedding,
        "local_bge": _LocalBgeEmbedding,
        "chroma_default": _ChromaDefaultEmbedding,
    }
    if provider not in builders:
        raise ValueError(
            f"未知的 EMBEDDING_PROVIDER: {provider}（可选：{', '.join(builders)}）"
        )
    try:
        return builders[provider]()
    except Exception as e:
        hint = _PROVIDER_HINT.get(provider, "")
        raise RuntimeError(
            f"Embedding 后端 '{provider}' 初始化失败：{e}"
            + (f" —— {hint}" if hint else "")
        ) from e
