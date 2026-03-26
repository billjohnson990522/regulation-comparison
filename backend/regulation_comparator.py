"""
法规对比模块
用于对比新老法规的差异，包括新增、删除、修改等变更检测
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import difflib
from chinoapi import simple_chat


class ChangeType(Enum):
    """变更类型枚举"""
    ADDED = "added"           # 新增
    DELETED = "deleted"       # 删除
    MODIFIED = "modified"     # 修改
    UNCHANGED = "unchanged"   # 未变化
    MOVED = "moved"           # 移动（编号变化但内容相似）


@dataclass
class DiffResult:
    """差异对比结果"""
    change_type: ChangeType
    old_item: Optional[Dict] = None
    new_item: Optional[Dict] = None
    title_diff: Optional[str] = None      # title差异详情
    content_diff: Optional[str] = None    # content差异详情
    number_changed: bool = False          # 编号是否变化
    similarity_score: float = 0.0         # 相似度分数
    children_diff: List['DiffResult'] = field(default_factory=list)
    ai_summary: Optional[str] = None      # AI生成的变更总结
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "change_type": self.change_type.value,
            "old_number": self.old_item.get("number") if self.old_item else None,
            "new_number": self.new_item.get("number") if self.new_item else None,
            "old_title": self.old_item.get("title") if self.old_item else None,
            "new_title": self.new_item.get("title") if self.new_item else None,
            "title_diff": self.title_diff,
            "content_diff": self.content_diff,
            "number_changed": self.number_changed,
            "similarity_score": self.similarity_score,
            "children_count": len(self.children_diff),
            "children_diff": [child.to_dict() for child in self.children_diff],
            "ai_summary": self.ai_summary
        }


class RegulationComparator:
    """法规对比器"""
    
    def __init__(self, old_data: List[Dict], new_data: List[Dict]):
        """
        初始化对比器
        
        Args:
            old_data: 老法规数据（JSON格式）
            new_data: 新法规数据（JSON格式）
        """
        self.old_data = old_data
        self.new_data = new_data
        self.diff_results: List[DiffResult] = []
        
    def compare(self) -> List[DiffResult]:
        """
        执行完整的法规对比
        
        对比流程：
        1. 一级标题对比：检查章节的新增、删除、修改
        2. 二级标题对比：检查条款的新增、删除、修改
        3. 三级标题对比：检查款项的新增、删除、修改，并对比content内容
        
        Returns:
            对比结果列表
        """
        print("=" * 60)
        print("开始法规对比分析")
        print("=" * 60)
        
        # 第一步：对比一级标题（章节）
        print("\n【第一步】对比一级标题（章节）...")
        self.diff_results = self._compare_level(self.old_data, self.new_data, level=1)
        
        # 打印对比摘要
        self._print_summary()
        
        return self.diff_results
    
    def _compare_level(self, old_items: List[Dict], new_items: List[Dict], 
                        level: int, parent_context: str = "") -> List[DiffResult]:
        """
        对比指定层级的标题
        
        核心算法：
        1. 首先按number精确匹配
        2. 对于无法匹配的项目，使用title相似度匹配
        3. 记录新增、删除、修改的情况
        
        Args:
            old_items: 老法规该层级的所有项目
            new_items: 新法规该层级的所有项目
            level: 当前层级（1/2/3）
            parent_context: 父级上下文信息（用于日志）
            
        Returns:
            该层级的对比结果列表
        """
        results = []
        
        # 创建索引便于快速查找
        old_by_number = {item["number"]: item for item in old_items}
        new_by_number = {item["number"]: item for item in new_items}
        
        # 记录已匹配的项目
        matched_old = set()
        matched_new = set()
        
        # 第一轮：按编号精确匹配
        for number, old_item in old_by_number.items():
            if number in new_by_number:
                new_item = new_by_number[number]
                matched_old.add(number)
                matched_new.add(number)
                
                # 检查title和content是否有变化
                result = self._compare_items(old_item, new_item, level, parent_context)
                results.append(result)
        
        # 第二轮：处理未匹配的老法规项目（可能删除或移动）
        unmatched_old = [item for item in old_items if item["number"] not in matched_old]
        unmatched_new = [item for item in new_items if item["number"] not in matched_new]
        
        # 使用相似度匹配来检测移动或修改
        for old_item in unmatched_old:
            best_match = None
            best_score = 0.0
            
            for new_item in unmatched_new:
                if new_item["number"] in matched_new:
                    continue
                    
                # 计算title相似度
                score = self._calculate_similarity(old_item["title"], new_item["title"])
                
                if score > best_score and score >= 0.5:  # 相似度阈值50%
                    best_score = score
                    best_match = new_item
            
            if best_match:
                # 找到相似项，可能是修改或移动
                matched_new.add(best_match["number"])
                result = self._compare_items(old_item, best_match, level, parent_context, best_score)
                result.number_changed = (old_item["number"] != best_match["number"])
                results.append(result)
            else:
                # 未找到匹配项，判定为删除
                result = DiffResult(
                    change_type=ChangeType.DELETED,
                    old_item=old_item,
                    new_item=None
                )
                results.append(result)
                self._log_change(level, "删除", old_item["number"], old_item["title"][:50], parent_context)
        
        # 第三轮：处理未匹配的新法规项目（新增）
        for new_item in unmatched_new:
            if new_item["number"] not in matched_new:
                result = DiffResult(
                    change_type=ChangeType.ADDED,
                    old_item=None,
                    new_item=new_item
                )
                results.append(result)
                self._log_change(level, "新增", new_item["number"], new_item["title"][:50], parent_context)
        
        # 按编号排序结果
        results.sort(key=lambda x: self._extract_number_order(x.old_item or x.new_item))
        
        return results
    
    def _compare_items(self, old_item: Dict, new_item: Dict, level: int, 
                       parent_context: str, similarity_score: float = 1.0) -> DiffResult:
        """
        对比两个项目（编号相同或相似）
        
        根据层级决定对比内容：
        - 一级标题（章）：只对比title
        - 二级标题（条）：只对比title
        - 三级标题（款）：对比title和content
        - 四级标题（目）：对比title和content
        """
        # 检查title是否变化
        title_changed = old_item["title"] != new_item["title"]
        title_diff = None
        
        if title_changed:
            title_diff = self._generate_diff(old_item["title"], new_item["title"])
        
        # 检查content是否变化（三级标题和四级标题需要检查）
        content_changed = False
        content_diff = None
        
        if level >= 3:  # 三级标题（款）和四级标题（目）都需要检查content
            old_content = old_item.get("content", "")
            new_content = new_item.get("content", "")
            content_changed = old_content != new_content
            
            if content_changed:
                content_diff = self._generate_diff(old_content, new_content)
        
        # 判断变更类型
        if title_changed or content_changed:
            change_type = ChangeType.MODIFIED
            self._log_change(level, "修改", f"{old_item['number']}→{new_item['number']}", 
                           old_item["title"][:50], parent_context)
        else:
            change_type = ChangeType.UNCHANGED
        
        # 递归对比子项
        children_diff = []
        if old_item.get("children") or new_item.get("children"):
            old_children = old_item.get("children", [])
            new_children = new_item.get("children", [])
            new_parent_context = f"{parent_context} > {old_item['number']}"
            children_diff = self._compare_level(old_children, new_children, level + 1, new_parent_context)
        
        return DiffResult(
            change_type=change_type,
            old_item=old_item,
            new_item=new_item,
            title_diff=title_diff,
            content_diff=content_diff,
            similarity_score=similarity_score,
            children_diff=children_diff
        )
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        使用difflib的SequenceMatcher计算相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            相似度分数（0-1之间）
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # 使用SequenceMatcher计算相似度
        matcher = difflib.SequenceMatcher(None, text1, text2)
        return matcher.ratio()
    
    def _generate_diff(self, old_text: str, new_text: str) -> str:
        """
        生成两个文本的差异对比
        
        Args:
            old_text: 原文本
            new_text: 新文本
            
        Returns:
            差异描述字符串
        """
        if not old_text:
            return f"[新增] {new_text}"
        if not new_text:
            return f"[删除] {old_text}"
        
        # 使用difflib生成差异
        diff = list(difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile='原法规',
            tofile='新法规',
            lineterm=''
        ))
        
        return ''.join(diff)
    
    def _extract_number_order(self, item: Dict) -> int:
        """
        从编号中提取排序用的数字
        
        例如：第一条 -> 1, 第十条 -> 10, 第五章 -> 5, 1. -> 1, 2、 -> 2
        
        Args:
            item: 法规项目
            
        Returns:
            排序用的数字
        """
        if not item:
            return 999999
            
        number = item.get("number", "")
        
        # 中文数字映射
        chinese_nums = {
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
            "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
            "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
            "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24, "二十五": 25,
            "二十六": 26, "二十七": 27, "二十八": 28, "二十九": 29, "三十": 30
        }
        
        # 尝试提取中文数字
        import re
        
        # 匹配"第X章"或"第X条"（一级、二级标题）
        match = re.search(r'第(.+?)(章|条)', number)
        if match:
            cn_num = match.group(1)
            return chinese_nums.get(cn_num, 999)
        
        # 匹配"（X）"格式的三级标题（款）
        match = re.search(r'（(.+?)）', number)
        if match:
            cn_num = match.group(1)
            return chinese_nums.get(cn_num, 999)
        
        # 匹配四级标题（目）的格式：1. 2. 1、2、 1. 2. 等
        # 格式1: "1." "2." "10." 等数字加点
        match = re.search(r'^(\d+)\.$', number.strip())
        if match:
            return int(match.group(1))
        
        # 格式2: "1、" "2、" "10、" 等数字加顿号
        match = re.search(r'^(\d+）、$', number.strip())
        if match:
            return int(match.group(1))
        
        # 格式3: 纯数字
        match = re.search(r'^(\d+)$', number.strip())
        if match:
            return int(match.group(1))
        
        return 999
    
    def _log_change(self, level: int, change_type: str, number: str, title_preview: str, context: str):
        """
        记录变更日志
        
        Args:
            level: 层级
            change_type: 变更类型
            number: 编号
            title_preview: 标题预览
            context: 上下文
        """
        level_names = {
            1: "一级标题",  # 章
            2: "二级标题",  # 条
            3: "三级标题",  # 款
            4: "四级标题"   # 目
        }
        level_name = level_names.get(level, f"{level}级标题")
        
        if context:
            print(f"  [{level_name}] {change_type}: {number} - {title_preview}... (位置: {context})")
        else:
            print(f"  [{level_name}] {change_type}: {number} - {title_preview}...")
    
    def _print_summary(self):
        """打印对比摘要"""
        print("\n" + "=" * 60)
        print("对比摘要")
        print("=" * 60)
        
        stats = {
            "added": 0,
            "deleted": 0,
            "modified": 0,
            "unchanged": 0
        }
        
        def count_changes(results: List[DiffResult]):
            for result in results:
                stats[result.change_type.value] += 1
                if result.children_diff:
                    count_changes(result.children_diff)
        
        count_changes(self.diff_results)
        
        print(f"  新增项目: {stats['added']}")
        print(f"  删除项目: {stats['deleted']}")
        print(f"  修改项目: {stats['modified']}")
        print(f"  未变化项目: {stats['unchanged']}")
        print("=" * 60)
    
    def export_results(self, output_path: str):
        """
        导出对比结果到JSON文件
        
        Args:
            output_path: 输出文件路径
        """
        results_data = [result.to_dict() for result in self.diff_results]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n对比结果已导出到: {output_path}")
    
    def generate_ai_summaries(self) -> None:
        """
        使用大模型为所有变动的条款生成变更总结
        
        按章节分组，同一章节的多个变更一起总结
        """
        print("\n" + "=" * 60)
        print("使用AI生成变更总结...")
        print("=" * 60)
        
        # 按章节分组收集变更项
        changes_by_chapter: Dict[str, List[DiffResult]] = {}
        
        def collect_changes_by_chapter(results: List[DiffResult], chapter_info: str = ""):
            """按章节递归收集所有变更项"""
            for result in results:
                if result.change_type == ChangeType.UNCHANGED:
                    # 即使未变化，也要检查子项
                    if result.children_diff:
                        # 获取章节信息
                        if result.old_item:
                            new_chapter_info = f"{result.old_item.get('number', '')} {result.old_item.get('title', '')}"
                        elif result.new_item:
                            new_chapter_info = f"{result.new_item.get('number', '')} {result.new_item.get('title', '')}"
                        else:
                            new_chapter_info = chapter_info
                        collect_changes_by_chapter(result.children_diff, new_chapter_info)
                else:
                    # 需要总结的变更项，按章节分组
                    if chapter_info not in changes_by_chapter:
                        changes_by_chapter[chapter_info] = []
                    changes_by_chapter[chapter_info].append(result)
        
        collect_changes_by_chapter(self.diff_results)
        
        total_changes = sum(len(changes) for changes in changes_by_chapter.values())
        print(f"共发现 {len(changes_by_chapter)} 个章节有变更，总计 {total_changes} 处变更")
        
        # 按章节生成总结
        processed = 0
        for chapter_info, changes in changes_by_chapter.items():
            processed += 1
            print(f"\n正在处理第 {processed}/{len(changes_by_chapter)} 个章节: {chapter_info}")
            print(f"  该章节有 {len(changes)} 处变更")
            
            # 为该章节的所有变更生成总结
            self._generate_chapter_summaries(chapter_info, changes)
    
    def _generate_chapter_summaries(self, chapter_info: str, changes: List[DiffResult]) -> None:
        """
        为一个章节的所有变更生成AI总结
        
        Args:
            chapter_info: 章节信息
            changes: 该章节的所有变更列表
        """
        # 构建批量总结的提示词
        prompt = self._build_batch_summary_prompt(chapter_info, changes)
        
        if not prompt:
            return
        
        try:
            # 调用大模型
            response = simple_chat(prompt)
            
            if response:
                # 解析AI返回的总结，分配给各个变更
                self._parse_and_assign_summaries(response, changes)
                print(f"  AI批量总结完成")
            else:
                print(f"  AI返回为空，跳过")
                
        except Exception as e:
            print(f"  AI总结失败: {e}")
            # 失败时为每个变更单独生成总结
            for result in changes:
                result.ai_summary = f"[AI总结失败: {e}]"
    
    def _build_batch_summary_prompt(self, chapter_info: str, changes: List[DiffResult]) -> Optional[str]:
        """
        构建批量总结的提示词
        
        Args:
            chapter_info: 章节信息
            changes: 变更列表
            
        Returns:
            提示词字符串
        """
        change_type_cn = {
            ChangeType.ADDED: "新增",
            ChangeType.DELETED: "删除",
            ChangeType.MODIFIED: "修改"
        }
        
        # 构建变更列表
        changes_text = []
        for i, result in enumerate(changes, 1):
            change_type_str = change_type_cn.get(result.change_type, "变更")
            
            if result.change_type == ChangeType.ADDED and result.new_item:
                number = result.new_item.get("number", "")
                title = result.new_item.get("title", "")
                content = result.new_item.get("content", "")
                changes_text.append(f"""
【变更{i}】{change_type_str}
编号：{number}
标题：{title}
内容：{content if content else "无"}""")
                
            elif result.change_type == ChangeType.DELETED and result.old_item:
                number = result.old_item.get("number", "")
                title = result.old_item.get("title", "")
                content = result.old_item.get("content", "")
                changes_text.append(f"""
【变更{i}】{change_type_str}
编号：{number}
标题：{title}
内容：{content if content else "无"}""")
                
            elif result.change_type == ChangeType.MODIFIED and result.old_item and result.new_item:
                old_number = result.old_item.get("number", "")
                new_number = result.new_item.get("number", "")
                old_title = result.old_item.get("title", "")
                new_title = result.new_item.get("title", "")
                old_content = result.old_item.get("content", "")
                new_content = result.new_item.get("content", "")
                changes_text.append(f"""
【变更{i}】{change_type_str}
原编号：{old_number}
新编号：{new_number}
原标题：{old_title}
新标题：{new_title}
原内容：{old_content if old_content else "无"}
新内容：{new_content if new_content else "无"}""")
        
        all_changes = "\n".join(changes_text)
        
        prompt = f"""请分析以下法规变更并生成简洁的总结。

所属章节：{chapter_info}

变更列表：
{all_changes}

请为每个变更生成一句话总结。格式要求：
1. 说明这是哪个章节哪一条的变更
2. 明确指出具体变更内容，需要精确到字词
3. 每个总结控制在50字以内
4. 按顺序输出，每个总结占一行，格式为：【变更X】总结内容

示例输出：
【变更1】第一章第二条修改，适用主体范围表述调整，"农村信用社"改为"农村信用合作社"。
【变更2】第一章第二条新增第（六）项，增加"非银行支付机构"作为适用主体。
【变更3】第一章第二条新增第（六）项，增加了"中国人民银行确定并公布的从事金融业务的其他机构"作为适用主体。

请直接输出总结，不要有其他内容："""

        return prompt
    
    def _parse_and_assign_summaries(self, response: str, changes: List[DiffResult]) -> None:
        """
        解析AI返回的总结并分配给各个变更
        
        Args:
            response: AI返回的文本
            changes: 变更列表
        """
        import re
        
        # 按行分割
        lines = response.strip().split('\n')
        
        # 提取每个变更的总结
        summaries = {}
        for line in lines:
            # 匹配【变更X】格式
            match = re.search(r'【变更(\d+)】(.+)', line)
            if match:
                idx = int(match.group(1))
                summary = match.group(2).strip()
                summaries[idx] = summary
        
        # 分配总结给各个变更
        for i, result in enumerate(changes, 1):
            if i in summaries:
                result.ai_summary = summaries[i]
            else:
                # 如果没有匹配到，尝试使用整行
                if i <= len(lines):
                    result.ai_summary = lines[i-1].strip()
                else:
                    result.ai_summary = "[未能解析AI总结]"
    
    def generate_report(self, output_path: str, include_ai_summary: bool = True):
        """
        生成人类可读的对比报告
        
        Args:
            output_path: 输出文件路径
            include_ai_summary: 是否包含AI生成的总结
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("法规对比报告")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        def process_result(result: DiffResult, indent: int = 0, chapter_info: str = ""):
            prefix = "  " * indent
            
            if result.change_type == ChangeType.ADDED and result.new_item:
                report_lines.append(f"{prefix}【新增】{result.new_item['number']}")
                report_lines.append(f"{prefix}  标题: {result.new_item['title']}")
                if include_ai_summary and result.ai_summary:
                    report_lines.append(f"{prefix}  AI总结: {result.ai_summary}")
                    
            elif result.change_type == ChangeType.DELETED and result.old_item:
                report_lines.append(f"{prefix}【删除】{result.old_item['number']}")
                report_lines.append(f"{prefix}  标题: {result.old_item['title']}")
                if include_ai_summary and result.ai_summary:
                    report_lines.append(f"{prefix}  AI总结: {result.ai_summary}")
                    
            elif result.change_type == ChangeType.MODIFIED and result.old_item and result.new_item:
                old_num = result.old_item['number']
                new_num = result.new_item['number']
                num_str = f"{old_num} → {new_num}" if old_num != new_num else old_num
                report_lines.append(f"{prefix}【修改】{num_str}")
                
                if result.title_diff:
                    report_lines.append(f"{prefix}  标题变更:")
                    report_lines.append(f"{prefix}    原: {result.old_item['title'][:100]}...")
                    report_lines.append(f"{prefix}    新: {result.new_item['title'][:100]}...")
                
                if result.content_diff:
                    report_lines.append(f"{prefix}  内容变更:")
                    report_lines.append(f"{prefix}    原: {result.old_item.get('content', '')[:100]}...")
                    report_lines.append(f"{prefix}    新: {result.new_item.get('content', '')[:100]}...")
                
                if include_ai_summary and result.ai_summary:
                    report_lines.append(f"{prefix}  AI总结: {result.ai_summary}")
            
            # 处理子项
            for child in result.children_diff:
                # 获取当前章节信息
                if result.old_item:
                    current_chapter = f"{result.old_item.get('number', '')} {result.old_item.get('title', '')}"
                elif result.new_item:
                    current_chapter = f"{result.new_item.get('number', '')} {result.new_item.get('title', '')}"
                else:
                    current_chapter = chapter_info
                process_result(child, indent + 1, current_chapter)
        
        for result in self.diff_results:
            # 获取章节信息
            if result.old_item:
                chapter_info = f"{result.old_item.get('number', '')} {result.old_item.get('title', '')}"
            elif result.new_item:
                chapter_info = f"{result.new_item.get('number', '')} {result.new_item.get('title', '')}"
            else:
                chapter_info = ""
            process_result(result, chapter_info=chapter_info)
            report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"对比报告已生成: {output_path}")
    
    def generate_summary_report(self, output_path: str) -> None:
        """
        生成简洁的变更总结报告（仅包含有变更的条款）
        
        Args:
            output_path: 输出文件路径
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("法规变更总结报告")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append("本报告仅包含有变更的条款（新增、删除、修改）")
        report_lines.append("")
        
        # 按章节分组收集变更
        changes_by_chapter: Dict[str, List[DiffResult]] = {}
        
        def collect_changes_by_chapter(results: List[DiffResult], current_chapter: str = ""):
            """按章节收集变更"""
            for result in results:
                if result.change_type != ChangeType.UNCHANGED:
                    # 获取所属章节
                    if current_chapter not in changes_by_chapter:
                        changes_by_chapter[current_chapter] = []
                    changes_by_chapter[current_chapter].append(result)
                
                # 递归处理子项
                if result.children_diff:
                    # 更新章节信息
                    if result.old_item:
                        new_chapter = f"{result.old_item.get('number', '')} {result.old_item.get('title', '')[:20]}"
                    elif result.new_item:
                        new_chapter = f"{result.new_item.get('number', '')} {result.new_item.get('title', '')[:20]}"
                    else:
                        new_chapter = current_chapter
                    collect_changes_by_chapter(result.children_diff, new_chapter)
        
        collect_changes_by_chapter(self.diff_results)
        
        # 按章节输出变更
        for chapter, changes in changes_by_chapter.items():
            if not chapter:
                continue
            report_lines.append(f"【{chapter}】")
            report_lines.append("-" * 60)
            
            for result in changes:
                if result.change_type == ChangeType.ADDED and result.new_item:
                    report_lines.append(f"  ✓ 新增 {result.new_item.get('number', '')}")
                elif result.change_type == ChangeType.DELETED and result.old_item:
                    report_lines.append(f"  ✗ 删除 {result.old_item.get('number', '')}")
                elif result.change_type == ChangeType.MODIFIED:
                    if result.old_item and result.new_item:
                        report_lines.append(f"  ✎ 修改 {result.old_item.get('number', '')}")
                
                if result.ai_summary:
                    report_lines.append(f"    └─ {result.ai_summary}")
            
            report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"变更总结报告已生成: {output_path}")


def main():
    """主函数：演示法规对比流程"""
    
    # 加载法规数据
    print("加载法规数据...")
    
    with open('backend/text/2016.json', 'r', encoding='utf-8') as f:
        old_regulation = json.load(f)
    
    with open('backend/text/2025.json', 'r', encoding='utf-8') as f:
        new_regulation = json.load(f)
    
    print(f"老法规(2016)章节数: {len(old_regulation)}")
    print(f"新法规(2025)章节数: {len(new_regulation)}")
    
    # 创建对比器并执行对比
    comparator = RegulationComparator(old_regulation, new_regulation)
    results = comparator.compare()
    
    # 使用AI生成变更总结
    comparator.generate_ai_summaries()
    
    # 导出结果
    comparator.export_results('backend/text/comparison_result.json')
    comparator.generate_report('backend/text/comparison_report.txt')
    comparator.generate_summary_report('backend/text/comparison_summary.txt')
    
    return results


if __name__ == "__main__":
    main()
