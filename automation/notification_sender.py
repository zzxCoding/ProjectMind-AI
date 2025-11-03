#!/usr/bin/env python3
"""
通知发送脚本
发送各种类型的通知（邮件、微信、钉钉等）
"""

import sys
import os
import json
import smtplib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.header import Header
from email import encoders
import tempfile

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from shared.config_loader import setup_environment
setup_environment()
from shared.utils import setup_logging, parse_arguments, format_timestamp, exit_with_error, exit_with_success
from shared.database_client import DatabaseClient

class NotificationSender:
    """通知发送器"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.db_client = DatabaseClient()
        
        # 通知配置（从环境变量或配置文件读取）
        self.config = {
            'email': {
                'smtp_server': os.getenv('SMTP_SERVER', 'smtp.qq.com'),
                'smtp_port': int(os.getenv('SMTP_PORT', '587')),
                'username': os.getenv('EMAIL_USERNAME', ''),
                'password': os.getenv('EMAIL_PASSWORD', ''),
                'from_name': os.getenv('EMAIL_FROM_NAME', 'ProjectMind-AI'),
                'enabled': os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
            },
            'wechat': {
                'webhook_url': os.getenv('WECHAT_WEBHOOK', ''),
                'enabled': os.getenv('WECHAT_ENABLED', 'false').lower() == 'true'
            },
            'dingtalk': {
                'webhook_url': os.getenv('DINGTALK_WEBHOOK', ''),
                'secret': os.getenv('DINGTALK_SECRET', ''),
                'enabled': os.getenv('DINGTALK_ENABLED', 'false').lower() == 'true'
            },
            'slack': {
                'webhook_url': os.getenv('SLACK_WEBHOOK', ''),
                'enabled': os.getenv('SLACK_ENABLED', 'false').lower() == 'true'
            }
        }
    
    def send_script_failure_alert(self, script_id: int, execution_id: int, 
                                 recipients: List[str], channels: List[str] = None) -> Dict[str, Any]:
        """
        发送脚本失败告警
        
        Args:
            script_id: 脚本ID
            execution_id: 执行记录ID
            recipients: 收件人列表
            channels: 发送渠道列表
            
        Returns:
            发送结果
        """
        # 获取脚本和执行信息
        script_info = self.db_client.get_script_by_id(script_id)
        executions = self.db_client.get_executions_by_script(script_id, 1)
        execution_info = executions[0] if executions else None
        
        if not script_info or not execution_info:
            return {'error': '无法获取脚本或执行信息'}
        
        # 构建告警消息
        alert_data = {
            'type': 'script_failure',
            'script_name': script_info['name'],
            'script_id': script_id,
            'execution_id': execution_id,
            'failure_time': execution_info['start_time'],
            'description': script_info.get('description', ''),
            'log_path': execution_info.get('log_path', ''),
            'severity': 'high'
        }
        
        subject = f"🚨 脚本执行失败告警: {script_info['name']}"
        message = self._build_failure_message(alert_data)
        
        return self._send_notifications(subject, message, recipients, channels)
    
    def send_system_health_report(self, recipients: List[str], 
                                channels: List[str] = None) -> Dict[str, Any]:
        """
        发送系统健康报告
        
        Args:
            recipients: 收件人列表
            channels: 发送渠道列表
            
        Returns:
            发送结果
        """
        # 获取系统统计信息
        stats = self.db_client.get_execution_stats(1)  # 最近24小时
        recent_executions = self.db_client.get_recent_executions(50)
        
        # 计算健康指标
        health_data = self._calculate_system_health(stats, recent_executions)
        
        subject = f"📊 系统健康报告 - {datetime.now().strftime('%Y-%m-%d')}"
        message = self._build_health_report_message(health_data)
        
        return self._send_notifications(subject, message, recipients, channels)
    
    def send_scheduled_report(self, report_type: str, recipients: List[str],
                            channels: List[str] = None) -> Dict[str, Any]:
        """
        发送定时报告
        
        Args:
            report_type: 报告类型 (daily, weekly, monthly)
            recipients: 收件人列表
            channels: 发送渠道列表
            
        Returns:
            发送结果
        """
        # 生成报告数据
        if report_type == 'daily':
            report_data = self._generate_daily_summary()
        elif report_type == 'weekly':
            report_data = self._generate_weekly_summary()
        elif report_type == 'monthly':
            report_data = self._generate_monthly_summary()
        else:
            return {'error': f'不支持的报告类型: {report_type}'}
        
        subject = f"📈 {report_type.upper()}运行报告 - {datetime.now().strftime('%Y-%m-%d')}"
        message = self._build_report_message(report_type, report_data)
        
        return self._send_notifications(subject, message, recipients, channels)
    
    def send_custom_notification(self, subject: str, message: str, 
                               recipients: List[str], channels: List[str] = None,
                               priority: str = 'normal') -> Dict[str, Any]:
        """
        发送自定义通知
        
        Args:
            subject: 主题
            message: 消息内容
            recipients: 收件人列表
            channels: 发送渠道列表
            priority: 优先级 (low, normal, high, urgent)
            
        Returns:
            发送结果
        """
        # 添加优先级标识
        priority_icons = {
            'low': '🔵',
            'normal': '⚪',
            'high': '🟠',
            'urgent': '🔴'
        }
        
        subject_with_priority = f"{priority_icons.get(priority, '⚪')} {subject}"
        
        return self._send_notifications(subject_with_priority, message, recipients, channels)
    
    def send_html_email(self, subject: str, html_content: str, recipients: List[str]) -> Dict[str, Any]:
        """
        发送HTML格式邮件
        
        Args:
            subject: 邮件主题
            html_content: HTML内容
            recipients: 收件人列表
            
        Returns:
            发送结果
        """
        if not self.config['email']['enabled']:
            return {
                'success': False,
                'error': '邮件功能未启用',
                'message': '邮件功能未启用'
            }
        
        return self._send_email(subject, html_content, recipients, is_html=True)
    
    def send_html_email_with_attachment(self, subject: str, html_content: str, 
                                       recipients: List[str], attachment_content: str = None, 
                                       attachment_filename: str = None) -> Dict[str, Any]:
        """
        发送带附件的HTML格式邮件
        
        Args:
            subject: 邮件主题
            html_content: HTML内容
            recipients: 收件人列表
            attachment_content: 附件内容（文本）
            attachment_filename: 附件文件名
            
        Returns:
            发送结果
        """
        if not self.config['email']['enabled']:
            return {
                'success': False,
                'error': '邮件功能未启用',
                'message': '邮件功能未启用'
            }
        
        return self._send_email_with_attachment(subject, html_content, recipients, 
                                              attachment_content, attachment_filename, is_html=True)
    
    def test_email_config(self) -> Dict[str, Any]:
        """
        测试邮件配置
        
        Returns:
            测试结果
        """
        import socket
        import time
        
        config = self.config['email']
        results = {
            'config_valid': False,
            'dns_resolution': False,
            'port_connection': False,
            'smtp_connection': False,
            'authentication': False,
            'overall_success': False,
            'details': [],
            'recommendations': []
        }
        
        try:
            # 1. 检查配置完整性
            self.logger.info("🔍 步靄1: 检查邮件配置...")
            missing = []
            if not config['enabled']:
                results['details'].append("❌ 邮件功能未启用")
                return results
            if not config['smtp_server']:
                missing.append('SMTP_SERVER')
            if not config['username']:
                missing.append('EMAIL_USERNAME')
            if not config['password']:
                missing.append('EMAIL_PASSWORD')
                
            if missing:
                results['details'].append(f"❌ 缺少配置: {', '.join(missing)}")
                results['recommendations'].append("设置缺少的环境变量")
                return results
                
            results['config_valid'] = True
            results['details'].append("✅ 邮件配置完整")
            
            # 2. DNS解析测试
            self.logger.info("🔍 步靄2: DNS解析测试...")
            try:
                start_time = time.time()
                ip_address = socket.gethostbyname(config['smtp_server'])
                dns_time = time.time() - start_time
                results['dns_resolution'] = True
                results['details'].append(f"✅ DNS解析成功: {config['smtp_server']} -> {ip_address} ({dns_time:.2f}s)")
            except socket.gaierror as e:
                results['details'].append(f"❌ DNS解析失败: {e}")
                results['recommendations'].append("检查SMTP服务器地址是否正确")
                return results
            
            # 3. 端口连接测试
            self.logger.info("🔍 步靄3: 端口连接测试...")
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(10)
                start_time = time.time()
                test_socket.connect((config['smtp_server'], config['smtp_port']))
                connect_time = time.time() - start_time
                test_socket.close()
                results['port_connection'] = True
                results['details'].append(f"✅ 端口连接成功 ({connect_time:.2f}s)")
            except socket.error as e:
                results['details'].append(f"❌ 端口连接失败: {e}")
                results['recommendations'].append(f"检查SMTP端口{config['smtp_port']}是否正确")
                if config['smtp_port'] == 25:
                    results['recommendations'].append("尝试使用端口587或465")
                return results
            
            # 4. SMTP连接测试
            self.logger.info("🔍 步靄4: SMTP连接测试...")
            try:
                # 尝试不同的SMTP连接方式
                server = None
                smtp_success = False
                
                # 方法1: 标准SMTP + STARTTLS
                try:
                    self.logger.info("  尝试方式1: SMTP + STARTTLS")
                    server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=15)
                    server.set_debuglevel(1)  # 启用调试输出查看详细信息
                    server.starttls()
                    server.set_debuglevel(0)  # 关闭调试输出
                    smtp_success = True
                    results['details'].append("✅ SMTP连接成功（STARTTLS模式）")
                except Exception as e1:
                    results['details'].append(f"  ⚠️ STARTTLS方式失败: {e1}")
                    if server:
                        try:
                            server.quit()
                        except:
                            pass
                    server = None
                
                # 方法2: 直接SSL连接（如果端口是465）
                if not smtp_success and config['smtp_port'] == 465:
                    try:
                        self.logger.info("  尝试方式2: SMTP_SSL")
                        server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=15)
                        smtp_success = True
                        results['details'].append("✅ SMTP连接成功（SSL模式）")
                    except Exception as e2:
                        results['details'].append(f"  ⚠️ SSL方式失败: {e2}")
                        if server:
                            try:
                                server.quit()
                            except:
                                pass
                        server = None
                
                if smtp_success:
                    results['smtp_connection'] = True
                else:
                    raise Exception("所有SMTP连接方式都失败")
                
                # 5. 认证测试
                self.logger.info("🔍 步靄5: 认证测试...")
                try:
                    server.login(config['username'], config['password'])
                    results['authentication'] = True
                    results['details'].append("✅ SMTP认证成功")
                    results['overall_success'] = True
                except smtplib.SMTPAuthenticationError as e:
                    results['details'].append(f"❌ SMTP认证失败: {e}")
                    results['recommendations'].append("检查用户名和密码")
                    if 'qq.com' in config['smtp_server']:
                        results['recommendations'].append("使用QQ邮箱的应用专用密码而不是登录密码")
                    elif 'gmail.com' in config['smtp_server']:
                        results['recommendations'].append("使用Gmail的应用密码而不是账户密码")
                        
                server.quit()
                
            except Exception as e:
                results['details'].append(f"❌ SMTP连接失败: {e}")
                
                # 根据错误类型提供具体建议
                error_str = str(e).lower()
                if 'timed out' in error_str or 'timeout' in error_str:
                    results['recommendations'].extend([
                        "尝试使用不同的SMTP端口：587（STARTTLS）或 465（SSL）",
                        "检查公司防火墙是否允许SMTP连接",
                        "联系邮件服务器管理员确认服务状态",
                        f"尝试命令行测试: telnet {config['smtp_server']} {config['smtp_port']}"
                    ])
                elif 'connection refused' in error_str:
                    results['recommendations'].extend([
                        "检查SMTP端口是否正确",
                        "确认SMTP服务器允许外部连接"
                    ])
                elif 'ssl' in error_str or 'tls' in error_str:
                    results['recommendations'].extend([
                        "检查SSL/TLS证书配置",
                        "尝试禁用SSL验证（仅测试用）"
                    ])
                else:
                    results['recommendations'].append("检查SMTP服务器设置和TLS支持")
                    
                # 提供常见邮件服务商的配置建议
                if 'kayak.com.cn' in config['smtp_server']:
                    results['recommendations'].extend([
                        "联系公司IT部门确认内部SMTP服务器配置",
                        "检查是否需要VPN或内网环境才能访问",
                        "确认SMTP服务器是否支持外部连接"
                    ])
                elif 'qq.com' in config['smtp_server']:
                    results['recommendations'].extend([
                        "确认使用端口587和应用专用密码",
                        "在QQ邮箱设置中启用SMTP服务"
                    ])
                
        except Exception as e:
            results['details'].append(f"❌ 测试异常: {e}")
            
        return results
    
    def _send_notifications(self, subject: str, message: str, recipients: List[str],
                          channels: List[str] = None) -> Dict[str, Any]:
        """
        发送通知到多个渠道
        
        Args:
            subject: 主题
            message: 消息内容
            recipients: 收件人列表
            channels: 发送渠道列表
            
        Returns:
            发送结果汇总
        """
        if channels is None:
            channels = ['email']  # 默认发送邮件
        
        results = {
            'timestamp': format_timestamp(),
            'subject': subject,
            'recipients': recipients,
            'channels_attempted': channels,
            'results': {}
        }
        
        # 发送邮件
        if 'email' in channels and self.config['email']['enabled']:
            email_result = self._send_email(subject, message, recipients, is_html=False)
            results['results']['email'] = email_result
        
        # 发送微信
        if 'wechat' in channels and self.config['wechat']['enabled']:
            wechat_result = self._send_wechat(message)
            results['results']['wechat'] = wechat_result
        
        # 发送钉钉
        if 'dingtalk' in channels and self.config['dingtalk']['enabled']:
            dingtalk_result = self._send_dingtalk(subject, message)
            results['results']['dingtalk'] = dingtalk_result
        
        # 发送Slack
        if 'slack' in channels and self.config['slack']['enabled']:
            slack_result = self._send_slack(subject, message)
            results['results']['slack'] = slack_result
        
        # 统计成功失败
        success_count = sum(1 for result in results['results'].values() if result.get('success', False))
        results['summary'] = {
            'total_channels': len(results['results']),
            'successful_channels': success_count,
            'failed_channels': len(results['results']) - success_count,
            'overall_success': success_count > 0
        }
        
        return results
    
    def _send_email(self, subject: str, message: str, recipients: List[str], 
                    is_html: bool = False) -> Dict[str, Any]:
        """发送邮件（支持HTML格式和超时处理）"""
        import socket
        from time import sleep
        
        try:
            config = self.config['email']
            
            # 详细的邮件配置诊断
            self.logger.info("=== 邮件配置诊断 ===")
            self.logger.info(f"SMTP服务器: {config['smtp_server']}")
            self.logger.info(f"SMTP端口: {config['smtp_port']}")
            self.logger.info(f"发件人: {config['from_name']} <{config['username']}>")
            self.logger.info(f"收件人: {', '.join(recipients)}")
            self.logger.info(f"邮件大小: {len(message) if isinstance(message, str) else len(str(message))} 字符")
            self.logger.info(f"格式: {'HTML' if is_html else 'TEXT'}")
            
            # 检查必需配置
            missing_configs = []
            if not config['smtp_server']:
                missing_configs.append('SMTP_SERVER')
            if not config['username']:
                missing_configs.append('EMAIL_USERNAME')
            if not config['password']:
                missing_configs.append('EMAIL_PASSWORD')
                
            if missing_configs:
                error_msg = f"缺少邮件配置: {', '.join(missing_configs)}"
                self.logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'message': '邮件配置不完整'
                }
            
            self.logger.info(f"开始发送邮件到: {', '.join(recipients)}")
            
            # 创建邮件消息
            if is_html:
                msg = MIMEMultipart('alternative')
            else:
                msg = MIMEMultipart()
                
            msg['From'] = f"{config['from_name']} <{config['username']}>"
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = Header(subject, 'utf-8')
            
            # 添加邮件正文
            if is_html:
                msg.attach(MIMEText(message, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            # 智能选择SMTP连接方式（基于端口自动选择）
            use_ssl = config['smtp_port'] == 465  # 端口465通常使用SSL
            
            # 重试发送邮件（最多3次）
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if use_ssl:
                        self.logger.info(f"第{attempt + 1}次尝试连接SMTP服务器（SSL模式）...")
                    else:
                        self.logger.info(f"第{attempt + 1}次尝试连接SMTP服务器（STARTTLS模式）...")
                    
                    # 详细的连接信息
                    import socket
                    import time
                    
                    # 测试DNS解析
                    start_time = time.time()
                    try:
                        ip_address = socket.gethostbyname(config['smtp_server'])
                        dns_time = time.time() - start_time
                        self.logger.info(f"DNS解析成功: {config['smtp_server']} -> {ip_address} ({dns_time:.2f}s)")
                    except socket.gaierror as e:
                        self.logger.error(f"DNS解析失败: {e}")
                        raise
                    
                    # 测试端口连接
                    self.logger.info(f"测试端口连接: {config['smtp_server']}:{config['smtp_port']}")
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_socket.settimeout(10)
                    try:
                        connect_start = time.time()
                        test_socket.connect((config['smtp_server'], config['smtp_port']))
                        connect_time = time.time() - connect_start
                        test_socket.close()
                        self.logger.info(f"端口连接成功 ({connect_time:.2f}s)")
                    except socket.error as e:
                        test_socket.close()
                        self.logger.error(f"端口连接失败: {e}")
                        raise
                    
                    # 创建SMTP连接（根据端口选择连接方式）
                    if use_ssl:
                        self.logger.info("创建SSL SMTP连接...")
                        server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=30)
                    else:
                        self.logger.info("创建普通SMTP连接...")
                        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=30)
                        self.logger.info("启动TLS加密...")
                        server.starttls()
                    
                    server.set_debuglevel(0)  # 关闭调试输出
                    
                    self.logger.info("登录SMTP服务器...")
                    server.login(config['username'], config['password'])
                    
                    self.logger.info("发送邮件...")
                    send_start = time.time()
                    server.send_message(msg)
                    send_time = time.time() - send_start
                    server.quit()
                    
                    self.logger.info(f"邮件发送成功 ({send_time:.2f}s)")
                    
                    self.logger.info(f"邮件发送成功: {recipients}")
                    return {
                        'success': True,
                        'recipients_count': len(recipients),
                        'message': f'邮件发送成功（第{attempt + 1}次尝试）'
                    }
                    
                except Exception as smtp_error:
                    error_type = type(smtp_error).__name__
                    error_msg = f"第{attempt + 1}次尝试失败 ({error_type}): {str(smtp_error)}"
                    self.logger.warning(error_msg)
                    
                    # 根据错误类型提供具体建议
                    if 'timeout' in str(smtp_error).lower():
                        self.logger.warning("ℹ️ 网络超时问题，可能原因：")
                        self.logger.warning("  1. SMTP服务器地址不正确")
                        self.logger.warning("  2. 网络防火墙阻挡")
                        self.logger.warning("  3. SMTP服务器负载过高")
                    elif 'authentication' in str(smtp_error).lower():
                        self.logger.warning("ℹ️ 认证失败，可能原因：")
                        self.logger.warning("  1. 用户名或密码错误")
                        self.logger.warning("  2. 需要启用应用专用密码")
                        self.logger.warning("  3. 账户被锁定")
                    elif 'connection' in str(smtp_error).lower():
                        self.logger.warning("ℹ️ 连接失败，可能原因：")
                        self.logger.warning("  1. SMTP端口不正确")
                        self.logger.warning("  2. 需要SSL/TLS连接")
                        self.logger.warning("  3. 服务器禁止外部连接")
                    
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5  # 逐步增加等待时间
                        self.logger.info(f"🔄 {wait_time}秒后重试...")
                        sleep(wait_time)
                    else:
                        self.logger.error("⁉️ 所有重试尝试都失败，请检查以下配置：")
                        self.logger.error(f"  SMTP_SERVER={config['smtp_server']}")
                        self.logger.error(f"  SMTP_PORT={config['smtp_port']}")
                        self.logger.error(f"  EMAIL_USERNAME={config['username']}")
                        self.logger.error("  EMAIL_PASSWORD=*** (检查是否设置)")
                        raise smtp_error
                        
            # 所有尝试都失败
            return {
                'success': False,
                'error': f'所有{max_retries}次尝试都失败',
                'message': '邮件发送失败'
            }
            
        except Exception as e:
            self.logger.error(f"邮件发送失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '邮件发送失败'
            }
    
    def _send_email_with_attachment(self, subject: str, message: str, recipients: List[str],
                                   attachment_content: str = None, attachment_filename: str = None,
                                   is_html: bool = False) -> Dict[str, Any]:
        """发送带附件的邮件"""
        import socket
        from time import sleep
        
        try:
            config = self.config['email']
            
            # 详细的邮件配置诊断
            self.logger.info("=== 带附件邮件配置诊断 ===")
            self.logger.info(f"SMTP服务器: {config['smtp_server']}")
            self.logger.info(f"SMTP端口: {config['smtp_port']}")
            self.logger.info(f"发件人: {config['from_name']} <{config['username']}>")
            self.logger.info(f"收件人: {', '.join(recipients)}")
            self.logger.info(f"邮件大小: {len(message) if isinstance(message, str) else len(str(message))} 字符")
            self.logger.info(f"格式: {'HTML' if is_html else 'TEXT'}")
            if attachment_filename:
                self.logger.info(f"附件: {attachment_filename} ({len(attachment_content) if attachment_content else 0} 字符)")
            
            # 检查必需配置
            missing_configs = []
            if not config['smtp_server']:
                missing_configs.append('SMTP_SERVER')
            if not config['username']:
                missing_configs.append('EMAIL_USERNAME')
            if not config['password']:
                missing_configs.append('EMAIL_PASSWORD')
                
            if missing_configs:
                error_msg = f"缺少邮件配置: {', '.join(missing_configs)}"
                self.logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'message': '邮件配置不完整'
                }
            
            self.logger.info(f"开始发送带附件邮件到: {', '.join(recipients)}")
            
            # 创建邮件消息
            msg = MIMEMultipart()
            msg['From'] = f"{config['from_name']} <{config['username']}>"
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = Header(subject, 'utf-8')
            
            # 添加邮件正文
            if is_html:
                msg.attach(MIMEText(message, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            # 添加附件
            self.logger.info(f"附件检查: attachment_content={'有内容' if attachment_content else '无内容'}, attachment_filename={attachment_filename}")
            if attachment_content and attachment_filename:
                # 使用测试验证的格式7：RFC标准的Content-Disposition格式
                part = MIMEText(attachment_content, 'plain', 'utf-8')
                
                # 使用RFC标准格式，文件名用参数方式传递并编码
                from email.header import Header
                encoded_filename = Header(attachment_filename, 'utf-8').encode()
                part.add_header('Content-Disposition', 'attachment', filename=encoded_filename)
                msg.attach(part)
                self.logger.info(f"已添加附件: {attachment_filename} (格式: RFC标准 text/plain)")
                
                # 调试：输出附件的完整信息
                self.logger.info(f"📋 调试信息:")
                self.logger.info(f"  - Content-Type: {part.get_content_type()}")
                self.logger.info(f"  - Content-Disposition: {part.get('Content-Disposition')}")
                self.logger.info(f"  - 附件内容长度: {len(attachment_content)} 字符")
                self.logger.info(f"  - 附件前100字符: {attachment_content[:100]}...")
            
            # 智能选择SMTP连接方式（基于端口自动选择）
            use_ssl = config['smtp_port'] == 465  # 端口465通常使用SSL
            
            # 重试发送邮件（最多3次）
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if use_ssl:
                        self.logger.info(f"第{attempt + 1}次尝试连接SMTP服务器（SSL模式）...")
                        server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=30)
                    else:
                        self.logger.info(f"第{attempt + 1}次尝试连接SMTP服务器（STARTTLS模式）...")
                        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=30)
                        server.starttls()
                    
                    # 登录和发送
                    self.logger.info("🔑 正在进行身份验证...")
                    server.login(config['username'], config['password'])
                    
                    self.logger.info("📧 正在发送邮件...")
                    text = msg.as_string()
                    
                    # 调试：保存邮件到临时文件
                    try:
                        import tempfile
                        import os
                        temp_file = os.path.join(tempfile.gettempdir(), f"debug_email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.eml")
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            f.write(text)
                        self.logger.info(f"📋 调试：完整邮件已保存到 {temp_file}")
                    except Exception as debug_error:
                        self.logger.warning(f"调试文件保存失败: {debug_error}")
                    
                    server.sendmail(config['username'], recipients, text)
                    server.quit()
                    
                    self.logger.info("✅ 带附件邮件发送成功！")
                    return {
                        'success': True,
                        'message': f'邮件已成功发送给 {len(recipients)} 个收件人'
                    }
                    
                except smtplib.SMTPException as smtp_error:
                    self.logger.warning(f"第{attempt + 1}次尝试失败: {smtp_error}")
                    
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        self.logger.info(f"🔄 {wait_time}秒后重试...")
                        sleep(wait_time)
                    else:
                        raise smtp_error
                        
            return {
                'success': False,
                'error': f'所有{max_retries}次尝试都失败',
                'message': '邮件发送失败'
            }
            
        except Exception as e:
            self.logger.error(f"带附件邮件发送失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '邮件发送失败'
            }
    
    def _send_wechat(self, message: str) -> Dict[str, Any]:
        """发送微信消息"""
        try:
            webhook_url = self.config['wechat']['webhook_url']
            
            payload = {
                'msgtype': 'text',
                'text': {
                    'content': message
                }
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info("微信消息发送成功")
            return {
                'success': True,
                'response': response.json(),
                'message': '微信消息发送成功'
            }
            
        except Exception as e:
            self.logger.error(f"微信消息发送失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '微信消息发送失败'
            }
    
    def _send_dingtalk(self, subject: str, message: str) -> Dict[str, Any]:
        """发送钉钉消息"""
        try:
            webhook_url = self.config['dingtalk']['webhook_url']
            
            # 构建钉钉消息格式
            content = f"**{subject}**\n\n{message}"
            
            payload = {
                'msgtype': 'markdown',
                'markdown': {
                    'title': subject,
                    'text': content
                }
            }
            
            # 如果配置了签名
            if self.config['dingtalk']['secret']:
                import time
                import hmac
                import hashlib
                import base64
                from urllib.parse import quote_plus
                
                timestamp = str(round(time.time() * 1000))
                secret_enc = self.config['dingtalk']['secret'].encode('utf-8')
                string_to_sign = f"{timestamp}\n{self.config['dingtalk']['secret']}"
                string_to_sign_enc = string_to_sign.encode('utf-8')
                hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
                sign = quote_plus(base64.b64encode(hmac_code))
                
                webhook_url += f"&timestamp={timestamp}&sign={sign}"
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info("钉钉消息发送成功")
            return {
                'success': True,
                'response': response.json(),
                'message': '钉钉消息发送成功'
            }
            
        except Exception as e:
            self.logger.error(f"钉钉消息发送失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '钉钉消息发送失败'
            }
    
    def _send_slack(self, subject: str, message: str) -> Dict[str, Any]:
        """发送Slack消息"""
        try:
            webhook_url = self.config['slack']['webhook_url']
            
            payload = {
                'text': subject,
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': f"*{subject}*\n{message}"
                        }
                    }
                ]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info("Slack消息发送成功")
            return {
                'success': True,
                'message': 'Slack消息发送成功'
            }
            
        except Exception as e:
            self.logger.error(f"Slack消息发送失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Slack消息发送失败'
            }
    
    def _build_failure_message(self, alert_data: Dict[str, Any]) -> str:
        """构建失败告警消息"""
        message = f"""
脚本执行失败告警

📋 脚本信息:
  • 脚本名称: {alert_data['script_name']}
  • 脚本ID: {alert_data['script_id']}
  • 描述: {alert_data.get('description', '无')}

⚠️ 失败信息:
  • 失败时间: {alert_data['failure_time']}
  • 执行ID: {alert_data['execution_id']}
  • 严重级别: {alert_data['severity'].upper()}

📝 日志路径: {alert_data.get('log_path', '无')}

🔧 建议操作:
1. 检查脚本代码逻辑
2. 查看详细执行日志
3. 检查系统资源和环境
4. 必要时联系开发人员

---
发送时间: {format_timestamp()}
系统: ProjectMind-AI
        """.strip()
        
        return message
    
    def _build_health_report_message(self, health_data: Dict[str, Any]) -> str:
        """构建健康报告消息"""
        status_icon = {
            'excellent': '🟢',
            'good': '🟡', 
            'warning': '🟠',
            'critical': '🔴'
        }
        
        icon = status_icon.get(health_data.get('overall_status', 'unknown'), '⚪')
        
        message = f"""
{icon} 系统健康报告

📊 整体状态: {health_data.get('overall_status', 'unknown').upper()}

📈 24小时统计:
  • 总执行次数: {health_data.get('total_executions', 0)}
  • 成功次数: {health_data.get('success_count', 0)}
  • 失败次数: {health_data.get('failed_count', 0)}
  • 成功率: {health_data.get('success_rate', 0):.1f}%

⚡ 性能指标:
  • 平均执行时间: {health_data.get('avg_execution_time', 0):.2f}秒
  • 活跃脚本数: {health_data.get('active_scripts', 0)}

🔍 异常情况:
  • 最近失败: {health_data.get('recent_failures', 0)}次
  • 问题脚本: {health_data.get('problematic_scripts', 0)}个

💡 建议关注:
{chr(10).join(f'  • {item}' for item in health_data.get('recommendations', []))}

---
报告时间: {format_timestamp()}
统计周期: 最近24小时
        """.strip()
        
        return message
    
    def _build_report_message(self, report_type: str, report_data: Dict[str, Any]) -> str:
        """构建报告消息"""
        type_names = {
            'daily': '日报',
            'weekly': '周报', 
            'monthly': '月报'
        }
        
        type_name = type_names.get(report_type, '报告')
        
        message = f"""
📈 {type_name}运行摘要

📊 执行统计:
  • 总执行次数: {report_data.get('total_executions', 0)}
  • 成功次数: {report_data.get('success_count', 0)}
  • 失败次数: {report_data.get('failed_count', 0)}
  • 成功率: {report_data.get('success_rate', 0):.1f}%

🎯 性能表现:
  • 平均执行时间: {report_data.get('avg_execution_time', 0):.2f}秒
  • 最长执行时间: {report_data.get('max_execution_time', 0):.2f}秒
  • 活跃脚本数: {report_data.get('unique_scripts', 0)}

📋 重要脚本:
{chr(10).join(f'  • {script["name"]}: {script["executions"]}次执行' for script in report_data.get('top_scripts', [])[:3])}

⚠️ 需要关注:
{chr(10).join(f'  • {issue}' for issue in report_data.get('issues', []))}

---
报告周期: {report_data.get('period', 'unknown')}
生成时间: {format_timestamp()}
        """.strip()
        
        return message
    
    def _calculate_system_health(self, stats: Dict[str, Any], 
                                recent_executions: List[Dict]) -> Dict[str, Any]:
        """计算系统健康指标"""
        success_rate = 0
        if stats.get('total_executions', 0) > 0:
            success_rate = (stats.get('success_count', 0) / stats['total_executions']) * 100
        
        # 计算平均执行时间
        execution_times = []
        for execution in recent_executions:
            if execution['start_time'] and execution['end_time']:
                duration = (execution['end_time'] - execution['start_time']).total_seconds()
                if duration > 0:
                    execution_times.append(duration)
        
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        # 确定整体健康状态
        if success_rate >= 95 and avg_execution_time < 30:
            overall_status = 'excellent'
        elif success_rate >= 85 and avg_execution_time < 60:
            overall_status = 'good'
        elif success_rate >= 70:
            overall_status = 'warning'
        else:
            overall_status = 'critical'
        
        # 生成建议
        recommendations = []
        if success_rate < 90:
            recommendations.append('成功率偏低，建议检查失败脚本')
        if avg_execution_time > 60:
            recommendations.append('平均执行时间过长，建议优化性能')
        if stats.get('failed_count', 0) > 10:
            recommendations.append('失败次数较多，需要重点关注')
        
        if not recommendations:
            recommendations.append('系统运行正常，保持现状')
        
        return {
            'overall_status': overall_status,
            'total_executions': stats.get('total_executions', 0),
            'success_count': stats.get('success_count', 0),
            'failed_count': stats.get('failed_count', 0),
            'success_rate': success_rate,
            'avg_execution_time': avg_execution_time,
            'active_scripts': len(set(e['script_id'] for e in recent_executions)),
            'recent_failures': sum(1 for e in recent_executions if e['status'] == 'FAILED'),
            'problematic_scripts': len(set(e['script_id'] for e in recent_executions if e['status'] == 'FAILED')),
            'recommendations': recommendations
        }
    
    def _generate_daily_summary(self) -> Dict[str, Any]:
        """生成日报摘要"""
        yesterday = datetime.now() - timedelta(days=1)
        start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        
        # 获取昨日执行记录
        all_executions = self.db_client.get_recent_executions(500)
        daily_executions = [
            e for e in all_executions
            if e['start_time'] and start_time <= e['start_time'] < end_time
        ]
        
        # 计算统计信息
        total = len(daily_executions)
        success_count = sum(1 for e in daily_executions if e['status'] == 'SUCCESS')
        failed_count = sum(1 for e in daily_executions if e['status'] == 'FAILED')
        success_rate = (success_count / total * 100) if total > 0 else 0
        
        # 计算执行时间
        execution_times = []
        for execution in daily_executions:
            if execution['start_time'] and execution['end_time']:
                duration = (execution['end_time'] - execution['start_time']).total_seconds()
                if duration > 0:
                    execution_times.append(duration)
        
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
        max_time = max(execution_times) if execution_times else 0
        
        # 统计脚本使用
        script_stats = {}
        for execution in daily_executions:
            script_id = execution['script_id']
            script_name = execution.get('script_name', f'Script_{script_id}')
            if script_name not in script_stats:
                script_stats[script_name] = 0
            script_stats[script_name] += 1
        
        top_scripts = sorted(script_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        top_scripts_formatted = [{'name': name, 'executions': count} for name, count in top_scripts]
        
        # 识别问题
        issues = []
        if success_rate < 90:
            issues.append(f'成功率偏低: {success_rate:.1f}%')
        if failed_count > 5:
            issues.append(f'失败次数过多: {failed_count}次')
        if avg_time > 60:
            issues.append(f'平均执行时间过长: {avg_time:.1f}秒')
        
        return {
            'period': yesterday.strftime('%Y-%m-%d'),
            'total_executions': total,
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': success_rate,
            'avg_execution_time': avg_time,
            'max_execution_time': max_time,
            'unique_scripts': len(script_stats),
            'top_scripts': top_scripts_formatted,
            'issues': issues
        }
    
    def _generate_weekly_summary(self) -> Dict[str, Any]:
        """生成周报摘要"""
        # 简化实现，实际可以更详细
        return self._generate_daily_summary()
    
    def _generate_monthly_summary(self) -> Dict[str, Any]:
        """生成月报摘要"""
        # 简化实现，实际可以更详细
        return self._generate_daily_summary()

def main():
    """主函数"""
    parser = parse_arguments("通知发送脚本")
    parser.add_argument('--type', choices=['failure', 'health', 'report', 'custom', 'test'], 
                       required=True, help='通知类型（test用于测试邮件配置）')
    parser.add_argument('--script-id', type=int, help='脚本ID（用于失败告警）')
    parser.add_argument('--execution-id', type=int, help='执行记录ID（用于失败告警）')
    parser.add_argument('--report-type', choices=['daily', 'weekly', 'monthly'], 
                       help='报告类型')
    parser.add_argument('--subject', help='自定义通知主题')
    parser.add_argument('--message', help='自定义通知内容')
    parser.add_argument('--recipients', nargs='+', help='收件人列表（test类型不需要）')
    parser.add_argument('--channels', nargs='+', 
                       choices=['email', 'wechat', 'dingtalk', 'slack'],
                       default=['email'], help='发送渠道')
    parser.add_argument('--priority', choices=['low', 'normal', 'high', 'urgent'],
                       default='normal', help='优先级')
    
    args = parser.parse_args()
    
    # 设置日志级别
    logger = setup_logging(args.log_level)
    
    sender = NotificationSender()
    
    try:
        if args.type == 'failure':
            if not args.script_id or not args.execution_id:
                exit_with_error("失败告警需要指定 --script-id 和 --execution-id")
            result = sender.send_script_failure_alert(
                args.script_id, args.execution_id, args.recipients, args.channels
            )
        
        elif args.type == 'health':
            result = sender.send_system_health_report(args.recipients, args.channels)
        
        elif args.type == 'report':
            if not args.report_type:
                exit_with_error("报告通知需要指定 --report-type")
            result = sender.send_scheduled_report(
                args.report_type, args.recipients, args.channels
            )
        
        elif args.type == 'custom':
            if not args.subject or not args.message:
                exit_with_error("自定义通知需要指定 --subject 和 --message")
            result = sender.send_custom_notification(
                args.subject, args.message, args.recipients, args.channels, args.priority
            )
        
        elif args.type == 'test':
            logger.info("🧪 开始测试邮件配置...")
            test_result = sender.test_email_config()
            
            print("\n=== 邮件配置测试结果 ===")
            for detail in test_result['details']:
                print(f"  {detail}")
                
            if test_result['recommendations']:
                print("\n💡 建议:")
                for rec in test_result['recommendations']:
                    print(f"  • {rec}")
                    
            if test_result['overall_success']:
                print("\n✅ 邮件配置测试成功！")
                exit_with_success()
            else:
                print("\n❌ 邮件配置测试失败")
                sys.exit(1)
        
        else:
            exit_with_error("无效的通知类型")
        
        # 输出结果
        summary = result.get('summary', {})
        if summary.get('overall_success', False):
            print(f"✅ 通知发送成功")
            print(f"   成功渠道: {summary['successful_channels']}/{summary['total_channels']}")
            print(f"   收件人: {len(args.recipients)}人")
        else:
            print(f"❌ 通知发送失败")
            for channel, channel_result in result.get('results', {}).items():
                status = "✅" if channel_result.get('success') else "❌"
                print(f"   {channel}: {status} {channel_result.get('message', '')}")
        
        # 详细结果（调试模式）
        if args.log_level == 'DEBUG':
            print(f"\n详细结果:")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        
        exit_with_success()
        
    except Exception as e:
        exit_with_error(f"通知发送失败: {e}")

if __name__ == "__main__":
    main()