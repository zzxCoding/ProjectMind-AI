#!/usr/bin/env python3
"""
SonarQube缺陷分析器使用示例
演示如何使用SonarQube分析器进行各种类型的代码质量分析
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from shared.utils import setup_logging
from shared.sonarqube_client import SonarQubeClient, SonarQubeConfig
from data_analysis.sonarqube_defect_analyzer import SonarQubeDefectAnalyzer

def example_basic_analysis():
    """示例1: 基本项目分析"""
    print("=" * 60)
    print("🔍 示例1: 基本项目分析")
    print("=" * 60)
    
    # 从环境变量获取项目标识符
    project_key = os.getenv('SONARQUBE_PROJECT_KEY', 'your-project-key')
    
    if project_key == 'your-project-key':
        print("⚠️ 请设置环境变量 SONARQUBE_PROJECT_KEY")
        return
    
    try:
        # 创建分析器
        analyzer = SonarQubeDefectAnalyzer(project_key)
        
        # 执行基本分析
        print(f"正在分析项目: {project_key}")
        analysis_data = analyzer.analyze_project_defects(
            severities=['CRITICAL', 'BLOCKER'],  # 只关注高严重性问题
            use_ai=False  # 不使用AI分析以提高速度
        )
        
        # 显示结果摘要
        summary = analysis_data['summary']
        print(f"\n📊 分析结果摘要:")
        print(f"   项目名称: {analysis_data['project_info']['name']}")
        print(f"   总问题数: {summary['issue_stats']['total']}")
        print(f"   安全热点: {summary['hotspot_stats']['total']}")
        print(f"   风险等级: {summary['risk_level']}")
        print(f"   质量门状态: {summary['quality_gate_status']}")
        
        # 按类型显示问题分布
        print(f"\n📈 问题类型分布:")
        for issue_type, count in summary['issue_stats']['by_type'].items():
            print(f"   {issue_type}: {count}")
        
        print("✅ 基本分析完成!")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")

def example_ai_enhanced_analysis():
    """示例2: AI增强分析"""
    print("=" * 60)
    print("🤖 示例2: AI增强分析")
    print("=" * 60)
    
    project_key = os.getenv('SONARQUBE_PROJECT_KEY', 'your-project-key')
    
    if project_key == 'your-project-key':
        print("⚠️ 请设置环境变量 SONARQUBE_PROJECT_KEY")
        return
    
    try:
        # 创建分析器，指定AI模型
        analyzer = SonarQubeDefectAnalyzer(
            project_key,
            ai_model='llama3'  # 使用指定的AI模型
        )
        
        # 执行AI增强分析
        print(f"正在执行AI增强分析: {project_key}")
        analysis_data = analyzer.analyze_project_defects(
            severities=['CRITICAL', 'BLOCKER', 'MAJOR'],
            use_ai=True  # 启用AI分析
        )
        
        # 显示AI分析结果
        if analysis_data.get('ai_analysis'):
            print(f"\n🧠 AI分析洞察:")
            print("-" * 40)
            print(analysis_data['ai_analysis'])
            print("-" * 40)
        
        # 生成详细报告
        markdown_report = analyzer.generate_markdown_report(analysis_data)
        
        # 保存报告
        report_filename = f"ai_analysis_report_{project_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        
        print(f"✅ AI增强分析完成! 详细报告保存为: {report_filename}")
        
    except Exception as e:
        print(f"❌ AI增强分析失败: {e}")

def example_custom_filtering():
    """示例3: 自定义过滤分析"""
    print("=" * 60)
    print("🎯 示例3: 自定义过滤分析")
    print("=" * 60)
    
    project_key = os.getenv('SONARQUBE_PROJECT_KEY', 'your-project-key')
    
    if project_key == 'your-project-key':
        print("⚠️ 请设置环境变量 SONARQUBE_PROJECT_KEY")
        return
    
    try:
        analyzer = SonarQubeDefectAnalyzer(project_key)
        
        # 场景1: 只关注安全问题
        print("🔒 场景1: 安全问题专项分析")
        security_analysis = analyzer.analyze_project_defects(
            severities=['CRITICAL', 'BLOCKER', 'MAJOR'],
            issue_types=['VULNERABILITY', 'SECURITY_HOTSPOT'],  # 只关注安全相关问题
            use_ai=True
        )
        
        security_summary = security_analysis['summary']
        print(f"   漏洞数: {security_summary['key_metrics']['vulnerabilities']}")
        print(f"   安全热点: {security_summary['key_metrics']['security_hotspots']}")
        print(f"   安全评级: {security_summary['key_metrics']['security_rating']}")
        
        # 场景2: 只关注代码质量问题
        print("\n📝 场景2: 代码质量专项分析")
        quality_analysis = analyzer.analyze_project_defects(
            severities=['MAJOR', 'MINOR'],
            issue_types=['CODE_SMELL'],  # 只关注代码异味
            use_ai=True
        )
        
        quality_summary = quality_analysis['summary']
        print(f"   代码异味数: {quality_summary['key_metrics']['code_smells']}")
        print(f"   可维护性评级: {quality_summary['key_metrics']['maintainability_rating']}")
        print(f"   重复代码密度: {quality_summary['key_metrics']['duplicated_lines_density']}%")
        
        print("✅ 自定义过滤分析完成!")
        
    except Exception as e:
        print(f"❌ 自定义过滤分析失败: {e}")

def example_multiple_projects():
    """示例4: 多项目对比分析"""
    print("=" * 60)
    print("📊 示例4: 多项目对比分析")
    print("=" * 60)
    
    # 从环境变量或命令行参数获取多个项目
    project_keys = [
        os.getenv('SONARQUBE_PROJECT_1', 'project-1'),
        os.getenv('SONARQUBE_PROJECT_2', 'project-2')
    ]
    
    if any(key.startswith('project-') for key in project_keys):
        print("⚠️ 请设置环境变量 SONARQUBE_PROJECT_1 和 SONARQUBE_PROJECT_2")
        return
    
    project_results = {}
    
    for project_key in project_keys:
        try:
            print(f"\n正在分析项目: {project_key}")
            
            analyzer = SonarQubeDefectAnalyzer(project_key)
            analysis_data = analyzer.analyze_project_defects(
                severities=['CRITICAL', 'BLOCKER', 'MAJOR'],
                use_ai=False  # 为了速度，不使用AI
            )
            
            project_results[project_key] = analysis_data['summary']
            
        except Exception as e:
            print(f"❌ 项目 {project_key} 分析失败: {e}")
            project_results[project_key] = None
    
    # 生成对比报告
    print("\n📈 项目对比结果:")
    print("-" * 80)
    print(f"{'项目':<20} {'总问题':<10} {'风险等级':<10} {'质量门':<10} {'安全评级':<10}")
    print("-" * 80)
    
    for project_key, result in project_results.items():
        if result:
            print(f"{project_key:<20} "
                  f"{result['issue_stats']['total']:<10} "
                  f"{result['risk_level']:<10} "
                  f"{result['quality_gate_status']:<10} "
                  f"{result['key_metrics']['security_rating']:<10}")
        else:
            print(f"{project_key:<20} {'ERROR':<10} {'N/A':<10} {'N/A':<10} {'N/A':<10}")
    
    print("-" * 80)
    print("✅ 多项目对比分析完成!")

def example_report_generation():
    """示例5: 报告生成和邮件发送"""
    print("=" * 60)
    print("📄 示例5: 报告生成和邮件发送")
    print("=" * 60)
    
    project_key = os.getenv('SONARQUBE_PROJECT_KEY', 'your-project-key')
    
    if project_key == 'your-project-key':
        print("⚠️ 请设置环境变量 SONARQUBE_PROJECT_KEY")
        return
    
    try:
        analyzer = SonarQubeDefectAnalyzer(project_key, ai_model='qwen3:32b')
        
        # 执行完整分析
        print("正在执行完整项目分析...")
        analysis_data = analyzer.analyze_project_defects(use_ai=True)
        
        # 生成多种格式报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        project_name_safe = analysis_data['project_info']['name'].replace(' ', '_').replace('/', '_')
        
        # 1. JSON格式
        json_filename = f"sonarqube_analysis_{project_name_safe}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"📄 JSON报告已保存: {json_filename}")
        
        # 2. Markdown格式
        markdown_report = analyzer.generate_markdown_report(analysis_data)
        markdown_filename = f"sonarqube_analysis_{project_name_safe}_{timestamp}.md"
        with open(markdown_filename, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        print(f"📄 Markdown报告已保存: {markdown_filename}")
        
        # 3. HTML格式
        html_report = analyzer.convert_markdown_to_html(markdown_report)
        html_filename = f"sonarqube_analysis_{project_name_safe}_{timestamp}.html"
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(html_report)
        print(f"📄 HTML报告已保存: {html_filename}")
        
        # 4. 邮件发送 (如果配置了邮件)
        email_recipients = os.getenv('EMAIL_RECIPIENTS')
        if email_recipients:
            recipients = [email.strip() for email in email_recipients.split(',')]
            print(f"📧 正在发送邮件报告给: {', '.join(recipients)}")
            
            result = analyzer.send_report_email(
                html_content=html_report,
                recipients=recipients,
                project_name=analysis_data['project_info']['name'],
                markdown_content=markdown_report
            )
            
            if result['success']:
                print("✅ 邮件发送成功!")
            else:
                print(f"❌ 邮件发送失败: {result.get('error')}")
        else:
            print("ℹ️ 未配置邮件收件人，跳过邮件发送")
        
        print("✅ 报告生成和发送完成!")
        
    except Exception as e:
        print(f"❌ 报告生成失败: {e}")

def example_custom_configuration():
    """示例6: 自定义配置使用"""
    print("=" * 60)
    print("⚙️ 示例6: 自定义配置使用")
    print("=" * 60)
    
    try:
        # 场景1: 使用自定义SonarQube配置
        custom_sonar_config = SonarQubeConfig(
            url=os.getenv('CUSTOM_SONARQUBE_URL', 'http://localhost:9000'),
            token=os.getenv('CUSTOM_SONARQUBE_TOKEN', ''),
            timeout=60,
            verify_ssl=False
        )
        
        custom_sonar_client = SonarQubeClient(custom_sonar_config)
        
        # 测试自定义配置的连接
        if custom_sonar_client.test_connection():
            print("✅ 自定义SonarQube配置连接成功")
            
            project_key = os.getenv('SONARQUBE_PROJECT_KEY', 'your-project-key')
            
            if project_key != 'your-project-key':
                # 使用自定义配置创建分析器
                analyzer = SonarQubeDefectAnalyzer(
                    project_key,
                    sonarqube_client=custom_sonar_client,
                    ai_model='llama3'
                )
                
                # 执行分析
                analysis_data = analyzer.analyze_project_defects(
                    severities=['CRITICAL', 'BLOCKER'],
                    use_ai=True
                )
                
                print(f"✅ 使用自定义配置分析完成")
                print(f"   项目: {analysis_data['project_info']['name']}")
                print(f"   问题数: {analysis_data['summary']['issue_stats']['total']}")
            else:
                print("⚠️ 请设置环境变量 SONARQUBE_PROJECT_KEY")
        else:
            print("❌ 自定义SonarQube配置连接失败")
        
        print("✅ 自定义配置示例完成!")
        
    except Exception as e:
        print(f"❌ 自定义配置示例失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='SonarQube缺陷分析器使用示例')
    parser.add_argument('--example', 
                       choices=['basic', 'ai', 'filter', 'multi', 'report', 'config', 'all'],
                       default='all',
                       help='要运行的示例')
    parser.add_argument('--project-key', help='SonarQube项目标识符')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.log_level)
    
    # 设置环境变量
    if args.project_key:
        os.environ['SONARQUBE_PROJECT_KEY'] = args.project_key
    
    print("🚀 SonarQube缺陷分析器使用示例")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查基本环境配置
    print("\n🔧 环境配置检查:")
    print(f"   SonarQube URL: {os.getenv('SONARQUBE_URL', '未设置')}")
    print(f"   项目标识符: {os.getenv('SONARQUBE_PROJECT_KEY', '未设置')}")
    print(f"   AI模型可用: {'是' if os.getenv('OLLAMA_BASE_URL') else '需要配置OLLAMA_BASE_URL'}")
    
    try:
        # 运行示例
        examples = {
            'basic': example_basic_analysis,
            'ai': example_ai_enhanced_analysis,
            'filter': example_custom_filtering,
            'multi': example_multiple_projects,
            'report': example_report_generation,
            'config': example_custom_configuration
        }
        
        if args.example == 'all':
            for example_name, example_func in examples.items():
                try:
                    example_func()
                    print()
                except KeyboardInterrupt:
                    print("\n用户中断执行")
                    break
                except Exception as e:
                    print(f"示例 {example_name} 执行失败: {e}")
                    print()
        else:
            if args.example in examples:
                examples[args.example]()
            else:
                print(f"未知示例: {args.example}")
        
        print("🎉 所有示例执行完成!")
        
    except KeyboardInterrupt:
        print("\n用户中断执行")
        sys.exit(1)
    except Exception as e:
        print(f"示例执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()