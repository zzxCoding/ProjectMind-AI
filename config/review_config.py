#!/usr/bin/env python3
"""
GitLab MR 自动审查配置文件
支持多项目配置
"""

import os
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class ReviewConfig:
    """审查配置"""
    
    # 基础配置
    enable: bool = True
    auto_trigger: bool = True  # 自动触发审查
    concurrent_reviews: int = 3  # 并发审查数量
    
        
    # AI 审查配置
    ai_review_enabled: bool = True
    ai_model: str = "codellama"
    ai_temperature: float = 0.3
    ai_max_tokens: int = 2000
    ai_prompt_template: str = "default"
    
    # 审查规则配置
    severity_threshold: str = "ERROR"  # 阻止合并的阈值
    max_issues_per_file: int = 10
    max_total_issues: int = 50
    
    # GitLab 交互配置
    auto_comment: bool = True
    auto_label: bool = True
    auto_block: bool = False  # 默认不阻断合并请求
    comment_template: str = "detailed"
    max_comment_length: int = 500000
    
    # 通知配置
    notify_on_success: bool = False
    notify_on_warning: bool = True
    notify_on_failure: bool = True
    notification_channels: List[str] = field(default_factory=lambda: ["gitlab"])
    
    # 团队规则配置
    team_rules_path: Optional[str] = None
    custom_rules: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_env(cls) -> 'ReviewConfig':
        """从环境变量创建配置"""
        return cls(
            enable=os.getenv('MR_REVIEW_ENABLE', 'true').lower() == 'true',
            auto_trigger=os.getenv('MR_REVIEW_AUTO_TRIGGER', 'true').lower() == 'true',
            concurrent_reviews=int(os.getenv('MR_REVIEW_CONCURRENT', '3')),
            
              
            ai_review_enabled=os.getenv('AI_REVIEW_ENABLED', 'true').lower() == 'true',
            ai_model=os.getenv('AI_MODEL', 'codellama'),
            ai_temperature=float(os.getenv('AI_TEMPERATURE', '0.3')),
            ai_max_tokens=int(os.getenv('AI_MAX_TOKENS', '2000')),
            
            severity_threshold=os.getenv('SEVERITY_THRESHOLD', 'ERROR'),
            max_issues_per_file=int(os.getenv('MAX_ISSUES_PER_FILE', '10')),
            max_total_issues=int(os.getenv('MAX_TOTAL_ISSUES', '50')),
            
            auto_comment=os.getenv('AUTO_COMMENT', 'true').lower() == 'true',
            auto_label=os.getenv('AUTO_LABEL', 'true').lower() == 'true',
            auto_block=os.getenv('AUTO_BLOCK', 'false').lower() == 'true',  # 默认不阻断合并请求
            
            notify_on_success=os.getenv('NOTIFY_ON_SUCCESS', 'false').lower() == 'true',
            notify_on_warning=os.getenv('NOTIFY_ON_WARNING', 'true').lower() == 'true',
            notify_on_failure=os.getenv('NOTIFY_ON_FAILURE', 'true').lower() == 'true',
            notification_channels=os.getenv('NOTIFICATION_CHANNELS', 'gitlab').split(','),
            
            team_rules_path=os.getenv('TEAM_RULES_PATH'),
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'ReviewConfig':
        """从配置文件加载"""
        import json
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return cls(**config_data)
            
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise ValueError(f"加载配置失败: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'enable': self.enable,
            'auto_trigger': self.auto_trigger,
            'concurrent_reviews': self.concurrent_reviews,
            
                
            'ai_review_enabled': self.ai_review_enabled,
            'ai_model': self.ai_model,
            'ai_temperature': self.ai_temperature,
            'ai_max_tokens': self.ai_max_tokens,
            
            'severity_threshold': self.severity_threshold,
            'max_issues_per_file': self.max_issues_per_file,
            'max_total_issues': self.max_total_issues,
            
            'auto_comment': self.auto_comment,
            'auto_label': self.auto_label,
            'auto_block': self.auto_block,
            'comment_template': self.comment_template,
            'max_comment_length': self.max_comment_length,
            
            'notify_on_success': self.notify_on_success,
            'notify_on_warning': self.notify_on_warning,
            'notify_on_failure': self.notify_on_failure,
            'notification_channels': self.notification_channels,
            
            'team_rules_path': self.team_rules_path,
            'custom_rules': self.custom_rules,
        }
    
    def _should_notify(self, status: str) -> bool:
        """判断是否应该发送通知"""
        if status == 'PASSED':
            return self.notify_on_success
        elif status == 'WARNING':
            return self.notify_on_warning
        elif status == 'FAILED':
            return self.notify_on_failure
        return False
    
    def save_to_file(self, config_path: str):
        """保存配置到文件"""
        import json
        
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            raise ValueError(f"保存配置失败: {e}")

# 预定义的配置模板
CONFIG_TEMPLATES = {
    'strict': {
        'severity_threshold': 'WARNING',
        'max_issues_per_file': 5,
        'max_total_issues': 20,
        'auto_block': True,
        'sonarqube_severities': ['CRITICAL', 'BLOCKER', 'MAJOR', 'MINOR'],
        'ai_temperature': 0.1,
    },
    'balanced': {
        'severity_threshold': 'ERROR',
        'max_issues_per_file': 10,
        'max_total_issues': 50,
        'auto_block': False,  # 默认不阻断合并请求
            'ai_temperature': 0.3,
    },
    'lenient': {
        'severity_threshold': 'CRITICAL',
        'max_issues_per_file': 20,
        'max_total_issues': 100,
        'auto_block': False,
          'ai_temperature': 0.5,
    }
}

def get_default_config() -> ReviewConfig:
    """获取默认配置"""
    return ReviewConfig.from_env()

def create_config_template(template_name: str = 'balanced') -> ReviewConfig:
    """创建配置模板"""
    if template_name not in CONFIG_TEMPLATES:
        raise ValueError(f"未知的配置模板: {template_name}")
    
    template_data = CONFIG_TEMPLATES[template_name]
    config = ReviewConfig.from_env()
    
    # 应用模板设置
    for key, value in template_data.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config


@dataclass
class AIConfig:
    """AI审查配置"""
    enabled: bool = True
    model: str = "codellama"
    temperature: float = 0.3
    max_tokens: int = 2000
    prompt_template: str = "default"
    focus_areas: List[str] = field(default_factory=lambda: ["security", "performance", "code_quality"])

@dataclass
class ReviewRules:
    """审查规则"""
    severity_threshold: str = "ERROR"
    max_issues_per_file: int = 10
    max_total_issues: int = 50
    auto_block: bool = False
    require_approval: bool = False

@dataclass
class GitLabConfig:
    """GitLab交互配置"""
    auto_comment: bool = True
    auto_label: bool = True
    auto_block: bool = False
    comment_template: str = "detailed"
    max_comment_length: int = 500000
    labels: Dict[str, str] = field(default_factory=lambda: {
        "review_passed": "review-approved",
        "review_failed": "review-needs-attention",
        "review_warning": "review-warning"
    })
    assign_reviewers: List[str] = field(default_factory=list)

@dataclass
class NotificationConfig:
    """通知配置"""
    enabled: bool = True
    channels: List[str] = field(default_factory=lambda: ["gitlab"])
    notify_on_success: bool = False
    notify_on_warning: bool = True
    notify_on_failure: bool = True
    slack_webhook: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)
    
    def _should_notify(self, status: str) -> bool:
        """判断是否应该发送通知"""
        if status == 'PASSED':
            return self.notify_on_success
        elif status == 'WARNING':
            return self.notify_on_warning
        elif status == 'FAILED':
            return self.notify_on_failure
        return False

@dataclass
class ProjectConfig:
    """项目配置"""
    gitlab_project_id: int
    enable: bool = True
    auto_trigger: bool = True
    
    ai_config: AIConfig = field(default_factory=AIConfig)
    review_rules: ReviewRules = field(default_factory=ReviewRules)
    gitlab_config: GitLabConfig = field(default_factory=GitLabConfig)
    notification_config: NotificationConfig = field(default_factory=NotificationConfig)
    
    custom_rules: Dict[str, Any] = field(default_factory=dict)
    team_rules_path: Optional[str] = None

@dataclass
class GlobalConfig:
    """全局配置"""
    enable: bool = True
    auto_trigger: bool = True
    concurrent_reviews: int = 3
    default_ai_model: str = "codellama"
    default_ai_temperature: float = 0.3
    default_ai_max_tokens: int = 2000
    default_comment_template: str = "detailed"
    max_comment_length: int = 500000
    notify_on_success: bool = False
    notify_on_warning: bool = True
    notify_on_failure: bool = True
    default_notification_channels: List[str] = field(default_factory=lambda: ["gitlab"])

@dataclass
class MultiProjectConfig:
    """多项目配置"""
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    projects: Dict[str, ProjectConfig] = field(default_factory=dict)
    global_custom_rules: Dict[str, Any] = field(default_factory=dict)
    
    def get_project_config(self, project_name: str) -> Optional[ProjectConfig]:
        """获取项目配置"""
        return self.projects.get(project_name)
    
    def get_project_config_by_id(self, project_id: int) -> Optional[ProjectConfig]:
        """通过项目ID获取项目配置"""
        for project_config in self.projects.values():
            if project_config.gitlab_project_id == project_id:
                return project_config
        return None
    
    def get_enabled_projects(self) -> Dict[str, ProjectConfig]:
        """获取启用的项目"""
        return {name: config for name, config in self.projects.items() if config.enable}
    
    def filter_projects(self, pattern: str = None, exclude: List[str] = None) -> Dict[str, ProjectConfig]:
        """过滤项目"""
        filtered = self.get_enabled_projects()
        
        if pattern:
            regex = re.compile(pattern)
            filtered = {name: config for name, config in filtered.items() if regex.match(name)}
        
        if exclude:
            filtered = {name: config for name, config in filtered.items() if name not in exclude}
        
        return filtered
    
    @classmethod
    def from_file(cls, config_path: str) -> 'MultiProjectConfig':
        """从配置文件加载"""
        import json
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 创建全局配置
            global_config_data = config_data.get('global_config', {})
            global_config = GlobalConfig(**global_config_data)
            
            # 创建项目配置
            projects_data = config_data.get('projects', {})
            projects = {}
            
            for project_name, project_data in projects_data.items():
                # 解析嵌套的配置对象
                ai_config = AIConfig(**project_data.get('ai_config', {}))
                review_rules = ReviewRules(**project_data.get('review_rules', {}))
                gitlab_config = GitLabConfig(**project_data.get('gitlab_config', {}))
                notification_config = NotificationConfig(**project_data.get('notification_config', {}))
                
                project_config = ProjectConfig(
                    gitlab_project_id=project_data['gitlab_project_id'],
                    enable=project_data.get('enable', True),
                    auto_trigger=project_data.get('auto_trigger', True),
                    ai_config=ai_config,
                    review_rules=review_rules,
                    gitlab_config=gitlab_config,
                    notification_config=notification_config,
                    custom_rules=project_data.get('custom_rules', {}),
                    team_rules_path=project_data.get('team_rules_path')
                )
                
                projects[project_name] = project_config
            
            return cls(
                global_config=global_config,
                projects=projects,
                global_custom_rules=config_data.get('global_custom_rules', {})
            )
            
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise ValueError(f"加载配置失败: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'global_config': self.global_config.__dict__,
            'projects': {name: {
                'gitlab_project_id': config.gitlab_project_id,
                'enable': config.enable,
                'auto_trigger': config.auto_trigger,
                  'ai_config': config.ai_config.__dict__,
                'review_rules': config.review_rules.__dict__,
                'gitlab_config': config.gitlab_config.__dict__,
                'notification_config': config.notification_config.__dict__,
                'custom_rules': config.custom_rules,
                'team_rules_path': config.team_rules_path
            } for name, config in self.projects.items()},
            'global_custom_rules': self.global_custom_rules
        }

def load_multi_project_config(config_path: str) -> MultiProjectConfig:
    """加载多项目配置"""
    return MultiProjectConfig.from_file(config_path)

if __name__ == "__main__":
    # 测试配置
    try:
        # 测试多项目配置
        config = load_multi_project_config("examples/review_config_example.json")
        print("✅ 多项目配置加载成功")
        print(f"   全局启用状态: {config.global_config.enable}")
        print(f"   项目数量: {len(config.projects)}")
        print(f"   启用的项目: {list(config.get_enabled_projects().keys())}")
        
        # 测试单个项目配置
        if 'web-app' in config.projects:
            web_app_config = config.projects['web-app']
            print(f"   Web应用项目ID: {web_app_config.gitlab_project_id}")
            print(f"   Web应用AI模型: {web_app_config.ai_config.model}")
            print(f"   Web应用AI模型: {web_app_config.ai_config.model}")
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        # 回退到旧版本测试
        try:
            config = get_default_config()
            print("✅ 单项目配置加载成功")
            print(f"   启用状态: {config.enable}")
            print(f"   AI分析: {config.ai_analysis_enabled}")
            print(f"   AI审查: {config.ai_review_enabled}")
        except Exception as e2:
            print(f"❌ 单项目配置也失败: {e2}")