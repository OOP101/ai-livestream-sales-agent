# backend/core/script_recommender.py
"""话术推荐和策略生成"""
from typing import Dict, Any
from core.llm_client import call_llm
import json


class ScriptRecommender:
    """话术推荐器"""

    STRATEGY_TEMPLATES = {
        "purchase": {"priority": "high", "action": "立即引导下单", "tips": "强调限时优惠、库存紧张、倒计时"},
        "question": {"priority": "high", "action": "专业解答后引导购买", "tips": "先回答问题，再关联产品优势"},
        "price": {"priority": "medium", "action": "价值塑造+价格对比", "tips": "强调性价比、赠品、组合优惠"},
        "negative": {"priority": "high", "action": "安抚情绪+解决方案", "tips": "真诚道歉、提供补偿方案、转移注意力"},
        "interaction": {"priority": "low", "action": "互动回应+产品植入", "tips": "友好回应，自然过渡到产品介绍"},
    }

    async def generate_strategy(self, intent: str, confidence: float, sentiment: str) -> Dict[str, Any]:
        """根据意图和情感生成执行策略"""
        base_strategy = self.STRATEGY_TEMPLATES.get(intent, {"priority": "low", "action": "观察等待", "tips": "继续观察弹幕走向"})
        if confidence < 0.6:
            base_strategy["priority"] = "low"
            base_strategy["action"] = "观察等待（置信度较低）"
        if sentiment == "negative" and intent != "negative":
            base_strategy["priority"] = "high"
            base_strategy["tips"] += "，注意观众情绪变化"
        return base_strategy

    async def refine_script(self, script: str, context: Dict[str, Any]) -> str:
        """优化话术，使其更口语化"""
        system_prompt = "你是一个直播话术优化专家。请将给定的话术优化为更自然、更有感染力的直播口语表达。要求：保持核心信息不变，使用直播常用语（家人们、宝宝们、亲们），增加互动感和紧迫感，控制在100字以内"
        user_prompt = f"原始话术：{script}\n\n上下文信息：{json.dumps(context, ensure_ascii=False)}"
        return (await call_llm(system_prompt, user_prompt)).strip()

# 全局单例
script_recommender = ScriptRecommender()
