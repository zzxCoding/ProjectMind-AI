#!/usr/bin/env python3
"""
性能监控脚本
监控脚本执行性能，生成性能报告和趋势分析
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import statistics

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.config_loader import setup_environment
setup_environment()
from shared.utils import setup_logging, parse_arguments, format_timestamp, exit_with_error, exit_with_success
from shared.database_client import DatabaseClient
from shared.ollama_client import OllamaClient

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.db_client = DatabaseClient()
        self.ollama_client = OllamaClient()
    
    def calculate_execution_metrics(self, executions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算执行指标
        
        Args:
            executions: 执行记录列表
            
        Returns:
            性能指标
        """
        if not executions:
            return {}
        
        metrics = {
            'total_executions': len(executions),
            'success_count': 0,
            'failed_count': 0,
            'running_count': 0,
            'execution_times': [],
            'success_rate': 0,
            'failure_rate': 0,
            'avg_execution_time': 0,
            'median_execution_time': 0,
            'min_execution_time': 0,
            'max_execution_time': 0,
            'std_execution_time': 0
        }
        
        execution_times = []
        
        for execution in executions:
            status = execution.get('status', '').upper()
            
            if status == 'SUCCESS':
                metrics['success_count'] += 1
            elif status == 'FAILED':
                metrics['failed_count'] += 1
            elif status == 'RUNNING':
                metrics['running_count'] += 1
            
            # 计算执行时间
            start_time = execution.get('start_time')
            end_time = execution.get('end_time')
            
            if start_time and end_time:
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time)
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time)
                
                duration = (end_time - start_time).total_seconds()
                if duration > 0:
                    execution_times.append(duration)
        
        # 计算比率
        if metrics['total_executions'] > 0:
            metrics['success_rate'] = (metrics['success_count'] / metrics['total_executions']) * 100
            metrics['failure_rate'] = (metrics['failed_count'] / metrics['total_executions']) * 100
        
        # 计算执行时间统计
        if execution_times:
            metrics['execution_times'] = execution_times
            metrics['avg_execution_time'] = statistics.mean(execution_times)
            metrics['median_execution_time'] = statistics.median(execution_times)
            metrics['min_execution_time'] = min(execution_times)
            metrics['max_execution_time'] = max(execution_times)
            
            if len(execution_times) > 1:
                metrics['std_execution_time'] = statistics.stdev(execution_times)
        
        return metrics
    
    def analyze_script_performance(self, script_id: int, days: int = 30) -> Dict[str, Any]:
        """
        分析单个脚本的性能
        
        Args:
            script_id: 脚本ID
            days: 分析时间范围（天）
            
        Returns:
            脚本性能分析结果
        """
        self.logger.info(f"分析脚本ID {script_id} 的性能（最近{days}天）")
        
        # 获取脚本信息
        script_info = self.db_client.get_script_by_id(script_id)
        if not script_info:
            return {'error': f'未找到脚本ID {script_id}'}
        
        # 获取执行记录
        executions = self.db_client.get_executions_by_script(script_id, 1000)
        
        # 过滤时间范围
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_executions = [
            e for e in executions 
            if e['start_time'] and e['start_time'] > cutoff_date
        ]
        
        # 计算性能指标
        metrics = self.calculate_execution_metrics(filtered_executions)
        
        # 构建结果
        result = {
            'script_id': script_id,
            'script_name': script_info['name'],
            'script_description': script_info['description'],
            'analysis_period': f"最近{days}天",
            'analysis_time': format_timestamp(),
            'metrics': metrics,
            'performance_grade': self._calculate_performance_grade(metrics),
            'recommendations': self._generate_recommendations(metrics)
        }
        
        return result
    
    def analyze_system_performance(self, days: int = 30) -> Dict[str, Any]:
        """
        分析整体系统性能
        
        Args:
            days: 分析时间范围（天）
            
        Returns:
            系统性能分析结果
        """
        self.logger.info(f"分析系统整体性能（最近{days}天）")
        
        # 获取系统统计信息
        system_stats = self.db_client.get_execution_stats(days)
        
        # 获取最近的执行记录
        recent_executions = self.db_client.get_recent_executions(1000)
        
        # 过滤时间范围
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_executions = [
            e for e in recent_executions 
            if e['start_time'] and e['start_time'] > cutoff_date
        ]
        
        # 计算整体指标
        overall_metrics = self.calculate_execution_metrics(filtered_executions)
        
        # 按脚本分组分析
        script_performance = defaultdict(list)
        for execution in filtered_executions:
            script_id = execution['script_id']
            script_performance[script_id].append(execution)
        
        # 计算每个脚本的性能
        script_metrics = {}
        for script_id, executions in script_performance.items():
            metrics = self.calculate_execution_metrics(executions)
            script_info = self.db_client.get_script_by_id(script_id)
            script_name = script_info['name'] if script_info else f"Script_{script_id}"
            
            script_metrics[script_name] = {
                'script_id': script_id,
                'metrics': metrics
            }
        
        # 识别性能问题脚本
        problematic_scripts = self._identify_problematic_scripts(script_metrics)
        
        # 构建结果
        result = {
            'analysis_period': f"最近{days}天",
            'analysis_time': format_timestamp(),
            'system_stats': system_stats,
            'overall_metrics': overall_metrics,
            'script_count': len(script_metrics),
            'script_metrics': script_metrics,
            'problematic_scripts': problematic_scripts,
            'system_health': self._calculate_system_health(overall_metrics),
            'recommendations': self._generate_system_recommendations(overall_metrics, problematic_scripts)
        }
        
        return result
    
    def generate_trend_analysis(self, script_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """
        生成趋势分析
        
        Args:
            script_id: 脚本ID，为None时分析整体趋势
            days: 分析时间范围
            
        Returns:
            趋势分析结果
        """
        self.logger.info(f"生成趋势分析（最近{days}天）")
        
        if script_id:
            executions = self.db_client.get_executions_by_script(script_id, 1000)
            analysis_target = f"脚本ID {script_id}"
        else:
            executions = self.db_client.get_recent_executions(1000)
            analysis_target = "整体系统"
        
        # 过滤时间范围
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_executions = [
            e for e in executions 
            if e['start_time'] and e['start_time'] > cutoff_date
        ]
        
        # 按日期分组
        daily_stats = self._group_by_date(filtered_executions)
        
        # 计算趋势
        trend_data = self._calculate_trends(daily_stats)
        
        result = {
            'analysis_target': analysis_target,
            'analysis_period': f"最近{days}天",
            'analysis_time': format_timestamp(),
            'daily_stats': daily_stats,
            'trends': trend_data,
            'insights': self._generate_trend_insights(trend_data)
        }
        
        return result
    
    def _group_by_date(self, executions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """按日期分组执行记录"""
        daily_data = defaultdict(lambda: {
            'total': 0,
            'success': 0,
            'failed': 0,
            'running': 0,
            'execution_times': []
        })
        
        for execution in executions:
            start_time = execution.get('start_time')
            if not start_time:
                continue
            
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            
            date_str = start_time.strftime('%Y-%m-%d')
            status = execution.get('status', '').upper()
            
            daily_data[date_str]['total'] += 1
            
            if status == 'SUCCESS':
                daily_data[date_str]['success'] += 1
            elif status == 'FAILED':
                daily_data[date_str]['failed'] += 1
            elif status == 'RUNNING':
                daily_data[date_str]['running'] += 1
            
            # 计算执行时间
            end_time = execution.get('end_time')
            if start_time and end_time:
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time)
                
                duration = (end_time - start_time).total_seconds()
                if duration > 0:
                    daily_data[date_str]['execution_times'].append(duration)
        
        # 计算每日的成功率和平均执行时间
        for date, data in daily_data.items():
            if data['total'] > 0:
                data['success_rate'] = (data['success'] / data['total']) * 100
            else:
                data['success_rate'] = 0
            
            if data['execution_times']:
                data['avg_execution_time'] = statistics.mean(data['execution_times'])
            else:
                data['avg_execution_time'] = 0
        
        return dict(daily_data)
    
    def _calculate_trends(self, daily_stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """计算趋势数据"""
        if len(daily_stats) < 2:
            return {'error': '数据点不足，无法计算趋势'}
        
        dates = sorted(daily_stats.keys())
        success_rates = [daily_stats[date]['success_rate'] for date in dates]
        execution_counts = [daily_stats[date]['total'] for date in dates]
        avg_times = [daily_stats[date]['avg_execution_time'] for date in dates if daily_stats[date]['avg_execution_time'] > 0]
        
        trends = {}
        
        # 成功率趋势
        if len(success_rates) >= 2:
            trends['success_rate_trend'] = self._calculate_linear_trend(success_rates)
        
        # 执行数量趋势
        if len(execution_counts) >= 2:
            trends['execution_count_trend'] = self._calculate_linear_trend(execution_counts)
        
        # 执行时间趋势
        if len(avg_times) >= 2:
            trends['execution_time_trend'] = self._calculate_linear_trend(avg_times)
        
        return trends
    
    def _calculate_linear_trend(self, values: List[float]) -> Dict[str, Any]:
        """计算线性趋势"""
        if len(values) < 2:
            return {'slope': 0, 'direction': 'stable'}
        
        n = len(values)
        x_values = list(range(n))
        
        # 计算线性回归斜率
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(values)
        
        numerator = sum((x_values[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        
        # 判断趋势方向
        if abs(slope) < 0.01:
            direction = 'stable'
        elif slope > 0:
            direction = 'increasing'
        else:
            direction = 'decreasing'
        
        return {
            'slope': slope,
            'direction': direction,
            'change_rate': abs(slope) / y_mean * 100 if y_mean != 0 else 0
        }
    
    def _calculate_performance_grade(self, metrics: Dict[str, Any]) -> str:
        """计算性能等级"""
        success_rate = metrics.get('success_rate', 0)
        avg_time = metrics.get('avg_execution_time', 0)
        
        if success_rate >= 95 and avg_time < 10:
            return 'A'
        elif success_rate >= 90 and avg_time < 30:
            return 'B'
        elif success_rate >= 80 and avg_time < 60:
            return 'C'
        elif success_rate >= 70:
            return 'D'
        else:
            return 'F'
    
    def _calculate_system_health(self, metrics: Dict[str, Any]) -> str:
        """计算系统健康度"""
        success_rate = metrics.get('success_rate', 0)
        
        if success_rate >= 95:
            return 'Excellent'
        elif success_rate >= 85:
            return 'Good'
        elif success_rate >= 70:
            return 'Fair'
        else:
            return 'Poor'
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """生成性能建议"""
        recommendations = []
        
        success_rate = metrics.get('success_rate', 0)
        avg_time = metrics.get('avg_execution_time', 0)
        std_time = metrics.get('std_execution_time', 0)
        
        if success_rate < 80:
            recommendations.append("成功率偏低，建议检查脚本逻辑和错误处理")
        
        if avg_time > 60:
            recommendations.append("平均执行时间较长，建议优化脚本性能")
        
        if std_time > avg_time * 0.5 and avg_time > 0:
            recommendations.append("执行时间波动较大，建议检查资源竞争问题")
        
        if not recommendations:
            recommendations.append("性能表现良好，无需特别优化")
        
        return recommendations
    
    def _generate_system_recommendations(self, metrics: Dict[str, Any], problematic_scripts: List[Dict]) -> List[str]:
        """生成系统级建议"""
        recommendations = []
        
        success_rate = metrics.get('success_rate', 0)
        
        if success_rate < 85:
            recommendations.append("系统整体成功率偏低，需要重点关注失败脚本")
        
        if len(problematic_scripts) > 0:
            recommendations.append(f"发现{len(problematic_scripts)}个问题脚本，建议优先处理")
        
        if metrics.get('avg_execution_time', 0) > 30:
            recommendations.append("系统平均执行时间较长，建议整体性能优化")
        
        return recommendations
    
    def _identify_problematic_scripts(self, script_metrics: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """识别问题脚本"""
        problematic = []
        
        for script_name, data in script_metrics.items():
            metrics = data['metrics']
            issues = []
            
            if metrics.get('success_rate', 0) < 70:
                issues.append('低成功率')
            
            if metrics.get('avg_execution_time', 0) > 120:
                issues.append('执行时间过长')
            
            if metrics.get('failure_rate', 0) > 30:
                issues.append('高失败率')
            
            if issues:
                problematic.append({
                    'script_name': script_name,
                    'script_id': data['script_id'],
                    'issues': issues,
                    'metrics': metrics
                })
        
        return problematic
    
    def _generate_trend_insights(self, trends: Dict[str, Any]) -> List[str]:
        """生成趋势洞察"""
        insights = []
        
        success_trend = trends.get('success_rate_trend', {})
        if success_trend.get('direction') == 'decreasing':
            insights.append(f"成功率呈下降趋势，下降幅度{success_trend.get('change_rate', 0):.1f}%")
        elif success_trend.get('direction') == 'increasing':
            insights.append(f"成功率呈上升趋势，改善幅度{success_trend.get('change_rate', 0):.1f}%")
        
        count_trend = trends.get('execution_count_trend', {})
        if count_trend.get('direction') == 'increasing':
            insights.append("脚本执行频率呈上升趋势")
        elif count_trend.get('direction') == 'decreasing':
            insights.append("脚本执行频率呈下降趋势")
        
        time_trend = trends.get('execution_time_trend', {})
        if time_trend.get('direction') == 'increasing':
            insights.append("平均执行时间呈增长趋势，可能存在性能退化")
        elif time_trend.get('direction') == 'decreasing':
            insights.append("平均执行时间呈改善趋势")
        
        return insights

def main():
    """主函数"""
    parser = parse_arguments("性能监控脚本")
    parser.add_argument('--script-id', type=int, help='分析特定脚本的性能')
    parser.add_argument('--system', action='store_true', help='分析系统整体性能')
    parser.add_argument('--trend', action='store_true', help='生成趋势分析')
    parser.add_argument('--days', type=int, default=30, help='分析时间范围（天）')
    parser.add_argument('--output-format', choices=['json', 'text'], default='text', help='输出格式')
    parser.add_argument('--use-ai', action='store_true', help='使用AI增强分析')
    
    args = parser.parse_args()
    
    # 设置日志级别
    logger = setup_logging(args.log_level)
    
    monitor = PerformanceMonitor()
    
    try:
        if args.script_id:
            # 分析特定脚本
            result = monitor.analyze_script_performance(args.script_id, args.days)
        elif args.system:
            # 分析系统性能
            result = monitor.analyze_system_performance(args.days)
        elif args.trend:
            # 趋势分析
            script_id = args.script_id if args.script_id else None
            result = monitor.generate_trend_analysis(script_id, args.days)
        else:
            exit_with_error("请指定分析类型: --script-id, --system, 或 --trend")
        
        # AI增强分析
        if args.use_ai and monitor.ollama_client.health_check():
            logger.info("使用AI进行性能分析增强...")
            try:
                ai_analysis = monitor.ollama_client.analyze_performance_data(result)
                result['ai_insights'] = ai_analysis
            except Exception as e:
                logger.warning(f"AI分析失败: {e}")
        
        # 输出结果
        if args.output_format == 'json':
            import json
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            # 文本格式输出
            if 'script_name' in result:
                # 单脚本分析
                print(f"=== 脚本性能分析: {result['script_name']} ===")
                metrics = result.get('metrics', {})
                print(f"性能等级: {result.get('performance_grade', 'N/A')}")
                print(f"成功率: {metrics.get('success_rate', 0):.1f}%")
                print(f"平均执行时间: {metrics.get('avg_execution_time', 0):.2f}秒")
                print(f"总执行次数: {metrics.get('total_executions', 0)}")
                
                print("\n建议:")
                for rec in result.get('recommendations', []):
                    print(f"  - {rec}")
            
            elif 'system_health' in result:
                # 系统分析
                print(f"=== 系统性能分析 ===")
                print(f"系统健康度: {result.get('system_health', 'N/A')}")
                metrics = result.get('overall_metrics', {})
                print(f"整体成功率: {metrics.get('success_rate', 0):.1f}%")
                print(f"脚本数量: {result.get('script_count', 0)}")
                
                problematic = result.get('problematic_scripts', [])
                if problematic:
                    print(f"\n问题脚本 ({len(problematic)}个):")
                    for script in problematic[:5]:  # 只显示前5个
                        print(f"  - {script['script_name']}: {', '.join(script['issues'])}")
            
            elif 'trends' in result:
                # 趋势分析
                print(f"=== 趋势分析: {result['analysis_target']} ===")
                insights = result.get('insights', [])
                if insights:
                    print("关键趋势:")
                    for insight in insights:
                        print(f"  - {insight}")
                else:
                    print("未发现明显趋势变化")
            
            # AI洞察
            if 'ai_insights' in result:
                print(f"\n=== AI分析洞察 ===")
                print(result['ai_insights'])
        
        exit_with_success()
        
    except Exception as e:
        exit_with_error(f"性能分析失败: {e}")

if __name__ == "__main__":
    main()