"""
数据库表结构定义模块
按照新架构指导文件定义所有MySQL表的CREATE TABLE语句
"""

from typing import Dict, List, Tuple
import mysql.connector


# ============================================================
# 表定义 SQL (新架构)
# 编码: utf8mb4, 排序: utf8mb4_0900_ai_ci
# ============================================================

TABLE_DEFINITIONS: Dict[str, str] = {
    # 1. 用户表
    "user_info": """
        CREATE TABLE IF NOT EXISTS user_info (
            uid INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            balance DECIMAL(10, 2) DEFAULT 0.00,
            permission INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 2. 管理员表 (新增)
    "admin_info": """
        CREATE TABLE IF NOT EXISTS admin_info (
            uid INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 3. 期刊列表
    "contentlist": """
        CREATE TABLE IF NOT EXISTS contentlist (
            Name VARCHAR(255) PRIMARY KEY,
            FullName TEXT,
            DataRange TEXT,
            UpdateDate TEXT,
            Price INT DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 4. 期刊年份统计 (新增)
    "contentlist_year_number": """
        CREATE TABLE IF NOT EXISTS contentlist_year_number (
            Name VARCHAR(255) PRIMARY KEY,
            YearNumberJson JSON COMMENT '格式: {"2023": 100, "2024": 50}'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 5. 文献表 (重构 - 仅保留DOI和Bib)
    "paperinfo": """
        CREATE TABLE IF NOT EXISTS paperinfo (
            DOI VARCHAR(255) PRIMARY KEY,
            Bib JSON NOT NULL COMMENT '包含完整BibTex字符串及元数据'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 6. 标签表
    "info_tag": """
        CREATE TABLE IF NOT EXISTS info_tag (
            Tag VARCHAR(255) PRIMARY KEY,
            TagType VARCHAR(255) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 7. 标签映射表
    "info_paper_with_tag": """
        CREATE TABLE IF NOT EXISTS info_paper_with_tag (
            id INT AUTO_INCREMENT PRIMARY KEY,
            Name VARCHAR(255) NOT NULL,
            Tag VARCHAR(255) NOT NULL,
            UNIQUE KEY uniq_name_tag (Name, Tag),
            INDEX idx_name (Name),
            INDEX idx_tag (Tag)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 8. 任务日志 (归档用 - 新结构)
    "query_log": """
        CREATE TABLE IF NOT EXISTS query_log (
            query_id VARCHAR(64) PRIMARY KEY,
            uid INT NOT NULL,
            search_params JSON,
            start_time DATETIME,
            end_time DATETIME,
            status VARCHAR(50),
            total_cost DECIMAL(10, 2),
            INDEX idx_uid (uid)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 9. 搜索结果 (归档用 - 新增，替代动态search_YYYYMMDD)
    "search_result": """
        CREATE TABLE IF NOT EXISTS search_result (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            uid INT NOT NULL,
            query_id VARCHAR(64) NOT NULL,
            doi VARCHAR(255) NOT NULL,
            ai_result JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_query (query_id),
            INDEX idx_uid (uid)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,

    # 10. API 列表
    "api_list": """
        CREATE TABLE IF NOT EXISTS api_list (
            api_index INT AUTO_INCREMENT PRIMARY KEY,
            api_key VARCHAR(512) NOT NULL UNIQUE,
            api_name VARCHAR(255),
            rpm_limit INT DEFAULT 3000,
            tpm_limit BIGINT DEFAULT 500000,
            is_active TINYINT(1) DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """,
}


# 表创建顺序（考虑外键依赖）
TABLE_ORDER: List[str] = [
    "user_info",
    "admin_info",
    "contentlist",
    "contentlist_year_number",
    "paperinfo",
    "info_tag",
    "info_paper_with_tag",
    "query_log",
    "search_result",
    "api_list",
]


def get_table_definitions() -> Dict[str, str]:
    """获取所有表定义"""
    return TABLE_DEFINITIONS.copy()


def create_table(conn, table_name: str) -> Tuple[bool, str]:
    """
    创建单个表
    
    Args:
        conn: MySQL连接
        table_name: 表名
        
    Returns:
        (success, message) 元组
    """
    if table_name not in TABLE_DEFINITIONS:
        return False, f"未知的表名: {table_name}"
    
    sql = TABLE_DEFINITIONS[table_name]
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        return True, f"表 {table_name} 创建成功"
    except mysql.connector.Error as e:
        return False, f"创建表 {table_name} 失败: {e}"
    finally:
        if cursor:
            cursor.close()


def table_exists(conn, table_name: str) -> bool:
    """检查表是否存在"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            (table_name,)
        )
        result = cursor.fetchone()
        return result[0] > 0 if result else False
    except Exception:
        return False
    finally:
        if cursor:
            cursor.close()


def create_all_tables(conn, skip_existing: bool = True) -> Dict[str, Tuple[bool, str]]:
    """
    按顺序创建所有表
    
    Args:
        conn: MySQL连接
        skip_existing: 是否跳过已存在的表
        
    Returns:
        {table_name: (success, message)} 字典
    """
    results = {}
    
    # 设置会话字符集
    try:
        cursor = conn.cursor()
        cursor.execute("SET NAMES utf8mb4")
        cursor.close()
    except Exception:
        pass
    
    for table_name in TABLE_ORDER:
        if skip_existing and table_exists(conn, table_name):
            results[table_name] = (True, f"表 {table_name} 已存在，跳过")
            continue
        
        success, message = create_table(conn, table_name)
        results[table_name] = (success, message)
        
        if not success:
            print(f"[ERROR] {message}")
        else:
            print(f"[OK] {message}")
    
    return results


def ensure_table_charset(conn, table_name: str) -> bool:
    """确保表使用utf8mb4字符集"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"ALTER TABLE `{table_name}` "
            f"CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[WARN] 转换表 {table_name} 字符集失败: {e}")
        return False
    finally:
        if cursor:
            cursor.close()


def add_column_if_not_exists(conn, table_name: str, column_name: str, 
                              column_def: str) -> bool:
    """如果列不存在则添加"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
            (table_name, column_name)
        )
        result = cursor.fetchone()
        if result and result[0] > 0:
            return True  # 列已存在
        
        cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN {column_def}")
        conn.commit()
        print(f"[OK] 为表 {table_name} 添加列 {column_name}")
        return True
    except Exception as e:
        print(f"[ERROR] 添加列失败: {e}")
        return False
    finally:
        if cursor:
            cursor.close()


def migrate_user_info_table(conn) -> bool:
    """迁移user_info表（添加created_at列如果不存在）"""
    return add_column_if_not_exists(
        conn, "user_info", "created_at",
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    )

