#!/usr/bin/env python3
"""
测试AI审查提示词和GitLab数据处理
"""

import json
from automation.mr_review_engine import MRReviewEngine, ReviewSeverity
from shared.gitlab_client import GitLabClient
from shared.ollama_client import OllamaClient

def test_real_mr_with_ai():
    """使用真实MR数据测试完整AI流程"""
    print("\n=== 测试真实MR数据 + AI分析 ===")
    
    # 使用真实MR数据
    gitlab_client = GitLabClient(log_level='DEBUG')
    project_id = "93"  # 项目ID
    mr_iid = 7078  # MR的IID
    # project_id = "3145"  # 项目ID
    # mr_iid = 1  # MR的IID
    try:
        # 1. 获取真实MR数据（使用智能上下文）
        mr_details = gitlab_client.get_merge_request_details_smart(project_id, mr_iid, enable_smart_context=True)
        if not mr_details:
            print("无法获取MR数据")
            return
            
        print(f"测试MR: {mr_details['basic_info']['title']}")
        print(f"变更文件数: {len(mr_details['changes'])}")
        
        # 2. 创建审查引擎并配置正确的AI模型
        engine = MRReviewEngine(log_level='DEBUG')
        # 使用与命令行相同的模型配置
        engine.config['ai_model'] = 'gpt-oss:120b'
        print(f"使用AI模型: {engine.config['ai_model']}")
        print(f"已启用DEBUG模式，将显示Ollama详细请求和响应信息")
        
        # 3. 分析前2个文件（避免调用太多AI）
        changes_to_test = mr_details['changes'][:5]
        print(f"分析前 {len(changes_to_test)} 个文件")
        
        # 4. 调用AI分析
        print("\n开始AI分析...")
        ai_issues = engine._analyze_with_ai(changes_to_test, mr_details)
        verified_ai_issues = engine._reanalyze_issues_with_original_prompt(ai_issues)
        print(f"\n=== AI分析结果 ===")
        print(f"初步发现问题数量: {len(ai_issues)}")
        print(f"复核后保留问题数量: {len(verified_ai_issues)}")

        verification_details = getattr(engine, 'last_issue_verification_details', {})
        if verification_details and verification_details.get('status') == 'success':
            removed = verification_details.get('removed_details', [])
            if removed:
                print("\n=== 复核剔除详情 ===")
                for item in removed:
                    human_index = item['index'] + 1
                    print(f"- 原索引 {human_index}: {item.get('title', '未知问题')}\n  原因: {item.get('reason', '未提供原因')}")
            else:
                print("\n复核判定：所有AI问题均符合提示词要求")
        elif verification_details:
            print(f"\n复核状态: {verification_details.get('status')}，复核未生效，保留初始问题列表")
        
        if len(verified_ai_issues) == 0:
            print("✅ AI没有报告任何问题 - 这是期望的结果！")
        else:
            print("❌ AI报告了以下问题:")
            for i, issue in enumerate(verified_ai_issues, 1):
                print(f"\n{i}. [{issue.severity.value}] {issue.title}")
                print(f"   类别: {issue.category}")
                print(f"   文件: {issue.file_path}")
                if issue.line_number:
                    print(f"   行号: {issue.line_number}")
                print(f"   描述: {issue.description}")
                if issue.suggestion:
                    print(f"   建议: {issue.suggestion}")
                print(f"   来源: {issue.source}")
        
        # 5. 分析问题类型
        if verified_ai_issues:
            print(f"\n=== 问题分析 ===")
            severity_counts = {}
            category_counts = {}
            for issue in verified_ai_issues:
                severity_counts[issue.severity.value] = severity_counts.get(issue.severity.value, 0) + 1
                category_counts[issue.category] = category_counts.get(issue.category, 0) + 1
            
            print(f"严重程度分布: {severity_counts}")
            print(f"类别分布: {category_counts}")
            
            # 检查是否有误报
            compilation_errors = [issue for issue in verified_ai_issues if "编译" in issue.title or "compilation" in issue.title.lower()]
            if compilation_errors:
                print(f"\n❌ 发现 {len(compilation_errors)} 个可能的编译错误误报:")
                for issue in compilation_errors:
                    print(f"  - {issue.title}")
            else:
                print("\n✅ 没有发现编译错误误报")

            severe_issues = [
                issue for issue in verified_ai_issues
                if issue.severity in {ReviewSeverity.CRITICAL, ReviewSeverity.ERROR}
            ]
            if severe_issues:
                print("\n=== 汇总建议分析 ===")
                summary_suggestions = engine._analyze_summary_suggestions(verified_ai_issues, mr_details)
                print(f"汇总建议数量: {len(summary_suggestions)}")
                for suggestion in summary_suggestions:
                    print(f"- {suggestion.title}: {suggestion.description}")
                    if suggestion.suggestion:
                        print(f"  建议: {suggestion.suggestion}")
            else:
                print("\n未检测到严重问题，跳过汇总建议分析")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """运行所有测试"""
    print("开始AI审查系统测试...\n")
    
    try:
        
        # 最重要的测试：使用真实数据测试AI
        test_real_mr_with_ai()
        
        print("\n=== 测试完成 ===")
        print("请检查上述输出，确保:")
        print("1. GitLab diff数据结构正确")
        print("2. 代码提取逻辑正确添加了diff标记")
        print("3. AI提示词包含所有约束条件")
        print("4. AI响应解析能正确处理各种格式")
        print("5. 真实MR数据AI分析结果合理")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
