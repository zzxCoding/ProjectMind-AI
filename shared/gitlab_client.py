#!/usr/bin/env python3
"""
GitLab客户端
封装python-gitlab库，提供GitLab数据获取和分析功能
"""

import os
import sys
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import gitlab
from gitlab.exceptions import (
    GitlabAuthenticationError,
    GitlabGetError,
    GitlabCreateError,
    GitlabUpdateError
)

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from config.gitlab_config import GitLabConfig, get_default_config
from shared.utils import setup_logging

class GitLabClient:
    """GitLab API客户端"""
    
    def __init__(self, config: Optional[GitLabConfig] = None, log_level: str = 'INFO'):
        """
        初始化GitLab客户端
        
        Args:
            config: GitLab配置，默认从环境变量获取
            log_level: 日志级别，默认INFO
        """
        self.config = config or get_default_config()
        self.logger = setup_logging(level=log_level)
        self._gitlab = None
        self._project = None
    
    def _parse_datetime_safe(self, date_str: Optional[str]) -> Optional[datetime]:
        """安全解析日期时间字符串"""
        if not date_str:
            return None
        try:
            if date_str.endswith('Z'):
                date_str = date_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(date_str)
            # 移除时区信息，保持一致性
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt
        except Exception as e:
            self.logger.warning(f"解析日期时间失败 '{date_str}': {e}")
            return None
    
    @property
    def gitlab(self):
        """懒加载GitLab连接"""
        if self._gitlab is None:
            self._gitlab = gitlab.Gitlab(
                url=self.config.url,
                private_token=self.config.token,
                timeout=self.config.timeout,
                ssl_verify=self.config.verify_ssl,
                keep_base_url=True  # 保持用户提供的基础URL
            )
        return self._gitlab
    
    @property
    def project(self):
        """获取当前项目"""
        if self._project is None and self.config.project_id:
            try:
                self._project = self.gitlab.projects.get(self.config.project_id)
            except GitlabGetError as e:
                self.logger.error(f"获取项目失败 {self.config.project_id}: {e}")
                raise
        return self._project
    
    def test_connection(self) -> bool:
        """测试GitLab连接"""
        try:
            # 尝试获取当前用户信息
            user = self.gitlab.auth()
            if user:
                username = user.get('username', 'Unknown')
                self.logger.info(f"GitLab连接成功，用户: {username}")
                return True
            else:
                # auth()返回None时，尝试其他方式验证连接
                try:
                    # 尝试获取用户列表（需要基本权限）
                    self.gitlab.users.list(per_page=1, get_all=False)
                    self.logger.info("GitLab连接成功（通过用户列表验证）")
                    return True
                except Exception:
                    # 尝试获取项目列表
                    try:
                        self.gitlab.projects.list(per_page=1, get_all=False)
                        self.logger.info("GitLab连接成功（通过项目列表验证）")
                        return True
                    except Exception as fallback_error:
                        self.logger.error(f"GitLab连接验证失败: {fallback_error}")
                        return False
        except GitlabAuthenticationError as e:
            self.logger.error(f"GitLab认证失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"GitLab连接失败: {e}")
            return False
    
    def get_project_info(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取项目信息
        
        Args:
            project_id: 项目ID，默认使用配置中的项目ID
            
        Returns:
            项目信息字典
        """
        try:
            pid = project_id or self.config.project_id
            if not pid:
                raise ValueError("未指定项目ID")
            
            project = self.gitlab.projects.get(pid)
            return {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'web_url': project.web_url,
                'created_at': project.created_at,
                'last_activity_at': project.last_activity_at,
                'default_branch': project.default_branch,
                'visibility': project.visibility,
                'star_count': project.star_count,
                'forks_count': project.forks_count,
                'issues_enabled': project.issues_enabled,
                'merge_requests_enabled': project.merge_requests_enabled
            }
        except Exception as e:
            self.logger.error(f"获取项目信息失败: {e}")
            return {}
    
    def get_merge_requests(self, project_id: Optional[str] = None,
                          state: str = 'all',
                          target_branch: Optional[str] = None,
                          since: Optional[datetime] = None,
                          until: Optional[datetime] = None,
                          author_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取合并请求列表
        
        Args:
            project_id: 项目ID
            state: 状态 (opened, closed, merged, all)
            target_branch: 目标分支
            since: 开始时间
            until: 结束时间
            author_id: 作者ID
            
        Returns:
            合并请求列表
        """
        try:
            pid = project_id or self.config.project_id
            if not pid:
                raise ValueError("未指定项目ID")
            
            project = self.gitlab.projects.get(pid)
            
            # 构建查询参数
            params = {
                'state': state,
                'order_by': 'created_at',
                'sort': 'desc',
                'per_page': 100
            }
            
            if target_branch:
                params['target_branch'] = target_branch
            if since:
                params['created_after'] = since.isoformat()
            if until:
                params['created_before'] = until.isoformat()
            if author_id:
                params['author_id'] = author_id
            
            # 获取所有合并请求
            merge_requests = []
            mrs = project.mergerequests.list(all=True, **params)
            
            for mr in mrs:
                # 处理时间格式，确保时区一致
                try:
                    created_at_str = mr.created_at
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str.replace('Z', '+00:00')
                    created_at = datetime.fromisoformat(created_at_str)
                    # 转换为不带时区的datetime，与since/until保持一致
                    if created_at.tzinfo:
                        created_at = created_at.replace(tzinfo=None)
                except Exception as e:
                    self.logger.warning(f"解析创建时间失败 {mr.iid}: {e}")
                    continue
                
                merged_at = None
                if hasattr(mr, 'merged_at') and mr.merged_at:
                    try:
                        merged_at_str = mr.merged_at
                        if merged_at_str.endswith('Z'):
                            merged_at_str = merged_at_str.replace('Z', '+00:00')
                        merged_at = datetime.fromisoformat(merged_at_str)
                        if merged_at.tzinfo:
                            merged_at = merged_at.replace(tzinfo=None)
                    except Exception as e:
                        self.logger.warning(f"解析合并时间失败 {mr.iid}: {e}")
                
                # 时间过滤
                if since and created_at < since:
                    continue
                if until and created_at > until:
                    continue
                
                merge_requests.append({
                    'iid': mr.iid,
                    'id': mr.id,
                    'title': mr.title,
                    'description': mr.description,
                    'state': mr.state,
                    'created_at': created_at,
                    'updated_at': self._parse_datetime_safe(mr.updated_at),
                    'merged_at': merged_at,
                    'closed_at': self._parse_datetime_safe(getattr(mr, 'closed_at', None)),
                    'source_branch': mr.source_branch,
                    'target_branch': mr.target_branch,
                    'author': {
                        'id': mr.author.get('id'),
                        'name': mr.author.get('name'),
                        'username': mr.author.get('username'),
                        'email': mr.author.get('email', '')
                    },
                    'assignees': [
                        {
                            'id': assignee.get('id'),
                            'name': assignee.get('name'),
                            'username': assignee.get('username')
                        }
                        for assignee in (mr.assignees or [])
                    ],
                    'reviewers': [
                        {
                            'id': reviewer.get('id'),
                            'name': reviewer.get('name'),
                            'username': reviewer.get('username')
                        }
                        for reviewer in (getattr(mr, 'reviewers', None) or [])
                    ],
                    'web_url': mr.web_url,
                    'changes_count': getattr(mr, 'changes_count', 0),
                    'user_notes_count': getattr(mr, 'user_notes_count', 0),
                    'upvotes': getattr(mr, 'upvotes', 0),
                    'downvotes': getattr(mr, 'downvotes', 0),
                    'work_in_progress': getattr(mr, 'work_in_progress', False),
                    'draft': getattr(mr, 'draft', False),
                    'merge_status': getattr(mr, 'merge_status', 'unknown'),
                    'labels': getattr(mr, 'labels', [])
                })
            
            self.logger.info(f"获取到 {len(merge_requests)} 个合并请求")
            return merge_requests
            
        except Exception as e:
            self.logger.error(f"获取合并请求失败: {e}")
            return []
    
    def get_merge_request_details(self, project_id: Optional[str], merge_request_iid: int) -> Dict[str, Any]:
        """
        获取合并请求详细信息
        
        Args:
            project_id: 项目ID
            merge_request_iid: 合并请求IID
            
        Returns:
            合并请求详细信息
        """
        try:
            pid = project_id or self.config.project_id
            if not pid:
                raise ValueError("未指定项目ID")
            
            project = self.gitlab.projects.get(pid)
            mr = project.mergerequests.get(merge_request_iid)
            
            # 获取提交列表
            commits = []
            try:
                for commit in mr.commits():
                    # commit是GitLab对象，需要使用属性访问
                    commit_data = {
                        'id': getattr(commit, 'id', ''),
                        'short_id': getattr(commit, 'short_id', ''),
                        'title': getattr(commit, 'title', ''),
                        'message': getattr(commit, 'message', ''),
                        'author_name': getattr(commit, 'author_name', ''),
                        'author_email': getattr(commit, 'author_email', ''),
                        'additions': 0,  # 统计信息可能不可用
                        'deletions': 0
                    }
                    
                    # 安全处理创建时间
                    try:
                        created_at_str = getattr(commit, 'created_at', '')
                        if created_at_str:
                            if created_at_str.endswith('Z'):
                                created_at_str = created_at_str.replace('Z', '+00:00')
                            commit_data['created_at'] = datetime.fromisoformat(created_at_str)
                        else:
                            commit_data['created_at'] = None
                    except Exception:
                        commit_data['created_at'] = None
                    
                    commits.append(commit_data)
            except Exception as e:
                self.logger.warning(f"获取提交列表失败: {e}")
            
            # 获取变更文件
            changes = []
            try:
                mr_changes = mr.changes()
                for change in mr_changes.get('changes', []):
                    changes.append({
                        'old_path': change.get('old_path'),
                        'new_path': change.get('new_path'),
                        'new_file': change.get('new_file', False),
                        'renamed_file': change.get('renamed_file', False),
                        'deleted_file': change.get('deleted_file', False),
                        'diff': change.get('diff', '')
                    })
            except Exception as e:
                self.logger.warning(f"获取变更文件失败: {e}")
            
            # 获取讨论/评论
            discussions = []
            try:
                for discussion in mr.discussions.list(all=True):
                    discussion_data = {
                        'id': discussion.id,
                        'individual_note': discussion.individual_note,
                        'notes': []
                    }
                    
                    for note in discussion.attributes.get('notes', []):
                        discussion_data['notes'].append({
                            'id': note.get('id'),
                            'body': note.get('body'),
                            'author': note.get('author', {}),
                            'created_at': note.get('created_at'),
                            'system': note.get('system', False),
                            'resolvable': note.get('resolvable', False),
                            'resolved': note.get('resolved', False)
                        })
                    
                    discussions.append(discussion_data)
            except Exception as e:
                self.logger.warning(f"获取讨论失败: {e}")
            
            return {
                'basic_info': {
                    'iid': mr.iid,
                    'title': mr.title,
                    'description': mr.description,
                    'state': mr.state,
                    'author': mr.author,
                    'created_at': mr.created_at,
                    'merged_at': getattr(mr, 'merged_at', None),
                    'source_branch': mr.source_branch,
                    'target_branch': mr.target_branch
                },
                'commits': commits,
                'changes': changes,
                'discussions': discussions,
                'statistics': {
                    'commits_count': len(commits),
                    'changes_count': len(changes),
                    'discussions_count': len(discussions),
                    'notes_count': sum(len(d['notes']) for d in discussions)
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取合并请求详情失败: {e}")
            return {}
    
    def get_merge_request_details_smart(self, project_id: Optional[str], merge_request_iid: int, 
                                      enable_smart_context: bool = True) -> Dict[str, Any]:
        """
        获取合并请求详细信息（智能上下文版本）
        
        Args:
            project_id: 项目ID
            merge_request_iid: 合并请求IID
            enable_smart_context: 是否启用智能上下文（仅对修改文件生效）
            
        Returns:
            合并请求详细信息（格式与原方法兼容）
        """
        try:
            pid = project_id or self.config.project_id
            if not pid:
                raise ValueError("未指定项目ID")
            
            project = self.gitlab.projects.get(pid)
            mr = project.mergerequests.get(merge_request_iid)
            
            # 获取提交列表（保持原逻辑）
            commits = []
            try:
                for commit in mr.commits():
                    commit_data = {
                        'id': getattr(commit, 'id', ''),
                        'short_id': getattr(commit, 'short_id', ''),
                        'title': getattr(commit, 'title', ''),
                        'message': getattr(commit, 'message', ''),
                        'author_name': getattr(commit, 'author_name', ''),
                        'author_email': getattr(commit, 'author_email', ''),
                        'additions': 0,
                        'deletions': 0
                    }
                    
                    try:
                        created_at_str = getattr(commit, 'created_at', '')
                        if created_at_str:
                            if created_at_str.endswith('Z'):
                                created_at_str = created_at_str.replace('Z', '+00:00')
                            commit_data['created_at'] = datetime.fromisoformat(created_at_str)
                        else:
                            commit_data['created_at'] = None
                    except Exception:
                        commit_data['created_at'] = None
                    
                    commits.append(commit_data)
            except Exception as e:
                self.logger.warning(f"获取提交列表失败: {e}")
            
            # 获取变更文件（智能上下文处理）
            changes = []
            try:
                if enable_smart_context:
                    # 使用智能上下文获取
                    changes = self._get_changes_with_smart_context(mr, project_id, merge_request_iid)
                else:
                    # 使用原逻辑
                    mr_changes = mr.changes()
                    for change in mr_changes.get('changes', []):
                        changes.append({
                            'old_path': change.get('old_path'),
                            'new_path': change.get('new_path'),
                            'new_file': change.get('new_file', False),
                            'renamed_file': change.get('renamed_file', False),
                            'deleted_file': change.get('deleted_file', False),
                            'diff': change.get('diff', '')
                        })
            except Exception as e:
                self.logger.warning(f"获取变更文件失败: {e}")
            
            # 获取讨论/评论（保持原逻辑）
            discussions = []
            try:
                for discussion in mr.discussions.list(all=True):
                    discussion_data = {
                        'id': discussion.id,
                        'individual_note': discussion.individual_note,
                        'notes': []
                    }
                    
                    for note in discussion.attributes.get('notes', []):
                        discussion_data['notes'].append({
                            'id': note.get('id'),
                            'body': note.get('body'),
                            'author': note.get('author', {}),
                            'created_at': note.get('created_at'),
                            'system': note.get('system', False),
                            'resolvable': note.get('resolvable', False),
                            'resolved': note.get('resolved', False)
                        })
                    
                    discussions.append(discussion_data)
            except Exception as e:
                self.logger.warning(f"获取讨论失败: {e}")
            
            return {
                'basic_info': {
                    'iid': mr.iid,
                    'title': mr.title,
                    'description': mr.description,
                    'state': mr.state,
                    'author': mr.author,
                    'created_at': mr.created_at,
                    'merged_at': getattr(mr, 'merged_at', None),
                    'source_branch': mr.source_branch,
                    'target_branch': mr.target_branch
                },
                'commits': commits,
                'changes': changes,
                'discussions': discussions,
                'statistics': {
                    'commits_count': len(commits),
                    'changes_count': len(changes),
                    'discussions_count': len(discussions),
                    'notes_count': sum(len(d['notes']) for d in discussions)
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取合并请求详情失败（智能模式）: {e}")
            return {}
    
    def _get_changes_with_smart_context(self, mr, project_id: str, merge_request_iid: int) -> List[Dict[str, Any]]:
        """使用智能上下文获取变更文件"""
        changes = []
        
        try:
            # 首先获取基础变更信息
            mr_changes = mr.changes()
            base_changes = mr_changes.get('changes', [])
            
            for change in base_changes:
                change_data = {
                    'old_path': change.get('old_path'),
                    'new_path': change.get('new_path'),
                    'new_file': change.get('new_file', False),
                    'renamed_file': change.get('renamed_file', False),
                    'deleted_file': change.get('deleted_file', False),
                }
                
                # 检查是否为修改文件
                if self._is_modified_file(change_data):
                    # 对修改文件应用智能上下文
                    original_size = len(change.get('diff', ''))
                    smart_diff = self._get_smart_diff_for_file(mr, change, project_id, merge_request_iid)
                    change_data['diff'] = smart_diff
                    new_size = len(smart_diff)
                    file_path = change_data.get('new_path', change_data.get('old_path'))
                    self.logger.info(f"智能处理修改文件 {file_path}: {original_size} -> {new_size} 字符 ({new_size-original_size:+d})")
                    
                    # 输出完整diff内容对比（用于调试）
                    if new_size > original_size and file_path and ('.java' in file_path or '.xml' in file_path):
                        self.logger.debug(f"        === 智能增强后完整diff内容 ===")
                        self.logger.debug(f"        文件: {file_path}")
                        self.logger.debug(f"        原始大小: {original_size} 字符")
                        self.logger.debug(f"        智能大小: {new_size} 字符")
                        self.logger.debug(f"        增加: {new_size - original_size} 字符 (+{((new_size - original_size) / original_size * 100):.1f}%)")
                        self.logger.debug(f"        ")
                        
                        # 输出完整的diff内容
                        smart_lines = smart_diff.split('\n')
                        for i, line in enumerate(smart_lines, 1):
                            self.logger.debug(f"          {i:3d}: {line}")
                        
                        self.logger.debug(f"        === 智能diff内容结束 (共{len(smart_lines)}行) ===")
                else:
                    # 新增/删除文件使用原逻辑
                    change_data['diff'] = change.get('diff', '')
                    file_path = change_data.get('new_path', change_data.get('old_path'))
                    self.logger.debug(f"文件 {file_path} 为新增/删除文件，使用原始diff")
                
                changes.append(change_data)
                
        except Exception as e:
            self.logger.warning(f"智能上下文获取失败，回退到原方法: {e}")
            # 如果智能获取失败，回退到原方法
            mr_changes = mr.changes()
            for change in mr_changes.get('changes', []):
                changes.append({
                    'old_path': change.get('old_path'),
                    'new_path': change.get('new_path'),
                    'new_file': change.get('new_file', False),
                    'renamed_file': change.get('renamed_file', False),
                    'deleted_file': change.get('deleted_file', False),
                    'diff': change.get('diff', '')
                })
        
        return changes
    
    def _is_modified_file(self, change: Dict[str, Any]) -> bool:
        """检测是否为修改文件（非新增、非删除）"""
        return not change.get('new_file', False) and not change.get('deleted_file', False)
    
    def _get_smart_diff_for_file(self, mr, change: Dict[str, Any], project_id: str, merge_request_iid: int) -> str:
        """为单个文件获取智能上下文的diff"""
        try:
            file_path = change.get('new_path', change.get('old_path', ''))
            original_diff = change.get('diff', '')
            
            # 检测文件类型
            file_type = self._detect_file_type_for_context(file_path)
            
            # 分析原始diff来估算修改行数
            modified_lines = self._count_modified_lines(original_diff)
            
            # 计算智能上下文行数
            context_lines = self._calculate_smart_context_lines(modified_lines, file_type)
            
            self.logger.info(f"🔍 智能分析文件 {file_path}: 类型={file_type}, 修改行={modified_lines}, 计算上下文={context_lines}行")
            
            # 直接使用经过测试验证的最佳API方法
            enhanced_diff = self._get_best_diff_from_gitlab(mr, file_path)
            
            if enhanced_diff and len(enhanced_diff) > len(original_diff):
                self.logger.info(f"✅ 获得更完整diff: {file_path} ({len(original_diff)} -> {len(enhanced_diff)} 字符, +{len(enhanced_diff) - len(original_diff)})")
                return enhanced_diff
            else:
                # 如果无法获得更好的diff，返回原始diff
                self.logger.info(f"📄 使用原始diff: {file_path} ({len(original_diff)} 字符)")
                return original_diff
                
        except Exception as e:
            self.logger.warning(f"获取文件智能diff失败: {e}")
            return change.get('diff', '')
    
    def _get_best_diff_from_gitlab(self, mr, file_path: str) -> Optional[str]:
        """使用最优方法生成完整diff"""
        try:
            import requests
            import base64
            
            session = requests.Session()
            session.headers.update({
                'PRIVATE-TOKEN': self.config.token,
                'Content-Type': 'application/json'
            })
            
            source_branch = mr.source_branch
            target_branch = mr.target_branch
            
            # 获取两个分支的文件内容
            target_file_url = f"{self.config.url}/api/v4/projects/{mr.project_id}/repository/files/{file_path.replace('/', '%2F')}"
            target_response = session.get(target_file_url, params={'ref': target_branch}, timeout=30)
            source_response = session.get(target_file_url, params={'ref': source_branch}, timeout=30)
            
            if target_response.status_code == 200 and source_response.status_code == 200:
                target_data = target_response.json()
                source_data = source_response.json()
                
                # 解码文件内容
                target_content = base64.b64decode(target_data['content']).decode('utf-8')
                source_content = base64.b64decode(source_data['content']).decode('utf-8')
                
                # 检查内容是否相同
                if target_content == source_content:
                    return None
                
                # 生成完整的diff (50行上下文)
                full_diff = self._generate_full_context_diff(target_content, source_content, file_path, 50)
                return full_diff
            
            return None
            
        except Exception as e:
            self.logger.debug(f"获取完整diff失败: {e}")
            return None
    
    def _detect_file_type_for_context(self, file_path: str) -> str:
        """检测文件类型用于上下文计算"""
        if not file_path:
            return 'other'
        
        file_path_lower = file_path.lower()
        
        if file_path_lower.endswith('.java'):
            return 'java'
        elif file_path_lower.endswith('.sql'):
            return 'sql'
        elif file_path_lower.endswith('.vue'):
            return 'vue'
        elif file_path_lower.endswith('.xml') and ('mapper' in file_path_lower or 'sql' in file_path_lower):
            return 'sql'  # SQL映射文件当作SQL处理
        else:
            return 'other'
    
    def _count_modified_lines(self, diff_content: str) -> int:
        """统计diff中的修改行数"""
        if not diff_content:
            return 0
        
        modified_count = 0
        lines = diff_content.split('\n')
        
        for line in lines:
            # 统计新增和删除的行（不包括上下文行）
            if line.startswith('+') and not line.startswith('+++'):
                modified_count += 1
            elif line.startswith('-') and not line.startswith('---'):
                modified_count += 1
        
        return modified_count
    
    def _calculate_smart_context_lines(self, modified_lines: int, file_type: str) -> int:
        """计算智能上下文行数"""
        # 基于修改行数的基础策略
        if modified_lines <= 3:
            # 微小改动需要更多上下文
            base_context = 15
        elif modified_lines <= 10:
            # 中等改动
            base_context = 12
        else:
            # 大改动
            base_context = 8
        
        # 基于文件类型的调整
        file_type_adjustments = {
            'sql': 5,   # SQL文件需要更多上下文
            'java': 2,  # Java方法边界
            'vue': 3,   # Vue组件结构
            'xml': 4,   # XML结构完整性
            'other': 0  # 其他文件不调整
        }
        
        adjustment = file_type_adjustments.get(file_type, 0)
        final_context = base_context + adjustment
        
        # 确保最小值
        min_context_by_type = {
            'sql': 20,    # SQL最少20行
            'java': 10,   # Java最少10行
            'vue': 10,    # Vue最少10行
            'xml': 8,     # XML最少8行
            'other': 5    # 其他最少5行
        }
        
        min_required = min_context_by_type.get(file_type, 5)
        return max(final_context, min_required)
    
    
    
    
    def _generate_full_context_diff(self, target_content: str, source_content: str, file_path: str, context_lines: int) -> Optional[str]:
        """自生成带完整上下文的diff"""
        try:
            import difflib
            
            target_lines = target_content.splitlines(keepends=True)
            source_lines = source_content.splitlines(keepends=True)
            
            # 使用unified_diff生成标准diff格式，指定上下文行数
            diff_lines = list(difflib.unified_diff(
                target_lines,
                source_lines, 
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                n=context_lines  # 关键：指定上下文行数
            ))
            
            if diff_lines:
                diff_content = ''.join(diff_lines)
                self.logger.info(f"✅ 自生成diff成功: {file_path} {len(diff_content)}字符 ({context_lines}行上下文)")
                return diff_content
            else:
                self.logger.warning(f"⚠️  两个版本内容相同: {file_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"生成diff失败: {e}")
            return None
    
    def get_users(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取用户列表
        
        Args:
            search: 搜索关键词
            
        Returns:
            用户列表
        """
        try:
            params = {'per_page': 100}
            if search:
                params['search'] = search
            
            users = self.gitlab.users.list(all=True, **params)
            return [
                {
                    'id': user.id,
                    'name': user.name,
                    'username': user.username,
                    'email': getattr(user, 'email', ''),
                    'state': user.state,
                    'avatar_url': getattr(user, 'avatar_url', ''),
                    'created_at': user.created_at
                }
                for user in users
            ]
        except Exception as e:
            self.logger.error(f"获取用户列表失败: {e}")
            return []
    
    def search_projects(self, search: str) -> List[Dict[str, Any]]:
        """
        搜索项目
        
        Args:
            search: 搜索关键词
            
        Returns:
            项目列表
        """
        try:
            projects = self.gitlab.projects.list(search=search, per_page=50)
            return [
                {
                    'id': project.id,
                    'name': project.name,
                    'description': project.description,
                    'web_url': project.web_url,
                    'path_with_namespace': project.path_with_namespace,
                    'visibility': project.visibility,
                    'created_at': project.created_at,
                    'last_activity_at': project.last_activity_at
                }
                for project in projects
            ]
        except Exception as e:
            self.logger.error(f"搜索项目失败: {e}")
            return []
    
    def get_project_files(self, project_id: Optional[str] = None, 
                          path: str = '', ref: Optional[str] = None) -> List[str]:
        """
        获取项目文件列表
        
        Args:
            project_id: 项目ID，默认使用配置中的项目ID
            path: 路径前缀，默认获取所有文件
            ref: 分支或标签，默认使用默认分支
            
        Returns:
            文件路径列表
        """
        try:
            pid = project_id or self.config.project_id
            if not pid:
                raise ValueError("未指定项目ID")
            
            project = self.gitlab.projects.get(pid)
            
            # 获取仓库文件树
            items = project.repository_tree(path=path, ref=ref, recursive=True, all=True)
            
            # 提取文件路径
            files = []
            for item in items:
                if item['type'] == 'blob':  # 文件
                    files.append(item['path'])
            
            self.logger.info(f"获取项目 {pid} 文件列表成功，共 {len(files)} 个文件")
            return files
            
        except Exception as e:
            self.logger.error(f"获取项目文件列表失败: {e}")
            return []
    
    def get_file_content(self, project_id: Optional[str] = None, 
                        file_path: str = '', ref: Optional[str] = None) -> Optional[str]:
        """
        获取文件内容
        
        Args:
            project_id: 项目ID，默认使用配置中的项目ID
            file_path: 文件路径
            ref: 分支或标签，默认使用默认分支
            
        Returns:
            文件内容，失败返回None
        """
        try:
            pid = project_id or self.config.project_id
            if not pid:
                raise ValueError("未指定项目ID")
            
            project = self.gitlab.projects.get(pid)
            
            # 获取文件
            file = project.files.get(file_path=file_path, ref=ref)
            
            # 解码内容
            content = file.decode()
            
            self.logger.info(f"获取文件内容成功: {file_path}")
            return content
            
        except Exception as e:
            self.logger.error(f"获取文件内容失败 {file_path}: {e}")
            return None

    def create_merge_request(self,
                            project_id: Optional[str] = None,
                            source_branch: str = '',
                            target_branch: str = 'main',
                            title: str = '',
                            description: Optional[str] = None,
                            assignee_id: Optional[int] = None,
                            reviewer_ids: Optional[List[int]] = None,
                            labels: Optional[List[str]] = None,
                            draft: bool = False,
                            remove_source_branch: bool = False,
                            squash: bool = False) -> Dict[str, Any]:
        """
        创建新的合并请求

        Args:
            project_id: 项目ID，默认使用配置中的项目ID
            source_branch: 源分支名称
            target_branch: 目标分支名称，默认为'main'
            title: 合并请求标题
            description: 合并请求描述（可选）
            assignee_id: 指派给的用户ID（可选）
            reviewer_ids: 审查者用户ID列表（可选）
            labels: 标签列表（可选）
            draft: 是否为草稿状态（可选）
            remove_source_branch: 合并后是否删除源分支（可选）
            squash: 是否压缩提交（可选）

        Returns:
            创建成功时返回MR信息字典，失败时返回空字典

        Raises:
            ValueError: 参数验证失败
        """
        try:
            # 参数验证
            pid = project_id or self.config.project_id
            if not pid:
                raise ValueError("未指定项目ID")

            if not source_branch:
                raise ValueError("源分支名称不能为空")

            if not target_branch:
                raise ValueError("目标分支名称不能为空")

            if not title:
                raise ValueError("合并请求标题不能为空")

            self.logger.info(f"创建合并请求: {source_branch} -> {target_branch}, 标题: {title[:50]}...")

            # 获取项目
            project = self.gitlab.projects.get(pid)

            # 构建创建参数
            data = {
                'source_branch': source_branch,
                'target_branch': target_branch,
                'title': title
            }

            # 可选参数
            if description:
                data['description'] = description

            if assignee_id:
                data['assignee_id'] = assignee_id

            if reviewer_ids:
                data['reviewer_ids'] = reviewer_ids

            if labels:
                data['labels'] = labels

            if draft:
                data['draft'] = draft

            if remove_source_branch:
                data['remove_source_branch'] = remove_source_branch

            if squash:
                data['squash'] = squash

            # 创建MR
            mr = project.mergerequests.create(data)

            # 格式化返回结果
            result = {
                'iid': mr.iid,
                'id': mr.id,
                'title': mr.title,
                'description': mr.description,
                'state': mr.state,
                'source_branch': mr.source_branch,
                'target_branch': mr.target_branch,
                'web_url': mr.web_url,
                'created_at': mr.created_at,
                'author': {
                    'id': mr.author.get('id'),
                    'name': mr.author.get('name'),
                    'username': mr.author.get('username')
                },
                'draft': getattr(mr, 'draft', False),
                'work_in_progress': getattr(mr, 'work_in_progress', False),
                'merge_status': getattr(mr, 'merge_status', 'unknown')
            }

            self.logger.info(f"创建合并请求成功: !{mr.iid} ({mr.title})")
            return result

        except Exception as e:
            self.logger.error(f"创建合并请求失败: {e}")
            return {}

    def approve_and_merge_merge_request(self,
                                       project_id: Optional[str] = None,
                                       merge_request_iid: int = 0,
                                       merge_commit_message: Optional[str] = None,
                                       sha: Optional[str] = None,
                                       merge_when_pipeline_succeeds: bool = False,
                                       wait_for_pipeline: bool = False) -> Dict[str, Any]:
        """
        审批并合并合并请求

        Args:
            project_id: 项目ID，默认使用配置中的项目ID
            merge_request_iid: 合并请求IID
            merge_commit_message: 合并提交消息（可选）
            sha: 合并的特定提交SHA（可选）
            merge_when_pipeline_succeeds: 当流水线成功后自动合并（可选）
            wait_for_pipeline: 等待流水线完成（可选）

        Returns:
            合并成功时返回结果字典，失败时返回空字典

        Raises:
            ValueError: 参数验证失败
        """
        try:
            # 参数验证
            pid = project_id or self.config.project_id
            if not pid:
                raise ValueError("未指定项目ID")

            if not merge_request_iid:
                raise ValueError("合并请求IID不能为空")

            self.logger.info(f"准备审批并合并 MR: !{merge_request_iid}")

            # 获取项目和MR
            project = self.gitlab.projects.get(pid)
            mr = project.mergerequests.get(merge_request_iid)

            # 检查MR状态
            if mr.state != 'opened':
                self.logger.warning(f"MR状态为 {mr.state}，无法合并")
                return {
                    'success': False,
                    'error': f'MR状态为 {mr.state}，无法合并',
                    'mr_state': mr.state
                }

            # 检查是否需要审批
            # GitLab中，某些用户可能需要先审批才能合并
            # 但这不是必须的，取决于项目设置
            try:
                # 获取当前用户信息
                current_user = self.gitlab.auth()
                user_id = current_user.get('id') if current_user else None

                if user_id:
                    # 尝试审批（如果需要）
                    try:
                        # 检查是否已经审批过
                        approvals = project.mergerequests.get(merge_request_iid, lazy=True).approvals()

                        # 如果需要审批且用户尚未审批
                        if hasattr(approvals, 'user_has_approved') and not approvals.user_has_approved:
                            self.logger.info(f"用户 {user_id} 审批 MR !{merge_request_iid}")
                            project.mergerequests.approve(merge_request_iid)
                            self.logger.info(f"审批成功")
                    except Exception as approval_error:
                        self.logger.warning(f"审批步骤跳过或失败: {approval_error}")
                        # 审批失败不阻断合并流程，继续尝试合并
            except Exception as e:
                self.logger.warning(f"检查审批状态失败: {e}")

            # 合并参数
            merge_data = {}

            if merge_commit_message:
                merge_data['merge_commit_message'] = merge_commit_message

            if sha:
                merge_data['sha'] = sha

            if merge_when_pipeline_succeeds:
                merge_data['merge_when_pipeline_succeeds'] = True

            if wait_for_pipeline:
                merge_data['wait_for_pipeline'] = True

            # 执行合并
            self.logger.info(f"合并 MR !{merge_request_iid} 到 {mr.target_branch}")
            self.logger.debug(f"合并参数: {merge_data}")

            # 等待MR状态变为可合并
            max_wait_time = 30  # 最多等待30秒
            wait_interval = 2  # 每2秒检查一次
            waited_time = 0

            while mr.merge_status not in ['can_be_merged', 'cannot_be_merged'] and waited_time < max_wait_time:
                self.logger.info(f"MR状态为 {mr.merge_status}，等待 {wait_interval} 秒后重新检查...")
                time.sleep(wait_interval)
                waited_time += wait_interval

                # 刷新MR状态 - 重新获取MR对象
                try:
                    mr = project.mergerequests.get(merge_request_iid)
                    self.logger.debug(f"更新后MR状态: {mr.merge_status}")
                except Exception as refresh_error:
                    self.logger.warning(f"刷新MR状态失败: {refresh_error}")

            # 最后检查一次MR状态
            self.logger.debug(f"合并前MR状态: {mr.merge_status}, 冲突: {mr.has_conflicts}")

            if mr.merge_status != 'can_be_merged':
                self.logger.error(f"MR状态不允许合并: {mr.merge_status} (等待了 {waited_time} 秒)")
                return {
                    'success': False,
                    'error': f'MR状态不允许合并: {mr.merge_status} (等待了 {waited_time} 秒)',
                    'mr_state': mr.merge_status,
                    'waited_time': waited_time
                }

            # 尝试合并
            try:
                result = mr.merge(**merge_data)
                self.logger.info(f"合并调用成功")
            except Exception as merge_error:
                self.logger.error(f"合并调用失败: {merge_error}")

                # 尝试获取更详细的错误信息
                try:
                    error_details = mr.merge_request_error()
                    self.logger.error(f"详细错误信息: {error_details}")
                    return {
                        'success': False,
                        'error': f'{merge_error} - 详细错误: {error_details}'
                    }
                except Exception as error_check_error:
                    self.logger.error(f"无法获取详细错误: {error_check_error}")
                    return {
                        'success': False,
                        'error': str(merge_error)
                    }

            # 格式化返回结果
            # 刷新MR状态获取最新信息
            try:
                mr = project.mergerequests.get(merge_request_iid)
            except Exception as final_refresh_error:
                self.logger.warning(f"最终刷新MR状态失败: {final_refresh_error}")

            return_data = {
                'success': True,
                'iid': mr.iid,
                'id': mr.id,
                'title': mr.title,
                'merged_at': mr.merged_at if hasattr(mr, 'merged_at') else None,
                'state': mr.state,
                'web_url': mr.web_url if hasattr(mr, 'web_url') else None,
                'message': '合并成功'
            }

            # 如果result有额外信息，也包含进去
            if isinstance(result, dict):
                return_data.update(result)
            elif hasattr(result, 'merged_at'):
                return_data['merged_at'] = result.merged_at
                return_data['merge_sha'] = getattr(result, 'sha', None)

            self.logger.info(f"合并成功: !{mr.iid} -> {mr.target_branch}")
            return return_data

        except Exception as e:
            self.logger.error(f"审批并合并失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

if __name__ == "__main__":
    # 测试GitLab客户端
    import argparse
    
    parser = argparse.ArgumentParser(description="GitLab客户端测试")
    parser.add_argument('--test', choices=['connection', 'projects', 'users', 'merge-requests', 'create-mr', 'merge-mr'],
                       default='connection', help='测试类型')
    parser.add_argument('--project-id', help='项目ID')
    parser.add_argument('--search', help='搜索关键词')
    parser.add_argument('--source-branch', help='源分支名称')
    parser.add_argument('--target-branch', help='目标分支名称')
    parser.add_argument('--title', help='合并请求标题')
    parser.add_argument('--description', help='合并请求描述')
    parser.add_argument('--iid', type=int, help='合并请求IID')
    args = parser.parse_args()
    
    client = GitLabClient()
    
    if args.test == 'connection':
        print("测试GitLab连接...")
        if client.test_connection():
            print("✅ GitLab连接正常")
        else:
            print("❌ GitLab连接失败")
    
    elif args.test == 'projects':
        print("获取项目列表...")
        if args.search:
            projects = client.search_projects(args.search)
        else:
            # 获取可访问的项目
            try:
                projects = client.gitlab.projects.list(membership=True, per_page=10)
                projects = [
                    {
                        'id': p.id,
                        'name': p.name,
                        'path_with_namespace': p.path_with_namespace
                    }
                    for p in projects
                ]
            except Exception as e:
                print(f"获取项目列表失败: {e}")
                projects = []
        
        if projects:
            print(f"找到 {len(projects)} 个项目:")
            for project in projects[:10]:  # 只显示前10个
                print(f"  - [{project['id']}] {project.get('name', 'Unknown')} ({project.get('path_with_namespace', 'Unknown')})")
        else:
            print("未找到项目")
    
    elif args.test == 'users':
        print("获取用户列表...")
        users = client.get_users(search=args.search)
        if users:
            print(f"找到 {len(users)} 个用户:")
            for user in users[:10]:  # 只显示前10个
                print(f"  - [{user['id']}] {user['name']} (@{user['username']})")
        else:
            print("未找到用户")
    
    elif args.test == 'merge-requests':
        if not args.project_id:
            print("❌ 需要指定 --project-id 参数")
        else:
            print(f"获取项目 {args.project_id} 的合并请求...")
            mrs = client.get_merge_requests(
                project_id=args.project_id,
                since=datetime.now() - timedelta(days=30)
            )
            if mrs:
                print(f"找到 {len(mrs)} 个合并请求:")
                for mr in mrs[:5]:  # 只显示前5个
                    print(f"  - !{mr['iid']} {mr['title']} ({mr['state']}) by {mr['author']['name']}")
            else:
                print("未找到合并请求")

    elif args.test == 'create-mr':
        if not all([args.project_id, args.source_branch, args.title]):
            print("❌ 创建MR需要 --project-id --source-branch --title 参数")
        else:
            print(f"创建合并请求: {args.source_branch} -> {args.target_branch or 'main'}")
            mr = client.create_merge_request(
                project_id=args.project_id,
                source_branch=args.source_branch,
                target_branch=args.target_branch or 'main',
                title=args.title,
                description=args.description
            )
            if mr:
                print(f"✅ 创建成功: !{mr['iid']}")
                print(f"   标题: {mr['title']}")
                print(f"   链接: {mr['web_url']}")
            else:
                print("❌ 创建失败")

    elif args.test == 'merge-mr':
        if not all([args.project_id, args.iid]):
            print("❌ 合并MR需要 --project-id --iid 参数")
        else:
            print(f"审批并合并 MR: !{args.iid}")
            result = client.approve_and_merge_merge_request(
                project_id=args.project_id,
                merge_request_iid=args.iid
            )
            if result.get('success'):
                print(f"✅ 合并成功: !{result['iid']}")
                print(f"   标题: {result['title']}")
                print(f"   合并时间: {result.get('merged_at', 'Unknown')}")
                print(f"   链接: {result['web_url']}")
            else:
                print(f"❌ 合并失败: {result.get('error')}")