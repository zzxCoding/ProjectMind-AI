#!/usr/bin/env python3
"""
GitLab合并记录分析器
分析指定日期范围内每个开发人员的合并记录，生成包含AI分析的详细报告
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import markdown
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from shared.utils import setup_logging, format_timestamp
from shared.gitlab_client import GitLabClient
from shared.ollama_client import OllamaClient
from automation.notification_sender import NotificationSender

class GitLabMergeAnalyzer:
    """GitLab合并记录分析器"""
    
    def __init__(self, project_id: str, gitlab_client: Optional[GitLabClient] = None,
                 ollama_client: Optional[OllamaClient] = None, ai_model: Optional[str] = None):
        """
        初始化分析器
        
        Args:
            project_id: GitLab项目ID
            gitlab_client: GitLab客户端
            ollama_client: Ollama AI客户端
            ai_model: 指定AI分析使用的模型名称
        """
        self.project_id = project_id
        self.gitlab = gitlab_client or GitLabClient()
        self.ollama = ollama_client or OllamaClient()
        self.ai_model = ai_model  # 指定的AI模型
        self.logger = setup_logging()
        self.notification_sender = NotificationSender()
    
    def analyze_merge_records(self, start_date: datetime, end_date: datetime,
                            target_branches: List[str] = None,
                            use_ai: bool = True) -> Dict[str, Any]:
        """
        分析合并记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            target_branches: 目标分支列表，为空则分析所有分支
            use_ai: 是否使用AI分析
            
        Returns:
            分析结果字典
        """
        self.logger.info(f"开始分析项目 {self.project_id} 的合并记录")
        self.logger.info(f"时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
        
        # 获取项目信息
        project_info = self.gitlab.get_project_info(self.project_id)
        if not project_info:
            raise ValueError(f"无法获取项目信息: {self.project_id}")
        
        # 获取合并请求
        all_merge_requests = []
        if target_branches:
            for branch in target_branches:
                mrs = self.gitlab.get_merge_requests(
                    project_id=self.project_id,
                    target_branch=branch,
                    state='merged',
                    since=start_date,
                    until=end_date
                )
                all_merge_requests.extend(mrs)
        else:
            all_merge_requests = self.gitlab.get_merge_requests(
                project_id=self.project_id,
                state='merged',
                since=start_date,
                until=end_date
            )
        
        self.logger.info(f"获取到 {len(all_merge_requests)} 个合并记录")
        
        if not all_merge_requests:
            return {
                'project_info': project_info,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'target_branches': target_branches
                },
                'summary': {
                    'total_merges': 0,
                    'developers_count': 0,
                    'branches_affected': set(),
                    'ai_analysis_enabled': use_ai
                },
                'developers': {},
                'ai_insights': None,
                'ai_model_info': {
                    'enabled': use_ai,
                    'model': self.ai_model or self.ollama.config.default_model if use_ai else None
                },
                'generated_at': format_timestamp()
            }
        
        # 按开发者分组分析（优化了性能以提高速度）
        developers_data = self._analyze_by_developer(all_merge_requests, use_ai)
        
        # 整体统计
        branches_affected = set()
        for mr in all_merge_requests:
            if mr.get('target_branch'):
                branches_affected.add(mr['target_branch'])
        
        summary = {
            'total_merges': len(all_merge_requests),
            'developers_count': len(developers_data),
            'branches_affected': list(branches_affected) if branches_affected else [],
            'ai_analysis_enabled': use_ai,
            'period_days': (end_date - start_date).days + 1
        }
        
        # AI整体分析
        ai_insights = None
        if use_ai:
            self.logger.info("开始执行整体AI分析...")
            ai_insights = self._generate_ai_insights(all_merge_requests, developers_data)
            self.logger.info("整体AI分析完成")
        
        return {
            'project_info': project_info,
            'analysis_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'target_branches': target_branches or ['所有分支']
            },
            'summary': summary,
            'developers': developers_data,
            'ai_insights': ai_insights,
            'ai_model_info': {
                'enabled': use_ai,
                'model': self.ai_model or self.ollama.config.default_model if use_ai else None
            },
            'generated_at': format_timestamp()
        }
    
    def _analyze_by_developer(self, merge_requests: List[Dict[str, Any]], 
                            use_ai: bool = True) -> Dict[str, Dict[str, Any]]:
        """按开发者分析合并记录"""
        developers = defaultdict(lambda: {
            'info': {},
            'merge_requests': [],
            'statistics': {
                'total_merges': 0,
                'branches': set(),
                'merge_frequency': {},
                'commit_stats': {
                    'total_commits': 0,
                    'total_changes': 0,
                    'avg_commits_per_mr': 0
                }
            },
            'ai_analysis': None
        })
        
        # 收集每个开发者的数据
        total_mrs = len(merge_requests)
        self.logger.info(f"开始处理 {total_mrs} 个合并请求的详细信息...")
        
        for i, mr in enumerate(merge_requests, 1):
            author = mr['author']
            username = author['username']
            
            # 进度显示
            if i % 20 == 0 or i == total_mrs:
                self.logger.info(f"处理进度: {i}/{total_mrs} ({i/total_mrs*100:.1f}%)")
            
            # 更新开发者信息
            developers[username]['info'] = {
                'name': author['name'],
                'username': author['username'],
                'email': author.get('email', ''),
                'id': author['id']
            }
            
            # 添加合并请求
            developers[username]['merge_requests'].append(mr)
            developers[username]['statistics']['total_merges'] += 1
            developers[username]['statistics']['branches'].add(mr['target_branch'])
            
            # 按日期统计频率 - 安全处理日期
            merge_date = None
            if mr.get('merged_at') and mr['merged_at']:
                merge_date = mr['merged_at'].date()
            elif mr.get('created_at') and mr['created_at']:
                merge_date = mr['created_at'].date()
            
            if merge_date:
                date_str = merge_date.strftime('%Y-%m-%d')
                if date_str not in developers[username]['statistics']['merge_frequency']:
                    developers[username]['statistics']['merge_frequency'][date_str] = 0
                developers[username]['statistics']['merge_frequency'][date_str] += 1
            
            # 获取详细统计信息 - 修复提交数和变更文件数获取问题
            try:
                # 获取真实的合并请求详细信息
                mr_details = self.gitlab.get_merge_request_details(self.project_id, mr['iid'])
                if mr_details and 'statistics' in mr_details:
                    commits_count = mr_details['statistics']['commits_count']
                    changes_count = mr_details['statistics']['changes_count']
                else:
                    # fallback到基本统计信息
                    commits_count = 1  # 至少有一个提交
                    changes_count = mr.get('changes_count', 0)
            except Exception as e:
                self.logger.warning(f"获取MR !{mr['iid']} 详细信息失败: {e}")
                # 使用基本统计信息作为fallback
                commits_count = 1  # 至少有一个提交
                changes_count = mr.get('changes_count', 0)
            
            developers[username]['statistics']['commit_stats']['total_commits'] += commits_count
            developers[username]['statistics']['commit_stats']['total_changes'] += changes_count
            
            # 更新合并请求数据（使用已有信息）
            mr['detailed_info'] = {
                'commits_count': commits_count,
                'changes_count': changes_count,
                'discussions_count': mr.get('user_notes_count', 0)  # 使用已有的评论数
            }
        
        self.logger.info(f"完成处理所有合并请求详细信息")
        
        # 转换为普通字典并计算统计信息
        result = {}
        total_developers = len(developers)
        self.logger.info(f"开始处理 {total_developers} 个开发者的统计信息...")
        
        for i, (username, data) in enumerate(developers.items(), 1):
            # 进度显示
            if i % 5 == 0 or i == total_developers:
                self.logger.info(f"开发者处理进度: {i}/{total_developers} ({username})")
            
            # 安全转换branches集合为列表
            branches_set = data['statistics']['branches']
            data['statistics']['branches'] = list(branches_set) if branches_set else []
            
            # 计算平均值
            if data['statistics']['total_merges'] > 0:
                data['statistics']['commit_stats']['avg_commits_per_mr'] = (
                    data['statistics']['commit_stats']['total_commits'] / 
                    data['statistics']['total_merges']
                )
            
            # AI分析单个开发者
            if use_ai:
                self.logger.info(f"正在为开发者 {username} 执行AI分析...")
                data['ai_analysis'] = self._analyze_developer_with_ai(username, data)
                self.logger.info(f"开发者 {username} 的AI分析完成")
            
            result[username] = data
        
        self.logger.info(f"完成所有开发者的统计和AI分析")
        
        return result
    
    def _analyze_developer_with_ai(self, username: str, developer_data: Dict[str, Any]) -> str:
        """使用AI分析单个开发者的表现"""
        try:
            merge_requests = developer_data['merge_requests']
            stats = developer_data['statistics']
            
            # Build structured analysis prompt
            prompt = f"""
As a GitLab project management expert, please analyze the merge record performance of developer {developer_data['info']['name']}.

## Developer Overview
- **Total Merges**: {stats['total_merges']} times
- **Branches Involved**: {', '.join(stats['branches']) if stats['branches'] else 'None'}
- **Records Analyzed**: {len(merge_requests)} items

## Detailed Merge Records
"""

            # Add all merge request records
            for i, mr in enumerate(merge_requests):
                prompt += f"{i+1}. **{mr['title']}** \n   📍 {mr['source_branch']} → {mr['target_branch']}\n"

            prompt += f"""

## Branch Synchronization Rules
### Required Synchronization
- `release/YYYYMMDD-b*` → Must sync to `develop` + `develop-7.1`
- `release/7.1-YYYYMMDD-b*` → Must sync to `develop-7.1`
- `develop` → Must sync to `develop-7.1`

### Special Exceptions
- `release/20221210-b25-*` → No sync required
- `release/YYYYMMDD → master` → Normal release to main branch, no additional sync needed
- `release/YYYYMMDD → develop` → Normal release sync to develop branch, no additional sync needed

## Missing Merge Detection Method (MUST Execute Step by Step)
**For each MR, execute the following 4-step verification:**

1. **🎯 Identify Sync Requirements**
   - Extract: source_branch → target_branch
   - Determine: Based on rules above, which branches MUST this MR sync to?
   - Example: If `feature/xxx → release/20241030-b02`, then MUST sync to `develop` AND `develop-7.1`

2. **🔍 Find Related Fixes**
   - Extract issue number (B12345) or feature ID from MR title
   - Mark this as "同源修复标识" (same-origin fix identifier)

3. **📋 Search for Sync Records**
   - In ALL {len(merge_requests)} MR records, search for MRs that:
     * Contain the same issue number/feature ID (同源修复)
     * Target the required sync branches (develop or develop-7.1)
   - If found: Mark as ✅ Safe
   - If NOT found: Mark as ⚠️ Missing Sync Risk

4. **📊 Output Verification Result**
   - List ONLY the MRs with missing sync risks
   - For each risky MR, specify: MR #号, 标题简述, 源分支→目标分支, 缺失同步分支

## Analysis Dimensions (Output Structure)

### 🚨 漏合并风险清单 (MUST Output This Section)
**Output Format (Use Markdown Table):**

| MR编号 | 标题 | 分支流向 | 缺失同步分支 | 风险等级 |
|--------|------|----------|--------------|----------|
| !1234  | xxx功能 | feature/xxx → release/20241030-b02 | develop, develop-7.1 | 🔴 高风险 |

**If no missing merge risks found, output:**
✅ 所有MR均已按规则同步，无漏合并风险

### 🌿 分支合规性评估
- 分支命名是否规范？
- 目标分支选择是否合理？

### 📊 提交模式分析
- 代码拆分粒度是否合理？
- 合并频率和节奏如何？

### 💡 改进建议
- 最多2条具体可执行的建议
- 基于实际数据

## Output Requirements
- ✅ 使用中文回答
- ✅ 总字数控制在200字内（漏合并清单不计入字数限制）
- ✅ 基于实际数据，避免猜测
- ✅ 严格遵守4个维度的输出结构
- ✅ **漏合并风险清单**是核心输出，必须逐条审查每个MR
- ✅ 使用清晰简洁的语言
"""
            
            # 添加超时和错误处理
            try:
                self.logger.debug(f"开始为开发者 {username} 调用Ollama API...")

                # 配置AI参数以获得更确定性和准确的输出
                options = {
                    'temperature': 0.0,      # 确定性输出，避免随机性
                    'top_p': 0.7,            # 控制采样范围
                    'repeat_penalty': 1.05,  # 减少重复内容
                    'do_sample': False       # 对于OpenAI兼容API，确保确定性输出
                }

                result = self.ollama.analyze_text(
                    prompt,
                    model=self.ai_model,
                    analysis_type="custom",
                    options=options
                )
                self.logger.debug(f"开发者 {username} 的Ollama API调用成功")
                return result
            except Exception as ollama_error:
                self.logger.warning(f"Ollama API调用失败（{username}）: {ollama_error}")
                return f"AI分析不可用：Ollama服务可能未启动或超时"
            
        except Exception as e:
            self.logger.error(f"AI分析开发者 {username} 失败: {e}")
            return f"分析失败: {str(e)}"
    
    def _generate_ai_insights(self, merge_requests: List[Dict[str, Any]], 
                            developers_data: Dict[str, Dict[str, Any]]) -> str:
        """生成整体AI洞察"""
        try:
            # 构建专业的整体分析提示词，基于个人分析结果进行归纳
            
            # 分支活跃度分析
            branch_activity = defaultdict(int)
            for mr in merge_requests:
                branch_activity[mr['target_branch']] += 1
            
            # 获取主要分支
            main_branches = sorted(branch_activity.items(), key=lambda x: x[1], reverse=True)[:5]
            
            prompt = f"""
你是一个高级GitLab项目管理专家，请基于各个开发者的个人AI分析结果，对项目整体合并情况进行归纳总结。

## 项目数据概览
合并记录总数：{len(merge_requests)}次
参与开发者：{len(developers_data)}人

## 主要分支活跃度
"""
            for branch, count in main_branches:
                prompt += f"- {branch}: {count}次合并\n"
            
            # 收集所有个人AI分析结果
            prompt += "\n## 各开发者AI分析结果汇总\n"
            
            for username, data in developers_data.items():
                user_info = data['info']['name']
                ai_analysis = data.get('ai_analysis', '无AI分析结果')
                
                prompt += f"\n### {user_info} (@{username}) 的分析结果:\n"
                if ai_analysis and ai_analysis != '无AI分析结果':
                    # 将个人分析结果添加到整体分析的输入中
                    prompt += f"{ai_analysis}\n"
                else:
                    prompt += "该开发者暂无AI分析结果\n"
            
            prompt += f"""

## 整体分析任务
请基于上述各个开发者的个人AI分析结果，进行简洁的项目级汇总。

## 输出结构 (严格遵守)

### 🚨 漏合并风险汇总
**从每个开发者的分析中提取漏合并信息，输出格式：**
- ⚠️ [姓名]：存在 X 个漏合并风险
- ⚠️ [姓名]：存在 X 个漏合并风险
- ✅ [姓名]：无漏合并风险

**注意：**
- 只统计人数，不列出具体MR详情
- 按风险数量从高到低排序
- 如果某人无风险，标记为✅

### 🤝 团队协作模式
1-2句话总结团队的合并习惯和协作特点

### 💡 改进建议
最多2条针对团队层面的具体建议

## 输出要求
- ✅ 使用中文回答
- ✅ 不要重复个人分析中的详细内容
- ✅ 总字数控制在150字内
- ✅ 简洁直观，便于快速了解项目整体风险
"""
            
            # 添加超时和错误处理
            try:
                self.logger.debug("开始调用Ollama API进行整体分析...")

                # 配置AI参数以获得更确定性和准确的输出
                options = {
                    'temperature': 0.0,      # 确定性输出，避免随机性
                    'top_p': 0.7,            # 控制采样范围
                    'repeat_penalty': 1.05,  # 减少重复内容
                    'do_sample': False       # 对于OpenAI兼容API，确保确定性输出
                }

                result = self.ollama.analyze_text(
                    prompt,
                    model=self.ai_model,
                    analysis_type="custom",
                    options=options
                )
                self.logger.debug("整体分析的Ollama API调用成功")
                return result
            except Exception as ollama_error:
                self.logger.warning(f"整体AI分析Ollama API调用失败: {ollama_error}")
                return f"AI整体分析不可用：Ollama服务可能未启动或超时"
            
        except Exception as e:
            self.logger.error(f"生成AI整体洞察失败: {e}")
            return f"分析失败: {str(e)}"
    
    def generate_markdown_report(self, analysis_data: Dict[str, Any]) -> str:
        """生成Markdown格式报告"""
        md_content = []
        
        # 标题和基本信息
        project_name = analysis_data['project_info']['name']
        period_start = analysis_data['analysis_period']['start_date'][:10]
        period_end = analysis_data['analysis_period']['end_date'][:10]
        
        md_content.append(f"# 📋 GitLab合并记录分析报告")
        md_content.append(f"")
        
        # 项目基本信息卡片
        md_content.append("## 🏗️ 项目信息")
        md_content.append(f"| 项目 | 内容 |")
        md_content.append(f"|------|------|")
        md_content.append(f"| **项目名称** | `{project_name}` |")
        md_content.append(f"| **项目ID** | `{analysis_data['project_info']['id']}` |")
        md_content.append(f"| **分析时间范围** | `{period_start}` 至 `{period_end}` |")
        
        target_branches = analysis_data['analysis_period']['target_branches']
        if target_branches and isinstance(target_branches, list):
            branches_text = ', '.join([f'`{b}`' for b in target_branches])
            md_content.append(f"| **目标分支** | {branches_text} |")
        else:
            md_content.append(f"| **目标分支** | `所有分支` |")
        
        md_content.append(f"| **报告生成时间** | `{analysis_data['generated_at']}` |")
        md_content.append(f"")
        
        # 整体统计仪表盘
        summary = analysis_data['summary']
        md_content.append("## 📊 数据仪表盘")
        md_content.append("")
        
        # 核心指标卡片
        branches_list = summary.get('branches_affected', [])
        daily_avg = summary['total_merges'] / summary['period_days'] if summary['period_days'] > 0 else 0
        
        md_content.append("### 🎯 核心指标")
        md_content.append("")
        md_content.append(f"| 指标 | 数值 | 趋势 |")
        md_content.append(f"|------|------|------|")
        md_content.append(f"| **📈 总合并数** | `{summary['total_merges']}` 次 | {'🔥 高活跃' if summary['total_merges'] > 50 else '📊 正常' if summary['total_merges'] > 10 else '📉 较少'} |")
        md_content.append(f"| **👥 参与开发者** | `{summary['developers_count']}` 人 | {'🌟 团队协作' if summary['developers_count'] > 5 else '👤 小团队' if summary['developers_count'] > 1 else '🧑‍💻 单人'} |")
        md_content.append(f"| **📊 分析周期** | `{summary['period_days']}` 天 | {'📅 长期分析' if summary['period_days'] > 30 else '📆 短期分析'} |")
        md_content.append(f"| **⚡ 平均每日合并数** | `{daily_avg:.1f}` 次/天 | {'🚀 高频' if daily_avg > 5 else '⚖️ 适中' if daily_avg > 1 else '🐌 低频'} |")
        md_content.append("")
        
        # 分支分布
        if branches_list:
            md_content.append("### 🌿 分支分布")
            md_content.append("")
            md_content.append(f"**涉及 `{len(branches_list)}` 个分支**")
            md_content.append("")
            
            # 按分支类型分组
            release_branches = [b for b in branches_list if 'release' in b.lower()]
            develop_branches = [b for b in branches_list if 'develop' in b.lower()]
            feature_branches = [b for b in branches_list if 'feature' in b.lower() or 'feat' in b.lower()]
            hotfix_branches = [b for b in branches_list if 'hotfix' in b.lower() or 'fix' in b.lower()]
            other_branches = [b for b in branches_list if b not in release_branches + develop_branches + feature_branches + hotfix_branches]
            
            md_content.append(f"| 分支类型 | 数量 | 分支列表 |")
            md_content.append(f"|----------|------|----------|")
            
            if release_branches:
                branch_list = ', '.join([f'`{b}`' for b in release_branches[:3]])
                if len(release_branches) > 3:
                    branch_list += f' 等{len(release_branches)}个'
                md_content.append(f"| 🚀 发布分支 | `{len(release_branches)}` | {branch_list} |")
            
            if develop_branches:
                branch_list = ', '.join([f'`{b}`' for b in develop_branches])
                md_content.append(f"| 🛠️ 开发分支 | `{len(develop_branches)}` | {branch_list} |")
            
            if feature_branches:
                branch_list = ', '.join([f'`{b}`' for b in feature_branches[:2]])
                if len(feature_branches) > 2:
                    branch_list += f' 等{len(feature_branches)}个'
                md_content.append(f"| ✨ 功能分支 | `{len(feature_branches)}` | {branch_list} |")
            
            if hotfix_branches:
                branch_list = ', '.join([f'`{b}`' for b in hotfix_branches[:2]])
                if len(hotfix_branches) > 2:
                    branch_list += f' 等{len(hotfix_branches)}个'
                md_content.append(f"| 🔧 修复分支 | `{len(hotfix_branches)}` | {branch_list} |")
            
            if other_branches:
                branch_list = ', '.join([f'`{b}`' for b in other_branches[:2]])
                if len(other_branches) > 2:
                    branch_list += f' 等{len(other_branches)}个'
                md_content.append(f"| 📂 其他分支 | `{len(other_branches)}` | {branch_list} |")
        
        else:
            md_content.append("### 🌿 分支分布")
            md_content.append("")
            md_content.append("⚠️ 未检测到分支活动")
        
        md_content.append("")
        
        # AI整体洞察
        if analysis_data['ai_insights']:
            md_content.append("## 🤖 AI智能分析")
            md_content.append("")
            md_content.append("> 🧠 **基于数据模式的智能洞察**")
            md_content.append("")
            
            # 将AI分析格式化为引用块
            ai_lines = analysis_data['ai_insights'].split('\n')
            for line in ai_lines:
                if line.strip():
                    if line.startswith('###') or line.startswith('**'):
                        md_content.append(f"> {line}")
                    else:
                        md_content.append(f"> {line}")
                else:
                    md_content.append(">")
            
            md_content.append("")
            md_content.append("> 💡 *以上分析基于合并模式和分支使用习惯生成*")
            md_content.append("")
        
        # 开发者详细分析
        md_content.append("## 👥 开发者详细分析")
        md_content.append("")
        
        # 按合并数排序开发者
        sorted_developers = sorted(
            analysis_data['developers'].items(),
            key=lambda x: x[1]['statistics']['total_merges'],
            reverse=True
        )
        
        for username, dev_data in sorted_developers:
            dev_info = dev_data['info']
            stats = dev_data['statistics']
            
            md_content.append(f"### 👤 {dev_info['name']} (@{username})")
            md_content.append("")
            
            # 基本信息卡片
            md_content.append("#### 📋 基本信息")
            md_content.append(f"| 项目 | 内容 |")
            md_content.append(f"|------|------|") 
            md_content.append(f"| **姓名** | {dev_info['name']} |")
            md_content.append(f"| **用户名** | @{username} |")
            md_content.append(f"| **邮箱** | {dev_info.get('email', '未提供')} |")
            md_content.append("")
            
            # 统计信息卡片
            md_content.append("#### 📊 合并统计")
            branches = stats.get('branches', [])
            branches_text = ', '.join([f"`{b}`" for b in branches]) if branches else '无'
            
            md_content.append(f"| 指标 | 数值 |")
            md_content.append(f"|------|------|") 
            md_content.append(f"| **总合并数** | `{stats['total_merges']}` 次 |")
            md_content.append(f"| **涉及分支** | {branches_text} |")
            md_content.append(f"| **总提交数** | `{stats['commit_stats']['total_commits']}` 个 |")
            md_content.append(f"| **总变更文件数** | `{stats['commit_stats']['total_changes']}` 个 |")
            md_content.append(f"| **平均每次MR提交数** | `{stats['commit_stats']['avg_commits_per_mr']:.1f}` 个 |")
            md_content.append("")
            
            # 合并频率
            if stats['merge_frequency']:
                md_content.append("#### 📅 合并频率分布")
                md_content.append(f"| 日期 | 合并次数 | 活跃度 |")
                md_content.append(f"|------|----------|--------|") 
                
                sorted_dates = sorted(stats['merge_frequency'].keys())
                max_count = max(stats['merge_frequency'].values())
                
                for date in sorted_dates:
                    count = stats['merge_frequency'][date]
                    # 生成活跃度条形图
                    bar_length = int((count / max_count) * 10) if max_count > 0 else 0
                    activity_bar = '🟩' * bar_length + '⬜' * (10 - bar_length)
                    md_content.append(f"| `{date}` | **{count}** 次 | {activity_bar} |")
                md_content.append("")
            
            # 详细合并记录
            md_content.append(f"#### 📝 合并记录详情 ({len(dev_data['merge_requests'])} 条)")
            md_content.append("")
            
            # 使用更宽的表格格式显示合并记录，不截断信息
            for i, mr in enumerate(dev_data['merge_requests'], 1):
                merge_time = mr['merged_at'].strftime('%Y-%m-%d %H:%M') if mr.get('merged_at') and mr['merged_at'] else '未知时间'
                commits = mr.get('detailed_info', {}).get('commits_count', '?')
                changes = mr.get('detailed_info', {}).get('changes_count', '?')
                
                # 根据标签和标题判断类型
                mr_type = '🔧 其他'
                title_lower = mr['title'].lower()
                if mr.get('labels'):
                    labels_text = ' '.join(mr['labels']).lower()
                    if any(keyword in labels_text for keyword in ['feat', 'feature']):
                        mr_type = '✨ 功能'
                    elif any(keyword in labels_text for keyword in ['fix', 'bug', 'hotfix']):
                        mr_type = '🐛 修复'
                    elif any(keyword in labels_text for keyword in ['doc']):
                        mr_type = '📚 文档'
                    elif any(keyword in labels_text for keyword in ['refactor']):
                        mr_type = '♻️ 重构'
                elif any(keyword in title_lower for keyword in ['修复', 'fix', 'bug']):
                    mr_type = '🐛 修复'
                elif any(keyword in title_lower for keyword in ['新增', '添加', 'add', 'feat']):
                    mr_type = '✨ 功能'
                elif any(keyword in title_lower for keyword in ['更新', 'update', '优化']):
                    mr_type = '🔄 更新'
                
                # 完整显示标题，不截断
                title = mr['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                # 分支信息，保持完整性
                source_branch = mr['source_branch']
                target_branch = mr['target_branch']
                
                # 构建MR链接
                mr_link = f"[!{mr['iid']}]({mr['web_url']})"
                
                # 统计信息
                stats_info = f"{commits}次提交 / {changes}个文件"
                
                # 使用纯文本一行格式显示合并记录
                merge_line = f"#{i} {mr_type} MR !{mr['iid']} - 标题: {title} - 分支流向: {source_branch} → {target_branch} - 提交统计: {stats_info} - 合并时间: {merge_time} - 链接: {mr_link}"
                
                if mr.get('labels'):
                    labels_text = ', '.join(mr['labels'])
                    merge_line += f" - 标签: {labels_text}"
                
                md_content.append(f'<div class="merge-record">{merge_line}</div>')  # 使用HTML div包装并应用样式
            
            md_content.append("")
            
            # AI分析
            if dev_data['ai_analysis']:
                md_content.append("#### 🤖 AI性能分析")
                md_content.append("> 💡 **智能分析报告**")
                md_content.append("")
                # 将AI分析文本格式化为引用块
                ai_lines = dev_data['ai_analysis'].split('\n')
                for line in ai_lines:
                    if line.strip():
                        md_content.append(f"> {line}")
                    else:
                        md_content.append(">")
                md_content.append("")
            
            md_content.append("---")
            md_content.append("")
        
        # 附录
        md_content.append("## 📋 附录")
        md_content.append("")
        md_content.append("### 分析说明")
        md_content.append("- 本报告基于GitLab API数据生成")
        md_content.append("- 仅统计状态为'merged'的合并请求")
        
        # 添加AI模型信息
        ai_model_info = analysis_data.get('ai_model_info', {})
        if ai_model_info.get('enabled'):
            ai_model = ai_model_info.get('model', '未知模型')
            md_content.append(f"- AI分析基于Ollama本地模型生成，使用模型: **{ai_model}**")
        else:
            md_content.append("- 本次分析未启用AI功能")
        
        md_content.append("")
        
        md_content.append("### 数据来源")
        md_content.append(f"- GitLab实例: {analysis_data['project_info'].get('web_url', '未知')}")
        md_content.append(f"- 项目链接: {analysis_data['project_info'].get('web_url', '未知')}")
        md_content.append("")
        
        return "\n".join(md_content)
    
    def convert_markdown_to_html(self, markdown_content: str) -> str:
        """将Markdown转换为HTML"""
        try:
            # 配置markdown扩展
            extensions = [
                'markdown.extensions.tables',
                'markdown.extensions.codehilite',
                'markdown.extensions.fenced_code',
                'markdown.extensions.toc'
            ]
            
            # 转换为HTML
            html = markdown.markdown(markdown_content, extensions=extensions)
            
            # 添加CSS样式
            styled_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GitLab合并记录分析报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        
        h1, h2, h3 {{
            color: #2c3e50;
            border-bottom: 1px solid #ecf0f1;
            padding-bottom: 10px;
        }}
        
        h1 {{ color: #e74c3c; }}
        h2 {{ color: #3498db; }}
        h3 {{ color: #f39c12; }}
        
        code {{
            background-color: #f8f9fa;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', monospace;
        }}
        
        pre {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        
        blockquote {{
            border-left: 4px solid #3498db;
            padding-left: 20px;
            margin: 20px 0;
            background-color: #f8f9fa;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        
        ul, ol {{
            padding-left: 30px;
        }}
        
        .ai-analysis {{
            background-color: #e8f5e8;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #27ae60;
            margin: 15px 0;
        }}
        
        .developer-section {{
            border: 1px solid #ecf0f1;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        
        .stat-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        
        .merge-record {{
            font-size: 0.9em;
            line-height: 1.4;
            margin: 8px 0;
            padding: 5px 0;
        }}
        
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        hr {{
            border: none;
            height: 2px;
            background: linear-gradient(to right, #3498db, #e74c3c);
            margin: 30px 0;
        }}
        
        .timestamp {{
            color: #7f8c8d;
            font-style: italic;
            text-align: right;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
{html}
<div class="timestamp">
    报告生成时间: {format_timestamp()}
</div>
</body>
</html>
"""
            return styled_html
            
        except Exception as e:
            self.logger.error(f"Markdown转HTML失败: {e}")
            return f"<html><body><h1>转换失败</h1><p>{str(e)}</p></body></html>"
    
    def send_report_email(self, html_content: str, recipients: List[str],
                         subject: str = None, project_name: str = None, 
                         markdown_content: str = None) -> Dict[str, Any]:
        """发送HTML格式的邮件报告（同时附上markdown文件）"""
        try:
            if not subject:
                date_str = datetime.now().strftime('%Y-%m-%d')
                subject = f"GitLab合并记录分析报告 - {project_name or self.project_id} ({date_str})"
            
            self.logger.info(f"📧 邮件主题: {subject}")
            
            # 如果有markdown内容，则发送HTML邮件并附上markdown文件
            if markdown_content:
                # 生成附件文件名
                date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                project_name_safe = (project_name or self.project_id).replace('/', '_').replace(' ', '_')
                attachment_filename = f"GitLab合并分析报告_{project_name_safe}_{date_str}.md"
                
                self.logger.info(f"📎 附件文件名: {attachment_filename}")
                self.logger.info(f"📎 附件大小: {len(markdown_content)} 字符")
                self.logger.info("正在发送HTML邮件（包含Markdown附件）...")
                
                return self.notification_sender.send_html_email_with_attachment(
                    subject, html_content, recipients, 
                    markdown_content, attachment_filename
                )
            else:
                # 仅发送HTML邮件
                self.logger.info("正在发送HTML邮件（无附件）...")
                return self.notification_sender.send_html_email(subject, html_content, recipients)
            
        except Exception as e:
            self.logger.error(f"发送邮件失败: {e}")
            return {'success': False, 'error': str(e)}
    
    # 已移除重复的邮件发送代码，使用通用的 NotificationSender.send_html_email() 代替

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="GitLab合并记录分析器")
    parser.add_argument('--project-id', required=True, help='GitLab项目ID')
    parser.add_argument('--start-date', required=True, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--target-branches', nargs='+', help='目标分支列表')
    parser.add_argument('--use-ai', action='store_true', help='启用AI分析')
    parser.add_argument('--ai-model', help='指定AI分析使用的模型名称 (如: qwen3:32b, llama3, gemma2等)')
    parser.add_argument('--output-format', choices=['json', 'markdown', 'html'], 
                       default='html', help='输出格式')
    parser.add_argument('--output-file', help='输出文件路径')
    parser.add_argument('--send-email', action='store_true', help='发送邮件报告')
    parser.add_argument('--email-recipients', nargs='+', help='邮件收件人列表')
    parser.add_argument('--email-subject', help='邮件主题')
    
    # GitLab配置选项（可选，未指定时使用环境变量）
    parser.add_argument('--gitlab-url', help='GitLab实例URL (默认从环境变量)')
    parser.add_argument('--gitlab-token', help='GitLab访问令牌 (默认从环境变量)')
    parser.add_argument('--gitlab-timeout', type=int, help='GitLab API超时时间')
    parser.add_argument('--gitlab-verify-ssl', type=bool, help='是否验证SSL证书')
    
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    try:
        # 解析日期
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        
        if start_date > end_date:
            raise ValueError("开始日期不能晚于结束日期")
        
        # 创建GitLab配置（如果提供了参数）
        gitlab_config = None
        if any([args.gitlab_url, args.gitlab_token, args.gitlab_timeout, args.gitlab_verify_ssl is not None]):
            from config.gitlab_config import GitLabConfig, get_default_config
            
            # 从环境变量获取默认配置
            default_config = get_default_config()
            
            # 使用命令行参数覆盖默认配置
            gitlab_config = GitLabConfig(
                url=args.gitlab_url or default_config.url,
                token=args.gitlab_token or default_config.token,
                timeout=args.gitlab_timeout or default_config.timeout,
                verify_ssl=args.gitlab_verify_ssl if args.gitlab_verify_ssl is not None else default_config.verify_ssl
            )
        
        # 创建GitLab客户端
        gitlab_client = GitLabClient(gitlab_config) if gitlab_config else None
        
        # 创建分析器
        analyzer = GitLabMergeAnalyzer(args.project_id, gitlab_client=gitlab_client, ai_model=args.ai_model)
        
        # 执行分析
        logger.info("开始分析GitLab合并记录...")
        analysis_data = analyzer.analyze_merge_records(
            start_date=start_date,
            end_date=end_date,
            target_branches=args.target_branches,
            use_ai=args.use_ai
        )
        
        # 输出结果
        logger.info(f"开始生成 {args.output_format} 格式的报告...")
        markdown_content = None  # 初始化markdown_content变量
        if args.output_format == 'json':
            output_content = json.dumps(analysis_data, indent=2, ensure_ascii=False, default=str)
        elif args.output_format == 'markdown':
            logger.info("正在生成Markdown报告...")
            markdown_content = analyzer.generate_markdown_report(analysis_data)
            output_content = markdown_content
        elif args.output_format == 'html':
            logger.info("正在生成Markdown报告...")
            markdown_content = analyzer.generate_markdown_report(analysis_data)
            logger.info("正在转换为HTML格式...")
            output_content = analyzer.convert_markdown_to_html(markdown_content)
        logger.info("报告生成完成")
        
        # 保存到文件
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(output_content)
            logger.info(f"分析报告已保存到: {args.output_file}")
        
        # 发送邮件
        if args.send_email and args.email_recipients:
            logger.info("开始发送邮件报告...")
            logger.info(f"收件人: {', '.join(args.email_recipients)}")
            
            if args.output_format == 'html':
                # 检查是否有附件
                has_attachment = markdown_content is not None
                if has_attachment:
                    logger.info("📎 将发送HTML邮件并附上Markdown文件")
                else:
                    logger.info("📧 将发送HTML邮件（无附件）")
                
                # 发送HTML邮件并附上markdown文件
                result = analyzer.send_report_email(
                    html_content=output_content,
                    recipients=args.email_recipients,
                    subject=args.email_subject,
                    project_name=analysis_data['project_info']['name'],
                    markdown_content=markdown_content
                )
                
                if result['success']:
                    if has_attachment:
                        logger.info("✅ HTML邮件发送成功（包含Markdown附件）")
                    else:
                        logger.info("✅ HTML邮件发送成功")
                    logger.info(f"已发送给 {len(args.email_recipients)} 个收件人")
                else:
                    logger.error(f"❌ 邮件发送失败: {result.get('error')}")
            else:
                logger.warning("⚠️ 只有HTML格式才支持发送邮件")
        
        # 输出摘要
        summary = analysis_data['summary']
        print(f"✅ 分析完成")
        print(f"   项目: {analysis_data['project_info']['name']}")
        print(f"   时间范围: {args.start_date} 至 {args.end_date}")
        print(f"   总合并数: {summary['total_merges']}")
        print(f"   参与开发者: {summary['developers_count']} 人")
        print(f"   涉及分支: {len(summary['branches_affected'])} 个")
        
        if not args.output_file and not args.send_email:
            print("\n" + output_content)
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()