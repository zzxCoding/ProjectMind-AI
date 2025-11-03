#!/usr/bin/env python3
"""
GitLab MR 自动审查 Pipeline 脚本
整合所有功能，提供完整的审查流程
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.gitlab_client import GitLabClient
from shared.ollama_client import OllamaClient
from shared.utils import setup_logging
from shared.file_lock import file_lock, FileLock
from automation.mr_review_engine import MRReviewEngine, ReviewResult
from automation.gitlab_mr_interactor import ReviewResultProcessor
from config.review_config import ReviewConfig, get_default_config, MultiProjectConfig, load_multi_project_config

class MRReviewPipeline:
    """MR 审查流水线"""
    
    @staticmethod
    def get_lock_name(project_id: str = None, mr_iid: int = None, operation: str = "review") -> str:
        """
        获取锁名称
        
        Args:
            project_id: 项目ID
            mr_iid: MR IID
            operation: 操作类型
            
        Returns:
            锁名称
        """
        if project_id and mr_iid:
            return f"mr_review_{project_id}_{mr_iid}"
        elif project_id:
            return f"mr_review_{project_id}_{operation}"
        else:
            return f"mr_review_{operation}"
    
    def __init__(self, config: Optional[ReviewConfig] = None, log_level: str = 'INFO', ai_temperature: Optional[float] = None):
        """
        初始化审查流水线
        
        Args:
            config: 审查配置
            log_level: 日志级别
            ai_temperature: AI温度参数
        """
        self.config = config or get_default_config()
        self.logger = setup_logging(level=log_level)
        
        # 初始化各个组件
        self.gitlab_client = GitLabClient()
        self.ollama_client = OllamaClient()
        
        # 初始化核心引擎
        self.review_engine = MRReviewEngine(
            gitlab_client=self.gitlab_client,
            ollama_client=self.ollama_client,
            log_level=log_level,
            ai_temperature=ai_temperature
        )
        
        # 初始化结果处理器
        self.result_processor = ReviewResultProcessor(log_level=log_level)
        
        # 应用配置到引擎
        self._apply_config_to_engine()
        
        self.logger.info("MR审查流水线初始化完成")
    
    def _apply_config_to_engine(self):
        """应用配置到审查引擎"""
        # 支持新旧配置格式
        if hasattr(self.config, 'review_rules'):
            # 新格式：多项目配置
            review_rules = self.config.review_rules
            ai_config = self.config.ai_config
            gitlab_config = self.config.gitlab_config
            
            self.review_engine.config.update({
                'max_issues_per_file': review_rules.max_issues_per_file,
                'severity_threshold': review_rules.severity_threshold,
                'enable_ai_review': ai_config.enabled,
                'ai_model': ai_config.model,
                'team_rules_path': self.config.team_rules_path,
            })
            
            # 应用配置到结果处理器
            self.result_processor.gitlab_interactor.config.update({
                'auto_comment': gitlab_config.auto_comment,
                'auto_label': gitlab_config.auto_label,
                'auto_block': gitlab_config.auto_block,
                'comment_template': gitlab_config.comment_template,
                'max_comment_length': gitlab_config.max_comment_length,
            })
        else:
            # 旧格式：单项目配置
            self.review_engine.config.update({
                'max_issues_per_file': self.config.max_issues_per_file,
                'severity_threshold': self.config.severity_threshold,
                'enable_ai_review': self.config.ai_review_enabled,
                'ai_model': self.config.ai_model,
                'team_rules_path': self.config.team_rules_path,
            })
            
            # 应用配置到结果处理器
            self.result_processor.gitlab_interactor.config.update({
                'auto_comment': self.config.auto_comment,
                'auto_label': self.config.auto_label,
                'auto_block': self.config.auto_block,
                'comment_template': self.config.comment_template,
                'max_comment_length': self.config.max_comment_length,
            })
    
    def review_single_mr(self, project_id: str, mr_iid: int) -> Dict[str, Any]:
        """
        审查单个MR
        
        Args:
            project_id: 项目ID
            mr_iid: 合并请求IID
            
        Returns:
            审查结果
        """
        start_time = time.time()
        
        # 获取锁名称
        lock_name = self.get_lock_name(project_id, mr_iid)
        
        # 尝试获取锁，不等待
        with file_lock(lock_name, timeout=0) as locked:
            if not locked:
                self.logger.info(f"MR {project_id}!{mr_iid} 正在被其他进程审查，跳过")
                return {
                    'success': False,
                    'project_id': project_id,
                    'mr_iid': mr_iid,
                    'error': 'MR正在被其他进程审查',
                    'execution_time': time.time() - start_time
                }
            
            try:
                self.logger.info(f"开始审查MR: {project_id}!{mr_iid}")
                
                # 1. 增量检查：检查是否需要执行审查
                if not self.result_processor.gitlab_interactor._should_perform_review(project_id, mr_iid):
                    self.logger.info(f"MR {project_id}!{mr_iid} 代码无变更，跳过审查")
                    
                    # 返回跳过审查的结果
                    from datetime import datetime
                    review_result = MRReviewEngine._create_skip_result(
                        project_id=project_id,
                        mr_iid=mr_iid,
                        skip_reason="代码无变更，跳过审查"
                    )
                else:
                    # 2. 执行审查
                    review_result = self.review_engine.review_merge_request(project_id, mr_iid)
                
                # 3. 处理和发布结果
                publish_success = self.result_processor.process_and_publish(project_id, mr_iid, review_result)
                
                # 4. 发送通知（如果配置了）
                if hasattr(self.config, 'notification_config') and self.config.notification_config._should_notify(review_result.status.value):
                    self._send_notification(project_id, mr_iid, review_result)
                elif hasattr(self.config, '_should_notify') and self.config._should_notify(review_result.status.value):
                    self._send_notification(project_id, mr_iid, review_result)
                
                # 5. 计算执行时间
                execution_time = time.time() - start_time
                
                # 6. 构建返回结果
                result = {
                    'success': True,
                    'project_id': project_id,
                    'mr_iid': mr_iid,
                    'mr_title': review_result.mr_title,
                    'review_status': review_result.status.value,
                    'issues_count': len(review_result.issues),
                    'execution_time': execution_time,
                    'published': publish_success,
                    'review_time': review_result.review_time.isoformat(),
                    'summary': review_result.summary
                }
                
                self.logger.info(f"MR审查完成: {project_id}!{mr_iid} - {review_result.status.value}")
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(f"MR审查失败: {project_id}!{mr_iid} - {e}")
                
                return {
                    'success': False,
                    'project_id': project_id,
                    'mr_iid': mr_iid,
                    'error': str(e),
                    'execution_time': execution_time
                }
    
    def review_project_mrs(self, project_id: str, 
                          state: str = 'opened',
                          target_branch: Optional[str] = None,
                          author_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        审查项目的所有MR
        
        Args:
            project_id: 项目ID
            state: MR状态
            target_branch: 目标分支
            author_id: 作者ID
            
        Returns:
            审查结果列表
        """
        # 获取项目级别的锁，防止同一项目的多个审查并发
        lock_name = self.get_lock_name(project_id, operation="project_review")
        
        # 尝试获取锁，不等待
        with file_lock(lock_name, timeout=0) as locked:
            if not locked:
                self.logger.info(f"项目 {project_id} 正在被其他进程审查，跳过")
                return []
            
            try:
                self.logger.info(f"开始审查项目 {project_id} 的MR")
                
                # 获取MR列表
                merge_requests = self.gitlab_client.get_merge_requests(
                    project_id=project_id,
                    state=state,
                    target_branch=target_branch,
                    author_id=author_id
                )
                
                if not merge_requests:
                    self.logger.info(f"项目 {project_id} 没有找到符合条件的MR")
                    return []
                
                self.logger.info(f"找到 {len(merge_requests)} 个MR，开始审查")
                
                # 并发审查（如果配置了）
                if self.config.concurrent_reviews > 1:
                    import concurrent.futures
                    
                    results = []
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrent_reviews) as executor:
                        # 提交所有审查任务
                        future_to_mr = {
                            executor.submit(self.review_single_mr, project_id, mr['iid']): mr
                            for mr in merge_requests
                        }
                        
                        # 收集结果
                        for future in concurrent.futures.as_completed(future_to_mr):
                            mr = future_to_mr[future]
                            try:
                                result = future.result()
                                results.append(result)
                            except Exception as e:
                                self.logger.error(f"MR审查异常 {mr['iid']}: {e}")
                                results.append({
                                    'success': False,
                                    'project_id': project_id,
                                    'mr_iid': mr['iid'],
                                    'error': str(e)
                                })
                    
                    return results
                
                else:
                    # 串行审查
                    results = []
                    for mr in merge_requests:
                        result = self.review_single_mr(project_id, mr['iid'])
                        results.append(result)
                
                return results
                
            except Exception as e:
                self.logger.error(f"审查项目MR失败: {e}")
                return []
    
    def monitor_and_review(self, project_id: str, 
                          interval: int = 300,
                          max_reviews: int = 10) -> None:
        """
        监控并自动审查新的MR
        
        Args:
            project_id: 项目ID
            interval: 检查间隔（秒）
            max_reviews: 最大审查数量
        """
        self.logger.info(f"开始监控项目 {project_id} 的新MR")
        
        reviewed_mrs = set()
        review_count = 0
        
        try:
            while review_count < max_reviews:
                try:
                    # 获取开放的MR
                    merge_requests = self.gitlab_client.get_merge_requests(
                        project_id=project_id,
                        state='opened',
                        since=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    )
                    
                    # 检查新的MR
                    new_mrs = [mr for mr in merge_requests if mr['iid'] not in reviewed_mrs]
                    
                    if new_mrs:
                        self.logger.info(f"发现 {len(new_mrs)} 个新MR")
                        
                        for mr in new_mrs:
                            self.logger.info(f"自动审查MR: {mr['iid']} - {mr['title']}")
                            result = self.review_single_mr(project_id, mr['iid'])
                            
                            if result['success']:
                                reviewed_mrs.add(mr['iid'])
                                review_count += 1
                                
                                if review_count >= max_reviews:
                                    self.logger.info(f"达到最大审查数量 {max_reviews}")
                                    break
                    
                    # 等待下一次检查
                    self.logger.info(f"等待 {interval} 秒后进行下一次检查")
                    time.sleep(interval)
                    
                except KeyboardInterrupt:
                    self.logger.info("收到中断信号，停止监控")
                    break
                except Exception as e:
                    self.logger.error(f"监控过程中发生错误: {e}")
                    time.sleep(interval)
                    continue
                    
        except Exception as e:
            self.logger.error(f"监控失败: {e}")
    
    def _send_notification(self, project_id: str, mr_iid: int, review_result: ReviewResult):
        """发送通知"""
        try:
            # 这里可以集成邮件、微信、钉钉等通知方式
            # 目前只是简单的日志记录
            self.logger.info(f"发送通知: MR {mr_iid} 审查完成 - {review_result.status.value}")
            
        except Exception as e:
            self.logger.warning(f"发送通知失败: {e}")
    
    def generate_report(self, results: List[Dict[str, Any]]) -> str:
        """生成审查报告"""
        total_mrs = len(results)
        successful_reviews = len([r for r in results if r['success']])
        failed_reviews = total_mrs - successful_reviews
        
        # 统计问题
        total_issues = sum(r.get('issues_count', 0) for r in results if r['success'])
        
        # 按状态统计
        status_counts = {}
        for result in results:
            if result['success']:
                status = result.get('review_status', 'UNKNOWN')
                status_counts[status] = status_counts.get(status, 0) + 1
        
        # 生成报告
        report = f"""
# GitLab MR 自动审查报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**总MR数**: {total_mrs}  
**成功审查**: {successful_reviews}  
**失败审查**: {failed_reviews}  
**发现问题**: {total_issues}  

## 📊 审查状态统计

"""
        
        for status, count in status_counts.items():
            emoji = {'PASSED': '✅', 'WARNING': '⚠️', 'FAILED': '❌'}.get(status, '📋')
            report += f"- {emoji} **{status}**: {count} 个\n"
        
        report += "\n## 📋 详细结果\n\n"
        
        for result in results:
            if result['success']:
                emoji = {'PASSED': '✅', 'WARNING': '⚠️', 'FAILED': '❌'}.get(result.get('review_status', 'UNKNOWN'), '📋')
                report += f"- {emoji} !{result['mr_iid']} {result['mr_title']} ({result.get('review_status', 'UNKNOWN')}) - {result.get('issues_count', 0)} 个问题\n"
            else:
                report += f"- ❌ !{result['mr_iid']} 审查失败 - {result.get('error', 'Unknown error')}\n"
        
        return report

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='GitLab MR 自动审查流水线')
    
    # 项目选择参数
    project_group = parser.add_mutually_exclusive_group()
    project_group.add_argument('--project-id', type=int, help='GitLab项目ID')
    project_group.add_argument('--project-name', help='项目名称')
    project_group.add_argument('--all-projects', action='store_true', help='审查所有项目')
    
    # 操作参数
    parser.add_argument('--mr-iid', type=int, help='审查单个MR')
    parser.add_argument('--all', action='store_true', help='审查所有开放的MR')
    parser.add_argument('--monitor', action='store_true', help='监控模式')
    
    # 配置参数
    parser.add_argument('--config', default='config/review_config.json', help='配置文件路径')
    parser.add_argument('--interval', type=int, default=300, help='监控间隔（秒）')
    parser.add_argument('--max-reviews', type=int, default=10, help='最大审查数量')
    parser.add_argument('--output', help='输出文件路径')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    # AI参数
    parser.add_argument('--ai-model', help='指定AI模型（覆盖配置文件设置）')
    parser.add_argument('--ai-temperature', type=float, help='指定AI温度参数（0.0-1.0）')
    
    # 评论参数
    parser.add_argument('--force-recomment', action='store_true', help='强制重新评论（忽略已有评论）')
    
    # 过滤参数
    parser.add_argument('--project-filter', help='项目过滤器（正则表达式）')
    parser.add_argument('--exclude-projects', help='排除项目列表（逗号分隔）')
    
    # 工具参数
    parser.add_argument('--discover-projects', action='store_true', help='发现所有配置的项目')
    parser.add_argument('--sync-projects', action='store_true', help='同步项目配置')
    parser.add_argument('--group-id', type=int, help='GitLab组ID（用于同步项目）')
    
    # 锁参数
    parser.add_argument('--lock-timeout', type=int, default=0, help='锁等待超时时间（秒），0表示不等待，-1表示无限等待')
    parser.add_argument('--no-lock', action='store_true', help='禁用文件锁机制')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    # 全局锁逻辑 - 防止多个流水线实例并发执行
    if not args.no_lock:
        global_lock_name = "mr_review_pipeline_global"
        
        with file_lock(global_lock_name, timeout=args.lock_timeout) as locked:
            if not locked:
                print("❌ MR审查流水线正在运行，请稍后再试")
                sys.exit(1)
            
            try:
                # 执行主要逻辑
                _execute_main_logic(args, logger)
            except Exception as e:
                logger.error(f"流水线执行失败: {e}")
                sys.exit(1)
    else:
        # 禁用锁，直接执行
        try:
            _execute_main_logic(args, logger)
        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            sys.exit(1)

def _execute_main_logic(args, logger):
    """执行主要的流水线逻辑"""
    try:
        # 工具命令
        if args.discover_projects:
            # 发现所有配置的项目
            multi_config = load_multi_project_config(args.config)
            print("📋 已配置的项目:")
            for name, config in multi_config.projects.items():
                status = "✅ 启用" if config.enable else "❌ 禁用"
                print(f"   {name}: {status} (ID: {config.gitlab_project_id})")
            return
        
        if args.sync_projects:
            # 同步项目配置
            if not args.group_id:
                print("❌ 同步项目需要指定 --group-id 参数")
                return
            print(f"🔄 同步GitLab组 {args.group_id} 的项目配置...")
            # TODO: 实现项目同步逻辑
            return
        
        # 加载配置
        try:
            multi_config = load_multi_project_config(args.config)
            logger.info(f"✅ 多项目配置加载成功，共 {len(multi_config.projects)} 个项目")
        except Exception as e:
            logger.warning(f"多项目配置加载失败，回退到单项目配置: {e}")
            # 回退到单项目配置
            if not args.project_id:
                print("❌ 请指定项目ID或项目名称")
                return
            
            config = ReviewConfig.from_file(args.config) if args.config else get_default_config()
            
            # 应用命令行AI参数（覆盖配置文件）
            if args.ai_model:
                config.ai_model = args.ai_model
                logger.info(f"使用命令行指定的AI模型: {args.ai_model}")
            
            if args.ai_temperature is not None:
                if 0.0 <= args.ai_temperature <= 1.0:
                    config.ai_temperature = args.ai_temperature
                    logger.info(f"使用命令行指定的AI温度: {args.ai_temperature}")
                else:
                    logger.warning(f"AI温度参数无效: {args.ai_temperature}，使用默认值")
            
            pipeline = MRReviewPipeline(config, log_level=args.log_level, ai_temperature=args.ai_temperature)
            
            # 设置force_recomment参数
            if args.force_recomment:
                pipeline.result_processor.gitlab_interactor.set_force_recomment(True)
            
            # 执行单项目逻辑
            if args.mr_iid:
                result = pipeline.review_single_mr(str(args.project_id), args.mr_iid)
                print_review_result(result)
            elif args.all:
                results = pipeline.review_project_mrs(str(args.project_id))
                print_summary(results)
            elif args.monitor:
                pipeline.monitor_and_review(
                    str(args.project_id),
                    interval=args.interval,
                    max_reviews=args.max_reviews
                )
            else:
                print("请指定 --mr-iid, --all 或 --monitor 参数")
            return
        
        # 多项目逻辑
        results = []
        
        # 获取要处理的项目
        projects_to_process = {}
        
        if args.all_projects:
            # 处理所有项目
            exclude_list = args.exclude_projects.split(',') if args.exclude_projects else []
            projects_to_process = multi_config.filter_projects(args.project_filter, exclude_list)
            print(f"🔄 处理所有项目，共 {len(projects_to_process)} 个")
            
        elif args.project_name:
            # 处理指定项目
            project_config = multi_config.get_project_config(args.project_name)
            if not project_config:
                print(f"❌ 未找到项目: {args.project_name}")
                return
            projects_to_process = {args.project_name: project_config}
            print(f"🔄 处理项目: {args.project_name}")
            
        elif args.project_id:
            # 通过项目ID查找项目
            project_config = multi_config.get_project_config_by_id(args.project_id)
            if not project_config:
                print(f"❌ 未找到项目ID: {args.project_id}")
                return
            
            # 找到项目名称
            project_name = None
            for name, config in multi_config.projects.items():
                if config.gitlab_project_id == args.project_id:
                    project_name = name
                    break
            
            if project_name:
                projects_to_process = {project_name: project_config}
                print(f"🔄 处理项目: {project_name}")
            else:
                print(f"❌ 未找到项目ID对应的名称: {args.project_id}")
                return
        
        else:
            print("请指定 --project-id, --project-name 或 --all-projects 参数")
            return
        
        # 处理项目
        for project_name, project_config in projects_to_process.items():
            print(f"\n🚀 处理项目: {project_name}")
            
            # 为每个项目创建流水线
            pipeline = create_project_pipeline(
                project_config, 
                multi_config.global_config,
                ai_model=args.ai_model,
                ai_temperature=args.ai_temperature,
                log_level=args.log_level,
                force_recomment=args.force_recomment
            )
            
            if args.mr_iid:
                # 审查单个MR
                result = pipeline.review_single_mr(str(project_config.gitlab_project_id), args.mr_iid)
                results.append(result)
                print_review_result(result)
                
            elif args.all:
                # 审查所有MR
                project_results = pipeline.review_project_mrs(str(project_config.gitlab_project_id))
                results.extend(project_results)
                print(f"📊 {project_name}: {len(project_results)} 个MR审查完成")
                
            elif args.monitor:
                # 监控模式
                print(f"🔍 监控项目: {project_name}")
                pipeline.monitor_and_review(
                    str(project_config.gitlab_project_id),
                    interval=args.interval,
                    max_reviews=args.max_reviews
                )
                break  # 监控模式只处理一个项目
                
            else:
                print("请指定 --mr-iid, --all 或 --monitor 参数")
                return
        
        # 生成报告
        if results and args.output:
            report = generate_multi_project_report(results, projects_to_process)
            
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"📄 报告已保存到: {args.output}")
    
    except Exception as e:
        logger.error(f"流水线执行失败: {e}")
        raise

def create_project_pipeline(project_config, global_config, ai_model=None, ai_temperature=None, log_level='INFO', force_recomment=False):
    """为项目创建流水线"""
    # 将项目配置转换为旧格式的ReviewConfig
    config = ReviewConfig(
        enable=project_config.enable,
        auto_trigger=project_config.auto_trigger,
        concurrent_reviews=global_config.concurrent_reviews,
        
          
        ai_review_enabled=project_config.ai_config.enabled,
        ai_model=ai_model or project_config.ai_config.model,
        ai_temperature=ai_temperature if ai_temperature is not None else project_config.ai_config.temperature,
        ai_max_tokens=project_config.ai_config.max_tokens,
        ai_prompt_template=project_config.ai_config.prompt_template,
        
        severity_threshold=project_config.review_rules.severity_threshold,
        max_issues_per_file=project_config.review_rules.max_issues_per_file,
        max_total_issues=project_config.review_rules.max_total_issues,
        
        auto_comment=project_config.gitlab_config.auto_comment,
        auto_label=project_config.gitlab_config.auto_label,
        auto_block=project_config.gitlab_config.auto_block,
        comment_template=project_config.gitlab_config.comment_template,
        max_comment_length=global_config.max_comment_length,
        
        notify_on_success=project_config.notification_config.notify_on_success,
        notify_on_warning=project_config.notification_config.notify_on_warning,
        notify_on_failure=project_config.notification_config.notify_on_failure,
        notification_channels=project_config.notification_config.channels,
        
        team_rules_path=project_config.team_rules_path,
        custom_rules=project_config.custom_rules
    )
    
    pipeline = MRReviewPipeline(config, log_level=log_level, ai_temperature=ai_temperature)
    
    # 设置force_recomment参数
    if force_recomment:
        pipeline.result_processor.gitlab_interactor.set_force_recomment(True)
    
    return pipeline

def print_review_result(result):
    """打印审查结果"""
    if result['success']:
        print(f"✅ MR审查完成: {result['mr_title']}")
        print(f"   状态: {result['review_status']}")
        print(f"   问题数: {result['issues_count']}")
        print(f"   执行时间: {result['execution_time']:.2f}秒")
    else:
        print(f"❌ MR审查失败: {result['error']}")

def print_summary(results):
    """打印汇总信息"""
    successful = len([r for r in results if r['success']])
    print(f"📊 审查完成: {successful}/{len(results)} 个MR")

def generate_multi_project_report(results, projects):
    """生成多项目报告"""
    total_mrs = len(results)
    successful_reviews = len([r for r in results if r['success']])
    failed_reviews = total_mrs - successful_reviews
    
    # 按项目统计
    project_stats = {}
    for result in results:
        if result['success']:
            project_id = result['project_id']
            if project_id not in project_stats:
                project_stats[project_id] = {'total': 0, 'successful': 0, 'issues': 0}
            
            project_stats[project_id]['total'] += 1
            project_stats[project_id]['successful'] += 1
            project_stats[project_id]['issues'] += result.get('issues_count', 0)
    
    report = f"""
# 多项目MR审查报告

## 📊 汇总统计
- **总MR数量**: {total_mrs}
- **成功审查**: {successful_reviews}
- **失败审查**: {failed_reviews}
- **成功率**: {successful_reviews/total_mrs*100:.1f}%

## 🏗️ 项目统计
"""
    
    for project_id, stats in project_stats.items():
        project_name = "Unknown"
        for name, config in projects.items():
            if str(config.gitlab_project_id) == project_id:
                project_name = name
                break
        
        success_rate = stats['successful'] / stats['total'] * 100 if stats['total'] > 0 else 0
        report += f"""
### {project_name}
- **总MR数量**: {stats['total']}
- **成功审查**: {stats['successful']}
- **成功率**: {success_rate:.1f}%
- **总问题数**: {stats['issues']}
"""
    
    # 详细结果
    report += "\n## 📋 详细结果\n"
    for result in results:
        if result['success']:
            emoji = {'PASSED': '✅', 'WARNING': '⚠️', 'FAILED': '❌'}.get(result.get('review_status', 'UNKNOWN'), '📋')
            report += f"- {emoji} 项目{result['project_id']} !{result['mr_iid']} {result['mr_title']} ({result.get('review_status', 'UNKNOWN')}) - {result.get('issues_count', 0)} 个问题\n"
        else:
            report += f"- ❌ 项目{result['project_id']} !{result['mr_iid']} 审查失败 - {result.get('error', 'Unknown error')}\n"
    
    return report

if __name__ == "__main__":
    main()