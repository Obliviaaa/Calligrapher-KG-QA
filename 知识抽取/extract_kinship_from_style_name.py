# -*- coding: utf-8 -*-
"""
从字号列中二次抽取亲属关系（最终版）
"""

import csv
import re

def extract_kinship_from_style_name(csv_path: str, output_path: str):
    """从字号列中抽取亲属关系"""
    
    kinship_triples = []
    
    # 已知书法家名单（用于验证亲属名字）
    known_calligraphers = set()
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            known_calligraphers.add(row['主体'])
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject = row['主体']
            relation = row['关系']
            obj = row['客体']
            
            # 只处理字号列
            if relation == '字号':
                # 亲属关系模式
                # 格式：人名 + 亲属称谓
                
                # 1. "XX从子" - XX的侄子
                # 如"王导从子" → 王导是亲属
                # 需要确保XX是有效的人名（2-4个字，不含"字"、"号"等）
                matches = re.findall(r'([^\s,，字号逸少夫尧]{2,4})从子', obj)
                for match in matches:
                    # 验证是否是有效的人名
                    if len(match) >= 2 and len(match) <= 4:
                        # 检查是否包含无效字符
                        if not any(c in match for c in ['字', '号', '逸', '少', '夫', '尧', '一', '作']):
                            kinship_triples.append({
                                '主体': subject,
                                '关系': '亲属',
                                '客体': match,
                                '亲属类型': '侄子'
                            })
                
                # 2. "XX次子" - XX的次子
                # 如"范仲淹次子" → 范仲淹是亲属
                matches = re.findall(r'([^\s,，字号逸少夫尧]{2,4})次子', obj)
                for match in matches:
                    if len(match) >= 2 and len(match) <= 4:
                        if not any(c in match for c in ['字', '号', '逸', '少', '夫', '尧', '一', '作']):
                            kinship_triples.append({
                                '主体': subject,
                                '关系': '亲属',
                                '客体': match,
                                '亲属类型': '次子'
                            })
                
                # 3. "XX嫡长子" - XX的嫡长子
                # 如"明仁宗嫡长子" → 明仁宗是亲属
                matches = re.findall(r'([^\s,，字号逸少夫尧]{2,5})嫡长子', obj)
                for match in matches:
                    if len(match) >= 2 and len(match) <= 5:
                        if not any(c in match for c in ['字', '号', '逸', '少', '夫', '尧', '一', '作']):
                            kinship_triples.append({
                                '主体': subject,
                                '关系': '亲属',
                                '客体': match,
                                '亲属类型': '嫡长子'
                            })
                
                # 4. "XX长子" - XX的长子
                matches = re.findall(r'([^\s,，字号逸少夫尧嫡]{2,4})长子', obj)
                for match in matches:
                    if len(match) >= 2 and len(match) <= 4:
                        if not any(c in match for c in ['字', '号', '逸', '少', '夫', '尧', '一', '作', '嫡']):
                            kinship_triples.append({
                                '主体': subject,
                                '关系': '亲属',
                                '客体': match,
                                '亲属类型': '长子'
                            })
                
                # 5. "XX子" - XX的儿子
                # 如"王旷子" → 王旷是亲属
                # 需要排除"字子XX"、"号XX子"等字号情况
                # 策略：先移除字号部分，再匹配
                
                # 移除"字子XX"（如"字子玉"、"字子敬"）
                cleaned_obj = re.sub(r'字子[^\s,，]{1,2}', '', obj)
                # 移除"号XX子"（如"号贞居子"、"号穀庵子"）
                cleaned_obj = re.sub(r'号[^\s,，]{1,4}子', '', cleaned_obj)
                # 移除"字XX"（如"字逸少"、"字尧夫"）
                cleaned_obj = re.sub(r'字[^\s,，]{2,4}', '', cleaned_obj)
                # 移除"XX次子"、"XX嫡长子"、"XX从子"（避免重复匹配）
                cleaned_obj = re.sub(r'[^\s,，]{2,5}(次子|嫡长子|从子)', '', cleaned_obj)
                
                # 然后匹配"XX子"
                matches = re.findall(r'([^\s,，字号]{2,4})子', cleaned_obj)
                for match in matches:
                    # 过滤掉常见的字号词
                    exclude_words = ['贞居', '穀庵', '多暇', '青丘', '云林', '大涤', '玄宴', 
                                     '二水', '芥', '未孩', '天隐', '木头老', '且渠', '叔子',
                                     '伯雨', '元镇', '季迪', '君谦', '公绶', '懋学', '伯度',
                                     '淹次', '仁宗嫡长', '长、观复', '明莫如忠', '澳、玄宴',
                                     '二水、芥', '弃、未孩', '人、天隐', '、木头老', '后改名师',
                                     '嗣元、', '宗第十一']
                    if match in exclude_words:
                        continue
                    # 过滤掉包含特殊字符的匹配
                    if any(c in match for c in ['、', '，', ',', '宗', '嫡', '次', '明', '澳', '弃', '人']):
                        continue
                    if len(match) >= 2 and len(match) <= 4:
                        if not any(c in match for c in ['字', '号', '逸', '少', '夫', '尧', '一', '作', '林', '云']):
                            kinship_triples.append({
                                '主体': subject,
                                '关系': '亲属',
                                '客体': match,
                                '亲属类型': '儿子'
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
    output_path = r"D:\奥义 学习\计算机\知识图谱\大作业\知识抽取\亲属关系_二次抽取.csv"
    
    print("正在从字号列中抽取亲属关系...")
    kinship_triples = extract_kinship_from_style_name(csv_path, output_path)
    
    print(f"\n抽取到 {len(kinship_triples)} 条亲属关系")
    print("\n全部结果：")
    for triple in kinship_triples:
        print(f"  {triple['主体']} → {triple['客体']} ({triple['亲属类型']})")