# -*- coding: utf-8 -*-
import csv
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS, XSD

CALLI = Namespace("http://example.org/ontology/calligraphy#")
CALLIGRAPHER = Namespace("http://example.org/calligraphy/calligrapher/")
SCRIPT = Namespace("http://example.org/calligraphy/script/")
STYLE = Namespace("http://example.org/calligraphy/style/")

g = Graph()
g.bind("calli", CALLI)
g.bind("calligrapher", CALLIGRAPHER)
g.bind("script", SCRIPT)
g.bind("style", STYLE)
g.bind("rdfs", RDFS)
g.bind("xsd", XSD)

relation_predicate_map = {
    '所属朝代': CALLI.dynasty,
    '字号': CALLI.styleName,
    '籍贯': CALLI.hometown,
    '官衔': CALLI.position,
    '代表作品': CALLI.representativeWork,
    '著述': CALLI.writing,
    '师承': CALLI.learnedFrom,
    '影响': CALLI.influenced,
    '擅长书体': CALLI.goodAtScript,
    '开创': CALLI.created,
    '生年': CALLI.birthYear,
    '卒年': CALLI.deathYear,
    # 亲属关系统一
    '儿子': CALLI.relative,
    '女儿': CALLI.relative,
    '孙子': CALLI.relative,
    '侄子': CALLI.relative,
    '弟弟': CALLI.relative,
    '哥哥': CALLI.relative,
    '亲属': CALLI.relative
}

calligraphers = set()
script_styles = set()
created_styles = set()

with open('../知识抽取/书法家三元组_更新.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    
    for row in reader:
        subject = row['主体']
        relation = row['关系']
        obj = row['客体']
        
        if not subject or not relation or not obj:
            continue
        
        calligraphers.add(subject)
        
        subject_uri = CALLIGRAPHER[subject]
        
        g.add((subject_uri, RDF.type, CALLI.Calligrapher))
        g.add((subject_uri, RDFS.label, Literal(subject, datatype=XSD.string)))
        
        if relation in relation_predicate_map:
            predicate = relation_predicate_map[relation]
            
            if relation == '擅长书体':
                object_uri = SCRIPT[obj]
                g.add((object_uri, RDF.type, CALLI.ScriptStyle))
                g.add((object_uri, RDFS.label, Literal(obj, datatype=XSD.string)))
                g.add((subject_uri, predicate, object_uri))
                script_styles.add(obj)
            elif relation == '开创':
                object_uri = STYLE[obj]
                g.add((object_uri, RDF.type, CALLI.InnovationStyle))
                g.add((object_uri, RDFS.label, Literal(obj, datatype=XSD.string)))
                g.add((subject_uri, predicate, object_uri))
                created_styles.add(obj)
            elif relation in ['师承', '影响']:
                object_uri = CALLIGRAPHER[obj]
                g.add((subject_uri, predicate, object_uri))
            elif relation in ['儿子', '女儿', '孙子', '侄子', '弟弟', '哥哥', '亲属', '父亲']:
                # 亲属关系统一使用relative谓词，双向添加
                # 过滤掉错误的亲属名字（包含"仲子"、"长子"等后缀）
                if obj.endswith('仲子') or obj.endswith('长子') or obj.endswith('次子') or "'" in obj:
                    continue
                object_uri = CALLIGRAPHER[obj]
                g.add((subject_uri, CALLI.relative, object_uri))
                # 反向关系：如果A是B的儿子，则B也是A的亲属
                g.add((object_uri, CALLI.relative, subject_uri))
            else:
                g.add((subject_uri, predicate, Literal(obj, datatype=XSD.string)))

# 尝试读取书体与开创三元组文件
import os
script_file = '../书体与开创三元组_new.csv'
if os.path.exists(script_file):
    with open(script_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            subject = row['主体']
            relation = row['关系']
            obj = row['客体']
            
            if not subject or not relation or not obj:
                continue
            
            calligraphers.add(subject)
            subject_uri = CALLIGRAPHER[subject]
            
            g.add((subject_uri, RDF.type, CALLI.Calligrapher))
            g.add((subject_uri, RDFS.label, Literal(subject, datatype=XSD.string)))
            
            if relation == '擅长书体':
                object_uri = SCRIPT[obj]
                g.add((object_uri, RDF.type, CALLI.ScriptStyle))
                g.add((object_uri, RDFS.label, Literal(obj, datatype=XSD.string)))
                g.add((subject_uri, CALLI.goodAtScript, object_uri))
                script_styles.add(obj)
            elif relation == '开创':
                object_uri = STYLE[obj]
                g.add((object_uri, RDF.type, CALLI.InnovationStyle))
                g.add((object_uri, RDFS.label, Literal(obj, datatype=XSD.string)))
                g.add((subject_uri, CALLI.created, object_uri))
                created_styles.add(obj)
    print(f'已加载书体与开创三元组文件')
else:
    print(f'书体与开创三元组文件不存在，跳过')

output_file = 'calligraphy_kg.ttl'
g.serialize(destination=output_file, format='turtle')

print(f'RDF数据已生成: {output_file}')
print(f'三元组总数: {len(g)}')
print(f'书法家数量: {len(calligraphers)}')
print(f'书体类型数量: {len(script_styles)}')
print(f'开创风格数量: {len(created_styles)}')

print('\n书体类型:')
for s in sorted(script_styles):
    print(f'  - {s}')

print('\n开创风格:')
for s in sorted(created_styles):
    print(f'  - {s}')

print('\n示例数据:')
print(g.serialize(format='turtle')[:2500])
