# -*- coding: utf-8 -*-
import csv

entities = {
    '人名': set(),
    '地名': set(),
    '时间': set(),
    '书体': set()
}

with open('书法家三元组.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        subject = row['主体']
        relation = row['关系']
        obj = row['客体']
        
        entities['人名'].add(subject)
        
        if relation == '所属朝代':
            entities['时间'].add(obj)
        elif relation == '籍贯':
            if obj:
                entities['地名'].add(obj)
        elif relation == '擅长书体':
            entities['书体'].add(obj)
        elif relation == '师承':
            entities['人名'].add(obj)
        elif relation == '影响':
            entities['人名'].add(obj)

with open('命名实体_v2.csv', 'w', encoding='utf-8-sig', newline='') as f:
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

print('=' * 60)
print('命名实体抽取结果')
print('=' * 60)
print(f'\n人名: {len(entities["人名"])} 个')
print(f'地名: {len(entities["地名"])} 个')
print(f'时间: {len(entities["时间"])} 个')
print(f'书体: {len(entities["书体"])} 个')
print(f'\n总计: {sum(len(v) for v in entities.values())} 个实体')

print('\n' + '=' * 60)
print('书体列表:')
print('=' * 60)
for i, script in enumerate(sorted(entities['书体'])):
    print(f'  {i+1}. {script}')

print('\n' + '=' * 60)
print('时间列表:')
print('=' * 60)
for i, time in enumerate(sorted(entities['时间'])):
    print(f'  {i+1}. {time}')

print(f'\n已保存到 命名实体_v2.csv')
