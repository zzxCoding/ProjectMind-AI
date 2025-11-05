#!/usr/bin/env python3
"""
GitLab分支创建流水线
用于创建临时版本分支，创建前校验源分支是否有未合并的请求
"""

import os
import sys
import re
import argparse
import time
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.gitlab_client import GitLabClient
from shared.utils import setup_logging
from shared.file_lock import file_lock


class BranchCreationPipeline:
    """分支创建流水线"""

    def __init__(self, log_level: str = 'INFO', webhook_url: Optional[str] = None,
                 webhook_method: str = 'POST', webhook_origin: Optional[str] = None,
                 webhook_custom_json: Optional[str] = None):
        """
        初始化分支创建流水线

        Args:
            log_level: 日志级别
            webhook_url: WPS Webhook URL（可选）
            webhook_method: Webhook请求方法（POST或GET，默认POST）
            webhook_origin: Origin header值（www.kdocs.cn或www.wps.cn）
            webhook_custom_json: 自定义JSON内容（字符串）
        """
        self.logger = setup_logging(level=log_level)
        self.gitlab_client = GitLabClient(log_level=log_level)

        # Webhook配置
        self.webhook_url = webhook_url or os.getenv('WPS_WEBHOOK_URL')
        self.webhook_method = webhook_method.upper()
        self.webhook_origin = webhook_origin or os.getenv('WPS_WEBHOOK_ORIGIN', 'www.wps.cn')
        self.webhook_custom_json = webhook_custom_json or os.getenv('WPS_WEBHOOK_CUSTOM_JSON', '{}')

        # 版本号正则表达式
        self.version_patterns = {
            'semantic': r'^v?\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$',  # v1.0.0, 2.1.3-beta
            'major_minor': r'^v?\d+\.\d+(-[a-zA-Z0-9]+)?$',    # v1.0, 2.1-beta
            'date_based': r'^\d{4}\.\d{2}\.\d{2}$',            # 2024.01.15
            'custom': r'^[a-zA-Z0-9._-]+$'                    # 自定义格式
        }

        self.logger.info("GitLab分支创建流水线初始化完成")
        if self.webhook_url:
            self.logger.info(f"WPS Webhook已配置: {self.webhook_method} {self.webhook_url}")
            self.logger.info(f"Origin: {self.webhook_origin}")

    def check_open_merge_requests(self, project_id: str, source_branch: str,
                                 include_targeted: bool = True) -> Dict[str, any]:
        """
        检查源分支的未合并请求

        Args:
            project_id: GitLab项目ID
            source_branch: 源分支名称
            include_targeted: 是否包含目标分支为该分支的MR

        Returns:
            检查结果字典
        """
        self.logger.info(f"检查分支 {source_branch} 的未合并请求...")

        try:
            # 获取项目
            project = self.gitlab_client.gitlab.projects.get(project_id)

            # 获取所有开放的MR
            open_mrs = project.mergerequests.list(state='opened', all=True)

            # 分析相关MR
            source_mrs = []  # 源分支相关的MR（作为源分支）
            targeted_mrs = []  # 目标分支相关的MR（作为目标分支）

            for mr in open_mrs:
                if mr.source_branch == source_branch:
                    source_mrs.append({
                        'iid': mr.iid,
                        'title': mr.title,
                        'author': mr.author['name'] if mr.author else 'Unknown',
                        'target_branch': mr.target_branch,
                        'created_at': mr.created_at,
                        'web_url': mr.web_url,
                        'type': 'outgoing'
                    })

                if include_targeted and mr.target_branch == source_branch:
                    targeted_mrs.append({
                        'iid': mr.iid,
                        'title': mr.title,
                        'author': mr.author['name'] if mr.author else 'Unknown',
                        'source_branch': mr.source_branch,
                        'created_at': mr.created_at,
                        'web_url': mr.web_url,
                        'type': 'incoming'
                    })

            total_mrs = len(source_mrs) + len(targeted_mrs)

            result = {
                'source_branch': source_branch,
                'total_open_mrs': total_mrs,
                'outgoing_mrs': source_mrs,
                'incoming_mrs': targeted_mrs,
                'has_open_mrs': total_mrs > 0,
                'safe_to_create_branch': total_mrs == 0
            }

            self.logger.info(f"分支 {source_branch} 检查完成:")
            self.logger.info(f"  未合并的传出MR: {len(source_mrs)} 个")
            self.logger.info(f"  未合并的传入MR: {len(targeted_mrs)} 个")
            self.logger.info(f"  总计: {total_mrs} 个")

            return result

        except Exception as e:
            self.logger.error(f"检查分支MR失败: {e}")
            return {
                'source_branch': source_branch,
                'total_open_mrs': 0,
                'outgoing_mrs': [],
                'incoming_mrs': [],
                'has_open_mrs': False,
                'safe_to_create_branch': False,
                'error': str(e)
            }

    def validate_branch_name(self, branch_name: str, pattern_type: str = 'semantic') -> Tuple[bool, str]:
        """
        验证分支名称是否符合规范

        Args:
            branch_name: 分支名称
            pattern_type: 验证模式类型

        Returns:
            (是否有效, 错误信息)
        """
        if not branch_name:
            return False, "分支名称不能为空"

        # 如果pattern_type是'none'或'custom'，跳过正则验证
        if pattern_type in ['none', 'custom']:
            # 只做基本安全检查
            pass
        elif pattern_type not in self.version_patterns:
            return False, f"未知的验证模式: {pattern_type}"
        else:
            # 进行正则验证
            pattern = self.version_patterns[pattern_type]
            if not re.match(pattern, branch_name):
                return False, f"分支名称不符合 {pattern_type} 模式: {pattern}"

        # 检查分支名长度
        if len(branch_name) > 100:
            return False, "分支名称过长（最多100字符）"

        # 检查是否包含不允许的字符
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', ' ', '\t', '\n']
        if any(char in branch_name for char in invalid_chars):
            return False, "分支名称包含无效字符"

        return True, ""

    def check_branch_exists(self, project_id: str, branch_name: str) -> bool:
        """
        检查分支是否已存在

        Args:
            project_id: GitLab项目ID
            branch_name: 分支名称

        Returns:
            分支是否存在
        """
        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)
            project.branches.get(branch_name)
            return True
        except Exception:
            return False

    def create_branch(self, project_id: str, source_branch: str, new_branch: str) -> Dict[str, any]:
        """
        创建新分支

        Args:
            project_id: GitLab项目ID
            source_branch: 源分支
            new_branch: 新分支名称

        Returns:
            创建结果字典
        """
        self.logger.info(f"创建分支: {new_branch} (基于 {source_branch})")

        try:
            project = self.gitlab_client.gitlab.projects.get(project_id)

            # 检查源分支是否存在
            try:
                source = project.branches.get(source_branch)
                self.logger.debug(f"源分支 {source_branch} 存在 (commit: {source.commit['id'][:8]})")
            except Exception as e:
                return {
                    'success': False,
                    'error': f'源分支 {source_branch} 不存在: {str(e)}',
                    'new_branch': new_branch,
                    'source_branch': source_branch
                }

            # 创建新分支
            branch = project.branches.create({
                'branch': new_branch,
                'ref': source_branch
            })

            result = {
                'success': True,
                'new_branch': new_branch,
                'source_branch': source_branch,
                'commit': branch.commit['id'],
                'commit_short': branch.commit['id'][:8],
                'created_at': datetime.now().isoformat(),
                'protected': branch.protected
            }

            self.logger.info(f"分支创建成功: {new_branch} (commit: {branch.commit['id'][:8]})")
            return result

        except Exception as e:
            self.logger.error(f"创建分支失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'new_branch': new_branch,
                'source_branch': source_branch
            }

    def send_webhook_notification(self, data: Dict[str, any]) -> Tuple[bool, str]:
        """
        发送 WPS Webhook 通知

        Args:
            data: 要发送的数据

        Returns:
            (是否成功, 错误信息)
        """
        if not self.webhook_url:
            self.logger.debug("未配置 Webhook URL，跳过通知")
            return True, ""

        try:
            # 准备请求头
            headers = {}
            if self.webhook_method == 'POST':
                headers['Origin'] = self.webhook_origin
                headers['Content-Type'] = 'application/json'

            # 解析自定义 JSON
            try:
                custom_data = json.loads(self.webhook_custom_json)
            except json.JSONDecodeError as e:
                self.logger.warning(f"解析自定义 JSON 失败: {e}，使用空对象")
                custom_data = {}

            # 合并数据（自定义数据在前，分支数据在后，分支数据会覆盖重复键）
            webhook_data = {**custom_data, **data}

            self.logger.info(f"发送 WPS Webhook: {self.webhook_method} {self.webhook_url}")

            # 发送请求
            if self.webhook_method == 'POST':
                response = requests.post(
                    self.webhook_url,
                    json=webhook_data,
                    headers=headers,
                    timeout=10
                )
            elif self.webhook_method == 'GET':
                response = requests.get(
                    self.webhook_url,
                    params=webhook_data,
                    headers={'Origin': self.webhook_origin} if self.webhook_origin else {},
                    timeout=10
                )
            else:
                return False, f"不支持的请求方法: {self.webhook_method}"

            # 检查响应
            if response.status_code in [200, 201, 202, 204]:
                self.logger.info(f"Webhook 通知发送成功 (HTTP {response.status_code})")
                return True, ""
            else:
                error_msg = f"Webhook 通知发送失败: HTTP {response.status_code}"
                self.logger.warning(error_msg)
                try:
                    self.logger.warning(f"响应内容: {response.text[:200]}")
                except:
                    pass
                return False, error_msg

        except requests.exceptions.Timeout:
            error_msg = "Webhook 请求超时"
            self.logger.warning(error_msg)
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "Webhook 连接错误"
            self.logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Webhook 通知发送异常: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def create_version_branch(self,
                            project_id: str,
                            source_branch: str,
                            version_name: str,
                            pattern_type: str = 'semantic',
                            force_create: bool = False,
                            check_open_mrs: bool = True) -> Dict[str, any]:
        """
        创建版本分支（完整流程）

        Args:
            project_id: GitLab项目ID
            source_branch: 源分支
            version_name: 版本名称（将用作分支名）
            pattern_type: 分支名验证模式
            force_create: 强制创建（忽略未合并MR检查）
            check_open_mrs: 是否检查未合并MR

        Returns:
            操作结果字典
        """
        start_time = time.time()
        lock_name = f"branch_creation_{project_id}_{source_branch}_{version_name}"

        # 获取锁，防止并发创建
        with file_lock(lock_name, timeout=0) as locked:
            if not locked:
                return {
                    'success': False,
                    'error': '分支创建正在进行中',
                    'execution_time': time.time() - start_time
                }

            try:
                self.logger.info(f"开始创建版本分支: {source_branch} -> {version_name}")

                # 1. 验证分支名称
                is_valid, error_msg = self.validate_branch_name(version_name, pattern_type)
                if not is_valid:
                    return {
                        'success': False,
                        'error': f'分支名称验证失败: {error_msg}',
                        'execution_time': time.time() - start_time
                    }

                # 2. 检查分支是否已存在
                if self.check_branch_exists(project_id, version_name):
                    return {
                        'success': False,
                        'error': f'分支 {version_name} 已存在',
                        'execution_time': time.time() - start_time
                    }

                # 3. 检查未合并的MR
                mr_check_result = None
                if check_open_mrs and not force_create:
                    mr_check_result = self.check_open_merge_requests(project_id, source_branch)

                    if mr_check_result.get('has_open_mrs', False):
                        self.logger.warning(f"分支 {source_branch} 有未合并的MR，跳过创建")

                        # 格式化MR信息用于输出
                        mr_details = []
                        for mr in mr_check_result.get('outgoing_mrs', []):
                            mr_details.append(f"  !{mr['iid']} - {mr['title']} ({mr['author']} -> {mr['target_branch']})")
                        for mr in mr_check_result.get('incoming_mrs', []):
                            mr_details.append(f"  !{mr['iid']} - {mr['title']} ({mr['source_branch']} -> {mr['author']})")

                        return {
                            'success': False,
                            'error': f'分支 {source_branch} 有 {mr_check_result["total_open_mrs"]} 个未合并的MR',
                            'open_mrs': mr_check_result,
                            'mr_details': mr_details,
                            'execution_time': time.time() - start_time
                        }

                # 4. 创建分支
                create_result = self.create_branch(project_id, source_branch, version_name)

                execution_time = time.time() - start_time

                if create_result['success']:
                    # 构建成功结果
                    result = {
                        'success': True,
                        'project_id': project_id,
                        'source_branch': source_branch,
                        'version_branch': version_name,
                        'commit': create_result['commit'],
                        'commit_short': create_result['commit_short'],
                        'created_at': create_result['created_at'],
                        'execution_time': execution_time,
                        'mr_check_result': mr_check_result
                    }

                    # 5. 发送 WPS Webhook 通知
                    webhook_data = {
                        'project_id': project_id,
                        'source_branch': source_branch,
                        'version_branch': version_name,
                        'commit': create_result['commit'],
                        'commit_short': create_result['commit_short'],
                        'created_at': create_result['created_at'],
                        'status': 'success'
                    }

                    webhook_success, webhook_error = self.send_webhook_notification(webhook_data)
                    result['webhook_notification'] = {
                        'success': webhook_success,
                        'error': webhook_error
                    }

                    self.logger.info(f"版本分支创建完成: {version_name} (执行时间: {execution_time:.2f}s)")
                    return result
                else:
                    # 创建失败
                    return {
                        'success': False,
                        'error': create_result['error'],
                        'execution_time': execution_time,
                        'mr_check_result': mr_check_result
                    }

            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(f"创建版本分支失败: {e}")

                return {
                    'success': False,
                    'error': str(e),
                    'execution_time': execution_time
                }

    def batch_create_version_branches(self,
                                    project_id: str,
                                    source_branch: str,
                                    version_list: List[str],
                                    pattern_type: str = 'semantic',
                                    force_create: bool = False) -> List[Dict[str, any]]:
        """
        批量创建版本分支

        Args:
            project_id: GitLab项目ID
            source_branch: 源分支
            version_list: 版本名称列表
            pattern_type: 分支名验证模式
            force_create: 强制创建

        Returns:
            创建结果列表
        """
        self.logger.info(f"开始批量创建 {len(version_list)} 个版本分支")

        results = []
        for i, version in enumerate(version_list, 1):
            self.logger.info(f"创建版本 {i}/{len(version_list)}: {version}")

            result = self.create_version_branch(
                project_id=project_id,
                source_branch=source_branch,
                version_name=version,
                pattern_type=pattern_type,
                force_create=force_create
            )

            results.append(result)

            # 如果失败且不是强制创建，停止后续创建
            if not result['success'] and not force_create:
                self.logger.error(f"版本 {version} 创建失败，停止批量创建")
                break

        return results


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='GitLab分支创建流水线')

    # 必需参数
    parser.add_argument('--project-id', required=True, help='GitLab项目ID')
    parser.add_argument('--source-branch', required=True, help='源分支名称')
    parser.add_argument('--version', required=False, help='版本名称')

    # 批量模式
    parser.add_argument('--batch-mode', action='store_true', help='批量模式')
    parser.add_argument('--versions-file', help='版本列表文件路径')

    # 验证和创建选项
    parser.add_argument('--pattern-type', choices=['semantic', 'major_minor', 'date_based', 'custom', 'none'],
                       default='none', help='分支名称验证模式（none=不限制格式，默认不验证）')
    parser.add_argument('--force-create', action='store_true', help='强制创建（忽略未合并MR）')
    parser.add_argument('--skip-mr-check', action='store_true', help='跳过未合并MR检查')

    # WPS Webhook 配置
    parser.add_argument('--webhook-url', help='WPS Webhook URL地址')
    parser.add_argument('--webhook-method', choices=['POST', 'GET'], default='POST',
                       help='Webhook请求方法（默认POST）')
    parser.add_argument('--webhook-origin', choices=['www.kdocs.cn', 'www.wps.cn'],
                       default='www.wps.cn', help='Origin header值（默认www.wps.cn）')
    parser.add_argument('--webhook-json', help='自定义JSON内容（字符串格式）')

    # 其他选项
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    parser.add_argument('--lock-timeout', type=int, default=0, help='锁等待超时时间（秒）')

    args = parser.parse_args()

    # 设置日志
    logger = setup_logging(args.log_level)

    # 验证参数
    if not args.batch_mode and not args.version:
        print("❌ 请提供 --version 或使用 --batch-mode")
        sys.exit(1)

    # 全局锁
    global_lock_name = f"gitlab_branch_creation_global_{args.project_id}"

    with file_lock(global_lock_name, timeout=args.lock_timeout) as locked:
        if not locked:
            print("❌ GitLab分支创建流水线正在运行，请稍后再试")
            sys.exit(1)

        try:
            # 创建流水线实例
            pipeline = BranchCreationPipeline(
                log_level=args.log_level,
                webhook_url=args.webhook_url,
                webhook_method=args.webhook_method,
                webhook_origin=args.webhook_origin,
                webhook_custom_json=args.webhook_json
            )

            if args.batch_mode:
                # 批量模式
                versions = []

                if args.versions_file:
                    # 从文件读取版本列表
                    with open(args.versions_file, 'r') as f:
                        versions = [line.strip() for line in f if line.strip()]
                else:
                    # 从标准输入读取版本列表
                    print("请输入要创建的版本列表（每行一个版本）：")
                    versions = [line.strip() for line in sys.stdin if line.strip()]

                if not versions:
                    print("❌ 未提供版本列表")
                    sys.exit(1)

                results = pipeline.batch_create_version_branches(
                    project_id=args.project_id,
                    source_branch=args.source_branch,
                    version_list=versions,
                    pattern_type=args.pattern_type,
                    force_create=args.force_create
                )

                # 打印结果
                print(f"\n📊 批量创建完成，共 {len(results)} 个版本")
                success_count = sum(1 for r in results if r['success'])
                print(f"成功: {success_count}, 失败: {len(results) - success_count}")

                for result in results:
                    if result['success']:
                        print(f"  ✅ {result['version_branch']} (commit: {result['commit_short']})")
                    else:
                        print(f"  ❌ {result.get('version_branch', '未知')} - {result.get('error', 'Unknown error')}")

            else:
                # 单版本模式
                result = pipeline.create_version_branch(
                    project_id=args.project_id,
                    source_branch=args.source_branch,
                    version_name=args.version,
                    pattern_type=args.pattern_type,
                    force_create=args.force_create,
                    check_open_mrs=not args.skip_mr_check
                )

                # 打印结果
                print_result(result)

        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            sys.exit(1)


def print_result(result):
    """打印创建结果"""
    if result['success']:
        print("\n✅ 版本分支创建成功")
        print(f"  项目ID: {result['project_id']}")
        print(f"  源分支: {result['source_branch']}")
        print(f"  版本分支: {result['version_branch']}")
        print(f"  提交: {result['commit_short']}")
        print(f"  创建时间: {result['created_at']}")
        print(f"  执行时间: {result['execution_time']:.2f}s")

        # 显示MR检查结果
        if result.get('mr_check_result'):
            mr_check = result['mr_check_result']
            print(f"\n📋 MR检查结果:")
            print(f"  传出MR: {len(mr_check.get('outgoing_mrs', []))} 个")
            print(f"  传入MR: {len(mr_check.get('incoming_mrs', []))} 个")
            print(f"  总计: {mr_check.get('total_open_mrs', 0)} 个")

        # 显示Webhook通知结果
        if result.get('webhook_notification'):
            webhook = result['webhook_notification']
            if webhook.get('success'):
                print(f"\n📡 WPS Webhook 通知: ✅ 发送成功")
            else:
                print(f"\n📡 WPS Webhook 通知: ❌ 发送失败")
                if webhook.get('error'):
                    print(f"  错误: {webhook['error']}")
    else:
        print("\n❌ 版本分支创建失败")
        print(f"  错误: {result.get('error', 'Unknown error')}")

        # 显示未合并的MR详情
        if result.get('mr_details'):
            print(f"\n📋 未合并的MR:")
            for mr_detail in result['mr_details']:
                print(f"  {mr_detail}")

        print(f"  执行时间: {result['execution_time']:.2f}s")


if __name__ == "__main__":
    main()