#!/usr/bin/env python3
"""
趋势分析脚本
生成详细的趋势分析报告，包括预测和建议
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import statistics
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from shared.config_loader import setup_environment
setup_environment()
from shared.utils import setup_logging, parse_arguments, format_timestamp, exit_with_error, exit_with_success
from shared.database_client import DatabaseClient
from shared.ollama_client import OllamaClient

class TrendAnalyzer:
    """趋势分析器"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.db_client = DatabaseClient()
        self.ollama_client = OllamaClient()
    
    def analyze_execution_trends(self, days: int = 30, script_id: Optional[int] = None) -> Dict[str, Any]:
        """
        分析执行趋势
        
        Args:
            days: 分析天数
            script_id: 特定脚本ID，None表示分析所有脚本
            
        Returns:
            趋势分析结果
        """
        self.logger.info(f"分析执行趋势（最近{days}天）")
        
        # 获取数据
        if script_id:
            executions = self.db_client.get_executions_by_script(script_id, 5000)
            analysis_scope = f"脚本ID {script_id}"
        else:
            executions = self.db_client.get_recent_executions(5000)
            analysis_scope = "所有脚本"
        
        # 过滤时间范围
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_executions = [
            e for e in executions 
            if e['start_time'] and e['start_time'] > cutoff_date
        ]
        
        if not filtered_executions:
            return {'error': '指定时间范围内无执行数据'}
        
        # 按小时、日、周分组分析
        hourly_data = self._group_by_time_period(filtered_executions, 'hour')
        daily_data = self._group_by_time_period(filtered_executions, 'day')
        weekly_data = self._group_by_time_period(filtered_executions, 'week')
        
        # 计算各种趋势
        trends = {
            'execution_volume': self._analyze_volume_trend(daily_data),
            'success_rate': self._analyze_success_rate_trend(daily_data),
            'performance': self._analyze_performance_trend(daily_data),
            'error_patterns': self._analyze_error_patterns(filtered_executions),
            'seasonal_patterns': self._analyze_seasonal_patterns(hourly_data, daily_data)
        }
        
        # 生成预测
        predictions = self._generate_predictions(daily_data)
        
        # 识别异常
        anomalies = self._detect_anomalies(daily_data)
        
        result = {
            'analysis_scope': analysis_scope,
            'time_range': f"最近{days}天",
            'analysis_time': format_timestamp(),
            'data_points': len(filtered_executions),
            'time_series': {
                'hourly': hourly_data,
                'daily': daily_data,
                'weekly': weekly_data
            },
            'trends': trends,
            'predictions': predictions,
            'anomalies': anomalies,
            'insights': self._generate_insights(trends, predictions, anomalies)
        }
        
        return result
    
    def analyze_script_popularity(self, days: int = 30) -> Dict[str, Any]:
        """
        分析脚本流行度趋势
        
        Args:
            days: 分析天数
            
        Returns:
            脚本流行度分析
        """
        self.logger.info(f"分析脚本流行度趋势（最近{days}天）")
        
        # 获取执行记录
        executions = self.db_client.get_recent_executions(5000)
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_executions = [
            e for e in executions 
            if e['start_time'] and e['start_time'] > cutoff_date
        ]
        
        # 按脚本分组
        script_stats = defaultdict(lambda: {
            'executions': [],
            'total_count': 0,
            'success_count': 0,
            'failed_count': 0,
            'script_name': 'Unknown'
        })
        
        for execution in filtered_executions:
            script_id = execution['script_id']
            script_stats[script_id]['executions'].append(execution)
            script_stats[script_id]['total_count'] += 1
            script_stats[script_id]['script_name'] = execution.get('script_name', f'Script_{script_id}')
            
            if execution['status'] == 'SUCCESS':
                script_stats[script_id]['success_count'] += 1
            elif execution['status'] == 'FAILED':
                script_stats[script_id]['failed_count'] += 1
        
        # 计算流行度指标
        popularity_data = []
        for script_id, stats in script_stats.items():
            success_rate = (stats['success_count'] / stats['total_count'] * 100) if stats['total_count'] > 0 else 0
            
            # 计算趋势
            daily_counts = self._get_daily_execution_counts(stats['executions'])
            trend = self._calculate_linear_trend(list(daily_counts.values())) if len(daily_counts) > 1 else {'direction': 'stable', 'slope': 0}
            
            popularity_data.append({
                'script_id': script_id,
                'script_name': stats['script_name'],
                'total_executions': stats['total_count'],
                'success_rate': success_rate,
                'trend_direction': trend['direction'],
                'trend_slope': trend['slope'],
                'popularity_score': self._calculate_popularity_score(stats['total_count'], success_rate, trend['slope'])
            })
        
        # 排序
        popularity_data.sort(key=lambda x: x['popularity_score'], reverse=True)
        
        result = {
            'time_range': f"最近{days}天",
            'analysis_time': format_timestamp(),
            'total_scripts': len(popularity_data),
            'script_rankings': popularity_data,
            'top_scripts': popularity_data[:10],
            'trending_up': [s for s in popularity_data if s['trend_direction'] == 'increasing'][:5],
            'trending_down': [s for s in popularity_data if s['trend_direction'] == 'decreasing'][:5],
            'summary': {
                'most_popular': popularity_data[0] if popularity_data else None,
                'most_reliable': max(popularity_data, key=lambda x: x['success_rate']) if popularity_data else None,
                'fastest_growing': max([s for s in popularity_data if s['trend_direction'] == 'increasing'], 
                                     key=lambda x: x['trend_slope'], default=None)
            }
        }
        
        return result
    
    def analyze_failure_trends(self, days: int = 30) -> Dict[str, Any]:
        """
        分析失败趋势
        
        Args:
            days: 分析天数
            
        Returns:
            失败趋势分析
        """
        self.logger.info(f"分析失败趋势（最近{days}天）")
        
        # 获取失败的执行记录
        executions = self.db_client.get_recent_executions(5000)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        failed_executions = [
            e for e in executions 
            if e['start_time'] and e['start_time'] > cutoff_date and e['status'] == 'FAILED'
        ]
        
        if not failed_executions:
            return {
                'time_range': f"最近{days}天",
                'message': '未发现失败记录',
                'total_failures': 0
            }
        
        # 按时间分析失败趋势
        daily_failures = self._group_by_time_period(failed_executions, 'day')
        failure_trend = self._analyze_failure_trend(daily_failures)
        
        # 按脚本分析失败分布
        script_failures = defaultdict(list)
        for execution in failed_executions:
            script_id = execution['script_id']
            script_failures[script_id].append(execution)
        
        # 识别问题脚本
        problematic_scripts = []
        for script_id, failures in script_failures.items():
            script_name = failures[0].get('script_name', f'Script_{script_id}')
            failure_rate = len(failures)
            
            # 计算该脚本的总执行次数
            all_script_executions = self.db_client.get_executions_by_script(script_id, 1000)
            recent_script_executions = [
                e for e in all_script_executions 
                if e['start_time'] and e['start_time'] > cutoff_date
            ]
            
            if recent_script_executions:
                failure_percentage = (len(failures) / len(recent_script_executions)) * 100
                
                problematic_scripts.append({
                    'script_id': script_id,
                    'script_name': script_name,
                    'total_failures': len(failures),
                    'total_executions': len(recent_script_executions),
                    'failure_rate': failure_percentage,
                    'recent_failures': failures[-5:]  # 最近5次失败
                })
        
        # 排序问题脚本
        problematic_scripts.sort(key=lambda x: x['failure_rate'], reverse=True)
        
        # 分析失败时间模式
        failure_time_patterns = self._analyze_failure_time_patterns(failed_executions)
        
        result = {
            'time_range': f"最近{days}天",
            'analysis_time': format_timestamp(),
            'total_failures': len(failed_executions),
            'daily_failures': daily_failures,
            'failure_trend': failure_trend,
            'problematic_scripts': problematic_scripts[:10],  # 前10个问题脚本
            'time_patterns': failure_time_patterns,
            'recommendations': self._generate_failure_recommendations(failure_trend, problematic_scripts)
        }
        
        return result
    
    def _group_by_time_period(self, executions: List[Dict], period: str) -> Dict[str, Dict[str, Any]]:
        """按时间周期分组"""
        grouped_data = defaultdict(lambda: {
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
            
            # 根据周期生成键
            if period == 'hour':
                key = start_time.strftime('%Y-%m-%d %H:00')
            elif period == 'day':
                key = start_time.strftime('%Y-%m-%d')
            elif period == 'week':
                # 获取周的开始日期
                days_since_monday = start_time.weekday()
                week_start = start_time - timedelta(days=days_since_monday)
                key = week_start.strftime('%Y-%m-%d')
            else:
                key = start_time.strftime('%Y-%m-%d')
            
            status = execution.get('status', '').upper()
            grouped_data[key]['total'] += 1
            
            if status == 'SUCCESS':
                grouped_data[key]['success'] += 1
            elif status == 'FAILED':
                grouped_data[key]['failed'] += 1
            elif status == 'RUNNING':
                grouped_data[key]['running'] += 1
            
            # 计算执行时间
            end_time = execution.get('end_time')
            if start_time and end_time:
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time)
                
                duration = (end_time - start_time).total_seconds()
                if duration > 0:
                    grouped_data[key]['execution_times'].append(duration)
        
        # 计算衍生指标
        for key, data in grouped_data.items():
            if data['total'] > 0:
                data['success_rate'] = (data['success'] / data['total']) * 100
                data['failure_rate'] = (data['failed'] / data['total']) * 100
            else:
                data['success_rate'] = 0
                data['failure_rate'] = 0
            
            if data['execution_times']:
                data['avg_execution_time'] = statistics.mean(data['execution_times'])
                data['median_execution_time'] = statistics.median(data['execution_times'])
            else:
                data['avg_execution_time'] = 0
                data['median_execution_time'] = 0
        
        return dict(grouped_data)
    
    def _analyze_volume_trend(self, daily_data: Dict[str, Dict]) -> Dict[str, Any]:
        """分析执行量趋势"""
        if len(daily_data) < 2:
            return {'error': '数据点不足'}
        
        dates = sorted(daily_data.keys())
        volumes = [daily_data[date]['total'] for date in dates]
        
        trend = self._calculate_linear_trend(volumes)
        
        return {
            'direction': trend['direction'],
            'slope': trend['slope'],
            'change_rate': trend.get('change_rate', 0),
            'average_daily_volume': statistics.mean(volumes),
            'peak_day': dates[volumes.index(max(volumes))],
            'peak_volume': max(volumes),
            'min_day': dates[volumes.index(min(volumes))],
            'min_volume': min(volumes)
        }
    
    def _analyze_success_rate_trend(self, daily_data: Dict[str, Dict]) -> Dict[str, Any]:
        """分析成功率趋势"""
        if len(daily_data) < 2:
            return {'error': '数据点不足'}
        
        dates = sorted(daily_data.keys())
        success_rates = [daily_data[date]['success_rate'] for date in dates]
        
        trend = self._calculate_linear_trend(success_rates)
        
        return {
            'direction': trend['direction'],
            'slope': trend['slope'],
            'change_rate': trend.get('change_rate', 0),
            'average_success_rate': statistics.mean(success_rates),
            'best_day': dates[success_rates.index(max(success_rates))],
            'best_rate': max(success_rates),
            'worst_day': dates[success_rates.index(min(success_rates))],
            'worst_rate': min(success_rates),
            'volatility': statistics.stdev(success_rates) if len(success_rates) > 1 else 0
        }
    
    def _analyze_performance_trend(self, daily_data: Dict[str, Dict]) -> Dict[str, Any]:
        """分析性能趋势"""
        dates = sorted(daily_data.keys())
        avg_times = [daily_data[date]['avg_execution_time'] for date in dates if daily_data[date]['avg_execution_time'] > 0]
        
        if len(avg_times) < 2:
            return {'error': '性能数据不足'}
        
        trend = self._calculate_linear_trend(avg_times)
        
        return {
            'direction': trend['direction'],
            'slope': trend['slope'],
            'change_rate': trend.get('change_rate', 0),
            'average_execution_time': statistics.mean(avg_times),
            'fastest_day': dates[avg_times.index(min(avg_times))] if avg_times else None,
            'fastest_time': min(avg_times) if avg_times else 0,
            'slowest_day': dates[avg_times.index(max(avg_times))] if avg_times else None,
            'slowest_time': max(avg_times) if avg_times else 0
        }
    
    def _analyze_error_patterns(self, executions: List[Dict]) -> Dict[str, Any]:
        """分析错误模式"""
        failed_executions = [e for e in executions if e['status'] == 'FAILED']
        
        if not failed_executions:
            return {'total_failures': 0, 'patterns': []}
        
        # 按脚本统计失败
        script_failures = defaultdict(int)
        for execution in failed_executions:
            script_name = execution.get('script_name', f"Script_{execution['script_id']}")
            script_failures[script_name] += 1
        
        # 按时间段统计失败
        hourly_failures = defaultdict(int)
        for execution in failed_executions:
            start_time = execution['start_time']
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            hour = start_time.hour
            hourly_failures[hour] += 1
        
        return {
            'total_failures': len(failed_executions),
            'failure_rate': len(failed_executions) / len(executions) * 100 if executions else 0,
            'top_failing_scripts': sorted(script_failures.items(), key=lambda x: x[1], reverse=True)[:5],
            'failure_by_hour': dict(hourly_failures),
            'peak_failure_hour': max(hourly_failures.items(), key=lambda x: x[1])[0] if hourly_failures else None
        }
    
    def _analyze_seasonal_patterns(self, hourly_data: Dict, daily_data: Dict) -> Dict[str, Any]:
        """分析季节性模式"""
        patterns = {}
        
        # 按小时分析
        if hourly_data:
            hourly_volumes = defaultdict(list)
            for time_str, data in hourly_data.items():
                hour = datetime.strptime(time_str, '%Y-%m-%d %H:00').hour
                hourly_volumes[hour].append(data['total'])
            
            avg_by_hour = {hour: statistics.mean(volumes) for hour, volumes in hourly_volumes.items()}
            peak_hour = max(avg_by_hour.items(), key=lambda x: x[1])[0] if avg_by_hour else None
            
            patterns['hourly'] = {
                'peak_hour': peak_hour,
                'distribution': avg_by_hour
            }
        
        # 按星期分析
        if daily_data:
            weekday_volumes = defaultdict(list)
            for date_str, data in daily_data.items():
                weekday = datetime.strptime(date_str, '%Y-%m-%d').weekday()
                weekday_volumes[weekday].append(data['total'])
            
            avg_by_weekday = {day: statistics.mean(volumes) for day, volumes in weekday_volumes.items()}
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            patterns['weekly'] = {
                'distribution': {weekday_names[day]: vol for day, vol in avg_by_weekday.items()},
                'busiest_day': weekday_names[max(avg_by_weekday.items(), key=lambda x: x[1])[0]] if avg_by_weekday else None
            }
        
        return patterns
    
    def _calculate_linear_trend(self, values: List[float]) -> Dict[str, Any]:
        """计算线性趋势"""
        if len(values) < 2:
            return {'slope': 0, 'direction': 'stable', 'change_rate': 0}
        
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
        
        # 计算变化率
        change_rate = abs(slope) / y_mean * 100 if y_mean != 0 else 0
        
        return {
            'slope': slope,
            'direction': direction,
            'change_rate': change_rate
        }
    
    def _generate_predictions(self, daily_data: Dict) -> Dict[str, Any]:
        """生成简单预测"""
        if len(daily_data) < 7:
            return {'error': '数据不足以进行预测'}
        
        dates = sorted(daily_data.keys())
        recent_data = dates[-7:]  # 最近7天
        
        # 预测执行量
        recent_volumes = [daily_data[date]['total'] for date in recent_data]
        avg_volume = statistics.mean(recent_volumes)
        trend = self._calculate_linear_trend(recent_volumes)
        
        # 简单的线性预测
        next_day_prediction = recent_volumes[-1] + trend['slope']
        next_week_avg_prediction = avg_volume + (trend['slope'] * 7)
        
        return {
            'next_day_volume': max(0, int(next_day_prediction)),
            'next_week_avg_volume': max(0, int(next_week_avg_prediction)),
            'confidence': 'low' if abs(trend['slope']) > avg_volume * 0.1 else 'medium',
            'trend_direction': trend['direction']
        }
    
    def _detect_anomalies(self, daily_data: Dict) -> List[Dict[str, Any]]:
        """检测异常"""
        if len(daily_data) < 7:
            return []
        
        anomalies = []
        dates = sorted(daily_data.keys())
        
        # 计算执行量的统计指标
        volumes = [daily_data[date]['total'] for date in dates]
        success_rates = [daily_data[date]['success_rate'] for date in dates]
        
        if len(volumes) > 1:
            volume_mean = statistics.mean(volumes)
            volume_std = statistics.stdev(volumes) if len(volumes) > 1 else 0
            
            success_mean = statistics.mean(success_rates)
            success_std = statistics.stdev(success_rates) if len(success_rates) > 1 else 0
            
            # 检测异常值（2个标准差之外）
            for date in dates:
                data = daily_data[date]
                volume = data['total']
                success_rate = data['success_rate']
                
                volume_z_score = (volume - volume_mean) / volume_std if volume_std > 0 else 0
                success_z_score = (success_rate - success_mean) / success_std if success_std > 0 else 0
                
                if abs(volume_z_score) > 2:
                    anomalies.append({
                        'date': date,
                        'type': 'volume_anomaly',
                        'description': f"执行量异常: {volume} (正常范围: {volume_mean:.1f}±{volume_std:.1f})",
                        'severity': 'high' if abs(volume_z_score) > 3 else 'medium'
                    })
                
                if abs(success_z_score) > 2:
                    anomalies.append({
                        'date': date,
                        'type': 'success_rate_anomaly',
                        'description': f"成功率异常: {success_rate:.1f}% (正常范围: {success_mean:.1f}±{success_std:.1f}%)",
                        'severity': 'high' if abs(success_z_score) > 3 else 'medium'
                    })
        
        return anomalies
    
    def _generate_insights(self, trends: Dict, predictions: Dict, anomalies: List) -> List[str]:
        """生成洞察"""
        insights = []
        
        # 执行量趋势洞察
        volume_trend = trends.get('execution_volume', {})
        if volume_trend.get('direction') == 'increasing':
            insights.append(f"执行量呈上升趋势，日均增长{volume_trend.get('change_rate', 0):.1f}%")
        elif volume_trend.get('direction') == 'decreasing':
            insights.append(f"执行量呈下降趋势，日均下降{volume_trend.get('change_rate', 0):.1f}%")
        
        # 成功率趋势洞察
        success_trend = trends.get('success_rate', {})
        if success_trend.get('direction') == 'decreasing':
            insights.append(f"成功率呈下降趋势，需要关注系统稳定性")
        elif success_trend.get('direction') == 'increasing':
            insights.append(f"成功率持续改善，系统稳定性提升")
        
        # 性能趋势洞察
        perf_trend = trends.get('performance', {})
        if perf_trend.get('direction') == 'increasing':
            insights.append("平均执行时间增长，可能存在性能退化")
        elif perf_trend.get('direction') == 'decreasing':
            insights.append("执行性能持续改善")
        
        # 异常洞察
        if anomalies:
            high_severity = [a for a in anomalies if a.get('severity') == 'high']
            if high_severity:
                insights.append(f"发现{len(high_severity)}个高严重性异常，需要立即关注")
        
        return insights
    
    def _get_daily_execution_counts(self, executions: List[Dict]) -> Dict[str, int]:
        """获取每日执行次数"""
        daily_counts = defaultdict(int)
        
        for execution in executions:
            start_time = execution.get('start_time')
            if start_time:
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time)
                date_str = start_time.strftime('%Y-%m-%d')
                daily_counts[date_str] += 1
        
        return dict(daily_counts)
    
    def _calculate_popularity_score(self, execution_count: int, success_rate: float, trend_slope: float) -> float:
        """计算流行度分数"""
        base_score = execution_count * (success_rate / 100)
        trend_bonus = max(0, trend_slope * 10)  # 上升趋势加分
        return base_score + trend_bonus
    
    def _analyze_failure_trend(self, daily_failures: Dict) -> Dict[str, Any]:
        """分析失败趋势"""
        if len(daily_failures) < 2:
            return {'direction': 'stable', 'slope': 0}
        
        dates = sorted(daily_failures.keys())
        failure_counts = [daily_failures[date]['total'] for date in dates]
        
        return self._calculate_linear_trend(failure_counts)
    
    def _analyze_failure_time_patterns(self, failed_executions: List[Dict]) -> Dict[str, Any]:
        """分析失败时间模式"""
        hour_failures = defaultdict(int)
        weekday_failures = defaultdict(int)
        
        for execution in failed_executions:
            start_time = execution.get('start_time')
            if start_time:
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time)
                
                hour_failures[start_time.hour] += 1
                weekday_failures[start_time.weekday()] += 1
        
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        return {
            'by_hour': dict(hour_failures),
            'by_weekday': {weekday_names[day]: count for day, count in weekday_failures.items()},
            'peak_failure_hour': max(hour_failures.items(), key=lambda x: x[1])[0] if hour_failures else None,
            'peak_failure_weekday': weekday_names[max(weekday_failures.items(), key=lambda x: x[1])[0]] if weekday_failures else None
        }
    
    def _generate_failure_recommendations(self, failure_trend: Dict, problematic_scripts: List[Dict]) -> List[str]:
        """生成失败分析建议"""
        recommendations = []
        
        if failure_trend.get('direction') == 'increasing':
            recommendations.append("失败率呈上升趋势，建议立即调查根本原因")
        
        if len(problematic_scripts) > 0:
            top_problem = problematic_scripts[0]
            recommendations.append(f"重点关注脚本'{top_problem['script_name']}'，失败率高达{top_problem['failure_rate']:.1f}%")
        
        if len([s for s in problematic_scripts if s['failure_rate'] > 50]) > 3:
            recommendations.append("多个脚本失败率超过50%，建议全面检查系统环境")
        
        return recommendations

def main():
    """主函数"""
    parser = parse_arguments("趋势分析脚本")
    parser.add_argument('--type', choices=['execution', 'popularity', 'failure'], default='execution', help='分析类型')
    parser.add_argument('--script-id', type=int, help='特定脚本ID')
    parser.add_argument('--days', type=int, default=30, help='分析时间范围（天）')
    parser.add_argument('--output-format', choices=['json', 'text'], default='text', help='输出格式')
    parser.add_argument('--use-ai', action='store_true', help='使用AI增强分析')
    
    args = parser.parse_args()
    
    # 设置日志级别
    logger = setup_logging(args.log_level)
    
    analyzer = TrendAnalyzer()
    
    try:
        if args.type == 'execution':
            result = analyzer.analyze_execution_trends(args.days, args.script_id)
        elif args.type == 'popularity':
            result = analyzer.analyze_script_popularity(args.days)
        elif args.type == 'failure':
            result = analyzer.analyze_failure_trends(args.days)
        else:
            exit_with_error("无效的分析类型")
        
        # AI增强分析
        if args.use_ai and analyzer.ollama_client.health_check():
            logger.info("使用AI进行趋势分析增强...")
            try:
                ai_analysis = analyzer.ollama_client.analyze_performance_data(result)
                result['ai_insights'] = ai_analysis
            except Exception as e:
                logger.warning(f"AI分析失败: {e}")
        
        # 输出结果
        if args.output_format == 'json':
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            # 文本格式输出
            print(f"=== {args.type.upper()}趋势分析 ===")
            print(f"分析范围: {result.get('analysis_scope', result.get('time_range', 'N/A'))}")
            print(f"数据点: {result.get('data_points', 'N/A')}")
            
            # 洞察
            insights = result.get('insights', [])
            if insights:
                print("\n关键洞察:")
                for insight in insights:
                    print(f"  • {insight}")
            
            # 异常
            anomalies = result.get('anomalies', [])
            if anomalies:
                print(f"\n发现异常 ({len(anomalies)}个):")
                for anomaly in anomalies[:5]:  # 只显示前5个
                    print(f"  • {anomaly['date']}: {anomaly['description']}")
            
            # 预测
            predictions = result.get('predictions', {})
            if predictions and 'error' not in predictions:
                print(f"\n预测:")
                print(f"  • 明日执行量预测: {predictions.get('next_day_volume', 'N/A')}")
                print(f"  • 下周平均执行量: {predictions.get('next_week_avg_volume', 'N/A')}")
            
            # AI洞察
            if 'ai_insights' in result:
                print(f"\n=== AI分析洞察 ===")
                print(result['ai_insights'])
        
        exit_with_success()
        
    except Exception as e:
        exit_with_error(f"趋势分析失败: {e}")

if __name__ == "__main__":
    main()