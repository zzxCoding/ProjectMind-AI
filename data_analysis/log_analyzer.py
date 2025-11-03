#!/usr/bin/env python3
"""
日志分析脚本
分析脚本执行日志，提取关键信息和异常
"""

import sys
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.config_loader import config, get_log_path, setup_environment
from shared.utils import setup_logging, parse_arguments, format_timestamp, exit_with_error, exit_with_success
from shared.database_client import DatabaseClient
from shared.ollama_client import OllamaClient

# 设置环境
setup_environment()

class LogAnalyzer:
    """日志分析器"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.db_client = DatabaseClient()
        self.ollama_client = OllamaClient()
        
        # 日志级别模式
        self.log_level_patterns = {
            'ERROR': re.compile(r'\[ERROR\]|\bERROR\b|\bFAILED\b', re.IGNORECASE),
            'WARNING': re.compile(r'\[WARNING\]|\bWARNING\b|\bWARN\b', re.IGNORECASE),
            'INFO': re.compile(r'\[INFO\]|\bINFO\b', re.IGNORECASE),
            'DEBUG': re.compile(r'\[DEBUG\]|\bDEBUG\b', re.IGNORECASE)
        }
        
        # 异常模式
        self.exception_patterns = {
            'connection': re.compile(r'connection.*(?:refused|timeout|failed)', re.IGNORECASE),
            'permission': re.compile(r'permission.*denied', re.IGNORECASE),
            'file_not_found': re.compile(r'(?:file|directory).*not found', re.IGNORECASE),
            'timeout': re.compile(r'timeout|timed out', re.IGNORECASE),
            'memory': re.compile(r'out of memory|memory error', re.IGNORECASE),
            'syntax': re.compile(r'syntax error|invalid syntax', re.IGNORECASE)
        }
    
    def read_log_file(self, log_path: str) -> List[str]:
        """
        读取日志文件
        
        Args:
            log_path: 日志文件路径
            
        Returns:
            日志行列表
        """
        try:
            # 使用配置加载器获取正确的日志路径
            log_path = get_log_path(log_path)
            
            if not os.path.exists(log_path):
                self.logger.error(f"日志文件不存在: {log_path}")
                return []
            
            with open(log_path, 'r', encoding='utf-8') as f:
                return f.readlines()
        except Exception as e:
            self.logger.error(f"读取日志文件失败: {e}")
            return []
    
    def analyze_log_levels(self, log_lines: List[str]) -> Dict[str, int]:
        """
        分析日志级别分布
        
        Args:
            log_lines: 日志行列表
            
        Returns:
            日志级别统计
        """
        level_counts = Counter()
        
        for line in log_lines:
            line = line.strip()
            if not line:
                continue
                
            for level, pattern in self.log_level_patterns.items():
                if pattern.search(line):
                    level_counts[level] += 1
                    break
            else:
                level_counts['OTHER'] += 1
        
        return dict(level_counts)
    
    def detect_exceptions(self, log_lines: List[str]) -> Dict[str, List[str]]:
        """
        检测异常和错误
        
        Args:
            log_lines: 日志行列表
            
        Returns:
            异常类型和对应的日志行
        """
        exceptions = defaultdict(list)
        
        for i, line in enumerate(log_lines, 1):
            line = line.strip()
            if not line:
                continue
                
            for exception_type, pattern in self.exception_patterns.items():
                if pattern.search(line):
                    exceptions[exception_type].append({
                        'line_number': i,
                        'content': line,
                        'timestamp': self._extract_timestamp(line)
                    })
        
        return dict(exceptions)
    
    def _extract_timestamp(self, line: str) -> Optional[str]:
        """
        从日志行提取时间戳
        
        Args:
            line: 日志行
            
        Returns:
            时间戳字符串
        """
        timestamp_patterns = [
            re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'),
            re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})'),
            re.compile(r'(\d{2}:\d{2}:\d{2})')
        ]
        
        for pattern in timestamp_patterns:
            match = pattern.search(line)
            if match:
                return match.group(1)
        
        return None
    
    def calculate_execution_time(self, log_lines: List[str]) -> Optional[float]:
        """
        计算执行时间
        
        Args:
            log_lines: 日志行列表
            
        Returns:
            执行时间（秒）
        """
        timestamps = []
        
        for line in log_lines:
            timestamp = self._extract_timestamp(line)
            if timestamp:
                try:
                    # 尝试不同的时间格式
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S']:
                        try:
                            dt = datetime.strptime(timestamp, fmt)
                            timestamps.append(dt)
                            break
                        except ValueError:
                            continue
                except ValueError:
                    continue
        
        if len(timestamps) >= 2:
            duration = (timestamps[-1] - timestamps[0]).total_seconds()
            return duration
        
        return None
    
    def generate_summary(self, analysis_result: Dict[str, Any]) -> str:
        """
        生成分析摘要
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            摘要文本
        """
        summary_parts = []
        
        # 基本信息
        total_lines = analysis_result.get('total_lines', 0)
        execution_time = analysis_result.get('execution_time')
        summary_parts.append(f"日志总行数: {total_lines}")
        
        if execution_time:
            summary_parts.append(f"执行时间: {execution_time:.2f}秒")
        
        # 日志级别分布
        log_levels = analysis_result.get('log_levels', {})
        if log_levels:
            summary_parts.append("日志级别分布:")
            for level, count in log_levels.items():
                summary_parts.append(f"  {level}: {count}")
        
        # 异常统计
        exceptions = analysis_result.get('exceptions', {})
        if exceptions:
            summary_parts.append("发现的异常:")
            for exc_type, exc_list in exceptions.items():
                summary_parts.append(f"  {exc_type}: {len(exc_list)}个")
        
        return '\n'.join(summary_parts)
    
    def analyze_single_log(self, log_path: str, use_ai: bool = False) -> Dict[str, Any]:
        """
        分析单个日志文件
        
        Args:
            log_path: 日志文件路径
            use_ai: 是否使用AI分析
            
        Returns:
            分析结果
        """
        self.logger.info(f"开始分析日志文件: {log_path}")
        
        log_lines = self.read_log_file(log_path)
        if not log_lines:
            return {'error': '无法读取日志文件或文件为空'}
        
        # 基础分析
        result = {
            'log_path': log_path,
            'total_lines': len(log_lines),
            'analysis_time': format_timestamp(),
            'log_levels': self.analyze_log_levels(log_lines),
            'exceptions': self.detect_exceptions(log_lines),
            'execution_time': self.calculate_execution_time(log_lines)
        }
        
        # AI增强分析
        if use_ai and self.ollama_client.health_check():
            self.logger.info("使用AI进行深度分析...")
            try:
                ai_analysis = self.ollama_client.analyze_logs(log_lines)
                result['ai_analysis'] = ai_analysis
            except Exception as e:
                self.logger.warning(f"AI分析失败: {e}")
                result['ai_analysis'] = "AI分析不可用"
        
        # 生成摘要
        result['summary'] = self.generate_summary(result)
        
        self.logger.info("日志分析完成")
        return result
    
    def analyze_execution_logs(self, script_id: int, limit: int = 10, use_ai: bool = False) -> List[Dict[str, Any]]:
        """
        分析脚本的执行日志
        
        Args:
            script_id: 脚本ID
            limit: 分析的执行记录数量
            use_ai: 是否使用AI分析
            
        Returns:
            分析结果列表
        """
        self.logger.info(f"开始分析脚本ID {script_id} 的执行日志")
        
        # 获取执行记录
        executions = self.db_client.get_executions_by_script(script_id, limit)
        if not executions:
            return []
        
        results = []
        for execution in executions:
            if execution['log_path']:
                analysis = self.analyze_single_log(execution['log_path'], use_ai)
                analysis['execution_id'] = execution['id']
                analysis['execution_status'] = execution['status']
                analysis['start_time'] = execution['start_time']
                results.append(analysis)
        
        return results
    
    def batch_analyze_recent_logs(self, days: int = 7, use_ai: bool = False) -> Dict[str, Any]:
        """
        批量分析最近的日志
        
        Args:
            days: 分析最近几天的日志
            use_ai: 是否使用AI分析
            
        Returns:
            批量分析结果
        """
        self.logger.info(f"开始批量分析最近{days}天的日志")
        
        # 获取最近的执行记录
        recent_executions = self.db_client.get_recent_executions(100)
        
        # 过滤时间范围
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_executions = [
            e for e in recent_executions 
            if e['start_time'] and e['start_time'] > cutoff_date
        ]
        
        results = {
            'analysis_time': format_timestamp(),
            'time_range': f"最近{days}天",
            'total_executions': len(filtered_executions),
            'log_analyses': [],
            'summary_stats': {
                'total_errors': 0,
                'total_warnings': 0,
                'common_exceptions': Counter(),
                'success_rate': 0
            }
        }
        
        # 分析每个日志
        for execution in filtered_executions:
            if execution['log_path']:
                analysis = self.analyze_single_log(execution['log_path'], use_ai)
                analysis['execution_info'] = execution
                results['log_analyses'].append(analysis)
                
                # 更新统计信息
                if 'log_levels' in analysis:
                    results['summary_stats']['total_errors'] += analysis['log_levels'].get('ERROR', 0)
                    results['summary_stats']['total_warnings'] += analysis['log_levels'].get('WARNING', 0)
                
                if 'exceptions' in analysis:
                    for exc_type, exc_list in analysis['exceptions'].items():
                        results['summary_stats']['common_exceptions'][exc_type] += len(exc_list)
        
        # 计算成功率
        success_count = sum(1 for e in filtered_executions if e['status'] == 'SUCCESS')
        if filtered_executions:
            results['summary_stats']['success_rate'] = success_count / len(filtered_executions) * 100
        
        self.logger.info("批量分析完成")
        return results

def main():
    """主函数"""
    parser = parse_arguments("日志分析脚本")
    parser.add_argument('--log-path', help='单个日志文件路径')
    parser.add_argument('--script-id', type=int, help='要分析的脚本ID')
    parser.add_argument('--batch', action='store_true', help='批量分析最近的日志')
    parser.add_argument('--days', type=int, default=7, help='批量分析的天数范围')
    parser.add_argument('--limit', type=int, default=10, help='分析的执行记录数量限制')
    parser.add_argument('--use-ai', action='store_true', help='使用AI进行深度分析')
    parser.add_argument('--output-format', choices=['json', 'text'], default='text', help='输出格式')
    
    args = parser.parse_args()
    
    # 设置日志级别
    logger = setup_logging(args.log_level)
    
    analyzer = LogAnalyzer()
    
    try:
        if args.log_path:
            # 分析单个日志文件
            result = analyzer.analyze_single_log(args.log_path, args.use_ai)
            
        elif args.script_id:
            # 分析脚本的执行日志
            results = analyzer.analyze_execution_logs(args.script_id, args.limit, args.use_ai)
            result = {
                'script_id': args.script_id,
                'analyses': results,
                'total_analyzed': len(results)
            }
            
        elif args.batch:
            # 批量分析
            result = analyzer.batch_analyze_recent_logs(args.days, args.use_ai)
            
        else:
            exit_with_error("请指定要分析的日志: --log-path, --script-id, 或 --batch")
        
        # 输出结果
        if args.output_format == 'json':
            import json
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            if 'summary' in result:
                print(result['summary'])
            elif 'analyses' in result:
                print(f"脚本ID {result['script_id']} 的日志分析结果:")
                for i, analysis in enumerate(result['analyses'], 1):
                    print(f"\n=== 执行记录 {i} ===")
                    print(analysis.get('summary', '无摘要'))
            else:
                print("批量分析结果:")
                stats = result.get('summary_stats', {})
                print(f"总执行次数: {result.get('total_executions', 0)}")
                print(f"成功率: {stats.get('success_rate', 0):.1f}%")
                print(f"总错误数: {stats.get('total_errors', 0)}")
                print(f"总警告数: {stats.get('total_warnings', 0)}")
                
                if stats.get('common_exceptions'):
                    print("常见异常:")
                    for exc_type, count in stats['common_exceptions'].most_common(5):
                        print(f"  {exc_type}: {count}")
        
        exit_with_success()
        
    except Exception as e:
        exit_with_error(f"日志分析失败: {e}")

if __name__ == "__main__":
    main()