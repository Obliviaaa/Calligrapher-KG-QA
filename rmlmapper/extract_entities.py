# -*- coding: utf-8 -*-
"""
命名实体抽取
抽取：人名、地名、时间、书体类型
"""
import csv
import re

entities = {
    '人名': set(),
    '地名': set(),
    '时间': set(),
    '书体': set()
}

# 书体类型列表
script_types = [
    '楷书', '行书', '草书', '隶书', '篆书', '魏碑',
    '章草', '今草', '狂草', '行草', '甲骨文', '金文',
    '石鼓文', '大篆', '小篆', '瘦金体', '八分书',
    '飞白书', '漆书', '草篆', '剪刀篆', '金错书', '今草'
]

with open('书法家三元组.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        subject = row['主体']
        relation = row['关系']
        obj = row['客体']
        
        # 人名：主体
        entities['人名'].add(subject)
        
        # 时间：朝代、生年、卒年
        if relation == '所属朝代':
            entities['时间'].add(obj)
        elif relation == '生年':
            # 生年转换为时间格式
            if obj.startswith('前'):
                entities['时间'].add(f'前{obj[1:]}年')
            else:
                entities['时间'].add(f'{obj}年')
        elif relation == '卒年':
            if obj.startswith('前'):
                entities['时间'].add(f'前{obj[1:]}年')
            else:
                entities['时间'].add(f'{obj}年')
        
        # 地名：籍贯
        elif relation == '籍贯':
            # 简单提取地名（取括号前的内容）
            match = re.match(r'^([^（(]+)', obj)
            if match:
                place = match.group(1).strip()
                if place:
                    entities['地名'].add(place)
        
        # 书体：擅长书体
        elif relation == '擅长书体':
            entities['书体'].add(obj)

# 保存到CSV
with open('命名实体.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['实体', '类型'])
    for entity in sorted(entities['人名']):
        writer.writerow([entity, '人名'])
    for entity in sorted(entities['地名']):
        writer.writerow([entity, '地名'])
    for entity in sorted(entities['时间']):
        writer.writerow([entity, '时间'])
    for entity in sorted(entities['书体']):
        writer.writerow([entity, '书体'])

print('命名实体抽取完成！')
print(f'人名: {len(entities["人名"])}个')
print(f'地名: {len(entities["地名"])}个')
print(f'时间: {len(entities["时间"])}个')
print(f'书体: {len(entities["书体"])}个')

print('\n时间实体示例:')
for t in sorted(entities['时间'])[:20]:
    print(f'  - {t}')
