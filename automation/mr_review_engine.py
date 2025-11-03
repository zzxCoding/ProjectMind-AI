#!/usr/bin/env python3
"""
GitLab MR 自动审查引擎
整合 SonarQube 静态分析和 Ollama AI 智能审查
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.gitlab_client import GitLabClient, get_default_config
from shared.ollama_client import OllamaClient
from config.ollama_config import get_default_ollama_config
from shared.utils import setup_logging
from shared.thread_pool_manager import ThreadPoolManager

class ReviewSeverity(Enum):
    """审查结果严重程度"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ReviewStatus(Enum):
    """审查状态"""
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"

@dataclass
class ReviewIssue:
    """审查问题"""
    severity: ReviewSeverity
    category: str
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    suggestion: Optional[str] = None
    source: str = "unknown"  # sonarqube, ai_review, etc.

@dataclass
class ReviewResult:
    """审查结果"""
    mr_id: int
    mr_title: str
    mr_author: str
    review_time: datetime
    status: ReviewStatus
    issues: List[ReviewIssue]
    summary: Dict[str, Any]
    metadata: Dict[str, Any]

class MRReviewEngine:
    """MR 自动审查引擎"""
    
    def __init__(self, 
                 gitlab_client: Optional[GitLabClient] = None,
                 ollama_client: Optional[OllamaClient] = None,
                 log_level: str = 'INFO',
                 ai_temperature: Optional[float] = None):
        """
        初始化审查引擎
        
        Args:
            gitlab_client: GitLab客户端
            ollama_client: Ollama客户端
            log_level: 日志级别
            ai_temperature: AI温度参数
        """
        # 存储当前审查的分析详情
        self.current_analysis_details = None
        self.gitlab_client = gitlab_client or GitLabClient()
        self.ollama_client = ollama_client or OllamaClient()
        self.logger = setup_logging(level=log_level)
        self.ai_temperature = ai_temperature
        
        # 根据日志级别设置Ollama debug模式
        if hasattr(self.ollama_client, 'debug_mode'):
            self.ollama_client.debug_mode = (log_level.upper() == 'DEBUG')
            if self.ollama_client.debug_mode:
                self.logger.info("已启用Ollama debug模式")
        
        # 审查配置
        self.config = {
            'max_files_per_analysis': 100,  # 最多分析的文件数量
            'max_file_size_kb': 5000,       # 最大文件大小5MB - 让AI处理大文件
            'max_issues_per_file': 10,      # 每个文件最大问题数
            'severity_threshold': ReviewSeverity.WARNING,  # 阻止合并的阈值
            'enable_ai_review': True,       # 启用AI审查
            'ai_model': 'codellama',        # AI模型
            'skip_file_patterns': ['.min.js', '.log', '.tmp', '.lock'],  # 跳过的文件模式
            'priority_file_extensions': [
                # 后端文件
                '.py', '.js', '.java', '.cpp', '.c', '.go', '.rs', '.php', '.rb',
                # 前端文件  
                '.vue', '.jsx', '.tsx', '.html', '.css', '.scss', '.sass', '.less',
                # 配置和SQL文件
                '.sql', '.xml', '.yaml', '.yml', '.json', '.toml'
            ]
        }

        # 首次AI提示词关键规则，用于复用与复核
        self.ai_issue_prompt_instructions = """
## Role
You are a highly-specialized Static Code Analysis Engine and expert Code Reviewer.

## Profile
- author: AI Prompt Engineering Expert
- version: 3.0
- language: Chinese
- description: You are designed to analyze code changes presented in GitLab diff format. Your primary function is to identify critical and high-priority issues while exhibiting a deep understanding of a specific enterprise technology stack. You excel at distinguishing genuine bugs from common false positives that arise from custom frameworks, multi-database environments, and enterprise-level application design patterns. You are precise, context-aware, and strictly adhere to the defined output format.

## Goals
1.  Analyze the provided GitLab code diff to identify potential software defects.
2.  Prioritize findings based on a strict severity hierarchy (Critical, High, Low).
3.  Filter out low-priority issues and a comprehensive list of known false positives related to specific frameworks and enterprise contexts.
4.  Report only valid, high-impact issues.
5.  Format the final report into a specific JSON structure with content in Chinese.

## Constraints

### General Rules
-   **Analyze Diff, Not Full File**: The input is a diff, not a complete file. Make reasonable judgments about incomplete code fragments based on programming knowledge.
-   **Ignore Compilation Errors**: Do not report compilation errors, as fragments may be valid within the full file context.
-   **Focus on Added Code**: Your analysis should primarily focus on the `[新增]` lines (added lines). `[删除]` (removed) and `[上下文]` (context) lines are for reference only.
-   **Do Not Report Duplicates from Context**: Do not report "duplicate code" based on context lines in the diff, as this is a common artifact of the diff format.

### Issue Prioritization
-   **CRITICAL PRIORITY (Must Report)**:
    -   **Memory Leaks**: Static collections that grow indefinitely, unclosed resources, connection leaks.
    -   **Security Vulnerabilities**: SQL injection, hardcoded credentials, authentication bypass, critical security flaws.
    -   **Critical Runtime Errors**: Null pointer exceptions, division by zero, infinite loops.
-   **HIGH PRIORITY (Should Report)**:
    -   **Resource Management**: File handles or database connections not properly closed (unless managed by a framework as specified below).
    -   **Performance Issues**: Inefficient algorithms, blocking I/O operations in critical paths.
    -   **Logic Errors**: Flaws in business logic that produce demonstrably incorrect results.
-   **LOW PRIORITY (Must Ignore)**:
    -   Code style, formatting, and comment suggestions.
    -   Variable naming conventions.
    -   Minor refactoring suggestions for code clarity or simplicity.

### File-Type Specific Rules
-   **SQL Files (.sql)**: Be extremely conservative. Only report definitive SQL syntax errors (e.g., missing semicolons, unclosed quotes). Do NOT make assumptions about ORM frameworks.
-   **XML SQL Mapper Files (MyBatis, etc.)**: These are valid configuration files. Do NOT report "content parsing errors" or "missing definitions." Only report obvious, malformed XML syntax (e.g., unclosed tags).
-   **Config Files (XML, YAML, JSON)**: Check for fundamental syntax validity but be lenient with framework-specific structures.

### Framework & Context Rules (False Positives - DO NOT Report)

#### 1. Custom Database & ORM Frameworks
-   **MyBatis/SQL Placeholders**: Constructs like `$S{{dealStatus}}` or `${{param}}` are VALID MyBatis syntax. DO NOT report them as SQL injection. Variations like `#{{param}}` or `:param` are also valid.
-   **Custom `Dbop` Framework**: Assume `Dbop.setDataSourceName()` calls are managed by the framework. DO NOT report thread safety issues or data source lifecycle mismanagement.
-   **Custom `SqlResult` Objects**: Assume `SqlResult` objects returned by `dbop.select()` are managed by the framework. DO NOT report resource leaks for unclosed `SqlResult` objects. The framework is responsible for cleanup.
-   **Framework-Managed Results**: Assume `dbop.select()` guarantees non-null results or has proper error handling. DO NOT report null pointer risks on its return values without clear evidence of a bug.
-   **Multiple DBType Definitions**: XML mappers may contain duplicate `sqlinfo` blocks with different `dbtype` attributes (e.g., `dbtype='all'` and `dbtype='db2'`). This is a valid multi-database support pattern.

#### 2. Enterprise Application Patterns
-   **Service Scope**: Spring services may be configured with `@Scope("prototype")`. In such cases, instance variables DO NOT pose a thread safety risk.
-   **Enterprise Context Indicators**: When package or class names contain `.batch.`, `.service.`, `Service`, `Manager`, `Batch`, or `Job`, apply more lenient review standards, as they operate within a managed framework.
-   **Request Object Access**: Assume direct access to request objects (e.g., `request.getKbatchTaskExec()`) is safe, as parameters are likely validated at a higher level (Controller/Interceptor).
-   **Batch Processing Methods**: Standard batch methods like `doJobSlice`, `doProcess`, `doCheckInput` are part of a larger framework. Assume the framework handles error handling, transactions, and retries.
-   **JSON Library Usage**: Assume established libraries like Fastjson are used correctly within the enterprise context and have passed security reviews. Do not report generic deserialization warnings without specific evidence of a vulnerability.

#### 3. Multi-Database SQL Compatibility
-   **Time Functions**: Variations like `current timestamp`, `CURRENT_TIMESTAMP`, `now()`, `SYSDATE`, `GETDATE()` are valid database-specific functions. Assume the framework handles compatibility.
-   **Oracle-DB2 Compatibility**: In DB2 environments with Oracle compatibility mode, Oracle functions like `to_char(sysdate, ...)` are valid. Reduce severity to a warning if unsure, but do not classify as an error.
-   **Function Syntax Variation**: Different spacing and capitalization in SQL functions are often intentional for multi-DB support.

### Specific Function Rules
-   **`dbop.update` Override**: When analyzing code calling `dbop.update()`, pay close attention to its implementation context. If it is known or can be inferred that the `dbop.update()` function itself handles connection release and transaction commits internally, then you MUST NOT report "datasource switching thread safety issues" or "unclosed SqlResult resource leaks" for the calling code.

## Input
-   A string containing a code diff in GitLab format, using `[新增]`, `[删除]`, and `[上下文]` markers.

## Output Instructions
-   **格式**: 必须直接返回一个合法的 JSON 对象，禁止使用 ``` 包裹。
-   **内容**: JSON 中所有字符串字段必须使用中文表述。
-   **唯一性**: 不得在 JSON 前后添加说明文字或额外内容。

### JSON Schema
{{
    "errors": [
        {{
            "type": "语法错误|逻辑错误|类型错误|运行时错误",
            "description": "错误描述",
            "line_number": 行号（如果能确定）, 
            "suggestion": "修复建议"
        }}
    ]
}}

### 示例
-   **存在问题时**: {{"errors": [{{"type": "逻辑错误", "description": "在循环内部创建数据库连接，可能导致性能问题和连接耗尽", "line_number": 42, "suggestion": "将数据库连接的创建和关闭移到循环外部。"}}]}}
-   **无问题时**: {{"errors": []}}

## Workflow
1.  Receive and parse the input GitLab diff string.
2.  Identify the file type to apply specific rules.
3.  Analyze the `[新增]` lines, using `[删除]` and `[上下文]` lines for full context.
4.  For each potential issue, classify its severity according to the `Issue Prioritization` rules.
5.  Systematically check each potential issue against the comprehensive list of `Framework & Context Rules (False Positives)`.
6.  Discard any issue that is classified as LOW PRIORITY or matches a false positive rule.
7.  For all remaining valid issues, gather the required information: type, description, line number, and a suggested fix.
8.  Construct the final JSON object according to the `Output Instructions`, ensuring all text is in Chinese.
9.  Return only the raw JSON object as the final response.
"""

        # 需要复核的AI问题来源
        self.ai_issue_verification_sources = {
            'ai_syntax_checker',
            'ai_review',
            'ai_review_text_parser'
        }

        self.last_issue_verification_details: Dict[str, Any] = {}
    
    @staticmethod
    def _create_skip_result(project_id: str, mr_iid: int, skip_reason: str) -> ReviewResult:
        """
        创建跳过审查的结果
        
        Args:
            project_id: 项目ID
            mr_iid: 合并请求IID
            skip_reason: 跳过原因
            
        Returns:
            审查结果
        """
        from datetime import datetime
        
        # 获取MR基本信息
        gitlab_client = GitLabClient()
        mr_details = gitlab_client.get_merge_request_details_smart(project_id, mr_iid, enable_smart_context=True)
        
        if mr_details:
            basic_info = mr_details['basic_info']
            mr_title = basic_info['title']
            mr_author = basic_info['author']['name']
        else:
            mr_title = f"MR {mr_iid}"
            mr_author = "Unknown"
        
        return ReviewResult(
            mr_id=mr_iid,
            mr_title=mr_title,
            mr_author=mr_author,
            review_time=datetime.now(),
            status=ReviewStatus.PASSED,  # 跳过审查视为通过
            issues=[],  # 没有问题
            summary={
                'total_issues': 0,
                'by_severity': {},
                'by_source': {},
                'files_affected': 0
            },
            metadata={
                'project_id': project_id,
                'files_changed': 0,
                'skip_reason': skip_reason,
                'skipped': True
            }
        )
    
    def review_merge_request(self, project_id: str, mr_iid: int) -> ReviewResult:
        """
        审查合并请求
        
        Args:
            project_id: 项目ID
            mr_iid: 合并请求IID
            
        Returns:
            审查结果
        """
        self.logger.info(f"开始审查合并请求: {project_id}!{mr_iid}")
        
        try:
            # 1. 获取MR详细信息（使用智能上下文）
            mr_details = self.gitlab_client.get_merge_request_details_smart(project_id, mr_iid, enable_smart_context=True)
            if not mr_details:
                raise ValueError(f"无法获取MR {mr_iid} 的详细信息")
            
            basic_info = mr_details['basic_info']
            changes = mr_details['changes']
            
            self.logger.info(f"MR标题: {basic_info['title']}")
            self.logger.info(f"变更文件数: {len(changes)}")
            
            # 2. 收集所有问题
            all_issues = []
            
            # 3. AI智能审查
            if self.config['enable_ai_review']:
                ai_issues = self._analyze_with_ai(changes, mr_details)
                self.logger.info(f"AI审查完成，初步发现 {len(ai_issues)} 个问题")

                verified_ai_issues = self._reanalyze_issues_with_original_prompt(ai_issues)
                all_issues.extend(verified_ai_issues)
                self.logger.info(f"AI复核后保留 {len(verified_ai_issues)} 个问题")
                
                # 4. AI汇总分析 - 只针对严重问题
                critical_or_error_issues = [issue for issue in all_issues 
                                          if issue.severity in [ReviewSeverity.CRITICAL, ReviewSeverity.ERROR]]
                if len(critical_or_error_issues) > 0:
                    summary_suggestions = self._analyze_summary_suggestions(all_issues, mr_details)
                    all_issues.extend(summary_suggestions)
                    self.logger.info(f"AI汇总分析完成，发现 {len(summary_suggestions)} 个建议")
                else:
                    self.logger.info("未发现严重问题，跳过AI汇总分析")
            
            # 5. 聚合和去重
            unique_issues = self._deduplicate_issues(all_issues)
            
            # 6. 确定审查状态
            review_status = self._determine_review_status(unique_issues)
            
            # 6. 生成摘要
            summary = self._generate_summary(unique_issues)
            
            # 7. 构建结果
            result = ReviewResult(
                mr_id=mr_iid,
                mr_title=basic_info['title'],
                mr_author=basic_info['author']['name'],
                review_time=datetime.now(),
                status=review_status,
                issues=unique_issues,
                summary=summary,
                metadata={
                    'project_id': project_id,
                    'files_changed': len(changes),
                    'ai_review_enabled': self.config['enable_ai_review'],
                    'review_config': self.config
                }
            )
            
            self.logger.info(f"审查完成: {review_status.value}, 发现 {len(unique_issues)} 个问题")
            return result
            
        except Exception as e:
            self.logger.error(f"审查失败: {e}")
            raise
    
      
    def _analyze_with_ai(self, changes: List[Dict[str, Any]], mr_details: Dict[str, Any]) -> List[ReviewIssue]:
        """使用AI进行智能审查 - 逐个文件完整分析"""
        issues = []
        
        try:
            self.logger.debug(f"开始AI分析，变更数量: {len(changes)}")
            
            # 筛选和排序文件
            filtered_changes = self._filter_and_prioritize_changes(changes)
            self.logger.debug(f"筛选后文件数量: {len(filtered_changes)}")
            
            files_to_analyze = filtered_changes[:self.config['max_files_per_analysis']]
            self.logger.debug(f"实际分析文件数量: {len(files_to_analyze)}")
            
            self.logger.info(f"AI分析 {len(files_to_analyze)} 个文件")
            
            # 使用逐个文件完整分析方法
            if len(files_to_analyze) == 0:
                return issues
            
            # 使用独立的逐个文件分析方法
            ai_issues, analysis_details = self._analyze_code_syntax_and_logic(files_to_analyze)
            analysis_details['total_issues'] = len(ai_issues)
            issues.extend(ai_issues)
            
            # 存储分析详情供后续使用
            self.current_analysis_details = analysis_details
            
            self.logger.info(f"AI逐个文件分析完成，发现 {len(ai_issues)} 个问题")
            
        except Exception as e:
            self.logger.error(f"AI审查失败: {e}")
            import traceback
            self.logger.error(f"详细错误信息: {traceback.format_exc()}")
        
        return issues
    
    def _analyze_code_syntax_and_logic(self, changes: List[Dict[str, Any]]) -> tuple[List[ReviewIssue], Dict[str, Any]]:
        """使用AI分析代码语法和逻辑正确性 - 多线程并发分析"""
        issues = []
        analysis_details = {
            'analyzed_files': [],
            'total_files': len(changes),
            'total_issues': 0,
            'thread_count': 3
        }
        
        try:
            self.logger.debug(f"开始语法和逻辑分析，变更数量: {len(changes)}")
            
            # 使用线程池管理器进行并发分析
            thread_pool_manager = ThreadPoolManager(max_workers=3, logger=self.logger)
            
            # 使用线程池并发分析文件
            issues, analysis_details_list = thread_pool_manager.analyze_files_concurrently(
                changes, 
                self._analyze_single_file_thread_safe
            )
            
            # 更新分析详情
            analysis_details['analyzed_files'] = analysis_details_list
            analysis_details['total_issues'] = len(issues)
            analysis_details['analysis_details'] = analysis_details_list
            
            # 统计分析结果
            successful_files = sum(1 for f in analysis_details_list if f.get('success', False))
            failed_files = len(analysis_details_list) - successful_files
            
            self.logger.info(f"多线程分析完成: 共分析 {len(changes)} 个文件，成功 {successful_files} 个，失败 {failed_files} 个，发现 {len(issues)} 个问题")
            
            return issues, analysis_details
            
        except Exception as e:
            self.logger.error(f"语法和逻辑分析失败: {e}")
            import traceback
            self.logger.error(f"语法和逻辑分析详细错误: {traceback.format_exc()}")
            return issues, analysis_details

    def _reanalyze_issues_with_original_prompt(self, issues: List[ReviewIssue]) -> List[ReviewIssue]:
        """使用首次提示词对AI问题列表进行复核"""
        if not issues:
            return issues

        # 仅复核AI自动生成的问题
        target_indexes = [
            idx for idx, issue in enumerate(issues)
            if issue.source in self.ai_issue_verification_sources
        ]
        if not target_indexes:
            return issues

        issue_entries = []
        for display_index, issue_index in enumerate(target_indexes, start=1):
            issue = issues[issue_index]
            issue_entries.append(
                f"{display_index}. 来源: {issue.source}\n"
                f"   严重级别: {issue.severity.value}\n"
                f"   文件: {issue.file_path or '未知'}\n"
                f"   行号: {issue.line_number if issue.line_number is not None else '未知'}\n"
                f"   标题: {issue.title}\n"
                f"   描述: {issue.description}\n"
                f"   建议: {issue.suggestion or '无'}"
            )

        issue_overview = "\n\n".join(issue_entries)

        verification_prompt = f"""
{self.ai_issue_prompt_instructions}

请注意：以上内容即为第一次AI分析使用的提示词要求。现在无需重新分析代码，请对下方问题列表进行复核，判断每条问题是否符合上述要求。

### 待复核问题列表（序号为1-based索引）
{issue_overview}

### 复核任务
- 仅根据提示词要求判断每条问题是否合规。
- 若问题符合要求，标记为“保留”；若不符合，标记为“剔除”并给出中文原因。
- 不允许新增问题或修改原有内容。

### 输出格式
请直接返回一个JSON对象：
{{
    "valid_indexes": [数字序号列表],
    "invalid_issues": [
        {{
            "index": 序号,
            "reason": "中文原因"
        }}
    ]
}}

- 所有文字必须使用中文。
- 若全部保留或全部剔除，请返回对应的数组（允许为空数组）。
- 禁止输出额外文字、解释或代码块。
"""

        verification_result = self._run_ai_analysis_with_fallback(
            prompt=verification_prompt,
            parse_function=self._parse_issue_verification_response,
            parse_args=(target_indexes,),
            stage_label='AI问题复核',
            reinforcement_instructions='请严格复核问题是否符合原提示词，按照要求输出JSON。'
        )

        if not verification_result or not isinstance(verification_result, dict):
            self.logger.warning("AI复核结果解析失败，保留全部AI问题")
            self.last_issue_verification_details = {
                'status': 'parse_failed',
                'original_issue_count': len(issues),
                'kept_issue_indexes': list(range(len(issues))),
                'removed_details': []
            }
            return issues

        valid_indexes = set(verification_result.get('valid_indexes', []))
        invalid_details = {
            detail['index']: detail.get('reason', '')
            for detail in verification_result.get('invalid_details', [])
            if isinstance(detail, dict) and 'index' in detail
        }

        if not valid_indexes and not invalid_details:
            self.logger.warning("AI复核未返回有效判断，保留全部AI问题")
            self.last_issue_verification_details = {
                'status': 'no_decision',
                'original_issue_count': len(issues),
                'kept_issue_indexes': list(range(len(issues))),
                'removed_details': []
            }
            return issues

        filtered_issues = []
        removed_count = 0
        removed_records = []

        for idx, issue in enumerate(issues):
            if idx in target_indexes:
                if idx in valid_indexes:
                    filtered_issues.append(issue)
                else:
                    removed_count += 1
                    reason = invalid_details.get(idx, '未提供原因')
                    removed_records.append({'index': idx, 'reason': reason, 'title': issue.title})
                    self.logger.debug(
                        f"AI复核剔除问题: source={issue.source}, file={issue.file_path}, line={issue.line_number}, "
                        f"title={issue.title}, 原因: {reason}"
                    )
            else:
                filtered_issues.append(issue)

        if removed_count > 0:
            self.logger.info(f"AI复核剔除 {removed_count} 个不符合提示词的问题")
        else:
            self.logger.info("AI复核未剔除任何问题，全部保留")

        kept_indexes = [idx for idx in target_indexes if idx in valid_indexes]
        self.last_issue_verification_details = {
            'status': 'success',
            'original_issue_count': len(issues),
            'kept_issue_indexes': kept_indexes,
            'removed_details': removed_records
        }

        return filtered_issues

    def _analyze_single_file(self, change: Dict[str, Any]) -> List[ReviewIssue]:
        """分析单个文件"""
        issues = []
        file_path = change.get('new_path', change.get('old_path', ''))
        
        try:
            # 判断变更类型
            change_type = self._determine_change_type(change)
            
            # 根据变更类型获取代码内容
            code_content = self._get_code_content_for_analysis(change, change_type)
            
            if code_content:
                # 检测文件类型
                file_type = self._detect_file_type(file_path)
                
                # 使用AI分析代码，传入变更类型信息
                analysis_issues = self._analyze_code_with_ai(
                    code_content, file_path, file_type, change_type
                )
                issues.extend(analysis_issues)
                
        except Exception as e:
            self.logger.warning(f"分析文件 {file_path} 失败: {e}")
        
        return issues

    def _analyze_single_file_thread_safe(self, change: Dict[str, Any], index: int, total: int) -> List[ReviewIssue]:
        """线程安全的单个文件分析方法"""
        import time
        start_time = time.time()
        
        file_path = change.get('new_path', change.get('old_path', ''))
        diff_size = len(change.get('diff', ''))
        
        self.logger.info(f"开始分析文件 {index+1}/{total}: {file_path} ({diff_size} bytes)")
        
        try:
            # 调用原有的分析方法
            issues = self._analyze_single_file(change)
            
            execution_time = time.time() - start_time
            self.logger.info(f"完成分析文件 {file_path}，耗时 {execution_time:.2f}s，发现 {len(issues)} 个问题")
            
            return issues
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"分析文件 {file_path} 失败，耗时 {execution_time:.2f}s: {e}")
            import traceback
            self.logger.error(f"文件分析详细错误: {traceback.format_exc()}")
            return []
    
    def _determine_change_type(self, change: Dict[str, Any]) -> str:
        """判断文件变更类型"""
        old_path = change.get('old_path', '')
        new_path = change.get('new_path', '')
        
        if not old_path and new_path:
            return 'new_file'  # 新增文件
        elif old_path and not new_path:
            return 'deleted_file'  # 删除文件
        elif old_path != new_path:
            return 'renamed_file'  # 重命名文件
        else:
            return 'modified_file'  # 修改文件
    
    def _get_code_content_for_analysis(self, change: Dict[str, Any], change_type: str) -> str:
        """根据变更类型获取用于分析的代码内容"""
        if change_type == 'new_file':
            # 新增文件：使用完整的diff内容（GitLab会提供完整文件内容）
            diff_content = change.get('diff', '')
            return self._extract_code_from_diff(diff_content, 'new_file')
        elif change_type == 'deleted_file':
            # 删除文件：通常不需要分析，但可以检查是否有相关依赖
            return ''
        elif change_type == 'renamed_file':
            # 重命名文件：分析可能的影响
            diff_content = change.get('diff', '')
            return self._extract_code_from_diff(diff_content, 'renamed')
        else:  # modified_file
            # 修改文件：直接使用GitLab提供的diff（包含合适的上下文）
            diff_content = change.get('diff', '')
            return self._extract_code_from_diff(diff_content, 'modified')
    
    def _filter_and_prioritize_changes(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """筛选和优先级排序文件变更"""
        filtered_changes = []
        
        for change in changes:
            file_path = change.get('new_path', change.get('old_path', ''))
            
            # 跳过删除的文件
            if change.get('deleted_file'):
                continue
            
            # 跳过匹配模式的文件
            if any(pattern in file_path for pattern in self.config['skip_file_patterns']):
                continue
            
            # 检查文件大小 - 提高限制，让AI处理大文件
            diff_content = change.get('diff', '')
            file_size_kb = len(diff_content.encode('utf-8')) / 1024
            if file_size_kb > self.config['max_file_size_kb']:
                self.logger.info(f"处理大文件: {file_path} ({file_size_kb:.1f}KB) - 使用单个文件分析")
                # 不跳过大文件，让AI完整分析
            
            # 计算优先级
            priority = self._calculate_file_priority(file_path, change)
            change['_priority'] = priority
            filtered_changes.append(change)
        
        # 按优先级排序
        filtered_changes.sort(key=lambda x: x.get('_priority', 0), reverse=True)
        
        return filtered_changes
    
    def _calculate_file_priority(self, file_path: str, change: Dict[str, Any]) -> int:
        """计算文件优先级"""
        priority = 1
        
        # 文件扩展名优先级
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in self.config['priority_file_extensions']:
            priority += 2
        
        # 关键路径优先级
        critical_paths = ['/src/', '/lib/', '/core/', '/api/', '/models/', '/controllers/']
        if any(path in file_path.lower() for path in critical_paths):
            priority += 2
        
        # 安全相关文件
        security_keywords = ['auth', 'security', 'login', 'password', 'token']
        if any(keyword in file_path.lower() for keyword in security_keywords):
            priority += 3
        
        # 变更量优先级
        diff_content = change.get('diff', '')
        additions = diff_content.count('\n+') - diff_content.count('\n+++')
        deletions = diff_content.count('\n-') - diff_content.count('\n---')
        total_changes = additions + deletions
        if total_changes > 100:
            priority += 1
        elif total_changes > 50:
            priority += 0.5
        
        return priority
    
    def _extract_code_from_diff(self, diff_text: str, change_type: str = 'modified') -> str:
        """智能从GitLab diff中提取代码内容，利用GitLab提供的上下文和行号信息"""
        if not diff_text:
            return ''
        
        try:
            lines = diff_text.split('\n')
            code_lines = []
            
            # 解析diff hunk headers获取行号信息
            # 格式: @@ -original_line,count +new_line,count @@
            hunk_pattern = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
            
            current_old_line = None
            current_new_line = None
            
            for line in lines:
                hunk_match = hunk_pattern.match(line)
                if hunk_match:
                    # 解析hunk header获取行号
                    current_old_line = int(hunk_match.group(1))
                    current_new_line = int(hunk_match.group(3))
                    continue
                
                if line.startswith((' ', '+', '-')):
                    # 安全地处理字符串切片
                    line_content = line[1:] if len(line) > 1 else ''
                    
                    # 确定实际行号（优先显示新文件的行号）
                    actual_line = None
                    if line.startswith('+'):
                        actual_line = current_new_line
                        if current_new_line is not None:
                            current_new_line += 1
                        if current_old_line is not None and not line.startswith('-'):
                            current_old_line += 1
                    elif line.startswith('-'):
                        actual_line = current_old_line
                        if current_old_line is not None:
                            current_old_line += 1
                    else:  # context line
                        actual_line = current_new_line
                        if current_new_line is not None:
                            current_new_line += 1
                        if current_old_line is not None:
                            current_old_line += 1
                    
                    # 保留原始行，但添加标记和实际行号以便AI理解
                    line_prefix = ""
                    if line.startswith('+'):
                        line_prefix = "[新增]"
                    elif line.startswith('-'):
                        line_prefix = "[删除]"
                    else:
                        line_prefix = "[上下文]"
                    
                    # 添加实际行号信息
                    if actual_line is not None:
                        code_lines.append(f"{line_prefix}[行{actual_line}] {line_content}")
                    else:
                        code_lines.append(f"{line_prefix} {line_content}")
            
            return '\n'.join(code_lines)
        except Exception as e:
            self.logger.warning(f"提取diff内容时出错: {e}")
            return f"提取diff内容时出错: {e}"
    
    def _detect_file_type(self, file_path: str) -> str:
        """检测文件类型"""
        if file_path.endswith('.vue'):
            return 'vue'
        elif file_path.endswith('.py'):
            return 'python'
        elif file_path.endswith(('.js', '.ts')):
            return 'javascript'
        elif file_path.endswith(('.jsx', '.tsx')):
            return 'jsx'
        elif file_path.endswith(('.java', '.kt')):
            return 'java'
        elif file_path.endswith(('.cpp', '.cc', '.cxx', '.c++', '.h', '.hpp')):
            return 'cpp'
        elif file_path.endswith('.c'):
            return 'c'
        elif file_path.endswith(('.go', '.rs')):
            return 'go'
        elif file_path.endswith(('.php', '.rb')):
            return 'script'
        elif file_path.endswith(('.html', '.htm')):
            return 'html'
        elif file_path.endswith(('.css', '.scss', '.sass', '.less')):
            return 'css'
        elif file_path.endswith(('.sh', '.bash', '.zsh')):
            return 'shell'
        elif file_path.endswith(('.sql', '.pgsql', '.mysql')):
            return 'sql'
        elif file_path.endswith('.xml'):
            return 'sql_mapper'  # 通常是MyBatis等SQL映射文件
        elif file_path.endswith(('.yaml', '.yml', '.json', '.toml')):
            return 'config'
        else:
            return 'unknown'
    
    def _analyze_code_with_ai(self, code: str, file_path: str, file_type: str, change_type: str = 'modified') -> List[ReviewIssue]:
        """使用AI分析代码语法和逻辑 - 支持智能上下文分析"""
        issues = []
        
        try:
            # 根据变更类型调整分析策略
            context_hint = ""
            if change_type == 'new_file':
                context_hint = "This is a new file. Perform comprehensive analysis including syntax, structure, security, and best practices."
            elif change_type == 'modified_file':
                context_hint = "This is a modified file. Code is marked as [新增], [删除], [上下文]. Focus on compatibility and logical consistency."
            elif change_type == 'renamed_file':
                context_hint = "This is a renamed file. Check for potential reference issues and import updates needed."
            
            # 构建语法检查提示
            context_section = f"Context Hint: {context_hint}\n\n" if context_hint else ""
            syntax_prompt = f"""
Analyze {file_type} code for issues:

File: {file_path}
Type: {change_type}
{context_section}Code:
```{file_type}
{code}
```

{self.ai_issue_prompt_instructions}
"""
            
            # 调用AI进行语法检查
            options = {}
            if self.ai_temperature is not None:
                options['temperature'] = self.ai_temperature
                options['top_k'] = 25
                options['top_p'] = 0.5
                options['repeat_penalty'] = 1.1

            syntax_issues = self._run_ai_analysis_with_fallback(
                prompt=syntax_prompt,
                parse_function=self._parse_syntax_analysis_response,
                parse_args=(file_path,),
                stage_label='代码语法分析',
                options=options if options else None,
                reinforcement_instructions='请重点关注新增代码中的高风险问题，宁可标记为疑似也不要遗漏。'
            )

            issues.extend(syntax_issues)
            
        except Exception as e:
            self.logger.warning(f"AI语法分析失败: {e}")
            
            # 如果AI分析失败，创建一个通用警告
            issue = ReviewIssue(
                severity=ReviewSeverity.WARNING,
                category='ai_analysis',
                title='AI语法分析失败',
                description=f'无法分析文件 {file_path} 的语法正确性: {str(e)}',
                file_path=file_path,
                line_number=1,
                suggestion='请手动检查代码语法',
                source='ai_syntax_checker'
            )
            issues.append(issue)
        
        return issues
    
    def _parse_syntax_analysis_response(self, ai_response, file_path: str) -> List[ReviewIssue]:
        """解析AI语法分析响应"""
        issues = []
        
        try:
            # 预处理AI响应，处理各种可能的格式
            import json
            
            # 记录原始响应类型用于调试
            self.logger.debug(f"原始AI响应类型: {type(ai_response)}")
            
            # 如果是字典格式，检查是否有response字段
            if isinstance(ai_response, dict):
                if 'response' in ai_response:
                    # 从response字段中提取实际的JSON数据
                    actual_response = ai_response['response']
                    self.logger.debug(f"检测到字典格式，从response字段提取数据")
                    
                    if isinstance(actual_response, str):
                        # 尝试解析response字段中的JSON
                        try:
                            # 第一次解析：解析转义的JSON字符串
                            first_parse = json.loads(actual_response)
                            self.logger.debug(f"第一次解析结果类型: {type(first_parse)}")
                            
                            # 如果第一次解析得到字符串，可能存在双重转义，尝试再次解析
                            if isinstance(first_parse, str):
                                try:
                                    self.logger.debug(f"检测到双重转义JSON，尝试第二次解析")
                                    second_parse = json.loads(first_parse)
                                    response_data = second_parse
                                    self.logger.debug(f"第二次解析成功，得到: {type(response_data)}")
                                except json.JSONDecodeError:
                                    # 如果第二次解析失败，使用第一次解析的结果
                                    response_data = first_parse
                                    self.logger.debug(f"第二次解析失败，使用第一次解析结果")
                            else:
                                response_data = first_parse
                                self.logger.debug(f"使用第一次解析结果: {type(response_data)}")
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"response字段JSON解析失败: {e}")
                            self.logger.debug(f"response字段内容: {actual_response[:200]}...")
                            return issues
                    else:
                        response_data = actual_response
                else:
                    response_data = ai_response
            elif isinstance(ai_response, str):
                # 直接是字符串格式，尝试解析JSON
                try:
                    response_data = json.loads(ai_response)
                    self.logger.debug(f"成功解析字符串JSON，得到: {type(response_data)}")
                except json.JSONDecodeError as e:
                    self.logger.warning(f"字符串JSON解析失败: {e}")
                    self.logger.debug(f"字符串内容: {ai_response[:200]}...")
                    return issues
            else:
                self.logger.warning(f"未知的AI响应类型: {type(ai_response)}")
                return issues
            
            # 现在response_data应该是解析后的JSON对象
            if not isinstance(response_data, dict):
                self.logger.warning(f"解析后的数据不是字典格式: {type(response_data)}")
                return issues
            
            # 提取errors数组
            errors = response_data.get('errors', [])
            self.logger.debug(f"找到 {len(errors)} 个错误")
            
            for error in errors:
                severity = ReviewSeverity.ERROR
                error_type = error.get('type', '语法错误')
                
                # 根据错误类型调整严重程度
                if '语法' in error_type or '编译' in error_type:
                    severity = ReviewSeverity.ERROR
                elif '类型' in error_type:
                    severity = ReviewSeverity.WARNING
                elif '逻辑' in error_type:
                    severity = ReviewSeverity.WARNING
                elif '运行时' in error_type:
                    severity = ReviewSeverity.WARNING
                
                issue = ReviewIssue(
                    severity=severity,
                    category='syntax',
                    title=f'{error_type}: {error.get("description", "未知错误")}',
                    description=error.get('description', ''),
                    file_path=file_path,
                    line_number=error.get('line_number', 1),
                    suggestion=error.get('suggestion', '请修复此错误'),
                    source='ai_syntax_checker'
                )
                issues.append(issue)
                self.logger.debug(f"成功解析问题: {issue.title}")
                
        except json.JSONDecodeError as e:
            # 如果AI返回的不是JSON，尝试从文本中提取错误信息
            self.logger.warning(f"JSON解析失败，尝试从文本中提取错误信息: {e}")
            
            # 如果是字典格式，从response字段提取文本
            if isinstance(ai_response, dict) and 'response' in ai_response:
                text_content = ai_response['response']
            elif isinstance(ai_response, str):
                text_content = ai_response
            else:
                text_content = str(ai_response)
            
            if '错误' in text_content or 'error' in text_content.lower():
                issue = ReviewIssue(
                    severity=ReviewSeverity.WARNING,
                    category='syntax',
                    title='AI检测到潜在问题',
                    description=text_content[:500],  # 限制描述长度
                    file_path=file_path,
                    line_number=1,
                    suggestion='请检查代码并修复AI识别的问题',
                    source='ai_syntax_checker'
                )
                issues.append(issue)
        except Exception as e:
            self.logger.warning(f"解析AI语法分析响应失败: {e}")
            import traceback
            self.logger.warning(f"详细错误信息: {traceback.format_exc()}")
        
        return issues

    def _handle_ai_response_error(self, ai_response, error: Exception, context: str) -> List[ReviewIssue]:
        """处理AI响应错误的专用方法"""
        issues = []
        
        # 创建错误记录问题
        error_issue = ReviewIssue(
            severity=ReviewSeverity.WARNING,
            category='ai_analysis',
            title=f'AI响应解析失败: {context}',
            description=f'AI响应解析失败: {str(error)}',
            suggestion='请检查AI模型配置和响应格式',
            source='ai_error_handler'
        )
        issues.append(error_issue)
        
        # 记录详细错误信息
        self.logger.error(f"AI响应解析失败 - 上下文: {context}")
        self.logger.error(f"错误类型: {type(error).__name__}")
        self.logger.error(f"错误信息: {str(error)}")
        
        # 尝试从失败的响应中提取有用信息
        if isinstance(ai_response, str) and len(ai_response) > 10:
            try:
                # 检查是否有明显的问题描述
                if any(keyword in ai_response.lower() for keyword in ['error', 'exception', 'failed', 'issue', 'problem']):
                    extracted_issues = self._extract_issues_from_text(ai_response)
                    issues.extend(extracted_issues)
                    self.logger.info(f"从错误响应中提取了 {len(extracted_issues)} 个问题")
            except Exception as extract_e:
                self.logger.warning(f"从错误响应提取问题时出错: {extract_e}")
        
        return issues
    
    def _parse_ai_response(self, ai_response) -> List[ReviewIssue]:
        """解析AI响应"""
        issues = []
        
        try:
            # 预处理AI响应，清理markdown代码块和思考过程
            self.logger.debug(f"原始AI响应类型: {type(ai_response)}")
            cleaned_response = self._clean_ai_response(ai_response)
            self.logger.debug(f"清理后的响应类型: {type(cleaned_response)}")
            
            # 安全地显示响应内容
            if isinstance(cleaned_response, str):
                self.logger.debug(f"清理后的响应: {cleaned_response[:300]}...")
            elif isinstance(cleaned_response, dict):
                self.logger.debug(f"清理后的响应: {str(cleaned_response)[:300]}...")
            else:
                self.logger.debug(f"清理后的响应: {str(cleaned_response)}")
            
            # 尝试解析JSON响应
            if isinstance(cleaned_response, str):
                response_data = json.loads(cleaned_response)
            elif isinstance(cleaned_response, dict):
                # 处理qwen3:32b等模型的特殊格式
                if 'response' in cleaned_response:
                    # 从response字段中提取实际的JSON数据
                    actual_response = cleaned_response['response']
                    self.logger.debug(f"检测到特殊格式，从response字段提取数据")
                    try:
                        if isinstance(actual_response, str):
                            self.logger.debug(f"尝试解析response字段JSON: {actual_response[:200]}...")
                            
                            # 预处理JSON字符串，移除可能的格式化问题
                            cleaned_json = self._clean_json_string(actual_response)
                            self.logger.debug(f"清理后的JSON: {cleaned_json[:200]}...")
                            
                            # 第一次解析：解析转义的JSON字符串
                            first_parse = json.loads(cleaned_json)
                            self.logger.debug(f"第一次解析结果类型: {type(first_parse)}")
                            
                            # 如果第一次解析得到字符串，可能存在双重转义，尝试再次解析
                            if isinstance(first_parse, str):
                                try:
                                    self.logger.debug(f"检测到双重转义JSON，尝试第二次解析")
                                    second_parse = json.loads(first_parse)
                                    response_data = second_parse
                                    self.logger.debug(f"第二次解析成功，得到: {type(response_data)}")
                                except json.JSONDecodeError:
                                    # 如果第二次解析失败，使用第一次解析的结果
                                    response_data = first_parse
                                    self.logger.debug(f"第二次解析失败，使用第一次解析结果")
                            else:
                                response_data = first_parse
                                self.logger.debug(f"使用第一次解析结果: {type(response_data)}")
                        else:
                            response_data = actual_response
                            self.logger.debug(f"response字段已经是对象类型: {type(response_data)}")
                    except json.JSONDecodeError as e:
                        # 如果response不是JSON，使用错误处理方法
                        return self._handle_ai_response_error(actual_response, e, "response字段JSON解析")
                else:
                    response_data = cleaned_response
            else:
                return self._handle_ai_response_error(cleaned_response, ValueError(f"未知的AI响应类型: {type(cleaned_response)}"), "响应类型检查")
            
            if isinstance(response_data, list):
                self.logger.debug(f"AI返回了 {len(response_data)} 个问题")
                for item in response_data:
                    try:
                        issue = ReviewIssue(
                            severity=ReviewSeverity(item.get('severity', 'INFO')),
                            category=item.get('category', 'ai_review'),
                            title=item.get('title', 'Unknown issue'),
                            description=item.get('description', ''),
                            file_path=item.get('file_path'),
                            line_number=item.get('line_number'),
                            suggestion=item.get('suggestion', ''),
                            source='ai_review'
                        )
                        issues.append(issue)
                        self.logger.debug(f"成功解析问题: {issue.title}")
                    except Exception as e:
                        self.logger.warning(f"解析AI问题失败: {e}")
                        continue
            else:
                self.logger.warning(f"AI响应格式错误，期望list但得到: {type(response_data)}")
                self.logger.warning(f"AI响应内容: {str(response_data)[:200]}...")
        
        except json.JSONDecodeError as e:
            return self._handle_ai_response_error(cleaned_response, e, "主JSON解析")
        except Exception as e:
            return self._handle_ai_response_error(cleaned_response, e, "AI响应处理异常")
        
        return issues
    
    def _analyze_summary_suggestions(self, issues: List[ReviewIssue], mr_details: Dict[str, Any]) -> List[ReviewIssue]:
        """AI汇总分析，提供整体建议（改进版本）"""
        summary_issues = []
        
        try:
            # 分析问题模式和趋势
            issue_patterns = self._analyze_issue_patterns(issues)
            
            # 构建增强的汇总分析提示
            summary_prompt = f"""
You are a senior software architect conducting a final review. Based on the detailed code analysis results, provide actionable recommendations:

## 合并请求上下文
- 标题: {mr_details['basic_info']['title']}
- 源分支: {mr_details['basic_info']['source_branch']}
- 目标分支: {mr_details['basic_info']['target_branch']}

## 问题分析总结
总计发现问题: {len(issues)}
- 严重问题(CRITICAL): {sum(1 for i in issues if i.severity == ReviewSeverity.CRITICAL)}
- 错误问题(ERROR): {sum(1 for i in issues if i.severity == ReviewSeverity.ERROR)}
- 警告问题(WARNING): {sum(1 for i in issues if i.severity == ReviewSeverity.WARNING)}
- 信息提示(INFO): {sum(1 for i in issues if i.severity == ReviewSeverity.INFO)}

## 问题模式分析
{issue_patterns}

## 问题分布
{self._format_issue_categories(issues)}

## 汇总规则
ONLY provide summary suggestions if there are CRITICAL or ERROR level issues that require immediate attention.

For minor issues (WARNING/INFO), return empty suggestions.

## 输出格式要求
请以JSON格式返回针对性建议：
{{
    "suggestions": [
        {{
            "category": "紧急修复",
            "title": "具体问题标题",
            "description": "基于实际CRITICAL/ERROR问题的修复说明",
            "suggestion": "具体修复步骤",
            "priority": "高",
            "related_issues": ["具体的CRITICAL/ERROR问题"]
        }}
    ]
}}

**严格要求**：
- 所有输出必须使用中文
- 只针对CRITICAL/ERROR级别问题提供建议
- 如果只有WARNING/INFO问题，返回空数组：{"suggestions": []}
- 不要提供通用的最佳实践建议
- 专注于实际需要修复的问题
"""
            
            # 调用AI进行汇总分析
            options = {}
            if self.ai_temperature is not None:
                options['temperature'] = self.ai_temperature

            summary_issues = self._run_ai_analysis_with_fallback(
                prompt=summary_prompt,
                parse_function=self._parse_enhanced_summary_response,
                parse_args=(),
                stage_label='汇总建议分析',
                options=options if options else None,
                reinforcement_instructions='请针对每个严重问题提供行动建议，若无法定位具体问题亦需说明原因。'
            )
            
        except Exception as e:
            self.logger.warning(f"AI汇总分析失败: {e}")
            # 提供基础的后备建议
            summary_issues = self._generate_fallback_suggestions(issues)
        
        return summary_issues
    
    def _analyze_issue_patterns(self, issues: List[ReviewIssue]) -> str:
        """分析问题模式和趋势"""
        if not issues:
            return "未发现明显问题模式"
        
        patterns = []
        
        # 按文件分组分析
        files_with_issues = {}
        for issue in issues:
            if issue.file_path:
                if issue.file_path not in files_with_issues:
                    files_with_issues[issue.file_path] = []
                files_with_issues[issue.file_path].append(issue)
        
        # 分析高频问题文件
        if files_with_issues:
            max_issues_file = max(files_with_issues.items(), key=lambda x: len(x[1]))
            if len(max_issues_file[1]) > 3:
                patterns.append(f"文件 {max_issues_file[0]} 集中了 {len(max_issues_file[1])} 个问题，建议重点关注")
        
        # 分析问题类型模式
        category_counts = {}
        severity_counts = {}
        for issue in issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1
            severity_counts[issue.severity.value] = severity_counts.get(issue.severity.value, 0) + 1
        
        # 分析主要问题类型
        if category_counts:
            top_category = max(category_counts.items(), key=lambda x: x[1])
            if top_category[1] >= len(issues) * 0.4:  # 占40%以上
                patterns.append(f"主要问题集中在 {top_category[0]} 方面，占比 {top_category[1]}/{len(issues)}")
        
        # 分析严重程度分布
        critical_error_count = severity_counts.get('CRITICAL', 0) + severity_counts.get('ERROR', 0)
        if critical_error_count > 0:
            patterns.append(f"发现 {critical_error_count} 个严重问题，需要优先处理")
        
        return "; ".join(patterns) if patterns else "问题分布较为分散，无明显集中模式"
    
    def _parse_enhanced_summary_response(self, ai_response) -> List[ReviewIssue]:
        """解析增强版AI汇总响应"""
        issues = []

        try:
            import json
            
            # 清理响应
            cleaned_response = self._clean_ai_response(ai_response)
            
            if isinstance(cleaned_response, str):
                response_data = json.loads(cleaned_response)
            elif isinstance(cleaned_response, dict):
                if 'response' in cleaned_response:
                    actual_response = cleaned_response['response']
                    if isinstance(actual_response, str):
                        response_data = json.loads(actual_response)
                    else:
                        response_data = actual_response
                else:
                    response_data = cleaned_response
            else:
                return issues
            
            for suggestion in response_data.get('suggestions', []):
                # 根据优先级确定严重程度
                priority = suggestion.get('priority', '中')
                if priority == '高':
                    severity = ReviewSeverity.WARNING
                else:
                    severity = ReviewSeverity.INFO
                
                issue = ReviewIssue(
                    severity=severity,
                    category=suggestion.get('category', 'summary'),
                    title=suggestion.get('title', '改进建议'),
                    description=suggestion.get('description', ''),
                    suggestion=suggestion.get('suggestion', ''),
                    source='ai_summary'
                )
                issues.append(issue)
                
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"解析增强版AI汇总响应失败: {e}")
            # 返回后备建议
            return self._generate_fallback_suggestions([])

        return issues

    def _parse_issue_verification_response(self, ai_response, index_map: List[int]) -> Dict[str, Any]:
        """解析AI复核响应，返回保留/剔除索引信息"""
        default_result = {
            'valid_indexes': index_map.copy(),
            'invalid_details': []
        }

        try:
            cleaned_response = self._clean_ai_response(ai_response)

            if isinstance(cleaned_response, str):
                response_data = json.loads(cleaned_response)
            elif isinstance(cleaned_response, dict):
                if 'response' in cleaned_response and isinstance(cleaned_response['response'], str):
                    response_data = json.loads(cleaned_response['response'])
                else:
                    response_data = cleaned_response
            else:
                return default_result

            if not isinstance(response_data, dict):
                return default_result

            valid_indexes = []
            for item in response_data.get('valid_indexes', []):
                if isinstance(item, int) and 1 <= item <= len(index_map):
                    mapped_index = index_map[item - 1]
                    if mapped_index not in valid_indexes:
                        valid_indexes.append(mapped_index)

            invalid_details = []
            for detail in response_data.get('invalid_issues', []):
                if not isinstance(detail, dict):
                    continue
                index_value = detail.get('index')
                if isinstance(index_value, int) and 1 <= index_value <= len(index_map):
                    mapped_index = index_map[index_value - 1]
                    invalid_details.append({
                        'index': mapped_index,
                        'reason': detail.get('reason', '')
                    })

            if not valid_indexes and invalid_details:
                # 如果没有明确保留索引，则默认为除无效索引外全部保留
                invalid_set = {item['index'] for item in invalid_details}
                valid_indexes = [idx for idx in index_map if idx not in invalid_set]

            result = {
                'valid_indexes': valid_indexes,
                'invalid_details': invalid_details
            }

            return result

        except json.JSONDecodeError as e:
            self.logger.warning(f"AI复核JSON解析失败: {e}")
            return default_result
        except Exception as e:
            self.logger.warning(f"解析AI复核响应时出错: {e}")
            return default_result

    def _run_ai_analysis_with_fallback(
        self,
        prompt: str,
        parse_function,
        parse_args: tuple = (),
        stage_label: str = "",
        options: Optional[Dict[str, Any]] = None,
        reinforcement_instructions: Optional[str] = None
    ) -> Any:
        """执行AI分析，必要时进行二阶段补充指令重试"""

        ollama_options = options if options else None

        primary_response = self.ollama_client.generate(
            prompt=prompt,
            model=self.config['ai_model'],
            options=ollama_options,
            enable_thinking=False
        )

        issues = parse_function(primary_response, *parse_args)

        if issues:
            return issues

        fallback_prompt = self._build_fallback_prompt(
            original_prompt=prompt,
            previous_response=primary_response,
            stage_label=stage_label,
            reinforcement_instructions=reinforcement_instructions
        )

        if not fallback_prompt:
            return issues

        fallback_response = self.ollama_client.generate(
            prompt=fallback_prompt,
            model=self.config['ai_model'],
            options=ollama_options,
            enable_thinking=False
        )

        fallback_issues = parse_function(fallback_response, *parse_args)

        return fallback_issues if fallback_issues else issues

    def _build_fallback_prompt(
        self,
        original_prompt: str,
        previous_response: Any,
        stage_label: str,
        reinforcement_instructions: Optional[str]
    ) -> str:
        """构建补充指令的第二阶段Prompt"""

        try:
            response_excerpt = self._format_ai_response_excerpt(previous_response)
        except Exception as e:
            self.logger.debug(f"整理AI上一轮响应失败: {e}")
            response_excerpt = "(上一轮输出无法提取)"

        instructions = [
            "请再次审查上述代码变更，确保找出最可能影响功能或安全的缺陷。",
            "禁止返回空的结果结构，若仅能给出潜在问题，请在描述中说明不确定性。",
            "输出必须严格遵循之前给出的JSON Schema，并仅输出该JSON。"
        ]

        if reinforcement_instructions:
            instructions.append(reinforcement_instructions)

        label = stage_label or "补充分析"

        fallback_prompt = (
            f"{original_prompt}\n\n"
            f"# {label}补充指令\n"
            + "\n".join(f"- {item}" for item in instructions)
            + "\n\n"
            + "上一轮输出（供参考，不要直接复制）:\n"
            + response_excerpt
        )

        return fallback_prompt

    def _format_ai_response_excerpt(self, ai_response: Any, max_length: int = 800) -> str:
        """提取AI响应摘要，用于第二阶段提示"""

        if isinstance(ai_response, dict):
            candidate = ai_response.get('response')
            if isinstance(candidate, str):
                text = candidate
            else:
                try:
                    text = json.dumps(ai_response, ensure_ascii=False)
                except Exception:
                    text = str(ai_response)
        else:
            text = str(ai_response)

        if not isinstance(text, str):
            text = str(text)

        cleaned_text = self._clean_markdown_content(text)

        if len(cleaned_text) > max_length:
            return cleaned_text[:max_length] + "..."

        return cleaned_text
    
    def _generate_fallback_suggestions(self, issues: List[ReviewIssue]) -> List[ReviewIssue]:
        """生成后备建议"""
        fallback_issues = []
        
        if not issues:
            # 无问题时的建议
            suggestion = ReviewIssue(
                severity=ReviewSeverity.INFO,
                category='最佳实践',
                title='代码质量保持',
                description='当前代码质量良好，建议继续保持代码规范',
                suggestion='定期进行代码审查，维护现有的代码质量标准',
                source='ai_summary'
            )
            fallback_issues.append(suggestion)
        else:
            # 有问题时的通用建议
            if any(issue.severity in [ReviewSeverity.CRITICAL, ReviewSeverity.ERROR] for issue in issues):
                suggestion = ReviewIssue(
                    severity=ReviewSeverity.WARNING,
                    category='代码质量',
                    title='优先修复严重问题',
                    description='发现了CRITICAL或ERROR级别的问题',
                    suggestion='建议优先修复严重问题，确保代码功能正确性',
                    source='ai_summary'
                )
                fallback_issues.append(suggestion)
            
            # 测试建议
            suggestion = ReviewIssue(
                severity=ReviewSeverity.INFO,
                category='测试策略',
                title='完善测试覆盖',
                description='建议增加测试用例以验证代码修改',
                suggestion='针对修改的代码添加单元测试和集成测试',
                source='ai_summary'
            )
            fallback_issues.append(suggestion)
        
        return fallback_issues
    
    def _format_issue_categories(self, issues: List[ReviewIssue]) -> str:
        """格式化问题类别统计"""
        categories = {}
        for issue in issues:
            category = issue.category
            categories[category] = categories.get(category, 0) + 1
        
        result = []
        for category, count in categories.items():
            result.append(f"{category}: {count}")
        
        return ", ".join(result)
    
    def _parse_summary_response(self, ai_response) -> List[ReviewIssue]:
        """解析AI汇总响应"""
        issues = []
        
        try:
            import json
            if isinstance(ai_response, str):
                response_data = json.loads(ai_response)
            elif isinstance(ai_response, dict):
                response_data = ai_response
            else:
                return issues
            
            for suggestion in response_data.get('suggestions', []):
                issue = ReviewIssue(
                    severity=ReviewSeverity.INFO,  # 汇总建议通常为INFO级别
                    category=suggestion.get('category', 'summary'),
                    title=suggestion.get('title', '建议'),
                    description=suggestion.get('description', ''),
                    suggestion=suggestion.get('suggestion', ''),
                    source='ai_summary'
                )
                issues.append(issue)
                
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"解析AI汇总响应失败: {e}")
        
        return issues
    
    def _clean_ai_response(self, ai_response):
        """清理AI响应，移除markdown代码块和思考过程"""
        
        if isinstance(ai_response, dict):
            # 如果是字典，递归清理其中的字符串值
            cleaned_dict = {}
            for key, value in ai_response.items():
                if isinstance(value, str):
                    cleaned_dict[key] = self._clean_markdown_content(value)
                else:
                    cleaned_dict[key] = value
            return cleaned_dict
        elif isinstance(ai_response, str):
            return self._clean_markdown_content(ai_response)
        else:
            # 对于不支持的类型，转换为字符串处理
            self.logger.warning(f"未知的AI响应类型: {type(ai_response)}，尝试转换为字符串")
            try:
                return str(ai_response)
            except Exception as e:
                self.logger.error(f"无法将AI响应转换为字符串: {e}")
                return '{"error": "无法解析AI响应"}'
    
    def _clean_markdown_content(self, content: str) -> str:
        """清理markdown内容，移除代码块和思考过程"""
        
        # 移除思考过程标签
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # 移除markdown代码块包装
        # 1. 移除 ```json 或 ``` 等代码块标记
        content = re.sub(r'```(?:json|javascript|python|bash)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        
        # 2. 处理可能的多行代码块情况
        lines = content.split('\n')
        cleaned_lines = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            if not in_code_block:
                cleaned_lines.append(line)
        
        content = '\n'.join(cleaned_lines)
        
        # 移除多余的空行
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # 去除首尾空白
        content = content.strip()
        
        return content
    
    def _clean_json_string(self, json_str: str) -> str:
        """清理JSON字符串，修复常见的格式问题"""
        if not json_str:
            return json_str
        
        try:
            # 移除可能的markdown代码块标记
            json_str = re.sub(r'```(?:json)?\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)
            
            # 移除注释（如果有的话）
            json_str = re.sub(r'//.*?\n', '\n', json_str)
            json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
            
            # 移除BOM和不可见字符
            json_str = json_str.replace('\ufeff', '')
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            
            # 修复转义字符问题
            # 处理错误的反斜杠转义
            json_str = re.sub(r'\\`', '`', json_str)  # 修复 \` 转义
            json_str = re.sub(r'\\([^"\\\/bfnrt])', r'\1', json_str)  # 移除非标准转义
            
            # 修复引号问题
            json_str = re.sub(r'[\u201c\u201d]', '"', json_str)  # 智能引号转普通引号
            json_str = re.sub(r'[\u2018\u2019]', "'", json_str)  # 智能单引号转普通单引号
            
            # 修复常见的JSON格式问题
            json_str = json_str.strip()
            
            # 确保是有效的JSON数组或对象格式
            if json_str.startswith('[') and json_str.endswith(']'):
                return json_str
            elif json_str.startswith('{') and json_str.endswith('}'):
                return json_str
            else:
                # 如果不是标准JSON格式，尝试包装为JSON数组
                if json_str.strip():
                    return f"[{json_str}]"
                return "[]"
                    
        except Exception as e:
            self.logger.warning(f"清理JSON字符串时出错: {e}")
            return json_str
    
    def _parse_json_leniently(self, json_str: str) -> Optional[Any]:
        """宽松解析JSON字符串，尝试修复常见错误"""
        if not json_str:
            return None
        
        try:
            # 首先尝试标准解析
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # 尝试修复常见问题
                cleaned = self._clean_json_string(json_str)
                return json.loads(cleaned)
            except json.JSONDecodeError:
                try:
                    # 尝试使用eval解析（仅用于安全环境）
                    # 注意：这里需要确保环境安全，或者使用更安全的替代方案
                    import ast
                    return ast.literal_eval(json_str)
                except (SyntaxError, ValueError):
                    return None
    
    def _extract_issues_from_text(self, text: str) -> List[ReviewIssue]:
        """从文本中提取问题（备用方案）"""
        issues = []

        if not text:
            return issues
        
        try:
            # 尝试从文本中提取结构化信息
            lines = text.split('\n')
            current_issue = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 检测严重程度
                severity = ReviewSeverity.WARNING  # 默认警告级别
                if any(keyword in line.upper() for keyword in ['CRITICAL', '严重', '关键']):
                    severity = ReviewSeverity.CRITICAL
                elif any(keyword in line.upper() for keyword in ['ERROR', '错误']):
                    severity = ReviewSeverity.ERROR
                elif any(keyword in line.upper() for keyword in ['WARNING', '警告']):
                    severity = ReviewSeverity.WARNING
                elif any(keyword in line.upper() for keyword in ['INFO', '信息']):
                    severity = ReviewSeverity.INFO
                
                # 检测问题类别
                category = 'ai_review'
                if any(keyword in line.lower() for keyword in ['security', '安全', '注入', '漏洞']):
                    category = 'security'
                elif any(keyword in line.lower() for keyword in ['performance', '性能', '效率']):
                    category = 'performance'
                elif any(keyword in line.lower() for keyword in ['syntax', '语法', '编译']):
                    category = 'syntax'
                elif any(keyword in line.lower() for keyword in ['logic', '逻辑', '业务']):
                    category = 'business_logic'
                elif any(keyword in line.lower() for keyword in ['code', '质量', 'quality']):
                    category = 'code_quality'
                
                # 检测文件路径
                file_path = None
                file_pattern = r'[a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*\.(?:java|py|js|vue|cpp|c|go|rs|php|rb|sql|xml|yaml|yml|json)'
                file_match = re.search(file_pattern, line)
                if file_match:
                    file_path = file_match.group()
                
                # 检测行号
                line_number = None
                line_pattern = r'line[:\s]*(\d+)|行[:\s]*(\d+)|(\d+)行'
                line_match = re.search(line_pattern, line, re.IGNORECASE)
                if line_match:
                    line_number = int(line_match.group(1) or line_match.group(2) or line_match.group(3))
                
                # 如果检测到新问题，保存当前问题并开始新的
                if current_issue and (severity != ReviewSeverity.INFO or len(line) > 50):
                    issues.append(current_issue)
                    current_issue = None
                
                # 创建新问题
                if not current_issue:
                    current_issue = ReviewIssue(
                        severity=severity,
                        category=category,
                        title=line[:100],  # 限制标题长度
                        description=line,
                        file_path=file_path,
                        line_number=line_number,
                        suggestion='',  # 从文本中提取建议比较困难
                        source='ai_review_text_parser'
                    )
                else:
                    # 补充现有问题的描述
                    current_issue.description += ' ' + line
            
            # 保存最后一个问题
            if current_issue:
                issues.append(current_issue)
                
        except Exception as e:
            self.logger.warning(f"从文本提取问题时出错: {e}")
            # 创建一个通用问题
            issues.append(ReviewIssue(
                severity=ReviewSeverity.WARNING,
                category='ai_review',
                title='AI检测到问题但解析失败',
                description=f'AI响应: {text[:500]}...',
                suggestion='请手动检查代码',
                source='ai_review_text_parser'
            ))

        return issues

    def _deduplicate_issues(self, issues: List[ReviewIssue]) -> List[ReviewIssue]:
        """去重问题"""
        unique_issues = []
        seen = set()
        
        for issue in issues:
            # 创建唯一标识
            key = (issue.file_path, issue.line_number, issue.title, issue.category)
            
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)
        
        return unique_issues
    
    def _determine_review_status(self, issues: List[ReviewIssue]) -> ReviewStatus:
        """确定审查状态"""
        has_critical = any(issue.severity == ReviewSeverity.CRITICAL for issue in issues)
        has_error = any(issue.severity == ReviewSeverity.ERROR for issue in issues)
        
        if has_critical or has_error:
            return ReviewStatus.FAILED
        elif any(issue.severity == ReviewSeverity.WARNING for issue in issues):
            return ReviewStatus.WARNING
        else:
            return ReviewStatus.PASSED
    
    def _generate_summary(self, issues: List[ReviewIssue]) -> Dict[str, Any]:
        """生成AI审查摘要"""
        summary = {
            'total_issues': len(issues),
            'by_severity': {},
            'by_category': {},
            'by_ai_focus': {},  # AI重点关注领域
            'by_source': {},
            'files_affected': set(),
            'ai_analysis_highlights': {
                'syntax_issues': 0,
                'logic_issues': 0,
                'security_issues': 0,
                'performance_issues': 0,
                'code_quality_issues': 0,
                'best_practices_violations': 0
            }
        }
        
        for issue in issues:
            # 按严重程度统计
            severity = issue.severity.value
            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
            
            # 按类别统计
            category = issue.category
            summary['by_category'][category] = summary['by_category'].get(category, 0) + 1
            
            # 按来源统计
            source = issue.source
            summary['by_source'][source] = summary['by_source'].get(source, 0) + 1
            
            # 按AI重点关注领域统计
            if issue.category in ['security', 'performance', 'code_quality']:
                summary['by_ai_focus'][issue.category] = summary['by_ai_focus'].get(issue.category, 0) + 1
            
            # AI分析亮点统计
            if source == 'ai_syntax_checker':
                summary['ai_analysis_highlights']['syntax_issues'] += 1
            elif source == 'ai_intelligent_review':
                if issue.category == 'security':
                    summary['ai_analysis_highlights']['security_issues'] += 1
                elif issue.category == 'performance':
                    summary['ai_analysis_highlights']['performance_issues'] += 1
                elif issue.category == 'code_quality':
                    summary['ai_analysis_highlights']['code_quality_issues'] += 1
                elif any(keyword in issue.title.lower() for keyword in ['logic', 'logical', '逻辑']):
                    summary['ai_analysis_highlights']['logic_issues'] += 1
                elif any(keyword in issue.title.lower() for keyword in ['best practice', 'practice', '最佳实践']):
                    summary['ai_analysis_highlights']['best_practices_violations'] += 1
            elif source == 'ai_summary':
                summary['ai_analysis_highlights']['best_practices_violations'] += 1
            
            # 记录受影响文件
            if issue.file_path:
                summary['files_affected'].add(issue.file_path)
        
        summary['files_affected'] = len(summary['files_affected'])
        
        # 添加分析详情
        if self.current_analysis_details:
            summary['analysis_details'] = self.current_analysis_details
            summary['files_analyzed'] = self.current_analysis_details.get('total_files', summary['files_affected'])
        else:
            summary['files_analyzed'] = summary['files_affected']
        
        return summary
    
    def _calculate_analysis_quality_score(self, issues: List[ReviewIssue]) -> float:
        """计算AI分析质量得分 (0-100) - 改进版本"""
        if not issues:
            return 95.0  # 没有问题时给95分，避免过于绝对
        
        base_score = 100.0
        total_deductions = 0.0
        
        # 改进的严重程度权重
        severity_weights = {
            'CRITICAL': 30,  # CRITICAL问题扣30分
            'ERROR': 15,     # ERROR问题扣15分  
            'WARNING': 5,    # WARNING问题扣5分
            'INFO': 1        # INFO问题扣1分
        }
        
        # 问题类别权重倍数
        category_multipliers = {
            'security': 1.5,     # 安全问题权重更高
            'performance': 1.3,  # 性能问题权重较高
            'syntax': 1.2,       # 语法问题权重中等
            'code_quality': 1.0, # 代码质量正常权重
            'best_practice': 0.8 # 最佳实践权重较低
        }
        
        # 计算基础扣分
        for issue in issues:
            base_deduction = severity_weights.get(issue.severity.value, 1)
            category_multiplier = category_multipliers.get(issue.category, 1.0)
            
            # 应用类别权重
            weighted_deduction = base_deduction * category_multiplier
            total_deductions += weighted_deduction
        
        # 问题数量惩罚：问题过多时额外扣分
        issue_count_penalty = 0
        if len(issues) > 10:
            issue_count_penalty = (len(issues) - 10) * 2  # 超过10个问题每个额外扣2分
        elif len(issues) > 5:
            issue_count_penalty = (len(issues) - 5) * 1   # 超过5个问题每个额外扣1分
        
        total_deductions += issue_count_penalty
        
        # AI分析覆盖度加分
        ai_issues = [issue for issue in issues if issue.source.startswith('ai_')]
        ai_coverage_bonus = 0
        if ai_issues:
            coverage_rate = len(ai_issues) / len(issues)
            if coverage_rate >= 0.8:  # 80%以上AI覆盖给额外加分
                ai_coverage_bonus = 5
            elif coverage_rate >= 0.6:  # 60%以上给小幅加分
                ai_coverage_bonus = 2
        
        # 计算最终得分
        final_score = base_score - total_deductions + ai_coverage_bonus
        
        # 确保得分在合理范围内
        final_score = max(0, min(100, final_score))
        
        return round(final_score, 1)
    
    
def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='GitLab MR 自动审查引擎')
    parser.add_argument('--project-id', required=True, help='GitLab项目ID')
    parser.add_argument('--mr-iid', required=True, type=int, help='合并请求IID')
    parser.add_argument('--output', choices=['json', 'console'], default='console', help='输出格式')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    try:
        # 创建审查引擎
        engine = MRReviewEngine()
        
        # 执行审查
        result = engine.review_merge_request(args.project_id, args.mr_iid)
        
        # 输出结果
        if args.output == 'json':
            # 计算AI分析质量得分
            def calculate_quality_score(issues):
                if not issues:
                    return 100.0
                
                score = 100.0
                deductions = 0.0
                
                severity_weights = {
                    'CRITICAL': 15,
                    'ERROR': 10,
                    'WARNING': 5,
                    'INFO': 1
                }
                
                for issue in issues:
                    deductions += severity_weights.get(issue.severity.value, 1)
                
                category_deductions = {
                    'security': 1.5,
                    'performance': 1.2,
                    'syntax': 1.0,
                }
                
                for issue in issues:
                    multiplier = category_deductions.get(issue.category, 1.0)
                    deductions *= multiplier
                
                ai_issues = [issue for issue in issues if issue.source.startswith('ai_')]
                ai_coverage = len(ai_issues) / len(issues) if issues else 1.0
                score *= ai_coverage
                
                final_score = max(0, score - deductions)
                return round(final_score, 1)
            
            output = {
                'mr_id': result.mr_id,
                'mr_title': result.mr_title,
                'status': result.status.value,
                'review_time': result.review_time.isoformat(),
                'summary': result.summary,
                'issues': [asdict(issue) for issue in result.issues],
                'metadata': result.metadata,
                'ai_analysis_metadata': {
                    'analysis_type': 'pure_ai',
                    'ai_model': result.metadata.get('review_config', {}).get('ai_model', 'unknown'),
                    'analysis_focus_areas': ['security', 'performance', 'code_quality', 'syntax', 'logic'],
                    'ai_analyzers_used': list(set(issue.source for issue in result.issues if issue.source.startswith('ai_'))),
                    'total_ai_issues': len([issue for issue in result.issues if issue.source.startswith('ai_')]),
                    'analysis_quality_score': calculate_quality_score(result.issues)
                }
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            # 控制台输出 - 优化为AI分析报告格式
            print(f"\n🤖 AI智能代码审查报告")
            print(f"═" * 60)
            print(f"📋 MR信息: {result.mr_title}")
            print(f"👤 作者: {result.mr_author}")
            print(f"📅 审查时间: {result.review_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📊 审查状态: {result.status.value}")
            print(f"📁 变更文件: {result.metadata['files_changed']}")
            print(f"🔍 发现问题: {len(result.issues)}")
            
            if result.issues:
                print(f"\n🎯 AI分析亮点:")
                highlights = result.summary['ai_analysis_highlights']
                if highlights['syntax_issues'] > 0:
                    print(f"  ✅ 语法检查: 发现 {highlights['syntax_issues']} 个问题")
                if highlights['security_issues'] > 0:
                    print(f"  🔒 安全分析: 发现 {highlights['security_issues']} 个风险")
                if highlights['performance_issues'] > 0:
                    print(f"  ⚡ 性能分析: 发现 {highlights['performance_issues']} 个问题")
                if highlights['logic_issues'] > 0:
                    print(f"  🧠 逻辑分析: 发现 {highlights['logic_issues']} 个问题")
                if highlights['code_quality_issues'] > 0:
                    print(f"  🎨 代码质量: 发现 {highlights['code_quality_issues']} 个问题")
                if highlights['best_practices_violations'] > 0:
                    print(f"  📚 最佳实践: 发现 {highlights['best_practices_violations']} 个改进建议")
                
                print(f"\n📋 问题详情:")
                for i, issue in enumerate(result.issues[:10], 1):  # 显示前10个问题
                    print(f"  {i}. [{issue.severity.value.upper()}] {issue.title}")
                    if issue.file_path:
                        print(f"     📁 文件: {issue.file_path}")
                    if issue.suggestion:
                        print(f"     💡 建议: {issue.suggestion}")
                    if issue.source != 'unknown':
                        print(f"     🤖 分析器: {issue.source}")
                
                if len(result.issues) > 10:
                    print(f"  ... 还有 {len(result.issues) - 10} 个问题，请查看详细报告")
            
            print(f"\n📊 AI分析统计:")
            print(f"  🎯 重点关注领域: {result.summary.get('by_ai_focus', {})}")
            print(f"  ⚠️  严重程度分布: {result.summary['by_severity']}")
            print(f"  🏷️  问题类别分布: {result.summary['by_category']}")
            print(f"  🔧 分析器来源: {result.summary['by_source']}")
            
            # AI分析质量指标
            ai_sources = [s for s in result.summary['by_source'].keys() if s.startswith('ai_')]
            if ai_sources:
                print(f"  🤖 AI分析覆盖率: {sum(result.summary['by_source'][s] for s in ai_sources)}/{len(result.issues)}")
            
            print(f"\n✨ AI驱动的智能代码审查完成")
    
    except Exception as e:
        logger.error(f"审查失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
