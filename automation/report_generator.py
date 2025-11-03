#!/usr/bin/env python3
"""
报告生成脚本
生成各种格式的系统运行报告
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

# 动态获取项目根目录
project_root = Path(__file__).parent.parent.absolute()
sys.path.append(str(project_root))

# 自动检测基础路径
if os.path.exists('/app/logs'):
    base_path = '/app'  # 容器环境
else:
    base_path = str(Path(__file__).parent.parent.parent.absolute())  # 本地环境
from shared.utils import setup_logging, parse_arguments, format_timestamp, exit_with_error, exit_with_success
from shared.database_client import DatabaseClient
from shared.ollama_client import OllamaClient

class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.db_client = DatabaseClient()
        self.ollama_client = OllamaClient()
    
    def generate_daily_report(self, target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        生成日报
        
        Args:
            target_date: 目标日期，默认为昨天
            
        Returns:
            日报数据
        """
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
        
        start_time = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        
        self.logger.info(f"生成日报: {start_time.strftime('%Y-%m-%d')}")
        
        # 获取当日执行记录
        all_executions = self.db_client.get_recent_executions(1000)
        daily_executions = [
            e for e in all_executions
            if e['start_time'] and start_time <= e['start_time'] < end_time
        ]
        
        # 基本统计
        stats = self._calculate_daily_stats(daily_executions)
        
        # 脚本执行排行
        script_ranking = self._get_script_ranking(daily_executions)
        
        # 错误分析
        error_analysis = self._analyze_daily_errors(daily_executions)
        
        # 性能分析
        performance_analysis = self._analyze_daily_performance(daily_executions)
        
        report = {
            'report_type': 'daily',
            'date': start_time.strftime('%Y-%m-%d'),
            'generated_at': format_timestamp(),
            'summary': {
                'total_executions': len(daily_executions),
                'success_rate': stats['success_rate'],
                'avg_execution_time': stats['avg_execution_time'],
                'unique_scripts': len(set(e['script_id'] for e in daily_executions))
            },
            'statistics': stats,
            'script_ranking': script_ranking,
            'error_analysis': error_analysis,
            'performance_analysis': performance_analysis,
            'recommendations': self._generate_daily_recommendations(stats, error_analysis, performance_analysis)
        }
        
        return report
    
    def generate_weekly_report(self, target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        生成周报
        
        Args:
            target_date: 目标日期，默认为上周
            
        Returns:
            周报数据
        """
        if target_date is None:
            target_date = datetime.now() - timedelta(days=7)
        
        # 获取周的开始和结束时间
        days_since_monday = target_date.weekday()
        start_time = target_date - timedelta(days=days_since_monday)
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=7)
        
        self.logger.info(f"生成周报: {start_time.strftime('%Y-%m-%d')} 到 {(end_time - timedelta(days=1)).strftime('%Y-%m-%d')}")
        
        # 获取周内执行记录
        all_executions = self.db_client.get_recent_executions(5000)
        weekly_executions = [
            e for e in all_executions
            if e['start_time'] and start_time <= e['start_time'] < end_time
        ]
        
        # 按日分组统计
        daily_breakdown = self._group_executions_by_day(weekly_executions, start_time, 7)
        
        # 周统计
        weekly_stats = self._calculate_weekly_stats(weekly_executions)
        
        # 趋势分析
        trend_analysis = self._analyze_weekly_trends(daily_breakdown)
        
        # 脚本使用分析
        script_usage = self._analyze_weekly_script_usage(weekly_executions)
        
        # 问题识别
        issues = self._identify_weekly_issues(weekly_executions, daily_breakdown)
        
        report = {
            'report_type': 'weekly',
            'week_start': start_time.strftime('%Y-%m-%d'),
            'week_end': (end_time - timedelta(days=1)).strftime('%Y-%m-%d'),
            'generated_at': format_timestamp(),
            'summary': {
                'total_executions': len(weekly_executions),
                'success_rate': weekly_stats['success_rate'],
                'avg_daily_executions': len(weekly_executions) / 7,
                'active_scripts': len(set(e['script_id'] for e in weekly_executions))
            },
            'daily_breakdown': daily_breakdown,
            'weekly_statistics': weekly_stats,
            'trend_analysis': trend_analysis,
            'script_usage': script_usage,
            'issues_identified': issues,
            'recommendations': self._generate_weekly_recommendations(trend_analysis, script_usage, issues)
        }
        
        return report
    
    def generate_monthly_report(self, target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        生成月报
        
        Args:
            target_date: 目标日期，默认为上个月
            
        Returns:
            月报数据
        """
        if target_date is None:
            target_date = datetime.now().replace(day=1) - timedelta(days=1)  # 上个月最后一天
        
        # 获取月的开始和结束时间
        start_time = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_time.month == 12:
            end_time = start_time.replace(year=start_time.year + 1, month=1)
        else:
            end_time = start_time.replace(month=start_time.month + 1)
        
        self.logger.info(f"生成月报: {start_time.strftime('%Y-%m')}")
        
        # 获取月内执行记录
        all_executions = self.db_client.get_recent_executions(10000)
        monthly_executions = [
            e for e in all_executions
            if e['start_time'] and start_time <= e['start_time'] < end_time
        ]
        
        # 月统计
        monthly_stats = self._calculate_monthly_stats(monthly_executions)
        
        # 按周分组分析
        weekly_breakdown = self._group_executions_by_week(monthly_executions, start_time)
        
        # 脚本健康度分析
        script_health = self._analyze_script_health(monthly_executions)
        
        # 系统性能趋势
        performance_trends = self._analyze_monthly_performance_trends(monthly_executions)
        
        # 容量规划建议
        capacity_planning = self._generate_capacity_planning(monthly_stats, performance_trends)
        
        report = {
            'report_type': 'monthly',
            'month': start_time.strftime('%Y-%m'),
            'generated_at': format_timestamp(),
            'summary': {
                'total_executions': len(monthly_executions),
                'success_rate': monthly_stats['success_rate'],
                'avg_daily_executions': len(monthly_executions) / (end_time - start_time).days,
                'total_scripts': len(set(e['script_id'] for e in monthly_executions)),
                'busiest_day': monthly_stats.get('busiest_day'),
                'peak_executions': monthly_stats.get('peak_executions', 0)
            },
            'monthly_statistics': monthly_stats,
            'weekly_breakdown': weekly_breakdown,
            'script_health': script_health,
            'performance_trends': performance_trends,
            'capacity_planning': capacity_planning,
            'recommendations': self._generate_monthly_recommendations(monthly_stats, script_health, performance_trends)
        }
        
        return report
    
    def generate_custom_report(self, start_date: datetime, end_date: datetime, 
                             report_name: str = "Custom Report") -> Dict[str, Any]:
        """
        生成自定义时间范围的报告
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            report_name: 报告名称
            
        Returns:
            自定义报告数据
        """
        self.logger.info(f"生成自定义报告: {start_date} 到 {end_date}")
        
        # 获取时间范围内的执行记录
        all_executions = self.db_client.get_recent_executions(20000)
        custom_executions = [
            e for e in all_executions
            if e['start_time'] and start_date <= e['start_time'] < end_date
        ]
        
        days_range = (end_date - start_date).days
        
        # 基本统计
        basic_stats = self._calculate_basic_stats(custom_executions)
        
        # 时间分布分析
        time_distribution = self._analyze_time_distribution(custom_executions, start_date, days_range)
        
        # 脚本分析
        script_analysis = self._analyze_scripts_comprehensive(custom_executions)
        
        # 异常检测
        anomalies = self._detect_anomalies_in_period(custom_executions, start_date, end_date)
        
        report = {
            'report_type': 'custom',
            'report_name': report_name,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'days_covered': days_range,
            'generated_at': format_timestamp(),
            'summary': {
                'total_executions': len(custom_executions),
                'success_rate': basic_stats['success_rate'],
                'avg_daily_executions': len(custom_executions) / days_range if days_range > 0 else 0,
                'unique_scripts': len(set(e['script_id'] for e in custom_executions))
            },
            'statistics': basic_stats,
            'time_distribution': time_distribution,
            'script_analysis': script_analysis,
            'anomalies': anomalies,
            'insights': self._generate_custom_insights(basic_stats, time_distribution, script_analysis, anomalies)
        }
        
        return report
    
    def export_report(self, report_data: Dict[str, Any], output_path: str, 
                     format_type: str = 'json') -> str:
        """
        导出报告到文件
        
        Args:
            report_data: 报告数据
            output_path: 输出路径
            format_type: 格式类型 (json, html, markdown)
            
        Returns:
            导出的文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format_type == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        
        elif format_type == 'html':
            html_content = self._generate_html_report(report_data)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        elif format_type == 'markdown':
            markdown_content = self._generate_markdown_report(report_data)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
        
        else:
            raise ValueError(f"不支持的导出格式: {format_type}")
        
        self.logger.info(f"报告已导出到: {output_path}")
        return str(output_path)
    
    def _calculate_daily_stats(self, executions: List[Dict]) -> Dict[str, Any]:
        """计算日统计"""
        if not executions:
            return {'success_rate': 0, 'avg_execution_time': 0, 'total_time': 0}
        
        success_count = sum(1 for e in executions if e['status'] == 'SUCCESS')
        failed_count = sum(1 for e in executions if e['status'] == 'FAILED')
        
        # 计算执行时间
        execution_times = []
        total_time = 0
        
        for execution in executions:
            if execution['start_time'] and execution['end_time']:
                duration = (execution['end_time'] - execution['start_time']).total_seconds()
                if duration > 0:
                    execution_times.append(duration)
                    total_time += duration
        
        return {
            'total_executions': len(executions),
            'success_count': success_count,
            'failed_count': failed_count,
            'running_count': len(executions) - success_count - failed_count,
            'success_rate': (success_count / len(executions)) * 100,
            'failure_rate': (failed_count / len(executions)) * 100,
            'avg_execution_time': sum(execution_times) / len(execution_times) if execution_times else 0,
            'total_execution_time': total_time,
            'min_execution_time': min(execution_times) if execution_times else 0,
            'max_execution_time': max(execution_times) if execution_times else 0
        }
    
    def _get_script_ranking(self, executions: List[Dict]) -> List[Dict[str, Any]]:
        """获取脚本执行排行"""
        script_stats = {}
        
        for execution in executions:
            script_id = execution['script_id']
            script_name = execution.get('script_name', f'Script_{script_id}')
            
            if script_id not in script_stats:
                script_stats[script_id] = {
                    'script_id': script_id,
                    'script_name': script_name,
                    'total_executions': 0,
                    'success_count': 0,
                    'failed_count': 0
                }
            
            script_stats[script_id]['total_executions'] += 1
            if execution['status'] == 'SUCCESS':
                script_stats[script_id]['success_count'] += 1
            elif execution['status'] == 'FAILED':
                script_stats[script_id]['failed_count'] += 1
        
        # 计算成功率并排序
        for stats in script_stats.values():
            if stats['total_executions'] > 0:
                stats['success_rate'] = (stats['success_count'] / stats['total_executions']) * 100
            else:
                stats['success_rate'] = 0
        
        return sorted(script_stats.values(), key=lambda x: x['total_executions'], reverse=True)
    
    def _analyze_daily_errors(self, executions: List[Dict]) -> Dict[str, Any]:
        """分析日错误"""
        failed_executions = [e for e in executions if e['status'] == 'FAILED']
        
        if not failed_executions:
            return {'total_errors': 0, 'error_scripts': [], 'error_patterns': {}}
        
        # 按脚本统计错误
        error_by_script = {}
        for execution in failed_executions:
            script_name = execution.get('script_name', f"Script_{execution['script_id']}")
            if script_name not in error_by_script:
                error_by_script[script_name] = 0
            error_by_script[script_name] += 1
        
        # 按时间统计错误
        error_by_hour = {}
        for execution in failed_executions:
            if execution['start_time']:
                hour = execution['start_time'].hour
                if hour not in error_by_hour:
                    error_by_hour[hour] = 0
                error_by_hour[hour] += 1
        
        return {
            'total_errors': len(failed_executions),
            'error_rate': (len(failed_executions) / len(executions)) * 100 if executions else 0,
            'error_by_script': sorted(error_by_script.items(), key=lambda x: x[1], reverse=True),
            'error_by_hour': error_by_hour,
            'most_problematic_script': max(error_by_script.items(), key=lambda x: x[1])[0] if error_by_script else None
        }
    
    def _analyze_daily_performance(self, executions: List[Dict]) -> Dict[str, Any]:
        """分析日性能"""
        if not executions:
            return {}
        
        # 按小时分组统计
        hourly_stats = {}
        for execution in executions:
            if execution['start_time']:
                hour = execution['start_time'].hour
                if hour not in hourly_stats:
                    hourly_stats[hour] = {'count': 0, 'times': []}
                
                hourly_stats[hour]['count'] += 1
                
                if execution['start_time'] and execution['end_time']:
                    duration = (execution['end_time'] - execution['start_time']).total_seconds()
                    if duration > 0:
                        hourly_stats[hour]['times'].append(duration)
        
        # 计算每小时平均执行时间
        for hour_data in hourly_stats.values():
            if hour_data['times']:
                hour_data['avg_time'] = sum(hour_data['times']) / len(hour_data['times'])
            else:
                hour_data['avg_time'] = 0
        
        # 找出最繁忙和最慢的时间
        busiest_hour = max(hourly_stats.items(), key=lambda x: x[1]['count'])[0] if hourly_stats else None
        slowest_hour = max(
            [(h, d) for h, d in hourly_stats.items() if d['avg_time'] > 0], 
            key=lambda x: x[1]['avg_time'],
            default=(None, None)
        )[0]
        
        return {
            'hourly_distribution': hourly_stats,
            'busiest_hour': busiest_hour,
            'slowest_hour': slowest_hour,
            'peak_executions': hourly_stats[busiest_hour]['count'] if busiest_hour else 0
        }
    
    def _generate_daily_recommendations(self, stats: Dict, error_analysis: Dict, 
                                      performance_analysis: Dict) -> List[str]:
        """生成日报建议"""
        recommendations = []
        
        # 成功率建议
        if stats['success_rate'] < 90:
            recommendations.append(f"成功率仅{stats['success_rate']:.1f}%，需要重点关注失败脚本")
        
        # 错误建议
        if error_analysis['total_errors'] > 0:
            most_problematic = error_analysis.get('most_problematic_script')
            if most_problematic:
                recommendations.append(f"脚本'{most_problematic}'错误最多，建议优先检查")
        
        # 性能建议
        if stats.get('avg_execution_time', 0) > 60:
            recommendations.append("平均执行时间超过1分钟，建议检查性能瓶颈")
        
        # 时间分布建议
        busiest_hour = performance_analysis.get('busiest_hour')
        if busiest_hour is not None:
            recommendations.append(f"最繁忙时段是{busiest_hour}点，可考虑负载均衡")
        
        return recommendations
    
    def _calculate_weekly_stats(self, executions: List[Dict]) -> Dict[str, Any]:
        """计算周统计"""
        return self._calculate_daily_stats(executions)  # 复用日统计逻辑
    
    def _group_executions_by_day(self, executions: List[Dict], start_time: datetime, 
                               days: int) -> Dict[str, Dict[str, Any]]:
        """按日分组执行记录"""
        daily_data = {}
        
        for i in range(days):
            current_date = start_time + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            daily_data[date_str] = {
                'date': date_str,
                'weekday': current_date.strftime('%A'),
                'total_executions': 0,
                'success_count': 0,
                'failed_count': 0,
                'success_rate': 0
            }
        
        # 统计每日数据
        for execution in executions:
            if execution['start_time']:
                date_str = execution['start_time'].strftime('%Y-%m-%d')
                if date_str in daily_data:
                    daily_data[date_str]['total_executions'] += 1
                    if execution['status'] == 'SUCCESS':
                        daily_data[date_str]['success_count'] += 1
                    elif execution['status'] == 'FAILED':
                        daily_data[date_str]['failed_count'] += 1
        
        # 计算成功率
        for day_data in daily_data.values():
            if day_data['total_executions'] > 0:
                day_data['success_rate'] = (day_data['success_count'] / day_data['total_executions']) * 100
        
        return daily_data
    
    def _analyze_weekly_trends(self, daily_breakdown: Dict[str, Dict]) -> Dict[str, Any]:
        """分析周趋势"""
        daily_counts = [data['total_executions'] for data in daily_breakdown.values()]
        daily_success_rates = [data['success_rate'] for data in daily_breakdown.values()]
        
        # 简单趋势计算
        if len(daily_counts) > 1:
            execution_trend = 'increasing' if daily_counts[-1] > daily_counts[0] else 'decreasing'
            success_trend = 'improving' if daily_success_rates[-1] > daily_success_rates[0] else 'declining'
        else:
            execution_trend = 'stable'
            success_trend = 'stable'
        
        return {
            'execution_volume_trend': execution_trend,
            'success_rate_trend': success_trend,
            'busiest_day': max(daily_breakdown.items(), key=lambda x: x[1]['total_executions'])[0],
            'most_reliable_day': max(daily_breakdown.items(), key=lambda x: x[1]['success_rate'])[0]
        }
    
    def _generate_html_report(self, report_data: Dict[str, Any]) -> str:
        """生成HTML格式报告"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; }}
                .stats {{ display: flex; gap: 20px; }}
                .stat-card {{ background: #e3f2fd; padding: 15px; border-radius: 5px; flex: 1; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .success {{ color: green; }}
                .failure {{ color: red; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{title}</h1>
                <p>生成时间: {generated_at}</p>
            </div>
            
            <div class="section">
                <h2>执行概览</h2>
                <div class="stats">
                    <div class="stat-card">
                        <h3>总执行次数</h3>
                        <p>{total_executions}</p>
                    </div>
                    <div class="stat-card">
                        <h3>成功率</h3>
                        <p class="success">{success_rate:.1f}%</p>
                    </div>
                    <div class="stat-card">
                        <h3>平均执行时间</h3>
                        <p>{avg_execution_time:.2f}秒</p>
                    </div>
                </div>
            </div>
            
            {content}
        </body>
        </html>
        """
        
        # 构建内容
        title = f"{report_data['report_type'].upper()}报告"
        summary = report_data.get('summary', {})
        
        content = ""
        if 'recommendations' in report_data:
            content += "<div class='section'><h2>建议</h2><ul>"
            for rec in report_data['recommendations']:
                content += f"<li>{rec}</li>"
            content += "</ul></div>"
        
        return html_template.format(
            title=title,
            generated_at=report_data.get('generated_at', ''),
            total_executions=summary.get('total_executions', 0),
            success_rate=summary.get('success_rate', 0),
            avg_execution_time=summary.get('avg_execution_time', 0),
            content=content
        )
    
    def _generate_markdown_report(self, report_data: Dict[str, Any]) -> str:
        """生成Markdown格式报告"""
        md_content = []
        
        # 标题
        title = f"{report_data['report_type'].upper()}报告"
        md_content.append(f"# {title}")
        md_content.append(f"生成时间: {report_data.get('generated_at', '')}")
        md_content.append("")
        
        # 概览
        summary = report_data.get('summary', {})
        md_content.append("## 执行概览")
        md_content.append(f"- 总执行次数: {summary.get('total_executions', 0)}")
        md_content.append(f"- 成功率: {summary.get('success_rate', 0):.1f}%")
        md_content.append(f"- 平均执行时间: {summary.get('avg_execution_time', 0):.2f}秒")
        md_content.append("")
        
        # 建议
        if 'recommendations' in report_data:
            md_content.append("## 建议")
            for rec in report_data['recommendations']:
                md_content.append(f"- {rec}")
            md_content.append("")
        
        return "\n".join(md_content)
    
    # 其他辅助方法的简化实现...
    def _calculate_basic_stats(self, executions: List[Dict]) -> Dict[str, Any]:
        return self._calculate_daily_stats(executions)
    
    def _analyze_time_distribution(self, executions: List[Dict], start_date: datetime, days: int) -> Dict[str, Any]:
        return {'distribution': 'time_analysis_placeholder'}
    
    def _analyze_scripts_comprehensive(self, executions: List[Dict]) -> Dict[str, Any]:
        return {'analysis': 'script_analysis_placeholder'}
    
    def _detect_anomalies_in_period(self, executions: List[Dict], start_date: datetime, end_date: datetime) -> List[Dict]:
        return []
    
    def _generate_custom_insights(self, *args) -> List[str]:
        return ['自定义报告分析完成']
    
    def _calculate_monthly_stats(self, executions: List[Dict]) -> Dict[str, Any]:
        return self._calculate_daily_stats(executions)
    
    def _group_executions_by_week(self, executions: List[Dict], start_time: datetime) -> Dict[str, Any]:
        return {'weekly_data': 'placeholder'}
    
    def _analyze_script_health(self, executions: List[Dict]) -> Dict[str, Any]:
        return {'health_analysis': 'placeholder'}
    
    def _analyze_monthly_performance_trends(self, executions: List[Dict]) -> Dict[str, Any]:
        return {'performance_trends': 'placeholder'}
    
    def _generate_capacity_planning(self, stats: Dict, trends: Dict) -> Dict[str, Any]:
        return {'capacity_recommendations': 'placeholder'}
    
    def _generate_weekly_recommendations(self, *args) -> List[str]:
        return ['周报分析完成']
    
    def _generate_monthly_recommendations(self, *args) -> List[str]:
        return ['月报分析完成']
    
    def _analyze_weekly_script_usage(self, executions: List[Dict]) -> Dict[str, Any]:
        return {'script_usage': 'placeholder'}
    
    def _identify_weekly_issues(self, executions: List[Dict], daily_breakdown: Dict) -> List[Dict]:
        return []

def main():
    """主函数"""
    parser = parse_arguments("报告生成脚本")
    parser.add_argument('--type', choices=['daily', 'weekly', 'monthly', 'custom'], 
                       required=True, help='报告类型')
    parser.add_argument('--date', help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD，用于自定义报告)')
    parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD，用于自定义报告)')
    parser.add_argument('--name', default='Custom Report', help='自定义报告名称')
    parser.add_argument('--output', help='输出文件路径')
    parser.add_argument('--format', choices=['json', 'html', 'markdown'], 
                       default='json', help='输出格式')
    parser.add_argument('--use-ai', action='store_true', help='使用AI增强报告')
    
    args = parser.parse_args()
    
    # 设置日志级别
    logger = setup_logging(args.log_level)
    
    generator = ReportGenerator()
    
    try:
        # 解析日期
        target_date = None
        if args.date:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
        
        # 生成报告
        if args.type == 'daily':
            report = generator.generate_daily_report(target_date)
        elif args.type == 'weekly':
            report = generator.generate_weekly_report(target_date)
        elif args.type == 'monthly':
            report = generator.generate_monthly_report(target_date)
        elif args.type == 'custom':
            if not args.start_date or not args.end_date:
                exit_with_error("自定义报告需要指定 --start-date 和 --end-date")
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
            report = generator.generate_custom_report(start_date, end_date, args.name)
        
        # AI增强
        if args.use_ai and generator.ollama_client.health_check():
            logger.info("使用AI增强报告...")
            try:
                ai_insights = generator.ollama_client.analyze_performance_data(report)
                report['ai_insights'] = ai_insights
            except Exception as e:
                logger.warning(f"AI增强失败: {e}")
        
        # 输出或导出报告
        if args.output:
            output_path = generator.export_report(report, args.output, args.format)
            print(f"报告已导出到: {output_path}")
        else:
            if args.format == 'json':
                print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
            else:
                # 默认文本输出
                print(f"=== {report['report_type'].upper()}报告 ===")
                summary = report.get('summary', {})
                print(f"总执行次数: {summary.get('total_executions', 0)}")
                print(f"成功率: {summary.get('success_rate', 0):.1f}%")
                
                if 'recommendations' in report:
                    print("\n建议:")
                    for rec in report['recommendations']:
                        print(f"  - {rec}")
                
                if 'ai_insights' in report:
                    print(f"\nAI洞察:")
                    print(report['ai_insights'])
        
        exit_with_success()
        
    except Exception as e:
        exit_with_error(f"报告生成失败: {e}")

if __name__ == "__main__":
    main()