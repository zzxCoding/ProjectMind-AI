#!/usr/bin/env python3
"""
GitLab MR 审查结果处理器
负责将审查结果回写到 GitLab MR 评论区
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import asdict

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.gitlab_client import GitLabClient
from config.gitlab_config import get_default_config
from shared.utils import setup_logging
from automation.mr_review_engine import MRReviewEngine, ReviewResult, ReviewStatus, ReviewIssue

class GitLabMRInteractor:
    """GitLab MR 交互器"""
    
    def __init__(self, gitlab_client: Optional[GitLabClient] = None, log_level: str = 'INFO'):
        """
        初始化GitLab交互器
        
        Args:
            gitlab_client: GitLab客户端
            log_level: 日志级别
        """
        self.gitlab_client = gitlab_client or GitLabClient()
        self.logger = setup_logging(level=log_level)
        
        # 交互配置
        self.config = {
            'auto_comment': True,  # 自动评论
            'auto_label': True,    # 自动添加标签
            'auto_block': True,    # 自动阻止合并
            'comment_template': 'default',  # 评论模板
            'max_comment_length': 500000,  # 评论最大长度 (500KB)
            'force_recomment': False,  # 强制重新评论（忽略已有评论）
        }
    
    def set_force_recomment(self, force_recomment: bool):
        """
        设置是否强制重新评论
        
        Args:
            force_recomment: 是否强制重新评论（忽略已有评论）
        """
        self.config['force_recomment'] = force_recomment
        self.logger.info(f"强制重新评论设置: {'启用' if force_recomment else '禁用'}")
    
    def post_review_result(self, project_id: str, mr_iid: int, review_result: ReviewResult) -> bool:
        """
        发布审查结果到GitLab MR - 基于Commit的增量审查
        
        Args:
            project_id: 项目ID
            mr_iid: 合并请求IID
            review_result: 审查结果
            
        Returns:
            是否成功
        """
        try:
            self.logger.info(f"开始发布审查结果到MR: {project_id}!{mr_iid}")
            
            # 1. 检查是否需要执行审查（基于Commit）
            if not self._should_perform_review(project_id, mr_iid):
                self.logger.info(f"MR {project_id}!{mr_iid} 代码无变更，跳过审查")
                return True
            
            # 2. 检查是否需要发布评论（优化：PASSED且无新问题时跳过）
            if not self._should_publish_comment(project_id, mr_iid, review_result):
                self.logger.info(f"MR {project_id}!{mr_iid} 审查通过且无新问题，跳过评论更新")
                
                # 仍然需要更新标签和记录commit（如果需要）
                if self.config['auto_label']:
                    self._update_labels(project_id, mr_iid, review_result)
                
                self._record_reviewed_commit(project_id, mr_iid)
                return True
            
            # 3. 生成评论内容
            comment = self._generate_review_comment(review_result)
            
            # 4. 发布评论（使用增量策略）
            if self.config['auto_comment']:
                success = self._post_comment_incremental(project_id, mr_iid, comment, review_result)
                if not success:
                    return False
            
            # 5. 更新标签
            if self.config['auto_label']:
                self._update_labels(project_id, mr_iid, review_result)
            
            # 6. 更新状态（如果需要阻止合并）
            if self.config['auto_block'] and review_result.status == ReviewStatus.FAILED:
                self._block_merge(project_id, mr_iid, review_result)
            
            # 7. 记录审查的Commit
            self._record_reviewed_commit(project_id, mr_iid)
            
            self.logger.info("审查结果发布成功")
            return True
            
        except Exception as e:
            self.logger.error(f"发布审查结果失败: {e}")
            return False
    
    def _should_publish_comment(self, project_id: str, mr_iid: int, review_result: ReviewResult) -> bool:
        """检查是否需要发布评论"""
        try:
            # 如果启用强制重新评论，直接返回True
            if self.config['force_recomment']:
                self.logger.info(f"MR {project_id}!{mr_iid} 启用强制重新评论，需要发布评论")
                return True
            
            # 如果审查结果不是PASSED，需要发布评论
            if review_result.status != ReviewStatus.PASSED:
                self.logger.info(f"MR {project_id}!{mr_iid} 审查结果为{review_result.status.value}，需要发布评论")
                return True
            
            # 如果PASSED但没有问题，检查是否有历史评论
            if len(review_result.issues) == 0:
                comment_history = self._get_comment_history(project_id, mr_iid)
                if not comment_history:
                    # 首次审查且通过，发布初始评论
                    self.logger.info(f"MR {project_id}!{mr_iid} 首次审查通过，需要发布评论")
                    return True
                else:
                    # 有历史评论且审查通过，无新问题，跳过评论更新
                    self.logger.info(f"MR {project_id}!{mr_iid} 审查通过且无新问题，跳过评论更新")
                    return False
            
            # PASSED但有问题（可能是警告级别的问题），需要发布评论
            self.logger.info(f"MR {project_id}!{mr_iid} 审查通过但有{len(review_result.issues)}个问题，需要发布评论")
            return True
            
        except Exception as e:
            self.logger.error(f"检查是否需要发布评论失败: {e}")
            return True  # 如果检查失败，默认发布评论
    
    def _generate_review_comment(self, review_result: ReviewResult) -> str:
        """生成AI审查评论"""
        
        # 根据状态选择图标
        status_icons = {
            ReviewStatus.PASSED: "✅",
            ReviewStatus.WARNING: "⚠️",
            ReviewStatus.FAILED: "❌"
        }
        
        icon = status_icons.get(review_result.status, "🔍")
        
        # 构建评论头部
        comment = f"""
# {icon} AI智能代码审查报告

**合并请求**: {review_result.mr_title} (!{review_result.mr_id})  
**审查时间**: {review_result.review_time.strftime('%Y-%m-%d %H:%M:%S')}  
**审查状态**: {review_result.status.value}  
**审查人**: AI自动审查机器人  

## 📊 AI审查摘要

- **变更文件**: {review_result.metadata['files_changed']} 个
- **发现问题**: {len(review_result.issues)} 个
- **AI分析文件**: {review_result.summary.get('files_analyzed', review_result.metadata['files_changed'])} 个

"""
        
        # 添加AI分析亮点（修复逻辑矛盾）
        if 'ai_analysis_highlights' in review_result.summary:
            highlights = review_result.summary['ai_analysis_highlights']
            comment += "## 🎯 AI分析亮点\n\n"
            
            # 统计总问题数
            total_issues_found = sum(highlights.values())
            
            if total_issues_found > 0:
                # 有问题时显示具体分析结果
                comment += f"- 🔍 **AI智能检查**: 完成了全面的代码分析，发现 {total_issues_found} 个需要关注的问题\n"
                
                if highlights.get('syntax_issues', 0) > 0:
                    comment += f"- ✅ **语法检查**: 发现 {highlights['syntax_issues']} 个语法相关问题\n"
                if highlights.get('security_issues', 0) > 0:
                    comment += f"- 🔒 **安全分析**: 发现 {highlights['security_issues']} 个安全风险\n"
                if highlights.get('performance_issues', 0) > 0:
                    comment += f"- ⚡ **性能分析**: 发现 {highlights['performance_issues']} 个性能问题\n"
                if highlights.get('logic_issues', 0) > 0:
                    comment += f"- 🧠 **逻辑分析**: 发现 {highlights['logic_issues']} 个逻辑问题\n"
                if highlights.get('code_quality_issues', 0) > 0:
                    comment += f"- 🎨 **代码质量**: 发现 {highlights['code_quality_issues']} 个质量问题\n"
                if highlights.get('best_practices_violations', 0) > 0:
                    comment += f"- 📚 **最佳实践**: 发现 {highlights['best_practices_violations']} 个改进建议\n"
            else:
                # 没有问题时的积极表述
                comment += "- 🤖 **AI分析确认**: 代码质量良好，AI智能检查未发现明显问题\n"
                comment += "- ✅ **语法检查**: 通过，无语法错误\n"
                comment += "- 🔒 **安全分析**: 通过，未发现安全风险\n"
                comment += "- ⚡ **性能分析**: 通过，代码性能表现良好\n"
                comment += "- 🧠 **逻辑分析**: 通过，代码逻辑结构清晰\n"
        
        comment += "\n### 📈 问题统计\n\n"
        
        # 添加文件分析详情（折叠式）
        if 'analysis_details' in review_result.summary:
            details = review_result.summary['analysis_details']
            comment += "### 📁 文件分析详情\n\n"
            
            # 分析概要
            total_large = len(details.get('large_files', []))
            total_batch = len(details.get('batch_files', []))
            total_skipped = len(details.get('skipped_files', []))
            total_analyzed = total_large + total_batch
            
            comment += f"**分析概要**: 共分析 {total_analyzed} 个文件\n"
            if total_large > 0:
                comment += f"- 大文件单独分析: {total_large} 个\n"
            if total_batch > 0:
                comment += f"- 批量分析: {total_batch} 个\n"
            if total_skipped > 0:
                comment += f"- 跳过文件: {total_skipped} 个\n"
            comment += "\n"
            
            # 优化的折叠详细信息
            comment += '<details><summary><strong>🔍 点击查看详细文件列表</strong></summary>\n\n'
            
            if details.get('large_files', []):
                comment += "#### 🔍 大文件分析\n"
                comment += "| 文件路径 | 文件大小 | 分析类型 |\n"
                comment += "|---------|---------|----------|\n"
                for file_info in details['large_files']:
                    size_kb = file_info['size'] / 1024
                    comment += f"| `{file_info['path']}` | {size_kb:.1f} KB | 单独分析 |\n"
                comment += "\n"
            
            if details.get('batch_files', []):
                comment += "#### 📦 批量分析文件\n"
                comment += "| 文件路径 | 文件大小 | 分析类型 |\n"
                comment += "|---------|---------|----------|\n"
                for file_info in details['batch_files']:
                    size_kb = file_info['size'] / 1024
                    comment += f"| `{file_info['path']}` | {size_kb:.1f} KB | 批量分析 |\n"
                comment += "\n"
            
            if details.get('skipped_files', []):
                comment += "#### ⏭️ 跳过的文件\n"
                comment += "| 文件路径 | 跳过原因 |\n"
                comment += "|---------|----------|\n"
                for file_info in details['skipped_files']:
                    comment += f"| `{file_info['path']}` | {file_info['reason']} |\n"
                comment += "\n"
            
            comment += "</details>\n\n"
        
        # 添加严重程度统计
        severity_stats = review_result.summary.get('by_severity', {})
        has_severity_issues = any(count > 0 for count in severity_stats.values())
        
        if has_severity_issues:
            comment += "| 严重程度 | 数量 |\n|---------|------|\n"
            for severity in ['CRITICAL', 'ERROR', 'WARNING', 'INFO']:
                count = severity_stats.get(severity, 0)
                if count > 0:
                    emoji = {'CRITICAL': '🔴', 'ERROR': '🟠', 'WARNING': '🟡', 'INFO': '🔵'}[severity]
                    comment += f"| {emoji} {severity} | {count} |\n"
        else:
            comment += "🎉 未发现任何代码问题！\n"
        
        comment += "\n### 🤖 AI分析器统计\n\n"
        
        # 添加AI分析器统计
        source_stats = review_result.summary.get('by_source', {})
        ai_analyzers = {k: v for k, v in source_stats.items() if k.startswith('ai_')}
        
        if ai_analyzers:
            for source, count in ai_analyzers.items():
                emoji_map = {
                    'ai_syntax_checker': '✅',
                    'ai_intelligent_review': '🧠',
                    'ai_summary': '📊'
                }
                emoji = emoji_map.get(source, '🤖')
                friendly_name = source.replace('ai_', '').replace('_', ' ').title()
                comment += f"- {emoji} **{friendly_name}**: {count} 个问题\n"
        else:
            comment += "- 🤖 **AI分析完成**: 所有检查均已通过\n"
        
        # 添加问题详情（优化折叠结构）
        if review_result.issues:
            comment += "\n## 🐛 AI发现问题详情\n\n"
            
            # 按严重程度分组
            issues_by_severity = {}
            for issue in review_result.issues:
                severity = issue.severity.value
                if severity not in issues_by_severity:
                    issues_by_severity[severity] = []
                issues_by_severity[severity].append(issue)
            
            # 输出问题（按严重程度排序）
            for severity in ['CRITICAL', 'ERROR', 'WARNING', 'INFO']:
                if severity in issues_by_severity:
                    issues = issues_by_severity[severity]
                    emoji = {'CRITICAL': '🔴', 'ERROR': '🟠', 'WARNING': '🟡', 'INFO': '🔵'}[severity]
                    
                    # 使用折叠结构优化长列表显示
                    if len(issues) <= 3:
                        # 少量问题直接显示
                        comment += f"### {emoji} {severity} 级问题 ({len(issues)}个)\n\n"
                        for i, issue in enumerate(issues, 1):
                            comment += self._format_issue_item(issue, i)
                    else:
                        # 多个问题使用折叠结构
                        comment += f"### {emoji} {severity} 级问题 ({len(issues)}个)\n\n"
                        
                        # 显示前2个问题
                        for i, issue in enumerate(issues[:2], 1):
                            comment += self._format_issue_item(issue, i)
                        
                        # 其余问题放在折叠区域
                        if len(issues) > 2:
                            comment += f'<details><summary><strong>📋 查看剩余 {len(issues) - 2} 个{severity}级问题</strong></summary>\n\n'
                            
                            for i, issue in enumerate(issues[2:], 3):
                                comment += self._format_issue_item(issue, i)
                            
                            comment += "</details>\n\n"
        
        # 添加AI分析建议和下一步
        comment += self._generate_recommendations(review_result)
        
        # 添加报告生成信息
        comment += f"\n---\n\n*🤖 此报告由自动审查系统生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        
        # 限制评论长度
        if len(comment) > self.config['max_comment_length']:
            comment = comment[:self.config['max_comment_length']] + "\n\n*报告过长，已截断，请查看完整报告*"
        
        return comment
    
    def _format_issue_item(self, issue: ReviewIssue, index: int) -> str:
        """格式化单个问题项"""
        # AI分析器图标
        analyzer_emoji = {
            'ai_syntax_checker': '✅',
            'ai_intelligent_review': '🧠',
            'ai_summary': '📊'
        }.get(issue.source, '🤖')
        
        formatted = f"#### {index}. {analyzer_emoji} {issue.title}\n"
        formatted += f"**类别**: {issue.category}  \n"
        formatted += f"**AI分析器**: {issue.source}  \n"
        
        if issue.file_path:
            formatted += f"**文件**: `{issue.file_path}`"
            if issue.line_number:
                formatted += f" (第{issue.line_number}行)"
            formatted += "  \n"
        
        formatted += f"**AI描述**: {issue.description}  \n"
        
        if issue.suggestion:
            formatted += f"**AI建议**: {issue.suggestion}  \n"
        
        formatted += "\n---\n\n"
        return formatted
    
    def _calculate_quality_score(self, issues: List[ReviewIssue]) -> float:
        """计算质量得分"""
        if not issues:
            return 95.0
        
        base_score = 100.0
        total_deductions = 0.0
        
        severity_weights = {
            'CRITICAL': 30,
            'ERROR': 15,
            'WARNING': 5,
            'INFO': 1
        }
        
        for issue in issues:
            deduction = severity_weights.get(issue.severity.value, 1)
            total_deductions += deduction
        
        # 问题数量惩罚
        if len(issues) > 10:
            total_deductions += (len(issues) - 10) * 2
        elif len(issues) > 5:
            total_deductions += (len(issues) - 5) * 1
        
        final_score = max(0, base_score - total_deductions)
        return round(final_score, 1)
    
    def _generate_recommendations(self, review_result: ReviewResult) -> str:
        """生成AI审查建议（改进版本）"""
        
        recommendations = "## 🎯 AI分析建议和下一步\n\n"
        
        # 计算质量得分用于更精准的建议
        quality_score = self._calculate_quality_score(review_result.issues)
        total_issues = len(review_result.issues)
        critical_issues = [issue for issue in review_result.issues if issue.severity.value == 'CRITICAL']
        error_issues = [issue for issue in review_result.issues if issue.severity.value == 'ERROR']
        
        # 根据状态和具体问题情况给出建议
        if review_result.status == ReviewStatus.PASSED:
            if total_issues == 0:
                recommendations += "✅ **AI分析确认：代码质量优秀，推荐合并**\n\n"
                recommendations += "- 🤖 AI智能检查：所有质量检查均已通过\n"
                recommendations += "- 🔒 安全分析：未发现安全风险\n"
                recommendations += "- ⚡ 性能分析：代码性能表现良好\n"
                recommendations += "- 🧠 逻辑分析：代码逻辑结构清晰\n"
                recommendations += f"- 📊 质量评分：{quality_score}/100 (优秀)\n"
                recommendations += "- ✅ **推荐操作**：可以直接合并\n"
            else:
                recommendations += f"✅ **AI分析：代码质量良好，发现 {total_issues} 个轻微问题，可以合并**\n\n"
                recommendations += f"- 🔍 发现问题：{total_issues} 个（主要为提升建议）\n"
                recommendations += "- 💡 这些问题不影响功能，但修复后可以提升代码质量\n"
                recommendations += f"- 📊 质量评分：{quality_score}/100\n"
                recommendations += "- ✅ **推荐操作**：可以合并，建议后续优化\n"
            
        elif review_result.status == ReviewStatus.WARNING:
            recommendations += f"⚠️ **AI分析：发现 {total_issues} 个问题，建议修复后合并**\n\n"
            warning_issues = [issue for issue in review_result.issues if issue.severity.value == 'WARNING']
            recommendations += f"- ⚠️ WARNING级问题：{len(warning_issues)} 个\n"
            recommendations += "- 🔧 这些问题可能影响代码质量或维护性\n"
            recommendations += f"- 📊 质量评分：{quality_score}/100\n"
            recommendations += "- 🔄 **推荐操作**：修复主要问题后合并\n"
            
        else:  # FAILED
            recommendations += f"❌ **AI分析：发现 {len(critical_issues + error_issues)} 个严重问题，禁止合并**\n\n"
            
            if critical_issues:
                recommendations += f"- 🔴 CRITICAL级问题：{len(critical_issues)} 个（必须修复）\n"
            if error_issues:
                recommendations += f"- 🟠 ERROR级问题：{len(error_issues)} 个（必须修复）\n"
            
            recommendations += f"- 📊 质量评分：{quality_score}/100 (需要改进)\n"
            recommendations += "- 🚫 **严禁合并**：存在阻止性问题\n"
            recommendations += "- 🔧 **必须操作**：修复所有CRITICAL和ERROR级问题\n"
            
            # 列出优先修复的问题
            high_priority_issues = critical_issues + error_issues
            if high_priority_issues:
                recommendations += "\n**🔴 优先修复问题（按重要性排序）：**\n"
                for i, issue in enumerate(high_priority_issues[:5], 1):
                    analyzer_emoji = {
                        'ai_syntax_checker': '✅',
                        'ai_intelligent_review': '🧠', 
                        'ai_summary': '📊'
                    }.get(issue.source, '🤖')
                    file_info = f" ({issue.file_path})" if issue.file_path else ""
                    recommendations += f"{i}. {analyzer_emoji} {issue.severity.value}: {issue.title}{file_info}\n"
                
                if len(high_priority_issues) > 5:
                    recommendations += f"   *... 还有 {len(high_priority_issues) - 5} 个严重问题需要修复*\n"
        
        # 添加AI驱动的通用建议
        recommendations += "\n### 🤖 AI智能建议\n"
        recommendations += "- 🧪 运行完整的单元测试和集成测试\n"
        recommendations += "- 📚 更新相关技术文档和API文档\n"
        recommendations += "- 🎯 遵循团队编码规范和最佳实践\n"
        recommendations += "- 🔍 考虑进行代码覆盖率分析\n"
        recommendations += "- ⚡ 进行性能基准测试\n"
        recommendations += "- 📋 检查是否有遗留的TODO或FIXME注释\n"
        
        # 添加AI分析质量评估（改进版本）
        recommendations += "\n### 🏆 AI分析质量评估\n"
        
        # AI覆盖度分析
        ai_issues = [issue for issue in review_result.issues if issue.source.startswith('ai_')]
        ai_coverage = len(ai_issues) / len(review_result.issues) if review_result.issues else 1.0
        
        recommendations += f"- 📊 代码质量评分：{quality_score}/100"
        if quality_score >= 90:
            recommendations += " (优秀)\n"
        elif quality_score >= 80:
            recommendations += " (良好)\n"
        elif quality_score >= 70:
            recommendations += " (一般)\n"
        else:
            recommendations += " (需要改进)\n"
        
        recommendations += f"- 🤖 AI分析覆盖度：{ai_coverage:.1%}\n"
        
        # 基于实际状态的推荐
        if review_result.status == ReviewStatus.PASSED:
            recommendations += "- ✅ 推荐合并：是（质量达标）\n"
        elif review_result.status == ReviewStatus.WARNING:
            recommendations += "- ⚠️ 推荐合并：建议修复问题后\n"
        else:
            recommendations += "- ❌ 推荐合并：否（存在阻止性问题）\n"
        
        # AI置信度评估
        if ai_coverage >= 0.8 and len(review_result.issues) > 0:
            recommendations += "- 🎯 AI分析置信度：高（覆盖全面）\n"
        elif ai_coverage >= 0.6:
            recommendations += "- 🎯 AI分析置信度：中高（覆盖较好）\n"
        elif len(review_result.issues) == 0:
            recommendations += "- 🎯 AI分析置信度：高（无问题发现）\n"
        else:
            recommendations += "- 🎯 AI分析置信度：中等（建议人工复核）\n"
        
        return recommendations
    
    def _post_comment(self, project_id: str, mr_iid: int, comment: str) -> bool:
        """发布评论到MR"""
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # 发布评论
            mr.notes.create({'body': comment})
            
            self.logger.info(f"评论已发布到MR: {project_id}!{mr_iid}")
            return True
            
        except Exception as e:
            self.logger.error(f"发布评论失败: {e}")
            return False
    
    def _update_labels(self, project_id: str, mr_iid: int, review_result: ReviewResult):
        """更新MR标签"""
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # 获取现有标签
            current_labels = mr.labels or []
            
            # 定义审查相关标签
            review_labels = {
                ReviewStatus.PASSED: ['review:passed', 'quality:good'],
                ReviewStatus.WARNING: ['review:warning', 'quality:needs-improvement'],
                ReviewStatus.FAILED: ['review:failed', 'quality:blocked']
            }
            
            # 移除旧的审查标签
            labels_to_remove = [
                'review:passed', 'review:warning', 'review:failed',
                'quality:good', 'quality:needs-improvement', 'quality:blocked'
            ]
            
            new_labels = [label for label in current_labels if label not in labels_to_remove]
            
            # 添加新标签
            new_labels.extend(review_labels[review_result.status])
            
            # 更新标签
            mr.labels = new_labels
            mr.save()
            
            self.logger.info(f"MR标签已更新: {new_labels}")
            
        except Exception as e:
            self.logger.warning(f"更新MR标签失败: {e}")
    
    def _block_merge(self, project_id: str, mr_iid: int, review_result: ReviewResult):
        """阻止MR合并"""
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # 添加阻止合并的标签
            current_labels = mr.labels or []
            if 'merge:blocked' not in current_labels:
                current_labels.append('merge:blocked')
                mr.labels = current_labels
                mr.save()
            
            # 如果支持，可以设置合并状态
            if hasattr(mr, 'merge_status'):
                # 这里可能需要根据GitLab版本调整
                pass
            
            self.logger.info(f"MR合并已阻止: {project_id}!{mr_iid}")
            
        except Exception as e:
            self.logger.warning(f"阻止MR合并失败: {e}")
    
    def get_review_history(self, project_id: str, mr_iid: int) -> List[Dict[str, Any]]:
        """获取MR的审查历史"""
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # 获取所有讨论
            discussions = mr.discussions.list(all=True)
            
            # 筛选出审查相关的讨论
            review_discussions = []
            for discussion in discussions:
                for note in discussion.attributes.get('notes', []):
                    if note.get('body', '').startswith(('✅ 代码审查报告', '⚠️ 代码审查报告', '❌ 代码审查报告')):
                        review_discussions.append({
                            'id': note.get('id'),
                            'author': note.get('author', {}),
                            'body': note.get('body', ''),
                            'created_at': note.get('created_at'),
                            'system': note.get('system', False)
                        })
            
            return review_discussions
            
        except Exception as e:
            self.logger.error(f"获取审查历史失败: {e}")
            return []
    
    # ========== 基于Commit的增量审查核心方法 ==========
    
    def _should_perform_review(self, project_id: str, mr_iid: int) -> bool:
        """检查是否需要执行审查（基于Commit和评论状态）"""
        try:
            # 如果启用强制重新评论，直接执行审查
            if self.config['force_recomment']:
                self.logger.info(f"MR {project_id}!{mr_iid} 启用强制重新评论，执行审查")
                return True
            
            # 获取MR的最新commit
            latest_commit = self._get_latest_commit(project_id, mr_iid)
            if not latest_commit:
                self.logger.warning(f"无法获取MR {project_id}!{mr_iid} 的最新commit")
                return True  # 如果获取失败，默认执行审查
            
            # 获取上次审查的commit
            last_reviewed_commit = self._get_last_reviewed_commit(project_id, mr_iid)
            
            # 如果没有审查记录，需要审查
            if not last_reviewed_commit:
                self.logger.info(f"MR {project_id}!{mr_iid} 首次审查")
                return True
            
            # 如果commit有变化，需要审查
            if latest_commit != last_reviewed_commit:
                self.logger.info(f"MR {project_id}!{mr_iid} 代码有变更 (commit: {latest_commit[:8]})")
                return True
            
            # 代码无变更，检查是否有系统评论
            has_system_comments = self._has_system_review_comments(project_id, mr_iid)
            
            if has_system_comments:
                self.logger.info(f"MR {project_id}!{mr_iid} 代码无变更且有系统评论，跳过审查")
                return False
            else:
                self.logger.info(f"MR {project_id}!{mr_iid} 代码无变更但无系统评论，执行审查")
                return True
            
        except Exception as e:
            self.logger.error(f"检查是否需要审查失败: {e}")
            return True  # 如果检查失败，默认执行审查
    
    def _has_system_review_comments(self, project_id: str, mr_iid: int) -> bool:
        """检查MR是否有系统审查评论"""
        try:
            comment_history = self._get_comment_history(project_id, mr_iid)
            self.logger.info(f"MR {project_id}!{mr_iid} 找到 {len(comment_history)} 条系统评论")
            
            if comment_history:
                for i, comment in enumerate(comment_history):
                    self.logger.info(f"  评论 {i+1}: {comment['body'][:100]}...")
            
            return len(comment_history) > 0
        except Exception as e:
            self.logger.warning(f"检查系统评论失败: {e}")
            return False  # 如果检查失败，认为没有评论
    
    def _get_latest_commit(self, project_id: str, mr_iid: int) -> Optional[str]:
        """获取MR的最新commit"""
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # 获取MR的所有commit
            commits_obj = mr.commits()
            commits = list(commits_obj)  # 转换为列表
            if commits:
                return commits[0].id  # 返回最新的commit
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取最新commit失败: {e}")
            return None
    
    def _get_last_reviewed_commit(self, project_id: str, mr_iid: int) -> Optional[str]:
        """获取上次审查的commit"""
        try:
            # 从本地存储读取上次审查的commit
            commit_file = self._get_commit_record_file(project_id, mr_iid)
            
            if os.path.exists(commit_file):
                with open(commit_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_reviewed_commit')
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取上次审查commit失败: {e}")
            return None
    
    def _record_reviewed_commit(self, project_id: str, mr_iid: int):
        """记录已审查的commit"""
        try:
            # 获取最新commit
            latest_commit = self._get_latest_commit(project_id, mr_iid)
            if not latest_commit:
                return
            
            # 准备保存的数据
            record_data = {
                'project_id': project_id,
                'mr_iid': mr_iid,
                'last_reviewed_commit': latest_commit,
                'reviewed_at': datetime.now().isoformat(),
                'review_count': self._get_review_count(project_id, mr_iid) + 1
            }
            
            # 保存到文件
            commit_file = self._get_commit_record_file(project_id, mr_iid)
            os.makedirs(os.path.dirname(commit_file), exist_ok=True)
            
            with open(commit_file, 'w', encoding='utf-8') as f:
                json.dump(record_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"已记录审查commit: {latest_commit[:8]}")
            
        except Exception as e:
            self.logger.error(f"记录审查commit失败: {e}")
    
    def _get_commit_record_file(self, project_id: str, mr_iid: int) -> str:
        """获取commit记录文件路径"""
        return os.path.join(project_root, 'output', 'review_commits', f'{project_id}_{mr_iid}.json')
    
    def _get_review_count(self, project_id: str, mr_iid: int) -> int:
        """获取审查次数"""
        try:
            commit_file = self._get_commit_record_file(project_id, mr_iid)
            
            if os.path.exists(commit_file):
                with open(commit_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('review_count', 0)
            
            return 0
            
        except Exception as e:
            self.logger.error(f"获取审查次数失败: {e}")
            return 0
    
    def _post_comment_incremental(self, project_id: str, mr_iid: int, comment: str, review_result: ReviewResult) -> bool:
        """增量评论策略"""
        try:
            # 如果启用强制重新评论，直接更新最新评论（而不是发布新评论）
            if self.config['force_recomment']:
                self.logger.info(f"MR {project_id}!{mr_iid} 启用强制重新评论，更新最新评论")
                return self._update_latest_comment(project_id, mr_iid, comment)
            
            # 获取评论历史
            comment_history = self._get_comment_history(project_id, mr_iid)
            
            # 如果是首次评论，直接发布
            if not comment_history:
                return self._post_new_comment(project_id, mr_iid, comment)
            
            # 检查是否需要更新现有评论
            if self._should_update_comment(comment_history, review_result):
                return self._update_latest_comment(project_id, mr_iid, comment)
            
            # 检查是否有新的问题需要评论
            new_issues = self._get_new_issues(comment_history, review_result)
            if new_issues:
                return self._post_new_comment(project_id, mr_iid, comment)
            
            # 没有新的内容，跳过评论
            self.logger.info(f"MR {project_id}!{mr_iid} 无新内容，跳过评论")
            return True
            
        except Exception as e:
            self.logger.error(f"增量评论失败: {e}")
            return self._post_new_comment(project_id, mr_iid, comment)  # 失败时回退到直接发布
    
    def _get_comment_history(self, project_id: str, mr_iid: int) -> List[Dict[str, Any]]:
        """获取评论历史"""
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # 获取系统评论
            notes = mr.notes.list(order_by='created_at', sort='desc', per_page=50)
            
            system_comments = []
            for note in notes:
                if self._is_system_review_comment(note.body):
                    system_comments.append({
                        'id': note.id,
                        'body': note.body,
                        'created_at': note.created_at,
                        'updated_at': note.updated_at
                    })
            
            return system_comments
            
        except Exception as e:
            self.logger.error(f"获取评论历史失败: {e}")
            return []
    
    def _should_update_comment(self, comment_history: List[Dict[str, Any]], review_result: ReviewResult) -> bool:
        """判断是否应该更新现有评论"""
        if not comment_history:
            return False
        
        # 获取最新评论
        latest_comment = comment_history[0]
        
        # 提取评论信息
        comment_info = self._extract_comment_info(latest_comment['body'])
        current_info = self._extract_review_result_info(review_result)
        
        # 如果状态或问题数量发生变化，则更新
        return (comment_info['status'] != current_info['status'] or
                comment_info['total_issues'] != current_info['total_issues'] or
                comment_info['critical_issues'] != current_info['critical_issues'])
    
    def _extract_comment_info(self, comment_body: str) -> Dict[str, Any]:
        """从评论中提取信息"""
        import re
        
        info = {
            'status': None,
            'total_issues': 0,
            'critical_issues': 0,
            'error_issues': 0,
            'warning_issues': 0
        }
        
        # 提取状态
        if '✅' in comment_body:
            info['status'] = 'PASSED'
        elif '⚠️' in comment_body:
            info['status'] = 'WARNING'
        elif '❌' in comment_body:
            info['status'] = 'FAILED'
        
        # 提取问题数量
        total_match = re.search(r'总计 (\d+) 个问题', comment_body)
        if total_match:
            info['total_issues'] = int(total_match.group(1))
        
        critical_match = re.search(r'严重: (\d+)', comment_body)
        if critical_match:
            info['critical_issues'] = int(critical_match.group(1))
        
        error_match = re.search(r'错误: (\d+)', comment_body)
        if error_match:
            info['error_issues'] = int(error_match.group(1))
        
        warning_match = re.search(r'警告: (\d+)', comment_body)
        if warning_match:
            info['warning_issues'] = int(warning_match.group(1))
        
        return info
    
    def _extract_review_result_info(self, review_result: ReviewResult) -> Dict[str, Any]:
        """从审查结果中提取信息"""
        return {
            'status': review_result.status.value,
            'total_issues': len(review_result.issues),
            'critical_issues': len([i for i in review_result.issues if i.severity in ['CRITICAL', 'BLOCKER']]),
            'error_issues': len([i for i in review_result.issues if i.severity == 'ERROR']),
            'warning_issues': len([i for i in review_result.issues if i.severity == 'WARNING'])
        }
    
    def _get_new_issues(self, comment_history: List[Dict[str, Any]], review_result: ReviewResult) -> List[ReviewIssue]:
        """获取新的问题"""
        # 简化实现：如果状态变化，则认为有新问题
        if not comment_history:
            return review_result.issues
        
        latest_comment = comment_history[0]
        comment_info = self._extract_comment_info(latest_comment['body'])
        current_info = self._extract_review_result_info(review_result)
        
        if comment_info['status'] != current_info['status']:
            return review_result.issues
        
        return []
    
    def _is_system_review_comment(self, comment_body: str) -> bool:
        """判断是否为系统审查评论"""
        return ('🤖' in comment_body or 
                '自动审查' in comment_body or 
                'AI审查' in comment_body or
                'SonarQube' in comment_body)
    
    def _post_new_comment(self, project_id: str, mr_iid: int, comment: str) -> bool:
        """发布新评论"""
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # 发布评论
            mr.notes.create({'body': comment})
            
            self.logger.info(f"评论发布成功: {project_id}!{mr_iid}")
            return True
            
        except Exception as e:
            self.logger.error(f"发布评论失败: {e}")
            return False
    
    def _update_latest_comment(self, project_id: str, mr_iid: int, comment: str) -> bool:
        """更新最新评论"""
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # 获取系统评论
            notes = mr.notes.list(order_by='created_at', sort='desc')
            
            # 找到最新的系统评论
            for note in notes:
                if self._is_system_review_comment(note.body):
                    # 更新评论
                    note.body = comment
                    note.save()
                    
                    self.logger.info(f"评论更新成功: {project_id}!{mr_iid}")
                    return True
            
            # 如果没有找到系统评论，则发布新评论
            return self._post_new_comment(project_id, mr_iid, comment)
            
        except Exception as e:
            self.logger.error(f"更新评论失败: {e}")
            return False


class ReviewResultProcessor:
    """审查结果处理器"""
    
    def __init__(self, gitlab_interactor: Optional[GitLabMRInteractor] = None, log_level: str = 'INFO'):
        """
        初始化结果处理器
        
        Args:
            gitlab_interactor: GitLab交互器
            log_level: 日志级别
        """
        self.gitlab_interactor = gitlab_interactor or GitLabMRInteractor(log_level=log_level)
        self.logger = setup_logging(level=log_level)
    
    def set_force_recomment(self, force_recomment: bool):
        """
        设置是否强制重新评论
        
        Args:
            force_recomment: 是否强制重新评论（忽略已有评论）
        """
        self.gitlab_interactor.set_force_recomment(force_recomment)
    
    def process_and_publish(self, project_id: str, mr_iid: int, review_result: ReviewResult) -> bool:
        """
        处理并发布审查结果
        
        Args:
            project_id: 项目ID
            mr_iid: 合并请求IID
            review_result: 审查结果
            
        Returns:
            是否成功
        """
        try:
            self.logger.info(f"开始处理审查结果: {project_id}!{mr_iid}")
            
            # 1. 保存审查结果到本地（可选）
            self._save_review_result(project_id, mr_iid, review_result)
            
            # 2. 发布到GitLab
            success = self.gitlab_interactor.post_review_result(project_id, mr_iid, review_result)
            
            if success:
                self.logger.info("审查结果处理完成")
                return True
            else:
                self.logger.error("审查结果发布失败")
                return False
                
        except Exception as e:
            self.logger.error(f"处理审查结果失败: {e}")
            return False
    
    def _save_review_result(self, project_id: str, mr_iid: int, review_result: ReviewResult):
        """保存审查结果到本地文件"""
        try:
            # 创建输出目录
            output_dir = os.path.join(project_root, 'output', 'review_results')
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = review_result.review_time.strftime('%Y%m%d_%H%M%S')
            filename = f"review_{project_id}_{mr_iid}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
            
            # 准备保存的数据
            save_data = {
                'project_id': project_id,
                'mr_iid': mr_iid,
                'mr_title': review_result.mr_title,
                'review_time': review_result.review_time.isoformat(),
                'status': review_result.status.value,
                'summary': review_result.summary,
                'issues': [self._serialize_issue(issue) for issue in review_result.issues],
                'metadata': review_result.metadata
            }
            
            # 保存到文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"审查结果已保存到: {filepath}")
            
        except Exception as e:
            self.logger.warning(f"保存审查结果失败: {e}")
    
    def _serialize_issue(self, issue) -> Dict[str, Any]:
        """序列化ReviewIssue对象为字典"""
        return {
            'severity': issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity),
            'category': issue.category,
            'title': issue.title,
            'description': issue.description,
            'file_path': issue.file_path,
            'line_number': issue.line_number,
            'suggestion': issue.suggestion,
            'source': issue.source
        }

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='GitLab MR 审查结果处理器')
    parser.add_argument('--project-id', required=True, help='GitLab项目ID')
    parser.add_argument('--mr-iid', required=True, type=int, help='合并请求IID')
    parser.add_argument('--review-result', help='审查结果JSON文件路径')
    parser.add_argument('--action', choices=['publish', 'history'], default='publish', help='操作类型')
    parser.add_argument('--force-recomment', action='store_true', help='强制重新评论（忽略已有评论）')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    try:
        processor = ReviewResultProcessor(log_level=args.log_level)
        
        # 设置强制重新评论
        if args.force_recomment:
            processor.set_force_recomment(True)
            logger.info("启用强制重新评论模式")
        
        if args.action == 'publish':
            # 如果有审查结果文件，加载它
            if args.review_result:
                with open(args.review_result, 'r', encoding='utf-8') as f:
                    review_data = json.load(f)
                
                # 创建ReviewResult对象
                from automation.mr_review_engine import ReviewResult, ReviewStatus, ReviewIssue
                from datetime import datetime
                
                issues = []
                for issue_data in review_data['issues']:
                    issue = ReviewIssue(
                        severity=ReviewStatus(issue_data['severity']) if issue_data['severity'] in [s.value for s in ReviewStatus] else ReviewStatus.INFO,
                        category=issue_data['category'],
                        title=issue_data['title'],
                        description=issue_data['description'],
                        file_path=issue_data.get('file_path'),
                        line_number=issue_data.get('line_number'),
                        suggestion=issue_data.get('suggestion'),
                        source=issue_data['source']
                    )
                    issues.append(issue)
                
                review_result = ReviewResult(
                    mr_id=review_data['mr_iid'],
                    mr_title=review_data['mr_title'],
                    mr_author=review_data.get('mr_author', 'Unknown'),
                    review_time=datetime.fromisoformat(review_data['review_time']),
                    status=ReviewStatus(review_data['status']),
                    issues=issues,
                    summary=review_data['summary'],
                    metadata=review_data['metadata']
                )
                
                success = processor.process_and_publish(args.project_id, args.mr_iid, review_result)
                print(f"发布结果: {'成功' if success else '失败'}")
            else:
                print("请提供审查结果文件路径")
                
        elif args.action == 'history':
            # 获取审查历史
            history = processor.gitlab_interactor.get_review_history(args.project_id, args.mr_iid)
            print(f"MR {args.mr_iid} 的审查历史:")
            for i, record in enumerate(history, 1):
                print(f"  {i}. {record['created_at']} - {record['author']['name']}")
                print(f"     状态: {'通过' if '✅' in record['body'] else '警告' if '⚠️' in record['body'] else '失败'}")
    
    except Exception as e:
        logger.error(f"处理失败: {e}")
        sys.exit(1)



if __name__ == "__main__":
    main()