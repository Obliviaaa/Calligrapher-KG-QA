# -*- coding: utf-8 -*-
"""
从籍贯列中抽取亲属关系（精确版）
"""

import csv
import re

def is_valid_name(name):
    """检查是否是有效的亲属名字"""
    # 过滤掉包含特殊字符的名字
    invalid_chars = ['(', ')', '）', '（', ',', '，', '、', ':', '：', '"', '"', ' ', '人', '兴', '镇', '江', '大', '司', '马', '相', '丞', '多', '年', '亲', '王', '奕', '欣', '七', '五', '十', '八', '世', '曾', '外', '长', '族', '寓', '上', '海', '侍', '郎', '妻', '三']
    for c in invalid_chars:
        if c in name:
            return False
    # 过滤掉太短或太长的名字
    if len(name) < 2 or len(name) > 5:
        return False
    return True

def clean_name(name):
    """清理亲属名字"""
    # 移除前缀（如"大司马"、"丞相"等）
    prefixes = ['大司马', '丞相', '多年', '亲王', '侍郎', '苏州', '寓上海', '周惕', '王芑', '冯景夏', '陈士璠', '江声', '钱玉炯', '翁方纲', '朱彝尊', '米万钟', '虞允文', '辽太祖长', '耶律倍', '钟繇', '王导', '王羲之', '王世贞', '吴大澂', '朱文嵘', '曹锐', '唐顺之', '赵孟頫', '文徵明', '归有光', '祝允明', '王锡爵', '师古', '杜佑', '苏洵', '宋濂', '严讷', '文徵明', '虞允文', '钱玉炯', '朱彝尊', '米万钟', '翁方纲', '陈士璠', '江声', '冯景夏', '周惕', '王芑', '曹锐', '朱文嵘', '唐顺之', '赵孟頫', '祝允明', '王锡爵', '师古', '杜佑', '苏洵', '宋濂', '严讷', '文徵明', '归有光', '王世贞', '吴大澂', '辽太祖', '耶律倍', '钟繇', '王导', '王羲之', '虞允文', '钱玉炯', '朱彝尊', '米万钟', '翁方纲', '陈士璠', '江声', '冯景夏', '周惕', '王芑', '曹锐', '朱文嵘', '唐顺之', '赵孟頫', '祝允明', '王锡爵', '师古', '杜佑', '苏洵', '宋濂', '严讷', '文徵明', '归有光', '王世贞', '吴大澂']
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name

def extract_kinship_from_hometown(csv_path: str, output_path: str):
    """从籍贯列中抽取亲属关系"""
    
    kinship_triples = []
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject = row['主体']
            relation = row['关系']
            obj = row['客体']
            
            # 只处理籍贯列
            if relation == '籍贯':
                # 亲属关系模式
                
                # 1. "XX长子" - XX的长子
                matches = re.findall(r'([^\s,，人()）（]{2,5})长子', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '长子'
                        })
                
                # 2. "XX次子" / "XX仲子" - XX的次子
                matches = re.findall(r'([^\s,，人()）（]{2,5})(次子|仲子)', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '次子'
                        })
                
                # 3. "XX第X子" - XX的儿子
                matches = re.findall(r'([^\s,，人()）（]{2,5})第[一二三四五六七八九十]+子', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '儿子'
                        })
                
                # 4. "XX季弟" - XX的季弟
                matches = re.findall(r'([^\s,，人()）（]{2,5})季弟', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '弟弟'
                        })
                
                # 5. "XX从弟" - XX的堂弟
                matches = re.findall(r'([^\s,，人()）（]{2,5})从弟', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '堂弟'
                        })
                
                # 6. "XX弟" - XX的弟弟（排除"季弟"、"从弟"）
                cleaned_obj = re.sub(r'[^\s,，人()）（]{2,5}(季弟|从弟)', '', obj)
                matches = re.findall(r'([^\s,，人()）（]{2,5})弟', cleaned_obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '弟弟'
                        })
                
                # 7. "XX兄" - XX的哥哥
                matches = re.findall(r'([^\s,，人()）（]{2,5})兄', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '哥哥'
                        })
                
                # 8. "XX孙" - XX的孙子
                matches = re.findall(r'([^\s,，人()）（之姊]{2,5})孙', obj)
                for match in matches:
                    if is_valid_name(match) and '之姊' not in match:
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '孙子'
                        })
                
                # 9. "XX侄" / "XX侄女" - XX的侄子/侄女
                matches = re.findall(r'([^\s,，人()）（]{2,5})侄(?:女)?', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '侄子'
                        })
                
                # 10. "XX外孙" - XX的外孙
                matches = re.findall(r'([^\s,，人()）（]{2,5})外孙', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '外孙'
                        })
                
                # 11. "XX子" - XX的儿子（排除已匹配的模式）
                cleaned_obj = obj
                cleaned_obj = re.sub(r'[^\s,，人()）（]{2,5}(长子|次子|仲子|第[一二三四五六七八九十]+子|季弟|从弟|弟|兄|孙|侄|外孙|曾孙)', '', cleaned_obj)
                matches = re.findall(r'([^\s,，人()）（]{2,5})子', cleaned_obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '儿子'
                        })
                
                # 12. "XX女" - XX的女儿
                matches = re.findall(r'([^\s,，人()）（]{2,5})女', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '女儿'
                        })
                
                # 13. "XX曾孙" - XX的曾孙
                matches = re.findall(r'([^\s,，人()）（]{2,5})曾孙', obj)
                for match in matches:
                    if is_valid_name(match):
                        kinship_triples.append({
                            '主体': subject,
                            '关系': '亲属',
                            '客体': match,
                            '亲属类型': '曾孙'
                        })
    
    # 去重
    unique_triples = []
    seen = set()
    for triple in kinship_triples:
        key = (triple['主体'], triple['客体'])
        if key not in seen:
            seen.add(key)
            unique_triples.append(triple)
    
    # 保存结果
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['主体', '关系', '客体', '亲属类型'])
        writer.writeheader()
        for triple in unique_triples:
            writer.writerow(triple)
    
    return unique_triples


if __name__ == "__main__":
    csv_path = r"D:\奥义 学习\计算机\知识图谱\大作业\知识抽取\书法家三元组.csv"
    output_path = r"D:\奥义 学习\计算机\知识图谱\大作业\知识抽取\亲属关系_籍贯抽取.csv"
    
    print("正在从籍贯列中抽取亲属关系...")
    kinship_triples = extract_kinship_from_hometown(csv_path, output_path)
    
    print(f"\n抽取到 {len(kinship_triples)} 条亲属关系")
    print("\n全部结果：")
    for triple in kinship_triples:
        print(f"  {triple['主体']} → {triple['客体']} ({triple['亲属类型']})")