# backend/core/rag_engine.py
"""RAG 检索增强生成引擎"""
from typing import List, Dict, Any, Optional
from rag.vector_store import vector_store
from core.llm_client import call_llm
import json


class RAGEngine:
    """RAG 引擎：检索 + 生成"""

    def __init__(self):
        self.store = vector_store

    async def retrieve(self, query: str, doc_type: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索相关知识片段"""
        return self.store.search(query, top_k=top_k, doc_type=doc_type)

    async def generate_with_context(self, query: str, intent_type: str, context_docs: List[Dict]) -> Dict[str, Any]:
        """基于检索结果生成话术推荐"""
        context_text = "\n\n".join([
            f"【来源：{doc.get('metadata', {}).get('title', '未知')}】\n{doc['content']}"
            for doc in context_docs
        ])
        system_prompt = f"""你是一个专业的直播带货话术顾问。
请根据观众的弹幕内容和检索到的相关知识，生成合适的话术推荐。
要求：话术要自然流畅，适合直播口语表达，适当使用"家人们""宝宝们"等直播常用称呼，话术长度控制在50-150字。
返回 JSON 格式：{{"script": "话术内容", "strategy": "执行策略", "urgency": "high/medium/low"}}
当前意图类型：{intent_type}"""
        user_prompt = f"观众弹幕：{query}\n\n检索到的相关知识：\n{context_text}\n\n请生成推荐话术和执行策略。"
        response = await call_llm(system_prompt, user_prompt)
        try:
            if "{" in response:
                json_str = response[response.index("{"):response.rindex("}") + 1]
                result = json.loads(json_str)
            else:
                result = {"script": response, "strategy": "正常推荐", "urgency": "medium"}
        except (json.JSONDecodeError, ValueError):
            result = {"script": response, "strategy": "正常推荐", "urgency": "medium"}
        return {
            "recommended_script": result.get("script", response),
            "strategy": result.get("strategy", "正常推荐"),
            "urgency": result.get("urgency", "medium"),
            "rag_sources": [{"title": doc.get("metadata", {}).get("title", ""), "score": doc.get("score", 0), "type": doc.get("metadata", {}).get("doc_type", "")} for doc in context_docs]
        }

    async def analyze_and_recommend(self, content: str, intent_type: str) -> Dict[str, Any]:
        """完整的 RAG 分析流程：检索 + 生成"""
        doc_type = None
        if intent_type in ["question"]:
            doc_type = "product"
        elif intent_type in ["purchase", "price"]:
            doc_type = "script"
        retrieved_docs = await self.retrieve(content, doc_type=doc_type, top_k=5)
        if len(retrieved_docs) < 2:
            retrieved_docs = await self.retrieve(content, top_k=5)
        return await self.generate_with_context(content, intent_type, retrieved_docs)

# 全局单例
rag_engine = RAGEngine()
