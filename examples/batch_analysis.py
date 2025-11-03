#!/usr/bin/env python3
"""
基于配置文件的批量GitLab项目分析
支持从JSON配置文件读取多个项目配置并批量分析
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def load_projects_config(config_file: str) -> dict:
    """加载项目配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件不存在: {config_file}")
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式错误: {e}")

def calculate_date_range(period_days: int) -> tuple:
    """计算分析日期范围"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=period_days - 1)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def run_project_analysis(project_config: dict, default_settings: dict, 
                        start_date: str, end_date: str, output_dir: str) -> bool:
    """运行单个项目的分析"""
    
    project_name = project_config['name']
    project_id = project_config['project_id']
    gitlab_config = project_config.get('gitlab_config', {})
    
    print(f"🔄 分析项目: {project_name} (ID: {project_id})")
    
    # 构建命令
    cmd = [
        'python3',
        f'{project_root}/data_analysis/gitlab_merge_analyzer.py',
        '--project-id', str(project_id),
        '--start-date', start_date,
        '--end-date', end_date,
        '--output-format', default_settings.get('output_format', 'html')
    ]
    
    # AI分析
    if default_settings.get('use_ai', True):
        cmd.append('--use-ai')
    
    # GitLab配置
    if 'url' in gitlab_config:
        cmd.extend(['--gitlab-url', gitlab_config['url']])
    if 'token' in gitlab_config:
        cmd.extend(['--gitlab-token', gitlab_config['token']])
    if 'timeout' in gitlab_config:
        cmd.extend(['--gitlab-timeout', str(gitlab_config['timeout'])])
    if 'verify_ssl' in gitlab_config:
        cmd.extend(['--gitlab-verify-ssl', str(gitlab_config['verify_ssl']).lower()])
    
    # 目标分支
    branches = project_config.get('default_branches', default_settings.get('include_branches', []))
    if branches:
        cmd.extend(['--target-branches'] + branches)
    
    # 输出文件
    safe_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    output_file = f"{output_dir}/{safe_name}_{start_date}_to_{end_date}.html"
    cmd.extend(['--output-file', output_file])
    
    # 邮件设置
    recipients = []
    if project_config.get('team_email'):
        recipients.append(project_config['team_email'])
    if project_config.get('manager_email'):
        recipients.append(project_config['manager_email'])
    
    if recipients:
        cmd.extend(['--send-email', '--email-recipients'] + recipients)
        
        # 自定义邮件主题
        subject_template = default_settings.get('email_subject_template', 
                                               '{project_name} 合并记录分析报告 - {start_date} 至 {end_date}')
        subject = subject_template.format(
            project_name=project_name,
            start_date=start_date,
            end_date=end_date
        )
        cmd.extend(['--email-subject', subject])
    
    try:
        # 执行分析
        print(f"   执行命令: {' '.join(cmd[:10])}...")  # 只显示前10个参数
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)  # 15分钟超时
        
        if result.returncode == 0:
            print(f"   ✅ 分析完成，报告保存至: {output_file}")
            if recipients:
                print(f"   📧 邮件已发送至: {', '.join(recipients)}")
            return True
        else:
            print(f"   ❌ 分析失败:")
            print(f"   错误信息: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ⏰ 分析超时（超过15分钟）")
        return False
    except Exception as e:
        print(f"   ❌ 执行异常: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="批量GitLab项目分析")
    parser.add_argument('--config', '-c', 
                       default='examples/projects_config.json',
                       help='项目配置文件路径')
    parser.add_argument('--projects', '-p', nargs='+',
                       help='指定要分析的项目名称（默认分析所有项目）')
    parser.add_argument('--days', '-d', type=int,
                       help='分析天数（覆盖配置文件设置）')
    parser.add_argument('--start-date', help='开始日期 YYYY-MM-DD')
    parser.add_argument('--end-date', help='结束日期 YYYY-MM-DD')
    parser.add_argument('--output-dir', '-o', 
                       default='reports',
                       help='报告输出目录')
    parser.add_argument('--no-email', action='store_true',
                       help='不发送邮件报告')
    parser.add_argument('--dry-run', action='store_true',
                       help='试运行，只显示将要执行的命令')
    
    args = parser.parse_args()
    
    print("🚀 GitLab项目批量分析工具")
    print("=" * 60)
    
    # 加载配置
    try:
        config = load_projects_config(args.config)
        print(f"✅ 配置文件加载成功: {args.config}")
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        return 1
    
    projects = config.get('projects', [])
    default_settings = config.get('default_settings', {})
    
    # 过滤项目
    if args.projects:
        projects = [p for p in projects if p['name'] in args.projects]
        print(f"🎯 指定分析项目: {', '.join(args.projects)}")
    
    if not projects:
        print("❌ 没有找到要分析的项目")
        return 1
    
    print(f"📊 将分析 {len(projects)} 个项目")
    
    # 确定日期范围
    if args.start_date and args.end_date:
        start_date, end_date = args.start_date, args.end_date
        print(f"📅 指定时间范围: {start_date} 至 {end_date}")
    else:
        days = args.days or default_settings.get('analysis_period_days', 30)
        start_date, end_date = calculate_date_range(days)
        print(f"📅 自动计算时间范围: {start_date} 至 {end_date} ({days} 天)")
    
    # 创建输出目录
    output_dir = args.output_dir
    Path(output_dir).mkdir(exist_ok=True)
    print(f"📂 输出目录: {os.path.abspath(output_dir)}")
    
    if args.dry_run:
        print("\n🔍 试运行模式 - 将要执行的分析:")
        print("-" * 60)
        for project in projects:
            print(f"   项目: {project['name']} (ID: {project['project_id']})")
            print(f"   GitLab: {project.get('gitlab_config', {}).get('url', '默认')}")
            print(f"   分支: {project.get('default_branches', ['默认'])}")
            print(f"   邮件: {project.get('team_email', '无')}")
            print()
        return 0
    
    # 执行分析
    print(f"\n🔄 开始批量分析...")
    print("-" * 60)
    
    results = []
    for i, project in enumerate(projects, 1):
        print(f"\n[{i}/{len(projects)}] ", end="")
        
        success = run_project_analysis(
            project, default_settings, start_date, end_date, output_dir
        )
        results.append((project['name'], success))
        
        print()  # 空行分隔
    
    # 汇总结果
    print("📊 批量分析完成")
    print("=" * 60)
    
    success_count = 0
    for project_name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"   {project_name}: {status}")
        if success:
            success_count += 1
    
    print(f"\n总计: {success_count}/{len(results)} 个项目分析成功")
    
    if success_count == len(results):
        print("🎉 所有项目分析完成！")
        return 0
    else:
        print("⚠️ 部分项目分析失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())