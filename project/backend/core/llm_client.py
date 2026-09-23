# backend/core/llm_client.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from core.config import settings

def get_llm() -> ChatOpenAI:
    """获取 LLM 实例"""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        max_tokens=settings.MAX_TOKENS,
        temperature=settings.TEMPERATURE,
        streaming=True,
    )

def get_embedding_model():
    """获取 Embedding 模型"""
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY,
        base_url=settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL,
        # 阿里云/DashScope 等兼容端点不接受 tiktoken 切好的 token 数组，须直接传文本
        check_embedding_ctx_length=False,
    )

async def call_llm(system_prompt: str, user_prompt: str) -> str:
    """调用 LLM 生成回复"""
    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = await llm.ainvoke(messages)
    return response.content
