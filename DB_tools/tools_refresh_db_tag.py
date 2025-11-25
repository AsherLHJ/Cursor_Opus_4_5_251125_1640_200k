"""
将 PaperAndTagInfo/InfoList.Tag.csv 的标签数据（GB2312）同步到 MySQL 表 info_tag。
目标：确保数据库表 info_tag 的内容与 CSV 完全一致（不多不少），主键为 tag。

运行：
    python tools_refresh_db_tag.py
"""
from __future__ import annotations

import os
import csv
import json
from typing import Dict, List, Tuple, Optional


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


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_SCRIPT_DIR, "config.json")
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


def ensure_info_tag_table(conn):
    """
    确保 info_tag 表存在，并尽量确保：
    - 存在列：tag (PK, NOT NULL), tagtype (NOT NULL)
    - 主键为 tag

    注意：若已有其他主键，将尝试替换为 tag 主键（可能需要权限）。
    """
    cursor = None
    try:
        cursor = conn.cursor()
        # 1) 创建表（若不存在）
        create_sql = """
        CREATE TABLE IF NOT EXISTS info_tag (
            tag VARCHAR(255) NOT NULL,
            tagtype VARCHAR(255) NOT NULL,
            PRIMARY KEY (tag)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """
        cursor.execute(create_sql)
        # 统一已存在表的字符集/排序规则
        try:
            cursor.execute("ALTER TABLE info_tag CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        except Exception:
            pass

        # 2) 补齐缺失列
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            """,
            (DB_CONFIG["DB_NAME"], "info_tag"),
        )
        existing_cols = {row[0] for row in cursor.fetchall()}
        if "tag" not in existing_cols:
            cursor.execute("ALTER TABLE info_tag ADD COLUMN tag VARCHAR(255) NOT NULL")
        if "tagtype" not in existing_cols:
            cursor.execute("ALTER TABLE info_tag ADD COLUMN tagtype VARCHAR(255) NOT NULL")

        # 3) 检查并校正主键为 tag
        cursor.execute(
            """
            SELECT k.column_name
            FROM information_schema.table_constraints AS c
            JOIN information_schema.key_column_usage AS k
              ON c.constraint_name = k.constraint_name
             AND c.table_schema = k.table_schema
             AND c.table_name = k.table_name
            WHERE c.table_schema=%s AND c.table_name=%s AND c.constraint_type='PRIMARY KEY'
            """,
            (DB_CONFIG["DB_NAME"], "info_tag"),
        )
        pk_cols = [row[0] for row in cursor.fetchall()]
        if not pk_cols:
            # 无主键则直接加
            try:
                cursor.execute("ALTER TABLE info_tag ADD PRIMARY KEY (tag)")
            except Exception as e:
                print(f"为 info_tag 添加主键(tag)失败：{e}")
        elif pk_cols != ["tag"]:
            # 主键不为 tag，尝试替换
            try:
                cursor.execute("ALTER TABLE info_tag DROP PRIMARY KEY")
                cursor.execute("ALTER TABLE info_tag ADD PRIMARY KEY (tag)")
            except Exception as e:
                print(f"替换 info_tag 主键为 tag 失败：{e}")
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def load_tags_from_csv(csv_path: str) -> Dict[str, str]:
    """
    从 CSV 读取标签数据，优先 UTF-8（含 BOM），其次 UTF-8，最后回退 GB2312。
    返回 {tag: tagtype}
    """
    def _try_read(enc: str) -> Dict[str, str]:
        tags_local: Dict[str, str] = {}
        with open(csv_path, "r", encoding=enc, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tag = (row.get("Tag") or "").strip()
                tagtype = (row.get("TagType") or "").strip()
                if not tag:
                    continue
                if tag in tags_local and tags_local[tag] != tagtype:
                    print(f"警告：CSV 中存在重复标签且类型不一致，覆盖为最新：{tag} -> {tagtype}")
                tags_local[tag] = tagtype or ""
        return tags_local

    for enc in ("utf-8-sig", "utf-8", "gb2312"):
        try:
            return _try_read(enc)
        except Exception:
            continue
    print("读取 CSV 文件失败：尝试了 UTF-8-SIG/UTF-8/GB2312 但均不兼容")
    return {}


def fetch_info_tag_from_db(conn) -> Dict[str, str]:
    """
    从数据库读取 info_tag 内容，返回 {tag: tagtype}
    """
    cursor = None
    data: Dict[str, str] = {}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tag, tagtype FROM info_tag")
        for tag, tagtype in cursor.fetchall():
            data[(tag or "").strip()] = (tagtype or "").strip()
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
    return data


def sync_info_tag(conn, desired: Dict[str, str], current: Dict[str, str]) -> Tuple[int, int, int]:
    """
    将 info_tag 表内容与 desired（CSV）同步为完全一致。
    返回 (inserted_count, updated_count, deleted_count)
    """
    to_insert: List[Tuple[str, str]] = []
    to_update: List[Tuple[str, str]] = []
    to_delete: List[str] = []

    desired_keys = set(desired.keys())
    current_keys = set(current.keys())

    # 需要插入
    for tag in sorted(desired_keys - current_keys):
        to_insert.append((tag, desired[tag]))

    # 需要更新
    for tag in sorted(desired_keys & current_keys):
        if (current.get(tag) or "") != (desired.get(tag) or ""):
            to_update.append((desired[tag], tag))  # (new_tagtype, tag)

    # 需要删除
    for tag in sorted(current_keys - desired_keys):
        to_delete.append(tag)

    cursor = None
    inserted = updated = deleted = 0
    try:
        cursor = conn.cursor()

        if to_insert:
            cursor.executemany(
                "INSERT INTO info_tag (`Tag`, `TagType`) VALUES (%s, %s)",
                to_insert,
            )
            inserted = cursor.rowcount

        if to_update:
            cursor.executemany(
                "UPDATE info_tag SET `TagType`=%s WHERE `Tag`=%s",
                to_update,
            )
            updated = cursor.rowcount

        if to_delete:
            cursor.executemany(
                "DELETE FROM info_tag WHERE `Tag`=%s",
                [(t,) for t in to_delete],
            )
            deleted = cursor.rowcount

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass

    return inserted, updated, deleted


def main():
    csv_path = os.path.join(_SCRIPT_DIR, "PaperAndTagInfo", "InfoList.Tag.csv")
    print(f"读取标签 CSV（优先UTF-8）：{csv_path}")

    desired = load_tags_from_csv(csv_path)
    if not desired:
        print("CSV 读取失败或为空，退出。")
        return
    print(f"CSV 中读取到 {len(desired)} 个标签")

    print(f"连接到 MySQL：{DB_CONFIG['DB_HOST']}:{DB_CONFIG['DB_PORT']}，数据库：{DB_CONFIG['DB_NAME']}")
    conn = get_connection()

    try:
        # 表准备
        exists = table_exists(conn, DB_CONFIG["DB_NAME"], "info_tag")
        if exists:
            print("表 info_tag 已存在，检查并补齐列与主键...")
        else:
            print("表 info_tag 不存在，正在创建...")
        ensure_info_tag_table(conn)
        print("表 info_tag 已就绪。")

        # 现有数据
        current = fetch_info_tag_from_db(conn)
        print(f"数据库当前包含 {len(current)} 个标签")

        # 同步
        inserted, updated, deleted = sync_info_tag(conn, desired, current)
        print("同步完成：")
        print(f"  插入：{inserted} 条")
        print(f"  更新：{updated} 条")
        print(f"  删除：{deleted} 条")

        # 再次校验一致性
        after = fetch_info_tag_from_db(conn)
        if len(after) != len(desired):
            print("警告：同步后数量仍不一致，请检查权限或约束。")
        else:
            # 严格逐条比对
            mismatch = [(k, desired[k], after.get(k)) for k in desired.keys() if desired[k] != after.get(k)]
            if mismatch:
                print("警告：同步后存在内容不一致：")
                for k, dv, av in mismatch[:10]:
                    print(f"  标签 {k}: CSV={dv}, DB={av}")
            else:
                print("校验通过：数据库内容与 CSV 完全一致。")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()