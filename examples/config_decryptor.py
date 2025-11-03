#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件解密工具
专门用于解密prod_mode_config.yml这类部分加密部分未加密的YAML配置文件
"""

import yaml
import sys
import os
import argparse
from pathlib import Path

# 添加shared目录到路径以便导入解密工具
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from decrypt_utils import AESDecryptUtil


class ConfigDecryptor:
    """配置文件解密器"""

    def __init__(self, key: str, iv: str = "0102030405060709"):
        """
        初始化配置解密器

        Args:
            key: 解密密钥（16位）
            iv: 初始化向量
        """
        self.aes_util = AESDecryptUtil(key, iv)
        self.encrypted_keys = set()  # 记录已解密的键
        self.failed_keys = set()     # 记录解密失败的键

    def is_encrypted_value(self, value: str) -> bool:
        """
        判断一个值是否为加密的Base64字符串

        Args:
            value: 要检查的值

        Returns:
            True表示是加密值，False表示不是
        """
        if not isinstance(value, str) or not value.strip():
            return False

        # 移除YAML的多行折叠标记
        clean_value = value.strip().replace('>-', '').strip()

        # 检查长度 - 加密值通常很长
        if len(clean_value) < 100:
            return False

        # 检查是否为有效的Base64字符
        try:
            import base64
            # 尝试解码，如果成功且结果合理，则认为是加密的
            decoded = base64.b64decode(clean_value)
            # 检查解码后的长度是否为AES块大小的倍数
            return len(decoded) % 16 == 0 and len(decoded) > 50
        except:
            return False

    def decrypt_value(self, value: str) -> str:
        """
        解密单个值

        Args:
            value: 要解密的值

        Returns:
            解密后的值，如果解密失败则返回原值
        """
        if not self.is_encrypted_value(value):
            return value

        # 检查原始值是否有多行折叠标记
        has_multiline_marker = value.strip().endswith('>-')

        # 移除YAML的多行折叠标记并清理
        clean_value = value.strip().replace('>-', '').strip()

        try:
            decrypted = self.aes_util.decrypt(clean_value)
            if decrypted:
                # 如果原始值有多行折叠标记，则在解密后的值后也添加标记
                if has_multiline_marker:
                    return decrypted + '\n>'
                else:
                    return decrypted
            else:
                return value  # 解密失败返回原值
        except Exception as e:
            print(f"解密失败: {e}")
            return value

    def decrypt_dict(self, data: dict, path: str = "") -> dict:
        """
        递归解密字典中的所有值

        Args:
            data: 要解密的字典
            path: 当前路径（用于日志）

        Returns:
            解密后的字典
        """
        result = {}

        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, dict):
                # 递归处理字典
                result[key] = self.decrypt_dict(value, current_path)
            elif isinstance(value, list):
                # 处理列表
                result[key] = self.decrypt_list(value, current_path)
            elif isinstance(value, str) and self.is_encrypted_value(value):
                # 解密字符串值
                print(f"正在解密: {current_path}")
                decrypted_value = self.decrypt_value(value)
                result[key] = decrypted_value

                if decrypted_value != value:
                    self.encrypted_keys.add(current_path)
                else:
                    self.failed_keys.add(current_path)
            else:
                # 普通值，直接复制
                result[key] = value

        return result

    def decrypt_list(self, data: list, path: str) -> list:
        """
        解密列表中的值

        Args:
            data: 要解密的列表
            path: 当前路径

        Returns:
            解密后的列表
        """
        result = []

        for i, item in enumerate(data):
            current_path = f"{path}[{i}]"

            if isinstance(item, dict):
                result.append(self.decrypt_dict(item, current_path))
            elif isinstance(item, list):
                result.append(self.decrypt_list(item, current_path))
            elif isinstance(item, str) and self.is_encrypted_value(item):
                print(f"正在解密: {current_path}")
                decrypted_item = self.decrypt_value(item)
                result.append(decrypted_item)

                if decrypted_item != item:
                    self.encrypted_keys.add(current_path)
                else:
                    self.failed_keys.add(current_path)
            else:
                result.append(item)

        return result

    def decrypt_config_file(self, input_file: str, output_file: str = None) -> dict:
        """
        解密配置文件

        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径（可选）

        Returns:
            解密后的配置数据
        """
        print(f"开始解密配置文件: {input_file}")

        # 读取配置文件
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            return None

        # 解密配置
        decrypted_config = self.decrypt_dict(config_data)

        # 输出统计信息
        print(f"\n解密完成!")
        print(f"成功解密的配置项: {len(self.encrypted_keys)}")
        for key in sorted(self.encrypted_keys):
            print(f"  ✓ {key}")

        if self.failed_keys:
            print(f"解密失败的配置项: {len(self.failed_keys)}")
            for key in sorted(self.failed_keys):
                print(f"  ✗ {key}")

        # 保存解密后的文件
        if output_file:
            try:
                self._save_preserving_format(input_file, output_file, decrypted_config)
                print(f"\n解密后的配置已保存到: {output_file}")
            except Exception as e:
                print(f"保存文件失败: {e}")

        return decrypted_config

    def analyze_config_file(self, input_file: str) -> None:
        """
        分析配置文件，显示哪些配置项是加密的

        Args:
            input_file: 配置文件路径
        """
        print(f"分析配置文件: {input_file}")

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            return

        encrypted_items = []
        plain_items = []

        self._analyze_item(config_data, "", encrypted_items, plain_items)

        print(f"\n分析结果:")
        print(f"加密的配置项 ({len(encrypted_items)}):")
        for item in encrypted_items:
            print(f"  🔒 {item} (长度: {self._get_value_length(config_data, item)})")

        print(f"\n未加密的配置项 ({len(plain_items)}):")
        for item in plain_items:
            print(f"  📄 {item}")

    def _analyze_item(self, data, path: str, encrypted_items: list, plain_items: list):
        """递归分析配置项"""
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, (dict, list)):
                    self._analyze_item(value, current_path, encrypted_items, plain_items)
                elif isinstance(value, str) and self.is_encrypted_value(value):
                    encrypted_items.append(current_path)
                elif isinstance(value, str):
                    plain_items.append(current_path)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                if isinstance(item, (dict, list)):
                    self._analyze_item(item, current_path, encrypted_items, plain_items)
                elif isinstance(item, str) and self.is_encrypted_value(item):
                    encrypted_items.append(current_path)
                elif isinstance(item, str):
                    plain_items.append(current_path)

    def _get_value_length(self, data, path: str) -> int:
        """获取配置项的长度"""
        try:
            keys = path.split('.')
            value = data
            for key in keys:
                value = value[key]
            return len(str(value))
        except:
            return 0

    def _save_preserving_format(self, input_file: str, output_file: str, decrypted_config: dict):
        """
        保存解密后的配置，使用更清晰的格式

        Args:
            input_file: 原始输入文件
            output_file: 输出文件
            decrypted_config: 解密后的配置数据
        """
        # 使用自定义的YAML输出格式
        with open(output_file, 'w', encoding='utf-8') as f:
            self._write_yaml_custom(f, decrypted_config)

    def _write_yaml_custom(self, f, data: dict, indent: int = 0):
        """
        自定义YAML写入，保持可读性
        """
        indent_str = '  ' * indent

        for key, value in data.items():
            if isinstance(value, dict):
                f.write(f"{indent_str}{key}:\n")
                self._write_yaml_custom(f, value, indent + 1)
            elif isinstance(value, list):
                f.write(f"{indent_str}{key}:\n")
                for item in value:
                    if isinstance(item, (dict, list)):
                        f.write(f"{indent_str}  -\n")
                        self._write_yaml_custom(f, item, indent + 2)
                    else:
                        f.write(f"{indent_str}  - {str(item)}\n")
            else:
                # 处理字符串值
                str_value = str(value)
                if len(str_value) > 100 or '\n' in str_value:
                    # 长字符串使用多行格式
                    f.write(f"{indent_str}{key}: >-\n")
                    lines = str_value.split('\n')
                    for line in lines:
                        f.write(f"{indent_str}  {line}\n")
                else:
                    # 短字符串使用单行格式
                    f.write(f"{indent_str}{key}: {str_value}\n")

    def _split_long_text(self, text: str, max_length: int = 80) -> list:
        """
        将长文本分割成多行，保持单词完整性

        Args:
            text: 要分割的文本
            max_length: 每行最大长度

        Returns:
            分割后的行列表
        """
        if len(text) <= max_length:
            return [text]

        lines = []
        current_line = ""

        for char in text:
            if len(current_line) >= max_length:
                # 寻找合适的分割点
                split_pos = current_line.rfind(',')
                if split_pos == -1:
                    split_pos = max_length - 1

                lines.append(current_line[:split_pos + 1])
                current_line = current_line[split_pos + 1:]
            current_line += char

        if current_line:
            lines.append(current_line)

        return lines

    def _prepare_replacements(self, data: dict, path: str, replacements: dict):
        """准备替换映射"""
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, (dict, list)):
                    self._prepare_replacements(value, current_path, replacements)
                else:
                    replacements[current_path] = str(value)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                if isinstance(item, (dict, list)):
                    self._prepare_replacements(item, current_path, replacements)
                else:
                    replacements[current_path] = str(item)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='配置文件解密工具')
    parser.add_argument('input_file', help='输入的配置文件路径')
    parser.add_argument('--key', '-k', required=True, help='解密密钥（16位）')
    parser.add_argument('--output', '-o', help='输出文件路径（可选）')
    parser.add_argument('--analyze', '-a', action='store_true', help='仅分析配置文件，不解密')
    parser.add_argument('--iv', default="0102030405060709", help='初始化向量（默认: 0102030405060709）')

    args = parser.parse_args()

    # 检查输入文件是否存在
    if not os.path.exists(args.input_file):
        print(f"错误: 文件不存在 - {args.input_file}")
        sys.exit(1)

    # 创建解密器
    try:
        decryptor = ConfigDecryptor(args.key, args.iv)
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)

    # 执行操作
    if args.analyze:
        decryptor.analyze_config_file(args.input_file)
    else:
        # 解密配置文件
        result = decryptor.decrypt_config_file(args.input_file, args.output)

        if not args.output:
            print("\n" + "="*50)
            print("解密后的配置内容:")
            print("="*50)
            if result:
                print(yaml.dump(result, default_flow_style=False,
                              allow_unicode=True, indent=2, sort_keys=False))


if __name__ == "__main__":
    # 示例用法
    if len(sys.argv) == 1:
        print("=== 配置文件解密工具示例 ===")

        # 检查示例配置文件是否存在
        example_config = "../temp/prod_mode_config.yml"
        if os.path.exists(example_config):
            print(f"发现示例配置文件: {example_config}")
            print("\n用法示例:")
            print(f"python {sys.argv[0]} {example_config} --key Finance-TA-WEB7. --analyze")
            print(f"python {sys.argv[0]} {example_config} --key Finance-TA-WEB7. --output decrypted_config.yml")
        else:
            print(f"未找到示例配置文件: {example_config}")

        print(f"\n基本用法:")
        print(f"python {sys.argv[0]} <配置文件> --key <16位密钥>")
        print(f"python {sys.argv[0]} <配置文件> --key <16位密钥> --output <输出文件>")
        print(f"python {sys.argv[0]} <配置文件> --key <16位密钥> --analyze")

        print(f"\n参数说明:")
        print(f"  --key, -k     解密密钥（必须，16位）")
        print(f"  --output, -o  输出文件路径（可选）")
        print(f"  --analyze, -a 仅分析配置文件，不解密")
        print(f"  --iv          初始化向量（默认: 0102030405060709）")
    else:
        main()