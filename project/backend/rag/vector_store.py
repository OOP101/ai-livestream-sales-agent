# backend/rag/vector_store.py
"""ChromaDB 向量存储管理"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from core.config import settings
from rag.embedding import get_embedding_backend


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
        """添加文档到向量库"""
        ids, texts, metadatas = [], [], []
        for doc in documents:
            doc_id = f"{doc.get('doc_type', 'doc')}_{len(ids)}"
            ids.append(doc_id)
            texts.append(doc["content"])
            metadatas.append({
                "title": doc.get("title", ""),
                "doc_type": doc.get("doc_type", ""),
                **doc.get("metadata", {})
            })
        embeddings = self.embedding_model.embed_documents(texts)
        self.collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        return ids

    def search(self, query: str, top_k: int = 5, doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """向量相似度检索"""
        query_embedding = self.embedding_model.embed_query(query)
        where_filter = {"doc_type": doc_type} if doc_type else None
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
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
        return self.collection.count()

# 全局单例
vector_store = VectorStore()
