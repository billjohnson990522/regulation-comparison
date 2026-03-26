#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
法规章节结构提取脚本
提取一级标题"第一章"、二级标题"第一条"、三级标题"（一）"的结构和内容
每个 number 的 content 包含从该标题到下一个同级标题之间的所有内容
"""

import re
import json
import sys
from pathlib import Path


def clean_spaces(text):
    """清理所有全角和半角空格"""
    if not text:
        return ''
    # 移除全角空格 (\u3000) 和半角空格
    return text.replace('\u3000', '').replace(' ', '')


def extract_regulation_structure(text):
    """
    提取法规的章节结构
    每个 number 的 content 包含从该标题到下一个同级标题之间的所有内容
    """
    lines = text.split('\n')
    
    # 定义正则表达式模式
    # 中文数字范围：零一二三四五六七八九十百千万
    chinese_num = '零一二三四五六七八九十百千万'
    
    # 一级标题：第一章、第二章等
    level1_pattern = re.compile(r'^第[' + chinese_num + r']+章')
    # 二级标题：第一条、第二条等
    level2_pattern = re.compile(r'^第[' + chinese_num + r']+条')
    # 三级标题：（一）、（二）等（使用全角括号）
    level3_pattern = re.compile(r'^（[' + chinese_num + r']+）')
    
    # 首先，找出所有标题的位置和类型
    all_headers = []
    
    for i, line in enumerate(lines):
        # 去除行首尾空白和全角空格
        line_stripped = clean_spaces(line.strip())
        if not line_stripped:
            continue
        
        # 检查一级标题
        match = level1_pattern.match(line_stripped)
        if match:
            number = match.group()
            # 提取标题内容（章节名称，如"总则"）
            title = line_stripped[len(number):].strip()
            all_headers.append({
                'level': 1,
                'number': number,
                'title': title,
                'line_num': i
            })
            continue
        
        # 检查二级标题
        match = level2_pattern.match(line_stripped)
        if match:
            number = match.group()
            # 提取标题内容（条款内容）
            title = line_stripped[len(number):].strip()
            all_headers.append({
                'level': 2,
                'number': number,
                'title': title,
                'line_num': i
            })
            continue
        
        # 检查三级标题
        match = level3_pattern.match(line_stripped)
        if match:
            number = match.group(0)
            # 提取标题内容
            title = line_stripped[len(number):].strip()
            all_headers.append({
                'level': 3,
                'number': number,
                'title': title,
                'line_num': i
            })
            continue
    
    # 构建树形结构
    result = []
    stack = []  # 用于跟踪当前的层级结构
    
    for i, header in enumerate(all_headers):
        # 确定这个标题的 content 范围（到下一个同级或更高级标题之前）
        start_line = header['line_num']
        end_line = len(lines)
        
        # 找到下一个同级或更高级标题的位置
        for j in range(i + 1, len(all_headers)):
            if all_headers[j]['level'] <= header['level']:
                end_line = all_headers[j]['line_num']
                break
        
        # 提取 content（从当前标题行之后到结束行之前）
        content_lines = []
        for j in range(start_line + 1, end_line):
            line = clean_spaces(lines[j].strip())
            if line:
                content_lines.append(line)
        
        content = '\n'.join(content_lines)
        
        node = {
            'level': header['level'],
            'number': header['number'],
            'title': header.get('title', ''),
            'content': content,
            'children': []
        }
        
        # 根据层级关系确定父节点
        while stack and stack[-1]['level'] >= header['level']:
            stack.pop()
        
        if stack:
            # 有父节点，添加到父节点的 children 中
            stack[-1]['children'].append(node)
        else:
            # 没有父节点，添加到结果中
            result.append(node)
        
        # 将当前节点压入栈
        stack.append(node)
    
    return result


def process_file(input_path, output_path=None):
    """
    处理单个文件
    """
    # 读取输入文件
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # 提取结构
    structure = extract_regulation_structure(text)
    
    # 确定输出路径
    if output_path is None:
        input_path = Path(input_path)
        output_path = input_path.parent / f"{input_path.stem}.json"
    
    # 保存为 JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)
    
    return output_path


def main():
    if len(sys.argv) < 2:
        print("用法：python extract_regulation.py <输入文件> [输出文件]")
        print("示例：python extract_regulation.py backend/text/2025.txt")
        print("       python extract_regulation.py backend/text/2025.txt output.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        output_path = process_file(input_file, output_file)
        print(f"✓ 提取完成：{output_path}")
        
        # 显示统计信息
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        level1_count = len(data)
        level2_count = sum(len(item.get('children', [])) for item in data)
        level3_count = sum(
            len(child.get('children', [])) 
            for item in data 
            for child in item.get('children', [])
        )
        
        print(f"  - 一级标题（章）：{level1_count} 个")
        print(f"  - 二级标题（条）：{level2_count} 个")
        print(f"  - 三级标题（款）：{level3_count} 个")
        
    except FileNotFoundError:
        print(f"✗ 错误：文件不存在 - {input_file}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ 错误：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
