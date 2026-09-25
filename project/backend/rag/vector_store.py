# backend/rag/vector_store.py
"""ChromaDB 向量存储管理"""
import hashlib
import logging
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from core.config import settings
from rag.embedding import get_embedding_backend

logger = logging.getLogger(__name__)


def make_doc_id(doc_type: str, content: str) -> str:
    """内容寻址的稳定文档 ID：同内容恒等，异内容必异。

    旧实现用 f"{doc_type}_{len(ids)}" 生成 ID，每次调用都从 0 重新计数。
    由于 ChromaDB 对已存在的 ID 走 upsert 语义，第二批写入会静默覆盖第一批，
    且源数据增删后 ID 会整体错位。改成内容哈希后，重复灌库是幂等的。
    """
    digest = hashlib.md5(content.encode("utf-8")).hexdigest()[:12]
    return f"{doc_type}_{digest}"


class VectorStore:
    """向量数据库管理类"""

    def __init__(self):
        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.embedding_model = get_embedding_backend()
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )

    def add_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """添加文档到向量库（幂等：内容寻址 ID + upsert）"""
        if not documents:
            return []
        ids, texts, metadatas = [], [], []
        for doc in documents:
            content = doc["content"]
            doc_type = doc.get("doc_type", "doc")
            ids.append(make_doc_id(doc_type, content))
            texts.append(content)
            metadatas.append({
                "title": doc.get("title", ""),
                "doc_type": doc_type,
                **doc.get("metadata", {})
            })
        embeddings = self.embedding_model.embed_documents(texts)
        # 用 upsert 而不是 add：重复灌同一批数据不会报错也不会产生重复记录
        self.collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        return ids

    def clear(self) -> None:
        """清空整个集合。

        重建索引前调用。仅靠内容寻址 ID 无法清理"源数据被删除后遗留的孤儿文档"，
        所以全量重建走 clear + add_documents。
        """
        self.client.delete_collection(name=settings.CHROMA_COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    def search(self, query: str, top_k: int = 5, doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """向量相似度检索

        检索属于「读路径」：库损坏 / 磁盘异常 / embedding 服务抖动时
        返回空列表让上层降级，比把异常抛到请求层打 500 更合适。
        """
        try:
            query_embedding = self.embedding_model.embed_query(query)
            where_filter = {"doc_type": doc_type} if doc_type else None
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
        except Exception:
            logger.exception("向量检索失败（doc_type=%s, top_k=%s）", doc_type, top_k)
            return []
        formatted_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                })
        return formatted_results

    def get_count(self) -> int:
        """获取集合中文档数量"""
        try:
            return self.collection.count()
        except Exception:
            logger.exception("读取向量库文档数失败")
            return 0

# 全局单例
vector_store = VectorStore()
