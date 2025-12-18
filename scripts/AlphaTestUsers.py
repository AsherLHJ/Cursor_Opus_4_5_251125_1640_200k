#!/usr/bin/env python3
"""
Alpha 测试用户批量管理脚本

功能：
- 批量注册 Alpha 测试账户到 paperdb.user_info 表
- 批量删除已注册的 Alpha 测试账户
- 将账户信息保存到 CSV 文件

使用方法：
  python scripts/AlphaTestUsers.py
"""

import os
import sys
import csv
import random
import string
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# 可配置参数（在此处修改）
# =============================================================================

# 操作模式开关：0 = 新增账户，1 = 删除账户
ACTION_MODE = 0

# user_info 表的 uid（主键）范围（格式："起始-结束"）
# 注意：uid 数量必须与后缀序号数量一致
UID_RANGE = "24-103"

# 用户名前缀
USERNAME_PREFIX = "autopaper"

# 后缀序号范围（格式："起始-结束"）
SUFFIX_RANGE = "21-100"

# 密码长度
PASSWORD_LENGTH = 6

# 新用户初始余额
INITIAL_BALANCE = 0.0

# 新用户初始权限（2表示普通用户）
INITIAL_PERMISSION = 2

# CSV 文件名（保存在 scripts 目录下）
CSV_FILENAME = "alpha_test_users.csv"


# =============================================================================
# 辅助函数
# =============================================================================

def parse_suffix_range(range_str: str) -> tuple:
    """
    解析后缀范围字符串
    例如："21-100" -> (21, 100)
    """
    parts = range_str.strip().split("-")
    if len(parts) != 2:
        raise ValueError(f"无效的后缀范围格式: {range_str}，应为 '起始-结束' 格式")
    
    start = int(parts[0].strip())
    end = int(parts[1].strip())
    
    if start > end:
        raise ValueError(f"起始值 {start} 不能大于结束值 {end}")
    
    return start, end


def generate_username(prefix: str, suffix_num: int) -> str:
    """
    生成用户名
    例如：prefix="autopaper", suffix_num=21 -> "autopaper0021"
    """
    return f"{prefix}{suffix_num:04d}"


def generate_password(length: int = 6) -> str:
    """
    生成随机密码
    由大小写英文字母和阿拉伯数字混合组成
    """
    # 确保至少包含一个大写字母、一个小写字母、一个数字
    password_chars = []
    password_chars.append(random.choice(string.ascii_uppercase))
    password_chars.append(random.choice(string.ascii_lowercase))
    password_chars.append(random.choice(string.digits))
    
    # 剩余位数随机选择
    all_chars = string.ascii_letters + string.digits
    remaining_length = length - 3
    if remaining_length > 0:
        password_chars.extend(random.choices(all_chars, k=remaining_length))
    
    # 打乱顺序
    random.shuffle(password_chars)
    
    return "".join(password_chars)


def get_db_connection():
    """
    获取数据库连接
    使用项目现有的数据库配置
    """
    try:
        from lib.load_data.db_base import _get_connection
        return _get_connection()
    except ImportError:
        # 如果无法导入，尝试直接读取配置
        import json
        import mysql.connector
        
        config_path = PROJECT_ROOT / "config.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        
        return mysql.connector.connect(
            host=cfg.get("DB_HOST", "127.0.0.1"),
            port=cfg.get("DB_PORT", 3306),
            user=cfg.get("DB_USER", "root"),
            password=cfg.get("DB_PASSWORD", ""),
            database=cfg.get("DB_NAME", "paperdb")
        )


def hash_password(password: str) -> str:
    """
    使用 bcrypt 哈希密码
    与项目现有的密码哈希方式保持一致
    """
    try:
        from lib.webserver.auth import hash_password as auth_hash
        return auth_hash(password)
    except ImportError:
        # 如果无法导入，直接使用 bcrypt
        import bcrypt
        pw_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


# =============================================================================
# 核心功能
# =============================================================================

def create_users():
    """
    批量创建 Alpha 测试用户
    """
    print("=" * 60)
    print("Alpha 测试用户批量注册")
    print("=" * 60)
    
    # 解析 UID 范围
    uid_start, uid_end = parse_suffix_range(UID_RANGE)
    uid_count = uid_end - uid_start + 1
    
    # 解析后缀范围
    suffix_start, suffix_end = parse_suffix_range(SUFFIX_RANGE)
    suffix_count = suffix_end - suffix_start + 1
    
    # 验证两个范围的数量是否一致
    if uid_count != suffix_count:
        print(f"错误: UID 范围数量 ({uid_count}) 与后缀范围数量 ({suffix_count}) 不一致！")
        print(f"  - UID_RANGE: {UID_RANGE} -> {uid_count} 个")
        print(f"  - SUFFIX_RANGE: {SUFFIX_RANGE} -> {suffix_count} 个")
        return
    
    print(f"UID 范围: {uid_start} - {uid_end}")
    print(f"用户名前缀: {USERNAME_PREFIX}")
    print(f"后缀范围: {suffix_start:04d} - {suffix_end:04d}")
    print(f"用户数量: {suffix_count}")
    print(f"密码长度: {PASSWORD_LENGTH}")
    print(f"初始余额: {INITIAL_BALANCE}")
    print(f"初始权限: {INITIAL_PERMISSION}")
    print("-" * 60)
    
    # 生成用户信息列表（uid, username, password）
    users = []
    uid_list = list(range(uid_start, uid_end + 1))
    suffix_list = list(range(suffix_start, suffix_end + 1))
    
    for idx in range(suffix_count):
        uid = uid_list[idx]
        suffix_num = suffix_list[idx]
        username = generate_username(USERNAME_PREFIX, suffix_num)
        password = generate_password(PASSWORD_LENGTH)
        users.append({"uid": uid, "username": username, "password": password})
    
    # 连接数据库
    conn = get_db_connection()
    cursor = conn.cursor()
    
    created_count = 0
    skipped_count = 0
    failed_count = 0
    
    try:
        for user in users:
            uid = user["uid"]
            username = user["username"]
            password = user["password"]
            
            # 检查 uid 是否已存在
            cursor.execute(
                "SELECT uid FROM user_info WHERE uid = %s",
                (uid,)
            )
            existing_uid = cursor.fetchone()
            
            if existing_uid:
                print(f"  [跳过] uid={uid}, {username} - UID 已存在")
                skipped_count += 1
                continue
            
            # 检查用户名是否已存在
            cursor.execute(
                "SELECT uid FROM user_info WHERE username = %s",
                (username,)
            )
            existing_username = cursor.fetchone()
            
            if existing_username:
                print(f"  [跳过] uid={uid}, {username} - 用户名已存在")
                skipped_count += 1
                continue
            
            try:
                # 哈希密码
                password_hash = hash_password(password)
                
                # 插入新用户（包含指定的 uid）
                cursor.execute(
                    """INSERT INTO user_info (uid, username, password, balance, permission) 
                       VALUES (%s, %s, %s, %s, %s)""",
                    (uid, username, password_hash, INITIAL_BALANCE, INITIAL_PERMISSION)
                )
                conn.commit()
                created_count += 1
                print(f"  [创建] uid={uid}, {username} - 密码: {password}")
                
            except Exception as e:
                print(f"  [失败] uid={uid}, {username} - {str(e)}")
                failed_count += 1
                conn.rollback()
    
    finally:
        cursor.close()
        conn.close()
    
    # 保存到 CSV 文件
    csv_path = Path(__file__).parent / CSV_FILENAME
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["uid", "username", "password"])
        writer.writeheader()
        writer.writerows(users)
    
    print("-" * 60)
    print(f"完成！")
    print(f"  - 创建成功: {created_count}")
    print(f"  - 已存在跳过: {skipped_count}")
    print(f"  - 创建失败: {failed_count}")
    print(f"  - CSV 文件已保存: {csv_path}")
    print("=" * 60)


def delete_users():
    """
    批量删除 Alpha 测试用户
    根据 UID_RANGE 指定的 uid 范围进行删除
    """
    print("=" * 60)
    print("Alpha 测试用户批量删除")
    print("=" * 60)
    
    # 解析 UID 范围
    uid_start, uid_end = parse_suffix_range(UID_RANGE)
    uid_count = uid_end - uid_start + 1
    
    print(f"UID 范围: {uid_start} - {uid_end}")
    print(f"预计删除用户数: {uid_count}")
    print("-" * 60)
    
    # 生成 uid 列表
    uid_list = list(range(uid_start, uid_end + 1))
    
    # 连接数据库
    conn = get_db_connection()
    cursor = conn.cursor()
    
    deleted_count = 0
    not_found_count = 0
    failed_count = 0
    
    try:
        for uid in uid_list:
            # 检查用户是否存在
            cursor.execute(
                "SELECT uid, username FROM user_info WHERE uid = %s",
                (uid,)
            )
            existing = cursor.fetchone()
            
            if not existing:
                print(f"  [不存在] uid={uid}")
                not_found_count += 1
                continue
            
            username = existing[1] if existing else ""
            
            try:
                # 删除用户
                cursor.execute(
                    "DELETE FROM user_info WHERE uid = %s",
                    (uid,)
                )
                conn.commit()
                deleted_count += 1
                print(f"  [删除] uid={uid}, {username}")
                
            except Exception as e:
                print(f"  [失败] uid={uid}, {username} - {str(e)}")
                failed_count += 1
                conn.rollback()
    
    finally:
        cursor.close()
        conn.close()
    
    print("-" * 60)
    print(f"完成！")
    print(f"  - 删除成功: {deleted_count}")
    print(f"  - 用户不存在: {not_found_count}")
    print(f"  - 删除失败: {failed_count}")
    print("=" * 60)


# =============================================================================
# 主入口
# =============================================================================

def main():
    """主函数"""
    print()
    
    if ACTION_MODE == 0:
        print("【模式】新增账户 (ACTION_MODE = 0)")
        print()
        create_users()
    elif ACTION_MODE == 1:
        print("【模式】删除账户 (ACTION_MODE = 1)")
        print()
        delete_users()
    else:
        print(f"错误: 无效的 ACTION_MODE 值: {ACTION_MODE}")
        print("请设置 ACTION_MODE 为 0（新增）或 1（删除）")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

