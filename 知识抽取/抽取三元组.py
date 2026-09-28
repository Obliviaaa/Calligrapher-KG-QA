# -*- coding: utf-8 -*-
import re
from html.parser import HTMLParser
import csv

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.rows = []
        self.cell_content = ''
        self.rowspan_cells = []
        
    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row = []
            for cell_val, remaining in self.rowspan_cells[:]:
                self.current_row.append(cell_val)
                if remaining > 1:
                    idx = self.rowspan_cells.index((cell_val, remaining))
                    self.rowspan_cells[idx] = (cell_val, remaining - 1)
                else:
                    self.rowspan_cells.remove((cell_val, remaining))
        elif tag == 'td' and self.in_row:
            self.in_cell = True
            self.cell_content = ''
            self.current_rowspan = 1
            for name, value in attrs:
                if name == 'rowspan':
                    self.current_rowspan = int(value)
                    
    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
        elif tag == 'tr' and self.in_row:
            self.in_row = False
            if self.current_row:
                self.rows.append(self.current_row)
        elif tag == 'td' and self.in_cell:
            self.in_cell = False
            self.current_row.append(self.cell_content.strip())
            if self.current_rowspan > 1:
                self.rowspan_cells.append((self.cell_content.strip(), self.current_rowspan - 1))
            
    def handle_data(self, data):
        if self.in_cell:
            self.cell_content += data

dynasty_names = set(['秦', '西汉', '东汉', '三国', '三国·魏', '三国·吴', '西晋', '东晋', '南朝', '南朝·宋', '南朝·齐', '南朝·梁', '南朝·陈', '北朝', '北魏', '东魏', '西魏', '北齐', '北周', '隋', '唐', '五代', '五代·梁', '五代·唐', '五代·晋', '五代·汉', '五代·周', '宋', '北宋', '南宋', '金', '金代', '元', '元代', '明', '明代', '清', '清代', '现代', '民国'])


# 从 NER 结果读取人名
def load_persons_from_ner(ner_csv_path):
    persons = set()
    with open(ner_csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['实体类型'] == '人名':
                persons.add(row['实体名称'])
    return persons
def extract_birth_death(raw_name):
    """从书家列提取生卒年信息"""
    birth = None
    death = None
    
    # 匹配格式: 名字(生年—卒年) 或 名字(?—卒年) 或 名字(生年—?)
    # 支持复杂格式如: 王羲之(303—361,一作321—379)
    match = re.search(r'\((\?|\d+)(—|—|-)(\?|\d+|前\d+)', raw_name)
    if match:
        birth_str = match.group(1)
        death_str = match.group(3)
        
        if birth_str != '?':
            birth = birth_str
        if death_str != '?' and not death_str.startswith('?'):
            death = death_str
    
    # 匹配格式: 名字生卒年不详
    if '生卒年不详' in raw_name:
        pass  # birth和death都为None
    
    return birth, death

def clean_name(name):
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'生卒年不详', '', name)
    name = name.strip()
    return name

famous_calligraphers = load_persons_from_ner('命名实体.csv')



def smart_split_names(text):
    if not text:
        return []
    text = text.strip()
    if not text:
        return []
    names = []
    for name in famous_calligraphers:
        if name in text:
            names.append(name)
    if names:
        seen = set()
        result = []
        for n in names:
            if n not in seen:
                seen.add(n)
                result.append(n)
        return result
    if '，' in text or '、' in text or ',' in text or ' ' in text:
        parts = re.split(r'[，,、\s]+', text)
        return [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]
    result = []
    for i in range(0, len(text), 2):
        if i + 2 <= len(text):
            result.append(text[i:i+2])
    if len(text) % 2 == 1 and result:
        last = result.pop()
        result.append(last + text[-1])
    return [n for n in result if len(n) >= 2]

def extract_works(text):
    if not text:
        return []
    works = re.findall(r'《([^》]+)》', text)
    return [w for w in works if w]

def extract_works_from_art_feature(text):
    writings = []
    works = []
    if not text:
        return writings, works
    
    writing_patterns = [
        r'著《([^》]+)》',
        r'撰《([^》]+)》',
        r'编《([^》]+)》',
        r'辑《([^》]+)》',
    ]
    
    work_patterns = [
        r'作《([^》]+)》',
        r'书《([^》]+)》',
        r'写《([^》]+)》',
    ]
    
    for pattern in writing_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if m and m not in writings:
                writings.append(m)
    
    for pattern in work_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if m and m not in works:
                works.append(m)
    
    return writings, works

with open('中国历代书法家图表.md', 'r', encoding='utf-8') as f:
    content = f.read()

tables = re.findall(r'<table>.*?</table>', content, re.DOTALL)
parser = TableParser()
parser.feed(tables[0])

calligraphers = []
for row in parser.rows:
    if len(row) >= 12 and row[0] != '年代':
        dynasty = row[0]
        raw_name = row[1]
        if raw_name:
            # 先提取生卒年，再清理名字
            birth, death = extract_birth_death(raw_name)
            cleaned = clean_name(raw_name)
            if cleaned and len(cleaned) >= 2 and cleaned not in dynasty_names:
                c = {
                    'dynasty': dynasty,
                    'raw_name': raw_name,
                    'name': cleaned,
                    'birth': birth,
                    'death': death,
                    'style_name': row[2],
                    'hometown': row[3],
                    'position': row[4],
                    'art_feature': row[5],
                    'style': row[6],
                    'other_skill': row[7],
                    'works': row[8],
                    'writings': row[9],
                    'teachers': row[10],
                    'influenced': row[11] if len(row) > 11 else ''
                }
                calligraphers.append(c)

print(f'共找到 {len(calligraphers)} 位书法家')

check_names = ['徐悲鸿', '白蕉', '启功', '沈尹默', '林散之', '齐白石', '于右任', '黄宾虹', '张大千']
found = []
for c in calligraphers:
    for name in check_names:
        if name == c['name']:
            found.append(name)
            print(f'找到: {c["name"]}, 朝代: {c["dynasty"]}')

print(f'\n找到的书家: {set(found)}')
missing = [n for n in check_names if n not in found]
print(f'未找到的书家: {missing}')

triples = []
for c in calligraphers:
    name = c['name']
    
    if c['dynasty']:
        triples.append((name, '所属朝代', c['dynasty']))
    
    # 添加生卒年三元组
    if c['birth']:
        triples.append((name, '生年', c['birth']))
    if c['death']:
        triples.append((name, '卒年', c['death']))
    
    if c['style_name']:
        style = c['style_name'].replace('。', '').strip()
        if style and len(style) > 1:
            triples.append((name, '字号', style))
    
    if c['hometown']:
        hometown = c['hometown'].replace('。', '').strip()
        if hometown and len(hometown) > 1:
            triples.append((name, '籍贯', hometown))
    
    if c['position']:
        position = c['position'].replace('。', '').strip()
        if position and len(position) > 1:
            triples.append((name, '官衔', position))
    
    works = extract_works(c['works'])
    for work in works:
        triples.append((name, '代表作品', work))
    
    writings = extract_works(c['writings'])
    for writing in writings:
        triples.append((name, '著述', writing))
    
    art_writings, art_works = extract_works_from_art_feature(c['art_feature'])
    for writing in art_writings:
        if writing not in writings:
            triples.append((name, '著述', writing))
    for work in art_works:
        if work not in works:
            triples.append((name, '代表作品', work))
    
    teachers = smart_split_names(c['teachers'])
    for teacher in teachers:
        triples.append((name, '师承', teacher))
    
    influenced = smart_split_names(c['influenced'])
    for person in influenced:
        triples.append((name, '影响', person))

with open('书法家三元组.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['主体', '关系', '客体'])
    for triple in triples:
        writer.writerow(triple)

print(f'\n共生成 {len(triples)} 条三元组')
print('已保存到 书法家三元组_完整版.csv')

print('\n=== 徐悲鸿相关三元组 ===')
xu_triples = [t for t in triples if t[0] == '徐悲鸿']
for t in xu_triples:
    print(f'  {t[0]} -> {t[1]} -> {t[2][:50]}...' if len(t[2]) > 50 else f'  {t[0]} -> {t[1]} -> {t[2]}')

print('\n=== 白蕉相关三元组 ===')
baijiao_triples = [t for t in triples if t[0] == '白蕉']
for t in baijiao_triples:
    print(f'  {t[0]} -> {t[1]} -> {t[2][:50]}...' if len(t[2]) > 50 else f'  {t[0]} -> {t[1]} -> {t[2]}')

print('\n=== 虞世南师承关系 ===')
yu_triples = [t for t in triples if t[0] == '虞世南' and t[1] == '师承']
for t in yu_triples:
    print(f'  {t[0]} -> {t[1]} -> {t[2]}')

print('\n=== 李斯影响关系 ===')
lisi_triples = [t for t in triples if t[0] == '李斯' and t[1] == '影响']
for t in lisi_triples:
    print(f'  {t[0]} -> {t[1]} -> {t[2]}')
