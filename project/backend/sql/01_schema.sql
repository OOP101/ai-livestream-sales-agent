-- ============================================
-- 直播带货AI Agent - 数据库初始化脚本
-- 数据库: SQLite
-- ============================================

-- 1. 商品表
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL COMMENT '商品名称',
    category VARCHAR(100) COMMENT '商品分类',
    price DECIMAL(10,2) NOT NULL COMMENT '商品价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    description TEXT COMMENT '商品描述',
    selling_points TEXT COMMENT '卖点（JSON数组）',
    specifications TEXT COMMENT '规格参数（JSON）',
    stock INTEGER DEFAULT 0 COMMENT '库存数量',
    status TINYINT DEFAULT 1 COMMENT '状态: 1上架 0下架',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. 弹幕记录表
CREATE TABLE IF NOT EXISTS danmaku_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) NOT NULL COMMENT '直播会话ID',
    user_id VARCHAR(64) COMMENT '用户ID',
    username VARCHAR(100) COMMENT '用户名',
    content TEXT NOT NULL COMMENT '弹幕内容',
    danmaku_type VARCHAR(20) DEFAULT 'comment' COMMENT '弹幕类型: comment/buy/gift/follow',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    INDEX idx_created (created_at)
);

-- 3. 话术库表
CREATE TABLE IF NOT EXISTS script_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category VARCHAR(50) NOT NULL COMMENT '话术分类: promotion/question/price/negative/interaction',
    title VARCHAR(200) NOT NULL COMMENT '话术标题',
    content TEXT NOT NULL COMMENT '话术内容模板',
    trigger_keywords TEXT COMMENT '触发关键词（JSON数组）',
    applicable_scenarios TEXT COMMENT '适用场景描述',
    effectiveness_score DECIMAL(3,2) DEFAULT 0.5 COMMENT '效果评分 0-1',
    usage_count INTEGER DEFAULT 0 COMMENT '使用次数',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. 分析结果表
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    danmaku_id INTEGER NOT NULL COMMENT '关联弹幕ID',
    session_id VARCHAR(64) NOT NULL COMMENT '直播会话ID',
    intent_type VARCHAR(30) NOT NULL COMMENT '意图类型',
    intent_confidence DECIMAL(4,3) COMMENT '意图置信度',
    sentiment VARCHAR(20) COMMENT '情感倾向: positive/neutral/negative',
    sentiment_score DECIMAL(4,3) COMMENT '情感得分 -1到1',
    keywords TEXT COMMENT '提取关键词（JSON数组）',
    recommended_script TEXT COMMENT '推荐话术',
    script_category VARCHAR(50) COMMENT '话术分类',
    rag_sources TEXT COMMENT 'RAG检索来源（JSON）',
    strategy TEXT COMMENT '执行策略建议',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (danmaku_id) REFERENCES danmaku_records(id),
    INDEX idx_session_intent (session_id, intent_type)
);

-- 5. 用户会话表
CREATE TABLE IF NOT EXISTS live_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) UNIQUE NOT NULL COMMENT '会话ID',
    host_name VARCHAR(100) COMMENT '主播名称',
    title VARCHAR(200) COMMENT '直播标题',
    platform VARCHAR(50) DEFAULT 'custom' COMMENT '直播平台',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/ended/paused',
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    total_danmaku INTEGER DEFAULT 0 COMMENT '弹幕总数',
    total_analysis INTEGER DEFAULT 0 COMMENT '分析总数',
    stats JSON COMMENT '统计数据（JSON）'
);

-- 6. 知识库文档表
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type VARCHAR(50) NOT NULL COMMENT '文档类型: product/script/faq',
    title VARCHAR(200) NOT NULL COMMENT '文档标题',
    content TEXT NOT NULL COMMENT '文档内容',
    metadata JSON COMMENT '元数据（JSON）',
    vector_id VARCHAR(100) COMMENT '向量库中的ID',
    is_active TINYINT DEFAULT 1 COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
