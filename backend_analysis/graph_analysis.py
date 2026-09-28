# -*- coding: utf-8 -*-
"""
图结构分析脚本

完成成员C的任务：
1. 流派分析（社区发现）
2. 中心性分析（影响力排名）
3. 路径分析（师承脉络）

基于PPT要求使用 NetworkX 进行图分析
"""

import os
import networkx as nx
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS
import pandas as pd
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib
import json
from pathlib import Path

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# =========================================================
# 配置
# =========================================================
INPUT_TTL = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend_qa', 'calligraphy_kg.ttl'))
OUTPUT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR.mkdir(exist_ok=True)

# 命名空间
CALLI = Namespace("http://example.org/ontology/calligraphy#")
CALLIGRAPHER = Namespace("http://example.org/calligraphy/calligrapher/")

# =========================================================
# 1. 从TTL构建NetworkX图
# =========================================================
def build_networkx_graph():
    """从TTL文件构建NetworkX图"""
    print("=" * 60)
    print("1. 构建人物关系图")
    print("=" * 60)
    
    # 读取TTL
    g = Graph()
    g.parse(INPUT_TTL, format="turtle")
    print(f"读取TTL: {len(g)} 条三元组")
    
    # 创建有向图（师承、影响关系有方向）
    G = nx.DiGraph()
    
    # 提取所有书法家
    calligraphers = set()
    for s, p, o in g.triples((None, None, None)):
        if str(s).startswith("http://example.org/calligraphy/calligrapher/"):
            calligraphers.add(str(s))
        if str(o).startswith("http://example.org/calligraphy/calligrapher/"):
            calligraphers.add(str(o))
    
    print(f"找到 {len(calligraphers)} 位书法家")
    
    # 添加节点
    name_map = {}
    for c in calligraphers:
        # 获取姓名
        name = c.split("/")[-1]
        for label in g.objects(URIRef(c), RDFS.label):
            name = str(label)
            break
        name_map[c] = name
        G.add_node(c, name=name)
    
    # 提取师承关系 (learnedFrom)
    learned_edges = []
    for s, p, o in g.triples((None, CALLI.learnedFrom, None)):
        if str(s) in calligraphers and str(o) in calligraphers:
            learned_edges.append((str(s), str(o)))
            G.add_edge(str(s), str(o), relation="learnedFrom")
    print(f"师承关系: {len(learned_edges)} 条")
    
    # 提取影响关系 (influenced)
    influenced_edges = []
    for s, p, o in g.triples((None, CALLI.influenced, None)):
        if str(s) in calligraphers and str(o) in calligraphers:
            influenced_edges.append((str(s), str(o)))
            G.add_edge(str(s), str(o), relation="influenced")
    print(f"影响关系: {len(influenced_edges)} 条")
    
    # 提取亲属关系 (relative)
    relative_edges = []
    for s, p, o in g.triples((None, CALLI.relative, None)):
        if str(s) in calligraphers and str(o) in calligraphers:
            relative_edges.append((str(s), str(o)))
            G.add_edge(str(s), str(o), relation="relative")
    print(f"亲属关系: {len(relative_edges)} 条")
    
    print(f"\n图统计:")
    print(f"  节点数: {G.number_of_nodes()}")
    print(f"  边数: {G.number_of_edges()}")
    
    return G, name_map, g

# =========================================================
# 2. 流派分析（按书体分类 + 朝代细分）
# =========================================================
SCRIPT = Namespace("http://example.org/calligraphy/script/")

# 朝代排序（按时间顺序）
DYNASTY_ORDER = [
    "汉", "西汉", "东汉", "三国", "晋", "西晋", "东晋",
    "南北朝", "南朝", "北朝", "隋", "唐",
    "五代", "宋", "北宋", "南宋", "元", "明", "清",
    "近代", "现代"
]

def normalize_dynasty(dynasty):
    """标准化朝代名称"""
    if not dynasty:
        return "未知"
    dynasty = str(dynasty).strip()
    # 统一朝代名称
    dynasty_map = {
        "西漢": "西汉", "東漢": "东汉", "漢": "汉",
        "西晉": "西晋", "東晉": "东晋", "晉": "晋",
        "三國": "三国", "南朝宋": "南朝", "南朝梁": "南朝",
    }
    return dynasty_map.get(dynasty, dynasty)

def analyze_schools(G, name_map, rdf_graph):
    """流派分析 - 按书体类型分类，并按朝代细分"""
    print("\n" + "=" * 60)
    print("2. 流派分析（按书体分类 + 朝代细分）")
    print("=" * 60)
    
    # 书体大类映射
    script_categories = {
        "楷书派": ["楷书", "魏碑", "瘦金体"],
        "行书派": ["行书"],
        "草书派": ["草书", "章草", "狂草", "今草"],
        "隶书派": ["隶书", "八分书"],
        "篆书派": ["篆书", "小篆", "大篆", "甲骨文", "石鼓文", "金文"],
        "行草派": ["行草"],
        "飞白派": ["飞白书"],
    }
    
    # 从RDF图提取每个书法家的擅长书体和朝代
    calligrapher_scripts = defaultdict(set)
    calligrapher_dynasty = {}
    
    for s, p, o in rdf_graph.triples((None, CALLI.goodAtScript, None)):
        s_str = str(s)
        o_str = str(o)
        if s_str.startswith("http://example.org/calligraphy/calligrapher/"):
            script_name = o_str.split("/")[-1]
            calligrapher_scripts[s_str].add(script_name)
    
    for s, p, o in rdf_graph.triples((None, CALLI.dynasty, None)):
        s_str = str(s)
        if s_str.startswith("http://example.org/calligraphy/calligrapher/"):
            calligrapher_dynasty[s_str] = normalize_dynasty(str(o))
    
    print(f"找到 {len(calligrapher_scripts)} 位有书体记录的书法家")
    print(f"找到 {len(calligrapher_dynasty)} 位有朝代记录的书法家")
    
    # 按书体大类分组，并记录朝代信息
    script_members = defaultdict(list)  # {流派: [(姓名, 书体, 朝代)]}
    
    for calligrapher_uri, scripts in calligrapher_scripts.items():
        name = name_map.get(calligrapher_uri, calligrapher_uri.split("/")[-1])
        dynasty = calligrapher_dynasty.get(calligrapher_uri, "未知")
        
        for script in scripts:
            # 找到对应的大类
            for category, script_list in script_categories.items():
                if script in script_list:
                    script_members[category].append((name, script, dynasty))
                    break
            else:
                # 未分类的书体，单独处理
                script_members[f"{script}派"].append((name, script, dynasty))
    
    # 统计结果（包含朝代细分）
    results = []
    for script_type in sorted(script_members.keys(), key=lambda x: len(script_members[x]), reverse=True):
        members = script_members[script_type]
        
        # 按朝代细分
        dynasty_groups = defaultdict(list)
        for m in members:
            dynasty_groups[m[2]].append(m[0])
        
        # 唯一化每个朝代的成员
        dynasty_unique = {}
        for dynasty, names in dynasty_groups.items():
            dynasty_unique[dynasty] = list(set(names))
        
        # 书体细分
        script_detail = defaultdict(int)
        for m in members:
            script_detail[m[1]] += 1
        
        # 总人数（去重）
        all_names = list(set([m[0] for m in members]))
        
        # 按时间顺序排列朝代
        sorted_dynasties = []
        for d in DYNASTY_ORDER:
            if d in dynasty_unique:
                sorted_dynasties.append((d, dynasty_unique[d]))
        # 其他朝代
        for d in dynasty_unique:
            if d not in DYNASTY_ORDER:
                sorted_dynasties.append((d, dynasty_unique[d]))
        
        results.append({
            "流派名称": script_type,
            "总人数": len(all_names),
            "书体分布": dict(script_detail),
            "朝代细分": sorted_dynasties,
            "代表人物": all_names[:5],
            "成员列表": sorted(all_names)
        })
    
    # 保存详细结果
    output_data = []
    for r in results:
        # 朝代细分字符串
        dynasty_str = "; ".join([f"{d}({len(names)}人)" for d, names in r["朝代细分"]])
        output_data.append({
            "流派名称": r["流派名称"],
            "总人数": r["总人数"],
            "书体分布": "; ".join([f"{k}({v}人)" for k, v in r["书体分布"].items()]),
            "朝代细分": dynasty_str,
            "代表人物": "; ".join(r["代表人物"]),
            "成员列表": "; ".join(r["成员列表"][:20]) + ("..." if len(r["成员列表"]) > 20 else "")
        })
    
    df = pd.DataFrame(output_data)
    df.to_csv(OUTPUT_DIR / "school_analysis.csv", index=False, encoding="utf-8-sig")
    print(f"\n已保存: {OUTPUT_DIR / 'school_analysis.csv'}")
    
    # 保存朝代细分详细表
    detail_data = []
    for r in results:
        for dynasty, names in r["朝代细分"]:
            detail_data.append({
                "流派": r["流派名称"],
                "朝代": dynasty,
                "人数": len(names),
                "代表人物": "; ".join(names[:5]),
                "成员": "; ".join(sorted(names)[:10]) + ("..." if len(names) > 10 else "")
            })
    
    detail_df = pd.DataFrame(detail_data)
    detail_df.to_csv(OUTPUT_DIR / "school_dynasty_detail.csv", index=False, encoding="utf-8-sig")
    print(f"已保存: {OUTPUT_DIR / 'school_dynasty_detail.csv'}")
    
    # 显示流派统计（含朝代细分）
    print("\n书体流派分布（含朝代细分）:")
    for r in results[:8]:  # 只显示前8个主要流派
        print(f"\n  {r['流派名称']}: {r['总人数']}人")
        detail_str = ", ".join([f"{k}({v})" for k, v in r['书体分布'].items()])
        print(f"    书体分布: {detail_str}")
        dynasty_str = ", ".join([f"{d}({len(names)})" for d, names in r['朝代细分'][:6]])
        print(f"    朝代细分: {dynasty_str}")
    
    return results

# =========================================================
# 3. 中心性分析
# =========================================================
def analyze_centrality(G, name_map):
    """中心性分析 - 计算影响力指标"""
    print("\n" + "=" * 60)
    print("3. 中心性分析（影响力排名）")
    print("=" * 60)
    
    # 转换为无向图计算中心性
    G_undirected = G.to_undirected()
    
    # 计算三种中心性指标
    print("计算度中心性...")
    degree_centrality = nx.degree_centrality(G_undirected)
    
    print("计算介数中心性...")
    betweenness_centrality = nx.betweenness_centrality(G_undirected)
    
    print("计算接近中心性...")
    closeness_centrality = nx.closeness_centrality(G_undirected)
    
    # 合并结果
    results = []
    for node in G.nodes():
        name = name_map.get(node, node.split("/")[-1])
        results.append({
            "name": name,
            "degree_centrality": round(degree_centrality.get(node, 0), 6),
            "betweenness_centrality": round(betweenness_centrality.get(node, 0), 6),
            "closeness_centrality": round(closeness_centrality.get(node, 0), 6),
        })
    
    df = pd.DataFrame(results)
    
    # 计算综合得分
    df["综合得分"] = (
        df["degree_centrality"] * 0.4 +
        df["betweenness_centrality"] * 0.3 +
        df["closeness_centrality"] * 0.3
    )
    
    # 按综合得分排序
    df = df.sort_values("综合得分", ascending=False)
    
    # 添加排名
    df["排名"] = range(1, len(df) + 1)
    df = df[["排名", "name", "degree_centrality", "betweenness_centrality", "closeness_centrality", "综合得分"]]
    
    # 保存结果
    df.to_csv(OUTPUT_DIR / "centrality_analysis.csv", index=False, encoding="utf-8-sig")
    print(f"\n已保存: {OUTPUT_DIR / 'centrality_analysis.csv'}")
    
    # 显示Top 10
    print("\n影响力人物 Top 10:")
    for _, row in df.head(10).iterrows():
        print(f"  {row['排名']}. {row['name']}")
        print(f"     度中心性: {row['degree_centrality']:.4f}, 介数: {row['betweenness_centrality']:.4f}, 接近: {row['closeness_centrality']:.4f}")
    
    return df

# =========================================================
# 4. 路径分析
# =========================================================
def analyze_paths(G, name_map):
    """路径分析 - 师承脉络"""
    print("\n" + "=" * 60)
    print("4. 路径分析（师承脉络）")
    print("=" * 60)
    
    # 创建反向映射
    name_to_uri = {v: k for k, v in name_map.items()}
    
    # 定义一些示例路径查询
    examples = [
        ("王羲之", "王献之"),  # 父子
        ("王羲之", "智永"),    # 师承脉络
        ("钟繇", "颜真卿"),    # 跨朝代
        ("张芝", "王羲之"),    # 师承
    ]
    
    results = []
    
    for source_name, target_name in examples:
        source = name_to_uri.get(source_name)
        target = name_to_uri.get(target_name)
        
        if not source or not target:
            print(f"\n{source_name} → {target_name}: 未找到节点")
            continue
        
        if source not in G.nodes() or target not in G.nodes():
            print(f"\n{source_name} → {target_name}: 节点不在图中")
            continue
        
        print(f"\n{source_name} → {target_name}:")
        
        try:
            # BFS 最短路径
            path = nx.shortest_path(G, source, target)
            path_names = [name_map.get(n, n.split("/")[-1]) for n in path]
            path_str = " → ".join(path_names)
            print(f"  最短路径: {path_str}")
            print(f"  路径长度: {len(path) - 1}")
            
            results.append({
                "source": source_name,
                "target": target_name,
                "path": path_str,
                "length": len(path) - 1,
                "status": "找到"
            })
        except nx.NetworkXNoPath:
            print(f"  无路径")
            results.append({
                "source": source_name,
                "target": target_name,
                "path": "无路径",
                "length": -1,
                "status": "无路径"
            })
        except nx.NodeNotFound as e:
            print(f"  节点不存在: {e}")
            results.append({
                "source": source_name,
                "target": target_name,
                "path": "节点不存在",
                "length": -1,
                "status": "节点不存在"
            })
    
    # 保存结果
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_DIR / "path_analysis.csv", index=False, encoding="utf-8-sig")
    print(f"\n已保存: {OUTPUT_DIR / 'path_analysis.csv'}")
    
    return results

# =========================================================
# 5. 生成可视化图表
# =========================================================
def generate_visualization(G, name_map, centrality_df, rdf_graph):
    """生成可视化图表"""
    print("\n" + "=" * 60)
    print("5. 生成可视化图表")
    print("=" * 60)
    
    # 创建反向映射
    name_to_uri = {v: k for k, v in name_map.items()}
    
    # ===== 图1: Top 100影响力人物网络 =====
    print("\n生成影响力人物网络图...")
    top_names = centrality_df.head(100)["name"].tolist()
    top_nodes = [name_to_uri.get(n) for n in top_names if name_to_uri.get(n) in G.nodes()]
    subgraph = G.subgraph(top_nodes)
    
    plt.figure(figsize=(24, 20))
    subgraph_undirected = subgraph.to_undirected()
    
    # 使用更好的布局算法
    pos = nx.spring_layout(subgraph_undirected, k=2.5, iterations=80, seed=42)
    
    # 节点大小根据度中心性（调整比例）
    degrees = dict(subgraph.degree())
    max_deg = max(degrees.values()) if degrees else 1
    node_sizes = [150 + (degrees.get(n, 1) / max_deg) * 600 for n in subgraph_undirected.nodes()]
    
    # 节点颜色根据综合得分
    scores = {}
    for n in subgraph_undirected.nodes():
        name = name_map.get(n, n.split("/")[-1])
        score_row = centrality_df[centrality_df["name"] == name]
        if len(score_row) > 0:
            scores[n] = score_row["综合得分"].values[0]
        else:
            scores[n] = 0
    
    # 颜色映射：得分越高颜色越深
    max_score = max(scores.values()) if scores else 1
    node_colors = [plt.cm.Blues(0.3 + 0.7 * (scores.get(n, 0) / max_score)) for n in subgraph_undirected.nodes()]
    
    labels = {n: name_map.get(n, n.split("/")[-1]) for n in subgraph_undirected.nodes()}
    
    nx.draw_networkx_nodes(subgraph_undirected, pos, node_size=node_sizes, 
                           node_color=node_colors, alpha=0.85)
    nx.draw_networkx_labels(subgraph_undirected, pos, labels, font_size=6, font_weight='bold')
    nx.draw_networkx_edges(subgraph_undirected, pos, alpha=0.15, arrows=False, width=0.3)
    
    plt.title("书法家关系网络（Top 100影响力人物）", fontsize=20, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "network_visualization_top100.png", dpi=150, bbox_inches='tight')
    print(f"已保存: {OUTPUT_DIR / 'network_visualization_top100.png'}")
    plt.close()
    
    # ===== 图2: 按书体流派分类的网络图 =====
    print("\n生成书体流派网络图...")
    
    # 提取书体信息
    calligrapher_scripts = defaultdict(set)
    for s, p, o in rdf_graph.triples((None, CALLI.goodAtScript, None)):
        s_str = str(s)
        o_str = str(o)
        if s_str.startswith("http://example.org/calligraphy/calligrapher/"):
            script_name = o_str.split("/")[-1]
            calligrapher_scripts[s_str].add(script_name)
    
    # 书体大类映射
    script_categories = {
        "楷书": ["楷书", "魏碑", "瘦金体"],
        "行书": ["行书"],
        "草书": ["草书", "章草", "狂草", "今草"],
        "隶书": ["隶书", "八分书"],
        "篆书": ["篆书", "小篆", "大篆", "甲骨文", "石鼓文", "金文"],
        "行草": ["行草"],
    }
    
    # 为每个书法家分配主要书体颜色
    script_colors = {
        "楷书": "#E74C3C",  # 红色
        "行书": "#3498DB",  # 蓝色
        "草书": "#2ECC71",  # 绿色
        "隶书": "#F39C12",  # 橙色
        "篆书": "#9B59B6",  # 紫色
        "行草": "#1ABC9C",  # 青色
    }
    
    # 取Top 150人物，按书体分类
    top150_names = centrality_df.head(150)["name"].tolist()
    top150_nodes = [name_to_uri.get(n) for n in top150_names if name_to_uri.get(n) in G.nodes()]
    
    # 确定每个节点的主要书体
    node_script = {}
    for n in top150_nodes:
        scripts = calligrapher_scripts.get(n, set())
        # 找到第一个匹配的大类
        for category, script_list in script_categories.items():
            if any(s in script_list for s in scripts):
                node_script[n] = category
                break
        if n not in node_script:
            node_script[n] = "行书"  # 默认
    
    subgraph2 = G.subgraph(top150_nodes)
    plt.figure(figsize=(28, 22))
    subgraph2_undirected = subgraph2.to_undirected()
    
    pos2 = nx.spring_layout(subgraph2_undirected, k=2, iterations=60, seed=123)
    
    # 节点大小
    degrees2 = dict(subgraph2.degree())
    max_deg2 = max(degrees2.values()) if degrees2 else 1
    node_sizes2 = [120 + (degrees2.get(n, 1) / max_deg2) * 500 for n in subgraph2_undirected.nodes()]
    
    # 节点颜色按书体
    node_colors2 = [script_colors.get(node_script.get(n, "行书"), "#95A5A6") for n in subgraph2_undirected.nodes()]
    
    labels2 = {n: name_map.get(n, n.split("/")[-1]) for n in subgraph2_undirected.nodes()}
    
    nx.draw_networkx_nodes(subgraph2_undirected, pos2, node_size=node_sizes2, 
                           node_color=node_colors2, alpha=0.75)
    nx.draw_networkx_labels(subgraph2_undirected, pos2, labels2, font_size=5)
    nx.draw_networkx_edges(subgraph2_undirected, pos2, alpha=0.12, arrows=False, width=0.2)
    
    # 添加图例
    legend_elements = [plt.scatter([], [], c=color, s=100, label=script) 
                       for script, color in script_colors.items()]
    plt.legend(handles=legend_elements, loc='upper right', fontsize=12, title="书体流派")
    
    plt.title("书法家关系网络（Top 150，按书体分类）", fontsize=22, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "network_visualization_by_script.png", dpi=150, bbox_inches='tight')
    print(f"已保存: {OUTPUT_DIR / 'network_visualization_by_script.png'}")
    plt.close()
    
    # ===== 图3: 中心性柱状图（扩展到Top 20） =====
    print("\n生成中心性对比图...")
    plt.figure(figsize=(16, 10))
    top_20 = centrality_df.head(20)
    x = range(len(top_20))
    
    plt.bar(x, top_20["degree_centrality"], width=0.25, label="度中心性", color='steelblue')
    plt.bar([i + 0.25 for i in x], top_20["betweenness_centrality"], width=0.25, label="介数中心性", color='coral')
    plt.bar([i + 0.5 for i in x], top_20["closeness_centrality"], width=0.25, label="接近中心性", color='green')
    
    plt.xticks([i + 0.25 for i in x], top_20["name"], rotation=45, ha='right', fontsize=10)
    plt.xlabel("书法家", fontsize=12)
    plt.ylabel("中心性值", fontsize=12)
    plt.title("影响力Top 20中心性指标对比", fontsize=16, fontweight='bold')
    plt.legend(fontsize=11)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "centrality_chart_top20.png", dpi=150, bbox_inches='tight')
    print(f"已保存: {OUTPUT_DIR / 'centrality_chart_top20.png'}")
    plt.close()
    
    # ===== 图4: 按朝代分布的网络图 =====
    print("\n生成朝代分布网络图...")
    
    # 提取朝代信息
    calligrapher_dynasty = {}
    for s, p, o in rdf_graph.triples((None, CALLI.dynasty, None)):
        s_str = str(s)
        if s_str.startswith("http://example.org/calligraphy/calligrapher/"):
            dynasty = str(o).strip()
            # 简化朝代分类
            if dynasty in ["汉", "西汉", "东汉", "三国", "晋", "西晋", "东晋", "南北朝"]:
                dynasty_group = "汉晋南北朝"
            elif dynasty in ["隋", "唐", "五代"]:
                dynasty_group = "隋唐五代"
            elif dynasty in ["宋", "北宋", "南宋"]:
                dynasty_group = "宋"
            elif dynasty == "元":
                dynasty_group = "元"
            elif dynasty == "明":
                dynasty_group = "明"
            elif dynasty == "清":
                dynasty_group = "清"
            elif dynasty in ["现代", "近代"]:
                dynasty_group = "现代"
            else:
                dynasty_group = "其他"
            calligrapher_dynasty[s_str] = dynasty_group
    
    # 朝代颜色
    dynasty_colors = {
        "汉晋南北朝": "#8B4513",  # 棕色
        "隋唐五代": "#DAA520",   # 金色
        "宋": "#4169E1",         # 皇家蓝
        "元": "#2F4F4F",         # 深灰
        "明": "#DC143C",         # 深红
        "清": "#006400",         # 深绿
        "现代": "#708090",       # 灰色
        "其他": "#A9A9A9",       # 浅灰
    }
    
    # 确定每个节点的朝代
    node_dynasty = {}
    for n in top150_nodes:
        dynasty = calligrapher_dynasty.get(n, "其他")
        node_dynasty[n] = dynasty
    
    plt.figure(figsize=(28, 22))
    
    node_colors3 = [dynasty_colors.get(node_dynasty.get(n, "其他"), "#A9A9A9") for n in subgraph2_undirected.nodes()]
    
    nx.draw_networkx_nodes(subgraph2_undirected, pos2, node_size=node_sizes2, 
                           node_color=node_colors3, alpha=0.75)
    nx.draw_networkx_labels(subgraph2_undirected, pos2, labels2, font_size=5)
    nx.draw_networkx_edges(subgraph2_undirected, pos2, alpha=0.12, arrows=False, width=0.2)
    
    # 添加图例
    legend_elements2 = [plt.scatter([], [], c=color, s=100, label=dynasty) 
                        for dynasty, color in dynasty_colors.items()]
    plt.legend(handles=legend_elements2, loc='upper right', fontsize=12, title="朝代")
    
    plt.title("书法家关系网络（Top 150，按朝代分类）", fontsize=22, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "network_visualization_by_dynasty.png", dpi=150, bbox_inches='tight')
    print(f"已保存: {OUTPUT_DIR / 'network_visualization_by_dynasty.png'}")
    plt.close()
    
    # ===== 图5: 关系类型网络图（区分师承、影响、亲属） =====
    print("\n生成关系类型网络图...")
    
    # 取Top 200人物，显示完整关系网络
    top200_names = centrality_df.head(200)["name"].tolist()
    top200_nodes = [name_to_uri.get(n) for n in top200_names if name_to_uri.get(n) in G.nodes()]
    
    # 创建包含所有关系类型的子图
    subgraph3 = G.subgraph(top200_nodes)
    
    plt.figure(figsize=(32, 26))
    
    # 使用kamada-kawai布局（更适合显示关系结构）
    subgraph3_undirected = subgraph3.to_undirected()
    
    # 计算布局
    try:
        pos3 = nx.kamada_kawai_layout(subgraph3_undirected)
    except:
        pos3 = nx.spring_layout(subgraph3_undirected, k=1.5, iterations=50, seed=456)
    
    # 节点大小和颜色
    degrees3 = dict(subgraph3.degree())
    max_deg3 = max(degrees3.values()) if degrees3 else 1
    node_sizes3 = [100 + (degrees3.get(n, 1) / max_deg3) * 400 for n in subgraph3_undirected.nodes()]
    
    # 节点颜色（统一使用浅蓝色）
    node_colors3 = '#A8D8EA'
    
    labels3 = {n: name_map.get(n, n.split("/")[-1]) for n in subgraph3_undirected.nodes()}
    
    # 绘制节点
    nx.draw_networkx_nodes(subgraph3_undirected, pos3, node_size=node_sizes3, 
                           node_color=node_colors3, alpha=0.8)
    nx.draw_networkx_labels(subgraph3_undirected, pos3, labels3, font_size=5)
    
    # 分别绘制不同类型的边（用不同颜色）
    # 师承关系 - 蓝色
    learned_edges = [(u, v) for u, v, d in subgraph3.edges(data=True) if d.get('relation') == 'learnedFrom']
    nx.draw_networkx_edges(subgraph3_undirected, pos3, edgelist=learned_edges, 
                           edge_color='#3498DB', alpha=0.6, width=1.5, arrows=False,
                           style='solid')
    
    # 影响关系 - 绿色
    influenced_edges = [(u, v) for u, v, d in subgraph3.edges(data=True) if d.get('relation') == 'influenced']
    nx.draw_networkx_edges(subgraph3_undirected, pos3, edgelist=influenced_edges, 
                           edge_color='#2ECC71', alpha=0.5, width=1.0, arrows=False,
                           style='dashed')
    
    # 亲属关系 - 红色
    relative_edges = [(u, v) for u, v, d in subgraph3.edges(data=True) if d.get('relation') == 'relative']
    nx.draw_networkx_edges(subgraph3_undirected, pos3, edgelist=relative_edges, 
                           edge_color='#E74C3C', alpha=0.7, width=2.0, arrows=False,
                           style='solid')
    
    # 添加图例（用线段表示）
    from matplotlib.lines import Line2D
    legend_lines = [
        Line2D([0], [0], color='#3498DB', linewidth=2, label='师承关系 (learnedFrom)'),
        Line2D([0], [0], color='#2ECC71', linewidth=2, linestyle='dashed', label='影响关系 (influenced)'),
        Line2D([0], [0], color='#E74C3C', linewidth=2, label='亲属关系 (relative)'),
    ]
    plt.legend(handles=legend_lines, loc='upper right', fontsize=14, title="关系类型", title_fontsize=14)
    
    # 添加统计信息
    stats_text = f"节点数: {subgraph3.number_of_nodes()}\n师承关系: {len(learned_edges)}条\n影响关系: {len(influenced_edges)}条\n亲属关系: {len(relative_edges)}条"
    plt.text(0.02, 0.02, stats_text, transform=plt.gca().transAxes, fontsize=12,
             verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.title("书法家关系网络（Top 200，区分关系类型）", fontsize=24, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "network_visualization_by_relation.png", dpi=150, bbox_inches='tight')
    print(f"已保存: {OUTPUT_DIR / 'network_visualization_by_relation.png'}")
    print(f"  - 包含 {subgraph3.number_of_nodes()} 位书法家")
    print(f"  - 师承关系: {len(learned_edges)} 条")
    print(f"  - 影响关系: {len(influenced_edges)} 条")
    print(f"  - 亲属关系: {len(relative_edges)} 条")
    plt.close()

# =========================================================
# 主函数
# =========================================================
def main():
    print("=" * 60)
    print("图结构分析")
    print("=" * 60)
    
    # 1. 构建图
    G, name_map, rdf_graph = build_networkx_graph()
    
    # 2. 流派分析（按书体分类）
    school_results = analyze_schools(G, name_map, rdf_graph)
    
    # 3. 中心性分析
    centrality_df = analyze_centrality(G, name_map)
    
    # 4. 路径分析
    path_results = analyze_paths(G, name_map)
    
    # 5. 可视化（扩展版）
    generate_visualization(G, name_map, centrality_df, rdf_graph)
    
    # 总结
    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  - {OUTPUT_DIR / 'school_analysis.csv'}")
    print(f"  - {OUTPUT_DIR / 'school_dynasty_detail.csv'}")
    print(f"  - {OUTPUT_DIR / 'centrality_analysis.csv'}")
    print(f"  - {OUTPUT_DIR / 'path_analysis.csv'}")
    print(f"  - {OUTPUT_DIR / 'network_visualization_top100.png'}")
    print(f"  - {OUTPUT_DIR / 'network_visualization_by_script.png'}")
    print(f"  - {OUTPUT_DIR / 'network_visualization_by_dynasty.png'}")
    print(f"  - {OUTPUT_DIR / 'network_visualization_by_relation.png'}")
    print(f"  - {OUTPUT_DIR / 'centrality_chart_top20.png'}")

if __name__ == "__main__":
    main()
