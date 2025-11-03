#!/usr/bin/env python3
"""
SQL项目扫描器
基于GitLab和AI的SQL文件异常扫描工具

功能特点：
- 支持版本路径精确匹配和模糊匹配
- 自动识别MySQL、Oracle、DB2数据库类型
- 使用AI进行SQL异常分析
- 生成详细的扫描报告
"""

import os
import sys
import json
import glob
import fnmatch
import re
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import threading

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.gitlab_client import GitLabClient
from shared.ollama_client import OllamaClient
from shared.utils import setup_logging
from shared.thread_pool_manager import ThreadPoolManager

class SQLProjectScanner:
    """SQL项目扫描器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化扫描器
        
        Args:
            config_path: 配置文件路径
        """
        self.logger = setup_logging()
        self.config = self._load_config(config_path)
        self.gitlab_client = GitLabClient()
        self.ollama_client = OllamaClient()
        self.thread_pool = ThreadPoolManager(max_workers=self.config.get('global_settings', {}).get('max_concurrent_files', 5))
        
        # 扫描统计
        self.scan_stats = {
            'total_files': 0,
            'scanned_files': 0,
            'error_files': 0,
            'issues_found': 0,
            'by_db_type': {},
            'by_version': {}
        }
        
        # 扫描结果
        self.scan_results = []

    def _log(self, level: str, message: str, **details) -> None:
        """统一日志输出，将详细信息写入 debug 级别便于排查。"""
        log_method = getattr(self.logger, level, None)
        if log_method is None:
            log_method = self.logger.info

        details_str = ""
        if details:
            details_str = ", ".join(f"{key}={value!r}" for key, value in details.items())

        if level == 'debug':
            if details_str:
                log_method(f"{message} | details: {details_str}")
            else:
                log_method(message)
        else:
            log_method(message)
            if details_str:
                self.logger.debug(f"{message} | details: {details_str}")

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """加载配置文件"""
        if config_path is None:
            config_path = os.path.join(project_root, 'examples', 'sql_project_config.json')
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self._log('info', "配置文件加载成功", config_path=config_path)
            return config
        except Exception as e:
            self._log('error', "配置文件加载失败", config_path=config_path, error=str(e))
            return {}
    
    def scan_project(self, project_id: str, version_path: str, 
                    db_type: Optional[str] = None, 
                    output_format: str = 'console',
                    branch: Optional[str] = None,
                    **kwargs) -> Dict[str, Any]:
        """
        扫描项目
        
        Args:
            project_id: 项目ID
            version_path: 版本路径
            db_type: 数据库类型过滤
            output_format: 输出格式
            **kwargs: 其他参数，包括AI相关参数
            
        Returns:
            扫描结果
        """
        # 提取AI参数
        ai_params = {
            'custom_model': kwargs.get('custom_model'),
            'enable_thinking': kwargs.get('enable_thinking', False),
            'temperature': kwargs.get('temperature', 0.7),
            'top_p': kwargs.get('top_p', 0.9),
            'max_tokens': kwargs.get('max_tokens', 2000),
            'analysis_depth': kwargs.get('analysis_depth', 'standard'),
            'focus_areas': kwargs.get('focus_areas'),
            'custom_instructions': kwargs.get('custom_instructions', '')
        }
        
        # 过滤掉None值
        ai_params = {k: v for k, v in ai_params.items() if v is not None}
        
        # 存储AI参数供后续使用
        self.ai_params = ai_params
        
        self._log('info', "开始扫描项目", project_id=project_id, version_path=version_path)
        if ai_params.get('custom_model'):
            self._log('info', "启用自定义AI模型", custom_model=ai_params['custom_model'])
        
        # 获取项目配置
        project_config = self.config.get('projects', {}).get(project_id)
        if not project_config:
            self._log('error', "未找到项目配置", project_id=project_id)
            return {'error': f'未找到项目配置: {project_id}'}
        
        # 解析版本路径
        version_dirs = self._resolve_version_paths(project_id, version_path, project_config, branch)
        if not version_dirs:
            self._log('error', "未找到匹配的版本路径", version_path=version_path)
            return {'error': f'未找到匹配的版本路径: {version_path}'}

        self._log('info', "解析到版本目录", version_dirs=version_dirs, count=len(version_dirs))
        
        # 扫描每个版本目录
        all_results = []
        for version_dir in version_dirs:
            version_name = os.path.basename(version_dir)
            self._log('info', "开始扫描版本", version_name=version_name, version_dir=version_dir)
            
            version_results = self._scan_version_directory(
                project_id, version_dir, version_name, project_config, db_type
            )
            all_results.extend(version_results)
        
        # 生成报告
        report = self._generate_report(all_results, project_id, version_path)
        
        # 输出结果
        self._output_results(report, output_format)
        
        return report
    
    def _resolve_version_paths(self, project_id: str, version_path: str, 
                              project_config: Dict[str, Any],
                              branch: Optional[str] = None) -> List[str]:
        """
        解析版本路径
        
        Args:
            project_id: 项目ID
            version_path: 版本路径（支持通配符）
            project_config: 项目配置
            
        Returns:
            匹配的版本目录列表
        """
        base_path = project_config.get('version_base_path', 'database/versions')
        
        # 获取项目所有文件
        try:
            project_files = self.gitlab_client.get_project_files(project_id, ref=branch)
            if not project_files:
                self._log('warning', "未获取到项目文件", project_id=project_id)
                return []
        except Exception as e:
            self._log('error', "获取项目文件失败", project_id=project_id, error=str(e))
            return []
        
        # 提取所有可能的版本目录
        version_dirs = set()
        for file_path in project_files:
            if file_path.startswith(base_path):
                # 提取版本目录路径
                relative_path = file_path[len(base_path):].lstrip('/')
                if '/' in relative_path:
                    version_dir = relative_path.split('/')[0]
                    full_version_path = f"{base_path}/{version_dir}"
                    version_dirs.add(full_version_path)
        
        version_dirs = sorted(list(version_dirs))
        
        # 匹配版本路径
        matched_dirs = []
        
        # 处理多个版本路径（逗号分隔）
        version_patterns = [v.strip() for v in version_path.split(',')]
        
        for pattern in version_patterns:
            if pattern == '*':
                # 匹配所有版本
                matched_dirs.extend(version_dirs)
            elif '*' in pattern or '?' in pattern:
                # 模糊匹配
                matched_dirs.extend([d for d in version_dirs 
                                   if fnmatch.fnmatch(os.path.basename(d), pattern)])
            elif re.match(r'^[^/]*\[.*\][^/]*$', pattern):
                # 正则表达式匹配
                regex_pattern = pattern.replace('[', '').replace(']', '')
                try:
                    regex = re.compile(regex_pattern)
                    matched_dirs.extend([d for d in version_dirs 
                                       if regex.match(os.path.basename(d))])
                except re.error as e:
                    self._log('error', "版本路径正则解析失败", pattern=pattern, regex_pattern=regex_pattern, error=str(e))
            else:
                # 精确匹配
                exact_match = f"{base_path}/{pattern}"
                if exact_match in version_dirs:
                    matched_dirs.append(exact_match)
        
        # 去重并排序
        matched_dirs = sorted(list(set(matched_dirs)))
        
        return matched_dirs
    
    def _scan_version_directory(self, project_id: str, version_dir: str, 
                              version_name: str, project_config: Dict[str, Any],
                              db_type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        扫描版本目录
        
        Args:
            project_id: 项目ID
            version_dir: 版本目录
            version_name: 版本名称
            project_config: 项目配置
            db_type_filter: 数据库类型过滤
            
        Returns:
            扫描结果列表
        """
        results = []
        
        # 获取版本目录下的所有文件
        try:
            all_files = self.gitlab_client.get_project_files(project_id, ref=branch)
            version_files = [f for f in all_files if f.startswith(version_dir)]
        except Exception as e:
            self._log('error', "获取版本文件失败", project_id=project_id, version_dir=version_dir, error=str(e))
            return results
        
        # 按数据库类型分类文件
        db_type_patterns = project_config.get('db_type_patterns', {})
        categorized_files = self._categorize_files_by_db_type(version_files, db_type_patterns)
        
        # 扫描每个数据库类型的文件
        for db_type, files in categorized_files.items():
            if db_type_filter and db_type != db_type_filter:
                continue
                
            self._log('info', "准备扫描数据库类型文件", db_type=db_type, file_count=len(files))
            
            # 更新统计
            if db_type not in self.scan_stats['by_db_type']:
                self.scan_stats['by_db_type'][db_type] = {
                    'total_files': 0,
                    'scanned_files': 0,
                    'error_files': 0,
                    'issues_found': 0
                }
            
            if version_name not in self.scan_stats['by_version']:
                self.scan_stats['by_version'][version_name] = {
                    'total_files': 0,
                    'scanned_files': 0,
                    'error_files': 0,
                    'issues_found': 0
                }
            
            self.scan_stats['by_db_type'][db_type]['total_files'] += len(files)
            self.scan_stats['by_version'][version_name]['total_files'] += len(files)
            self.scan_stats['total_files'] += len(files)
            
            # 并发扫描文件
            file_results = self._scan_files_concurrent(
                project_id, files, db_type, version_name
            )
            results.extend(file_results)
        
        return results
    
    def _categorize_files_by_db_type(self, files: List[str], 
                                    db_type_patterns: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        按数据库类型分类文件
        
        Args:
            files: 文件列表
            db_type_patterns: 数据库类型匹配模式
            
        Returns:
            按数据库类型分类的文件字典
        """
        categorized = {}
        
        for file_path in files:
            # 跳过非SQL文件
            if not file_path.lower().endswith(('.sql', '.mysql', '.oracle', '.db2')):
                continue
            
            # 检测数据库类型
            detected_db_type = self._detect_db_type(file_path, db_type_patterns)
            
            if detected_db_type not in categorized:
                categorized[detected_db_type] = []
            categorized[detected_db_type].append(file_path)
        
        return categorized
    
    def _detect_db_type(self, file_path: str, db_type_patterns: Dict[str, List[str]]) -> str:
        """
        检测文件数据库类型
        
        Args:
            file_path: 文件路径
            db_type_patterns: 数据库类型匹配模式
            
        Returns:
            数据库类型
        """
        # 基于文件路径匹配
        for db_type, patterns in db_type_patterns.items():
            for pattern in patterns:
                if fnmatch.fnmatch(file_path, pattern):
                    return db_type
        
        # 基于文件扩展名
        file_lower = file_path.lower()
        if '.mysql.sql' in file_lower or file_lower.endswith('.mysql'):
            return 'mysql'
        elif '.oracle.sql' in file_lower or file_lower.endswith('.oracle'):
            return 'oracle'
        elif '.db2.sql' in file_lower or file_lower.endswith('.db2'):
            return 'db2'
        
        # 基于内容检测（如果需要）
        return 'default'
    
    def _scan_files_concurrent(self, project_id: str, files: List[str], 
                              db_type: str, version_name: str) -> List[Dict[str, Any]]:
        """
        并发扫描文件
        
        Args:
            project_id: 项目ID
            files: 文件列表
            db_type: 数据库类型
            version_name: 版本名称
            
        Returns:
            扫描结果列表
        """
        results = []
        
        def scan_single_file(file_path: str) -> Optional[Dict[str, Any]]:
            """扫描单个文件"""
            try:
                return self._scan_single_file(project_id, file_path, db_type, version_name)
            except Exception as e:
                self._log('error', "扫描文件失败", file_path=file_path, db_type=db_type, version=version_name, error=str(e))
                return {
                    'file_path': file_path,
                    'db_type': db_type,
                    'version': version_name,
                    'error': str(e),
                    'status': 'error'
                }
        
        # 使用线程池并发扫描
        tasks = [
            (scan_single_file, (file_path,), {})
            for file_path in files
        ]

        task_results = self.thread_pool.execute_tasks(tasks)

        for task_result in task_results:
            if task_result.success:
                result = task_result.result
                if result:
                    results.append(result)
            else:
                error_message = task_result.error or '未知错误'
                self._log('error', "获取扫描结果失败", error=error_message, db_type=db_type, version=version_name)
                results.append({
                    'file_path': task_result.file_path or '未知文件',
                    'db_type': db_type,
                    'version': version_name,
                    'error': error_message,
                    'status': 'error'
                })
        
        return results
    
    def _scan_single_file(self, project_id: str, file_path: str, 
                         db_type: str, version_name: str) -> Optional[Dict[str, Any]]:
        """
        扫描单个文件
        
        Args:
            project_id: 项目ID
            file_path: 文件路径
            db_type: 数据库类型
            version_name: 版本名称
            
        Returns:
            扫描结果
        """
        self._log('debug', "扫描文件", file_path=file_path)
        
        # 获取文件内容
        try:
            file_content = self.gitlab_client.get_file_content(project_id, file_path, ref=branch)
            if not file_content:
                self._log('warning', "文件内容为空", file_path=file_path)
                return None
        except Exception as e:
            self._log('error', "获取文件内容失败", file_path=file_path, project_id=project_id, error=str(e))
            return None

        # 检查文件大小
        file_size = len(file_content)
        max_size = self.config.get('global_settings', {}).get('max_file_size', 100000)
        if file_size > max_size:
            self._log('warning', "文件过大，跳过扫描", file_path=file_path, file_size=file_size, max_size=max_size)
            return None
        
        # AI分析
        try:
            # 获取AI参数（从类属性或方法参数传递）
            ai_params = getattr(self, 'ai_params', {})
            ai_result = self._analyze_sql_with_ai(
                file_content, db_type, file_path, 
                project_id=project_id,
                **ai_params
            )
        except Exception as e:
            self._log('error', "AI分析失败", file_path=file_path, db_type=db_type, error=str(e))
            ai_result = {'error': str(e)}
        
        # 构建结果
        result = {
            'file_path': file_path,
            'db_type': db_type,
            'version': version_name,
            'file_size': file_size,
            'scan_time': datetime.now().isoformat(),
            'ai_analysis': ai_result,
            'status': 'success'
        }
        
        # 更新统计
        self.scan_stats['scanned_files'] += 1
        self.scan_stats['by_db_type'][db_type]['scanned_files'] += 1
        self.scan_stats['by_version'][version_name]['scanned_files'] += 1
        
        if 'error' in ai_result:
            self.scan_stats['error_files'] += 1
            self.scan_stats['by_db_type'][db_type]['error_files'] += 1
            self.scan_stats['by_version'][version_name]['error_files'] += 1
        elif ai_result.get('issues'):
            self.scan_stats['issues_found'] += len(ai_result['issues'])
            self.scan_stats['by_db_type'][db_type]['issues_found'] += len(ai_result['issues'])
            self.scan_stats['by_version'][version_name]['issues_found'] += len(ai_result['issues'])
        
        return result
    
    def _analyze_sql_with_ai(self, sql_content: str, db_type: str, file_path: str, 
                          custom_model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        使用AI分析SQL内容
        
        Args:
            sql_content: SQL内容
            db_type: 数据库类型
            file_path: 文件路径
            custom_model: 自定义模型名称
            **kwargs: 其他AI参数
            
        Returns:
            AI分析结果
        """
        # 获取项目配置
        project_id = kwargs.get('project_id', '93')  # 从参数获取项目ID
        project_config = self.config.get('projects', {}).get(project_id, {})
        ai_config = project_config.get('ai_analysis', {})
        
        # 构建分析提示词
        prompt = self._build_analysis_prompt(sql_content, db_type, file_path, ai_config, **kwargs)
        
        # 确定使用的模型（优先级：命令行参数 > 配置文件 > 默认值）
        model = custom_model or ai_config.get('model', 'qwen:7b')
        enable_thinking = kwargs.get('enable_thinking', ai_config.get('enable_thinking', False))
        
        # 获取其他AI参数
        ai_params = {
            'temperature': kwargs.get('temperature', ai_config.get('temperature', 0.7)),
            'top_p': kwargs.get('top_p', ai_config.get('top_p', 0.9)),
            'max_tokens': kwargs.get('max_tokens', ai_config.get('max_tokens', 2000))
        }
        
        self._log('info', "执行AI模型分析", file_path=file_path, model=model, enable_thinking=enable_thinking)
        
        try:
            # 执行AI分析
            result = self.ollama_client.analyze_text(
                prompt, model, "custom", enable_thinking=enable_thinking
            )
            
            # 解析AI结果
            parsed_result = self._parse_ai_result(result)
            
            # 添加分析元信息
            parsed_result['analysis_metadata'] = {
                'model_used': model,
                'db_type': db_type,
                'file_path': file_path,
                'analysis_time': datetime.now().isoformat(),
                'ai_params': ai_params
            }
            
            return parsed_result
            
        except Exception as e:
            self._log('error', "AI模型分析失败", file_path=file_path, db_type=db_type, model=model, error=str(e))
            return {
                'error': str(e),
                'analysis_metadata': {
                    'model_used': model,
                    'db_type': db_type,
                    'file_path': file_path,
                    'analysis_time': datetime.now().isoformat(),
                    'ai_params': ai_params
                }
            }
    
    def _build_analysis_prompt(self, sql_content: str, db_type: str, 
                              file_path: str, ai_config: Dict[str, Any], **kwargs) -> str:
        """
        构建AI分析提示词
        
        Args:
            sql_content: SQL内容
            db_type: 数据库类型
            file_path: 文件路径
            ai_config: AI配置
            **kwargs: 其他参数
            
        Returns:
            分析提示词
        """
        # 获取检查重点（支持命令行参数覆盖）
        focus_areas = kwargs.get('focus_areas', ai_config.get('focus_areas', [
            "语法错误", "性能问题", "安全风险", "逻辑异常", "最佳实践"
        ]))
        
        # 获取分析深度
        analysis_depth = kwargs.get('analysis_depth', ai_config.get('analysis_depth', 'standard'))
        
        # 获取自定义分析指令
        custom_instructions = kwargs.get('custom_instructions', ai_config.get('custom_instructions', ''))
        
        # 根据分析深度调整提示词复杂度
        if analysis_depth == 'deep':
            depth_instruction = """
请进行深度分析，包括：
- 详细的执行计划分析
- 复杂查询的性能影响评估
- 潜在的并发问题
- 长期维护性评估
"""
        elif analysis_depth == 'quick':
            depth_instruction = """
请进行快速检查，重点关注：
- 明显的语法错误
- 严重的性能问题
- 关键的安全风险
"""
        else:  # standard
            depth_instruction = """
请进行标准分析，包括：
- 语法正确性检查
- 性能问题识别
- 安全风险评估
- 逻辑一致性检查
"""
        
        prompt = f"""
请分析以下{db_type.upper()} SQL文件，检查以下方面的潜在问题：

检查重点：
{chr(10).join(f'- {area}' for area in focus_areas)}

分析深度：{analysis_depth}
{depth_instruction}

文件路径：{file_path}
数据库类型：{db_type}

SQL内容：
```sql
{sql_content}
```

请按照以下格式返回分析结果：

## 问题汇总
[如果没有发现问题，请写"无问题发现"]

## 详细分析
### 1. 语法检查
- 检查SQL语法是否正确
- 检查关键字使用是否正确
- 检查表名、字段名是否规范

### 2. 性能分析
- 检查是否有性能问题
- 检查索引使用是否合理
- 检查查询是否可以优化

### 3. 安全检查
- 检查是否存在SQL注入风险
- 检查权限控制是否合理
- 检查敏感数据是否暴露

### 4. 逻辑分析
- 检查业务逻辑是否合理
- 检查数据一致性是否保证
- 检查事务处理是否正确

### 5. 最佳实践
- 检查是否符合数据库开发规范
- 检查代码可维护性
- 检查注释和文档是否完整

## 修改建议
[针对发现的问题提供具体的修改建议]

{custom_instructions}

要求：直接给出分析结果，不要包含思考过程或推理步骤。
"""
        return prompt
    
    def _parse_ai_result(self, ai_result: str) -> Dict[str, Any]:
        """
        解析AI分析结果
        
        Args:
            ai_result: AI分析结果字符串
            
        Returns:
            解析后的结果字典
        """
        # 简单的结果解析
        issues = []
        
        # 检查是否有明显的错误
        error_indicators = [
            "语法错误", "错误", "异常", "失败", "不存在", "无效", "未定义"
        ]
        
        warning_indicators = [
            "警告", "注意", "建议", "优化", "风险", "问题"
        ]
        
        for indicator in error_indicators:
            if indicator in ai_result:
                issues.append({
                    'type': 'error',
                    'description': f"发现{indicator}相关问题",
                    'details': ai_result
                })
                break
        
        for indicator in warning_indicators:
            if indicator in ai_result:
                issues.append({
                    'type': 'warning',
                    'description': f"发现{indicator}相关问题",
                    'details': ai_result
                })
                break
        
        return {
            'raw_result': ai_result,
            'issues': issues,
            'has_issues': len(issues) > 0
        }
    
    def _generate_report(self, results: List[Dict[str, Any]], 
                        project_id: str, version_path: str) -> Dict[str, Any]:
        """
        生成扫描报告
        
        Args:
            results: 扫描结果列表
            project_id: 项目ID
            version_path: 版本路径
            
        Returns:
            扫描报告
        """
        report = {
            'project_id': project_id,
            'version_path': version_path,
            'scan_time': datetime.now().isoformat(),
            'statistics': self.scan_stats,
            'results': results,
            'summary': {
                'total_files': self.scan_stats['total_files'],
                'scanned_files': self.scan_stats['scanned_files'],
                'error_files': self.scan_stats['error_files'],
                'issues_found': self.scan_stats['issues_found'],
                'success_rate': f"{(self.scan_stats['scanned_files'] / max(self.scan_stats['total_files'], 1)) * 100:.1f}%"
            }
        }
        
        return report
    
    def _output_results(self, report: Dict[str, Any], output_format: str):
        """
        输出扫描结果
        
        Args:
            report: 扫描报告
            output_format: 输出格式
        """
        if output_format == 'console':
            self._output_console(report)
        elif output_format == 'text':
            self._output_text(report)
        elif output_format == 'json':
            self._output_json(report)
        else:
            self._log('error', "不支持的输出格式", output_format=output_format)
    
    def _output_console(self, report: Dict[str, Any]):
        """控制台输出"""
        print("\n" + "="*60)
        print("SQL项目扫描报告")
        print("="*60)
        
        # 基本信息
        print(f"项目ID: {report['project_id']}")
        print(f"版本路径: {report['version_path']}")
        print(f"扫描时间: {report['scan_time']}")
        print()
        
        # 统计信息
        summary = report['summary']
        print("扫描统计:")
        print(f"  总文件数: {summary['total_files']}")
        print(f"  已扫描: {summary['scanned_files']}")
        print(f"  错误文件: {summary['error_files']}")
        print(f"  发现问题: {summary['issues_found']}")
        print(f"  成功率: {summary['success_rate']}")
        print()
        
        # 按数据库类型统计
        if report['statistics']['by_db_type']:
            print("按数据库类型统计:")
            for db_type, stats in report['statistics']['by_db_type'].items():
                print(f"  {db_type}: {stats['scanned_files']}/{stats['total_files']} 文件, 发现 {stats['issues_found']} 个问题")
            print()
        
        # 按版本统计
        if report['statistics']['by_version']:
            print("按版本统计:")
            for version, stats in report['statistics']['by_version'].items():
                print(f"  {version}: {stats['scanned_files']}/{stats['total_files']} 文件, 发现 {stats['issues_found']} 个问题")
            print()
        
        # 显示有问题的文件
        issue_files = [r for r in report['results'] if r.get('ai_analysis', {}).get('has_issues')]
        if issue_files:
            print("问题文件:")
            for result in issue_files[:10]:  # 显示前10个
                file_path = result['file_path']
                db_type = result['db_type']
                version = result['version']
                issues_count = len(result['ai_analysis'].get('issues', []))
                print(f"  - {file_path} ({db_type}, {version}) - {issues_count} 个问题")
            
            if len(issue_files) > 10:
                print(f"  ... 还有 {len(issue_files) - 10} 个问题文件")
            print()
        
        print("="*60)
    
    def _output_text(self, report: Dict[str, Any]):
        """文本文件输出"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sql_scan_report_{report['project_id']}_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("SQL项目扫描报告\n")
            f.write("="*60 + "\n")
            f.write(f"项目ID: {report['project_id']}\n")
            f.write(f"版本路径: {report['version_path']}\n")
            f.write(f"扫描时间: {report['scan_time']}\n\n")
            
            # 统计信息
            summary = report['summary']
            f.write("扫描统计:\n")
            f.write(f"  总文件数: {summary['total_files']}\n")
            f.write(f"  已扫描: {summary['scanned_files']}\n")
            f.write(f"  错误文件: {summary['error_files']}\n")
            f.write(f"  发现问题: {summary['issues_found']}\n")
            f.write(f"  成功率: {summary['success_rate']}\n\n")
            
            # 详细结果
            f.write("详细结果:\n")
            for result in report['results']:
                f.write(f"\n文件: {result['file_path']}\n")
                f.write(f"数据库类型: {result['db_type']}\n")
                f.write(f"版本: {result['version']}\n")
                f.write(f"状态: {result['status']}\n")
                
                if result.get('ai_analysis'):
                    ai_result = result['ai_analysis']
                    if ai_result.get('has_issues'):
                        f.write(f"发现问题: {len(ai_result.get('issues', []))} 个\n")
                    
                    # 写入AI分析结果
                    f.write("AI分析结果:\n")
                    f.write(ai_result.get('raw_result', '无分析结果'))
                    f.write("\n")
        
        print(f"报告已保存到: {filename}")
    
    def _output_json(self, report: Dict[str, Any]):
        """JSON格式输出"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sql_scan_report_{report['project_id']}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"报告已保存到: {filename}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SQL项目扫描器")
    parser.add_argument('--project-id', required=True, help='项目ID')
    parser.add_argument('--version-path', required=True, help='版本路径（支持通配符）')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--db-type', choices=['mysql', 'oracle', 'db2'], help='数据库类型过滤')
    parser.add_argument('--output', choices=['console', 'text', 'json'], default='console', help='输出格式')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    # AI相关参数
    parser.add_argument('--model', help='自定义AI模型名称')
    parser.add_argument('--enable-thinking', action='store_true', help='启用AI思考过程')
    parser.add_argument('--temperature', type=float, default=0.7, help='AI温度参数 (0.0-2.0)')
    parser.add_argument('--top-p', type=float, default=0.9, help='AI top_p参数 (0.0-1.0)')
    parser.add_argument('--max-tokens', type=int, default=2000, help='AI最大输出令牌数')
    parser.add_argument('--analysis-depth', choices=['quick', 'standard', 'deep'], default='standard', 
                       help='分析深度: quick(快速), standard(标准), deep(深度)')
    parser.add_argument('--focus-areas', nargs='+', 
                       help='重点关注领域，如: 语法错误 性能问题 安全风险')
    parser.add_argument('--branch', help='指定扫描分支（默认使用默认分支）')
    parser.add_argument('--custom-instructions', help='自定义分析指令')
    
    args = parser.parse_args()
    
    # 创建扫描器
    scanner = SQLProjectScanner(args.config)
    
    # 构建AI参数
    ai_kwargs = {}
    if args.model:
        ai_kwargs['custom_model'] = args.model
    if args.enable_thinking:
        ai_kwargs['enable_thinking'] = True
    if args.temperature != 0.7:
        ai_kwargs['temperature'] = args.temperature
    if args.top_p != 0.9:
        ai_kwargs['top_p'] = args.top_p
    if args.max_tokens != 2000:
        ai_kwargs['max_tokens'] = args.max_tokens
    if args.analysis_depth != 'standard':
        ai_kwargs['analysis_depth'] = args.analysis_depth
    if args.focus_areas:
        ai_kwargs['focus_areas'] = args.focus_areas
    if args.custom_instructions:
        ai_kwargs['custom_instructions'] = args.custom_instructions
    
    # 执行扫描
    result = scanner.scan_project(
        project_id=args.project_id,
        version_path=args.version_path,
        db_type=args.db_type,
        output_format=args.output,
        branch=args.branch,
        **ai_kwargs
    )
    
    if result.get('error'):
        print(f"扫描失败: {result['error']}")
        sys.exit(1)
    else:
        print("扫描完成")
        sys.exit(0)

if __name__ == "__main__":
    main()
