#!/usr/bin/env python3
"""
多项目GitLab分析示例
展示如何分析多个GitLab项目的合并记录
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def run_analysis(project_config: dict, output_dir: str = "reports"):
    """
    运行单个项目的分析
    
    Args:
        project_config: 项目配置字典
        output_dir: 输出目录
    """
    
    # 构建命令参数
    cmd = [
        'python3',
        f'{project_root}/data_analysis/gitlab_merge_analyzer.py',
        '--project-id', str(project_config['project_id']),
        '--start-date', project_config['start_date'],
        '--end-date', project_config['end_date'],
        '--use-ai',
        '--output-format', 'html'
    ]
    
    # 添加GitLab配置
    if 'gitlab_url' in project_config:
        cmd.extend(['--gitlab-url', project_config['gitlab_url']])
    
    if 'gitlab_token' in project_config:
        cmd.extend(['--gitlab-token', project_config['gitlab_token']])
    
    if 'gitlab_timeout' in project_config:
        cmd.extend(['--gitlab-timeout', str(project_config['gitlab_timeout'])])
    
    if 'gitlab_verify_ssl' in project_config:
        cmd.extend(['--gitlab-verify-ssl', str(project_config['gitlab_verify_ssl']).lower()])
    
    # 添加目标分支
    if 'target_branches' in project_config:
        cmd.extend(['--target-branches'] + project_config['target_branches'])
    
    # 输出文件
    project_name = project_config.get('name', f"project_{project_config['project_id']}")
    output_file = f"{output_dir}/{project_name}_{project_config['start_date']}_to_{project_config['end_date']}.html"
    cmd.extend(['--output-file', output_file])
    
    # 邮件发送
    if 'email_recipients' in project_config:
        cmd.extend(['--send-email'])
        cmd.extend(['--email-recipients'] + project_config['email_recipients'])
        
        if 'email_subject' in project_config:
            cmd.extend(['--email-subject', project_config['email_subject']])
    
    print(f"🔄 正在分析项目: {project_name}")
    print(f"   项目ID: {project_config['project_id']}")
    print(f"   时间范围: {project_config['start_date']} 至 {project_config['end_date']}")
    
    try:
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            print(f"   ✅ 分析完成: {output_file}")
            if 'email_recipients' in project_config:
                print(f"   📧 邮件已发送到: {', '.join(project_config['email_recipients'])}")
        else:
            print(f"   ❌ 分析失败:")
            print(f"   错误信息: {result.stderr}")
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"   ⏰ 分析超时")
        return False
    except Exception as e:
        print(f"   ❌ 执行失败: {e}")
        return False

def main():
    """主函数 - 多项目分析示例"""
    
    print("🚀 多项目GitLab合并记录分析")
    print("=" * 50)
    
    # 创建输出目录
    output_dir = "reports"
    os.makedirs(output_dir, exist_ok=True)
    
    # 配置要分析的项目
    # 可以根据实际情况修改这些配置
    projects = [
        {
            'name': 'main_project',
            'project_id': 12345,
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'target_branches': ['main', 'develop'],
            'email_recipients': ['dev-team@company.com'],
            'email_subject': '主项目1月份合并记录分析报告'
            # 使用环境变量中的默认GitLab配置
        },
        {
            'name': 'mobile_app',
            'project_id': 67890,
            'gitlab_url': 'https://gitlab.company.com',  # 私有GitLab实例
            'gitlab_token': 'glpat-xxxxxxxxxxxxxxxxxxxx',  # 项目专用token
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'target_branches': ['main', 'release'],
            'email_recipients': ['mobile-team@company.com', 'pm@company.com'],
            'email_subject': '移动应用1月份合并记录分析报告'
        },
        {
            'name': 'api_service',
            'project_id': 11111,
            'gitlab_url': 'https://gitlab.example.com',
            'gitlab_token': 'glpat-yyyyyyyyyyyyyyyyyyyy',
            'gitlab_verify_ssl': False,  # 如果是自签名证书
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'email_recipients': ['backend-team@company.com']
        }
    ]
    
    # 执行分析
    results = []
    for i, project in enumerate(projects, 1):
        print(f"\n[{i}/{len(projects)}] ", end="")
        success = run_analysis(project, output_dir)
        results.append((project['name'], success))
    
    # 汇总结果
    print(f"\n📊 分析完成汇总:")
    print("=" * 50)
    
    success_count = 0
    for project_name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"   {project_name}: {status}")
        if success:
            success_count += 1
    
    print(f"\n总计: {success_count}/{len(results)} 个项目分析成功")
    print(f"报告文件保存在: {os.path.abspath(output_dir)} 目录")
    
    if success_count == len(results):
        print("🎉 所有项目分析完成！")
    else:
        print("⚠️ 部分项目分析失败，请检查配置和网络连接")

if __name__ == "__main__":
    main()