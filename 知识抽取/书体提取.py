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

def clean_name(name):
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'生卒年不详', '', name)
    return name.strip()

def extract_script_styles(text):
    script_styles = []
    
    patterns = [
        (r'小篆', '小篆'),
        (r'大篆', '大篆'),
        (r'篆书', '篆书'),
        (r'悬针篆', '悬针篆'),
        (r'剪刀篆', '剪刀篆'),
        (r'金错书', '金错书'),
        (r'铁线篆', '铁线篆'),
        (r'章草', '章草'),
        (r'今草', '今草'),
        (r'狂草', '狂草'),
        (r'草书', '草书'),
        (r'行书', '行书'),
        (r'行草', '行草'),
        (r'楷书', '楷书'),
        (r'真书', '楷书'),
        (r'正书', '楷书'),
        (r'隶书', '隶书'),
        (r'八分', '八分书'),
        (r'飞白', '飞白书'),
        (r'甲骨文', '甲骨文'),
        (r'金文', '金文'),
        (r'石鼓文', '石鼓文'),
        (r'魏碑', '魏碑'),
        (r'瘦金体', '瘦金体'),
    ]
    
    for pattern, style in patterns:
        if re.search(pattern, text):
            if style not in script_styles:
                script_styles.append(style)
    
    return script_styles

with open('中国历代书法家图表.md', 'r', encoding='utf-8') as f:
    content = f.read()

tables = re.findall(r'<table>.*?</table>', content, re.DOTALL)
parser = TableParser()
parser.feed(tables[0])

triples = []
script_style_stats = {}

for row in parser.rows[1:]:
    if len(row) >= 7:
        name = clean_name(row[1])
        art_feature = row[5]
        
        if name and len(name) >= 2:
            styles = extract_script_styles(art_feature)
            for style in styles:
                triples.append((name, '擅长书体', style))
                script_style_stats[style] = script_style_stats.get(style, 0) + 1

with open('书体三元组.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['主体', '关系', '客体'])
    for triple in triples:
        writer.writerow(triple)

print(f'共提取 {len(triples)} 条书体三元组')
print(f'\n书体统计:')
for style, count in sorted(script_style_stats.items(), key=lambda x: -x[1]):
    print(f'  {style}: {count}人')

print(f'\n示例三元组:')
for t in triples[:20]:
    print(f'  {t[0]} -> {t[1]} -> {t[2]}')
