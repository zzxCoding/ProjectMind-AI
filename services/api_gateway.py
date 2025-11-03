#!/usr/bin/env python3
"""
API网关脚本
为Python脚本功能提供统一的HTTP API接口
"""

import sys
import os
import json
import asyncio
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import aiohttp
from aiohttp import web
import aiofiles
import logging
from pathlib import Path

# 动态获取项目根目录
project_root = Path(__file__).parent.parent.absolute()
sys.path.append(str(project_root))

# 自动检测基础路径
if os.path.exists('/app/logs'):
    base_path = '/app'  # 容器环境
    scripts_base_path = '/app/python-scripts'
else:
    base_path = str(Path(__file__).parent.parent.parent.absolute())  # 本地环境
    scripts_base_path = str(project_root)
from shared.utils import setup_logging, parse_arguments, format_timestamp, exit_with_error
from shared.database_client import DatabaseClient
from shared.ollama_client import OllamaClient

class APIGateway:
    """Python脚本API网关"""
    
    def __init__(self, host: str = "localhost", port: int = 9999):
        self.host = host
        self.port = port
        self.logger = setup_logging()
        
        # 脚本路径配置
        self.scripts_base_path = scripts_base_path
        
        # 初始化客户端
        self.db_client = DatabaseClient()
        self.ollama_client = OllamaClient()
        
        # 创建Web应用
        self.app = web.Application()
        self._setup_routes()
        self._setup_middleware()
        
        # API统计
        self.start_time = datetime.now()
        self.request_count = 0
        self.script_execution_count = 0
        self.active_executions = {}
    
    def _setup_routes(self):
        """设置路由"""
        # 基础接口
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/info', self.get_api_info)
        self.app.router.add_get('/scripts', self.list_available_scripts)
        
        # 数据分析API
        self.app.router.add_post('/api/v1/analysis/logs', self.analyze_logs)
        self.app.router.add_post('/api/v1/analysis/performance', self.analyze_performance)
        self.app.router.add_post('/api/v1/analysis/trends', self.analyze_trends)
        self.app.router.add_get('/api/v1/analysis/scripts/{script_id}/performance', self.get_script_performance)
        
        # 自动化API
        self.app.router.add_post('/api/v1/backup/create', self.create_backup)
        self.app.router.add_post('/api/v1/backup/restore', self.restore_backup)
        self.app.router.add_get('/api/v1/backup/list', self.list_backups)
        self.app.router.add_post('/api/v1/reports/generate', self.generate_report)
        self.app.router.add_post('/api/v1/notifications/send', self.send_notification)
        
        # 服务集成API
        self.app.router.add_post('/api/v1/ollama/analyze', self.ollama_analyze)
        self.app.router.add_get('/api/v1/ollama/models', self.ollama_models)
        
        # 脚本执行API
        self.app.router.add_post('/api/v1/execute/{script_name}', self.execute_script)
        self.app.router.add_get('/api/v1/execution/{execution_id}/status', self.get_execution_status)
        self.app.router.add_get('/api/v1/execution/{execution_id}/output', self.get_execution_output)
        
        # 批量操作API
        self.app.router.add_post('/api/v1/batch/analysis', self.batch_analysis)
        self.app.router.add_post('/api/v1/batch/health-check', self.batch_health_check)
        
        # 实时API
        self.app.router.add_get('/api/v1/realtime/dashboard', self.get_dashboard_data)
        self.app.router.add_get('/api/v1/realtime/alerts', self.get_active_alerts)
    
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
        
        @web.middleware
        async def error_handler_middleware(request, handler):
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"未处理的异常: {e}", exc_info=True)
                return web.json_response({
                    'error': 'Internal server error',
                    'message': str(e),
                    'timestamp': format_timestamp()
                }, status=500)
        
        self.app.middlewares.append(error_handler_middleware)
        self.app.middlewares.append(request_logger_middleware)
        self.app.middlewares.append(cors_middleware)
    
    async def health_check(self, request):
        """健康检查"""
        try:
            # 检查各个服务状态
            db_healthy = self.db_client.test_connection()
            ollama_healthy = self.ollama_client.health_check()
            
            # 检查脚本目录
            scripts_accessible = os.path.exists(self.scripts_base_path)
            
            all_healthy = db_healthy and ollama_healthy and scripts_accessible
            
            return web.json_response({
                'status': 'healthy' if all_healthy else 'degraded',
                'timestamp': format_timestamp(),
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'services': {
                    'database': db_healthy,
                    'ollama': ollama_healthy,
                    'scripts': scripts_accessible
                },
                'statistics': {
                    'total_requests': self.request_count,
                    'script_executions': self.script_execution_count,
                    'active_executions': len(self.active_executions)
                }
            })
        except Exception as e:
            return web.json_response({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': format_timestamp()
            }, status=500)
    
    async def get_api_info(self, request):
        """获取API信息"""
        return web.json_response({
            'service': 'Python Scripts API Gateway',
            'version': '1.0.0',
            'description': 'Unified API for Python script functionalities',
            'start_time': format_timestamp(self.start_time),
            'base_path': self.scripts_base_path,
            'endpoints': {
                'analysis': [
                    'POST /api/v1/analysis/logs',
                    'POST /api/v1/analysis/performance', 
                    'POST /api/v1/analysis/trends',
                    'GET /api/v1/analysis/scripts/{id}/performance'
                ],
                'automation': [
                    'POST /api/v1/backup/create',
                    'POST /api/v1/reports/generate',
                    'POST /api/v1/notifications/send'
                ],
                'execution': [
                    'POST /api/v1/execute/{script_name}',
                    'GET /api/v1/execution/{id}/status'
                ],
                'integration': [
                    'POST /api/v1/ollama/analyze',
                    'GET /api/v1/ollama/models'
                ]
            }
        })
    
    async def list_available_scripts(self, request):
        """列出可用脚本"""
        try:
            available_scripts = {
                'data_analysis': [
                    {
                        'name': 'log_analyzer',
                        'file': 'data_analysis/log_analyzer.py',
                        'description': '日志分析脚本',
                        'parameters': ['--log-path', '--script-id', '--batch']
                    },
                    {
                        'name': 'performance_monitor',
                        'file': 'data_analysis/performance_monitor.py',
                        'description': '性能监控脚本',
                        'parameters': ['--script-id', '--system', '--days']
                    },
                    {
                        'name': 'trend_analysis',
                        'file': 'data_analysis/trend_analysis.py',
                        'description': '趋势分析脚本',
                        'parameters': ['--type', '--days', '--script-id']
                    }
                ],
                'automation': [
                    {
                        'name': 'backup_processor',
                        'file': 'automation/backup_processor.py',
                        'description': '备份处理脚本',
                        'parameters': ['--action', '--type', '--backup-path']
                    },
                    {
                        'name': 'report_generator',
                        'file': 'automation/report_generator.py',
                        'description': '报告生成脚本',
                        'parameters': ['--type', '--output', '--format']
                    },
                    {
                        'name': 'notification_sender',
                        'file': 'automation/notification_sender.py',
                        'description': '通知发送脚本',
                        'parameters': ['--type', '--recipients', '--channels']
                    }
                ],
                'services': [
                    {
                        'name': 'ollama_service',
                        'file': 'services/ollama_service.py',
                        'description': 'Ollama AI分析服务',
                        'parameters': ['--host', '--port', '--test']
                    }
                ]
            }
            
            return web.json_response({
                'available_scripts': available_scripts,
                'total_scripts': sum(len(category) for category in available_scripts.values()),
                'base_path': self.scripts_base_path
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_logs(self, request):
        """日志分析API"""
        try:
            data = await request.json()
            log_path = data.get('log_path')
            script_id = data.get('script_id')
            batch_mode = data.get('batch', False)
            use_ai = data.get('use_ai', False)
            
            # 构建命令参数
            cmd_args = ['python3', f'{self.scripts_base_path}/data_analysis/log_analyzer.py']
            
            if log_path:
                cmd_args.extend(['--log-path', log_path])
            elif script_id:
                cmd_args.extend(['--script-id', str(script_id)])
            elif batch_mode:
                cmd_args.append('--batch')
            else:
                return web.json_response({'error': 'log_path, script_id, or batch mode required'}, status=400)
            
            if use_ai:
                cmd_args.append('--use-ai')
            
            cmd_args.extend(['--output-format', 'json'])
            
            # 执行脚本
            result = await self._execute_python_script(cmd_args)
            
            if result['success']:
                try:
                    analysis_result = json.loads(result['output'])
                    return web.json_response({
                        'status': 'success',
                        'analysis': analysis_result,
                        'execution_time': result['execution_time']
                    })
                except json.JSONDecodeError:
                    return web.json_response({
                        'status': 'success',
                        'raw_output': result['output'],
                        'execution_time': result['execution_time']
                    })
            else:
                return web.json_response({
                    'status': 'failed',
                    'error': result['error'],
                    'stderr': result['stderr']
                }, status=500)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_performance(self, request):
        """性能分析API"""
        try:
            data = await request.json()
            script_id = data.get('script_id')
            system_wide = data.get('system', False)
            days = data.get('days', 7)
            trend_analysis = data.get('trend', False)
            use_ai = data.get('use_ai', False)
            
            cmd_args = ['python3', f'{self.scripts_base_path}/data_analysis/performance_monitor.py']
            
            if script_id:
                cmd_args.extend(['--script-id', str(script_id)])
            elif system_wide:
                cmd_args.append('--system')
            elif trend_analysis:
                cmd_args.append('--trend')
            
            cmd_args.extend(['--days', str(days)])
            cmd_args.extend(['--output-format', 'json'])
            
            if use_ai:
                cmd_args.append('--use-ai')
            
            result = await self._execute_python_script(cmd_args)
            
            if result['success']:
                try:
                    analysis_result = json.loads(result['output'])
                    return web.json_response({
                        'status': 'success',
                        'analysis': analysis_result,
                        'execution_time': result['execution_time']
                    })
                except json.JSONDecodeError:
                    return web.json_response({
                        'status': 'success',
                        'raw_output': result['output'],
                        'execution_time': result['execution_time']
                    })
            else:
                return web.json_response({
                    'status': 'failed',
                    'error': result['error']
                }, status=500)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_trends(self, request):
        """趋势分析API"""
        try:
            data = await request.json()
            analysis_type = data.get('type', 'execution')
            script_id = data.get('script_id')
            days = data.get('days', 30)
            use_ai = data.get('use_ai', False)
            
            cmd_args = ['python3', f'{self.scripts_base_path}/data_analysis/trend_analysis.py']
            cmd_args.extend(['--type', analysis_type])
            cmd_args.extend(['--days', str(days)])
            cmd_args.extend(['--output-format', 'json'])
            
            if script_id:
                cmd_args.extend(['--script-id', str(script_id)])
            
            if use_ai:
                cmd_args.append('--use-ai')
            
            result = await self._execute_python_script(cmd_args)
            
            if result['success']:
                try:
                    analysis_result = json.loads(result['output'])
                    return web.json_response({
                        'status': 'success',
                        'analysis': analysis_result,
                        'execution_time': result['execution_time']
                    })
                except json.JSONDecodeError:
                    return web.json_response({
                        'status': 'success',
                        'raw_output': result['output']
                    })
            else:
                return web.json_response({
                    'status': 'failed',
                    'error': result['error']
                }, status=500)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_script_performance(self, request):
        """获取脚本性能数据"""
        try:
            script_id = request.match_info['script_id']
            days = int(request.query.get('days', '7'))
            
            # 直接从数据库获取数据
            executions = self.db_client.get_executions_by_script(int(script_id), 100)
            script_info = self.db_client.get_script_by_id(int(script_id))
            
            if not script_info:
                return web.json_response({'error': 'Script not found'}, status=404)
            
            # 计算性能指标
            total = len(executions)
            success_count = sum(1 for e in executions if e['status'] == 'SUCCESS')
            success_rate = (success_count / total * 100) if total > 0 else 0
            
            # 执行时间统计
            execution_times = []
            for execution in executions:
                if execution['start_time'] and execution['end_time']:
                    duration = (execution['end_time'] - execution['start_time']).total_seconds()
                    if duration > 0:
                        execution_times.append(duration)
            
            avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
            
            return web.json_response({
                'script_id': int(script_id),
                'script_name': script_info['name'],
                'description': script_info.get('description', ''),
                'performance_metrics': {
                    'total_executions': total,
                    'success_rate': success_rate,
                    'avg_execution_time': avg_time,
                    'min_execution_time': min(execution_times) if execution_times else 0,
                    'max_execution_time': max(execution_times) if execution_times else 0
                },
                'recent_executions': executions[:10],  # 最近10次执行
                'analysis_period': f'Last {days} days'
            })
        except ValueError:
            return web.json_response({'error': 'Invalid script_id'}, status=400)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def create_backup(self, request):
        """创建备份API"""
        try:
            data = await request.json()
            backup_type = data.get('type', 'incremental')
            since_hours = data.get('since_hours', 24)
            
            cmd_args = ['python3', f'{self.scripts_base_path}/automation/backup_processor.py']
            cmd_args.extend(['--action', 'backup'])
            cmd_args.extend(['--type', backup_type])
            cmd_args.extend(['--output-format', 'json'])
            
            if backup_type == 'incremental':
                cmd_args.extend(['--since-hours', str(since_hours)])
            
            result = await self._execute_python_script(cmd_args)
            
            if result['success']:
                try:
                    backup_result = json.loads(result['output'])
                    return web.json_response({
                        'status': 'success',
                        'backup': backup_result,
                        'execution_time': result['execution_time']
                    })
                except json.JSONDecodeError:
                    return web.json_response({
                        'status': 'success',
                        'message': 'Backup completed',
                        'raw_output': result['output']
                    })
            else:
                return web.json_response({
                    'status': 'failed',
                    'error': result['error']
                }, status=500)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def restore_backup(self, request):
        """恢复备份API"""
        try:
            data = await request.json()
            backup_path = data.get('backup_path')
            components = data.get('components', ['scripts', 'logs', 'database'])
            
            if not backup_path:
                return web.json_response({'error': 'backup_path required'}, status=400)
            
            cmd_args = ['python3', f'{self.scripts_base_path}/automation/backup_processor.py']
            cmd_args.extend(['--action', 'restore'])
            cmd_args.extend(['--backup-path', backup_path])
            cmd_args.extend(['--components'] + components)
            cmd_args.extend(['--output-format', 'json'])
            
            result = await self._execute_python_script(cmd_args)
            
            if result['success']:
                return web.json_response({
                    'status': 'success',
                    'message': 'Restore completed',
                    'output': result['output']
                })
            else:
                return web.json_response({
                    'status': 'failed',
                    'error': result['error']
                }, status=500)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def list_backups(self, request):
        """列出备份API"""
        try:
            cmd_args = ['python3', f'{self.scripts_base_path}/automation/backup_processor.py']
            cmd_args.extend(['--action', 'list'])
            cmd_args.extend(['--output-format', 'json'])
            
            result = await self._execute_python_script(cmd_args)
            
            if result['success']:
                try:
                    backup_list = json.loads(result['output'])
                    return web.json_response({
                        'status': 'success',
                        'backups': backup_list
                    })
                except json.JSONDecodeError:
                    return web.json_response({
                        'status': 'success',
                        'raw_output': result['output']
                    })
            else:
                return web.json_response({
                    'status': 'failed',
                    'error': result['error']
                }, status=500)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def generate_report(self, request):
        """生成报告API"""
        try:
            data = await request.json()
            report_type = data.get('type', 'daily')
            output_format = data.get('format', 'json')
            target_date = data.get('date')
            use_ai = data.get('use_ai', False)
            
            cmd_args = ['python3', f'{self.scripts_base_path}/automation/report_generator.py']
            cmd_args.extend(['--type', report_type])
            cmd_args.extend(['--format', output_format])
            
            if target_date:
                cmd_args.extend(['--date', target_date])
            
            if use_ai:
                cmd_args.append('--use-ai')
            
            result = await self._execute_python_script(cmd_args)
            
            if result['success']:
                if output_format == 'json':
                    try:
                        report_data = json.loads(result['output'])
                        return web.json_response({
                            'status': 'success',
                            'report': report_data
                        })
                    except json.JSONDecodeError:
                        return web.json_response({
                            'status': 'success',
                            'raw_output': result['output']
                        })
                else:
                    return web.json_response({
                        'status': 'success',
                        'report_content': result['output'],
                        'format': output_format
                    })
            else:
                return web.json_response({
                    'status': 'failed',
                    'error': result['error']
                }, status=500)
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def send_notification(self, request):
        """发送通知API"""
        try:
            data = await request.json()
            notification_type = data.get('type', 'custom')
            recipients = data.get('recipients', [])
            channels = data.get('channels', ['email'])
            subject = data.get('subject', '')
            message = data.get('message', '')
            priority = data.get('priority', 'normal')
            
            if not recipients:
                return web.json_response({'error': 'recipients required'}, status=400)
            
            cmd_args = ['python3', f'{self.scripts_base_path}/automation/notification_sender.py']
            cmd_args.extend(['--type', notification_type])
            cmd_args.extend(['--recipients'] + recipients)
            cmd_args.extend(['--channels'] + channels)
            cmd_args.extend(['--priority', priority])
            
            if subject:
                cmd_args.extend(['--subject', subject])
            if message:
                cmd_args.extend(['--message', message])
            
            result = await self._execute_python_script(cmd_args)
            
            return web.json_response({
                'status': 'success' if result['success'] else 'failed',
                'result': result['output'],
                'execution_time': result['execution_time']
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def ollama_analyze(self, request):
        """Ollama分析API"""
        try:
            data = await request.json()
            text = data.get('text', '')
            analysis_type = data.get('type', 'summary')
            model = data.get('model')
            
            if not text:
                return web.json_response({'error': 'text required'}, status=400)
            
            result = self.ollama_client.analyze_text(text, model, analysis_type)
            
            return web.json_response({
                'status': 'success',
                'analysis_type': analysis_type,
                'model': model or self.ollama_client.config.default_model,
                'result': result,
                'timestamp': format_timestamp()
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def ollama_models(self, request):
        """获取Ollama模型列表API"""
        try:
            models = self.ollama_client.list_models()
            return web.json_response({
                'status': 'success',
                'models': models,
                'total': len(models)
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def execute_script(self, request):
        """执行脚本API"""
        try:
            script_name = request.match_info['script_name']
            data = await request.json() if request.can_read_body else {}
            
            # 获取参数
            parameters = data.get('parameters', [])
            async_execution = data.get('async', True)
            
            # 构建脚本路径
            script_mapping = {
                'log_analyzer': 'data_analysis/log_analyzer.py',
                'performance_monitor': 'data_analysis/performance_monitor.py',
                'trend_analysis': 'data_analysis/trend_analysis.py',
                'backup_processor': 'automation/backup_processor.py',
                'report_generator': 'automation/report_generator.py',
                'notification_sender': 'automation/notification_sender.py'
            }
            
            if script_name not in script_mapping:
                return web.json_response({'error': f'Unknown script: {script_name}'}, status=404)
            
            script_path = f'{self.scripts_base_path}/{script_mapping[script_name]}'
            cmd_args = ['python3', script_path] + parameters
            
            if async_execution:
                # 异步执行
                execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                
                # 启动后台任务
                task = asyncio.create_task(self._execute_python_script(cmd_args))
                self.active_executions[execution_id] = {
                    'task': task,
                    'script_name': script_name,
                    'start_time': datetime.now(),
                    'status': 'running',
                    'parameters': parameters
                }
                
                return web.json_response({
                    'status': 'accepted',
                    'execution_id': execution_id,
                    'message': 'Script execution started',
                    'async': True
                })
            else:
                # 同步执行
                result = await self._execute_python_script(cmd_args)
                return web.json_response({
                    'status': 'completed',
                    'result': result,
                    'async': False
                })
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_execution_status(self, request):
        """获取执行状态API"""
        try:
            execution_id = request.match_info['execution_id']
            
            if execution_id not in self.active_executions:
                return web.json_response({'error': 'Execution not found'}, status=404)
            
            execution = self.active_executions[execution_id]
            task = execution['task']
            
            if task.done():
                # 任务已完成
                try:
                    result = await task
                    execution['status'] = 'completed'
                    execution['result'] = result
                    execution['end_time'] = datetime.now()
                    
                    return web.json_response({
                        'execution_id': execution_id,
                        'status': 'completed',
                        'result': result,
                        'start_time': format_timestamp(execution['start_time']),
                        'end_time': format_timestamp(execution['end_time']),
                        'duration': (execution['end_time'] - execution['start_time']).total_seconds()
                    })
                except Exception as e:
                    execution['status'] = 'failed'
                    execution['error'] = str(e)
                    execution['end_time'] = datetime.now()
                    
                    return web.json_response({
                        'execution_id': execution_id,
                        'status': 'failed',
                        'error': str(e),
                        'start_time': format_timestamp(execution['start_time']),
                        'end_time': format_timestamp(execution['end_time'])
                    })
            else:
                # 任务仍在运行
                return web.json_response({
                    'execution_id': execution_id,
                    'status': 'running',
                    'script_name': execution['script_name'],
                    'start_time': format_timestamp(execution['start_time']),
                    'duration': (datetime.now() - execution['start_time']).total_seconds()
                })
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_execution_output(self, request):
        """获取执行输出API"""
        try:
            execution_id = request.match_info['execution_id']
            
            if execution_id not in self.active_executions:
                return web.json_response({'error': 'Execution not found'}, status=404)
            
            execution = self.active_executions[execution_id]
            
            if execution['status'] == 'completed':
                return web.json_response({
                    'execution_id': execution_id,
                    'status': 'completed',
                    'output': execution.get('result', {}).get('output', ''),
                    'stderr': execution.get('result', {}).get('stderr', ''),
                    'success': execution.get('result', {}).get('success', False)
                })
            elif execution['status'] == 'failed':
                return web.json_response({
                    'execution_id': execution_id,
                    'status': 'failed',
                    'error': execution.get('error', 'Unknown error')
                })
            else:
                return web.json_response({
                    'execution_id': execution_id,
                    'status': 'running',
                    'message': 'Execution still in progress'
                })
                
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def batch_analysis(self, request):
        """批量分析API"""
        try:
            data = await request.json()
            analysis_tasks = data.get('tasks', [])
            
            if not analysis_tasks:
                return web.json_response({'error': 'tasks required'}, status=400)
            
            results = []
            for task in analysis_tasks:
                task_type = task.get('type')
                task_params = task.get('parameters', {})
                
                try:
                    if task_type == 'log_analysis':
                        # 执行日志分析
                        cmd_args = ['python3', f'{self.scripts_base_path}/data_analysis/log_analyzer.py']
                        if task_params.get('log_path'):
                            cmd_args.extend(['--log-path', task_params['log_path']])
                        cmd_args.extend(['--output-format', 'json'])
                        
                        result = await self._execute_python_script(cmd_args)
                        results.append({
                            'task_type': task_type,
                            'status': 'success' if result['success'] else 'failed',
                            'result': result['output'] if result['success'] else result['error']
                        })
                    
                    elif task_type == 'performance_analysis':
                        # 执行性能分析
                        cmd_args = ['python3', f'{self.scripts_base_path}/data_analysis/performance_monitor.py']
                        if task_params.get('script_id'):
                            cmd_args.extend(['--script-id', str(task_params['script_id'])])
                        else:
                            cmd_args.append('--system')
                        cmd_args.extend(['--output-format', 'json'])
                        
                        result = await self._execute_python_script(cmd_args)
                        results.append({
                            'task_type': task_type,
                            'status': 'success' if result['success'] else 'failed',
                            'result': result['output'] if result['success'] else result['error']
                        })
                    
                    else:
                        results.append({
                            'task_type': task_type,
                            'status': 'failed',
                            'error': f'Unsupported task type: {task_type}'
                        })
                        
                except Exception as e:
                    results.append({
                        'task_type': task_type,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            return web.json_response({
                'status': 'completed',
                'total_tasks': len(analysis_tasks),
                'successful_tasks': sum(1 for r in results if r['status'] == 'success'),
                'results': results
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def batch_health_check(self, request):
        """批量健康检查API"""
        try:
            data = await request.json() if request.can_read_body else {}
            script_ids = data.get('script_ids', [])
            
            # 如果没有指定脚本ID，检查所有脚本
            if not script_ids:
                scripts = self.db_client.get_all_scripts()
                script_ids = [s['id'] for s in scripts]
            
            health_results = []
            for script_id in script_ids:
                try:
                    # 获取脚本最近的执行记录
                    executions = self.db_client.get_executions_by_script(script_id, 20)
                    
                    if executions:
                        success_count = sum(1 for e in executions if e['status'] == 'SUCCESS')
                        success_rate = (success_count / len(executions)) * 100
                        
                        # 计算平均执行时间
                        execution_times = []
                        for execution in executions:
                            if execution['start_time'] and execution['end_time']:
                                duration = (execution['end_time'] - execution['start_time']).total_seconds()
                                if duration > 0:
                                    execution_times.append(duration)
                        
                        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
                        
                        # 健康评级
                        if success_rate >= 90 and avg_time < 30:
                            health_grade = 'excellent'
                        elif success_rate >= 80 and avg_time < 60:
                            health_grade = 'good'
                        elif success_rate >= 70:
                            health_grade = 'warning'
                        else:
                            health_grade = 'critical'
                        
                        health_results.append({
                            'script_id': script_id,
                            'script_name': executions[0].get('script_name', f'Script_{script_id}'),
                            'health_grade': health_grade,
                            'success_rate': success_rate,
                            'avg_execution_time': avg_time,
                            'recent_executions': len(executions),
                            'last_execution': format_timestamp(executions[0]['start_time']) if executions else None
                        })
                    else:
                        health_results.append({
                            'script_id': script_id,
                            'health_grade': 'unknown',
                            'message': 'No execution history found'
                        })
                        
                except Exception as e:
                    health_results.append({
                        'script_id': script_id,
                        'health_grade': 'error',
                        'error': str(e)
                    })
            
            # 整体健康状况汇总
            grade_counts = {}
            for result in health_results:
                grade = result.get('health_grade', 'unknown')
                grade_counts[grade] = grade_counts.get(grade, 0) + 1
            
            return web.json_response({
                'overall_health': {
                    'total_scripts': len(script_ids),
                    'grade_distribution': grade_counts,
                    'healthy_percentage': (grade_counts.get('excellent', 0) + grade_counts.get('good', 0)) / len(script_ids) * 100 if script_ids else 0
                },
                'script_health': health_results,
                'timestamp': format_timestamp()
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_dashboard_data(self, request):
        """获取仪表板数据API"""
        try:
            # 获取系统概览数据
            stats_24h = self.db_client.get_execution_stats(1)
            stats_7d = self.db_client.get_execution_stats(7)
            recent_executions = self.db_client.get_recent_executions(20)
            
            # 计算趋势
            success_rate_24h = (stats_24h.get('success_count', 0) / max(stats_24h.get('total_executions', 1), 1)) * 100
            success_rate_7d = (stats_7d.get('success_count', 0) / max(stats_7d.get('total_executions', 1), 1)) * 100
            
            # 活跃脚本统计
            active_scripts = len(set(e['script_id'] for e in recent_executions))
            
            # 最近失败的执行
            recent_failures = [e for e in recent_executions if e['status'] == 'FAILED']
            
            dashboard_data = {
                'system_overview': {
                    'total_executions_24h': stats_24h.get('total_executions', 0),
                    'success_rate_24h': success_rate_24h,
                    'success_rate_7d': success_rate_7d,
                    'trend': 'up' if success_rate_24h > success_rate_7d else 'down' if success_rate_24h < success_rate_7d else 'stable'
                },
                'active_scripts': active_scripts,
                'recent_failures': len(recent_failures),
                'system_health': {
                    'database': self.db_client.test_connection(),
                    'ollama': self.ollama_client.health_check(),
                    'api_gateway': True
                },
                'recent_activity': [
                    {
                        'script_name': e.get('script_name', f"Script_{e['script_id']}"),
                        'status': e['status'],
                        'start_time': format_timestamp(e['start_time']),
                        'duration': (e['end_time'] - e['start_time']).total_seconds() if e.get('end_time') else None
                    }
                    for e in recent_executions[:10]
                ],
                'api_statistics': {
                    'total_requests': self.request_count,
                    'script_executions': self.script_execution_count,
                    'active_executions': len(self.active_executions),
                    'uptime_hours': (datetime.now() - self.start_time).total_seconds() / 3600
                },
                'timestamp': format_timestamp()
            }
            
            return web.json_response(dashboard_data)
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_active_alerts(self, request):
        """获取活跃告警API"""
        try:
            # 检查需要告警的情况
            alerts = []
            
            # 检查最近的失败
            recent_executions = self.db_client.get_recent_executions(50)
            recent_failures = [e for e in recent_executions if e['status'] == 'FAILED']
            
            if len(recent_failures) > 5:
                alerts.append({
                    'type': 'high_failure_rate',
                    'severity': 'warning',
                    'message': f'最近有{len(recent_failures)}个脚本执行失败',
                    'count': len(recent_failures),
                    'timestamp': format_timestamp()
                })
            
            # 检查长时间运行的脚本
            long_running = []
            for execution_id, execution in self.active_executions.items():
                duration = (datetime.now() - execution['start_time']).total_seconds()
                if duration > 300:  # 5分钟
                    long_running.append({
                        'execution_id': execution_id,
                        'script_name': execution['script_name'],
                        'duration': duration
                    })
            
            if long_running:
                alerts.append({
                    'type': 'long_running_scripts',
                    'severity': 'info',
                    'message': f'{len(long_running)}个脚本执行时间超过5分钟',
                    'scripts': long_running,
                    'timestamp': format_timestamp()
                })
            
            # 检查系统健康
            if not self.db_client.test_connection():
                alerts.append({
                    'type': 'database_connectivity',
                    'severity': 'critical',
                    'message': '数据库连接异常',
                    'timestamp': format_timestamp()
                })
            
            if not self.ollama_client.health_check():
                alerts.append({
                    'type': 'ollama_connectivity',
                    'severity': 'warning',
                    'message': 'Ollama服务不可用',
                    'timestamp': format_timestamp()
                })
            
            return web.json_response({
                'total_alerts': len(alerts),
                'alerts': alerts,
                'system_status': 'critical' if any(a['severity'] == 'critical' for a in alerts) else 'warning' if alerts else 'normal',
                'last_check': format_timestamp()
            })
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def _execute_python_script(self, cmd_args: List[str]) -> Dict[str, Any]:
        """执行Python脚本"""
        start_time = datetime.now()
        self.script_execution_count += 1
        
        try:
            self.logger.info(f"执行脚本: {' '.join(cmd_args)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.scripts_base_path
            )
            
            stdout, stderr = await process.communicate()
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'success': process.returncode == 0,
                'output': stdout.decode('utf-8'),
                'stderr': stderr.decode('utf-8'),
                'return_code': process.returncode,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"脚本执行失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'output': '',
                'stderr': '',
                'return_code': -1,
                'execution_time': execution_time
            }
    
    async def start_server(self):
        """启动API网关服务"""
        self.logger.info(f"启动API网关服务: http://{self.host}:{self.port}")
        
        # 清理过期的执行记录
        asyncio.create_task(self._cleanup_executions_periodically())
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        self.logger.info("API网关服务启动成功")
        self.logger.info("可用的API端点:")
        for route in self.app.router.routes():
            self.logger.info(f"  {route.method} {route.resource}")
        
        try:
            await asyncio.Future()  # run forever
        except KeyboardInterrupt:
            self.logger.info("收到停止信号")
        finally:
            await runner.cleanup()
            self.logger.info("API网关服务已停止")
    
    async def _cleanup_executions_periodically(self):
        """定期清理过期的执行记录"""
        while True:
            try:
                current_time = datetime.now()
                expired_executions = []
                
                for execution_id, execution in self.active_executions.items():
                    # 清理超过1小时的已完成执行
                    if execution.get('end_time') and (current_time - execution['end_time']).total_seconds() > 3600:
                        expired_executions.append(execution_id)
                    # 清理超过6小时的运行中执行（可能已死锁）
                    elif (current_time - execution['start_time']).total_seconds() > 21600:
                        expired_executions.append(execution_id)
                
                for execution_id in expired_executions:
                    del self.active_executions[execution_id]
                    self.logger.info(f"清理过期执行记录: {execution_id}")
                
                # 每10分钟清理一次
                await asyncio.sleep(600)
                
            except Exception as e:
                self.logger.error(f"清理执行记录时发生错误: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟再试

def main():
    """主函数"""
    parser = parse_arguments("Python脚本API网关")
    parser.add_argument('--host', default='localhost', help='服务绑定地址')
    parser.add_argument('--port', type=int, default=9999, help='服务端口')
    parser.add_argument('--test', action='store_true', help='测试模式（检查依赖）')
    
    args = parser.parse_args()
    
    # 设置日志级别
    logger = setup_logging(args.log_level)
    
    try:
        gateway = APIGateway(args.host, args.port)
        
        if args.test:
            # 测试模式
            logger.info("测试模式 - 检查系统依赖")
            
            # 检查数据库连接
            if gateway.db_client.test_connection():
                logger.info("✅ 数据库连接正常")
            else:
                logger.error("❌ 数据库连接失败")
            
            # 检查Ollama连接
            if gateway.ollama_client.health_check():
                logger.info("✅ Ollama服务正常")
            else:
                logger.warning("⚠️  Ollama服务不可用（部分功能将受限）")
            
            # 检查脚本目录
            if os.path.exists(gateway.scripts_base_path):
                logger.info("✅ Python脚本目录可访问")
                
                # 列出可用脚本
                scripts = [
                    'data_analysis/log_analyzer.py',
                    'data_analysis/performance_monitor.py', 
                    'data_analysis/trend_analysis.py',
                    'automation/backup_processor.py',
                    'automation/report_generator.py',
                    'automation/notification_sender.py'
                ]
                
                available_scripts = []
                for script in scripts:
                    script_path = os.path.join(gateway.scripts_base_path, script)
                    if os.path.exists(script_path):
                        available_scripts.append(script)
                
                logger.info(f"✅ 可用脚本数量: {len(available_scripts)}")
                for script in available_scripts:
                    logger.info(f"  - {script}")
                    
                if len(available_scripts) < len(scripts):
                    missing = set(scripts) - set(available_scripts)
                    logger.warning(f"⚠️  缺失脚本: {missing}")
            else:
                logger.error("❌ Python脚本目录不存在")
            
            logger.info("依赖检查完成")
        else:
            # 启动服务
            asyncio.run(gateway.start_server())
            
    except Exception as e:
        logger.error(f"API网关启动失败: {e}")
        exit_with_error(f"API网关启动失败: {e}")

if __name__ == "__main__":
    main()