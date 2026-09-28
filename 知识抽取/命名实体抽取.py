# -*- coding: utf-8 -*-
"""
混合方法命名实体抽取：
1. 人名：从笔画索引表格提取（规则方法，精准）
2. 地名、时间、书体：使用LangChain LLM抽取
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
# 1. 定义结构化输出模型
# ========================
class NamedEntities(BaseModel):
    """命名实体结构化输出（不含人名，人名用规则提取）"""
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
# 2. 从正文表格提取人名（规则方法）
# ========================
def extract_persons_from_tables(json_path: str) -> List[str]:
    """从正文表格的'书家'列提取人名"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    persons = set()

    for page in data.get('pdf_info', []):
        for block in page.get('preproc_blocks', []):
            if block.get('type') == 'table':
                for sub_block in block.get('blocks', []):
                    for line in sub_block.get('lines', []):
                        for span in line.get('spans', []):
                            if 'html' in span:
                                html = span['html']
                                # 跳过索引表格
                                if '画' in html and ('王献之' in html or '丁云鹏' in html or '二画' in html):
                                    continue

                                soup = BeautifulSoup(html, 'html.parser')
                                rows = soup.find_all('tr')

                                for row in rows:
                                    cells = row.find_all('td')
                                    if len(cells) >= 2:
                                        # 第一列是年代，第二列是书家
                                        book_cell = cells[1].get_text(strip=True)

                                        # 提取书家姓名（去掉生卒年）
                                        # 例如：李斯(?—前208) -> 李斯
                                        # 例如：王羲之(303—361) -> 王羲之
                                        match = re.match(r'^([^\(]+)', book_cell)
                                        if match:
                                            name = match.group(1).strip()
                                            # 过滤掉表头
                                            if name and name != '书家' and len(name) >= 2 and len(name) <= 4:
                                                persons.add(name)

    return list(persons)


# ========================
# 3. 从正文表格提取文本（用于LLM抽取）
# ========================
def extract_table_texts(json_path: str) -> List[str]:
    """从JSON文件中提取正文表格的文本内容"""
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
                                html = span['html']
                                # 跳过索引表格
                                if '画' in html and ('王献之' in html or '丁云鹏' in html):
                                    continue

                                soup = BeautifulSoup(html, 'html.parser')
                                cells = soup.find_all('td')
                                cell_texts = [cell.get_text(strip=True) for cell in cells]
                                table_text = ' '.join(cell_texts)
                                if table_text:
                                    table_texts.append(table_text)

    return table_texts


# ========================
# 4. 使用LangChain抽取地名、时间、书体
# ========================
def extract_entities_with_langchain(texts: List[str], api_key: str, base_url: str, known_persons: List[str]) -> NamedEntities:
    """使用LangChain的结构化输出功能抽取命名实体"""

    llm = ChatOpenAI(
        model="qwen-turbo",
        temperature=0,
        api_key=api_key,
        base_url=base_url
    )

    structured_llm = llm.with_structured_output(NamedEntities)

    # 改进的prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个专业的命名实体识别系统，专门用于从中国历代书法家相关文本中抽取实体。

请从给定的文本中抽取以下三类命名实体：

1. **地名**：籍贯、出生地等地理位置，如"琅琊临沂"、"吴郡"、"会稽"、"河南上蔡"等

2. **时间**：
   - 朝代名称：如"东晋"、"唐代"、"宋代"、"秦"、"汉"、"魏"、"晋"等
   - 年份数字：特别注意括号内的生卒年，如"(303—361)"中的"303"和"361"
   - 公元前年份：如"前208"

3. **书体**：书法字体类型

**书体类型说明**（只抽取以下类型）：
- 基本书体：楷书、行书、草书、隶书、篆书
- 章草、今草、狂草、行草、行楷
- 甲骨文、金文、石鼓文、大篆、小篆
- 魏碑、瘦金体、八分书、飞白书、漆书
- 草篆、剪刀篆、金错书、悬针篆、垂露篆

**不要抽取以下内容作为书体**：
- 人名（如"米芾"、"黄庭坚"、"郑文公"）
- 作品名（如"兰亭序"、"黄庭经"、"急就章"）
- 碑名（如"郑文公碑"、"张迁碑"、"礼器碑"）
- 绘画题材（如"人物"、"山水"、"花卉"、"仕女"）
- 朝代名（如"魏"、"晋"、"魏晋"）
- 其他非书体名词

请严格按照以上规则抽取实体。"""),
        ("human", "请从以下文本中抽取命名实体：\n\n{text}")
    ])

    chain = prompt | structured_llm

    all_text = '\n'.join(texts)
    all_entities = NamedEntities()

    chunk_size = 2000
    total_chunks = (len(all_text) + chunk_size - 1) // chunk_size

    for i in range(0, len(all_text), chunk_size):
        chunk = all_text[i:i+chunk_size]
        chunk_num = i // chunk_size + 1
        try:
            result = chain.invoke({"text": chunk})
            all_entities.places.extend(result.places)
            all_entities.times.extend(result.times)
            all_entities.scripts.extend(result.scripts)
            print(f"已处理 {chunk_num}/{total_chunks} 块")
        except Exception as e:
            print(f"处理第 {chunk_num} 块出错: {str(e)[:100]}")
            continue

    # 去重
    all_entities.places = list(set(all_entities.places))
    all_entities.times = list(set(all_entities.times))
    all_entities.scripts = list(set(all_entities.scripts))

    return all_entities


# ========================
# 5. 保存结果
# ========================
def save_entities(persons: List[str], entities: NamedEntities, output_path: str):
    """保存命名实体到CSV文件"""
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['实体类型', '实体名称'])

        for person in sorted(persons):
            writer.writerow(['人名', person])

        for place in sorted(entities.places):
            writer.writerow(['地名', place])

        for time in sorted(entities.times):
            writer.writerow(['时间', time])

        for script in sorted(entities.scripts):
            writer.writerow(['书体', script])

    print(f"\n命名实体已保存到: {output_path}")
    print(f"人名: {len(persons)} 个（规则方法从笔画索引提取）")
    print(f"地名: {len(entities.places)} 个")
    print(f"时间: {len(entities.times)} 个")
    print(f"书体: {len(entities.scripts)} 个")


# ========================
# 主函数
# ========================
if __name__ == "__main__":
    API_KEY = "sk-1c1e348420124733ad316c60182ccc09"
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    json_path = r"D:\奥义 学习\计算机\知识图谱\大作业\中国历代书法家图表.json"
    output_path = r"D:\奥义 学习\计算机\知识图谱\大作业\命名实体_混合方法.csv"

    print("=" * 50)
    print("混合方法命名实体抽取")
    print("人名：规则方法（从笔画索引提取）")
    print("地名/时间/书体：LangChain LLM抽取")
    print("=" * 50)

    # 1. 从正文表格提取人名
    print("\n[1/3] 正在从正文表格提取人名...")
    persons = extract_persons_from_tables(json_path)
    print(f"提取到 {len(persons)} 个人名")

    # 2. 提取正文表格文本
    print("\n[2/3] 正在提取正文表格文本...")
    table_texts = extract_table_texts(json_path)
    print(f"共提取 {len(table_texts)} 个表格")

    # 3. 使用LangChain抽取其他实体
    print("\n[3/3] 正在使用LangChain抽取地名/时间/书体...")
    entities = extract_entities_with_langchain(table_texts, API_KEY, BASE_URL, persons)

    # 4. 保存结果
    print("\n[4/4] 正在保存结果...")
    save_entities(persons, entities, output_path)
