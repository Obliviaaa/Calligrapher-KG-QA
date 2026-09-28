# -*- coding: utf-8 -*-
"""
使用LangChain进行命名实体抽取
方法：Generative Style + Structured Output
"""

import json
import re
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from bs4 import BeautifulSoup
import csv


# ========================
# 1. 定义结构化输出模型（Pydantic）
# ========================
class NamedEntities(BaseModel):
    """命名实体结构化输出"""
    persons: List[str] = Field(
        default_factory=list,
        description="人名列表，如：王羲之、颜真卿、苏轼"
    )
    places: List[str] = Field(
        default_factory=list,
        description="地名列表，如：琅琊临沂、吴郡、会稽"
    )
    times: List[str] = Field(
        default_factory=list,
        description="时间列表，包括朝代和年份，如：东晋、303、361、前208"
    )
    scripts: List[str] = Field(
        default_factory=list,
        description="书体列表，如：楷书、行书、草书、篆书"
    )


# ========================
# 2. 从JSON中提取表格文本
# ========================
def extract_table_texts(json_path: str) -> List[str]:
    """从JSON文件中提取所有表格的文本内容"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    table_texts = []

    for page in data.get('pdf_info', []):
        for block in page.get('preproc_blocks', []):
            if block.get('type') == 'table':
                for sub_block in block.get('blocks', []):
                    for line in sub_block.get('lines', []):
                        for span in line.get('spans', []):
                            if 'html' in span:
                                # 解析HTML表格
                                html = span['html']
                                soup = BeautifulSoup(html, 'html.parser')

                                # 提取所有单元格文本
                                cells = soup.find_all('td')
                                cell_texts = [cell.get_text(strip=True) for cell in cells]

                                # 合并为一段文本
                                table_text = ' '.join(cell_texts)
                                if table_text:
                                    table_texts.append(table_text)

    return table_texts


# ========================
# 3. 使用LangChain进行命名实体抽取
# ========================
def extract_entities_with_langchain(texts: List[str], api_key: str, base_url: str = None) -> NamedEntities:
    """使用LangChain的结构化输出功能抽取命名实体"""

    # 初始化LLM
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0,
        api_key=api_key,
        base_url=base_url
    )

    # 绑定结构化输出
    structured_llm = llm.with_structured_output(NamedEntities)

    # 定义提示模板
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个专业的命名实体识别系统，专门用于从中国历代书法家相关文本中抽取实体。

请从给定的文本中抽取以下四类命名实体：

1. **人名**：书法家的姓名，如"王羲之"、"颜真卿"、"苏轼"等
2. **地名**：籍贯、出生地等地理位置，如"琅琊临沂"、"吴郡"、"会稽"等
3. **时间**：
   - 朝代名称，如"东晋"、"唐代"、"宋代"等
   - 年份数字，特别注意括号内的生卒年，如"(303—361)"中的"303"和"361"
   - 公元前年份，如"前208"
4. **书体**：书法字体类型，如"楷书"、"行书"、"草书"、"篆书"、"隶书"、"章草"等

注意事项：
- 年份要从括号中提取，如"李斯(?—前208)"应提取"前208"
- "生卒年不详"不需要提取
- 书体名称要准确，如"章草"、"今草"、"狂草"等都是不同的书体
- 地名要完整，如"楚国上蔡(今河南上蔡西)"应提取"楚国上蔡"和"河南上蔡西"
"""),
        ("human", "请从以下文本中抽取命名实体：\n\n{text}")
    ])

    # 创建链
    chain = prompt | structured_llm

    # 合并所有文本
    all_text = '\n'.join(texts)

    # 由于文本太长，分批处理
    all_entities = NamedEntities()

    # 每次处理5000字符
    chunk_size = 5000
    for i in range(0, len(all_text), chunk_size):
        chunk = all_text[i:i+chunk_size]
        try:
            result = chain.invoke({"text": chunk})
            all_entities.persons.extend(result.persons)
            all_entities.places.extend(result.places)
            all_entities.times.extend(result.times)
            all_entities.scripts.extend(result.scripts)
            print(f"已处理 {i+len(chunk)}/{len(all_text)} 字符")
        except Exception as e:
            print(f"处理出错: {e}")
            continue

    # 去重
    all_entities.persons = list(set(all_entities.persons))
    all_entities.places = list(set(all_entities.places))
    all_entities.times = list(set(all_entities.times))
    all_entities.scripts = list(set(all_entities.scripts))

    return all_entities


# ========================
# 4. 保存结果
# ========================
def save_entities(entities: NamedEntities, output_path: str):
    """保存命名实体到CSV文件"""
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['实体类型', '实体名称'])

        for person in sorted(entities.persons):
            writer.writerow(['人名', person])

        for place in sorted(entities.places):
            writer.writerow(['地名', place])

        for time in sorted(entities.times):
            writer.writerow(['时间', time])

        for script in sorted(entities.scripts):
            writer.writerow(['书体', script])

    print(f"\n命名实体已保存到: {output_path}")
    print(f"人名: {len(entities.persons)} 个")
    print(f"地名: {len(entities.places)} 个")
    print(f"时间: {len(entities.times)} 个")
    print(f"书体: {len(entities.scripts)} 个")


# ========================
# 主函数
# ========================
if __name__ == "__main__":
    import os

    # 配置API
    # 方式1：使用环境变量
    # export OPENAI_API_KEY="your-api-key"

    # 方式2：直接设置（不推荐在生产环境使用）
    API_KEY = "your-api-key-here"  # 替换为你的API Key
    BASE_URL = None  # 如果使用代理，设置base_url，如 "https://api.openai.com/v1"

    # 文件路径
    json_path = r"D:\奥义 学习\计算机\知识图谱\大作业\中国历代书法家图表.json"
    output_path = r"D:\奥义 学习\计算机\知识图谱\大作业\命名实体_LangChain.csv"

    print("=" * 50)
    print("LangChain 命名实体抽取")
    print("方法：Generative Style + Structured Output")
    print("=" * 50)

    # 1. 提取表格文本
    print("\n[1/3] 正在提取表格文本...")
    table_texts = extract_table_texts(json_path)
    print(f"共提取 {len(table_texts)} 个表格")

    # 2. 使用LangChain抽取命名实体
    print("\n[2/3] 正在使用LangChain抽取命名实体...")
    if API_KEY == "your-api-key-here":
        print("请先设置API_KEY！")
        print("方法1: 设置环境变量 OPENAI_API_KEY")
        print("方法2: 在代码中修改 API_KEY 变量")
    else:
        entities = extract_entities_with_langchain(table_texts, API_KEY, BASE_URL)

        # 3. 保存结果
        print("\n[3/3] 正在保存结果...")
        save_entities(entities, output_path)
