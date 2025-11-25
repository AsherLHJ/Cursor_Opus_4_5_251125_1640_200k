"""
MySQL 表结构初始化与 Sentences.csv 导入

功能：
1) 连接 MySQL（数据库：DB_NAME 来自 config.json，默认 PaperDB）
2) 检查是否存在 sentence 表，不存在则创建（utf8mb4 / utf8mb4_0900_ai_ci）
   - 两列：sentence_index INT AUTO_INCREMENT 主键；sentence TEXT NOT NULL
   - 在 sentence(255) 上建立唯一索引，配合 INSERT IGNORE 去重
3) 读取脚本同目录下的 Sentences.csv，每一行作为一条句子插入（跳过空行/标题行）

运行：
    python tools_refresh_db_sentence.py
"""
from __future__ import annotations

import os
import json
import re
import csv
from typing import List, Optional, Tuple


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


def ensure_sentence_table(conn):
    """
    确保 sentence 表存在。
    列定义：
    - sentence_index: INT 主键，自增（从 1 开始）
    - sentence: TEXT NOT NULL（存储句子）
    索引：
    - UNIQUE KEY uniq_sentence (sentence(255)) 用于去重
    """
    cursor = None
    try:
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS sentence (
            sentence_index INT NOT NULL AUTO_INCREMENT,
            sentence TEXT NOT NULL,
            PRIMARY KEY (sentence_index),
            UNIQUE KEY uniq_sentence (sentence(255))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """
        cursor.execute(create_sql)
        # 统一已存在表的字符集/排序规则
        try:
            cursor.execute("ALTER TABLE sentence CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        except Exception:
            pass
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def _clean_text(text: str) -> str:
    """
    清理文本中可能导致 SQL 问题的字符
    """
    if not text:
        return ""
    t = text.strip().replace("\x00", "")
    # 压缩连续空白为单空格
    t = re.sub(r"\s+", " ", t)
    return t


def get_csv_path(script_dir: str) -> str:
    """
    计算 Sentences.csv 路径（与脚本同目录）
    """
    return os.path.join(script_dir, "Sentences.csv")


def parse_sentences_from_csv(csv_path: str) -> List[str]:
    """
    读取 CSV 文件第一列作为 sentence。
    跳过标题行（若第一行是 'Sentences' 或 'Sentence'），去除空行，文件内去重。
    """
    if not os.path.isfile(csv_path):
        print(f"未找到 CSV 文件：{csv_path}")
        return []

    sentences: List[str] = []
    seen_in_file = set()

    # 优先使用 utf-8-sig（兼容 BOM），失败时回退 latin-1
    def _read_with_encoding(enc: str) -> List[List[str]]:
        with open(csv_path, "r", encoding=enc, newline="") as f:
            return list(csv.reader(f))

    rows: List[List[str]] = []
    try:
        rows = _read_with_encoding("utf-8-sig")
    except UnicodeDecodeError:
        rows = _read_with_encoding("latin-1")

    for idx, row in enumerate(rows):
        if not row:
            continue
        cell = _clean_text(row[0] if len(row) > 0 else "")
        if not cell:
            continue
        # 跳过标题行
        if idx == 0 and cell.lower() in {"sentences", "sentence"}:
            continue
        if cell in seen_in_file:
            continue
        seen_in_file.add(cell)
        sentences.append(cell)

    return sentences


def insert_sentences(conn, sentences: List[str]) -> int:
    """
    批量插入 sentence 记录。使用 INSERT IGNORE 以忽略重复（按 sentence 唯一索引）。
    仅写入 (sentence)。
    返回尝试插入的行数（注意：被 IGNORE 的不计入真正新增）。
    """
    if not sentences:
        return 0
    cursor = None
    try:
        cursor = conn.cursor()
        sql = "INSERT IGNORE INTO sentence (sentence) VALUES (%s)"
        attempted = 0
        for s in sentences:
            try:
                cursor.execute(sql, (s,))
                attempted += 1
            except Exception as e:
                print(f"插入记录时出错: {e}")
                print(f"问题记录: sentence={s[:30]}...")
                continue
        return attempted
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def main():
    # 解析 CSV 路径（与本文件同级目录下的 Sentences.csv）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = get_csv_path(script_dir)

    print(f"连接到 MySQL：{DB_CONFIG['DB_HOST']}:{DB_CONFIG['DB_PORT']}，数据库：{DB_CONFIG['DB_NAME']}")
    conn = get_connection()

    try:
        # 1) 确认/创建 sentence 表
        exists = table_exists(conn, DB_CONFIG["DB_NAME"], "sentence")
        if exists:
            print("表 sentence 已存在。")
        else:
            print("表 sentence 不存在，正在创建...")
            ensure_sentence_table(conn)
            print("表 sentence 已创建。")

        # 2) 读取 CSV -> 解析 sentence 列表
        sentences = parse_sentences_from_csv(csv_path)
        unique_preview = len(sentences)
        print(f"在 CSV 中解析到 {unique_preview} 条候选句子记录。")

        # 3) 插入到 sentence（忽略重复）
        attempted = insert_sentences(conn, sentences)
        print(f"sentence：已尝试插入 {attempted} 条记录（重复将被忽略）。")

        # 4) 打印统计
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sentence")
        total_in_db = cursor.fetchone()[0]
        print(f"sentence 表当前共有 {total_in_db} 条记录。")
        cursor.close()

        # 可选：抽样查看几条
        cursor = conn.cursor()
        cursor.execute(
            "SELECT sentence_index, LEFT(sentence, 30) FROM sentence ORDER BY sentence_index ASC LIMIT 5"
        )
        samples = cursor.fetchall()
        if samples:
            print("示例数据（前 5 条）：")
            for s in samples:
                print(f"  sentence_index={s[0]}, sentence={s[1]}")
        cursor.close()

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()