# backend/core/rag_engine.py
"""RAG 检索增强生成引擎"""
import asyncio
from typing import List, Dict, Any, Optional
from rag.vector_store import vector_store
from core.config import settings
from core.llm_client import call_llm
import json


class RAGEngine:
    """RAG 引擎：检索 + 生成"""

    def __init__(self):
        self.store = vector_store

    async def retrieve(self, query: str, doc_type: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索相关知识片段

        vector_store.search 是同步实现（embedding 请求 + Chroma 查询），
        直接在 async 函数里调用会占住事件循环、拖垮并发请求，
        因此下沉到线程池执行。
        """
        return await asyncio.to_thread(self.store.search, query, top_k=top_k, doc_type=doc_type)

    async def generate_with_context(self, query: str, intent_type: str, context_docs: List[Dict]) -> Dict[str, Any]:
        """基于检索结果生成话术推荐"""
        # 按预算拼接检索上下文：文档一多，prompt 长度与调用成本会同步膨胀。
        # 检索结果已按相关度排序，超预算时丢弃尾部片段而不是截断正文。
        budget = settings.RAG_CONTEXT_MAX_CHARS
        parts, used = [], 0
        for doc in context_docs:
            piece = f"【来源：{doc.get('metadata', {}).get('title', '未知')}】\n{doc.get('content', '')}"
            remaining = budget - used
            if remaining <= 0:
                break
            if len(piece) > remaining:
                if not parts:
                    # 预算比单条文档还小时，至少保留截断后的第一条：
                    # 否则上下文会整个变空，话术生成彻底失去依据
                    parts.append(piece[:remaining])
                break
            parts.append(piece)
            used += len(piece)
        context_text = "\n\n".join(parts)
        system_prompt = f"""你是一个专业的直播带货话术顾问。
请根据观众的弹幕内容和检索到的相关知识，生成合适的话术推荐。
要求：话术要自然流畅，适合直播口语表达，适当使用"家人们""宝宝们"等直播常用称呼，话术长度控制在50-150字。
返回 JSON 格式：{{"script": "话术内容", "strategy": "执行策略", "urgency": "high/medium/low"}}
当前意图类型：{intent_type}"""
        user_prompt = f"观众弹幕：{query}\n\n检索到的相关知识：\n{context_text}\n\n请生成推荐话术和执行策略。"
        response = await call_llm(system_prompt, user_prompt)
        result: Dict[str, Any] = {}
        try:
            if "{" in response:
                parsed = json.loads(response[response.index("{"):response.rindex("}") + 1])
                # 模型可能返回数组或纯值，只有 dict 才能安全取字段
                if isinstance(parsed, dict):
                    result = parsed
        except (json.JSONDecodeError, ValueError):
            result = {}
        return {
            "recommended_script": result.get("script") or response,
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
