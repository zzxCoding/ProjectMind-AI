#!/usr/bin/env python3
"""
Ollama服务脚本
提供Ollama AI分析服务的HTTP API接口
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
import aiohttp
from aiohttp import web, ClientSession
import logging
from pathlib import Path

# 动态获取项目根目录
project_root = Path(__file__).parent.parent.absolute()
sys.path.append(str(project_root))

# 自动检测基础路径
if os.path.exists('/app/logs'):
    base_path = '/app'  # 容器环境
else:
    base_path = str(Path(__file__).parent.parent.parent.absolute())  # 本地环境
from shared.utils import setup_logging, parse_arguments, format_timestamp, exit_with_error
from shared.database_client import DatabaseClient
from shared.ollama_client import OllamaClient
from config.ollama_config import OllamaConfig, get_available_models, get_model_info

class OllamaService:
    """Ollama AI分析服务"""
    
    def __init__(self, host: str = "localhost", port: int = 8888):
        self.host = host
        self.port = port
        self.logger = setup_logging()
        
        # 初始化客户端
        self.db_client = DatabaseClient()
        self.ollama_client = OllamaClient()
        
        # 创建Web应用
        self.app = web.Application()
        self._setup_routes()
        self._setup_middleware()
        
        # 服务状态
        self.start_time = datetime.now()
        self.request_count = 0
        self.error_count = 0
    
    def _setup_routes(self):
        """设置路由"""
        # 健康检查
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/status', self.get_status)
        
        # Ollama相关接口
        self.app.router.add_get('/models', self.list_models)
        self.app.router.add_post('/models/pull', self.pull_model)
        self.app.router.add_post('/analyze/text', self.analyze_text)
        self.app.router.add_post('/analyze/logs', self.analyze_logs)
        self.app.router.add_post('/analyze/performance', self.analyze_performance)
        
        # 数据分析接口
        self.app.router.add_post('/analysis/script-performance', self.analyze_script_performance)
        self.app.router.add_post('/analysis/system-health', self.analyze_system_health)
        self.app.router.add_post('/analysis/trend-prediction', self.predict_trends)
        
        # 报告生成接口
        self.app.router.add_post('/reports/generate', self.generate_report)
        self.app.router.add_get('/reports/daily', self.get_daily_insights)
        
        # 批量处理接口
        self.app.router.add_post('/batch/analyze-recent-logs', self.batch_analyze_logs)
        self.app.router.add_post('/batch/health-check', self.batch_health_check)
    
    def _setup_middleware(self):
        """设置中间件"""
        @web.middleware
        async def request_logger_middleware(request, handler):
            start_time = datetime.now()
            self.request_count += 1
            
            try:
                response = await handler(request)
                duration = (datetime.now() - start_time).total_seconds()
                
                self.logger.info(f"{request.method} {request.path} - {response.status} - {duration:.3f}s")
                return response
            except Exception as e:
                self.error_count += 1
                duration = (datetime.now() - start_time).total_seconds()
                self.logger.error(f"{request.method} {request.path} - ERROR: {e} - {duration:.3f}s")
                raise
        
        @web.middleware
        async def cors_middleware(request, handler):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response
        
        self.app.middlewares.append(request_logger_middleware)
        self.app.middlewares.append(cors_middleware)
    
    async def health_check(self, request):
        """健康检查接口"""
        try:
            # 检查Ollama服务
            ollama_healthy = self.ollama_client.health_check()
            
            # 检查数据库连接
            db_healthy = self.db_client.test_connection()
            
            status = "healthy" if (ollama_healthy and db_healthy) else "unhealthy"
            
            return web.json_response({
                'status': status,
                'timestamp': format_timestamp(),
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'services': {
                    'ollama': ollama_healthy,
                    'database': db_healthy
                },
                'stats': {
                    'total_requests': self.request_count,
                    'error_count': self.error_count,
                    'error_rate': (self.error_count / max(self.request_count, 1)) * 100
                }
            })
        except Exception as e:
            return web.json_response({
                'status': 'error',
                'error': str(e)
            }, status=500)
    
    async def get_status(self, request):
        """获取服务状态"""
        try:
            models = self.ollama_client.list_models()
            recent_executions = self.db_client.get_recent_executions(10)
            
            return web.json_response({
                'service': 'OllamaService',
                'version': '1.0.0',
                'start_time': format_timestamp(self.start_time),
                'uptime': str(datetime.now() - self.start_time),
                'available_models': len(models),
                'recent_executions': len(recent_executions),
                'endpoints': [
                    '/health', '/status', '/models', '/analyze/text',
                    '/analyze/logs', '/analysis/script-performance'
                ]
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def list_models(self, request):
        """列出可用模型"""
        try:
            models = self.ollama_client.list_models()
            available_models = get_available_models()
            
            model_info = []
            for model in models:
                model_name = model.get('name', '')
                info = get_model_info(model_name) or {}
                model_info.append({
                    **model,
                    'description': info.get('description', ''),
                    'good_for': info.get('good_for', [])
                })
            
            return web.json_response({
                'installed_models': model_info,
                'available_models': available_models,
                'total_installed': len(models)
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def pull_model(self, request):
        """拉取模型"""
        try:
            data = await request.json()
            model_name = data.get('model')
            
            if not model_name:
                return web.json_response({'error': 'model parameter required'}, status=400)
            
            # 异步拉取模型
            success = self.ollama_client.pull_model(model_name)
            
            if success:
                return web.json_response({
                    'status': 'success',
                    'message': f'Model {model_name} pulled successfully'
                })
            else:
                return web.json_response({
                    'status': 'failed',
                    'message': f'Failed to pull model {model_name}'
                }, status=400)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_text(self, request):
        """文本分析接口"""
        try:
            data = await request.json()
            text = data.get('text', '')
            analysis_type = data.get('type', 'summary')
            model = data.get('model')
            
            if not text:
                return web.json_response({'error': 'text parameter required'}, status=400)
            
            result = self.ollama_client.analyze_text(text, model, analysis_type)
            
            return web.json_response({
                'analysis_type': analysis_type,
                'model_used': model or self.ollama_client.config.default_model,
                'result': result,
                'timestamp': format_timestamp()
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_logs(self, request):
        """日志分析接口"""
        try:
            data = await request.json()
            
            if 'log_lines' in data:
                # 直接分析日志行
                log_lines = data['log_lines']
                model = data.get('model')
                result = self.ollama_client.analyze_logs(log_lines, model)
                
                return web.json_response({
                    'analysis_type': 'log_analysis',
                    'lines_analyzed': len(log_lines),
                    'result': result,
                    'timestamp': format_timestamp()
                })
            
            elif 'log_path' in data:
                # 分析日志文件
                log_path = data['log_path']
                model = data.get('model')
                
                # 读取日志文件
                try:
                    if not os.path.isabs(log_path):
                        log_path = os.path.join(base_path, log_path)
                    
                    with open(log_path, 'r', encoding='utf-8') as f:
                        log_lines = f.readlines()[:1000]  # 限制行数
                    
                    result = self.ollama_client.analyze_logs(log_lines, model)
                    
                    return web.json_response({
                        'analysis_type': 'log_file_analysis',
                        'log_path': log_path,
                        'lines_analyzed': len(log_lines),
                        'result': result,
                        'timestamp': format_timestamp()
                    })
                except FileNotFoundError:
                    return web.json_response({'error': f'Log file not found: {log_path}'}, status=404)
            
            else:
                return web.json_response({'error': 'log_lines or log_path parameter required'}, status=400)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_performance(self, request):
        """性能数据分析接口"""
        try:
            data = await request.json()
            performance_data = data.get('performance_data', {})
            model = data.get('model')
            
            if not performance_data:
                return web.json_response({'error': 'performance_data parameter required'}, status=400)
            
            result = self.ollama_client.analyze_performance_data(performance_data, model)
            
            return web.json_response({
                'analysis_type': 'performance_analysis',
                'result': result,
                'timestamp': format_timestamp()
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_script_performance(self, request):
        """脚本性能分析接口"""
        try:
            data = await request.json()
            script_id = data.get('script_id')
            days = data.get('days', 7)
            use_ai = data.get('use_ai', True)
            
            if not script_id:
                return web.json_response({'error': 'script_id parameter required'}, status=400)
            
            # 获取脚本执行记录
            executions = self.db_client.get_executions_by_script(script_id, 100)
            
            if not executions:
                return web.json_response({'error': f'No executions found for script {script_id}'}, status=404)
            
            # 基础性能统计
            total_executions = len(executions)
            success_count = sum(1 for e in executions if e['status'] == 'SUCCESS')
            success_rate = (success_count / total_executions * 100) if total_executions > 0 else 0
            
            # 执行时间分析
            execution_times = []
            for execution in executions:
                if execution['start_time'] and execution['end_time']:
                    duration = (execution['end_time'] - execution['start_time']).total_seconds()
                    if duration > 0:
                        execution_times.append(duration)
            
            avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
            
            analysis_result = {
                'script_id': script_id,
                'script_name': executions[0].get('script_name', f'Script_{script_id}'),
                'analysis_period': f'Last {days} days',
                'total_executions': total_executions,
                'success_rate': success_rate,
                'avg_execution_time': avg_time,
                'performance_grade': self._calculate_performance_grade(success_rate, avg_time)
            }
            
            # AI增强分析
            if use_ai:
                ai_insights = self.ollama_client.analyze_performance_data(analysis_result)
                analysis_result['ai_insights'] = ai_insights
            
            return web.json_response(analysis_result)
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_system_health(self, request):
        """系统健康分析接口"""
        try:
            data = await request.json()
            days = data.get('days', 1)
            use_ai = data.get('use_ai', True)
            
            # 获取系统统计
            stats = self.db_client.get_execution_stats(days)
            recent_executions = self.db_client.get_recent_executions(100)
            
            # 计算健康指标
            health_score = self._calculate_health_score(stats)
            
            analysis_result = {
                'analysis_period': f'Last {days} days',
                'system_stats': stats,
                'health_score': health_score,
                'status': self._get_health_status(health_score),
                'recommendations': self._generate_health_recommendations(stats, health_score),
                'timestamp': format_timestamp()
            }
            
            # AI增强分析
            if use_ai:
                ai_insights = self.ollama_client.analyze_performance_data(analysis_result)
                analysis_result['ai_insights'] = ai_insights
            
            return web.json_response(analysis_result)
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def predict_trends(self, request):
        """趋势预测接口"""
        try:
            data = await request.json()
            prediction_days = data.get('prediction_days', 7)
            script_id = data.get('script_id')  # 可选，预测特定脚本
            
            # 获取历史数据
            if script_id:
                executions = self.db_client.get_executions_by_script(script_id, 1000)
                analysis_scope = f'Script {script_id}'
            else:
                executions = self.db_client.get_recent_executions(1000)
                analysis_scope = 'System'
            
            # 简单的趋势分析（实际应该使用更复杂的算法）
            daily_counts = self._group_by_day(executions)
            trend_data = self._calculate_simple_trend(daily_counts)
            
            # 生成预测
            predictions = {
                'scope': analysis_scope,
                'prediction_period': f'Next {prediction_days} days',
                'trend_direction': trend_data.get('direction', 'stable'),
                'predicted_daily_average': trend_data.get('predicted_avg', 0),
                'confidence': trend_data.get('confidence', 'low'),
                'recommendations': self._generate_trend_recommendations(trend_data)
            }
            
            # AI增强预测
            ai_prediction = self.ollama_client.analyze_performance_data({
                'historical_data': daily_counts,
                'trend_data': trend_data,
                'prediction_request': predictions
            })
            predictions['ai_insights'] = ai_prediction
            
            return web.json_response(predictions)
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def generate_report(self, request):
        """生成报告接口"""
        try:
            data = await request.json()
            report_type = data.get('type', 'daily')
            target_date = data.get('date')
            use_ai = data.get('use_ai', True)
            
            # 获取报告数据
            if report_type == 'daily':
                report_data = self._generate_daily_report_data(target_date)
            elif report_type == 'weekly':
                report_data = self._generate_weekly_report_data(target_date)
            else:
                return web.json_response({'error': f'Unsupported report type: {report_type}'}, status=400)
            
            # AI增强报告
            if use_ai:
                ai_summary = self.ollama_client.analyze_performance_data(report_data)
                report_data['ai_summary'] = ai_summary
            
            return web.json_response({
                'report_type': report_type,
                'generated_at': format_timestamp(),
                **report_data
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_daily_insights(self, request):
        """获取日常洞察"""
        try:
            # 获取今日的关键指标
            today_stats = self.db_client.get_execution_stats(1)
            recent_failures = self.db_client.get_recent_executions(50)
            failed_today = [e for e in recent_failures if e['status'] == 'FAILED']
            
            insights = {
                'date': format_timestamp().split(' ')[0],
                'key_metrics': {
                    'total_executions': today_stats.get('total_executions', 0),
                    'success_rate': (today_stats.get('success_count', 0) / max(today_stats.get('total_executions', 1), 1)) * 100,
                    'failures_today': len(failed_today)
                },
                'alerts': self._generate_daily_alerts(today_stats, failed_today),
                'recommendations': self._generate_daily_recommendations(today_stats)
            }
            
            # AI洞察
            ai_insights = self.ollama_client.analyze_performance_data(insights)
            insights['ai_insights'] = ai_insights
            
            return web.json_response(insights)
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def batch_analyze_logs(self, request):
        """批量分析日志"""
        try:
            data = await request.json()
            log_paths = data.get('log_paths', [])
            model = data.get('model')
            
            if not log_paths:
                return web.json_response({'error': 'log_paths parameter required'}, status=400)
            
            results = []
            for log_path in log_paths:
                try:
                    if not os.path.isabs(log_path):
                        log_path = os.path.join(base_path, log_path)
                    
                    with open(log_path, 'r', encoding='utf-8') as f:
                        log_lines = f.readlines()[:500]  # 限制行数
                    
                    analysis = self.ollama_client.analyze_logs(log_lines, model)
                    results.append({
                        'log_path': log_path,
                        'status': 'success',
                        'lines_analyzed': len(log_lines),
                        'analysis': analysis
                    })
                except Exception as e:
                    results.append({
                        'log_path': log_path,
                        'status': 'error',
                        'error': str(e)
                    })
            
            return web.json_response({
                'batch_analysis': True,
                'total_files': len(log_paths),
                'successful': sum(1 for r in results if r['status'] == 'success'),
                'results': results,
                'timestamp': format_timestamp()
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def batch_health_check(self, request):
        """批量健康检查"""
        try:
            data = await request.json()
            script_ids = data.get('script_ids', [])
            
            if not script_ids:
                # 检查所有活跃脚本
                scripts = self.db_client.get_all_scripts()
                script_ids = [s['id'] for s in scripts]
            
            health_results = []
            for script_id in script_ids:
                try:
                    executions = self.db_client.get_executions_by_script(script_id, 20)
                    if executions:
                        success_count = sum(1 for e in executions if e['status'] == 'SUCCESS')
                        success_rate = (success_count / len(executions)) * 100
                        
                        health_status = 'healthy' if success_rate >= 80 else 'unhealthy'
                        
                        health_results.append({
                            'script_id': script_id,
                            'script_name': executions[0].get('script_name', f'Script_{script_id}'),
                            'health_status': health_status,
                            'success_rate': success_rate,
                            'recent_executions': len(executions)
                        })
                except Exception as e:
                    health_results.append({
                        'script_id': script_id,
                        'error': str(e)
                    })
            
            # 汇总健康状况
            healthy_count = sum(1 for r in health_results if r.get('health_status') == 'healthy')
            overall_health = 'good' if healthy_count / len(health_results) >= 0.8 else 'warning'
            
            return web.json_response({
                'overall_health': overall_health,
                'total_scripts': len(script_ids),
                'healthy_scripts': healthy_count,
                'results': health_results,
                'timestamp': format_timestamp()
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    # 辅助方法
    def _calculate_performance_grade(self, success_rate: float, avg_time: float) -> str:
        """计算性能等级"""
        if success_rate >= 95 and avg_time < 10:
            return 'A'
        elif success_rate >= 90 and avg_time < 30:
            return 'B'
        elif success_rate >= 80 and avg_time < 60:
            return 'C'
        else:
            return 'D'
    
    def _calculate_health_score(self, stats: Dict[str, Any]) -> float:
        """计算健康分数"""
        total = stats.get('total_executions', 0)
        if total == 0:
            return 0
        
        success_rate = (stats.get('success_count', 0) / total) * 100
        return success_rate
    
    def _get_health_status(self, health_score: float) -> str:
        """获取健康状态"""
        if health_score >= 95:
            return 'excellent'
        elif health_score >= 85:
            return 'good'
        elif health_score >= 70:
            return 'warning'
        else:
            return 'critical'
    
    def _generate_health_recommendations(self, stats: Dict, health_score: float) -> List[str]:
        """生成健康建议"""
        recommendations = []
        
        if health_score < 80:
            recommendations.append('系统成功率偏低，需要重点关注失败脚本')
        
        if stats.get('failed_count', 0) > 10:
            recommendations.append('失败次数较多，建议检查系统环境')
        
        if not recommendations:
            recommendations.append('系统运行正常')
        
        return recommendations
    
    def _group_by_day(self, executions: List[Dict]) -> Dict[str, int]:
        """按天分组执行记录"""
        from collections import defaultdict
        daily_counts = defaultdict(int)
        
        for execution in executions:
            if execution.get('start_time'):
                date_str = execution['start_time'].strftime('%Y-%m-%d')
                daily_counts[date_str] += 1
        
        return dict(daily_counts)
    
    def _calculate_simple_trend(self, daily_counts: Dict[str, int]) -> Dict[str, Any]:
        """计算简单趋势"""
        if len(daily_counts) < 2:
            return {'direction': 'stable', 'predicted_avg': 0, 'confidence': 'low'}
        
        values = list(daily_counts.values())
        avg = sum(values) / len(values)
        
        # 简单线性趋势
        recent_avg = sum(values[-3:]) / min(3, len(values))
        early_avg = sum(values[:3]) / min(3, len(values))
        
        if recent_avg > early_avg * 1.1:
            direction = 'increasing'
        elif recent_avg < early_avg * 0.9:
            direction = 'decreasing'
        else:
            direction = 'stable'
        
        return {
            'direction': direction,
            'predicted_avg': recent_avg,
            'confidence': 'medium'
        }
    
    def _generate_trend_recommendations(self, trend_data: Dict) -> List[str]:
        """生成趋势建议"""
        direction = trend_data.get('direction', 'stable')
        
        if direction == 'increasing':
            return ['执行量呈上升趋势，建议检查系统容量']
        elif direction == 'decreasing':
            return ['执行量呈下降趋势，可能需要关注脚本使用情况']
        else:
            return ['执行量保持稳定']
    
    def _generate_daily_report_data(self, target_date: str = None) -> Dict[str, Any]:
        """生成日报数据"""
        # 简化实现
        stats = self.db_client.get_execution_stats(1)
        return {
            'date': target_date or format_timestamp().split(' ')[0],
            'summary': stats,
            'highlights': ['系统运行正常']
        }
    
    def _generate_weekly_report_data(self, target_date: str = None) -> Dict[str, Any]:
        """生成周报数据"""
        # 简化实现
        stats = self.db_client.get_execution_stats(7)
        return {
            'week': target_date or 'current',
            'summary': stats,
            'trends': ['执行量保持稳定']
        }
    
    def _generate_daily_alerts(self, stats: Dict, failed_executions: List) -> List[str]:
        """生成日常告警"""
        alerts = []
        
        if stats.get('failed_count', 0) > 5:
            alerts.append(f"今日失败次数较多: {stats['failed_count']}次")
        
        if len(failed_executions) > 0:
            alerts.append(f"有{len(failed_executions)}个脚本执行失败")
        
        return alerts
    
    def _generate_daily_recommendations(self, stats: Dict) -> List[str]:
        """生成日常建议"""
        recommendations = []
        
        success_rate = (stats.get('success_count', 0) / max(stats.get('total_executions', 1), 1)) * 100
        
        if success_rate < 90:
            recommendations.append('建议检查失败的脚本')
        else:
            recommendations.append('系统运行良好，继续保持')
        
        return recommendations
    
    async def start_server(self):
        """启动服务器"""
        self.logger.info(f"启动Ollama服务: http://{self.host}:{self.port}")
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        self.logger.info("Ollama服务启动成功")
        
        # 保持运行
        try:
            await asyncio.Future()  # run forever
        except KeyboardInterrupt:
            self.logger.info("收到停止信号")
        finally:
            await runner.cleanup()
            self.logger.info("Ollama服务已停止")

def main():
    """主函数"""
    parser = parse_arguments("Ollama AI分析服务")
    parser.add_argument('--host', default='localhost', help='服务绑定地址')
    parser.add_argument('--port', type=int, default=8888, help='服务端口')
    parser.add_argument('--test', action='store_true', help='测试模式（不启动服务器）')
    
    args = parser.parse_args()
    
    # 设置日志级别
    logger = setup_logging(args.log_level)
    
    try:
        service = OllamaService(args.host, args.port)
        
        if args.test:
            # 测试模式：检查服务依赖
            logger.info("测试模式 - 检查服务依赖")
            
            # 测试数据库连接
            if service.db_client.test_connection():
                logger.info("✅ 数据库连接正常")
            else:
                logger.error("❌ 数据库连接失败")
                return
            
            # 测试Ollama连接
            if service.ollama_client.health_check():
                logger.info("✅ Ollama服务正常")
            else:
                logger.error("❌ Ollama服务不可用")
                return
            
            logger.info("✅ 所有依赖检查通过，可以启动服务")
        else:
            # 正常启动服务
            asyncio.run(service.start_server())
            
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        exit_with_error(f"Ollama服务启动失败: {e}")

if __name__ == "__main__":
    main()