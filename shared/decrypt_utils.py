#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AES解密工具
用于解密使用AES-128-CBC模式加密的数据
与Java版本的AESUtil保持兼容
"""

import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import sys
import argparse
import json


class AESDecryptUtil:
    """AES解密工具类"""

    def __init__(self, key: str, iv: str = "0102030405060709"):
        """
        初始化AES解密工具

        Args:
            key: 密钥，长度必须为16位
            iv: 初始化向量，默认为"0102030405060709"
        """
        if not key:
            raise ValueError("密钥不能为空")

        if len(key) != 16:
            raise ValueError(f"密钥长度必须为16位，当前长度: {len(key)}")

        self.key = key.encode('utf-8')
        self.iv = iv.encode('utf-8')

    def decrypt(self, encrypted_data: str) -> str:
        """
        解密AES-128-CBC加密的数据

        Args:
            encrypted_data: Base64编码的加密数据

        Returns:
            解密后的原始字符串

        Raises:
            Exception: 解密失败时抛出异常
        """
        try:
            # Base64解码
            encrypted_bytes = base64.b64decode(encrypted_data)

            # 创建AES解密器
            cipher = AES.new(self.key, AES.MODE_CBC, self.iv)

            # 解密
            decrypted_bytes = cipher.decrypt(encrypted_bytes)

            # 去除填充
            original_bytes = unpad(decrypted_bytes, AES.block_size)

            # 转换为字符串
            original_string = original_bytes.decode('utf-8')

            return original_string

        except Exception as e:
            print(f"解密失败: {str(e)}")
            return None

    def encrypt(self, plaintext: str) -> str:
        """
        加密数据（用于测试验证）

        Args:
            plaintext: 要加密的明文

        Returns:
            Base64编码的加密数据
        """
        try:
            # 创建AES加密器
            cipher = AES.new(self.key, AES.MODE_CBC, self.iv)

            # 填充并加密
            padded_data = self._pad(plaintext.encode('utf-8'), AES.block_size)
            encrypted_bytes = cipher.encrypt(padded_data)

            # Base64编码
            encrypted_string = base64.b64encode(encrypted_bytes).decode('utf-8')

            return encrypted_string

        except Exception as e:
            print(f"加密失败: {str(e)}")
            return None

    @staticmethod
    def _pad(data: bytes, block_size: int) -> bytes:
        """PKCS5填充"""
        pad_length = block_size - (len(data) % block_size)
        padding = bytes([pad_length] * pad_length)
        return data + padding


def main():
    """主函数 - 命令行工具"""
    parser = argparse.ArgumentParser(description='AES解密工具')
    parser.add_argument('--key', '-k', required=True, help='解密密钥（16位）')
    parser.add_argument('--data', '-d', required=True, help='要解密的Base64编码数据')
    parser.add_argument('--encrypt', '-e', action='store_true', help='加密模式')
    parser.add_argument('--pretty', '-p', action='store_true', help='美化JSON输出')

    args = parser.parse_args()

    try:
        # 创建解密工具实例
        aes_util = AESDecryptUtil(args.key)

        if args.encrypt:
            # 加密模式
            result = aes_util.encrypt(args.data)
            if result:
                print(f"加密结果: {result}")
        else:
            # 解密模式
            result = aes_util.decrypt(args.data)
            if result:
                print("解密成功:")

                # 尝试解析为JSON并美化输出
                if args.pretty:
                    try:
                        json_obj = json.loads(result)
                        print(json.dumps(json_obj, indent=2, ensure_ascii=False))
                    except json.JSONDecodeError:
                        print(result)
                else:
                    print(result)

    except ValueError as e:
        print(f"参数错误: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"执行错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # 示例用法
    if len(sys.argv) == 1:
        print("=== AES解密工具示例 ===")

        # 示例配置（与Java版本一致）
        example_key = "Finance-TA-WEB7."
        example_data = '{"baseInfo":{"desc":"基本信息","id":"baseInfo","alive":true,"mouseOver":"","iconClass":"item-base","activeClass":"selected-base","validate":true,"show":true},"techInfo":{"desc":"技术信息","id":"techInfo","alive":false,"mouseOver":"","iconClass":"item-period","activeClass":"selected-period","validate":true,"show":true},"bussinessType":{"desc":"销售商业务","id":"bussinessType","alive":false,"mouseOver":"","iconClass":"item-sale-fee-pay","activeClass":"selected-sale-fee-pay","validate":false,"show":true},"prodInterest":{"desc":"产品权限","id":"prodInterest","alive":false,"mouseOver":"","iconClass":"item-limit","activeClass":"selected-limit","validate":false,"show":true},"prjTailing":{"desc":"尾随佣金","id":"prjTailing","alive":false,"mouseOver":"","iconClass":"item-capital","activeClass":"selected-capital","validate":false,"show":true},"prjFeeDivide":{"desc":"费用分成","id":"prjFeeDivide","alive":false,"mouseOver":"","iconClass":"item-nav","activeClass":"selected-nav","validate":false,"show":true},"feeDiscount":{"desc":"折扣率上限","id":"feeDiscount","alive":false,"mouseOver":"","iconClass":"item-other","activeClass":"selected-other","validate":false,"show":true},"capitalAcct":{"desc":"垫资户","id":"capitalAcct","alive":false,"mouseOver":"","iconClass":"item-trutee","activeClass":"selected-trutee","validate":false,"show":true}}'

        print(f"原始数据: {example_data[:100]}...")
        print(f"密钥: {example_key}")

        try:
            # 加密测试
            aes_util = AESDecryptUtil(example_key)
            encrypted = aes_util.encrypt(example_data)
            print(f"加密结果: {encrypted}")

            # 解密测试
            decrypted = aes_util.decrypt(encrypted)
            print(f"解密结果: {decrypted[:100]}...")

            # 验证结果
            if decrypted == example_data:
                print("✓ 加密解密测试成功")
            else:
                print("✗ 加密解密测试失败")

        except Exception as e:
            print(f"测试失败: {str(e)}")

        print("\n=== 命令行用法 ===")
        print("解密: python decrypt_utils.py --key <16位密钥> --data <Base64数据>")
        print("加密: python decrypt_utils.py --key <16位密钥> --data <明文> --encrypt")
        print("美化JSON输出: python decrypt_utils.py --key <16位密钥> --data <Base64数据> --pretty")

    else:
        main()