#!/usr/bin/env python3
"""
创建管理员账户脚本

用途：
    向数据库中添加新的管理员账户。

使用方法：
    1. 修改下方的 ADMIN_USERNAME 和 ADMIN_PASSWORD 变量
    2. 运行: python scripts/create_admin.py

注意：
    - 密码会自动使用bcrypt加密
    - 需要数据库连接配置正确（读取config.json）
    - 需要先安装依赖: pip install bcrypt mysql-connector-python
"""

import sys
import os

# ============================================================
# 修改以下变量来设置管理员账户
# ============================================================
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "your_password_here"  # 明文密码，脚本会自动加密
# ============================================================

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def main():
    print("=" * 50)
    print("管理员账户创建工具")
    print("=" * 50)
    print()
    
    # 检查是否修改了默认密码
    if ADMIN_PASSWORD == "your_password_here":
        print("[错误] 请先修改脚本中的 ADMIN_PASSWORD 变量！")
        print("       不要使用默认的 'your_password_here'")
        sys.exit(1)
    
    # 导入必要的模块
    try:
        import bcrypt
    except ImportError:
        print("[错误] 缺少bcrypt模块，请运行: pip install bcrypt")
        sys.exit(1)
    
    try:
        import mysql.connector
    except ImportError:
        print("[错误] 缺少mysql-connector-python模块，请运行: pip install mysql-connector-python")
        sys.exit(1)
    
    # 加载配置
    try:
        from lib.config import config_loader as config
        print(f"[信息] 数据库配置:")
        print(f"       Host: {config.DB_HOST}")
        print(f"       Port: {config.DB_PORT}")
        print(f"       Database: {config.DB_NAME}")
        print(f"       Mode: {'本地开发' if config.local_develop_mode else '云端生产'}")
        print()
    except Exception as e:
        print(f"[错误] 加载配置失败: {e}")
        sys.exit(1)
    
    # 加密密码
    print(f"[步骤1] 加密密码...")
    password_hash = bcrypt.hashpw(
        ADMIN_PASSWORD.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    print(f"       密码已加密 (bcrypt)")
    
    # 连接数据库
    print(f"\n[步骤2] 连接数据库...")
    try:
        conn = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        cursor = conn.cursor()
        print("       数据库连接成功")
    except Exception as e:
        print(f"[错误] 数据库连接失败: {e}")
        sys.exit(1)
    
    # 检查用户名是否已存在
    print(f"\n[步骤3] 检查用户名 '{ADMIN_USERNAME}'...")
    cursor.execute(
        "SELECT uid FROM admin_info WHERE username = %s",
        (ADMIN_USERNAME,)
    )
    existing = cursor.fetchone()
    
    if existing:
        print(f"[警告] 用户名 '{ADMIN_USERNAME}' 已存在 (ID: {existing[0]})")
        response = input("       是否更新密码? (y/N): ").strip().lower()
        if response == 'y':
            cursor.execute(
                "UPDATE admin_info SET password = %s WHERE username = %s",
                (password_hash, ADMIN_USERNAME)
            )
            conn.commit()
            print(f"[成功] 管理员 '{ADMIN_USERNAME}' 的密码已更新")
        else:
            print("[取消] 操作已取消")
    else:
        # 创建新管理员
        print(f"\n[步骤4] 创建管理员账户...")
        cursor.execute(
            "INSERT INTO admin_info (username, password) VALUES (%s, %s)",
            (ADMIN_USERNAME, password_hash)
        )
        conn.commit()
        admin_id = cursor.lastrowid
        print(f"[成功] 管理员账户创建成功!")
        print(f"       用户名: {ADMIN_USERNAME}")
        print(f"       管理员ID: {admin_id}")
    
    # 清理
    cursor.close()
    conn.close()
    
    print()
    print("=" * 50)
    print("提示：")
    print(f"  - 管理员登录地址: /admin/login.html")
    print(f"  - 用户名: {ADMIN_USERNAME}")
    print(f"  - 请妥善保管密码")
    print("=" * 50)


if __name__ == "__main__":
    main()

