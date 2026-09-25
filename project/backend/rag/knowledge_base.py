# backend/rag/knowledge_base.py
"""知识库初始化和管理"""
import json
from pathlib import Path
from typing import List, Dict, Any
from rag.vector_store import vector_store

KNOWLEDGE_DIR = Path(__file__).parent.parent / "data" / "knowledge"

class KnowledgeBase:
    """知识库管理类"""

    @staticmethod
    def load_json_data(filename: str) -> List[Dict[str, Any]]:
        """加载 JSON 知识文件"""
        filepath = KNOWLEDGE_DIR / filename
        if not filepath.exists():
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def init_knowledge_base():
        """初始化知识库：将数据文件导入向量数据库"""
        print("📚 正在初始化知识库...")
        documents = []
        # 1. 加载商品知识
        products = KnowledgeBase.load_json_data("products.json")
        for product in products:
            documents.append({
                "content": f"商品：{product['name']}\n分类：{product['category']}\n价格：{product['price']}元\n描述：{product['description']}\n卖点：{', '.join(product.get('selling_points', []))}",
                "title": product["name"],
                "doc_type": "product",
                "metadata": {"category": product.get("category", ""), "price": product.get("price", 0)}
            })
        # 2. 加载话术模板
        scripts = KnowledgeBase.load_json_data("scripts.json")
        for script in scripts:
            documents.append({
                "content": f"话术分类：{script['category']}\n话术内容：{script['content']}\n适用场景：{script.get('scenario', '')}",
                "title": script.get("title", ""),
                "doc_type": "script",
                "metadata": {"category": script.get("category", "")}
            })
        # 3. 导入向量库
        #    先清空再写入：源数据被删减时，仅靠内容寻址 ID 无法清理遗留的孤儿文档
        if documents:
            vector_store.clear()
            vector_store.add_documents(documents)
            print(f"✅ 知识库初始化完成，导入 {len(documents)} 条文档")
        else:
            print("⚠️ 未找到知识库数据文件")

    @staticmethod
    def search_product(query: str, top_k: int = 3) -> List[Dict]:
        """检索商品知识"""
        return vector_store.search(query, top_k=top_k, doc_type="product")

    @staticmethod
    def search_script(query: str, top_k: int = 3) -> List[Dict]:
        """检索话术模板"""
        return vector_store.search(query, top_k=top_k, doc_type="script")
