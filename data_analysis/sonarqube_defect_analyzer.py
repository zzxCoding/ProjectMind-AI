#!/usr/bin/env python3
"""
SonarQube项目缺陷分析器
分析SonarQube项目的代码质量问题，生成包含AI分析的详细报告
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import markdown

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from shared.utils import setup_logging, format_timestamp
from shared.sonarqube_client import SonarQubeClient, SonarQubeConfig
from shared.ollama_client import OllamaClient
from automation.notification_sender import NotificationSender

class SonarQubeDefectAnalyzer:
    """SonarQube项目缺陷分析器"""
    
    def __init__(self, project_key: str, sonarqube_client: Optional[SonarQubeClient] = None,
                 ollama_client: Optional[OllamaClient] = None, ai_model: Optional[str] = None):
        """
        初始化分析器
        
        Args:
            project_key: SonarQube项目标识符
            sonarqube_client: SonarQube客户端
            ollama_client: Ollama AI客户端
            ai_model: 指定AI分析使用的模型名称
        """
        self.project_key = project_key
        self.sonarqube = sonarqube_client or SonarQubeClient()
        self.ollama = ollama_client or OllamaClient()
        self.ai_model = ai_model
        self.logger = setup_logging()
        self.notification_sender = NotificationSender()
    
    def analyze_project_defects(self, severities: List[str] = None,
                               issue_types: List[str] = None,
                               use_ai: bool = True) -> Dict[str, Any]:
        """
        分析项目缺陷
        
        Args:
            severities: 严重程度过滤 ['INFO', 'MINOR', 'MAJOR', 'CRITICAL', 'BLOCKER']
            issue_types: 问题类型过滤 ['CODE_SMELL', 'BUG', 'VULNERABILITY'] (Community Edition不支持SECURITY_HOTSPOT)
            use_ai: 是否使用AI分析
            
        Returns:
            分析结果字典
        """
        self.logger.info(f"开始分析SonarQube项目 {self.project_key} 的缺陷")
        
        # 设置默认过滤条件
        if not severities:
            severities = ['CRITICAL', 'BLOCKER', 'MAJOR']
        if not issue_types:
            issue_types = ['BUG', 'VULNERABILITY', 'CODE_SMELL']  # Community Edition不支持SECURITY_HOTSPOT
        
        # 获取项目信息
        project_info = self.sonarqube.get_project_info(self.project_key)
        if not project_info:
            raise ValueError(f"无法获取项目信息: {self.project_key}")
        
        # 获取项目度量数据
        measures = self.sonarqube.get_project_measures(self.project_key)
        
        # 获取质量门状态
        quality_gate = self.sonarqube.get_quality_gate_status(self.project_key)
        
        # 获取问题列表（保留原始数据统计）
        self.logger.info("获取项目问题数据...")
        raw_issues = self.sonarqube.get_project_issues(
            self.project_key,
            severities=severities,
            types=issue_types,
            statuses=['OPEN', 'CONFIRMED', 'REOPENED']
        )
        
        # 记录原始问题数量
        total_raw_issues = len(raw_issues)
        self.logger.info(f"原始问题数量: {total_raw_issues}")
        
        # 如果问题数量过多，进行智能采样
        if total_raw_issues > 2000:
            self.logger.warning(f"问题数量过多({total_raw_issues} > 2000)，启用智能采样")
            issues = self._manual_sampling(raw_issues, 2000)
        else:
            issues = raw_issues
        
        # 调试：检查返回的issues类型
        self.logger.info(f"issues类型: {type(issues)}")
        if issues and len(issues) > 0:
            self.logger.info(f"第一个issue类型: {type(issues[0])}")
            if isinstance(issues[0], dict):
                self.logger.info(f"第一个issue内容: {list(issues[0].keys())}")
            else:
                self.logger.info(f"第一个issue内容: {issues[0]}")
        
        # 获取安全热点
        hotspots = self.sonarqube.get_project_hotspots(
            self.project_key,
            statuses=['TO_REVIEW', 'ACKNOWLEDGED']
        )
        
        self.logger.info(f"获取到 {len(issues)} 个问题，{len(hotspots)} 个安全热点")
        
        # 调试：再次检查issues内容
        self.logger.info(f"准备分类分析 - issues类型: {type(issues)}")
        if issues:
            self.logger.info(f"issues[0]类型: {type(issues[0]) if len(issues) > 0 else 'empty'}")
            if len(issues) > 0 and isinstance(issues[0], str):
                self.logger.error(f"检测到字符串类型的issues: {issues[:5]}")  # 显示前5个
                # 修复：如果issues是响应对象的字段名列表，尝试从原始响应中提取真正的问题
                self.logger.info("尝试修复issues数据...")
                # 重新获取问题数据
                fixed_issues = self.sonarqube.get_project_issues(
                    self.project_key,
                    severities=severities,
                    types=issue_types,
                    statuses=['OPEN', 'CONFIRMED', 'REOPENED']
                )
                self.logger.info(f"修复后的issues类型: {type(fixed_issues)}")
                issues = fixed_issues
        
        # 分类分析问题
        categorized_issues = self._categorize_issues(issues)
        categorized_hotspots = self._categorize_hotspots(hotspots)
        
        # 计算统计摘要
        summary = self._calculate_summary(issues, raw_issues, total_raw_issues, hotspots, measures, quality_gate)
        
        # AI分析
        ai_analysis = None
        if use_ai:
            self.logger.info("开始执行AI缺陷分析...")
            ai_analysis = self._generate_ai_analysis(
                issues, hotspots, measures, categorized_issues, categorized_hotspots
            )
            self.logger.info("AI缺陷分析完成")
        
        return {
            'project_info': project_info,
            'analysis_config': {
                'severities': severities,
                'issue_types': issue_types,
                'ai_analysis_enabled': use_ai
            },
            'summary': summary,
            'measures': measures,
            'quality_gate': quality_gate,
            'issues': {
                'raw_data': issues,
                'categorized': categorized_issues,
                'total_count': len(issues)
            },
            'security_hotspots': {
                'raw_data': hotspots,
                'categorized': categorized_hotspots,
                'total_count': len(hotspots)
            },
            'ai_analysis': ai_analysis,
            'ai_model_info': {
                'enabled': use_ai,
                'model': self.ai_model or self.ollama.config.default_model if use_ai else None
            },
            'generated_at': format_timestamp()
        }
    
    def _categorize_issues(self, issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按类型和严重性分类问题"""
        categorized = {
            'by_type': defaultdict(list),
            'by_severity': defaultdict(list),
            'by_component': defaultdict(list),
            'by_rule': defaultdict(list)
        }
        
        for issue in issues:
            # 调试：检查每个issue的类型
            if not isinstance(issue, dict):
                self.logger.error(f"期望字典类型的issue，但得到了: {type(issue)} - {issue}")
                continue
                
            issue_type = issue.get('type', 'UNKNOWN')
            severity = issue.get('severity', 'UNKNOWN')
            component = issue.get('component', 'UNKNOWN')
            rule = issue.get('rule', 'UNKNOWN')
            
            categorized['by_type'][issue_type].append(issue)
            categorized['by_severity'][severity].append(issue)
            categorized['by_component'][component].append(issue)
            categorized['by_rule'][rule].append(issue)
        
        # 转换为普通字典
        for category in categorized:
            categorized[category] = dict(categorized[category])
        
        return categorized
    
    def _categorize_hotspots(self, hotspots: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按类别和状态分类安全热点"""
        categorized = {
            'by_category': defaultdict(list),
            'by_status': defaultdict(list),
            'by_vulnerability_probability': defaultdict(list),
            'by_component': defaultdict(list)
        }
        
        for hotspot in hotspots:
            category = hotspot.get('securityCategory', 'UNKNOWN')
            status = hotspot.get('status', 'UNKNOWN')
            vuln_prob = hotspot.get('vulnerabilityProbability', 'UNKNOWN')
            component = hotspot.get('component', 'UNKNOWN')
            
            categorized['by_category'][category].append(hotspot)
            categorized['by_status'][status].append(hotspot)
            categorized['by_vulnerability_probability'][vuln_prob].append(hotspot)
            categorized['by_component'][component].append(hotspot)
        
        # 转换为普通字典
        for category in categorized:
            categorized[category] = dict(categorized[category])
        
        return categorized
    
    def _calculate_summary(self, issues: List[Dict[str, Any]], 
                          raw_issues: List[Dict[str, Any]],
                          total_raw_issues: int,
                          hotspots: List[Dict[str, Any]],
                          measures: Dict[str, Any],
                          quality_gate: Dict[str, Any]) -> Dict[str, Any]:
        """计算统计摘要"""
        # 问题统计（基于原始数据）
        issue_stats = {
            'total': total_raw_issues,  # 原始总数
            'by_type': {},
            'by_severity': {}
        }
        
        # 基于原始数据进行统计
        for issue in raw_issues:
            # 类型检查，防止字符串错误
            if not isinstance(issue, dict):
                self.logger.error(f"期望字典类型的issue，但得到了: {type(issue)} - {issue}")
                continue
                
            issue_type = issue.get('type', 'UNKNOWN')
            severity = issue.get('severity', 'UNKNOWN')
            
            issue_stats['by_type'][issue_type] = issue_stats['by_type'].get(issue_type, 0) + 1
            issue_stats['by_severity'][severity] = issue_stats['by_severity'].get(severity, 0) + 1
        
        # 添加采样信息
        issue_stats['sampled_total'] = len(issues)  # 采样后数量
        issue_stats['sampled'] = total_raw_issues > 2000  # 是否经过采样
        
        # 安全热点统计
        hotspot_stats = {
            'total': len(hotspots),
            'by_category': {},
            'by_status': {},
            'by_vulnerability_probability': {}
        }
        
        for hotspot in hotspots:
            # 类型检查，防止字符串错误
            if not isinstance(hotspot, dict):
                self.logger.error(f"期望字典类型的hotspot，但得到了: {type(hotspot)} - {hotspot}")
                continue
                
            category = hotspot.get('securityCategory', 'UNKNOWN')
            status = hotspot.get('status', 'UNKNOWN')
            vuln_prob = hotspot.get('vulnerabilityProbability', 'UNKNOWN')
            
            hotspot_stats['by_category'][category] = hotspot_stats['by_category'].get(category, 0) + 1
            hotspot_stats['by_status'][status] = hotspot_stats['by_status'].get(status, 0) + 1
            hotspot_stats['by_vulnerability_probability'][vuln_prob] = hotspot_stats['by_vulnerability_probability'].get(vuln_prob, 0) + 1
        
        # 计算风险等级
        risk_level = self._calculate_risk_level(issue_stats, hotspot_stats, measures)
        
        # 质量门状态
        gate_status = quality_gate.get('status', 'UNKNOWN')
        gate_conditions = quality_gate.get('conditions', [])
        
        return {
            'issue_stats': issue_stats,
            'hotspot_stats': hotspot_stats,
            'quality_gate_status': gate_status,
            'quality_gate_conditions': len(gate_conditions),
            'failed_conditions': len([c for c in gate_conditions if c.get('status') == 'ERROR']),
            'risk_level': risk_level,
            'key_metrics': {
                'bugs': measures.get('bugs', 0),
                'vulnerabilities': measures.get('vulnerabilities', 0),
                'code_smells': measures.get('code_smells', 0),
                'security_hotspots': measures.get('security_hotspots', 0),
                'coverage': measures.get('coverage', 0),
                'duplicated_lines_density': measures.get('duplicated_lines_density', 0),
                'maintainability_rating': measures.get('maintainability_rating', 'A'),
                'reliability_rating': measures.get('reliability_rating', 'A'),
                'security_rating': measures.get('security_rating', 'A')
            }
        }
    
    def _calculate_risk_level(self, issue_stats: Dict[str, Any], 
                            hotspot_stats: Dict[str, Any],
                            measures: Dict[str, Any]) -> str:
        """计算项目风险等级"""
        score = 0
        
        # 基于问题严重性计算分数
        severity_weights = {'BLOCKER': 10, 'CRITICAL': 8, 'MAJOR': 5, 'MINOR': 2, 'INFO': 1}
        for severity, count in issue_stats.get('by_severity', {}).items():
            weight = severity_weights.get(severity, 1)
            score += count * weight
        
        # 基于安全热点计算分数
        vuln_weights = {'HIGH': 8, 'MEDIUM': 5, 'LOW': 2}
        for prob, count in hotspot_stats.get('by_vulnerability_probability', {}).items():
            weight = vuln_weights.get(prob, 1)
            score += count * weight
        
        # 基于度量数据调整分数
        bugs = measures.get('bugs', 0)
        vulnerabilities = measures.get('vulnerabilities', 0)
        score += bugs * 5 + vulnerabilities * 8
        
        # 确定风险等级
        if score >= 100:
            return 'CRITICAL'  # 极高风险
        elif score >= 50:
            return 'HIGH'      # 高风险
        elif score >= 20:
            return 'MEDIUM'    # 中等风险
        elif score >= 5:
            return 'LOW'       # 低风险
        else:
            return 'MINIMAL'   # 极低风险
    
    def _generate_ai_analysis(self, issues: List[Dict[str, Any]], 
                            hotspots: List[Dict[str, Any]],
                            measures: Dict[str, Any],
                            categorized_issues: Dict[str, Any],
                            categorized_hotspots: Dict[str, Any]) -> str:
        """生成AI分析报告"""
        try:
            # 构建AI分析提示词
            # 🆕 增强版AI分析提示词
            # 计算问题模式
            issue_patterns = self._analyze_issue_patterns_for_ai(issues)
            quality_score = self._calculate_quality_score_for_ai(measures, categorized_issues['by_severity'])
            
            prompt = f"""
作为资深代码质量专家和架构师，请对以下SonarQube项目进行深度质量分析：

## 项目概览
- **项目标识**: {self.project_key}
- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **综合质量评分**: {quality_score}/100

## 质量现状分析
**总问题数**: {len(issues)} | **安全热点**: {len(hotspots)}

**问题分类**:
"""
            
            # 添加问题类型统计
            for issue_type, issues_list in categorized_issues['by_type'].items():
                prompt += f"- {issue_type}: {len(issues_list)}个\n"
            
            prompt += "\n**严重程度分布**:\n"
            for severity, issues_list in categorized_issues['by_severity'].items():
                prompt += f"- {severity}: {len(issues_list)}个\n"
            
            prompt += f"\n## 关键质量指标\n"
            prompt += f"- **可靠性**: Bugs({measures.get('bugs', 0)}) | 评级({measures.get('reliability_rating', 'N/A')})\n"
            prompt += f"- **安全性**: 漏洞({measures.get('vulnerabilities', 0)}) | 热点({measures.get('security_hotspots', 0)}) | 评级({measures.get('security_rating', 'N/A')})\n"
            prompt += f"- **可维护性**: 代码异味({measures.get('code_smells', 0)}) | 评级({measures.get('maintainability_rating', 'N/A')})\n"
            prompt += f"- **测试覆盖率**: {measures.get('coverage', 'N/A')}%\n"
            prompt += f"- **重复代码密度**: {measures.get('duplicated_lines_density', 'N/A')}%\n"
            
            prompt += f"\n## 问题模式分析\n{issue_patterns}\n\n## 具体问题示例\n"
            
            # 添加一些具体问题示例
            critical_issues = [issue for issue in issues if issue.get('severity') in ['BLOCKER', 'CRITICAL']]
            if critical_issues:
                prompt += "### 高优先级问题示例:\n"
                for i, issue in enumerate(critical_issues[:8], 1):  # 只展示前8个
                    component = issue.get('component', '').split(':')[-1] if ':' in issue.get('component', '') else issue.get('component', 'N/A')
                    prompt += f"{i}. **{issue.get('severity', 'UNKNOWN')}** - {issue.get('message', 'N/A')} (文件: {component}, 行: {issue.get('line', 'N/A')})\n"
            
            # 添加安全热点示例
            high_risk_hotspots = [hs for hs in hotspots if hs.get('vulnerabilityProbability') == 'HIGH']
            if high_risk_hotspots:
                prompt += "\n### 高风险安全热点示例:\n"
                for i, hotspot in enumerate(high_risk_hotspots[:5], 1):  # 只展示前5个
                    component = hotspot.get('component', '').split(':')[-1] if ':' in hotspot.get('component', '') else hotspot.get('component', 'N/A')
                    prompt += f"{i}. **{hotspot.get('securityCategory', 'UNKNOWN')}** - {hotspot.get('message', 'N/A')} (文件: {component}, 行: {hotspot.get('line', 'N/A')})\n"
            
            prompt += f"""

## 深度分析任务
请基于以上数据提供专业的质量分析报告：

### 1. **根因分析**
- 分析问题产生的根本原因（团队习惯、流程缺陷、技术选型等）
- 识别重复出现的问题模式

### 2. **业务风险评估** 
- 从业务角度评估当前问题对系统稳定性、安全性的影响
- 预测不修复可能导致的风险

### 3. **质量改进路线图**
- 短期修复优先级（1-2周内必须解决的问题）
- 中期改进计划（1-3个月内的质量提升）
- 长期架构优化建议

### 4. **团队协作建议**
- 开发流程改进建议（代码审查、测试流程等）
- 工具和自动化改进建议

## 输出要求
- 使用中文，保持专业性和实用性
- 重点关注可操作的具体建议
- 避免泛泛而谈，基于实际数据分析
- 内容控制在500字以内，条理清晰
"""
            
            # 调用AI分析
            try:
                self.logger.debug("开始调用Ollama API进行缺陷分析...")
                result = self.ollama.analyze_text(prompt, model=self.ai_model, analysis_type="custom")
                self.logger.debug("Ollama API调用成功")
                return result
            except Exception as ollama_error:
                self.logger.warning(f"Ollama API调用失败: {ollama_error}")
                return f"AI分析不可用：Ollama服务可能未启动或超时"
            
        except Exception as e:
            self.logger.error(f"生成AI分析失败: {e}")
            return f"分析失败: {str(e)}"
    
    def generate_markdown_report(self, analysis_data: Dict[str, Any]) -> str:
        """生成优化后的Markdown格式报告"""
        md_content = []
        
        # 标题和基本信息
        project_name = analysis_data['project_info']['name']
        project_key = analysis_data['project_info']['key']
        
        md_content.append(f"# 📊 SonarQube项目质量分析报告")
        md_content.append(f"")
        
        # 添加SonarQube项目链接
        sonarqube_url = self.sonarqube.config.url
        project_url = f"{sonarqube_url}/dashboard?id={self.project_key}"
        md_content.append(f"🔗 **[在SonarQube中查看项目详情]({project_url})**")
        md_content.append("")
        
        # 🆕 执行摘要 - 新增部分
        self._add_executive_summary(md_content, analysis_data)
        
        # 项目基本信息卡片
        md_content.append("## 🏗️ 项目信息")
        md_content.append(f"| 项目 | 内容 |")
        md_content.append(f"|------|------|")
        md_content.append(f"| **项目名称** | `{project_name}` |")
        md_content.append(f"| **项目标识** | `{project_key}` |")
        md_content.append(f"| **上次分析时间** | `{analysis_data['project_info'].get('lastAnalysisDate', 'N/A')}` |")
        md_content.append(f"| **报告生成时间** | `{analysis_data['generated_at']}` |")
        md_content.append(f"")
        
        # 质量门状态
        summary = analysis_data['summary']
        quality_gate_status = summary['quality_gate_status']
        gate_emoji = "✅" if quality_gate_status == "OK" else "❌" if quality_gate_status == "ERROR" else "⚠️"
        
        md_content.append("## 🚦 质量门状态")
        md_content.append(f"**状态**: {gate_emoji} `{quality_gate_status}`")
        
        failed_conditions = summary.get('failed_conditions', 0)
        total_conditions = summary.get('quality_gate_conditions', 0)
        if failed_conditions > 0:
            md_content.append(f"**失败条件**: `{failed_conditions}/{total_conditions}`")
        md_content.append(f"")
        
        # 业务影响评估 - 新增部分
        self._add_business_impact_section(md_content, analysis_data)
        
        # 风险等级评估
        risk_level = summary['risk_level']
        risk_emoji = {
            'CRITICAL': '🔴',
            'HIGH': '🟠', 
            'MEDIUM': '🟡',
            'LOW': '🟢',
            'MINIMAL': '⚪'
        }.get(risk_level, '❓')
        
        md_content.append("## ⚡ 风险等级评估")
        md_content.append(f"**项目风险等级**: {risk_emoji} `{risk_level}`")
        md_content.append(f"")
        
        # 核心指标仪表盘
        md_content.append("## 📈 核心质量指标")
        md_content.append("")
        key_metrics = summary['key_metrics']
        
        md_content.append(f"| 指标 | 数值 | 评级/状态 |")
        md_content.append(f"|------|------|----------|")
        md_content.append(f"| **🐛 Bugs** | `{key_metrics['bugs']}` | {self._get_rating_emoji(key_metrics['reliability_rating'])} {key_metrics['reliability_rating']} |")
        md_content.append(f"| **🔓 漏洞** | `{key_metrics['vulnerabilities']}` | {self._get_rating_emoji(key_metrics['security_rating'])} {key_metrics['security_rating']} |")
        md_content.append(f"| **💨 代码异味** | `{key_metrics['code_smells']}` | {self._get_rating_emoji(key_metrics['maintainability_rating'])} {key_metrics['maintainability_rating']} |")
        md_content.append(f"| **🔥 安全热点** | `{key_metrics['security_hotspots']}` | - |")
        md_content.append(f"| **📊 测试覆盖率** | `{key_metrics['coverage']}`% | {'✅' if key_metrics['coverage'] >= 80 else '⚠️' if key_metrics['coverage'] >= 60 else '❌'} |")
        md_content.append(f"| **📋 重复代码密度** | `{key_metrics['duplicated_lines_density']}`% | {'✅' if key_metrics['duplicated_lines_density'] <= 3 else '⚠️' if key_metrics['duplicated_lines_density'] <= 5 else '❌'} |")
        md_content.append("")
        
        # 问题统计分布
        md_content.append("## 🔍 问题分布统计")
        
        issue_stats = summary['issue_stats']
        hotspot_stats = summary['hotspot_stats']
        
        # 按类型统计 - 增强显示
        md_content.append("### 📊 缺陷类型分布")
        md_content.append("")
        
        total_issues = issue_stats['total']
        if total_issues > 0:
            md_content.append(f"**总计发现 `{total_issues}` 个代码质量问题**")
            md_content.append("")
            
            md_content.append("| 缺陷类型 | 数量 | 占比 | 说明 |")
            md_content.append("|----------|------|------|------|")
            
            # 定义类型说明
            type_descriptions = {
                'BUG': '功能性错误，可能导致程序异常或结果错误',
                'VULNERABILITY': '安全漏洞，存在被恶意利用的风险', 
                'CODE_SMELL': '代码异味，影响代码可读性和维护性'
            }
            
            # 按重要性排序显示
            type_order = ['BUG', 'VULNERABILITY', 'CODE_SMELL']
            for issue_type in type_order:
                count = issue_stats['by_type'].get(issue_type, 0)
                if count > 0:
                    percentage = (count / total_issues * 100)
                    type_emoji = {'BUG': '🐛', 'VULNERABILITY': '🔓', 'CODE_SMELL': '💨'}.get(issue_type, '❓')
                    description = type_descriptions.get(issue_type, '')
                    md_content.append(f"| {type_emoji} **{issue_type}** | `{count}` | `{percentage:.1f}%` | {description} |")
        else:
            md_content.append("✅ **未发现代码质量问题**")
        
        md_content.append("")
        
        # 按严重程度统计
        md_content.append("### 🚨 按严重程度统计")
        md_content.append(f"| 严重程度 | 数量 | 优先级 |")
        md_content.append(f"|----------|------|--------|")
        
        severity_order = ['BLOCKER', 'CRITICAL', 'MAJOR', 'MINOR', 'INFO']
        for severity in severity_order:
            count = issue_stats['by_severity'].get(severity, 0)
            if count > 0:
                severity_emoji = {
                    'BLOCKER': '🔴',
                    'CRITICAL': '🟠', 
                    'MAJOR': '🟡',
                    'MINOR': '🔵',
                    'INFO': '⚪'
                }.get(severity, '❓')
                priority = {
                    'BLOCKER': '立即处理',
                    'CRITICAL': '高优先级',
                    'MAJOR': '中优先级', 
                    'MINOR': '低优先级',
                    'INFO': '信息'
                }.get(severity, '未知')
                md_content.append(f"| {severity_emoji} {severity} | `{count}` | {priority} |")
        md_content.append("")
        
        # 安全热点统计  
        if hotspot_stats['total'] > 0:
            md_content.append("### 🔥 安全热点统计")
            md_content.append(f"**总计**: `{hotspot_stats['total']}` 个")
            md_content.append("")
            
            # 按风险概率统计
            md_content.append(f"| 风险概率 | 数量 | 处理建议 |")
            md_content.append(f"|----------|------|----------|")
            
            prob_order = ['HIGH', 'MEDIUM', 'LOW']
            for prob in prob_order:
                count = hotspot_stats['by_vulnerability_probability'].get(prob, 0)
                if count > 0:
                    prob_emoji = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(prob, '❓')
                    suggestion = {'HIGH': '立即审查', 'MEDIUM': '及时审查', 'LOW': '定期审查'}.get(prob, '审查')
                    md_content.append(f"| {prob_emoji} {prob} | `{count}` | {suggestion} |")
            md_content.append("")
        
        # AI智能分析
        if analysis_data['ai_analysis']:
            md_content.append("## 🤖 AI智能分析")
            md_content.append("")
            md_content.append("> 🧠 **基于项目质量数据的智能洞察**")
            md_content.append("")
            
            # 将AI分析格式化为引用块
            ai_lines = analysis_data['ai_analysis'].split('\n')
            for line in ai_lines:
                if line.strip():
                    if line.startswith('###') or line.startswith('**'):
                        md_content.append(f"> {line}")
                    else:
                        md_content.append(f"> {line}")
                else:
                    md_content.append(">")
            
            md_content.append("")
            md_content.append("> 💡 *以上分析基于SonarQube数据和代码质量模式生成*")
            md_content.append("")
        
        # 问题详情
        self._add_issue_details_section(md_content, analysis_data)
        
        # 务实的修复建议
        self._add_practical_recommendations(md_content, analysis_data)
        
        # 🆕 修复优先级矩阵 - 替换原有的修复建议
        self._add_priority_matrix_section(md_content, analysis_data)
        
        # 附录
        md_content.append("## 📋 附录")
        md_content.append("")
        md_content.append("### 分析说明")
        md_content.append("- 本报告基于SonarQube静态代码分析数据生成")
        
        actual_total = issue_stats.get('total', len(analysis_data['issues']['raw_data']))
        sampled_total = issue_stats.get('sampled_total', len(analysis_data['issues']['raw_data']))
        is_sampled = issue_stats.get('sampled', False)
        
        if is_sampled:
            md_content.append(f"- **项目实际缺陷**: `{actual_total}` 个代码质量问题")
            md_content.append(f"- **智能采样分析**: `{sampled_total}` 个问题用于详细分析")
            md_content.append("- ⚠️ **大数据量采样策略**:")
            md_content.append("  - 🔴 BLOCKER/CRITICAL问题: 100% 全量分析")
            md_content.append("  - 🟡 MAJOR问题: 30% 分层采样")
            md_content.append("  - 🟢 MINOR/INFO问题: 10% 代表性采样")
        else:
            md_content.append(f"- **分析问题数量**: `{actual_total}` 个代码质量问题")
            
        md_content.append(f"- 检查了 `{hotspot_stats['total']}` 个安全热点")
        
        # 添加AI模型信息
        ai_model_info = analysis_data.get('ai_model_info', {})
        if ai_model_info.get('enabled'):
            ai_model = ai_model_info.get('model', '未知模型')
            md_content.append(f"- AI分析基于Ollama本地模型生成，使用模型: **{ai_model}**")
        else:
            md_content.append("- 本次分析未启用AI功能")
        
        md_content.append("")
        
        # 添加SonarQube项目链接
        md_content.append("### 🔗 查看详情")
        sonarqube_url = self.sonarqube.config.url
        project_url = f"{sonarqube_url}/dashboard?id={self.project_key}"
        md_content.append(f"📊 [在SonarQube中查看完整项目分析]({project_url})")
        md_content.append("")
        
        return "\n".join(md_content)
    
    def _add_executive_summary(self, md_content: list, analysis_data: dict):
        """添加执行摘要部分"""
        md_content.append("## 📋 执行摘要")
        md_content.append("")
        
        summary = analysis_data['summary']
        issue_stats = summary['issue_stats']
        risk_level = summary['risk_level']
        total_issues = issue_stats['total']
        critical_issues = issue_stats['by_severity'].get('BLOCKER', 0) + issue_stats['by_severity'].get('CRITICAL', 0)
        
        # 整体评级
        risk_emoji = {
            'CRITICAL': '🔴',
            'HIGH': '🟠', 
            'MEDIUM': '🟡',
            'LOW': '🟢',
            'MINIMAL': '⚪'
        }.get(risk_level, '❓')
        
        md_content.append(f"### 🎯 关键发现")
        md_content.append(f"- **整体风险等级**: {risk_emoji} **{risk_level}**")
        
        # 显示实际数量和采样数量
        actual_total = issue_stats.get('total', total_issues)
        sampled_total = issue_stats.get('sampled_total', len(analysis_data['issues']['raw_data']))
        is_sampled = issue_stats.get('sampled', False)
        
        if is_sampled:
            md_content.append(f"- **实际缺陷总数**: **{actual_total}** 个代码质量问题")
            md_content.append(f"- **智能采样分析**: **{sampled_total}** 个问题 (高优先级100%保留)")
        else:
            md_content.append(f"- **发现问题总数**: **{actual_total}** 个代码质量问题")
        
        if critical_issues > 0:
            md_content.append(f"- **紧急问题**: **{critical_issues}** 个严重缺陷需要立即处理")
        else:
            md_content.append("- **紧急问题**: ✅ 无严重阻塞性问题")
        
        # 业务影响快速评估
        md_content.append("")
        md_content.append("### 💼 业务影响快速评估")
        
        vulnerabilities = issue_stats['by_type'].get('VULNERABILITY', 0)
        bugs = issue_stats['by_type'].get('BUG', 0)
        code_smells = issue_stats['by_type'].get('CODE_SMELL', 0)
        
        if vulnerabilities > 0:
            md_content.append(f"- **安全风险**: 🔴 **高** - 发现 **{vulnerabilities}** 个安全漏洞，存在数据泄露风险")
        else:
            md_content.append("- **安全风险**: 🟢 **低** - 未发现安全漏洞")
            
        if bugs > 0:
            md_content.append(f"- **功能风险**: {'🔴 **高**' if bugs > 10 else '🟡 **中**'} - **{bugs}** 个功能缺陷可能影响用户体验")
        else:
            md_content.append("- **功能风险**: 🟢 **低** - 未发现功能性缺陷")
            
        if code_smells > 20:
            md_content.append(f"- **维护风险**: 🟡 **中** - **{code_smells}** 个代码异味影响长期维护")
        elif code_smells > 0:
            md_content.append(f"- **维护风险**: 🟢 **低** - **{code_smells}** 个代码异味，整体可控")
        else:
            md_content.append("- **维护风险**: 🟢 **低** - 代码质量良好")
        
        # 行动建议
        md_content.append("")
        md_content.append("### ⚡ 立即行动建议")
        
        if critical_issues > 0:
            days_needed = min(7, max(1, critical_issues // 2 + 1))
            md_content.append(f"- 🚨 **紧急修复**: **{days_needed}** 天内完成所有严重问题修复")
            
        if vulnerabilities > 0:
            md_content.append("- 🛡️ **安全优先**: 立即审查所有安全漏洞，优先修复高风险项")
            
        # 资源投入建议
        team_size = self._recommend_team_size(total_issues)
        estimated_hours = self._estimate_fix_time(issue_stats['by_severity'], total_issues)
        
        md_content.append(f"- 💰 **资源配置**: 建议投入 **{team_size}** 名开发人员，预计 **{estimated_hours}** 工时")
        
        md_content.append("")
        md_content.append("---")
        md_content.append("")
    
    def _add_business_impact_section(self, md_content: list, analysis_data: dict):
        """添加业务影响评估部分"""
        md_content.append("## 💼 业务影响评估")
        md_content.append("")
        
        issue_stats = analysis_data['summary']['issue_stats']
        measures = analysis_data.get('measures', {})
        
        # 计算性能相关问题
        performance_issues = 0
        memory_issues = 0
        
        for issue in analysis_data['issues']['raw_data']:
            if isinstance(issue, dict):
                rule = issue.get('rule', '').lower()
                message = issue.get('message', '').lower()
                
                if any(keyword in rule or keyword in message for keyword in ['performance', 'memory', 'resource', 'timeout']):
                    performance_issues += 1
                if any(keyword in rule or keyword in message for keyword in ['memory', 'leak', 'heap']):
                    memory_issues += 1
        
        md_content.append("| 影响维度 | 风险等级 | 详细说明 | 建议措施 |")
        md_content.append("|----------|----------|----------|----------|")
        
        # 用户体验影响
        ux_risk = "🔴 高" if performance_issues > 5 else "🟡 中" if performance_issues > 2 else "🟢 低"
        ux_desc = f"{performance_issues}个性能问题" + ("可能导致响应延迟" if performance_issues > 0 else "")
        ux_action = "立即优化关键路径" if performance_issues > 5 else "监控性能指标" if performance_issues > 0 else "维持现状"
        md_content.append(f"| **用户体验** | {ux_risk} | {ux_desc} | {ux_action} |")
        
        # 数据安全影响
        vuln_count = issue_stats['by_type'].get('VULNERABILITY', 0)
        security_risk = "🔴 高" if vuln_count > 3 else "🟡 中" if vuln_count > 0 else "🟢 低"
        security_desc = f"{vuln_count}个安全漏洞" if vuln_count > 0 else "未发现安全风险"
        security_action = "立即修复所有漏洞" if vuln_count > 3 else "尽快修复" if vuln_count > 0 else "加强安全检测"
        md_content.append(f"| **数据安全** | {security_risk} | {security_desc} | {security_action} |")
        
        # 系统稳定性影响
        bugs = issue_stats['by_type'].get('BUG', 0)
        stability_risk = "🔴 高" if bugs > 10 else "🟡 中" if bugs > 3 else "🟢 低"
        stability_desc = f"{bugs}个功能缺陷"
        if memory_issues > 0:
            stability_desc += f"，{memory_issues}个内存问题"
        stability_action = "紧急修复核心缺陷" if bugs > 10 else "按优先级修复" if bugs > 0 else "保持监控"
        md_content.append(f"| **系统稳定性** | {stability_risk} | {stability_desc} | {stability_action} |")
        
        # 合规性影响
        coverage = measures.get('coverage', 0)
        compliance_risk = "🟡 中" if coverage < 50 else "🟢 低"
        compliance_desc = f"测试覆盖率{coverage:.1f}%" + ("，可能影响审计" if coverage < 50 else "，符合标准")
        compliance_action = "提升测试覆盖率" if coverage < 50 else "维持质量标准"
        md_content.append(f"| **合规性** | {compliance_risk} | {compliance_desc} | {compliance_action} |")
        
        md_content.append("")
    
    def _recommend_team_size(self, total_issues: int) -> int:
        """根据问题数量推荐团队规模"""
        if total_issues > 50:
            return 3
        elif total_issues > 20:
            return 2
        else:
            return 1
    
    def _estimate_fix_time(self, severity_stats: dict, _: int) -> int:
        """估算修复时间（小时）"""
        blocker_hours = severity_stats.get('BLOCKER', 0) * 4
        critical_hours = severity_stats.get('CRITICAL', 0) * 2
        major_hours = severity_stats.get('MAJOR', 0) * 1
        minor_hours = severity_stats.get('MINOR', 0) * 0.5
        
        total_hours = blocker_hours + critical_hours + major_hours + minor_hours
        return int(max(8, total_hours))  # 最少8小时
    
    def _add_priority_matrix_section(self, md_content: list, analysis_data: dict):
        """添加修复优先级矩阵部分"""
        md_content.append("## 🎯 修复优先级矩阵")
        md_content.append("")
        
        issues = analysis_data['issues']['raw_data']
        
        # 按优先级分类问题
        priority_groups = {
            'P0': [],  # 安全漏洞和阻塞性问题
            'P1': [],  # 严重功能问题
            'P2': [],  # 重要质量问题
            'P3': []   # 一般改进项
        }
        
        for issue in issues:
            if isinstance(issue, dict):
                severity = issue.get('severity', '')
                issue_type = issue.get('type', '')
                
                if issue_type == 'VULNERABILITY' or severity == 'BLOCKER':
                    priority_groups['P0'].append(issue)
                elif severity == 'CRITICAL' or (issue_type == 'BUG' and severity == 'MAJOR'):
                    priority_groups['P1'].append(issue)
                elif severity == 'MAJOR':
                    priority_groups['P2'].append(issue)
                else:
                    priority_groups['P3'].append(issue)
        
        md_content.append("| 优先级 | 问题类型 | 数量 | 业务影响 | 建议完成时间 |")
        md_content.append("|--------|----------|------|----------|-------------|")
        
        if len(priority_groups['P0']) > 0:
            md_content.append(f"| 🚨 **P0** | 安全漏洞/阻塞问题 | **{len(priority_groups['P0'])}** | 数据泄露/系统崩溃 | **立即修复** (1-2天) |")
            
        if len(priority_groups['P1']) > 0:
            md_content.append(f"| 🔴 **P1** | 严重功能缺陷 | **{len(priority_groups['P1'])}** | 影响核心业务流程 | **本周内** (3-5天) |")
            
        if len(priority_groups['P2']) > 0:
            md_content.append(f"| 🟡 **P2** | 重要质量问题 | **{len(priority_groups['P2'])}** | 影响用户体验 | **2周内** |")
            
        if len(priority_groups['P3']) > 0:
            md_content.append(f"| 🟢 **P3** | 代码质量改进 | **{len(priority_groups['P3'])}** | 长期维护性 | **1个月内** |")
        
        md_content.append("")
        
        # 添加具体的P0问题列表（如果有）
        if len(priority_groups['P0']) > 0:
            md_content.append("### 🚨 P0级问题详情 (需立即处理)")
            md_content.append("")
            
            for i, issue in enumerate(priority_groups['P0'][:10], 1):  # 只显示前10个
                component = issue.get('component', '').split(':')[-1]
                line = issue.get('line', 'N/A')
                message = issue.get('message', '无描述')[:80] + ('...' if len(issue.get('message', '')) > 80 else '')
                
                md_content.append(f"**{i}.** `{component}:{line}` - {message}")
            
            if len(priority_groups['P0']) > 10:
                md_content.append(f"... 还有 {len(priority_groups['P0']) - 10} 个P0问题，详见完整报告")
            
            md_content.append("")
        
        # 添加代码修复示例（为高优先级问题）
        self._add_code_fix_examples(md_content, priority_groups)
    
    def _add_code_fix_examples(self, md_content: list, priority_groups: dict):
        """添加代码修复示例"""
        critical_issues = priority_groups['P0'] + priority_groups['P1']
        
        if len(critical_issues) > 0:
            md_content.append("### 🔧 关键问题修复示例")
            md_content.append("")
            
            examples_shown = 0
            for issue in critical_issues[:5]:  # 只显示前5个示例
                rule = issue.get('rule', '')
                message = issue.get('message', '')
                component = issue.get('component', '').split(':')[-1]
                line = issue.get('line', 'N/A')
                
                # 生成修复示例
                fix_example = self._generate_fix_example(rule, message)
                if fix_example:
                    examples_shown += 1
                    md_content.append(f"#### 示例 {examples_shown}: {component}:{line}")
                    md_content.append(f"**问题**: {message}")
                    md_content.append("")
                    md_content.append(fix_example)
                    md_content.append("")
                    
                if examples_shown >= 3:  # 最多显示3个示例
                    break
            
            if examples_shown == 0:
                md_content.append("具体修复建议请参考SonarQube规则文档。")
                md_content.append("")
    
    def _generate_fix_example(self, rule: str, message: str) -> str:
        """生成具体的修复示例"""
        # 常见的修复示例模板
        fix_templates = {
            'java:S1172': {
                'description': '移除未使用的方法参数',
                'before': '''```java
// ❌ 当前代码 (存在未使用参数)
public void processData(String data, int unusedParam) {
    System.out.println(data);
}
```''',
                'after': '''```java
// ✅ 修复后代码 (移除未使用参数)
public void processData(String data) {
    System.out.println(data);
}
```'''
            },
            'java:S2095': {
                'description': '确保资源正确关闭',
                'before': '''```java
// ❌ 当前代码 (资源未关闭)
FileInputStream fis = new FileInputStream("file.txt");
// ... 使用资源但未关闭
```''',
                'after': '''```java
// ✅ 修复后代码 (使用try-with-resources)
try (FileInputStream fis = new FileInputStream("file.txt")) {
    // ... 使用资源，自动关闭
}
```'''
            },
            'java:S1118': {
                'description': '工具类应该有私有构造函数',
                'before': '''```java
// ❌ 当前代码 (公共构造函数)
public class Utils {
    public static String format(String text) {
        return text.trim();
    }
}
```''',
                'after': '''```java
// ✅ 修复后代码 (私有构造函数)
public class Utils {
    private Utils() {
        // 防止实例化
    }
    
    public static String format(String text) {
        return text.trim();
    }
}
```'''
            }
        }
        
        if rule in fix_templates:
            template = fix_templates[rule]
            return f"**解决方案**: {template['description']}\n\n{template['before']}\n\n{template['after']}"
        
        # 对于没有特定模板的规则，返回通用建议
        if 'unused' in message.lower():
            return "**解决方案**: 移除未使用的代码元素以提高代码清洁度。"
        elif 'null' in message.lower():
            return "**解决方案**: 添加空值检查或使用Optional来避免NullPointerException。"
        elif 'security' in message.lower() or 'vulnerability' in message.lower():
            return "**解决方案**: 请立即审查此安全问题，考虑使用安全的API或添加适当的验证。"
        
        return None
        
    def _analyze_issue_patterns_for_ai(self, issues: list) -> str:
        """为AI分析生成问题模式信息"""
        if not issues:
            return "无问题数据"
            
        # 统计规则分布
        rule_count = {}
        component_count = {}
        
        for issue in issues:
            if isinstance(issue, dict):
                rule = issue.get('rule', 'unknown')
                component = issue.get('component', '').split(':')[-1]
                
                rule_count[rule] = rule_count.get(rule, 0) + 1
                if component:
                    component_count[component] = component_count.get(component, 0) + 1
        
        # 找出高频问题
        top_rules = sorted(rule_count.items(), key=lambda x: x[1], reverse=True)[:3]
        top_files = sorted(component_count.items(), key=lambda x: x[1], reverse=True)[:3]
        
        patterns = []
        if top_rules:
            patterns.append("**高频规则**: " + ", ".join([f"{rule}({count}次)" for rule, count in top_rules]))
        if top_files:
            patterns.append("**问题集中**: " + ", ".join([f"{file}({count}问题)" for file, count in top_files]))
        
        return "\n".join(patterns) if patterns else "问题分布较为均匀"
        
    def _calculate_quality_score_for_ai(self, measures: dict, severity_stats: dict) -> int:
        """为AI分析计算综合质量评分 (0-100)"""
        score = 100
        
        # 覆盖率影响 (最多扣30分)
        coverage = measures.get('coverage', 0)
        if coverage < 50:
            score -= 30
        elif coverage < 70:
            score -= 15
        elif coverage < 80:
            score -= 5
        
        # 重复代码影响 (最多扣15分)
        duplicated = measures.get('duplicated_lines_density', 0)
        if duplicated > 10:
            score -= 15
        elif duplicated > 5:
            score -= 10
        elif duplicated > 3:
            score -= 5
        
        # 严重问题影响 (最多扣40分)
        blocker = len(severity_stats.get('BLOCKER', []))
        critical = len(severity_stats.get('CRITICAL', []))
        major = len(severity_stats.get('MAJOR', []))
        
        score -= min(40, blocker * 10 + critical * 5 + major * 2)
        
        # 技术债务影响 (最多扣15分)
        debt_ratio = measures.get('sqale_debt_ratio', 0)
        if debt_ratio > 20:
            score -= 15
        elif debt_ratio > 10:
            score -= 10
        elif debt_ratio > 5:
            score -= 5
        
        return max(0, score)
    
    def _manual_sampling(self, issues: list, max_count: int) -> list:
        """手动采样处理大量问题（兼容旧版本客户端）"""
        if len(issues) <= max_count:
            return issues
            
        self.logger.warning(f"⚠️ 问题数量过多({len(issues)} > {max_count})，启用手动采样")
        
        # 按严重程度分组
        severity_groups = {
            'BLOCKER': [],
            'CRITICAL': [],
            'MAJOR': [],
            'MINOR': [],
            'INFO': []
        }
        
        for issue in issues:
            if isinstance(issue, dict):
                severity = issue.get('severity', 'INFO')
                if severity in severity_groups:
                    severity_groups[severity].append(issue)
        
        # 采样策略
        sampled = []
        
        # 1. 所有BLOCKER和CRITICAL问题
        sampled.extend(severity_groups['BLOCKER'])
        sampled.extend(severity_groups['CRITICAL'])
        self.logger.info(f"🔴 保留所有高优先级问题: {len(sampled)}个")
        
        remaining_budget = max_count - len(sampled)
        if remaining_budget <= 0:
            return sampled[:max_count]
        
        # 2. 30%的MAJOR问题
        major_count = min(len(severity_groups['MAJOR']), max(int(len(severity_groups['MAJOR']) * 0.3), 50))
        major_count = min(major_count, remaining_budget)
        if major_count > 0:
            step = max(1, len(severity_groups['MAJOR']) // major_count)
            major_sampled = severity_groups['MAJOR'][::step][:major_count]
            sampled.extend(major_sampled)
            self.logger.info(f"🟡 MAJOR问题采样: {len(major_sampled)}/{len(severity_groups['MAJOR'])}个")
        
        remaining_budget = max_count - len(sampled)
        if remaining_budget <= 0:
            return sampled
        
        # 3. 10%的MINOR问题
        minor_issues = severity_groups['MINOR'] + severity_groups['INFO']
        minor_count = min(len(minor_issues), max(int(len(minor_issues) * 0.1), remaining_budget))
        if minor_count > 0:
            step = max(1, len(minor_issues) // minor_count)
            minor_sampled = minor_issues[::step][:minor_count]
            sampled.extend(minor_sampled)
            self.logger.info(f"🟢 MINOR/INFO问题采样: {len(minor_sampled)}/{len(minor_issues)}个")
        
        self.logger.info(f"✅ 手动采样完成: {len(sampled)}/{len(issues)} 个问题")
        return sampled[:max_count]
    
    def _add_issue_details_section(self, md_content: list, analysis_data: dict):
        """添加问题详情部分"""
        md_content.append("## 📋 问题详情")
        md_content.append("")
        
        issues = analysis_data['issues']['raw_data']
        if not issues:
            md_content.append("✅ 未发现代码质量问题。")
            md_content.append("")
            return
        
        # 按严重程度排序，获取前20个不同类型的问题
        severity_order = ['BLOCKER', 'CRITICAL', 'MAJOR', 'MINOR', 'INFO']
        type_order = ['BUG', 'VULNERABILITY', 'CODE_SMELL']
        
        # 分类收集问题
        categorized_issues = {}
        for severity in severity_order:
            categorized_issues[severity] = {}
            for issue_type in type_order:
                categorized_issues[severity][issue_type] = []
        
        # 分类所有问题
        for issue in issues:
            if isinstance(issue, dict):
                severity = issue.get('severity', 'UNKNOWN')
                issue_type = issue.get('type', 'UNKNOWN')
                if severity in categorized_issues and issue_type in categorized_issues[severity]:
                    categorized_issues[severity][issue_type].append(issue)
        
        # 选择前20个最重要的问题
        selected_issues = []
        for severity in severity_order:
            for issue_type in type_order:
                issues_of_type = categorized_issues[severity][issue_type]
                if issues_of_type and len(selected_issues) < 20:
                    # 每种类型最多取4个
                    for issue in issues_of_type[:4]:
                        if len(selected_issues) < 20:
                            selected_issues.append(issue)
        
        if not selected_issues:
            md_content.append("✅ 未发现需要重点关注的问题。")
            md_content.append("")
            return
        
        md_content.append(f"以下是 **{len(selected_issues)}** 个需要重点关注的问题：")
        md_content.append("")
        
        for i, issue in enumerate(selected_issues, 1):
            severity = issue.get('severity', 'UNKNOWN')
            issue_type = issue.get('type', 'UNKNOWN')
            message = issue.get('message', '无描述')
            component = issue.get('component', '').split(':')[-1]  # 只取文件名部分
            line = issue.get('line', 'N/A')
            rule = issue.get('rule', 'unknown')
            
            # 问题标题
            severity_emoji = {
                'BLOCKER': '🚫', 'CRITICAL': '🔴', 'MAJOR': '🟠', 
                'MINOR': '🟡', 'INFO': '🔵'
            }.get(severity, '❓')
            
            type_emoji = {
                'BUG': '🐛', 'VULNERABILITY': '🔓', 'CODE_SMELL': '💨'
            }.get(issue_type, '❓')
            
            md_content.append(f"### {i}. {severity_emoji} {type_emoji} {severity} - {issue_type}")
            md_content.append("")
            
            # 英文描述和中文翻译
            md_content.append(f"**问题描述**: {message}")
            chinese_description = self._get_chinese_description(message, rule)
            if chinese_description and chinese_description != message:
                md_content.append(f"**中文说明**: {chinese_description}")
            md_content.append("")
            
            md_content.append(f"**位置**: `{component}:{line}`")
            md_content.append("")
            
            # 规则和规则解释
            rule_explanation = self._get_rule_explanation(rule)
            md_content.append(f"**规则**: `{rule}`")
            if rule_explanation:
                md_content.append(f"**规则说明**: {rule_explanation}")
            md_content.append("")
            
            # 添加修复建议
            fix_suggestion = self._get_fix_suggestion(issue_type, severity, rule)
            if fix_suggestion:
                md_content.append(f"**修复建议**: {fix_suggestion}")
                md_content.append("")
            
            md_content.append("---")
            md_content.append("")
        
        md_content.append("")
    
    def _get_fix_suggestion(self, issue_type: str, severity: str, rule: str) -> str:
        """获取问题修复建议"""        
        # 特殊规则的具体修复建议
        rule_suggestions = {
            'java:S1172': """**修复方法**: 移除未使用的参数
```java
// ❌ 修复前
public void process(String data, int unusedParam) { }

// ✅ 修复后  
public void process(String data) { }
```""",
            
            'java:S1481': """**修复方法**: 移除未使用的变量
```java
// ❌ 修复前
public void method() {
    String unused = "test";
    doSomething();
}

// ✅ 修复后
public void method() {
    doSomething();
}
```""",
            
            'java:S1118': """**修复方法**: 添加私有构造函数
```java
// ❌ 修复前
public class Utils {
    public static void helper() { }
}

// ✅ 修复后
public class Utils {
    private Utils() { }
    public static void helper() { }
}
```""",
            
            'java:S2095': """**修复方法**: 使用try-with-resources
```java
// ❌ 修复前
FileInputStream fis = new FileInputStream(file);
// ... 使用fis
fis.close();

// ✅ 修复后
try (FileInputStream fis = new FileInputStream(file)) {
    // ... 使用fis
}
```""",
            
            'java:S1144': """**修复方法**: 移除未使用的私有方法
```java
// ❌ 修复前
private void unusedMethod() { }

// ✅ 修复后
// 直接删除该方法
```""",
            
            'squid:S00108': """**修复方法**: 移除空代码块或添加注释
```java
// ❌ 修复前
if (condition) {
    // 空代码块
}

// ✅ 修复后
if (condition) {
    // TODO: 实现具体逻辑
}
```""",
        }
        
        # 优先返回规则特定建议
        if rule in rule_suggestions:
            return rule_suggestions[rule]
        
        # 通用建议
        general_suggestions = {
            'BUG': {
                'BLOCKER': '🚨 **立即修复**: 系统阻塞性错误，必须在发布前解决',
                'CRITICAL': '🔴 **1-2天内修复**: 严重逻辑错误，影响核心功能',
                'MAJOR': '🟠 **1周内修复**: 重要功能问题，需要及时处理'
            },
            'VULNERABILITY': {
                'BLOCKER': '🚨 **立即修复**: 严重安全漏洞，存在被攻击风险',
                'CRITICAL': '🔴 **紧急修复**: 高安全风险，需要立即评估和修复',
                'MAJOR': '🟠 **及时修复**: 潜在安全风险，应尽快处理'
            },
            'CODE_SMELL': {
                'MAJOR': '💨 **重构优化**: 代码结构问题，影响维护性',
                'MINOR': '🔧 **适时优化**: 代码质量可以改善',
                'INFO': '💡 **参考建议**: 最佳实践建议，可逐步改进'
            }
        }
        
        # 返回类型和严重程度相关建议
        if issue_type in general_suggestions and severity in general_suggestions[issue_type]:
            return general_suggestions[issue_type][severity]
        
        # 默认建议
        return f"建议查看SonarQube规则详情，了解具体修复方法"
    
    def _get_chinese_description(self, english_message: str, rule: str = None) -> str:
        """获取问题的中文描述"""
        # 常见问题的中文翻译
        chinese_translations = {
            # Java常见问题
            "Remove this unused method parameter": "移除这个未使用的方法参数",
            "Remove this unused local variable": "移除这个未使用的局部变量", 
            "Add a private constructor to hide the implicit public one": "添加私有构造函数来隐藏隐式的公共构造函数",
            "Use try-with-resources or close this": "使用try-with-resources或者关闭这个资源",
            "Remove this unused private method": "移除这个未使用的私有方法",
            "Either remove or fill this block of code": "移除或填充这个代码块",
            "Make this field final": "将这个字段设为final",
            "Replace this lambda with a method reference": "用方法引用替换这个lambda表达式",
            "Cognitive Complexity": "认知复杂度过高，建议简化代码逻辑",
            "Cyclomatic Complexity": "圈复杂度过高，建议拆分方法",
            
            # 通用问题类型
            "unused": "存在未使用的代码元素",
            "complexity": "代码复杂度过高", 
            "duplicate": "存在重复代码",
            "security": "存在安全风险",
            "resource": "资源管理问题",
            "null": "可能的空指针问题",
        }
        
        # 精确匹配
        if english_message in chinese_translations:
            return chinese_translations[english_message]
        
        # 模糊匹配
        message_lower = english_message.lower()
        for keyword, translation in chinese_translations.items():
            if keyword.lower() in message_lower:
                return translation
                
        return ""  # 没有找到翻译
    
    def _get_rule_explanation(self, rule: str) -> str:
        """获取规则解释"""
        rule_explanations = {
            'java:S1172': '检测方法中未使用的参数，这些参数会增加代码复杂度',
            'java:S1481': '检测未使用的局部变量，应该移除以保持代码清洁',
            'java:S1118': '工具类应该有私有构造函数，防止被实例化',
            'java:S2095': '检测资源是否正确关闭，防止内存泄漏',
            'java:S1144': '检测未使用的私有方法，应该移除以减少代码冗余',
            'java:S00108': '检测空的代码块，应该移除或添加说明注释',
            'java:S1213': '常量定义位置建议，提高代码组织性',
            'java:S3776': '方法认知复杂度过高，建议拆分方法',
            'java:S1541': '方法圈复杂度过高，建议简化逻辑',
            'java:S1192': '检测重复的字符串字面量，建议定义为常量',
        }
        
        return rule_explanations.get(rule, "")
    
    def _add_practical_recommendations(self, md_content: list, analysis_data: dict):
        """添加务实的修复建议部分"""
        md_content.append("## 🎯 务实修复建议")
        md_content.append("")
        
        issues = analysis_data['issues']['raw_data']
        if not issues:
            md_content.append("✅ 项目代码质量良好，无需特别关注的问题。")
            md_content.append("")
            return
        
        # 分析问题分布
        file_problems = {}  # 文件 -> 问题列表
        severity_stats = {'BLOCKER': 0, 'CRITICAL': 0, 'MAJOR': 0, 'MINOR': 0, 'INFO': 0}
        
        for issue in issues:
            if isinstance(issue, dict):
                component = issue.get('component', '')
                severity = issue.get('severity', 'UNKNOWN')
                
                # 提取文件名
                if ':' in component:
                    filename = component.split(':')[-1]
                else:
                    filename = component
                
                if filename not in file_problems:
                    file_problems[filename] = []
                file_problems[filename].append(issue)
                
                if severity in severity_stats:
                    severity_stats[severity] += 1
        
        # 1. 最急需修复的文件
        md_content.append("### 🚨 最急需修复的文件 (Top 5)")
        md_content.append("")
        
        # 按问题数量和严重程度排序文件
        file_scores = {}
        for filename, file_issues in file_problems.items():
            score = 0
            critical_count = 0
            major_count = 0
            
            for issue in file_issues:
                severity = issue.get('severity', '')
                if severity == 'BLOCKER':
                    score += 10
                    critical_count += 1
                elif severity == 'CRITICAL':
                    score += 8
                    critical_count += 1
                elif severity == 'MAJOR':
                    score += 5
                    major_count += 1
                elif severity == 'MINOR':
                    score += 2
                else:
                    score += 1
            
            file_scores[filename] = {
                'score': score,
                'total': len(file_issues),
                'critical': critical_count,
                'major': major_count
            }
        
        # 排序并显示前5个
        top_files = sorted(file_scores.items(), key=lambda x: x[1]['score'], reverse=True)[:5]
        
        for i, (filename, stats) in enumerate(top_files, 1):
            critical_major = stats['critical'] + stats['major']
            md_content.append(f"**{i}. `{filename}`**")
            md_content.append(f"- 🔥 **{stats['total']}个问题** ({stats['critical']}个严重 + {stats['major']}个重要)")
            md_content.append(f"- 💡 **建议**: {'立即修复' if stats['critical'] > 0 else '本周内处理'}")
            md_content.append("")
        
        # 2. 按问题类型的具体建议
        md_content.append("### 🛠️ 分类修复策略")
        md_content.append("")
        
        issue_stats = analysis_data['summary']['issue_stats']
        
        # BUG修复建议
        bug_count = issue_stats['by_type'].get('BUG', 0)
        if bug_count > 0:
            md_content.append(f"#### 🐛 BUG修复 ({bug_count}个)")
            md_content.append("**立即行动**:")
            md_content.append("- 🚨 先修复所有BLOCKER和CRITICAL级别的BUG")
            md_content.append("- 📋 为每个BUG创建测试用例，确保修复后不再出现")
            md_content.append("- 🔍 重点检查空指针异常、数组越界、资源泄露等常见问题")
            md_content.append("")
        
        # 漏洞修复建议
        vuln_count = issue_stats['by_type'].get('VULNERABILITY', 0)
        if vuln_count > 0:
            md_content.append(f"#### 🔓 安全漏洞修复 ({vuln_count}个)")
            md_content.append("**安全优先**:")
            md_content.append("- 🛡️ 立即修复所有安全漏洞，这是最高优先级")
            md_content.append("- 🔐 重点关注：SQL注入、XSS攻击、敏感信息泄露")
            md_content.append("- 📝 建立安全代码审查检查清单")
            md_content.append("")
        
        # 代码异味修复建议
        smell_count = issue_stats['by_type'].get('CODE_SMELL', 0)
        if smell_count > 0:
            md_content.append(f"#### 💨 代码异味整治 ({smell_count}个)")
            md_content.append("**分批处理**:")
            md_content.append("- 🎯 每周处理20-30个CODE_SMELL，持续改进")
            md_content.append("- 🔄 重点关注：重复代码、复杂度过高、命名不规范")
            md_content.append("- 📊 设置质量门：新代码不能引入新的CODE_SMELL")
            md_content.append("")
        
        # 3. 本周行动计划
        md_content.append("### 📅 本周行动计划")
        md_content.append("")
        
        total_critical = severity_stats['BLOCKER'] + severity_stats['CRITICAL']
        if total_critical > 0:
            md_content.append(f"#### 第一优先级 - 紧急修复 ({total_critical}个)")
            md_content.append(f"- 📍 **目标**: 本周内清零所有BLOCKER和CRITICAL问题")
            if total_critical <= 10:
                md_content.append(f"- ⏰ **时间安排**: 每天处理2-3个，预计3-4天完成")
            else:
                md_content.append(f"- ⏰ **时间安排**: 每天处理5-8个，预计本周完成大部分")
            md_content.append(f"- 👥 **建议**: 分配给最有经验的开发人员处理")
            md_content.append("")
        
        major_count = severity_stats['MAJOR']
        if major_count > 0:
            md_content.append(f"#### 第二优先级 - 重要修复 ({major_count}个)")
            md_content.append(f"- 📍 **目标**: 2周内处理完所有MAJOR问题")
            md_content.append(f"- ⏰ **时间安排**: 每天处理3-5个")
            md_content.append(f"- 🎯 **重点**: 影响功能和性能的问题")
            md_content.append("")
        
        # 4. 质量改进建议
        md_content.append("### 🚀 质量改进措施")
        md_content.append("")
        
        measures = analysis_data.get('measures', {})
        coverage = measures.get('coverage', 0)
        
        md_content.append("#### 立即实施的改进措施:")
        md_content.append("")
        
        if coverage < 50:
            md_content.append("1. **📊 测试覆盖率提升**")
            md_content.append(f"   - 当前覆盖率: {coverage}%，目标: 70%+")
            md_content.append("   - 优先为核心业务逻辑编写单元测试")
            md_content.append("   - 使用JUnit + Mockito搭建测试框架")
            md_content.append("")
        
        md_content.append("2. **🔧 代码审查流程**")
        md_content.append("   - 每个PR必须经过SonarQube扫描")
        md_content.append("   - 不允许新增CRITICAL以上问题")
        md_content.append("   - 建立代码质量检查清单")
        md_content.append("")
        
        md_content.append("3. **📈 持续改进**")
        md_content.append("   - 设定每周修复问题数量目标")
        md_content.append("   - 定期（每月）进行代码质量评审")
        md_content.append("   - 建立技术债务管理机制")
        md_content.append("")
        
        # 5. 投入产出估算
        total_issues = len(issues)
        estimated_hours = self._estimate_fix_time(severity_stats, total_issues)
        
        md_content.append("### 💰 投入产出估算")
        md_content.append("")
        md_content.append(f"**预估修复工作量**: `{estimated_hours}`小时")
        md_content.append(f"**建议团队配置**: {self._recommend_team_size(total_issues)}人")
        md_content.append(f"**预期完成时间**: {self._estimate_completion_time(total_issues)}周")
        md_content.append("")
        md_content.append("**收益预期**:")
        md_content.append("- 🚀 系统稳定性提升60%+")
        md_content.append("- 🛡️ 安全风险降低80%+") 
        md_content.append("- 🔧 后期维护成本降低40%+")
        md_content.append("- 👨‍💻 新人上手时间缩短50%+")
        md_content.append("")
    
    def _estimate_fix_time(self, severity_stats: dict, total_issues: int) -> str:
        """估算修复时间"""
        hours = 0
        hours += severity_stats.get('BLOCKER', 0) * 4  # 每个BLOCKER 4小时
        hours += severity_stats.get('CRITICAL', 0) * 3  # 每个CRITICAL 3小时
        hours += severity_stats.get('MAJOR', 0) * 2  # 每个MAJOR 2小时
        hours += severity_stats.get('MINOR', 0) * 1  # 每个MINOR 1小时
        hours += severity_stats.get('INFO', 0) * 0.5  # 每个INFO 0.5小时
        
        return f"{int(hours)}-{int(hours * 1.5)}"
    
    def _recommend_team_size(self, total_issues: int) -> str:
        """推荐团队规模"""
        if total_issues < 50:
            return "1-2"
        elif total_issues < 200:
            return "2-3"
        elif total_issues < 500:
            return "3-4"
        else:
            return "4-5"
    
    def _estimate_completion_time(self, total_issues: int) -> str:
        """估算完成时间"""
        if total_issues < 50:
            return "2-3"
        elif total_issues < 200:
            return "4-6"
        elif total_issues < 500:
            return "6-10"
        else:
            return "10-16"
    
    def _get_rating_emoji(self, rating: str) -> str:
        """获取评级对应的emoji"""
        rating_emojis = {
            'A': '🟢',
            'B': '🟡', 
            'C': '🟠',
            'D': '🔴',
            'E': '🔴'
        }
        return rating_emojis.get(str(rating).upper(), '❓')
    
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
    <title>SonarQube项目缺陷分析报告</title>
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
            padding: 15px 20px;
            border-radius: 5px;
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
        
        .risk-critical {{ background-color: #ffeaa7; }}
        .risk-high {{ background-color: #fab1a0; }}
        .risk-medium {{ background-color: #e17055; }}
        .risk-low {{ background-color: #00b894; }}
        .risk-minimal {{ background-color: #ddd; }}
        
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
        """发送HTML格式的邮件报告"""
        try:
            if not subject:
                date_str = datetime.now().strftime('%Y-%m-%d')
                subject = f"SonarQube项目缺陷分析报告 - {project_name or self.project_key} ({date_str})"
            
            self.logger.info(f"📧 邮件主题: {subject}")
            
            # 如果有markdown内容，则发送HTML邮件并附上markdown文件
            if markdown_content:
                # 生成附件文件名
                date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                project_name_safe = (project_name or self.project_key).replace('/', '_').replace(' ', '_')
                attachment_filename = f"SonarQube缺陷分析报告_{project_name_safe}_{date_str}.md"
                
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

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SonarQube项目缺陷分析器")
    parser.add_argument('--project-key', required=True, help='SonarQube项目标识符')
    parser.add_argument('--severities', nargs='+', 
                       choices=['INFO', 'MINOR', 'MAJOR', 'CRITICAL', 'BLOCKER'],
                       default=['CRITICAL', 'BLOCKER', 'MAJOR'],
                       help='严重程度过滤')
    parser.add_argument('--issue-types', nargs='+',
                       choices=['CODE_SMELL', 'BUG', 'VULNERABILITY'],
                       default=['BUG', 'VULNERABILITY', 'CODE_SMELL'],
                       help='问题类型过滤')
    parser.add_argument('--use-ai', action='store_true', help='启用AI分析')
    parser.add_argument('--ai-model', help='指定AI分析使用的模型名称')
    parser.add_argument('--output-format', choices=['json', 'markdown', 'html'], 
                       default='html', help='输出格式')
    parser.add_argument('--output-file', help='输出文件路径')
    parser.add_argument('--send-email', action='store_true', help='发送邮件报告')
    parser.add_argument('--email-recipients', nargs='+', help='邮件收件人列表')
    parser.add_argument('--email-subject', help='邮件主题')
    
    # SonarQube配置选项
    parser.add_argument('--sonarqube-url', help='SonarQube实例URL')
    parser.add_argument('--sonarqube-token', help='SonarQube访问令牌')
    parser.add_argument('--sonarqube-timeout', type=int, help='SonarQube API超时时间')
    parser.add_argument('--sonarqube-verify-ssl', type=bool, help='是否验证SSL证书')
    
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    try:
        # 创建SonarQube配置
        sonarqube_config = None
        if any([args.sonarqube_url, args.sonarqube_token, args.sonarqube_timeout, 
                args.sonarqube_verify_ssl is not None]):
            from shared.sonarqube_client import get_default_sonarqube_config
            
            # 获取默认配置
            default_config = get_default_sonarqube_config()
            
            # 使用命令行参数覆盖默认配置
            sonarqube_config = SonarQubeConfig(
                url=args.sonarqube_url or default_config.url,
                token=args.sonarqube_token or default_config.token,
                timeout=args.sonarqube_timeout or default_config.timeout,
                verify_ssl=args.sonarqube_verify_ssl if args.sonarqube_verify_ssl is not None else default_config.verify_ssl
            )
        
        # 创建SonarQube客户端
        sonarqube_client = SonarQubeClient(sonarqube_config) if sonarqube_config else None
        
        # 创建分析器
        analyzer = SonarQubeDefectAnalyzer(
            args.project_key, 
            sonarqube_client=sonarqube_client,
            ai_model=args.ai_model
        )
        
        # 执行分析
        logger.info("开始分析SonarQube项目缺陷...")
        analysis_data = analyzer.analyze_project_defects(
            severities=args.severities,
            issue_types=args.issue_types,
            use_ai=args.use_ai
        )
        
        # 输出结果
        logger.info(f"开始生成 {args.output_format} 格式的报告...")
        markdown_content = None
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
                result = analyzer.send_report_email(
                    html_content=output_content,
                    recipients=args.email_recipients,
                    subject=args.email_subject,
                    project_name=analysis_data['project_info']['name'],
                    markdown_content=markdown_content
                )
                
                if result['success']:
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
        print(f"   项目标识: {args.project_key}")
        print(f"   总问题数: {summary['issue_stats']['total']}")
        print(f"   安全热点: {summary['hotspot_stats']['total']}")
        print(f"   风险等级: {summary['risk_level']}")
        print(f"   质量门状态: {summary['quality_gate_status']}")
        
        if not args.output_file and not args.send_email:
            print("\n" + output_content)
        
    except Exception as e:
        import traceback
        logger.error(f"分析失败: {e}")
        logger.error(f"完整堆栈信息:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()