# -*- coding: utf-8 -*-
"""
从字号中抽取亲属关系
简单方案：匹配"XX子"、"XX女"、"XX孙"、"XX从子"、"XX侄"等模式
"""
import re
import csv

# 读取书法家名单
calligraphers = set()
with open('书法家三元组.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        calligraphers.add(row['主体'])

print(f'共{len(calligraphers)}位书法家')

# 亲属关系抽取函数
def extract_kinship(style_name, calligraphers):
    """从字号中抽取亲属关系"""
    results = []
    
    # 匹配"XX从子"模式
    # 尝试匹配2-4字人名
    for match in re.findall(r'(\S{2,4})从子', style_name):
        # 从后向前尝试匹配书法家名
        for i in range(2, min(5, len(match)+1)):
            candidate = match[-i:]  # 取最后i个字符
            if candidate in calligraphers:
                results.append((candidate, '侄子'))
                break
    
    # 匹配"XX子"模式（排除"从子"）
    for match in re.findall(r'(\S{2,4})子(?![女孙])', style_name):
        if '从子' not in match:  # 排除从子
            for i in range(2, min(5, len(match)+1)):
                candidate = match[-i:]
                if candidate in calligraphers:
                    results.append((candidate, '儿子'))
                    break
    
    # 匹配"XX女"模式
    for match in re.findall(r'(\S{2,4})女', style_name):
        for i in range(2, min(5, len(match)+1)):
            candidate = match[-i:]
            if candidate in calligraphers:
                results.append((candidate, '女儿'))
                break
    
    # 匹配"XX孙"模式
    for match in re.findall(r'(\S{2,4})孙', style_name):
        for i in range(2, min(5, len(match)+1)):
            candidate = match[-i:]
            if candidate in calligraphers:
                results.append((candidate, '孙子'))
                break
    
    # 匹配"XX侄"模式
    for match in re.findall(r'(\S{2,4})侄', style_name):
        for i in range(2, min(5, len(match)+1)):
            candidate = match[-i:]
            if candidate in calligraphers:
                results.append((candidate, '侄子'))
                break
    
    # 匹配"XX弟"模式
    for match in re.findall(r'(\S{2,4})弟', style_name):
        for i in range(2, min(5, len(match)+1)):
            candidate = match[-i:]
            if candidate in calligraphers:
                results.append((candidate, '弟弟'))
                break
    
    # 匹配"XX兄"模式
    for match in re.findall(r'(\S{2,4})兄', style_name):
        for i in range(2, min(5, len(match)+1)):
            candidate = match[-i:]
            if candidate in calligraphers:
                results.append((candidate, '哥哥'))
                break
    
    return results

# 读取字号并抽取亲属关系
kinship_triples = []
with open('书法家三元组.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        subject = row['主体']
        relation = row['关系']
        obj = row['客体']
        
        # 从字号中抽取
        if relation == '字号':
            style_name = obj
            kinships = extract_kinship(style_name, calligraphers)
            for relative_name, kinship_type in kinships:
                kinship_triples.append((subject, kinship_type, relative_name))
                print(f'抽取(字号): {subject} -{kinship_type}-> {relative_name} (从"{style_name}")')
        
        # 从籍贯中抽取
        if relation == '籍贯':
            hometown = obj
            kinships = extract_kinship(hometown, calligraphers)
            for relative_name, kinship_type in kinships:
                kinship_triples.append((subject, kinship_type, relative_name))
                print(f'抽取(籍贯): {subject} -{kinship_type}-> {relative_name} (从"{hometown}")')

print(f'\n共抽取 {len(kinship_triples)} 条亲属关系')

# 将亲属关系添加到三元组文件
with open('书法家三元组.csv', 'a', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    for triple in kinship_triples:
        writer.writerow(triple)

print('已将亲属关系添加到 书法家三元组.csv')

# 打印示例
print('\n亲属关系统计:')
kinship_stats = {}
for s, r, o in kinship_triples:
    kinship_stats[r] = kinship_stats.get(r, 0) + 1
for k, v in sorted(kinship_stats.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}条')
