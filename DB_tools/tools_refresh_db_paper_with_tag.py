"""
将 PaperAndTagInfo/InfoList.PaperWithTag.csv（默认GB2312）导入到 MySQL 表 info_paper_with_tag。

表结构：
- id: INT AUTO_INCREMENT PRIMARY KEY
- Name: VARCHAR(255) NOT NULL（同 PaperInfo.Name 的语义）
- Tag: VARCHAR(255) NOT NULL（同 info_tag.Tag 的语义）
- 唯一约束：UNIQUE (Name, Tag)，避免重复映射

策略：
- 读取 CSV -> 校验 Name/Tag 的存在性（PaperInfo/ info_tag）-> 仅插入合法映射
- 对已存在映射使用 INSERT IGNORE，避免重复错误
- 表不存在时创建；存在时尽量补齐缺失列、主键、索引

运行：
    python tools_refresh_db_paper_with_tag.py
"""
from __future__ import annotations

import os
import csv
import json
from typing import Dict, List, Tuple, Optional, Set


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


def ensure_info_paper_with_tag_table(conn):
    """
    确保 info_paper_with_tag 表存在，且包含：
    - id: INT AUTO_INCREMENT PRIMARY KEY
    - Name: VARCHAR(255) NOT NULL
    - Tag: VARCHAR(255) NOT NULL
    - UNIQUE KEY uniq_name_tag (Name, Tag)
    - 索引：idx_name(Name), idx_tag(Tag)

    若已存在旧列名（如 name/tag 小写），尝试重命名为 Name/Tag。
    若主键非 id 或缺失，尝试设置为 id。
    """
    cursor = None
    try:
        cursor = conn.cursor()
        # 1) 创建表（若不存在）
        create_sql = """
        CREATE TABLE IF NOT EXISTS info_paper_with_tag (
            id INT NOT NULL AUTO_INCREMENT,
            `Name` VARCHAR(255) NOT NULL,
            `Tag` VARCHAR(255) NOT NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uniq_name_tag (`Name`, `Tag`),
            INDEX idx_name (`Name`),
            INDEX idx_tag (`Tag`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """
        cursor.execute(create_sql)
        # 统一已存在表的字符集/排序规则
        try:
            cursor.execute("ALTER TABLE info_paper_with_tag CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        except Exception:
            pass

        # 2) 列存在性检查与重命名/补齐
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            """,
            (DB_CONFIG["DB_NAME"], "info_paper_with_tag"),
        )
        existing_cols = {row[0] for row in cursor.fetchall()}
        existing_lower = {c.lower() for c in existing_cols}

        # id 列
        if "id" not in existing_lower:
            cursor.execute("ALTER TABLE info_paper_with_tag ADD COLUMN id INT NOT NULL AUTO_INCREMENT FIRST")

        # Name 列
        if "Name" not in existing_cols:
            if "name" in existing_lower:
                cursor.execute("ALTER TABLE info_paper_with_tag CHANGE COLUMN `name` `Name` VARCHAR(255) NOT NULL")
            else:
                cursor.execute("ALTER TABLE info_paper_with_tag ADD COLUMN `Name` VARCHAR(255) NOT NULL")

        # Tag 列
        if "Tag" not in existing_cols:
            if "tag" in existing_lower:
                cursor.execute("ALTER TABLE info_paper_with_tag CHANGE COLUMN `tag` `Tag` VARCHAR(255) NOT NULL")
            else:
                cursor.execute("ALTER TABLE info_paper_with_tag ADD COLUMN `Tag` VARCHAR(255) NOT NULL")

        # 3) 主键为 id
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
            (DB_CONFIG["DB_NAME"], "info_paper_with_tag"),
        )
        pk_cols = [row[0] for row in cursor.fetchall()]
        if pk_cols != ["id"]:
            try:
                cursor.execute("ALTER TABLE info_paper_with_tag DROP PRIMARY KEY")
                cursor.execute("ALTER TABLE info_paper_with_tag ADD PRIMARY KEY (id)")
            except Exception as e:
                print(f"调整主键为 id 失败：{e}")

        # 4) 唯一索引与普通索引
        cursor.execute(
            """
            SELECT INDEX_NAME, COLUMN_NAME
            FROM information_schema.statistics
            WHERE table_schema=%s AND table_name=%s
            """,
            (DB_CONFIG["DB_NAME"], "info_paper_with_tag"),
        )
        idx = {}
        for name, col in cursor.fetchall():
            idx.setdefault(name, []).append(col)

        # 唯一 (Name, Tag)
        if "uniq_name_tag" not in idx or set(idx.get("uniq_name_tag", [])) != {"Name", "Tag"}:
            try:
                cursor.execute("ALTER TABLE info_paper_with_tag ADD UNIQUE KEY uniq_name_tag (`Name`, `Tag`)")
            except Exception as e:
                print(f"添加唯一索引 (Name, Tag) 失败：{e}")

        # idx_name
        if "idx_name" not in idx or idx.get("idx_name") != ["Name"]:
            try:
                cursor.execute("CREATE INDEX idx_name ON info_paper_with_tag (`Name`)")
            except Exception:
                pass

        # idx_tag
        if "idx_tag" not in idx or idx.get("idx_tag") != ["Tag"]:
            try:
                cursor.execute("CREATE INDEX idx_tag ON info_paper_with_tag (`Tag`)")
            except Exception:
                pass

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def load_paper_with_tag_csv(csv_path: str) -> List[Tuple[str, str]]:
    """
    读取 PaperAndTagInfo/InfoList.PaperWithTag.csv，返回 [(Name, Tag)]
    默认编码 GB2312；若失败则回退到 UTF-8（含 BOM）。
    """
    rows: List[Tuple[str, str]] = []
    def _read_with_encoding(enc: str) -> List[Tuple[str, str]]:
        res: List[Tuple[str, str]] = []
        with open(csv_path, "r", encoding=enc, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("Name") or "").strip()
                tag = (row.get("Tag") or "").strip()
                if not name or not tag:
                    continue
                res.append((name, tag))
        return res

    # 优先 UTF-8（含 BOM），其次 UTF-8，再回退 GB2312
    for enc in ("utf-8-sig", "utf-8", "gb2312"):
        try:
            rows = _read_with_encoding(enc)
            break
        except Exception:
            rows = []
            continue
    if not rows:
        print("读取 CSV 失败：尝试了 UTF-8-SIG/UTF-8/GB2312 但均不兼容")
        return []
    return rows


def fetch_distinct_names_from_paperinfo(conn) -> Set[str]:
    """
    获取 PaperInfo 表中已有的 Name 集合（去重）。
    """
    cursor = None
    names: Set[str] = set()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Name FROM PaperInfo")
        for (n,) in cursor.fetchall():
            n = (n or "").strip()
            if n:
                names.add(n)
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
    return names


def fetch_tags_from_info_tag(conn) -> Set[str]:
    """
    获取 info_tag 表中已有的 Tag 集合。
    """
    cursor = None
    tags: Set[str] = set()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT `Tag` FROM info_tag")
        for (t,) in cursor.fetchall():
            t = (t or "").strip()
            if t:
                tags.add(t)
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
    return tags


def insert_name_tag_mappings(conn, rows: List[Tuple[str, str]]) -> int:
    """
    批量插入 Name-Tag 映射到 info_paper_with_tag。
    使用 INSERT IGNORE 避免重复（唯一约束 Name+Tag）。
    返回成功插入的条数（被 IGNORE 的不计新增）。
    """
    if not rows:
        return 0
    cursor = None
    inserted = 0
    try:
        cursor = conn.cursor()
        sql = "INSERT IGNORE INTO info_paper_with_tag (`Name`, `Tag`) VALUES (%s, %s)"
        cursor.executemany(sql, rows)
        inserted = cursor.rowcount
        return inserted
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def main():
    csv_path = os.path.join(_SCRIPT_DIR, "PaperAndTagInfo", "InfoList.PaperWithTag.csv")
    print(f"读取 CSV（优先UTF-8）：{csv_path}")

    rows = load_paper_with_tag_csv(csv_path)
    if not rows:
        print("CSV 读取失败或为空，退出。")
        return
    print(f"CSV 中读取到 {len(rows)} 条 Name-Tag 映射")

    print(f"连接到 MySQL：{DB_CONFIG['DB_HOST']}:{DB_CONFIG['DB_PORT']}，数据库：{DB_CONFIG['DB_NAME']}")
    conn = get_connection()

    try:
        # 表准备
        exists = table_exists(conn, DB_CONFIG["DB_NAME"], "info_paper_with_tag")
        if exists:
            print("表 info_paper_with_tag 已存在，检查并补齐结构...")
        else:
            print("表 info_paper_with_tag 不存在，正在创建...")
        ensure_info_paper_with_tag_table(conn)
        print("表 info_paper_with_tag 已就绪。")

        # 参照合法性校验
        names_set = fetch_distinct_names_from_paperinfo(conn)
        tags_set = fetch_tags_from_info_tag(conn)
        valid_rows: List[Tuple[str, str]] = []
        invalid_rows: List[Tuple[str, str, str]] = []  # (Name, Tag, reason)

        for name, tag in rows:
            if name not in names_set:
                invalid_rows.append((name, tag, "Name 不在 PaperInfo 中"))
                continue
            if tag not in tags_set:
                invalid_rows.append((name, tag, "Tag 不在 info_tag 中"))
                continue
            valid_rows.append((name, tag))

        print(f"有效映射：{len(valid_rows)} 条；无效映射：{len(invalid_rows)} 条")
        if invalid_rows:
            for n, t, r in invalid_rows[:20]:
                print(f"  跳过：({n}, {t})，原因：{r}")
            if len(invalid_rows) > 20:
                print(f"  其余 {len(invalid_rows) - 20} 条略")

        # 插入
        inserted = insert_name_tag_mappings(conn, valid_rows)
        print(f"插入完成：新增 {inserted} 条（重复已忽略）")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()