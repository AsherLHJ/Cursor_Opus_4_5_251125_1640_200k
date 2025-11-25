#!/usr/bin/env python3
"""
数据库初始化统一入口脚本

功能:
1. 连接MySQL数据库
2. 按正确顺序创建所有表
3. 导入期刊/文献/标签/API Key数据

使用方法:
    python init_database.py [--skip-data] [--only-schema] [--config PATH]

参数:
    --skip-data     只创建表结构，不导入数据
    --only-schema   只创建表结构（同--skip-data）
    --config PATH   指定config.json路径（默认为同目录下的config.json）
"""

import os
import sys
import json
import argparse
from typing import Optional

# 添加当前目录到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    import mysql.connector
except ImportError:
    print("[ERROR] 请先安装 mysql-connector-python: pip install mysql-connector-python")
    sys.exit(1)

from lib.db_schema import create_all_tables, migrate_user_info_table
from lib.loader_bib import load_contentlist, load_bib_data
from lib.loader_tags import load_tags_data
from lib.loader_api import load_api_keys


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"[WARN] 无法读取配置文件 {config_path}: {e}")
        cfg = {}
    
    # 支持新架构的配置格式
    if 'database' in cfg:
        db_cfg = cfg.get('database', {})
        local_mode = cfg.get('local_develop_mode', True)
        db_section = db_cfg.get('local' if local_mode else 'cloud', {})
        return {
            'DB_HOST': db_section.get('host', '127.0.0.1'),
            'DB_PORT': int(db_section.get('port', 3306)),
            'DB_USER': db_section.get('user', 'root'),
            'DB_PASSWORD': db_section.get('password', ''),
            'DB_NAME': db_section.get('name', 'paperdb'),
        }
    
    # 兼容旧格式
    return {
        'DB_HOST': cfg.get('DB_HOST', '127.0.0.1'),
        'DB_PORT': int(cfg.get('DB_PORT', 3306)),
        'DB_USER': cfg.get('DB_USER', 'root'),
        'DB_PASSWORD': cfg.get('DB_PASSWORD', ''),
        'DB_NAME': cfg.get('DB_NAME', 'paperdb'),
    }


def get_connection(config: dict):
    """建立数据库连接"""
    try:
        conn = mysql.connector.connect(
            host=config['DB_HOST'],
            port=config['DB_PORT'],
            user=config['DB_USER'],
            password=config['DB_PASSWORD'],
            database=config['DB_NAME'],
            autocommit=True,
            connection_timeout=10,
        )
        # 设置字符集
        cursor = conn.cursor()
        cursor.execute("SET NAMES utf8mb4")
        cursor.close()
        return conn
    except mysql.connector.Error as e:
        print(f"[ERROR] 连接数据库失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='数据库初始化脚本')
    parser.add_argument('--skip-data', action='store_true',
                        help='只创建表结构，不导入数据')
    parser.add_argument('--only-schema', action='store_true',
                        help='只创建表结构（同--skip-data）')
    parser.add_argument('--config', type=str, default=None,
                        help='config.json路径')
    args = parser.parse_args()
    
    skip_data = args.skip_data or args.only_schema
    
    # 确定配置文件路径
    if args.config:
        config_path = args.config
    else:
        # 优先使用DB_tools目录下的config.json
        config_path = os.path.join(SCRIPT_DIR, 'config.json')
        if not os.path.exists(config_path):
            # 回退到项目根目录的config.json
            config_path = os.path.join(os.path.dirname(SCRIPT_DIR), 'config.json')
    
    print(f"=" * 60)
    print("数据库初始化脚本 (新架构)")
    print(f"=" * 60)
    print(f"配置文件: {config_path}")
    
    # 加载配置
    config = load_config(config_path)
    print(f"数据库: {config['DB_HOST']}:{config['DB_PORT']}/{config['DB_NAME']}")
    print()
    
    # 连接数据库
    print("[Step 1] 连接数据库...")
    conn = get_connection(config)
    print("[OK] 数据库连接成功")
    print()
    
    try:
        # 创建表结构
        print("[Step 2] 创建表结构...")
        results = create_all_tables(conn, skip_existing=True)
        
        success_count = sum(1 for s, _ in results.values() if s)
        print(f"[OK] 表结构创建完成: {success_count}/{len(results)} 个表")
        print()
        
        # 迁移旧表（添加新列）
        print("[Step 3] 迁移旧表结构...")
        migrate_user_info_table(conn)
        print("[OK] 表迁移完成")
        print()
        
        if skip_data:
            print("[INFO] 跳过数据导入 (--skip-data)")
            print()
        else:
            # 定义数据目录
            data_dir = os.path.join(SCRIPT_DIR, 'Data')
            paper_info_dir = os.path.join(SCRIPT_DIR, 'PaperAndTagInfo')
            api_key_dir = os.path.join(SCRIPT_DIR, 'APIKey')
            
            # 导入ContentList
            print("[Step 4] 导入期刊列表...")
            csv_path = os.path.join(paper_info_dir, 'InfoList.Paper.csv')
            if os.path.exists(csv_path):
                journal_info = load_contentlist(conn, csv_path)
                print(f"[OK] 导入 {len(journal_info)} 个期刊")
            else:
                print(f"[SKIP] 文件不存在: {csv_path}")
                journal_info = {}
            print()
            
            # 导入标签数据
            print("[Step 5] 导入标签数据...")
            tag_csv = os.path.join(paper_info_dir, 'InfoList.Tag.csv')
            mapping_csv = os.path.join(paper_info_dir, 'InfoList.PaperWithTag.csv')
            if os.path.exists(tag_csv) and os.path.exists(mapping_csv):
                tag_count, mapping_count = load_tags_data(conn, tag_csv, mapping_csv)
                print(f"[OK] 导入 {tag_count} 个标签, {mapping_count} 个映射")
            else:
                print(f"[SKIP] 标签文件不存在")
            print()
            
            # 导入API Key
            print("[Step 6] 导入API Key...")
            if os.path.isdir(api_key_dir):
                api_count = load_api_keys(conn, api_key_dir)
                print(f"[OK] 导入 {api_count} 个API Key")
            else:
                print(f"[SKIP] API Key目录不存在: {api_key_dir}")
            print()
            
            # 导入文献数据
            print("[Step 7] 导入文献数据...")
            failed_records = []
            if os.path.isdir(data_dir) and journal_info:
                stats, failed_records = load_bib_data(conn, data_dir, journal_info)
                total = sum(stats.values())
                print(f"[OK] 导入 {total} 篇文献 (来自 {len(stats)} 个期刊)")
            else:
                print(f"[SKIP] Data目录不存在或期刊列表为空")
            print()
            
            # 打印导入失败的文献
            if failed_records:
                print("[Step 7.1] 导入失败的文献汇总:")
                print(f"  共 {len(failed_records)} 条记录导入失败")
                print("-" * 60)
                for idx, rec in enumerate(failed_records, 1):
                    print(f"  [{idx}] DOI: {rec['doi']}")
                    print(f"      文件: {rec['file']}")
                    print(f"      原因: {rec['error']}")
                    print()
                print("-" * 60)
                print()
        
        # 统计
        print("[Step 8] 统计表数据...")
        _print_table_stats(conn)
        
    finally:
        conn.close()
    
    print()
    print("=" * 60)
    print("数据库初始化完成!")
    print("=" * 60)


def _print_table_stats(conn):
    """打印各表的记录数"""
    tables = [
        'user_info', 'admin_info', 'contentlist', 'contentlist_year_number',
        'paperinfo', 'info_tag', 'info_paper_with_tag', 'query_log',
        'search_result', 'api_list'
    ]
    
    cursor = conn.cursor()
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} 条记录")
        except Exception:
            print(f"  {table}: (表不存在或查询失败)")
    cursor.close()


if __name__ == '__main__':
    main()

