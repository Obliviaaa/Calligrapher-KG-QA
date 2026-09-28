"""
书法家知识图谱 SPARQL 查询工具模块
提供基于 LangChain @tool 装饰器的 SPARQL 查询函数，用于书法家知识图谱问答系统。
"""

from SPARQLWrapper import SPARQLWrapper, JSON
from langchain_core.tools import tool
import pandas as pd

SPARQL_ENDPOINT = "http://localhost:8000/sparql"

# 谓词映射：完整 URI -> 中文名称
PREDICATE_MAP = {
    "http://example.org/calligraphy/dynasty": "朝代",
    "http://example.org/calligraphy/styleName": "字号",
    "http://example.org/calligraphy/hometown": "籍贯",
    "http://example.org/calligraphy/position": "官衔",
    "http://example.org/calligraphy/artFeature": "艺术特色",
    "http://example.org/calligraphy/styleCharacteristic": "风格特征",
    "http://example.org/calligraphy/otherSkill": "兼习",
    "http://example.org/calligraphy/representativeWork": "代表作品",
    "http://example.org/calligraphy/writing": "著述",
    "http://example.org/calligraphy/learnedFrom": "师承",
    "http://example.org/calligraphy/influenced": "影响",
    "http://example.org/calligraphy/relative": "亲属",
    "http://example.org/calligraphy/goodAtScript": "擅长书体",
    "http://example.org/calligraphy/created": "创立流派",
    "http://example.org/calligraphy/birthYear": "出生年份",
    "http://example.org/calligraphy/deathYear": "逝世年份",
    "http://www.w3.org/2000/01/rdf-schema#label": "名称",
}


def execute_sparql_query(query: str) -> str:
    """执行 SPARQL 查询并返回结果。

    使用 SPARQLWrapper 向本地端点发送 SPARQL 查询，
    将返回的 JSON 结果转换为 pandas DataFrame 字符串。

    Args:
        query: SPARQL 查询字符串

    Returns:
        成功时返回 DataFrame 的字符串表示；
        查询失败时返回以"查询执行失败"开头的错误信息字符串。
    """
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        results = sparql.query().convert()
        bindings = results.get("results", {}).get("bindings", [])
        if not bindings:
            return ""
        rows = []
        for binding in bindings:
            row = {}
            for key in bindings[0].keys():
                value = binding.get(key, {}).get("value", "")
                row[key] = value
            rows.append(row)
        df = pd.DataFrame(rows)
        return df.to_string(index=False)
    except Exception as e:
        return f"查询执行失败: {str(e)}"


@tool
def query_all_calligraphers() -> str:
    """查询所有书法家的姓名。

    当用户想要了解知识图谱中收录了哪些书法家，
    或者需要获取全部书法家列表时使用此工具。

    Returns:
        包含所有书法家姓名的表格字符串，若无结果则返回提示信息。
    """
    query = """
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name WHERE {
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
    }
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_calligraphers_by_dynasty(dynasty: str) -> str:
    """根据朝代查询书法家姓名。

    当用户询问某个朝代有哪些书法家时使用此工具。
    使用 CONTAINS 进行模糊匹配，可以匹配朝代名称的一部分。

    Args:
        dynasty: 朝代名称，如"唐"、"宋"、"明"等。

    Returns:
        包含该朝代书法家姓名的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        ?c calli:dynasty ?d .
        FILTER(CONTAINS(LCASE(?d), LCASE('{dynasty}')))
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_calli_details(calli_name: str) -> str:
    """查询书法家的所有详细信息。

    当用户想要了解某位书法家的全面信息时使用此工具，
    会返回该书法家的所有属性和对应值。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"颜真卿"等。

    Returns:
        包含该书法家所有详细信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?p ?v WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c ?p ?v .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"

    # 在Python中做谓词映射和值处理
    predicate_map = {
        "dynasty": "朝代", "birthYear": "生年", "deathYear": "卒年", "styleName": "字号",
        "hometown": "籍贯", "position": "官衔", "representativeWork": "代表作品",
        "writing": "著述", "artFeature": "艺术特色", "styleCharacteristic": "风格特征",
        "otherSkill": "兼习",
    }
    relation_map = {
        "learnedFrom": "师承", "influenced": "影响", "relative": "亲属",
        "goodAtScript": "擅长书体", "created": "开创",
    }

    # 重新查询获取原始结果
    from SPARQLWrapper import SPARQLWrapper, JSON as SPARQL_JSON
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(SPARQL_JSON)
    try:
        results = sparql.query().convert()
        bindings = results.get("results", {}).get("bindings", [])
    except Exception as e:
        return f"查询执行失败: {str(e)}"

    if not bindings:
        return "没有查询到结果"

    info = []
    for binding in bindings:
        p = binding.get("p", {}).get("value", "")
        v = binding.get("v", {}).get("value", "")
        # 提取谓词短名
        p_short = p.split("#")[-1] if "#" in p else p.split("/")[-1]
        if p_short in predicate_map and v:
            info.append(f"{predicate_map[p_short]}：{v}")
        elif p_short in relation_map:
            # 提取对象名称
            if "calligrapher/" in v:
                info.append(f"{relation_map[p_short]}：{v.split('calligrapher/')[-1]}")
            elif "script/" in v:
                info.append(f"{relation_map[p_short]}：{v.split('script/')[-1]}")
            elif "style/" in v:
                info.append(f"{relation_map[p_short]}：{v.split('style/')[-1]}")

    return "\n".join(info) if info else "没有查询到结果"


@tool
def query_style_name(calli_name: str) -> str:
    """查询书法家的字号。

    当用户询问某位书法家的字号、别号时使用此工具。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"苏轼"等。

    Returns:
        包含该书法家字号信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?styleName WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:styleName ?styleName .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_hometown(calli_name: str) -> str:
    """查询书法家的籍贯。

    当用户询问某位书法家的籍贯、出生地时使用此工具。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"颜真卿"等。

    Returns:
        包含该书法家籍贯信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?hometown WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:hometown ?hometown .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_dynasty(calli_name: str) -> str:
    """查询书法家所属的朝代。

    当用户询问某位书法家生活在哪个朝代时使用此工具。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"柳公权"等。

    Returns:
        包含该书法家朝代信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?dynasty WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:dynasty ?dynasty .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_teacher_of(calli_name: str) -> str:
    """查询书法家的师承关系（向谁学习）。

    当用户询问某位书法家的老师、师承来源时使用此工具。
    通过 learnedFrom 对象属性链接到老师的 URI，再获取其 label。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王献之"、"颜真卿"等。

    Returns:
        包含该书法家师承信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?teacher WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:learnedFrom ?t .
        ?t rdfs:label ?teacher .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_students_of(calli_name: str) -> str:
    """查询某位书法家的弟子/传人（谁向此人学习）。

    当用户询问某位书法家有哪些弟子、传人、学生时使用此工具。
    通过反向查找 learnedFrom 关系：查找所有 calli:learnedFrom 指向该书法家的其他人。
    使用精确 URI 匹配定位该书法家。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"颜真卿"等。

    Returns:
        包含该书法家弟子/传人信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?studentName WHERE {{
        ?s a calli:Calligrapher .
        ?s calli:learnedFrom <http://example.org/calligraphy/calligrapher/{calli_name}> .
        ?s rdfs:label ?studentName .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_influenced_by(calli_name: str) -> str:
    """查询书法家受到谁的影响。

    当用户询问某位书法家受到哪些人的影响时使用此工具。
    通过 influenced 对象属性链接到影响者的 URI，再获取其 label。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"苏轼"等。

    Returns:
        包含该书法家受影响信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?influencedBy WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:influenced ?i .
        ?i rdfs:label ?influencedBy .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_influenced_on(calli_name: str) -> str:
    """查询某位书法家影响了谁（反向查询）。

    当用户询问某位书法家影响了哪些人、对后世有什么影响时使用此工具。
    通过反向查找 influenced 关系：查找所有 calli:influenced 指向该书法家的人。
    使用精确 URI 匹配定位该书法家。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"范仲淹"等。

    Returns:
        包含受该书法家影响的人的信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?influencedName WHERE {{
        ?s a calli:Calligrapher .
        ?s calli:influenced <http://example.org/calligraphy/calligrapher/{calli_name}> .
        ?s rdfs:label ?influencedName .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_representative_works(calli_name: str) -> str:
    """查询书法家的代表作品。

    当用户询问某位书法家有哪些代表作品时使用此工具。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"颜真卿"等。

    Returns:
        包含该书法家代表作品的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?work WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:representativeWork ?work .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_art_feature(calli_name: str) -> str:
    """查询书法家的艺术特色和风格特征。

    当用户询问某位书法家的艺术特色、风格特点时使用此工具。
    同时查询 artFeature 和 styleCharacteristic 两个属性，均使用 OPTIONAL，
    因为并非所有书法家都有这两项信息。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"颜真卿"等。

    Returns:
        包含该书法家艺术特色和风格特征的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?artFeature ?styleCharacteristic WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        OPTIONAL {{ ?c calli:artFeature ?artFeature }}
        OPTIONAL {{ ?c calli:styleCharacteristic ?styleCharacteristic }}
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_writings(calli_name: str) -> str:
    """查询书法家的著述。

    当用户询问某位书法家有哪些著作、文章时使用此工具。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"苏轼"、"赵孟頫"等。

    Returns:
        包含该书法家著述信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?writing WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:writing ?writing .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_position(calli_name: str) -> str:
    """查询书法家的官衔。

    当用户询问某位书法家担任过什么官职时使用此工具。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"颜真卿"、"柳公权"等。

    Returns:
        包含该书法家官衔信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?position WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:position ?position .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_other_skill(calli_name: str) -> str:
    """查询书法家的兼习（其他技能）。

    当用户询问某位书法家还擅长什么其他技艺时使用此工具。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"苏轼"、"赵孟頫"等。

    Returns:
        包含该书法家兼习信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?otherSkill WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:otherSkill ?otherSkill .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_relatives(calli_name: str) -> str:
    """查询书法家的亲属关系。

    当用户询问某位书法家的亲属、家人时使用此工具。
    通过 relative 对象属性链接到亲属的 URI，再获取其 label。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"王献之"等。

    Returns:
        包含该书法家亲属信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?relative WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        ?c calli:relative ?r .
        ?r rdfs:label ?relative .
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_social_circle(calli_name: str) -> str:
    """查询书法家的交游圈（师承、影响、亲属的综合查询）。

    当用户询问某位书法家的社交圈、交游关系、人际网络时使用此工具。
    通过 UNION 将师承（learnedFrom）、影响（influenced）、亲属（relative）三种关系
    合并在一次查询中，返回与该书法家有社会关联的所有人物。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"苏轼"等。

    Returns:
        包含该书法家交游圈信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?relation ?person WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        {{
            ?c calli:learnedFrom ?p .
            ?p rdfs:label ?person .
            BIND("师承" AS ?relation)
        }} UNION {{
            ?c calli:influenced ?p .
            ?p rdfs:label ?person .
            BIND("影响" AS ?relation)
        }} UNION {{
            ?c calli:relative ?p .
            ?p rdfs:label ?person .
            BIND("亲属" AS ?relation)
        }}
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_school(calli_name: str) -> str:
    """查询书法家所属的流派信息。

    当用户询问某位书法家属于什么流派、创立了什么流派、擅长什么书体时使用此工具。
    查询 created（创立的流派）和 goodAtScript（擅长的书体）两个对象属性，
    均通过 URI 获取 label，使用 OPTIONAL 因为并非所有书法家都有这两项信息。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"颜真卿"等。

    Returns:
        包含该书法家流派信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?school ?script WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        OPTIONAL {{
            ?c calli:created ?s .
            ?s rdfs:label ?school .
        }}
        OPTIONAL {{
            ?c calli:goodAtScript ?g .
            ?g rdfs:label ?script .
        }}
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_calligraphers_by_script(script: str) -> str:
    """根据书体查询擅长该书体的书法家。

    当用户询问擅长某种书体的书法家有哪些时使用此工具。
    通过 goodAtScript 对象属性链接到书体的 URI，再获取其 label，
    使用 CONTAINS 对书体名称进行模糊匹配。

    Args:
        script: 书体名称，如"楷书"、"行书"、"草书"等。

    Returns:
        包含擅长该书体的书法家姓名的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        ?c calli:goodAtScript ?s .
        ?s rdfs:label ?scriptLabel .
        FILTER(CONTAINS(LCASE(?scriptLabel), LCASE('{script}')))
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def query_birth_death_year(calli_name: str) -> str:
    """查询书法家的生卒年。

    当用户询问某位书法家的出生年份、逝世年份、生卒年时使用此工具。
    同时查询 birthYear 和 deathYear 两个属性，均使用 OPTIONAL，
    因为并非所有书法家都有完整的生卒年信息。
    使用 CONTAINS 对姓名进行模糊匹配。

    Args:
        calli_name: 书法家姓名，如"王羲之"、"颜真卿"等。

    Returns:
        包含该书法家生卒年信息的表格字符串，若无结果则返回提示信息。
    """
    query = f"""
    PREFIX calli: <http://example.org/ontology/calligraphy#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?birthYear ?deathYear WHERE {{
        ?c a calli:Calligrapher .
        ?c rdfs:label ?name .
        FILTER(CONTAINS(LCASE(?name), LCASE('{calli_name}')))
        OPTIONAL {{ ?c calli:birthYear ?birthYear }}
        OPTIONAL {{ ?c calli:deathYear ?deathYear }}
    }}
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result


@tool
def execute_custom_sparql_query(query: str) -> str:
    """执行自定义 SPARQL 查询。

    当其他预设工具无法满足查询需求，或者用户需要执行复杂的自定义 SPARQL 查询时使用此工具。
    直接将用户提供的 SPARQL 查询字符串发送到端点执行。

    Args:
        query: 完整的 SPARQL 查询字符串，需要包含必要的 PREFIX 声明。

    Returns:
        查询结果的表格字符串；查询失败时返回错误信息；无结果时返回提示信息。
    """
    result = execute_sparql_query(query)
    if result.startswith("查询执行失败"):
        return result
    if not result:
        return "没有查询到结果"
    return result
