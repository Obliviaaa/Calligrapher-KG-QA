#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用langgraph创建的中国书法家知识图谱查询Agent

工作流设计：
START → route_question → (tool | sparql | direct)
  tool → call_tool → tool_node → should_continue → (final_answer | generate_sparql)
  sparql → generate_sparql → execute_sparql → final_answer
  direct → final_answer

1. route_question: LLM决定路径
   - "tool": 可以通过本地工具回答
   - "sparql": 需要复杂SPARQL生成（跨实体、统计、多条件）
   - "direct": LLM直接回答（无需KG）

2. call_tool: LLM使用bind_tools选择工具和参数（无硬编码实体识别）

3. should_continue_after_tool: 任何工具返回空/失败 → 尝试generate_sparql兜底；否则→final_answer

4. generate_sparql: LLM生成SPARQL查询，清理反引号，包含完整本体描述

5. execute_sparql: 执行SPARQL查询，空结果返回"SPARQL查询返回空结果"

6. final_answer: 三种策略
   - has_partial_failure: 部分有结果+部分空 → KG结果回答已有部分，LLM补充缺失部分，注明来源
   - has_valid_result: 全部有效 → 仅基于KG结果回答
   - 无有效结果 → LLM自身知识回答，注明非KG来源
"""

from typing import Annotated, Sequence, TypedDict, Optional
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

from utils import setup_llm

# 导入rdf_tool.py中的所有工具
from rdf_tool import (
    query_all_calligraphers,
    query_calligraphers_by_dynasty,
    query_calli_details,
    query_style_name,
    query_hometown,
    query_dynasty,
    query_teacher_of,
    query_influenced_by,
    query_influenced_on,
    query_representative_works,
    query_art_feature,
    query_writings,
    query_position,
    query_other_skill,
    query_relatives,
    query_students_of,
    query_calligraphers_by_script,
    query_birth_death_year,
    query_social_circle,
    query_school,
    execute_custom_sparql_query,
)

# 20个查询工具列表（不含execute_custom_sparql_query）
tools = [
    query_all_calligraphers,
    query_calligraphers_by_dynasty,
    query_calli_details,
    query_style_name,
    query_hometown,
    query_dynasty,
    query_teacher_of,
    query_influenced_by,
    query_influenced_on,
    query_representative_works,
    query_art_feature,
    query_writings,
    query_position,
    query_other_skill,
    query_relatives,
    query_students_of,
    query_calligraphers_by_script,
    query_birth_death_year,
    query_social_circle,
    query_school,
]

# 全局LLM实例
llm = None


class AgentState(TypedDict):
    """Agent状态"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_node: Optional[str]
    sparql_query: Optional[str]


def route_question(state: AgentState):
    """
    解析用户问题，决定走哪条路径：
    - "tool": 可以通过本地工具直接回答
    - "sparql": 需要生成SPARQL查询（工具不足以回答的复杂查询）
    - "direct": LLM直接回答（无需查询知识图谱）
    """
    print("route_question", flush=True)

    # 获取用户最新的查询
    user_query = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    if not user_query:
        return {"messages": [AIMessage(content="未收到有效的用户查询")], "next_node": "direct"}

    # 让LLM根据用户问题决定路径
    route_prompt = f"""你是一个路由决策助手。根据用户的查询，决定应该走哪条处理路径。

用户查询：{user_query}

可选路径：
1. "tool" - 用户的问题可以通过调用本地查询工具直接回答。
   适用场景：查询某位书法家的具体信息（如字号、籍贯、朝代、师承、代表作品、艺术特色、擅长书体、生卒年、亲属、影响等）、
   查询某个朝代的书法家列表、查询所有书法家、查询某位书法家的学生、查询书法家创造的书法风格等。
   只要是关于知识图谱中已有数据的单实体查询，都应该选择"tool"。
   **重要**：凡是涉及特定书法家的属性、关系、影响的查询，无论措辞如何（如"XX的影响"、"XX对后世的影响"、"XX的成就"），都必须选择"tool"，因为知识图谱中可能包含相关数据。

2. "sparql" - 用户的问题比较复杂，需要生成SPARQL查询语句才能回答。
   适用场景：跨实体关联查询（如"哪些书法家师从同一位老师"）、
   统计分析（如"哪个朝代书法家最多"）、多条件组合查询（如"唐代的书法家谁影响了最多人"）、
   或需要查询知识图谱中不直接对应某个工具的复杂关系。

3. "direct" - 用户的问题不需要查询知识图谱，LLM可以直接回答。
   适用场景：闲聊、关于书法的一般性知识问题、与知识图谱数据无关的问题。
   **注意**：只要用户提到了特定书法家的名字，就不应该选择"direct"，因为很可能需要查询知识图谱中的数据。

请仅返回路径名称：tool、sparql 或 direct"""

    response = llm.invoke([
        SystemMessage(content=route_prompt),
        HumanMessage(content=user_query)
    ])

    next_node = response.content.strip().lower().strip('"').strip("'")
    # 确保返回的是有效路径
    if next_node not in ["tool", "sparql", "direct"]:
        next_node = "tool"  # 默认走工具路径

    print("route_question →", next_node, flush=True)
    return {"messages": [response], "next_node": next_node}


def call_tool(state: AgentState):
    """
    LLM根据用户问题选择合适的工具并生成调用参数。
    使用bind_tools让LLM直接看到工具的schema，自主选择工具和参数。
    """
    print("call_tool", flush=True)

    # 获取用户最新的查询
    user_query = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    if not user_query:
        return {"messages": [AIMessage(content="未收到有效的用户查询")], "next_node": "direct"}

    # 使用绑定了工具的LLM，让LLM自主选择工具和参数
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke([
        SystemMessage(content="""你是一个知识图谱查询助手。请根据用户的问题，选择最合适的工具进行查询。

重要规则：
1. 优先选择精确匹配的工具，而不是笼统的详情查询。例如：
   - 用户问"交游圈/社交圈/人际网络" → 用 query_social_circle，不要用 query_calli_details
   - 用户问"师承/老师" → 用 query_teacher_of
   - 用户问"学生/弟子" → 用 query_students_of
   - 用户问"亲属/家人" → 用 query_relatives
   - 用户问"受到谁影响/受谁影响" → 用 query_influenced_by
   - 用户问"影响了谁/对后世的影响/对XX的影响" → 用 query_influenced_on
   - 用户问"影响"（未明确方向） → 同时用 query_influenced_by 和 query_influenced_on
   - 用户问"流派/书派" → 用 query_school
2. 只有当用户确实想了解书法家的全面信息时，才使用 query_calli_details。
3. 如果用户问题涉及多个方面，必须选择所有相关的工具，不能遗漏任何一个方面。
   例如"范仲淹的亲属和影响" → 必须同时选择 query_relatives 和 query_influenced_on（或 query_influenced_by）。
   例如"王羲之的师承和代表作品" → 必须同时选择 query_teacher_of 和 query_representative_works。
4. 注意区分"受影响"和"影响别人"的方向：
   - query_influenced_by 查的是"此人受到谁影响"（入边）
   - query_influenced_on 查的是"此人影响了谁"（出边）
   用户问"XX的影响"或"XX对后世的影响"时，应该用 query_influenced_on。"""),
        HumanMessage(content=user_query)
    ])

    if hasattr(response, 'tool_calls') and response.tool_calls:
        print("工具调用请求：", response.tool_calls, flush=True)
    else:
        print("未生成工具调用请求，将直接回答", flush=True)

    return {"messages": [response]}


def should_continue_after_tool(state: AgentState) -> str:
    """
    工具执行后，判断是否需要继续生成SPARQL查询。
    如果任何一个工具返回空结果或失败，尝试SPARQL路径兜底；否则直接生成最终答案。
    """
    # 检查所有工具结果
    tool_results = []
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage):
            tool_results.append(msg.content)

    if not tool_results:
        # 没有工具结果，尝试SPARQL
        return "generate_sparql"

    # 检查是否有任何一个工具结果为空或失败
    has_failure = any(
        r.startswith("查询执行失败") or r == "没有查询到结果"
        or r == "没有获取到查询结果" or r == "SPARQL查询返回空结果"
        or r == "[]" or r.strip() == ""
        for r in tool_results
    )

    if has_failure:
        print("部分工具查询无结果，尝试SPARQL路径兜底", flush=True)
        return "generate_sparql"

    return "final_answer"


def generate_sparql(state: AgentState):
    """
    根据用户问题生成SPARQL查询语句。
    当本地工具不足以回答用户问题时使用此路径。
    包含完整本体描述，包括所有谓词。
    """
    print("generate_sparql", flush=True)

    # 获取用户最新的查询
    user_query = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    if not user_query:
        return {"messages": [AIMessage(content="未收到有效的用户查询")], "next_node": "direct"}

    sparql_prompt = f"""你是一个SPARQL查询生成助手。请根据用户的问题，生成一个有效的SPARQL查询语句。

用户问题：{user_query}

知识图谱的命名空间和本体结构：
- PREFIX calli: <http://example.org/ontology/calligraphy#>
- PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
- PREFIX script: <http://example.org/calligraphy/script/>
- 书法家实体类型: calli:Calligrapher
- 书法家标签: rdfs:label
- 属性谓词:
  * calli:dynasty - 朝代（字符串）
  * calli:styleName - 字号（字符串）
  * calli:hometown - 籍贯（字符串）
  * calli:position - 官衔（字符串）
  * calli:artFeature - 艺术特色（字符串）
  * calli:styleCharacteristic - 风格特征（字符串）
  * calli:otherSkill - 兼习（字符串）
  * calli:representativeWork - 代表作品（字符串）
  * calli:writing - 著述（字符串）
  * calli:goodAtScript - 擅长书体（指向书体URI，如script:草书、script:楷书、script:行书、script:篆书、script:隶书等）
  * calli:created - 创造的书法风格（指向风格URI）
  * calli:birthYear - 生年（字符串）
  * calli:deathYear - 卒年（字符串）
  * calli:learnedFrom - 师承（指向另一位书法家URI，表示此人师从谁）
  * calli:influenced - 受影响（指向另一位书法家URI，表示此人受到谁影响）
  * calli:relative - 亲属（指向另一位书法家URI）
  注意关系的方向：
  - 查询"XX的师承/老师"：XX calli:learnedFrom ?teacher
  - 查询"XX的学生/弟子"：?student calli:learnedFrom XX（反向）
  - 查询"XX受到谁影响"：XX calli:influenced ?influencer
  - 查询"XX影响了谁/对后世的影响"：?influencedPerson calli:influenced XX（反向）

注意事项：
1. 书法家URI格式为: http://example.org/calligraphy/calligrapher/姓名
2. 师承(learnedFrom)、影响(influenced)和亲属(relative)的值是书法家URI，需要通过rdfs:label获取名称
3. 擅长书体(goodAtScript)的值是书体URI，如script:草书，需要通过rdfs:label获取名称
4. 只返回SPARQL查询语句，不要包含其他解释性文字
5. 查询语句必须是完整且有效的
6. 使用UNION时，必须将所有UNION分支放在同一个WHERE花括号内，每个分支用独立的花括号包裹。绝对不能将UNION放在WHERE花括号外面。
7. 不要在URI两端添加反引号或其他引号字符

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

示例10 - 多属性UNION查询："范仲淹的亲属和影响"
SELECT ?relation ?person WHERE {{ {{ <http://example.org/calligraphy/calligrapher/范仲淹> calli:relative ?r . ?r rdfs:label ?person . BIND("亲属" AS ?relation) }} UNION {{ <http://example.org/calligraphy/calligrapher/范仲淹> calli:influenced ?i . ?i rdfs:label ?person . BIND("影响" AS ?relation) }} }}"""

    response = llm.invoke([SystemMessage(content=sparql_prompt)])
    sparql_query = response.content.strip()

    # 清理可能的markdown代码块标记
    if sparql_query.startswith("```"):
        lines = sparql_query.split("\n")
        sparql_query = "\n".join(lines[1:-1]) if len(lines) > 2 else sparql_query

    # 清理LLM可能在URI中添加的反引号（包括ASCII反引号和Unicode左右反引号）
    for ch in ['`', '\u2018', '\u2019', '\u201C', '\u201D']:
        sparql_query = sparql_query.replace(ch, '')

    print("生成的SPARQL查询:", sparql_query, flush=True)

    return {
        "messages": [AIMessage(content=sparql_query)],
        "sparql_query": sparql_query
    }


def execute_sparql(state: AgentState):
    """
    执行生成的SPARQL查询。
    如果结果为空列表[]，返回"SPARQL查询返回空结果"消息。
    如果执行失败，将错误信息传递给final_answer节点。
    """
    print("execute_sparql", flush=True)

    sparql_query = state.get("sparql_query", None)

    if not sparql_query:
        return {"messages": [AIMessage(content="无法获取SPARQL查询语句")], "next_node": "direct"}

    try:
        result = execute_custom_sparql_query.invoke(sparql_query)
        print("SPARQL查询结果:", result, flush=True)

        if isinstance(result, str) and result.startswith("查询执行失败"):
            return {
                "messages": [ToolMessage(content=result, tool_call_id="sparql_query_failed")],
            }
        # 空结果也视为查询失败
        if isinstance(result, list) and len(result) == 0:
            return {
                "messages": [ToolMessage(content="SPARQL查询返回空结果", tool_call_id="sparql_query_empty")],
            }

        return {
            "messages": [ToolMessage(content=str(result), tool_call_id="sparql_query_result")],
        }
    except Exception as e:
        error_message = f"执行SPARQL查询时出错：{str(e)}"
        print(error_message, flush=True)
        return {
            "messages": [AIMessage(content=error_message)],
            "next_node": "direct"
        }


def is_empty_result(r: str) -> bool:
    """
    判断查询结果是否为空或失败。
    """
    return (r.startswith("查询执行失败") or r == "没有查询到结果"
            or r == "没有获取到查询结果" or r == "SPARQL查询返回空结果"
            or r == "[]" or r.strip() == "")


def final_answer(state: AgentState):
    """
    生成最终答案。三种策略：
    - has_partial_failure: 部分有结果+部分空 → KG结果回答已有部分，LLM补充缺失部分，注明来源
    - has_valid_result: 全部有效 → 仅基于KG结果回答
    - 无有效结果 → LLM自身知识回答，注明非KG来源
    """
    print("final_answer", flush=True)

    # 查找用户原始查询
    user_query = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    if not user_query:
        return {"messages": [AIMessage(content="未找到用户原始查询")]}

    # 只收集工具执行结果（ToolMessage），排除中间产生的AIMessage
    # （如route_question的路由决策"direct"/"tool"/"sparql"、generate_sparql的SPARQL查询文本等）
    results = []
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage):
            results.append(msg.content)

    result_str = "\n\n".join(results) if results else "没有获取到查询结果"

    # 判断是否有有效的查询结果
    has_valid_result = bool(results) and not all(is_empty_result(r) for r in results)
    # 判断是否有部分查询失败（部分有结果、部分无结果）
    has_partial_failure = has_valid_result and any(is_empty_result(r) for r in results)

    if has_partial_failure:
        prompt = f"""用户原始查询：{user_query}

查询结果：
{result_str}

注意：查询结果中部分信息有结果，部分信息没有查到。
请严格按以下规则回答：
1. 对于查询结果中**已有**的部分，直接使用知识图谱的查询结果，不要添加查询结果中没有的内容。
2. 对于查询结果中**缺失**的部分，才可以基于你自身的知识进行补充，但必须明确标注"（根据历史知识补充）"。
3. 绝对不要在已有查询结果的基础上自行扩展或添加查询结果中未出现的内容。"""
    elif has_valid_result:
        prompt = f"""用户原始查询：{user_query}

查询结果：
{result_str}

请严格按以下规则回答：
1. 只基于以上查询结果回答用户问题，对查询结果进行整理和格式化即可。
2. 绝对不要添加查询结果中没有出现的内容，不要基于你自身知识进行任何补充或扩展。
3. 如果查询结果已经充分回答了用户问题，直接给出简洁清晰的答案即可。"""
    else:
        prompt = f"""用户原始查询：{user_query}

知识图谱查询未能获取到有效结果（查询结果为：{result_str}）。
请基于你自身的知识，尽量回答用户的问题。
但请注意说明这些信息并非来自知识图谱查询，标注"根据历史知识"。"""

    final_response = llm.invoke([SystemMessage(content=prompt)])
    print("最终答案:", final_response.content, flush=True)

    return {"messages": [AIMessage(content=final_response.content)]}


def create_agent_workflow(llm_instance):
    """
    创建并返回知识图谱查询agent的工作流
    """
    global llm
    llm = llm_instance

    # 创建工具节点
    tool_node = ToolNode(tools)

    # 创建图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("route_question", route_question)
    workflow.add_node("call_tool", call_tool)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("generate_sparql", generate_sparql)
    workflow.add_node("execute_sparql", execute_sparql)
    workflow.add_node("final_answer", final_answer)

    # START → route_question
    workflow.add_edge(START, "route_question")

    # route_question 根据决策走不同路径
    workflow.add_conditional_edges(
        "route_question",
        lambda state: state.get("next_node", "tool"),
        {
            "tool": "call_tool",
            "sparql": "generate_sparql",
            "direct": "final_answer"
        }
    )

    # call_tool → tool_node（执行工具）
    workflow.add_edge("call_tool", "tool_node")

    # tool_node 执行后，判断是否需要SPARQL兜底
    workflow.add_conditional_edges(
        "tool_node",
        should_continue_after_tool,
        {
            "final_answer": "final_answer",
            "generate_sparql": "generate_sparql"
        }
    )

    # generate_sparql → execute_sparql
    workflow.add_edge("generate_sparql", "execute_sparql")

    # execute_sparql → final_answer
    workflow.add_edge("execute_sparql", "final_answer")

    # 编译图
    app = workflow.compile()
    return app


def process_query_result(result):
    """
    处理查询结果，转换为友好的文本格式
    """
    messages = result["messages"]

    # 查找最后一个AI消息
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return msg.content

    return "未找到有效的查询结果"


def run_agent():
    """
    运行知识图谱查询Agent
    """
    # 设置LLM
    global llm
    llm = setup_llm()

    # 创建agent工作流
    app = create_agent_workflow(llm)

    # 保存workflow图
    try:
        graph_png = app.get_graph().draw_mermaid_png()
        with open("workflow_graph.png", "wb") as f:
            f.write(graph_png)
        print("图表已保存到: workflow_graph.png")
    except Exception as e:
        print(f"获取图表时出错: {e}")
 
    print("=== 中国书法家知识图谱查询Agent ===")
    print("您可以查询关于书法家、朝代、师承关系等信息")
    print("例如：'查询所有唐代书法家'、'王羲之的师承是谁'、'颜真卿的代表作品有哪些'")
    print("输入'退出'结束对话\n")

    while True:
        user_input = input("您的问题: ")

        if user_input.lower() in ["退出", "quit", "exit"]:
            print("对话结束，再见！")
            break

        try:
            result = app.invoke({
                "messages": [
                    HumanMessage(content=user_input)
                ]
            })

            response_text = process_query_result(result)
            print(f"\nAgent: {response_text}\n")

        except Exception as e:
            print(f"处理请求时出错: {e}\n")


if __name__ == "__main__":
    run_agent()
