"""tools_refresh_db_api

用途（READ-ONLY/INIT）：
    1. 连接 MySQL（DB_NAME 来自 config.json，默认 PaperDB）
    2. 若不存在则创建 api_list 表（仅保存账号与速率限额元数据，不再涉及“共享开关”等动态配置）
    3. 从同级目录下的 APIKey/ 读取所有 .txt 文件；每行非空文本视为一个 api_key，文件名作为 api_name；去重插入。

当前架构说明：
    - 账户并发已统一为“共享池”模型，本脚本不负责，也不写入任何共享/队列开关。
    - 不处理 tokens_per_req 全局参数；该参数统一由 app_settings 后台接口维护。
    - 脚本仅用于初始化或补充 api_list 内容，不应用于运行期动态切换任何模式。

运行：
        python tools_refresh_db_api.py
"""
from __future__ import annotations

import os
import json
import re
from typing import List, Optional, Dict, Any, Tuple


# =========================
# 配置（从 config.json 读取）
# =========================
def load_db_config(config_path: str) -> dict:
    """
    从 config.json 读取数据库配置（DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME）
    若字段缺失，使用合理默认值。
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    host = cfg.get("DB_HOST", "127.0.0.1")
    port = cfg.get("DB_PORT", 3306)
    # 端口可能是字符串，统一转 int
    try:
        port = int(port)
    except Exception:
        port = 3306

    user = cfg.get("DB_USER", "root")
    password = cfg.get("DB_PASSWORD", "")
    database = cfg.get("DB_NAME", "PaperDB")

    return {
        "DB_HOST": host,
        "DB_PORT": port,
        "DB_USER": user,
        "DB_PASSWORD": password,
        "DB_NAME": database,
    }


# 与本文件同目录的 config.json
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DB_CONFIG = load_db_config(_CONFIG_PATH)


def get_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    autocommit: bool = True,
    connect_timeout: int = 10,
):
    """
    建立到 MySQL 的连接，返回连接对象。
    依赖 mysql-connector-python
    若未传入参数，默认读取 DB_CONFIG。
    """
    # 默认读取配置
    host = host or DB_CONFIG["DB_HOST"]
    port = port or DB_CONFIG["DB_PORT"]
    user = user or DB_CONFIG["DB_USER"]
    password = password or DB_CONFIG["DB_PASSWORD"]
    database = database or DB_CONFIG["DB_NAME"]

    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            autocommit=autocommit,
            connection_timeout=connect_timeout,
        )
        # 统一连接会话字符集为 utf8mb4
        try:
            cur = conn.cursor()
            cur.execute("SET NAMES utf8mb4")
            cur.close()
        except Exception:
            pass
        return conn
    except ImportError:
        print("未找到 mysql-connector-python，请先安装：pip install mysql-connector-python")
        raise
    except Exception as e:
        print(f"连接 MySQL 失败：{e}")
        raise


def table_exists(conn, db_name: str, table_name: str) -> bool:
    """
    检查表是否存在（基于 information_schema）
    """
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
            (db_name, table_name),
        )
        count = cursor.fetchone()[0]
        return count > 0
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def ensure_api_list_table(conn):
    """确保 api_list 表存在（仅账号与限额元数据）。

    保留字段（为兼容旧版本，不建议擅自删除）：
      - api_index: 主键自增
      - api_key: 唯一的实际密钥值
      - api_name: 来源文件名（含扩展名）
      - up / is_active: 启用状态兼容字段（旧版本用 up，新版本用 is_active）
      - rpm_limit / tpm_limit: 速率与 token 上限（用于聚合有效容量）
      - tokens_per_req: 历史字段（当前容量统一采用全局 tokens_per_req，可选择未来迁移/废弃）
      - 其余（query_table, search_id, account_name）为历史兼容；新架构中不再使用查询绑定或多租户名称逻辑，但保留避免升级迁移复杂度。
    """
    cursor = None
    try:
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS api_list (
            api_index INT NOT NULL AUTO_INCREMENT,
            api_key VARCHAR(512) NOT NULL,
            api_name VARCHAR(255) NOT NULL,
            query_table VARCHAR(128) DEFAULT NULL,
            search_id INT DEFAULT NULL,
            up TINYINT(1) NOT NULL DEFAULT 1,
            account_name VARCHAR(128) NOT NULL DEFAULT 'default',
            rpm_limit INT NOT NULL DEFAULT 30000,
            tpm_limit BIGINT NOT NULL DEFAULT 5000000,
            tokens_per_req INT NOT NULL DEFAULT 400,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            PRIMARY KEY (api_index),
            UNIQUE KEY uniq_api_key (api_key),
            INDEX idx_api_name (api_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """
        cursor.execute(create_sql)
        # 统一已存在表的字符集/排序规则
        try:
            cursor.execute("ALTER TABLE api_list CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        except Exception:
            pass
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass

def _read_text_lines(file_path: str) -> List[str]:
    """
    读取文本文件的所有行，优先使用 utf-8，失败时使用 latin-1
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().splitlines()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read().splitlines()


def _clean_text(text: str) -> str:
    """
    清理文本中可能导致 SQL 问题的字符
    """
    if not text:
        return ""
    t = text.strip().replace('\x00', '')
    # 压缩连续空白为单空格
    t = re.sub(r'\s+', ' ', t)
    return t


def get_apikey_dir(script_dir: str) -> str:
    """
    计算 APIKey 目录路径（与脚本同级的 APIKey）
    """
    return os.path.join(script_dir, "APIKey")


def parse_apikeys_from_directory(apikey_dir: str) -> List[Tuple[str, str]]:
    """
    扫描 APIKey 目录下所有 .txt 文件。
    每个非空行作为一个 api_key，来源文件名作为 api_name。
    返回列表 [(api_key, api_name), ...]
    """
    if not os.path.isdir(apikey_dir):
        return []

    rows: List[Tuple[str, str]] = []
    for entry in os.listdir(apikey_dir):
        if not entry.lower().endswith(".txt"):
            continue
        file_path = os.path.join(apikey_dir, entry)
        if not os.path.isfile(file_path):
            continue

        filename = entry  # 按要求使用来源的 txt 文件名（含扩展名）
        lines = _read_text_lines(file_path)

        # 去重同一文件内部重复 key
        seen_in_file = set()
        for line in lines:
            key = _clean_text(line)
            if not key:
                continue
            if key in seen_in_file:
                continue
            seen_in_file.add(key)
            rows.append((key, filename))
    return rows


def insert_api_rows(conn, rows: List[Tuple[str, str]]) -> int:
    """
    批量插入 api_list 记录。使用 INSERT IGNORE 以忽略重复（按 api_key 唯一）。
    仅写入 (api_key, api_name)，其他字段使用默认值。
    返回尝试插入的行数（注意：被 IGNORE 的不计入真正新增）。
    """
    if not rows:
        return 0
    cursor = None
    try:
        cursor = conn.cursor()
        sql = """
        INSERT IGNORE INTO api_list (api_key, api_name)
        VALUES (%s, %s)
        """
        # 逐条插入以便更好处理单行错误
        attempted = 0
        for row in rows:
            try:
                cursor.execute(sql, row)
                attempted += 1
            except Exception as e:
                print(f"插入记录时出错: {e}")
                print(f"问题记录: api_key={row[0][:30]}..., 来自文件={row[1]}")
                continue
        return attempted
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def main():
    # 解析 APIKey 目录（与本文件同级目录下的 APIKey）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    apikey_dir = get_apikey_dir(script_dir)

    print(f"连接到 MySQL：{DB_CONFIG['DB_HOST']}:{DB_CONFIG['DB_PORT']}，数据库：{DB_CONFIG['DB_NAME']}")
    conn = get_connection()

    try:
        # 1) 确认/创建 api_list
        exists = table_exists(conn, DB_CONFIG['DB_NAME'], "api_list")
        if exists:
            print("表 api_list 已存在。")
        else:
            print("表 api_list 不存在，正在创建...")
            ensure_api_list_table(conn)
            print("表 api_list 已创建。")

    # 架构已统一共享并发：不再初始化任何“共享开关”或分支标记

        # 2) 读取 APIKey 目录 -> 解析 api_key 列表
        rows = parse_apikeys_from_directory(apikey_dir)
        unique_preview = len(rows)
        print(f"在 APIKey 目录下解析到 {unique_preview} 条候选 API Key 记录。")

        # 3) 插入到 api_list（忽略重复）
        attempted = insert_api_rows(conn, rows)
        print(f"api_list：已尝试插入 {attempted} 条记录（重复将被忽略）。")

        # 4) 打印统计
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM api_list")
        total_in_db = cursor.fetchone()[0]
        print(f"api_list 表当前共有 {total_in_db} 条记录。")
        cursor.close()

        # 可选：抽样查看几条
        cursor = conn.cursor()
        cursor.execute(
            "SELECT api_index, LEFT(api_key, 30), api_name, up FROM api_list ORDER BY api_index ASC LIMIT 5"
        )
        samples = cursor.fetchall()
        if samples:
            print("示例数据（前 5 条）：")
            for s in samples:
                print(f"  api_index={s[0]}, api_key={s[1]}, api_name={s[2]}, up={s[3]}")
        cursor.close()

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()