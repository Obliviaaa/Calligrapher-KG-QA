# -*- coding: utf-8 -*-
"""
中国书法家知识图谱 Web应用
包含自然语言问答、SPARQL查询、知识抽取展示和交互式网络可视化
采用中国书法传统美学风格
"""

from rdflib import Graph
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import json
import os
import csv
from SPARQLWrapper import SPARQLWrapper, JSON
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from utils import setup_llm

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TTL_PATH = os.path.join(BASE_DIR, '..', 'backend_qa', 'calligraphy_kg.ttl')
ANALYSIS_DIR = os.path.join(BASE_DIR, '..', 'backend_analysis')
SPARQL_ENDPOINT = "http://localhost:8000/sparql"

# 创建图数据库
g = Graph()

# 加载知识图谱
if os.path.exists(TTL_PATH):
    g.parse(TTL_PATH, format='turtle')
    print(f'已加载知识图谱: {TTL_PATH}')
else:
    raise FileNotFoundError(f"未找到知识图谱文件: {TTL_PATH}")

print(f'已加载 {len(g)} 条三元组')

# 初始化LLM
_agent_workflow = None
try:
    _llm = setup_llm()
    LLM_AVAILABLE = True
    print("LLM初始化成功")
    # 初始化LangGraph工作流
    try:
        import sys
        backend_qa_dir = os.path.abspath(os.path.join(BASE_DIR, '..', 'backend_qa'))
        if backend_qa_dir not in sys.path:
            sys.path.insert(0, backend_qa_dir)
        from rdf_agent import create_agent_workflow
        _agent_workflow = create_agent_workflow(_llm)
        print("LangGraph工作流初始化成功")
    except Exception as e:
        print(f"LangGraph工作流初始化失败: {e}，将使用规则匹配模式")
        import traceback
        traceback.print_exc()
except Exception as e:
    LLM_AVAILABLE = False
    _llm = None
    print(f"LLM初始化失败: {e}，将使用规则匹配模式")

# 统计信息
triple_count = len(g)
CALLI_NS = "http://example.org/ontology/calligraphy#"

# 从知识图谱中提取所有书法家姓名
ALL_CALLIGRAPHER_NAMES = []
for s, p, o in g:
    if str(p) == "http://www.w3.org/2000/01/rdf-schema#label":
        obj_str = str(o)
        if obj_str and len(obj_str) >= 2:
            ALL_CALLIGRAPHER_NAMES.append(obj_str)
ALL_CALLIGRAPHER_NAMES = sorted(set(ALL_CALLIGRAPHER_NAMES), key=len, reverse=True)

# 精确统计书法家数量
_calli_count_q = """
PREFIX calli: <http://example.org/ontology/calligraphy#>
SELECT (COUNT(?c) AS ?count)
WHERE { ?c a calli:Calligrapher }
"""
for _row in g.query(_calli_count_q):
    calligrapher_count = int(_row[0])
    break

# 统计关系类型数量
relation_types = set()
for s, p, o in g:
    p_str = str(p)
    if CALLI_NS in p_str:
        relation_types.add(p_str.split("#")[-1])
relation_type_count = len(relation_types)

# 统计流派数量
school_count = 0
_csv_path = os.path.join(ANALYSIS_DIR, 'school_analysis.csv')
if os.path.exists(_csv_path):
    with open(_csv_path, 'r', encoding='utf-8-sig') as _f:
        _reader = csv.DictReader(_f)
        school_count = sum(1 for _ in _reader)
else:
    _q = """
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    SELECT (COUNT(DISTINCT ?s) AS ?count)
    WHERE { ?c calli:goodAtScript ?s }
    """
    for _row in g.query(_q):
        school_count = int(_row[0])

# 统计实体链接数量
sameas_count = 0
for s, p, o in g:
    if str(p) == "http://www.w3.org/2002/07/owl#sameAs":
        sameas_count += 1

app = FastAPI(
    title="中国书法家知识图谱问答系统",
    description="基于中国历代书法家图表 中国书法的历史沿革及书风演变构建的知识问答系统"
)

# 挂载backend_analysis为静态文件目录
if os.path.exists(ANALYSIS_DIR):
    app.mount("/static/graph", StaticFiles(directory=ANALYSIS_DIR), name="graph_analysis")
    GRAPH_IMG_DIR = ANALYSIS_DIR
    print(f"已挂载图分析静态文件: {ANALYSIS_DIR}")
else:
    GRAPH_IMG_DIR = None


# ============================================================
# 公共CSS和HTML模板
# ============================================================

def get_common_css():
    return """
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700;900&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

    :root {
        --ink-black: #1a1a2e;
        --ink-dark: #16213e;
        --ink-medium: #2c3e50;
        --cinnabar: #c0392b;
        --cinnabar-light: #e74c3c;
        --vermillion: #d35400;
        --paper: #f5f0e8;
        --paper-light: #faf7f2;
        --paper-dark: #e8e0d0;
        --jade: #27ae60;
        --jade-dark: #1e8449;
        --indigo: #2c3e50;
        --gold: #d4a017;
        --gold-light: #f0c040;
        --bronze: #8B7355;
        --shadow: rgba(26,26,46,0.12);
        --shadow-lg: rgba(26,26,46,0.2);
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
        font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
        background: var(--paper);
        color: var(--ink-black);
        min-height: 100vh;
        overflow-x: hidden;
    }

    /* 水墨纹理背景 */
    body::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background:
            radial-gradient(ellipse at 20% 50%, rgba(192,57,43,0.03) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 20%, rgba(44,62,80,0.04) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 80%, rgba(212,160,23,0.03) 0%, transparent 50%);
        pointer-events: none;
        z-index: 0;
    }

    .app-container {
        display: flex;
        min-height: 100vh;
        position: relative;
        z-index: 1;
    }

    /* 侧边导航 */
    .sidebar {
        width: 240px;
        background: var(--ink-black);
        color: var(--paper);
        padding: 0;
        position: fixed;
        top: 0; left: 0; bottom: 0;
        z-index: 100;
        display: flex;
        flex-direction: column;
        transition: transform 0.3s ease;
        overflow-y: auto;
    }

    .sidebar-header {
        padding: 28px 20px 20px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }

    .sidebar-header h1 {
        font-family: 'Noto Serif SC', serif;
        font-size: 18px;
        font-weight: 700;
        color: var(--paper);
        letter-spacing: 2px;
        line-height: 1.6;
    }

    .sidebar-header .subtitle {
        font-size: 11px;
        color: rgba(245,240,232,0.5);
        margin-top: 6px;
        letter-spacing: 1px;
    }

    .sidebar-nav {
        padding: 12px 0;
        flex: 1;
    }

    .nav-item {
        display: flex;
        align-items: center;
        padding: 12px 20px;
        color: rgba(245,240,232,0.65);
        text-decoration: none;
        font-size: 14px;
        transition: all 0.25s ease;
        border-left: 3px solid transparent;
        gap: 12px;
    }

    .nav-item:hover {
        color: var(--paper);
        background: rgba(255,255,255,0.05);
        border-left-color: rgba(192,57,43,0.5);
    }

    .nav-item.active {
        color: var(--paper);
        background: rgba(192,57,43,0.15);
        border-left-color: var(--cinnabar);
        font-weight: 500;
    }

    .nav-item .nav-icon {
        width: 20px;
        text-align: center;
        font-size: 16px;
    }

    .sidebar-footer {
        padding: 16px 20px;
        border-top: 1px solid rgba(255,255,255,0.08);
        font-size: 11px;
        color: rgba(245,240,232,0.3);
        text-align: center;
    }

    /* 主内容区 */
    .main-content {
        margin-left: 240px;
        flex: 1;
        padding: 32px 40px;
        min-height: 100vh;
    }

    /* 页面标题 */
    .page-header {
        margin-bottom: 32px;
        padding-bottom: 20px;
        border-bottom: 2px solid var(--paper-dark);
        position: relative;
    }

    .page-header::after {
        content: '';
        position: absolute;
        bottom: -2px;
        left: 0;
        width: 80px;
        height: 2px;
        background: var(--cinnabar);
    }

    .page-header h2 {
        font-family: 'Noto Serif SC', serif;
        font-size: 26px;
        font-weight: 700;
        color: var(--ink-black);
        letter-spacing: 1px;
    }

    .page-header p {
        font-size: 14px;
        color: var(--bronze);
        margin-top: 6px;
    }

    /* 卡片 */
    .card {
        background: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 2px 12px var(--shadow);
        margin-bottom: 24px;
        border: 1px solid rgba(0,0,0,0.04);
        transition: box-shadow 0.3s ease;
    }

    .card:hover {
        box-shadow: 0 4px 20px var(--shadow-lg);
    }

    .card-title {
        font-family: 'Noto Serif SC', serif;
        font-size: 17px;
        font-weight: 600;
        color: var(--ink-black);
        margin-bottom: 16px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--paper-dark);
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .card-title .icon {
        color: var(--cinnabar);
        font-size: 18px;
    }

    /* 统计卡片 */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin-bottom: 28px;
    }

    .stat-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 8px var(--shadow);
        border: 1px solid rgba(0,0,0,0.04);
        position: relative;
        overflow: hidden;
    }

    .stat-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
    }

    .stat-card:nth-child(1)::before { background: var(--cinnabar); }
    .stat-card:nth-child(2)::before { background: var(--ink-medium); }
    .stat-card:nth-child(3)::before { background: var(--jade); }
    .stat-card:nth-child(4)::before { background: var(--gold); }
    .stat-card:nth-child(5)::before { background: var(--vermillion); }

    .stat-card .number {
        font-family: 'Noto Serif SC', serif;
        font-size: 32px;
        font-weight: 900;
        color: var(--ink-black);
        line-height: 1;
    }

    .stat-card .label {
        font-size: 13px;
        color: var(--bronze);
        margin-top: 8px;
    }

    /* 聊天框 */
    .chat-container {
        background: var(--paper-light);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid var(--paper-dark);
    }

    .chat-box {
        height: 380px;
        overflow-y: auto;
        padding: 16px;
        background: white;
        border-radius: 8px;
        margin-bottom: 16px;
        border: 1px solid var(--paper-dark);
        scroll-behavior: smooth;
    }

    .chat-message {
        margin: 10px 0;
        padding: 10px 16px;
        border-radius: 12px;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.7;
        animation: fadeIn 0.3s ease;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .chat-message.user {
        background: var(--ink-black);
        color: var(--paper);
        margin-left: auto;
        border-bottom-right-radius: 4px;
    }

    .chat-message.bot {
        background: white;
        color: var(--ink-black);
        border: 1px solid var(--paper-dark);
        border-bottom-left-radius: 4px;
    }

    .chat-message.error {
        background: #fde8e8;
        color: var(--cinnabar);
        border: 1px solid #f5c6c6;
    }

    .chat-message.system {
        background: rgba(192,57,43,0.06);
        color: var(--ink-medium);
        border: 1px solid rgba(192,57,43,0.12);
        font-size: 13px;
    }

    .input-group {
        display: flex;
        gap: 10px;
    }

    .input-group input {
        flex: 1;
        padding: 12px 16px;
        border: 2px solid var(--paper-dark);
        border-radius: 8px;
        font-size: 14px;
        font-family: 'Noto Sans SC', sans-serif;
        background: white;
        transition: border-color 0.25s ease;
    }

    .input-group input:focus {
        outline: none;
        border-color: var(--cinnabar);
    }

    .btn {
        padding: 12px 24px;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 14px;
        font-family: 'Noto Sans SC', sans-serif;
        transition: all 0.25s ease;
        font-weight: 500;
    }

    .btn-primary {
        background: var(--cinnabar);
        color: white;
    }

    .btn-primary:hover {
        background: var(--cinnabar-light);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(192,57,43,0.3);
    }

    .btn-secondary {
        background: var(--paper-dark);
        color: var(--ink-medium);
    }

    .btn-secondary:hover {
        background: var(--bronze);
        color: white;
    }

    /* 示例问题标签 */
    .example-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
    }

    .example-tag {
        padding: 6px 14px;
        background: white;
        border: 1px solid var(--paper-dark);
        border-radius: 20px;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
        color: var(--ink-medium);
    }

    .example-tag:hover {
        background: var(--cinnabar);
        color: white;
        border-color: var(--cinnabar);
    }

    /* 表格 */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }

    .data-table th {
        background: var(--ink-black);
        color: var(--paper);
        padding: 10px 14px;
        text-align: left;
        font-weight: 500;
        font-size: 12px;
        letter-spacing: 0.5px;
    }

    .data-table td {
        padding: 10px 14px;
        border-bottom: 1px solid var(--paper-dark);
        color: var(--ink-medium);
    }

    .data-table tr:hover td {
        background: rgba(192,57,43,0.03);
    }

    /* 标签 */
    .tag {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 500;
    }

    .tag-red { background: rgba(192,57,43,0.1); color: var(--cinnabar); }
    .tag-blue { background: rgba(44,62,80,0.1); color: var(--ink-medium); }
    .tag-green { background: rgba(39,174,96,0.1); color: var(--jade-dark); }
    .tag-gold { background: rgba(212,160,23,0.1); color: #b8860b; }
    .tag-purple { background: rgba(142,68,173,0.1); color: #8e44ad; }

    /* SPARQL编辑器 */
    .sparql-editor {
        width: 100%;
        min-height: 220px;
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        padding: 16px;
        border: 2px solid var(--paper-dark);
        border-radius: 8px;
        font-size: 13px;
        resize: vertical;
        background: #1e1e2e;
        color: #cdd6f4;
        line-height: 1.6;
    }

    .sparql-editor:focus {
        outline: none;
        border-color: var(--cinnabar);
    }

    .sparql-result {
        margin-top: 16px;
        background: white;
        border: 1px solid var(--paper-dark);
        border-radius: 8px;
        padding: 16px;
        max-height: 400px;
        overflow: auto;
        font-size: 13px;
    }

    /* 流派卡片 */
    .school-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 16px;
    }

    .school-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid var(--paper-dark);
        transition: all 0.3s ease;
        cursor: default;
    }

    .school-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px var(--shadow-lg);
        border-color: var(--cinnabar);
    }

    .school-card h4 {
        font-family: 'Noto Serif SC', serif;
        font-size: 16px;
        color: var(--cinnabar);
        margin-bottom: 10px;
    }

    .school-card .info-line {
        font-size: 13px;
        color: var(--ink-medium);
        margin: 4px 0;
        line-height: 1.6;
    }

    .school-card .info-label {
        color: var(--bronze);
        font-weight: 500;
    }

    /* 中心性排名 */
    .rank-list {
        max-height: 500px;
        overflow-y: auto;
    }

    .rank-item {
        display: flex;
        align-items: center;
        padding: 10px 12px;
        border-bottom: 1px solid var(--paper-dark);
        transition: background 0.2s ease;
    }

    .rank-item:hover {
        background: rgba(192,57,43,0.03);
    }

    .rank-badge {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 700;
        margin-right: 12px;
        flex-shrink: 0;
    }

    .rank-badge.gold { background: linear-gradient(135deg, #f0c040, #d4a017); color: white; }
    .rank-badge.silver { background: linear-gradient(135deg, #bdc3c7, #95a5a6); color: white; }
    .rank-badge.bronze { background: linear-gradient(135deg, #cd7f32, #8B7355); color: white; }
    .rank-badge.normal { background: var(--paper-dark); color: var(--ink-medium); }

    .rank-name {
        flex: 1;
        font-weight: 500;
        font-size: 14px;
    }

    .rank-score {
        font-size: 12px;
        color: var(--bronze);
    }

    /* 图表容器 */
    .chart-container {
        height: 400px;
        width: 100%;
    }

    .chart-container-sm {
        height: 300px;
        width: 100%;
    }

    /* 两栏布局 */
    .two-col {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 24px;
    }

    .three-col {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 24px;
    }

    .main-side {
        display: grid;
        grid-template-columns: 1fr 360px;
        gap: 24px;
    }

    /* 关系抽取展示 */
    .relation-example {
        background: white;
        border-radius: 10px;
        padding: 20px;
        border-left: 4px solid var(--cinnabar);
        margin-bottom: 16px;
    }

    .relation-example .source-text {
        font-family: 'Noto Serif SC', serif;
        font-size: 15px;
        color: var(--ink-black);
        margin-bottom: 12px;
        line-height: 1.8;
        padding: 10px;
        background: var(--paper-light);
        border-radius: 6px;
    }

    .relation-example .extracted-relations {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }

    .relation-triple {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        background: var(--paper-light);
        border-radius: 6px;
        font-size: 13px;
        border: 1px solid var(--paper-dark);
    }

    .relation-triple .subject { color: var(--cinnabar); font-weight: 600; }
    .relation-triple .predicate { color: var(--jade-dark); font-weight: 500; }
    .relation-triple .object { color: var(--ink-medium); font-weight: 600; }
    .relation-triple .arrow { color: var(--bronze); }

    /* 实体链接表 */
    .link-status {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 500;
    }

    .link-high { background: rgba(39,174,96,0.1); color: var(--jade-dark); }
    .link-medium { background: rgba(212,160,23,0.1); color: #b8860b; }
    .link-low { background: rgba(192,57,43,0.1); color: var(--cinnabar); }

    /* 本体图 */
    .ontology-class {
        background: white;
        border: 2px solid var(--ink-black);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        margin: 8px;
    }

    .ontology-class .class-name {
        font-family: 'Noto Serif SC', serif;
        font-size: 16px;
        font-weight: 700;
        color: var(--cinnabar);
    }

    .ontology-class .class-label {
        font-size: 12px;
        color: var(--bronze);
        margin-top: 4px;
    }

    /* 工作流展示 */
    .workflow-steps {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0;
        margin: 20px 0;
        flex-wrap: wrap;
    }

    .workflow-step {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 12px 16px;
        background: white;
        border: 2px solid var(--paper-dark);
        border-radius: 10px;
        min-width: 120px;
        transition: all 0.3s ease;
    }

    .workflow-step:hover {
        border-color: var(--cinnabar);
        box-shadow: 0 4px 12px var(--shadow);
    }

    .workflow-step .step-icon {
        font-size: 24px;
        margin-bottom: 6px;
    }

    .workflow-step .step-name {
        font-size: 12px;
        font-weight: 600;
        color: var(--ink-black);
        text-align: center;
    }

    .workflow-step .step-desc {
        font-size: 10px;
        color: var(--bronze);
        text-align: center;
        margin-top: 4px;
    }

    .workflow-arrow {
        font-size: 20px;
        color: var(--cinnabar);
        padding: 0 8px;
    }

    /* 评分对照 */
    .score-table {
        width: 100%;
        border-collapse: collapse;
    }

    .score-table th {
        background: var(--ink-black);
        color: var(--paper);
        padding: 12px 16px;
        text-align: left;
        font-size: 13px;
    }

    .score-table td {
        padding: 12px 16px;
        border-bottom: 1px solid var(--paper-dark);
        font-size: 13px;
    }

    .score-table .score-item {
        font-weight: 500;
    }

    .score-table .score-points {
        color: var(--cinnabar);
        font-weight: 700;
    }

    .score-table .score-status {
        color: var(--jade-dark);
        font-weight: 600;
    }

    /* 滚动条 */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--paper-light); }
    ::-webkit-scrollbar-thumb { background: var(--paper-dark); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--bronze); }

    /* 移动端菜单按钮 */
    .mobile-menu-btn {
        display: none;
        position: fixed;
        top: 12px; left: 12px;
        z-index: 200;
        width: 40px; height: 40px;
        background: var(--ink-black);
        color: var(--paper);
        border: none;
        border-radius: 8px;
        font-size: 20px;
        cursor: pointer;
        box-shadow: 0 2px 8px var(--shadow-lg);
    }

    /* 响应式 */
    @media (max-width: 1024px) {
        .main-side { grid-template-columns: 1fr; }
        .two-col { grid-template-columns: 1fr; }
        .three-col { grid-template-columns: 1fr; }
    }

    @media (max-width: 768px) {
        .sidebar { transform: translateX(-100%); }
        .sidebar.open { transform: translateX(0); }
        .mobile-menu-btn { display: flex; align-items: center; justify-content: center; }
        .main-content { margin-left: 0; padding: 60px 16px 24px; }
        .stats-grid { grid-template-columns: repeat(2, 1fr); }
    }

    /* 加载动画 */
    .loading-dots::after {
        content: '';
        animation: dots 1.5s steps(4, end) infinite;
    }

    @keyframes dots {
        0%, 20% { content: ''; }
        40% { content: '.'; }
        60% { content: '..'; }
        80%, 100% { content: '...'; }
    }

    /* 选项卡 */
    .tabs {
        display: flex;
        gap: 0;
        border-bottom: 2px solid var(--paper-dark);
        margin-bottom: 20px;
    }

    .tab-btn {
        padding: 10px 20px;
        background: none;
        border: none;
        border-bottom: 2px solid transparent;
        margin-bottom: -2px;
        cursor: pointer;
        font-size: 14px;
        font-family: 'Noto Sans SC', sans-serif;
        color: var(--bronze);
        transition: all 0.2s ease;
    }

    .tab-btn:hover { color: var(--ink-black); }

    .tab-btn.active {
        color: var(--cinnabar);
        border-bottom-color: var(--cinnabar);
        font-weight: 600;
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; }

    /* 路径分析 */
    .path-display {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        padding: 12px;
        background: var(--paper-light);
        border-radius: 8px;
        margin: 8px 0;
    }

    .path-node {
        padding: 4px 12px;
        background: white;
        border: 1px solid var(--paper-dark);
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
    }

    .path-arrow {
        color: var(--cinnabar);
        font-size: 16px;
    }

    .network-wrapper {
        position: relative;
        height: 600px;
        background: white;
        border-radius: 12px;
        border: 1px solid var(--paper-dark);
    }

    .network-container {
        height: 100%;
        width: 100%;
        position: absolute;
        top: 0;
        left: 0;
    }

    .network-toolbar {
        position: absolute;
        top: 12px;
        left: 12px;
        right: 12px;
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        z-index: 10;
        background: rgba(255,255,255,0.95);
        padding: 12px;
        border-radius: 8px;
        box-shadow: 0 2px 8px var(--shadow);
    }

    .network-filter-group {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .network-filter-label {
        font-size: 12px;
        color: var(--bronze);
        font-weight: 500;
    }

    .network-filter-btn {
        padding: 6px 12px;
        background: var(--paper-light);
        border: 1px solid var(--paper-dark);
        border-radius: 6px;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
        color: var(--ink-medium);
    }

    .network-filter-btn:hover {
        background: var(--paper-dark);
    }

    .network-filter-btn.active {
        background: var(--cinnabar);
        color: white;
        border-color: var(--cinnabar);
    }

    .network-search {
        padding: 8px 12px;
        border: 1px solid var(--paper-dark);
        border-radius: 6px;
        font-size: 13px;
        width: 180px;
        outline: none;
        transition: border-color 0.2s ease;
    }

    .network-search:focus {
        border-color: var(--cinnabar);
    }

    .node-detail-panel {
        position: absolute;
        bottom: 12px;
        right: 12px;
        width: 280px;
        max-height: 300px;
        background: white;
        border-radius: 10px;
        border: 1px solid var(--paper-dark);
        box-shadow: 0 4px 16px var(--shadow-lg);
        z-index: 10;
        overflow-y: auto;
        display: none;
    }

    .node-detail-panel.show {
        display: block;
    }

    .node-detail-header {
        padding: 16px;
        background: var(--ink-black);
        color: var(--paper);
        border-radius: 10px 10px 0 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .node-detail-header h4 {
        font-family: 'Noto Serif SC', serif;
        font-size: 16px;
        margin: 0;
    }

    .node-detail-close {
        background: none;
        border: none;
        color: var(--paper);
        font-size: 18px;
        cursor: pointer;
        padding: 4px;
    }

    .node-detail-body {
        padding: 16px;
    }

    .node-detail-item {
        margin: 8px 0;
        font-size: 13px;
        line-height: 1.6;
    }

    .node-detail-item .label {
        color: var(--bronze);
        font-weight: 500;
        margin-right: 8px;
    }

    .node-detail-item .value {
        color: var(--ink-medium);
    }

    .network-stats-bar {
        position: absolute;
        bottom: 12px;
        left: 12px;
        background: rgba(255,255,255,0.95);
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 11px;
        color: var(--bronze);
        z-index: 10;
        box-shadow: 0 2px 6px var(--shadow);
    }

    .network-legend {
        position: absolute;
        top: 80px;
        right: 12px;
        background: rgba(255,255,255,0.95);
        padding: 12px;
        border-radius: 8px;
        font-size: 11px;
        z-index: 10;
        box-shadow: 0 2px 6px var(--shadow);
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 4px 0;
    }

    .legend-line {
        width: 20px;
        height: 3px;
        border-radius: 2px;
    }

    .legend-line.teacher {{ background: #3498db; }}
    .legend-line.influenced {{ background: #27ae60; }}
    .legend-line.relative {{ background: #c0392b; }}
    .legend-line.created {{ background: #9b59b6; }}
    """


def get_nav_html(active_page):
    nav_items = [
        ("/", "首页", "fa"),
        ("/sparql", "SPARQL查询", "fa"),
        ("/network", "关系网络", "fa"),
        ("/schools", "流派分析", "fa"),
    ]
    icons = ["🏠", "📋", "🕸️", "🏛️"]
    nav_html = ""
    for i, (href, label, _) in enumerate(nav_items):
        active_class = "active" if href == active_page else ""
        nav_html += f'<a href="{href}" class="nav-item {active_class}"><span class="nav-icon">{icons[i]}</span>{label}</a>\n'
    return nav_html


def get_page_template(active_page, title, content):
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <title>{title} - 中国书法家知识图谱</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
        <style>{get_common_css()}</style>
    </head>
    <body>
        <button class="mobile-menu-btn" onclick="toggleSidebar()">☰</button>
        <div class="app-container">
            <nav class="sidebar" id="sidebar">
                <div class="sidebar-header">
                    <h1>书法家<br>知识图谱</h1>
                    <div class="subtitle">CALLIGRAPHY KG</div>
                </div>
                <div class="sidebar-nav">
                    {get_nav_html(active_page)}
                </div>
                <div class="sidebar-footer">
                    基于中国历代书法家图表 中国书法的历史沿革及书风演变构建<br>© 2026 知识图谱课程大作业
                </div>
            </nav>
            <main class="main-content">
                {content}
            </main>
        </div>
        <script>
            function toggleSidebar() {{
                document.getElementById('sidebar').classList.toggle('open');
            }}
        </script>
    </body>
    </html>
    """


# ============================================================
# 页面路由
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home():
    content = f"""
    <div class="page-header">
        <h2>知识问答系统</h2>
        <p>基于SPARQL端点的智能问答，支持自然语言查询与SPARQL生成</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="number">{triple_count}</div>
            <div class="label">三元组数量</div>
        </div>
        <div class="stat-card">
            <div class="number">{calligrapher_count}</div>
            <div class="label">书法家数量</div>
        </div>
        <div class="stat-card">
            <div class="number">{school_count}</div>
            <div class="label">流派数量</div>
        </div>
        <div class="stat-card">
            <div class="number">{relation_type_count}</div>
            <div class="label">关系类型</div>
        </div>
        <div class="stat-card">
            <div class="number">{sameas_count}</div>
            <div class="label">实体链接</div>
        </div>
    </div>

    <div class="main-side">
        <div>
            <div class="card">
                <div class="card-title"><span class="icon">💬</span> 知识问答</div>
                <div class="chat-container">
                    <div class="chat-box" id="chatBox">
                        <div class="chat-message system">您好！我是中国书法家知识图谱问答助手。您可以向我询问书法家的信息，系统会通过SPARQL端点自动查询或生成SPARQL语句来回答您的问题。</div>
                    </div>
                    <div class="input-group">
                        <input type="text" id="userInput" placeholder="请输入您的问题..." onkeypress="handleKeyPress(event)">
                        <button class="btn btn-primary" onclick="sendMessage()">发送</button>
                    </div>
                    <div class="example-tags">
                        <span class="example-tag" onclick="askExample('王羲之的师承是谁？')">王羲之的师承</span>
                        <span class="example-tag" onclick="askExample('查询唐代书法家')">唐代书法家</span>
                        <span class="example-tag" onclick="askExample('颜真卿的影响有哪些？')">颜真卿的影响</span>
                        <span class="example-tag" onclick="askExample('文彭的字号是什么？')">文彭的字号</span>
                        <span class="example-tag" onclick="askExample('查询文徵明的详细信息')">文徵明详细信息</span>
                        <span class="example-tag" onclick="askExample('擅长草书的书法家有哪些？')">擅长草书</span>
                    </div>
                </div>
            </div>
        </div>

        <div>
            <div class="card">
                <div class="card-title"><span class="icon">⚙️</span> 问答工作流</div>
                <p style="font-size:13px;color:var(--bronze);margin-bottom:16px;line-height:1.7;">
                    系统使用规则匹配+SPARQL端点+大模型的层次化工作流：
                </p>
                <div class="workflow-steps" style="flex-direction:column;align-items:stretch;gap:12px;">
                    <div class="workflow-step" style="flex-direction:row;gap:12px;min-width:auto;">
                        <span class="step-icon">📝</span>
                        <div>
                            <div class="step-name">1. 问句解析</div>
                            <div class="step-desc">提取命名实体，判断查询意图</div>
                        </div>
                    </div>
                    <div style="text-align:center;color:var(--cinnabar);">↓</div>
                    <div class="workflow-step" style="flex-direction:row;gap:12px;min-width:auto;">
                        <span class="step-icon">🔀</span>
                        <div>
                            <div class="step-name">2. 路由决策</div>
                            <div class="step-desc">规则匹配 / SPARQL生成 / 大模型回答</div>
                        </div>
                    </div>
                    <div style="text-align:center;color:var(--cinnabar);">↓</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
                        <div class="workflow-step" style="min-width:auto;padding:8px;">
                            <span class="step-icon">🔧</span>
                            <div class="step-name" style="font-size:11px;">规则匹配</div>
                        </div>
                        <div class="workflow-step" style="min-width:auto;padding:8px;">
                            <span class="step-icon">📊</span>
                            <div class="step-name" style="font-size:11px;">SPARQL生成</div>
                        </div>
                        <div class="workflow-step" style="min-width:auto;padding:8px;">
                            <span class="step-icon">🤖</span>
                            <div class="step-name" style="font-size:11px;">大模型回答</div>
                        </div>
                    </div>
                    <div style="text-align:center;color:var(--cinnabar);">↓</div>
                    <div class="workflow-step" style="flex-direction:row;gap:12px;min-width:auto;">
                        <span class="step-icon">✅</span>
                        <div>
                            <div class="step-name">3. 结果整合</div>
                            <div class="step-desc">大模型根据结果生成最终回答</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-title"><span class="icon">🔧</span> 可用查询</div>
                <div style="font-size:12px;color:var(--ink-medium);line-height:2;">
                    <div><span class="tag tag-red">query_all_calligraphers</span> 查询所有书法家</div>
                    <div><span class="tag tag-blue">query_by_script</span> 按书体查询书法家</div>
                    <div><span class="tag tag-blue">query_by_dynasty</span> 按朝代查询</div>
                    <div><span class="tag tag-green">query_calli_details</span> 查询详细信息</div>
                    <div><span class="tag tag-gold">query_teacher_of</span> 查询师承</div>
                    <div><span class="tag tag-purple">query_influenced_by</span> 查询影响</div>
                    <div><span class="tag tag-red">query_representative_works</span> 查询代表作品</div>
                    <div><span class="tag tag-blue">execute_custom_sparql</span> 自定义SPARQL</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function sendMessage() {{
            const input = document.getElementById('userInput');
            const message = input.value.trim();
            if (!message) return;
            addMessage(message, 'user');
            input.value = '';
            const loadingMsg = addMessage('正在思考中...', 'bot');
            try {{
                const response = await fetch('/api/chat', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ query: message }})
                }});
                const data = await response.json();
                loadingMsg.remove();
                if (data.error) {{
                    addMessage('抱歉，' + data.error, 'error');
                }} else {{
                    addMessage(data.response, 'bot');
                }}
            }} catch (error) {{
                loadingMsg.remove();
                addMessage('系统出错：' + error.message, 'error');
            }}
        }}

        function addMessage(content, type) {{
            const chatBox = document.getElementById('chatBox');
            const msg = document.createElement('div');
            msg.className = 'chat-message ' + type;
            // 简单的markdown渲染：处理加粗、换行、列表
            let html = content
                .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                .replace(/\\n- /g, '<br>• ')
                .replace(/\\n/g, '<br>');
            msg.innerHTML = html;
            chatBox.appendChild(msg);
            chatBox.scrollTop = chatBox.scrollHeight;
            return msg;
        }}

        function handleKeyPress(event) {{
            if (event.key === 'Enter') sendMessage();
        }}

        function askExample(question) {{
            document.getElementById('userInput').value = question;
            sendMessage();
        }}
    </script>
    """
    return get_page_template("/", "知识问答系统", content)




@app.get("/sparql", response_class=HTMLResponse)
async def sparql_page():
    content = """
    <div class="page-header">
        <h2>SPARQL查询</h2>
        <p>高级SPARQL查询界面，支持大模型自主生成SPARQL语句并执行</p>
    </div>

    <div class="main-side">
        <div>
            <div class="card">
                <div class="card-title"><span class="icon">🤖</span> 自然语言转SPARQL查询</div>
                <p style="font-size:12px;color:var(--bronze);margin-bottom:12px;line-height:1.7;">
                    输入自然语言问题，大模型将自动生成SPARQL语句并执行查询。基于few-shot示例引导大模型生成可执行的SPARQL。
                </p>
                <div style="display:flex;gap:10px;margin-bottom:12px;">
                    <input type="text" id="nlQuery" placeholder="例如：明代的草书书法家有哪些？" style="flex:1;padding:10px 14px;border:2px solid var(--paper-dark);border-radius:6px;font-size:14px;font-family:inherit;" />
                    <button class="btn btn-primary" onclick="nl2sparql()">生成并执行</button>
                </div>
                <div class="example-tags" style="margin-bottom:12px;">
                    <span class="example-tag" onclick="setNLExample('王羲之的师承是谁')">王羲之的师承</span>
                    <span class="example-tag" onclick="setNLExample('明代的草书书法家有哪些')">明代草书书法家</span>
                    <span class="example-tag" onclick="setNLExample('谁师从颜真卿')">谁师从颜真卿</span>
                    <span class="example-tag" onclick="setNLExample('各朝代书法家数量')">各朝代数量</span>
                    <span class="example-tag" onclick="setNLExample('文徵明的字号和生卒年')">文徵明字号生卒</span>
                    <span class="example-tag" onclick="setNLExample('文徵明的亲属有哪些')">文徵明亲属</span>
                </div>
                <div id="nlGeneratedSparql" style="display:none;margin-bottom:12px;">
                    <div style="font-size:12px;color:var(--bronze);margin-bottom:6px;">生成的SPARQL语句：</div>
                    <pre id="nlSparqlCode" style="background:var(--paper-dark);padding:12px;border-radius:6px;font-size:12px;overflow-x:auto;white-space:pre-wrap;font-family:monospace;"></pre>
                </div>
                <div class="sparql-result" id="nlResults">自然语言查询结果将显示在这里...</div>
            </div>

            <div class="card">
                <div class="card-title"><span class="icon">📋</span> SPARQL查询编辑器</div>
                <textarea class="sparql-editor" id="sparqlQuery">PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?name ?dynasty
WHERE {
    ?c a calli:Calligrapher ;
       rdfs:label ?name ;
       calli:dynasty ?dynasty .
}
LIMIT 20</textarea>
                <div style="display:flex;gap:10px;margin-top:12px;">
                    <button class="btn btn-primary" onclick="executeQuery()">▶ 执行查询</button>
                    <button class="btn btn-secondary" onclick="clearResults()">清除结果</button>
                </div>
                <div class="sparql-result" id="results">查询结果将显示在这里...</div>
            </div>

            <div class="card">
                <div class="card-title"><span class="icon">💡</span> 查询示例</div>
                <div class="example-tags">
                    <span class="example-tag" onclick="loadExample(1)">查询所有书法家</span>
                    <span class="example-tag" onclick="loadExample(2)">唐代书法家</span>
                    <span class="example-tag" onclick="loadExample(3)">王羲之详细信息</span>
                    <span class="example-tag" onclick="loadExample(4)">王羲之的师承</span>
                    <span class="example-tag" onclick="loadExample(5)">王羲之影响了谁</span>
                    <span class="example-tag" onclick="loadExample(6)">颜真卿的师承</span>
                    <span class="example-tag" onclick="loadExample(7)">擅长草书的书法家</span>
                    <span class="example-tag" onclick="loadExample(8)">有亲属关系的书法家</span>
                    <span class="example-tag" onclick="loadExample(9)">文彭开创了什么</span>
                    <span class="example-tag" onclick="loadExample(10)">CBDB链接查询</span>
                </div>
            </div>
        </div>

        <div>
            <div class="card">
                <div class="card-title"><span class="icon">📖</span> 本体结构参考</div>
                <table class="data-table">
                    <thead><tr><th>谓词</th><th>含义</th><th>类型</th></tr></thead>
                    <tbody>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:dynasty</td><td>所属朝代</td><td><span class="tag tag-blue">数据属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:birthYear</td><td>生年</td><td><span class="tag tag-blue">数据属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:deathYear</td><td>卒年</td><td><span class="tag tag-blue">数据属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:styleName</td><td>字号</td><td><span class="tag tag-blue">数据属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:hometown</td><td>籍贯</td><td><span class="tag tag-blue">数据属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:position</td><td>官衔</td><td><span class="tag tag-blue">数据属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:representativeWork</td><td>代表作品</td><td><span class="tag tag-blue">数据属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:writing</td><td>著述</td><td><span class="tag tag-blue">数据属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:learnedFrom</td><td>师承</td><td><span class="tag tag-green">对象属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:influenced</td><td>影响</td><td><span class="tag tag-green">对象属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:relative</td><td>亲属</td><td><span class="tag tag-green">对象属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:goodAtScript</td><td>擅长书体</td><td><span class="tag tag-green">对象属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">calli:created</td><td>开创</td><td><span class="tag tag-green">对象属性</span></td></tr>
                        <tr><td style="font-family:monospace;font-size:12px;">owl:sameAs</td><td>外部链接</td><td><span class="tag tag-gold">链接属性</span></td></tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div class="card-title"><span class="icon">📊</span> 关系类型分布</div>
                <div id="chart" class="chart-container-sm"></div>
            </div>
        </div>
    </div>

    <script>
        function setNLExample(text) {
            document.getElementById('nlQuery').value = text;
        }

        async function nl2sparql() {
            const query = document.getElementById('nlQuery').value.trim();
            if (!query) { alert('请输入自然语言问题'); return; }
            const resultsDiv = document.getElementById('nlResults');
            const sparqlDiv = document.getElementById('nlGeneratedSparql');
            const sparqlCode = document.getElementById('nlSparqlCode');
            resultsDiv.textContent = '大模型正在生成SPARQL语句...';
            sparqlDiv.style.display = 'none';
            try {
                const response = await fetch('/api/nl2sparql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });
                const data = await response.json();
                if (data.error) {
                    resultsDiv.innerHTML = '<span style="color:var(--cinnabar);">错误: ' + data.error + '</span>';
                } else {
                    // 显示生成的SPARQL
                    if (data.sparql) {
                        sparqlDiv.style.display = 'block';
                        sparqlCode.textContent = data.sparql;
                    }
                    // 显示查询结果
                    if (data.results && data.results.bindings && data.results.bindings.length > 0) {
                        const vars = data.head.vars;
                        let html = '<table class="data-table"><thead><tr>';
                        vars.forEach(v => html += '<th>' + v + '</th>');
                        html += '</tr></thead><tbody>';
                        data.results.bindings.forEach(row => {
                            html += '<tr>';
                            vars.forEach(v => {
                                const val = row[v] ? row[v].value : '';
                                html += '<td>' + val + '</td>';
                            });
                            html += '</tr>';
                        });
                        html += '</tbody></table>';
                        html += '<p style="margin-top:8px;font-size:12px;color:var(--bronze);">共 ' + data.results.bindings.length + ' 条结果</p>';
                        // 如果有LLM补充回答（部分维度缺失时），也显示
                        if (data.llm_supplement) {
                            html += '<div style="margin-top:12px;padding:12px;background:var(--paper-light);border-radius:8px;border-left:3px solid var(--bronze);"><strong>LLM整合回答：</strong><br><br>' + data.llm_supplement.replace(/\\n/g, '<br>') + '</div>';
                        }
                        resultsDiv.innerHTML = html;
                    } else if (data.sparql_error) {
                        let errorHtml = '<span style="color:var(--cinnabar);">SPARQL执行失败: ' + data.sparql_error + '</span>';
                        if (data.llm_supplement) {
                            errorHtml += '<div style="margin-top:12px;padding:12px;background:var(--paper-light);border-radius:8px;border-left:3px solid var(--cinnabar);"><strong>LLM补充回答：</strong><br>' + data.llm_supplement.replace(/\\n/g, '<br>') + '</div>';
                        }
                        resultsDiv.innerHTML = errorHtml;
                    } else if (data.llm_supplement) {
                        resultsDiv.innerHTML = '<div style="padding:12px;background:var(--paper-light);border-radius:8px;border-left:3px solid var(--bronze);"><strong>知识图谱查询结果为空，以下为LLM基于历史知识的补充回答：</strong><br><br>' + data.llm_supplement.replace(/\\n/g, '<br>') + '</div>';
                    } else {
                        resultsDiv.textContent = '查询结果为空';
                    }
                }
            } catch (error) {
                resultsDiv.innerHTML = '<span style="color:var(--cinnabar);">错误: ' + error.message + '</span>';
            }
        }

        const examples = {
            1: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?name
WHERE {
    ?c a calli:Calligrapher ;
       rdfs:label ?name .
}
LIMIT 20`,
            2: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?name ?dynasty
WHERE {
    ?c a calli:Calligrapher ;
       rdfs:label ?name ;
       calli:dynasty ?dynasty .
    FILTER(CONTAINS(?dynasty, "唐"))
}`,
            3: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?p ?o
WHERE {
    <http://example.org/calligraphy/calligrapher/王羲之> ?p ?o .
}`,
            4: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?teacher
WHERE {
    <http://example.org/calligraphy/calligrapher/王羲之> calli:learnedFrom ?t .
    ?t rdfs:label ?teacher .
}`,
            5: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?influenced
WHERE {
    <http://example.org/calligraphy/calligrapher/王羲之> calli:influenced ?i .
    ?i rdfs:label ?influenced .
}`,
            6: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?teacher
WHERE {
    <http://example.org/calligraphy/calligrapher/颜真卿> calli:learnedFrom ?t .
    ?t rdfs:label ?teacher .
}`,
            7: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?name ?script
WHERE {
    ?c a calli:Calligrapher ;
       rdfs:label ?name ;
       calli:goodAtScript ?s .
    ?s rdfs:label ?script .
    FILTER(CONTAINS(?script, "草书"))
}`,
            8: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?name ?relative
WHERE {
    ?c a calli:Calligrapher ;
       rdfs:label ?name ;
       calli:relative ?r .
    ?r rdfs:label ?relative .
}`,
            9: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?style
WHERE {
    <http://example.org/calligraphy/calligrapher/文彭> calli:created ?s .
    ?s rdfs:label ?style .
}`,
            10: `PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?name ?cbdb_link
WHERE {
    ?c a calli:Calligrapher ;
       rdfs:label ?name ;
       owl:sameAs ?cbdb_link .
}
LIMIT 20`
        };

        function loadExample(num) {
            document.getElementById('sparqlQuery').value = examples[num];
        }

        async function executeQuery() {
            const query = document.getElementById('sparqlQuery').value;
            const resultsDiv = document.getElementById('results');
            resultsDiv.textContent = '查询中...';
            try {
                const response = await fetch('/api/sparql?query=' + encodeURIComponent(query));
                const data = await response.json();
                if (data.error) {
                    resultsDiv.innerHTML = '<span style="color:var(--cinnabar);">错误: ' + data.error + '</span>';
                } else if (data.results && data.results.bindings) {
                    const vars = data.head.vars;
                    if (data.results.bindings.length === 0) {
                        resultsDiv.textContent = '查询结果为空';
                    } else {
                        let html = '<table class="data-table"><thead><tr>';
                        vars.forEach(v => html += '<th>' + v + '</th>');
                        html += '</tr></thead><tbody>';
                        data.results.bindings.forEach(row => {
                            html += '<tr>';
                            vars.forEach(v => {
                                const val = row[v] ? row[v].value : '';
                                html += '<td>' + val + '</td>';
                            });
                            html += '</tr>';
                        });
                        html += '</tbody></table>';
                        html += '<p style="margin-top:8px;font-size:12px;color:var(--bronze);">共 ' + data.results.bindings.length + ' 条结果</p>';
                        resultsDiv.innerHTML = html;
                    }
                } else {
                    resultsDiv.textContent = JSON.stringify(data, null, 2);
                }
            } catch (error) {
                resultsDiv.innerHTML = '<span style="color:var(--cinnabar);">错误: ' + error.message + '</span>';
            }
        }

        function clearResults() {
            document.getElementById('results').textContent = '查询结果将显示在这里...';
        }

        async function loadRelationStats() {
            try {
                const response = await fetch('/api/relation_stats');
                const data = await response.json();
                if (data.labels && data.counts) {
                    const chart = echarts.init(document.getElementById('chart'));
                    chart.setOption({
                        tooltip: { trigger: 'axis' },
                        xAxis: { type: 'category', data: data.labels, axisLabel: { rotate: 25, fontSize: 11 } },
                        yAxis: { type: 'value', name: '数量' },
                        series: [{
                            data: data.counts,
                            type: 'bar',
                            itemStyle: { color: '#c0392b', borderRadius: [4, 4, 0, 0] }
                        }],
                        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
                    });
                    window.addEventListener('resize', () => chart.resize());
                }
            } catch (error) {
                console.error('加载统计图表失败:', error);
            }
        }
        loadRelationStats();
    </script>
    """
    return get_page_template("/sparql", "SPARQL查询", content)


@app.get("/network", response_class=HTMLResponse)
async def network_page():
    content = f"""
    <div class="page-header">
        <h2>关系网络可视化</h2>
        <p>基于知识图谱数据的动态交互式人物关系网络</p>
    </div>

    <div class="card">
        <div class="card-title"><span class="icon">🕸️</span> 交互式关系网络图</div>
        <p style="font-size:13px;color:var(--bronze);margin-bottom:16px;line-height:1.7;">
            使用ECharts力导向图动态渲染，支持筛选关系类型、搜索人物、点击查看详情、拖拽节点、缩放平移等交互操作。
        </p>
        <div class="network-wrapper">
            <div class="network-toolbar">
                <div class="network-filter-group">
                    <span class="network-filter-label">关系类型：</span>
                    <button class="network-filter-btn active" data-type="all" onclick="filterRelation('all')">全部</button>
                    <button class="network-filter-btn" data-type="师承" onclick="filterRelation('师承')">师承</button>
                    <button class="network-filter-btn" data-type="影响" onclick="filterRelation('影响')">影响</button>
                    <button class="network-filter-btn" data-type="亲属" onclick="filterRelation('亲属')">亲属</button>
                    <button class="network-filter-btn" data-type="开创" onclick="filterRelation('开创')">开创</button>
                </div>
                <div class="network-filter-group">
                    <span class="network-filter-label">朝代：</span>
                    <button class="network-filter-btn active" data-dynasty="all" onclick="filterDynasty('all')">全部</button>
                    <button class="network-filter-btn" data-dynasty="秦汉魏晋" onclick="filterDynasty('秦汉魏晋')">秦汉魏晋</button>
                    <button class="network-filter-btn" data-dynasty="隋唐五代" onclick="filterDynasty('隋唐五代')">隋唐五代</button>
                    <button class="network-filter-btn" data-dynasty="宋元" onclick="filterDynasty('宋元')">宋元</button>
                    <button class="network-filter-btn" data-dynasty="明清" onclick="filterDynasty('明清')">明清</button>
                </div>
                <input type="text" class="network-search" id="networkSearch" placeholder="搜索书法家姓名..." onkeyup="searchNode(this.value)" />
            </div>
            <div class="network-container" id="networkChart"></div>
            <div class="network-legend">
                <div class="legend-item"><div class="legend-line teacher"></div><span>师承关系</span></div>
                <div class="legend-item"><div class="legend-line influenced"></div><span>影响关系</span></div>
                <div class="legend-item"><div class="legend-line relative"></div><span>亲属关系</span></div>
                <div class="legend-item"><div class="legend-line created"></div><span>开创流派</span></div>
            </div>
            <div class="network-stats-bar" id="networkStats">节点: 0 | 关系: 0</div>
            <div class="node-detail-panel" id="nodeDetailPanel">
                <div class="node-detail-header">
                    <h4 id="nodeDetailName">-</h4>
                    <button class="node-detail-close" onclick="closeNodeDetail()">×</button>
                </div>
                <div class="node-detail-body" id="nodeDetailBody">
                    <p style="text-align:center;color:var(--bronze);">点击节点查看详情</p>
                </div>
            </div>
        </div>
    </div>

    <div class="two-col">
        <div class="card">
            <div class="card-title"><span class="icon">🏆</span> 影响力排名（中心性分析）</div>
            <p style="font-size:12px;color:var(--bronze);margin-bottom:10px;">
                度中心性衡量直接影响力，节点越大表示影响力越强
            </p>
            <div class="rank-list" id="centralityList" style="max-height:300px;">
                <p style="text-align:center;color:var(--bronze);padding:20px;">加载中...</p>
            </div>
        </div>
        <div class="card">
            <div class="card-title"><span class="icon">🛤️</span> 路径分析 - 师承脉络</div>
            <p style="font-size:12px;color:var(--bronze);margin-bottom:10px;">
                探索书法家之间的师承传承路径
            </p>
            <div id="pathAnalysis">
                <p style="text-align:center;color:var(--bronze);">加载中...</p>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-title"><span class="icon">📝</span> 操作说明</div>
        <div style="font-size:13px;color:var(--ink-medium);line-height:2;">
            <div><strong>筛选关系</strong>：点击关系类型按钮筛选特定关系</div>
            <div><strong>筛选朝代</strong>：点击朝代按钮筛选特定时期的人物</div>
            <div><strong>搜索人物</strong>：输入姓名搜索并高亮显示</div>
            <div><strong>查看详情</strong>：点击节点查看书法家详细信息</div>
            <div><strong>拖拽节点</strong>：鼠标拖拽节点调整位置</div>
            <div><strong>缩放平移</strong>：鼠标滚轮缩放，拖拽空白区域平移</div>
            <div><strong>节点大小</strong>：节点越大表示度中心性越高（影响力越强）</div>
            <div><strong>节点颜色</strong>：按朝代分类：秦汉魏晋(棕)、隋唐五代(金)、宋元(蓝)、明清(红)</div>
        </div>
    </div>

    <script>
        let networkChart = null;
        let originalData = null;
        let currentRelationFilter = 'all';
        let currentDynastyFilter = 'all';

        const relationColors = {{
            '师承': '#3498db',
            '影响': '#27ae60',
            '亲属': '#c0392b',
            '开创': '#9b59b6'
        }};

        const dynastyColors = [
            '#8B4513',
            '#DAA520',
            '#2c3e50',
            '#c0392b',
            '#95a5a6'
        ];

        async function loadNetworkData() {{
            try {{
                const response = await fetch('/api/network_data');
                const data = await response.json();
                originalData = data;
                renderNetwork(data);
                updateStats(data);
            }} catch (error) {{
                console.error('加载网络数据失败:', error);
                document.getElementById('networkChart').innerHTML = '<p style="text-align:center;padding:100px;color:var(--cinnabar);">数据加载失败，请刷新页面重试</p>';
            }}
        }}

        function renderNetwork(data) {{
            const container = document.getElementById('networkChart');
            if (!networkChart) {{
                networkChart = echarts.init(container);
            }}

            const nodes = data.nodes.map(node => ({{
                name: node.name,
                symbolSize: node.symbolSize,
                category: node.category,
                dynasty: node.dynasty,
                itemStyle: {{
                    color: dynastyColors[node.category] || dynastyColors[4]
                }},
                label: {{
                    show: true,
                    fontSize: node.symbolSize > 30 ? 12 : (node.symbolSize > 20 ? 10 : 8),
                    color: '#333'
                }}
            }}));

            const links = data.links.map(link => ({{
                source: link.source,
                target: link.target,
                type: link.type,
                lineStyle: {{
                    color: relationColors[link.type] || '#999',
                    width: link.type === '师承' ? 2 : 1.5,
                    curveness: link.type === '影响' ? 0.2 : 0
                }}
            }}));

            const option = {{
                tooltip: {{
                    trigger: 'item',
                    formatter: function(params) {{
                        if (params.dataType === 'node') {{
                            return `<strong>${{params.data.name}}</strong><br/>朝代: ${{params.data.dynasty || '未知'}}`;
                        }} else {{
                            return `${{params.data.source}} → ${{params.data.target}}<br/>关系: ${{params.data.type}}`;
                        }}
                    }}
                }},
                series: [{{
                    type: 'graph',
                    layout: 'force',
                    data: nodes,
                    links: links,
                    categories: data.categories.map((cat, i) => ({{
                        name: cat.name,
                        itemStyle: {{ color: dynastyColors[i] }}
                    }})),
                    roam: true,
                    draggable: true,
                    focusNodeAdjacency: true,
                    force: {{
                        repulsion: 300,
                        gravity: 0.1,
                        edgeLength: [50, 150],
                        layoutAnimation: true
                    }},
                    emphasis: {{
                        focus: 'adjacency',
                        lineStyle: {{ width: 3 }}
                    }},
                    edgeSymbol: ['none', 'arrow'],
                    edgeSymbolSize: [4, 8],
                    lineStyle: {{
                        opacity: 0.6
                    }}
                }}]
            }};

            networkChart.setOption(option);

            networkChart.on('click', function(params) {{
                if (params.dataType === 'node') {{
                    showNodeDetail(params.data.name);
                }}
            }});
        }}

        function filterRelation(type) {{
            currentRelationFilter = type;
            updateFilterButtons('type', type);
            applyFilters();
        }}

        function filterDynasty(dynasty) {{
            currentDynastyFilter = dynasty;
            updateFilterButtons('dynasty', dynasty);
            applyFilters();
        }}

        function updateFilterButtons(filterType, activeValue) {{
            const buttons = document.querySelectorAll(`.network-filter-btn[data-${{filterType}}]`);
            buttons.forEach(btn => {{
                btn.classList.toggle('active', btn.dataset[filterType] === activeValue);
            }});
        }}

        function applyFilters() {{
            if (!originalData) return;

            let filteredNodes = [...originalData.nodes];
            let filteredLinks = [...originalData.links];

            if (currentRelationFilter !== 'all') {{
                filteredLinks = filteredLinks.filter(link => link.type === currentRelationFilter);
                const connectedNodes = new Set();
                filteredLinks.forEach(link => {{
                    connectedNodes.add(link.source);
                    connectedNodes.add(link.target);
                }});
                filteredNodes = filteredNodes.filter(node => connectedNodes.has(node.name));
            }}

            if (currentDynastyFilter !== 'all') {{
                const dynastyMap = {{
                    '秦汉魏晋': [0],
                    '隋唐五代': [1],
                    '宋元': [2],
                    '明清': [3]
                }};
                const allowedCategories = dynastyMap[currentDynastyFilter] || [0,1,2,3,4];
                filteredNodes = filteredNodes.filter(node => allowedCategories.includes(node.category));
                const nodeNames = new Set(filteredNodes.map(n => n.name));
                filteredLinks = filteredLinks.filter(link => nodeNames.has(link.source) && nodeNames.has(link.target));
            }}

            renderNetwork({{
                nodes: filteredNodes,
                links: filteredLinks,
                categories: originalData.categories
            }});
            updateStats({{ nodes: filteredNodes, links: filteredLinks }});
        }}

        function searchNode(keyword) {{
            if (!networkChart || !keyword.trim()) {{
                if (networkChart) {{
                    networkChart.dispatchAction({{
                        type: 'downplay',
                        seriesIndex: 0
                    }});
                }}
                return;
            }}

            networkChart.dispatchAction({{
                type: 'highlight',
                seriesIndex: 0,
                name: keyword.trim()
            }});
        }}

        async function showNodeDetail(name) {{
            const panel = document.getElementById('nodeDetailPanel');
            const nameEl = document.getElementById('nodeDetailName');
            const bodyEl = document.getElementById('nodeDetailBody');

            nameEl.textContent = name;
            panel.classList.add('show');

            try {{
                const response = await fetch(`/api/calligrapher_detail?name=${{encodeURIComponent(name)}}`);
                const data = await response.json();

                if (data.info && data.info.length > 0) {{
                    bodyEl.innerHTML = data.info.map(item =>
                        `<div class="node-detail-item"><span class="label">${{item.split('：')[0]}}：</span><span class="value">${{item.split('：')[1] || ''}}</span></div>`
                    ).join('');
                }} else {{
                    bodyEl.innerHTML = '<p style="text-align:center;color:var(--bronze);">暂无详细信息</p>';
                }}
            }} catch (error) {{
                bodyEl.innerHTML = '<p style="text-align:center;color:var(--cinnabar);">加载详情失败</p>';
            }}
        }}

        function closeNodeDetail() {{
            document.getElementById('nodeDetailPanel').classList.remove('show');
        }}

        function updateStats(data) {{
            document.getElementById('networkStats').textContent = `节点: ${{data.nodes.length}} | 关系: ${{data.links.length}}`;
        }}

        async function loadCentralityData() {{
            try {{
                const response = await fetch('/api/centrality_data');
                const data = await response.json();
                const list = document.getElementById('centralityList');
                if (list && data.centrality) {{
                    list.innerHTML = data.centrality.slice(0, 15).map(item => {{
                        const badgeClass = item.rank <= 3 ? ['gold', 'silver', 'bronze'][item.rank - 1] : 'normal';
                        return `<div class="rank-item">
                            <span class="rank-badge ${{badgeClass}}">${{item.rank}}</span>
                            <span class="rank-name">${{item.name}}</span>
                            <span class="rank-score">综合: ${{item.composite.toFixed(3)}}</span>
                        </div>`;
                    }}).join('');
                }}
            }} catch (error) {{
                console.error('加载中心性数据失败:', error);
            }}
        }}

        async function loadPathAnalysis() {{
            try {{
                const response = await fetch('/api/path_analysis');
                const data = await response.json();
                const container = document.getElementById('pathAnalysis');
                if (data.paths && data.paths.length > 0) {{
                    container.innerHTML = data.paths.slice(0, 5).map(p => {{
                        if (p.status !== '找到') return `<div class="path-display"><span>${{p.source}} → ${{p.target}}: ${{p.status}}</span></div>`;
                        const nodes = p.path.split(' → ');
                        return `<div class="path-display">
                            <strong style="margin-right:8px;color:var(--cinnabar);">${{p.source}} → ${{p.target}}</strong>
                            ${{nodes.map((n, i) => `<span class="path-node">${{n}}</span>${{i < nodes.length - 1 ? '<span class="path-arrow">→</span>' : ''}}`).join('')}}
                            <span style="margin-left:8px;font-size:12px;color:var(--bronze);">长度: ${{p.length}}</span>
                        </div>`;
                    }}).join('');
                }} else {{
                    container.innerHTML = '<p style="text-align:center;color:var(--bronze);">暂无路径分析数据</p>';
                }}
            }} catch (error) {{
                console.error('加载路径分析失败:', error);
            }}
        }}

        loadNetworkData();
        loadCentralityData();
        loadPathAnalysis();

        window.addEventListener('resize', function() {{
            if (networkChart) {{
                networkChart.resize();
            }}
        }});
    </script>
    """
    return get_page_template("/network", "关系网络", content)


@app.get("/schools", response_class=HTMLResponse)
async def schools_page():
    content = """
    <div class="page-header">
        <h2>流派与图结构分析</h2>
        <p>书法流派分析、社区发现、中心性分析与路径分析</p>
    </div>

    <div class="card">
        <div class="card-title"><span class="icon">🏛️</span> 主要书法流派</div>
        <div class="school-grid" id="schoolsGrid">
            <p style="text-align:center;color:var(--bronze);padding:20px;">加载中...</p>
        </div>
    </div>

    <div class="two-col">
        <div class="card">
            <div class="card-title"><span class="icon">📈</span> 流派人数分布</div>
            <div id="pieChart" class="chart-container-sm"></div>
        </div>
        <div class="card">
            <div class="card-title"><span class="icon">📊</span> 流派影响力对比</div>
            <div id="barChart" class="chart-container-sm"></div>
        </div>
    </div>

    <div class="card">
        <div class="card-title"><span class="icon">🏆</span> 图结构分析 - 中心性Top 20</div>
        <div id="centralityChart" class="chart-container-sm"></div>
    </div>

    <script>
        let schoolsData = null;

        async function loadSchoolsData() {
            try {
                const response = await fetch('/api/schools_data');
                schoolsData = await response.json();
                renderSchools(schoolsData);
            } catch (error) {
                console.error('加载流派数据失败:', error);
            }
        }

        function renderSchools(data) {
            const grid = document.getElementById('schoolsGrid');
            grid.innerHTML = data.schools.map(school => `
                <div class="school-card">
                    <h4>${school.name}</h4>
                    <div class="info-line"><span class="info-label">代表人物：</span>${school.representatives.length > 0 ? school.representatives.join('、') : '暂无'}</div>
                    <div class="info-line"><span class="info-label">成员数量：</span>${school.count}人</div>
                    ${school.members_preview.length > 0 ? '<div class="info-line" style="font-size:12px;color:var(--bronze);margin-top:4px;">' + school.members_preview.join('、') + '...</div>' : ''}
                </div>
            `).join('');

            const topSchools = data.schools.slice(0, 10);
            const colors = ['#c0392b', '#2c3e50', '#27ae60', '#d4a017', '#8e44ad', '#e67e22', '#1abc9c', '#3498db', '#95a5a6', '#7f8c8d'];

            const pieChart = echarts.init(document.getElementById('pieChart'));
            pieChart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
                legend: { orient: 'vertical', left: 'left', top: 'middle', textStyle: { fontSize: 11 } },
                series: [{
                    type: 'pie',
                    radius: ['35%', '65%'],
                    data: topSchools.map((s, i) => ({ value: s.count, name: s.name, itemStyle: { color: colors[i % colors.length] } })),
                    itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
                    label: { show: false },
                    emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } }
                }]
            });

            const barChart = echarts.init(document.getElementById('barChart'));
            barChart.setOption({
                tooltip: { trigger: 'axis' },
                grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
                xAxis: { type: 'category', data: topSchools.map(s => s.name.replace('派', '')), axisLabel: { rotate: 25, fontSize: 11 } },
                yAxis: { type: 'value', name: '人数' },
                series: [{
                    data: topSchools.map(s => s.count),
                    type: 'bar',
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#c0392b' },
                            { offset: 1, color: '#e74c3c' }
                        ]),
                        borderRadius: [4, 4, 0, 0]
                    },
                    label: { show: true, position: 'top', fontSize: 11 }
                }]
            });

            window.addEventListener('resize', () => { pieChart.resize(); barChart.resize(); });
        }

        async function loadCentralityChart() {
            try {
                const response = await fetch('/api/centrality_data');
                const data = await response.json();
                if (data.centrality && data.centrality.length > 0) {
                    const top20 = data.centrality.slice(0, 20);
                    const chart = echarts.init(document.getElementById('centralityChart'));
                    chart.setOption({
                        tooltip: { trigger: 'axis' },
                        legend: { data: ['度中心性', '介数中心性', '接近中心性'], top: 0 },
                        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
                        xAxis: { type: 'category', data: top20.map(i => i.name), axisLabel: { rotate: 35, fontSize: 10 } },
                        yAxis: { type: 'value' },
                        series: [
                            { name: '度中心性', type: 'bar', data: top20.map(i => i.degree), itemStyle: { color: '#c0392b' } },
                            { name: '介数中心性', type: 'bar', data: top20.map(i => i.betweenness), itemStyle: { color: '#2c3e50' } },
                            { name: '接近中心性', type: 'bar', data: top20.map(i => i.closeness), itemStyle: { color: '#27ae60' } }
                        ]
                    });
                    window.addEventListener('resize', () => chart.resize());
                }
            } catch (error) {
                console.error('加载中心性图表失败:', error);
            }
        }

        loadSchoolsData();
        loadCentralityChart();
    </script>
    """
    return get_page_template("/schools", "流派分析", content)





# ============================================================
# API端点
# ============================================================

@app.get("/api/relation_stats")
async def relation_stats():
    label_map = {
        "learnedFrom": "师承", "influenced": "影响", "relative": "亲属",
        "goodAtScript": "擅长书体", "created": "开创",
        "styleName": "字号", "representativeWork": "代表作品",
        "writing": "著述", "hometown": "籍贯", "dynasty": "朝代",
        "birthYear": "生年", "deathYear": "卒年", "position": "官衔",
        "artFeature": "艺术特色", "styleCharacteristic": "风格特征",
        "otherSkill": "兼习"
    }
    stats = {}
    for s, p, o in g:
        p_str = str(p)
        if CALLI_NS in p_str:
            prop = p_str.split("#")[-1]
            label = label_map.get(prop, prop)
            stats[label] = stats.get(label, 0) + 1
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    return {"labels": [item[0] for item in sorted_stats], "counts": [item[1] for item in sorted_stats]}


@app.get("/api/network_data")
async def network_data():
    queries = {
        "teacher": """PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?teacher WHERE { ?c a calli:Calligrapher ; rdfs:label ?name ; calli:learnedFrom ?t . ?t rdfs:label ?teacher . }""",
        "influenced": """PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?influenced WHERE { ?c a calli:Calligrapher ; rdfs:label ?name ; calli:influenced ?i . ?i rdfs:label ?influenced . }""",
        "relative": """PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?relative WHERE { ?c a calli:Calligrapher ; rdfs:label ?name ; calli:relative ?r . ?r rdfs:label ?relative . }""",
        "created": """PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?style WHERE { ?c a calli:Calligrapher ; rdfs:label ?name ; calli:created ?s . ?s rdfs:label ?style . }""",
        "dynasty": """PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?dynasty WHERE { ?c a calli:Calligrapher ; rdfs:label ?name ; calli:dynasty ?dynasty . }""",
        "centrality": """PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name (COUNT(?p) AS ?degree) WHERE { ?c a calli:Calligrapher ; rdfs:label ?name ; ?p ?o . } GROUP BY ?name ORDER BY DESC(?degree) LIMIT 200""",
    }

    nodes_set = set()
    links = []
    dynasty_map = {}
    degree_map = {}

    for row in g.query(queries["dynasty"]):
        name, dynasty = str(row[0]), str(row[1])
        dynasty_map[name] = dynasty
        nodes_set.add(name)

    for row in g.query(queries["centrality"]):
        degree_map[str(row[0])] = int(row[1])

    for row in g.query(queries["teacher"]):
        name, teacher = str(row[0]), str(row[1])
        nodes_set.update([name, teacher])
        links.append({"source": teacher, "target": name, "type": "师承"})

    for row in g.query(queries["influenced"]):
        name, influenced = str(row[0]), str(row[1])
        nodes_set.update([name, influenced])
        links.append({"source": name, "target": influenced, "type": "影响"})

    for row in g.query(queries["relative"]):
        name, relative = str(row[0]), str(row[1])
        nodes_set.update([name, relative])
        links.append({"source": name, "target": relative, "type": "亲属"})

    for row in g.query(queries["created"]):
        name, style = str(row[0]), str(row[1])
        nodes_set.add(name)
        links.append({"source": name, "target": style, "type": "开创"})

    # 限制节点数量：只保留度中心性Top 300的节点，避免ECharts渲染卡顿
    MAX_NODES = 300
    if len(nodes_set) > MAX_NODES:
        # 按度中心性排序，保留Top节点
        sorted_nodes = sorted(nodes_set, key=lambda n: degree_map.get(n, 1), reverse=True)
        top_nodes = set(sorted_nodes[:MAX_NODES])
        # 过滤边：只保留两端节点都在top_nodes中的边
        links = [l for l in links if l["source"] in top_nodes and l["target"] in top_nodes]
        nodes_set = top_nodes

    dynasty_to_category = {
        "秦": 0, "西汉": 0, "东汉": 0, "三国": 0, "魏": 0, "晋": 0, "东晋": 0, "西晋": 0, "南北朝": 0,
        "隋": 1, "唐": 1, "五代": 1,
        "宋": 2, "北宋": 2, "南宋": 2, "金": 2, "元": 2,
        "明": 3, "清": 3, "现代": 3, "民国": 3
    }

    max_degree = max(degree_map.values()) if degree_map else 1
    nodes = []
    for name in nodes_set:
        dynasty = dynasty_map.get(name, "")
        category = dynasty_to_category.get(dynasty, 4)
        degree = degree_map.get(name, 1)
        symbol_size = max(15, min(80, 15 + (degree / max_degree) * 65))
        nodes.append({"name": name, "symbolSize": round(symbol_size), "category": category, "dynasty": dynasty})

    return {
        "nodes": nodes, "links": links,
        "categories": [
            {"name": "秦汉魏晋南北朝"}, {"name": "隋唐五代"}, {"name": "宋元"}, {"name": "明清现代"}, {"name": "其他"}
        ]
    }


@app.get("/api/calligrapher_detail")
async def calligrapher_detail(name: str):
    """获取书法家详细信息，用于网络图节点点击展示"""
    predicate_map = {
        "dynasty": "朝代", "birthYear": "生年", "deathYear": "卒年", "styleName": "字号",
        "hometown": "籍贯", "position": "官衔", "representativeWork": "代表作品",
        "writing": "著述", "artFeature": "艺术特色", "styleCharacteristic": "风格特征",
        "otherSkill": "兼习", "learnedFrom": "师承", "influenced": "影响",
        "relative": "亲属", "goodAtScript": "擅长书体", "created": "开创",
    }

    q = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?p ?o WHERE {{
        <http://example.org/calligraphy/calligrapher/{name}> ?p ?o .
    }}
    """

    info = []
    for row in g.query(q):
        p = str(row[0]).split("#")[-1] if "#" in str(row[0]) else str(row[0]).split("/")[-1]
        o = str(row[1])
        if p in predicate_map:
            if "calligrapher/" in o:
                o = o.split("calligrapher/")[-1]
            elif "script/" in o:
                o = o.split("script/")[-1]
            elif "style/" in o:
                o = o.split("style/")[-1]
            info.append(f"{predicate_map[p]}：{o}")

    return {"name": name, "info": info}


@app.get("/api/centrality_data")
async def centrality_data():
    centrality_list = []
    csv_path = os.path.join(ANALYSIS_DIR, 'centrality_analysis.csv')
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 20: break
                centrality_list.append({
                    "rank": i + 1,
                    "name": row.get("name", ""),
                    "degree": float(row.get("degree_centrality", 0)),
                    "betweenness": float(row.get("betweenness_centrality", 0)),
                    "closeness": float(row.get("closeness_centrality", 0)),
                    "composite": float(row.get("综合得分", 0))
                })
    return {"centrality": centrality_list}


@app.get("/api/path_analysis")
async def path_analysis_data():
    paths = []
    csv_path = os.path.join(ANALYSIS_DIR, 'path_analysis.csv')
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                paths.append({
                    "source": row.get("source", ""),
                    "target": row.get("target", ""),
                    "path": row.get("path", ""),
                    "length": int(row.get("length", -1)) if row.get("length", "-1").isdigit() else -1,
                    "status": row.get("status", "")
                })
    return {"paths": paths}




@app.get("/api/schools_data")
async def schools_data():
    schools_list = []
    csv_path = os.path.join(ANALYSIS_DIR, 'school_analysis.csv')
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                members_str = row.get("成员列表", "")
                members = [m.strip() for m in members_str.split(";") if m.strip()] if members_str else []
                reps_str = row.get("代表人物", "")
                reps = [r.strip() for r in reps_str.split(";") if r.strip()] if reps_str else []
                schools_list.append({
                    "name": row.get("流派名称", ""),
                    "count": int(row.get("总人数", 0)),
                    "script_distribution": row.get("书体分布", ""),
                    "representatives": reps[:5],
                    "members_preview": members[:10]
                })
    if not schools_list:
        query = """
        PREFIX calli: <http://example.org/ontology/calligraphy#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?script (COUNT(?c) AS ?count) WHERE {
            ?c a calli:Calligrapher ; calli:goodAtScript ?s . ?s rdfs:label ?script .
        } GROUP BY ?script ORDER BY DESC(?count)
        """
        for row in g.query(query):
            schools_list.append({
                "name": f"{str(row[0])}派", "count": int(row[1]),
                "script_distribution": str(row[0]), "representatives": [], "members_preview": []
            })
    return {"schools": schools_list}


@app.get("/api/chat")
async def chat_get():
    return {"error": "请使用POST方法提交问题"}


@app.post("/api/chat")
async def chat(request: Request):
    try:
        body = await request.json()
        query = body.get("query", "")
        if not query:
            return {"error": "请提供查询内容"}

        # 使用LangGraph工作流处理查询
        if LLM_AVAILABLE and _llm is not None and _agent_workflow is not None:
            try:
                result = _agent_workflow.invoke({
                    "messages": [HumanMessage(content=query)]
                })
                # 提取最终AI回答
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
                        return {"response": msg.content}
                return {"response": "未找到有效的查询结果"}
            except Exception as e:
                print(f"LangGraph工作流执行失败: {e}")
                import traceback
                traceback.print_exc()

        # LLM不可用时，回退到规则匹配
        rule_result = await process_query(query)
        if rule_result:
            return {"response": rule_result}

        return {"response": "您好！我可以帮您查询知识图谱中书法家的师承、影响、字号、生卒年、朝代、代表作品、擅长书体、亲属、籍贯、官衔等信息。\n\n例如：\n• '王羲之的字号是什么'\n• '颜真卿的师承是谁'\n• '唐代书法家有哪些'\n• '擅长草书的书法家有哪些'\n• '文徵明的详细信息'"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


async def _generate_sparql_with_llm(query: str) -> str:
    """使用LLM生成SPARQL查询语句"""
    sparql_prompt = f"""用户查询：{query}

请生成一个有效的SPARQL查询语句。

## 命名空间
PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

## 本体结构
- calli:Calligrapher: 书法家类型
- rdfs:label: 姓名
- calli:dynasty: 朝代
- calli:birthYear/deathYear: 生卒年
- calli:styleName: 字号
- calli:hometown: 籍贯
- calli:position: 官衔
- calli:representativeWork: 代表作品
- calli:learnedFrom: 师承（对象属性，指向另一个Calligrapher，表示此人师从谁）
- calli:influenced: 受影响（对象属性，指向另一个Calligrapher，表示此人受到谁影响）
- calli:relative: 亲属（对象属性，指向另一个Calligrapher）
- calli:goodAtScript: 擅长书体（对象属性，指向Script）
- calli:created: 开创（对象属性，指向InnovationStyle）
- 实体URI格式：<http://example.org/calligraphy/calligrapher/姓名>

注意关系的方向：
- 查询"XX的师承/老师"：XX calli:learnedFrom ?teacher
- 查询"XX的学生/弟子"：?student calli:learnedFrom XX（反向）
- 查询"XX受到谁影响"：XX calli:influenced ?influencer
- 查询"XX影响了谁/对后世的影响"：?influencedPerson calli:influenced XX（反向）

## 注意事项
1. 只返回SPARQL查询语句，不要包含其他解释性文字
2. 查询语句必须是完整且有效的
3. 使用UNION时，必须将所有UNION分支放在同一个WHERE花括号内，每个分支用独立的花括号包裹。绝对不能将UNION放在WHERE花括号外面。
4. 不要在URI两端添加反引号或其他引号字符
5. 用户问题包含多个维度时，必须用UNION将所有维度都包含在查询中，不能遗漏

## Few-shot示例

示例1 - 单属性查询："王羲之的师承"
SELECT ?teacher WHERE {{ <http://example.org/calligraphy/calligrapher/王羲之> calli:learnedFrom ?t . ?t rdfs:label ?teacher . }}

示例2 - FILTER条件查询："唐代书法家"
SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:dynasty ?d . FILTER(CONTAINS(?d, "唐")) }}

示例3 - 单属性查询："颜真卿的字号"
SELECT ?styleName WHERE {{ <http://example.org/calligraphy/calligrapher/颜真卿> calli:styleName ?styleName . }}

示例4 - 多条件组合查询："明代的草书书法家有哪些"
SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:dynasty ?d ; calli:goodAtScript ?s . ?s rdfs:label ?script . FILTER(CONTAINS(?d, "明") && CONTAINS(?script, "草书")) }}

示例5 - 关系反向查询："谁师从王羲之"
SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:learnedFrom <http://example.org/calligraphy/calligrapher/王羲之> . }}

示例5b - 影响反向查询："王羲之影响了谁"
SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:influenced <http://example.org/calligraphy/calligrapher/王羲之> . }}

示例6 - 多属性查询："文徵明的字号和生卒年"
SELECT ?styleName ?birthYear ?deathYear WHERE {{ <http://example.org/calligraphy/calligrapher/文徵明> calli:styleName ?styleName ; calli:birthYear ?birthYear ; calli:deathYear ?deathYear . }}

示例7 - 聚合查询："各朝代书法家数量"
SELECT ?dynasty (COUNT(?c) AS ?count) WHERE {{ ?c a calli:Calligrapher ; calli:dynasty ?dynasty . }} GROUP BY ?dynasty ORDER BY DESC(?count)

示例8 - 亲属关系查询："文徵明的亲属有哪些"
SELECT ?relative WHERE {{ <http://example.org/calligraphy/calligrapher/文徵明> calli:relative ?r . ?r rdfs:label ?relative . }}

示例9 - 交游圈查询："王羲之的交游圈"
SELECT ?relation ?person WHERE {{ {{ <http://example.org/calligraphy/calligrapher/王羲之> calli:learnedFrom ?t . ?t rdfs:label ?person . BIND("师承" AS ?relation) }} UNION {{ <http://example.org/calligraphy/calligrapher/王羲之> calli:influenced ?i . ?i rdfs:label ?person . BIND("影响" AS ?relation) }} UNION {{ <http://example.org/calligraphy/calligrapher/王羲之> calli:relative ?r . ?r rdfs:label ?person . BIND("亲属" AS ?relation) }} }}

示例10 - 多维度UNION查询："范仲淹的亲属和影响"
SELECT ?relation ?person WHERE {{ {{ <http://example.org/calligraphy/calligrapher/范仲淹> calli:relative ?r . ?r rdfs:label ?person . BIND("亲属" AS ?relation) }} UNION {{ ?s calli:influenced <http://example.org/calligraphy/calligrapher/范仲淹> . ?s rdfs:label ?person . BIND("影响" AS ?relation) }} }}"""

    sparql_response = _llm.invoke([SystemMessage(content=sparql_prompt)])
    sparql_query = sparql_response.content.strip()
    # 清理markdown代码块标记
    if sparql_query.startswith("```"):
        sparql_query = sparql_query.split("\n", 1)[-1]
    if sparql_query.endswith("```"):
        sparql_query = sparql_query.rsplit("```", 1)[0]
    sparql_query = sparql_query.strip()
    # 清理LLM可能在URI中添加的反引号（包括ASCII反引号和Unicode左右反引号）
    for ch in ['`', '\u2018', '\u2019', '\u201C', '\u201D']:
        sparql_query = sparql_query.replace(ch, '')
    return sparql_query


async def _query_sparql_endpoint(sparql_query: str) -> str:
    """通过SPARQLWrapper查询SPARQL端点"""
    try:
        sparql = SPARQLWrapper(SPARQL_ENDPOINT)
        sparql.setQuery(sparql_query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        # 格式化结果
        if results and "results" in results and "bindings" in results["results"]:
            bindings = results["results"]["bindings"]
            if not bindings:
                return ""
            vars_list = results.get("head", {}).get("vars", [])
            lines = []
            for binding in bindings:
                row_parts = []
                for var in vars_list:
                    if var in binding:
                        val = binding[var].get("value", "")
                        # 简化URI显示
                        if "calligrapher/" in val:
                            val = val.split("calligrapher/")[-1]
                        elif "script/" in val:
                            val = val.split("script/")[-1]
                        elif "style/" in val:
                            val = val.split("style/")[-1]
                        row_parts.append(val)
                    else:
                        row_parts.append("")
                lines.append("：".join(row_parts))
            return "\n".join(lines)
        return ""
    except Exception as e:
        print(f"SPARQL端点查询失败: {e}")
        # 回退到本地rdflib查询
        try:
            results = g.query(sparql_query)
            lines = []
            for row in results:
                row_parts = []
                for val in row:
                    v = str(val) if val else ""
                    if "calligrapher/" in v: v = v.split("calligrapher/")[-1]
                    elif "script/" in v: v = v.split("script/")[-1]
                    elif "style/" in v: v = v.split("style/")[-1]
                    row_parts.append(v)
                lines.append("：".join(row_parts))
            return "\n".join(lines) if lines else ""
        except Exception as e2:
            print(f"本地SPARQL查询也失败: {e2}")
            return ""


async def _summarize_with_llm(query: str, sparql_result: str) -> str:
    """使用LLM整合SPARQL结果生成最终回答"""
    prompt = f"""用户查询：{query}

SPARQL查询结果：
{sparql_result}

请根据以上信息，为用户提供一个清晰、简洁的最终答案。

回答规则：
- 如果查询结果中有有效数据，优先基于查询结果回答
- 如果查询结果为空，说明知识图谱中未查到相关数据，请使用你自己的知识进行补充回答
- 如果用户查询涉及多个方面，但查询结果只覆盖了部分方面，对于已有结果的部分直接使用查询结果，对于缺失的部分使用你自己的知识进行补充，并标注"（根据历史知识补充）"
- 当使用自己的知识补充时，必须明确区分来源，格式如："知识图谱中暂无此数据。根据历史知识，XXX..."或"（根据历史知识补充）XXX"
- 使用清晰的格式组织信息"""

    response = _llm.invoke([SystemMessage(content=prompt)])
    return response.content


async def process_query(query: str) -> str:
    """基于规则匹配的查询处理"""
    query = query.strip()
    detected_name = None
    for name in ALL_CALLIGRAPHER_NAMES:
        if name in query:
            detected_name = name
            break

    # 多关键词组合查询：分别调用对应的查询函数，合并结果
    if detected_name:
        query_parts = []
        if "师承" in query or "老师" in query or "师父" in query or "跟谁学" in query:
            query_parts.append(await query_teacher_info(detected_name))
        if "影响" in query or "影响了谁" in query:
            query_parts.append(await query_influenced_info(detected_name))
        if "亲属" in query or "亲戚" in query or "家人" in query or "父亲" in query or "儿子" in query:
            query_parts.append(await query_relative_info(detected_name))
        if "字号" in query or "字什么" in query or "号什么" in query or "字、" in query or "号、" in query or query.endswith("字") or query.endswith("号"):
            query_parts.append(await query_style_name_info(detected_name))
        if "生卒" in query or "生年" in query or "卒年" in query:
            query_parts.append(await query_years_info(detected_name))
        if "朝代" in query or "哪个朝" in query or "哪个时代" in query:
            query_parts.append(await query_dynasty_info(detected_name))
        if "作品" in query or "代表作" in query:
            query_parts.append(await query_works_info(detected_name))
        if "书体" in query or "擅长" in query or "善写" in query:
            query_parts.append(await query_script_info(detected_name))
        if "流派" in query or "书派" in query or "开创" in query or "所属流派" in query:
            query_parts.append(await query_school_info(detected_name))
        if "交游" in query or "社交" in query or "人际" in query or "交游圈" in query or "关系网" in query:
            query_parts.append(await query_social_circle_info(detected_name))
        if "籍贯" in query or "哪里人" in query or "出生" in query:
            query_parts.append(await query_hometown_info(detected_name))
        if "官" in query or "职位" in query:
            query_parts.append(await query_position_info(detected_name))
        if "详细" in query or "信息" in query or "介绍" in query or "所有" in query:
            query_parts.append(await query_details(detected_name))
        # 如果匹配到了关键词，返回合并结果
        if query_parts:
            return "\n".join(query_parts)
        # 检测到名字但没有匹配任何关键词，返回详细信息
        return await query_details(detected_name)

    dynasties = ["唐代", "宋朝", "元朝", "明朝", "清朝", "汉代", "魏晋", "隋朝", "三国", "南北朝", "东晋", "西汉", "东汉"]
    dyn_simple = {"唐代": "唐", "宋朝": "宋", "元朝": "元", "明朝": "明", "清朝": "清", "汉代": "汉", "魏晋": "晋", "隋朝": "隋", "东晋": "东晋"}
    for dyn in dynasties:
        if dyn in query:
            return await query_by_dynasty(dyn_simple.get(dyn, dyn.replace("代", "").replace("朝", "")))
    for dyn in ["唐", "宋", "元", "明", "清", "汉", "晋", "隋"]:
        if dyn in query and ("书法家" in query or "有哪些" in query or "查询" in query):
            return await query_by_dynasty(dyn)

    # 按书体查询书法家
    scripts = ["草书", "楷书", "行书", "篆书", "隶书", "章草", "今草", "狂草", "魏碑", "瘦金体", "甲骨文", "金文", "飞白书", "八分书", "小篆", "大篆"]
    for script in scripts:
        if script in query and ("擅长" in query or "书法家" in query or "有哪些" in query or "谁" in query or "查询" in query):
            return await query_by_script(script)

    # 规则匹配无结果，返回None让chat端点使用LLM
    return None


async def query_teacher_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?teacher WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:learnedFrom ?t . ?t rdfs:label ?teacher . }}'
    try:
        teachers = [str(row[0]) for row in g.query(q)]
        return f"{name}的师承是：{', '.join(teachers)}" if teachers else f"抱歉，未找到{name}的师承信息"
    except:
        return f"{name}的师承需要进一步查询"


async def query_influenced_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?influenced WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:influenced ?i . ?i rdfs:label ?influenced . }}'
    try:
        influenced = [str(row[0]) for row in g.query(q)]
        return f"{name}影响了：{', '.join(influenced[:10])}" if influenced else f"抱歉，未找到受{name}影响的人物信息"
    except:
        return f"关于{name}的影响需要进一步查询"


async def query_style_name_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> SELECT ?styleName WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:styleName ?styleName . }}'
    try:
        styles = [str(row[0]) for row in g.query(q)]
        return f"{name}的字号是：{styles[0]}" if styles else f"抱歉，未找到{name}的字号信息"
    except Exception as e:
        return f"查询{name}的字号时出错：{e}"


async def query_years_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> SELECT ?birthYear ?deathYear WHERE {{ OPTIONAL {{ <http://example.org/calligraphy/calligrapher/{name}> calli:birthYear ?birthYear }} OPTIONAL {{ <http://example.org/calligraphy/calligrapher/{name}> calli:deathYear ?deathYear }} }}'
    try:
        for row in g.query(q):
            birth = str(row[0]) if row[0] else "不详"
            death = str(row[1]) if row[1] else "不详"
            if birth != "不详" or death != "不详":
                return f"{name}的生卒年是：{birth}年 - {death}年"
        return f"抱歉，未找到{name}的生卒年信息"
    except Exception as e:
        return f"查询{name}的生卒年时出错：{e}"


async def query_dynasty_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> SELECT ?dynasty WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:dynasty ?dynasty . }}'
    try:
        dynasties = [str(row[0]) for row in g.query(q)]
        return f"{name}是{dynasties[0]}人" if dynasties else f"抱歉，未找到{name}的朝代信息"
    except Exception as e:
        return f"查询{name}的朝代时出错：{e}"


async def query_works_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> SELECT ?work WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:representativeWork ?work . }}'
    try:
        works = [str(row[0]) for row in g.query(q)]
        return f"{name}的代表作品包括：{', '.join(works)}" if works else f"抱歉，未找到{name}的代表作品信息"
    except Exception as e:
        return f"查询{name}的代表作品时出错：{e}"


async def query_script_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?script WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:goodAtScript ?s . ?s rdfs:label ?script . }}'
    try:
        scripts = [str(row[0]) for row in g.query(q)]
        return f"{name}擅长的书体包括：{', '.join(scripts)}" if scripts else f"抱歉，未找到{name}擅长书体的信息"
    except Exception as e:
        return f"查询{name}的擅长书体时出错：{e}"


async def query_school_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?school WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:created ?s . ?s rdfs:label ?school . }}'
    try:
        schools = [str(row[0]) for row in g.query(q)]
        return f"{name}开创的流派：{', '.join(schools)}" if schools else f"抱歉，未找到{name}的流派信息"
    except Exception as e:
        return f"查询{name}的流派时出错：{e}"


async def query_social_circle_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?relation ?person WHERE {{{{ <http://example.org/calligraphy/calligrapher/{name}> calli:learnedFrom ?t . ?t rdfs:label ?person . BIND("师承" AS ?relation) }} UNION {{ <http://example.org/calligraphy/calligrapher/{name}> calli:influenced ?i . ?i rdfs:label ?person . BIND("影响" AS ?relation) }} UNION {{ <http://example.org/calligraphy/calligrapher/{name}> calli:relative ?r . ?r rdfs:label ?person . BIND("亲属" AS ?relation) }}}}'
    try:
        teachers, influenced, relatives = [], [], []
        for row in g.query(q):
            rel, person = str(row[0]), str(row[1])
            if rel == "师承": teachers.append(person)
            elif rel == "影响": influenced.append(person)
            elif rel == "亲属": relatives.append(person)
        parts = []
        if teachers: parts.append(f"师承：{', '.join(teachers)}")
        if influenced: parts.append(f"影响：{', '.join(influenced)}")
        if relatives: parts.append(f"亲属：{', '.join(relatives)}")
        return f"{name}的交游圈：\n" + "\n".join(parts) if parts else f"抱歉，未找到{name}的交游圈信息"
    except Exception as e:
        return f"查询{name}的交游圈时出错：{e}"


async def query_relative_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?relative WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:relative ?r . ?r rdfs:label ?relative . }}'
    try:
        relatives = [str(row[0]) for row in g.query(q)]
        return f"{name}的亲属包括：{', '.join(relatives)}" if relatives else f"抱歉，未找到{name}的亲属关系信息"
    except Exception as e:
        return f"查询{name}的亲属关系时出错：{e}"


async def query_hometown_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> SELECT ?hometown WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:hometown ?hometown . }}'
    try:
        hometowns = [str(row[0]) for row in g.query(q)]
        return f"{name}的籍贯：{hometowns[0]}" if hometowns else f"抱歉，未找到{name}的籍贯信息"
    except Exception as e:
        return f"查询{name}的籍贯时出错：{e}"


async def query_position_info(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> SELECT ?position WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> calli:position ?position . }}'
    try:
        positions = [str(row[0]) for row in g.query(q)]
        return f"{name}的官衔：{positions[0]}" if positions else f"抱歉，未找到{name}的官衔信息"
    except Exception as e:
        return f"查询{name}的官衔时出错：{e}"


async def query_by_dynasty(dynasty: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:dynasty ?dynasty . FILTER(CONTAINS(?dynasty, "{dynasty}")) }} LIMIT 30'
    try:
        names = [str(row[0]) for row in g.query(q)]
        return f"{dynasty}代书法家包括：{', '.join(names)}" if names else f"抱歉，未找到{dynasty}代书法家信息"
    except Exception as e:
        return f"查询{dynasty}代书法家时出错：{e}"


async def query_by_script(script: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:goodAtScript ?s . ?s rdfs:label ?script . FILTER(CONTAINS(?script, "{script}")) }} ORDER BY ?name'
    try:
        names = [str(row[0]) for row in g.query(q)]
        return f"擅长{script}的书法家包括（共{len(names)}人）：{'、'.join(names[:30])}" if names else f"抱歉，未找到擅长{script}的书法家信息"
    except Exception as e:
        return f"查询擅长{script}的书法家时出错：{e}"


async def query_details(name: str) -> str:
    q = f'PREFIX calli: <http://example.org/ontology/calligraphy#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?p ?o WHERE {{ <http://example.org/calligraphy/calligrapher/{name}> ?p ?o . }}'
    try:
        predicate_map = {
            "dynasty": "朝代", "birthYear": "生年", "deathYear": "卒年", "styleName": "字号",
            "hometown": "籍贯", "position": "官衔", "representativeWork": "代表作品",
            "writing": "著述", "artFeature": "艺术特色", "styleCharacteristic": "风格特征", "otherSkill": "兼习",
        }
        relation_map = {
            "learnedFrom": "师承", "influenced": "影响", "relative": "亲属",
            "goodAtScript": "擅长书体", "created": "开创",
        }
        info = []
        for row in g.query(q):
            p = str(row[0]).split("#")[-1] if "#" in str(row[0]) else str(row[0]).split("/")[-1]
            o = str(row[1])
            if p in predicate_map and o:
                info.append(f"{predicate_map[p]}：{o}")
            elif p in relation_map:
                if "calligrapher/" in o: info.append(f"{relation_map[p]}：{o.split('calligrapher/')[-1]}")
                elif "script/" in o: info.append(f"{relation_map[p]}：{o.split('script/')[-1]}")
                elif "style/" in o: info.append(f"{relation_map[p]}：{o.split('style/')[-1]}")
        return f"{name}的详细信息：\n" + "\n".join(info) if info else f"抱歉，未找到{name}的详细信息"
    except Exception as e:
        return f"查询{name}的详细信息时出错：{e}"


@app.post("/api/nl2sparql")
async def nl2sparql(request: Request):
    """自然语言转SPARQL：用户输入自然语言问题，大模型通过few-shot生成SPARQL语句并执行"""
    try:
        body = await request.json()
        query = body.get("query", "")
        if not query:
            return {"error": "请提供自然语言查询内容"}

        if not LLM_AVAILABLE or _llm is None:
            return {"error": "LLM不可用，无法生成SPARQL"}

        # 使用few-shot提示生成SPARQL
        sparql_prompt = f"""用户查询：{query}

请生成一个有效的SPARQL查询语句。

## 命名空间
PREFIX calli: <http://example.org/ontology/calligraphy#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

## 本体结构
- calli:Calligrapher: 书法家类型
- rdfs:label: 姓名
- calli:dynasty: 朝代
- calli:birthYear/deathYear: 生卒年
- calli:styleName: 字号
- calli:hometown: 籍贯
- calli:position: 官衔
- calli:representativeWork: 代表作品
- calli:learnedFrom: 师承（对象属性，指向另一个Calligrapher，表示此人师从谁）
- calli:influenced: 受影响（对象属性，指向另一个Calligrapher，表示此人受到谁影响）
- calli:relative: 亲属（对象属性，指向另一个Calligrapher）
- calli:goodAtScript: 擅长书体（对象属性，指向Script）
- calli:created: 开创（对象属性，指向InnovationStyle）
- 实体URI格式：<http://example.org/calligraphy/calligrapher/姓名>

注意关系的方向：
- 查询"XX的师承/老师"：XX calli:learnedFrom ?teacher
- 查询"XX的学生/弟子"：?student calli:learnedFrom XX（反向）
- 查询"XX受到谁影响"：XX calli:influenced ?influencer
- 查询"XX影响了谁/对后世的影响"：?influencedPerson calli:influenced XX（反向）

## 注意事项
1. 只返回SPARQL查询语句，不要包含其他解释性文字
2. 查询语句必须是完整且有效的
3. 使用UNION时，必须将所有UNION分支放在同一个WHERE花括号内，每个分支用独立的花括号包裹。绝对不能将UNION放在WHERE花括号外面。
4. 不要在URI两端添加反引号或其他引号字符
5. 用户问题包含多个维度时，必须用UNION将所有维度都包含在查询中，不能遗漏

## Few-shot示例

示例1 - 单属性查询："王羲之的师承"
SELECT ?teacher WHERE {{ <http://example.org/calligraphy/calligrapher/王羲之> calli:learnedFrom ?t . ?t rdfs:label ?teacher . }}

示例2 - FILTER条件查询："唐代书法家"
SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:dynasty ?d . FILTER(CONTAINS(?d, "唐")) }}

示例3 - 单属性查询："颜真卿的字号"
SELECT ?styleName WHERE {{ <http://example.org/calligraphy/calligrapher/颜真卿> calli:styleName ?styleName . }}

示例4 - 多条件组合查询："明代的草书书法家有哪些"
SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:dynasty ?d ; calli:goodAtScript ?s . ?s rdfs:label ?script . FILTER(CONTAINS(?d, "明") && CONTAINS(?script, "草书")) }}

示例5 - 关系反向查询："谁师从王羲之"
SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:learnedFrom <http://example.org/calligraphy/calligrapher/王羲之> . }}

示例5b - 影响反向查询："王羲之影响了谁"
SELECT ?name WHERE {{ ?c a calli:Calligrapher ; rdfs:label ?name ; calli:influenced <http://example.org/calligraphy/calligrapher/王羲之> . }}

示例6 - 多属性查询："文徵明的字号和生卒年"
SELECT ?styleName ?birthYear ?deathYear WHERE {{ <http://example.org/calligraphy/calligrapher/文徵明> calli:styleName ?styleName ; calli:birthYear ?birthYear ; calli:deathYear ?deathYear . }}

示例7 - 聚合查询："各朝代书法家数量"
SELECT ?dynasty (COUNT(?c) AS ?count) WHERE {{ ?c a calli:Calligrapher ; calli:dynasty ?dynasty . }} GROUP BY ?dynasty ORDER BY DESC(?count)

示例8 - 亲属关系查询："文徵明的亲属有哪些"
SELECT ?relative WHERE {{ <http://example.org/calligraphy/calligrapher/文徵明> calli:relative ?r . ?r rdfs:label ?relative . }}

示例9 - 交游圈查询："王羲之的交游圈"
SELECT ?relation ?person WHERE {{ {{ <http://example.org/calligraphy/calligrapher/王羲之> calli:learnedFrom ?t . ?t rdfs:label ?person . BIND("师承" AS ?relation) }} UNION {{ <http://example.org/calligraphy/calligrapher/王羲之> calli:influenced ?i . ?i rdfs:label ?person . BIND("影响" AS ?relation) }} UNION {{ <http://example.org/calligraphy/calligrapher/王羲之> calli:relative ?r . ?r rdfs:label ?person . BIND("亲属" AS ?relation) }} }}

示例10 - 多维度UNION查询："范仲淹的亲属和影响"
SELECT ?relation ?person WHERE {{ {{ <http://example.org/calligraphy/calligrapher/范仲淹> calli:relative ?r . ?r rdfs:label ?person . BIND("亲属" AS ?relation) }} UNION {{ ?s calli:influenced <http://example.org/calligraphy/calligrapher/范仲淹> . ?s rdfs:label ?person . BIND("影响" AS ?relation) }} }}"""

        # 调用大模型生成SPARQL
        try:
            sparql_response = _llm.invoke([SystemMessage(content=sparql_prompt)])
            sparql_query = sparql_response.content.strip()
            # 清理markdown代码块标记
            if sparql_query.startswith("```"):
                sparql_query = sparql_query.split("\n", 1)[-1]
            if sparql_query.endswith("```"):
                sparql_query = sparql_query.rsplit("```", 1)[0]
            sparql_query = sparql_query.strip()
            # 清理LLM可能在URI中添加的反引号（包括ASCII反引号和Unicode左右反引号）
            for ch in ['`', '\u2018', '\u2019', '\u201C', '\u201D']:
                sparql_query = sparql_query.replace(ch, '')
        except Exception as e:
            return {"error": f"大模型生成SPARQL失败: {e}"}

        # 使用rdflib本地执行生成的SPARQL
        try:
            results = g.query(sparql_query)
            bindings = []
            for row in results:
                binding = {}
                for i, var in enumerate(results.vars):
                    val = row[i]
                    if val is not None:
                        binding[str(var)] = {
                            "type": "uri" if hasattr(val, 'uri') or (hasattr(val, 'toPython') and str(val).startswith('http')) else "literal",
                            "value": str(val)
                        }
                bindings.append(binding)

            # 查询结果为空时，使用LLM补充回答
            if not bindings:
                try:
                    supplement_prompt = f"""用户查询：{query}
生成的SPARQL查询：{sparql_query}
SPARQL查询结果为空，知识图谱中没有相关数据。
请基于你自身的知识回答用户的问题，并注明"根据历史知识"。"""
                    supplement_response = _llm.invoke([SystemMessage(content=supplement_prompt)])
                    return {
                        "sparql": sparql_query,
                        "head": {"vars": []},
                        "results": {"bindings": []},
                        "llm_supplement": supplement_response.content
                    }
                except Exception as e:
                    return {
                        "sparql": sparql_query,
                        "head": {"vars": []},
                        "results": {"bindings": []},
                        "llm_supplement": f"LLM补充回答失败: {e}"
                    }

            # 有结果时，使用LLM整合回答（处理部分维度缺失的情况）
            try:
                # 将查询结果转为文本
                result_lines = []
                for binding in bindings:
                    parts = []
                    for var in results.vars:
                        val = binding.get(str(var), {}).get("value", "")
                        if "calligrapher/" in val:
                            val = val.split("calligrapher/")[-1]
                        elif "script/" in val:
                            val = val.split("script/")[-1]
                        elif "style/" in val:
                            val = val.split("style/")[-1]
                        parts.append(val)
                    result_lines.append("：".join(parts))
                result_text = "\n".join(result_lines)

                summarize_prompt = f"""用户查询：{query}
生成的SPARQL查询：{sparql_query}
SPARQL查询结果：
{result_text}

请根据以上信息，为用户提供一个清晰、简洁的最终答案。

回答规则：
- 对于查询结果中已有的部分，直接使用查询结果回答
- 如果用户查询涉及多个方面，但查询结果只覆盖了部分方面，对于缺失的部分使用你自身的知识进行补充，并标注"（根据历史知识补充）"
- 当使用自己的知识补充时，必须明确区分来源
- 使用清晰的格式组织信息"""
                summarize_response = _llm.invoke([SystemMessage(content=summarize_prompt)])
                return {
                    "sparql": sparql_query,
                    "head": {"vars": [str(v) for v in results.vars] if results.vars else []},
                    "results": {"bindings": bindings},
                    "llm_supplement": summarize_response.content
                }
            except Exception as e:
                return {
                    "sparql": sparql_query,
                    "head": {"vars": [str(v) for v in results.vars] if results.vars else []},
                    "results": {"bindings": bindings},
                    "llm_supplement": f"LLM整合回答失败: {e}"
                }
        except Exception as e:
            # SPARQL执行失败，尝试LLM补充回答
            try:
                error_prompt = f"""用户查询：{query}
生成的SPARQL查询：{sparql_query}
SPARQL执行出错：{e}
请基于你自身的知识回答用户的问题，并注明"根据历史知识"。"""
                error_response = _llm.invoke([SystemMessage(content=error_prompt)])
                return {
                    "sparql": sparql_query,
                    "sparql_error": str(e),
                    "llm_supplement": error_response.content
                }
            except Exception:
                return {
                    "sparql": sparql_query,
                    "sparql_error": str(e)
                }

    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sparql")
async def sparql_query(query: str = None):
    if not query:
        return {"message": "请提供SPARQL查询参数 'query'"}
    try:
        results = g.query(query)
        bindings = []
        for row in results:
            binding = {}
            for i, var in enumerate(results.vars):
                val = row[i]
                if val is not None:
                    binding[str(var)] = {
                        "type": "uri" if hasattr(val, 'uri') or (hasattr(val, 'toPython') and str(val).startswith('http')) else "literal",
                        "value": str(val)
                    }
            bindings.append(binding)
        return {
            "head": {"vars": [str(v) for v in results.vars] if results.vars else []},
            "results": {"bindings": bindings}
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sparql")
async def sparql_post(request: Request):
    body = await request.body()
    from urllib.parse import parse_qs
    data = parse_qs(body.decode('utf-8'))
    query = data.get('query', [None])[0]
    return await sparql_query(query)
