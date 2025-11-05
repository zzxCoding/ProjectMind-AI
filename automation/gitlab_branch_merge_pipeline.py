#!/usr/bin/env python3
"""
GitLab分支合并流水线
自动化创建合并请求并批准合并到目标分支
"""

import os
import sys
import argparse
import time
from datetime import datetime
from typing import Dict, List, Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.gitlab_client import GitLabClient
from shared.utils import setup_logging
from shared.file_lock import file_lock


class BranchMergePipeline:
    """分支合并流水线"""

    def __init__(self, log_level: str = 'INFO'):
        """
        初始化合并流水线

        Args:
            log_level: 日志级别
        """
        self.logger = setup_logging(level=log_level)
        self.gitlab_client = GitLabClient(log_level=log_level)
        self.logger.info("GitLab分支合并流水线初始化完成")

    def merge_branches(self,
                       project_id: str,
                       source_branch: str,
                       target_branch: str = 'main',
                       mr_title: Optional[str] = None,
                       mr_description: Optional[str] = None,
                       assignee_id: Optional[int] = None,
                       reviewer_ids: Optional[List[int]] = None,
                       labels: Optional[List[str]] = None,
                       auto_merge: bool = True,
                       merge_commit_message: Optional[str] = None,
                       remove_source_branch: bool = False,
                       squash: bool = False) -> Dict:
        """
        执行分支合并流程

        Args:
            project_id: GitLab项目ID
            source_branch: 源分支名称
            target_branch: 目标分支名称，默认为'main'
            mr_title: 合并请求标题
            mr_description: 合并请求描述
            assignee_id: 指派给的用户ID
            reviewer_ids: 审查者用户ID列表
            labels: 标签列表
            auto_merge: 是否自动合并
            merge_commit_message: 合并提交消息
            remove_source_branch: 合并后是否删除源分支
            squash: 是否压缩提交

        Returns:
            合并结果字典
        """
        start_time = time.time()
        lock_name = f"branch_merge_{project_id}_{source_branch}_{target_branch}"

        # 获取锁，防止并发合并
        with file_lock(lock_name, timeout=0) as locked:
            if not locked:
                self.logger.warning(
                    f"分支合并正在进行中: {source_branch} -> {target_branch}")
                return {
                    'success': False,
                    'error': '分支合并正在进行中',
                    'execution_time': time.time() - start_time
                }

            try:
                self.logger.info(
                    f"开始合并分支: {source_branch} -> {target_branch}")

                # 1. 创建合并请求
                if not mr_title:
                    mr_title = f"Merge {source_branch} into {target_branch}"

                self.logger.info(f"创建合并请求: {mr_title}")

                mr = self.gitlab_client.create_merge_request(
                    project_id=project_id,
                    source_branch=source_branch,
                    target_branch=target_branch,
                    title=mr_title,
                    description=mr_description,
                    assignee_id=assignee_id,
                    reviewer_ids=reviewer_ids,
                    labels=labels,
                    remove_source_branch=remove_source_branch,
                    squash=squash
                )

                if not mr:
                    execution_time = time.time() - start_time
                    self.logger.error("创建合并请求失败")
                    return {
                        'success': False,
                        'error': '创建合并请求失败',
                        'execution_time': execution_time
                    }

                mr_iid = mr['iid']
                mr_web_url = mr['web_url']
                self.logger.info(f"合并请求创建成功: !{mr_iid}")

                # 2. 自动合并（如果启用）
                merge_result = None
                if auto_merge:
                    self.logger.info(f"自动合并MR: !{mr_iid}")

                    # 构建合并提交消息
                    if not merge_commit_message:
                        merge_commit_message = f"Merge branch '{source_branch}' into '{target_branch}'"

                    # 执行批准并合并
                    merge_result = self.gitlab_client.approve_and_merge_merge_request(
                        project_id=project_id,
                        merge_request_iid=mr_iid,
                        merge_commit_message=merge_commit_message,
                        merge_when_pipeline_succeeds=False,
                        wait_for_pipeline=False
                    )

                    if merge_result.get('success'):
                        self.logger.info(
                            f"合并成功: !{mr_iid} -> {target_branch}")
                    else:
                        self.logger.warning(
                            f"自动合并失败: {merge_result.get('error', 'Unknown error')}")

                # 3. 计算执行时间
                execution_time = time.time() - start_time

                # 4. 构建返回结果
                result = {
                    'success': True,
                    'project_id': project_id,
                    'source_branch': source_branch,
                    'target_branch': target_branch,
                    'mr_iid': mr_iid,
                    'mr_title': mr['title'],
                    'mr_web_url': mr_web_url,
                    'auto_merge': auto_merge,
                    'merge_result': merge_result,
                    'execution_time': execution_time,
                    'merge_time': datetime.now().isoformat()
                }

                self.logger.info(
                    f"分支合并完成: {source_branch} -> {target_branch} (执行时间: {execution_time:.2f}s)")
                return result

            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(f"分支合并失败: {e}")

                return {
                    'success': False,
                    'project_id': project_id,
                    'source_branch': source_branch,
                    'target_branch': target_branch,
                    'error': str(e),
                    'execution_time': execution_time
                }

    def batch_merge_branches(self,
                             project_id: str,
                             branches: List[str],
                             target_branch: str = 'main',
                             **merge_kwargs) -> List[Dict]:
        """
        批量合并多个分支到目标分支

        Args:
            project_id: GitLab项目ID
            branches: 源分支列表
            target_branch: 目标分支名称
            **merge_kwargs: 合并参数

        Returns:
            合并结果列表
        """
        self.logger.info(
            f"开始批量合并 {len(branches)} 个分支到 {target_branch}")

        results = []
        for branch in branches:
            self.logger.info(f"处理分支: {branch}")

            result = self.merge_branches(
                project_id=project_id,
                source_branch=branch,
                target_branch=target_branch,
                **merge_kwargs
            )

            results.append(result)

            # 如果失败，停止后续合并
            if not result['success']:
                self.logger.error(
                    f"分支 {branch} 合并失败，停止后续合并")
                break

        return results


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='GitLab分支合并流水线')

    # 必需参数
    parser.add_argument('--project-id', required=True,
                        help='GitLab项目ID')
    parser.add_argument('--source-branch', required=True,
                        help='源分支名称')

    # 可选参数
    parser.add_argument('--target-branch', default='main',
                        help='目标分支名称 (默认: main)')
    parser.add_argument('--title', help='合并请求标题')
    parser.add_argument('--description', help='合并请求描述')
    parser.add_argument('--assignee-id', type=int, help='指派给的用户ID')
    parser.add_argument('--reviewer-ids', type=int, nargs='+',
                        help='审查者用户ID列表')
    parser.add_argument('--labels', type=str, nargs='+',
                        help='标签列表')
    parser.add_argument('--merge-commit-message',
                        help='合并提交消息')
    parser.add_argument('--remove-source-branch', action='store_true',
                        help='合并后删除源分支')
    parser.add_argument('--no-squash', action='store_true',
                        help='不压缩提交')

    # 模式选择
    parser.add_argument('--no-auto-merge', action='store_true',
                        help='不自动合并（仅创建MR）')
    parser.add_argument('--batch-mode', action='store_true',
                        help='批量模式（从文件或标准输入读取分支列表）')
    parser.add_argument('--branches-file', help='分支列表文件路径')

    # 其他参数
    parser.add_argument('--log-level', default='INFO',
                        help='日志级别 (默认: INFO)')
    parser.add_argument('--lock-timeout', type=int, default=0,
                        help='锁等待超时时间（秒），0表示不等待')

    args = parser.parse_args()

    # 设置日志
    logger = setup_logging(args.log_level)

    # 全局锁逻辑
    global_lock_name = f"gitlab_branch_merge_global_{args.project_id}"

    with file_lock(global_lock_name, timeout=args.lock_timeout) as locked:
        if not locked:
            print("❌ GitLab分支合并流水线正在运行，请稍后再试")
            sys.exit(1)

        try:
            # 创建流水线实例
            pipeline = BranchMergePipeline(log_level=args.log_level)

            # 构建合并参数
            merge_kwargs = {
                'mr_title': args.title,
                'mr_description': args.description,
                'assignee_id': args.assignee_id,
                'reviewer_ids': args.reviewer_ids,
                'labels': args.labels,
                'merge_commit_message': args.merge_commit_message,
                'remove_source_branch': args.remove_source_branch,
                'squash': not args.no_squash,
                'auto_merge': not args.no_auto_merge
            }

            # 执行合并
            if args.batch_mode:
                # 批量模式
                branches = []

                if args.branches_file:
                    # 从文件读取分支列表
                    with open(args.branches_file, 'r') as f:
                        branches = [line.strip()
                                   for line in f if line.strip()]
                else:
                    # 从标准输入读取分支列表
                    print("请输入要合并的分支列表（每行一个分支）：")
                    branches = [line.strip()
                               for line in sys.stdin if line.strip()]

                if not branches:
                    print("❌ 未提供分支列表")
                    sys.exit(1)

                results = pipeline.batch_merge_branches(
                    project_id=args.project_id,
                    branches=branches,
                    target_branch=args.target_branch,
                    **merge_kwargs
                )

                # 打印结果
                print(f"\n📊 批量合并完成，共 {len(results)} 个分支")
                for result in results:
                    if result['success']:
                        print(
                            f"  ✅ {result['source_branch']} -> {result['target_branch']}")
                    else:
                        print(
                            f"  ❌ {result['source_branch']} 失败: {result.get('error', 'Unknown error')}")

            else:
                # 单分支模式
                result = pipeline.merge_branches(
                    project_id=args.project_id,
                    source_branch=args.source_branch,
                    target_branch=args.target_branch,
                    **merge_kwargs
                )

                # 打印结果
                print_result(result)

        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            sys.exit(1)


def print_result(result):
    """打印合并结果"""
    if result['success']:
        print("\n✅ 分支合并成功")
        print(f"  项目ID: {result['project_id']}")
        print(f"  分支: {result['source_branch']} -> {result['target_branch']}")
        print(f"  MR: !{result['mr_iid']} - {result['mr_title']}")
        print(f"  链接: {result['mr_web_url']}")

        if result['auto_merge'] and result['merge_result']:
            merge_result = result['merge_result']
            if merge_result.get('success'):
                print(f"  状态: ✅ 自动合并成功")
            else:
                print(f"  状态: ⚠️  需要手动合并 ({merge_result.get('error')})")

        print(f"  执行时间: {result['execution_time']:.2f}s")
    else:
        print("\n❌ 分支合并失败")
        print(f"  错误: {result.get('error', 'Unknown error')}")
        print(f"  执行时间: {result['execution_time']:.2f}s")


if __name__ == "__main__":
    main()
