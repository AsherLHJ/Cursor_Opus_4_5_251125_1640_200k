"""
MySQL 表结构初始化与 Data 目录导入（基于 CSV 验证）

功能：
1) 连接 MySQL（数据库：PaperDB）
2) 读取 PaperAndTagInfo/InfoList.Paper.csv 获取期刊/会议信息
3) 检查是否存在 ContentList 表，不存在则创建（包含 Name, FullName, DataRange, UpdateDate 字段）
4) 验证 Data 目录下的子文件夹是否在 CSV 中存在对应记录
5) 仅处理在 CSV 中存在的子文件夹，读取其 .bib 文件并导入到 PaperInfo 表
6) 汇报处理成功和失败的文件夹信息

运行：
    python tools_refresh_db_paper.py
"""
from __future__ import annotations

import os
from typing import List, Optional, Dict, Any, Tuple
import re
import json
import csv


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

def load_paper_info_csv(csv_path: str) -> Dict[str, Dict[str, Any]]:
    """
    从 InfoList.Paper.csv 读取期刊/会议信息
    返回格式：{Name: {Full Name: xxx, Data Range: xxx, Update Date: xxx}}
    """
    paper_info = {}
    try:
        # 优先 UTF-8（含 BOM），兼容 GB2312
        encodings = ("utf-8-sig", "utf-8", "gb2312")
        for enc in encodings:
            try:
                with open(csv_path, 'r', encoding=enc, newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = (row.get('Name') or '').strip()
                        if name:
                            price_raw = (row.get('Price') or '').strip()
                            try:
                                price_val = int(price_raw) if price_raw != '' else None
                            except ValueError:
                                price_val = None
                            paper_info[name] = {
                                'Full Name': (row.get('Full Name') or '').strip(),
                                'Data Range': (row.get('Data Range') or '').strip(),
                                'Update Date': (row.get('Update Date') or '').strip(),
                                'Price': price_val,
                            }
                return paper_info
            except UnicodeDecodeError:
                continue
        print("读取 CSV 失败：尝试了 UTF-8-SIG/UTF-8/GB2312 但均不兼容")
        return {}
    except Exception as e:
        print(f"读取 CSV 文件失败: {e}")
        return {}

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


def ensure_contentlist_table(conn):
    """
    确保 ContentList 表存在。
    表结构：
    - Name: VARCHAR(255) NOT NULL PRIMARY KEY（会议/期刊名字）
    - FullName: TEXT（完整名称）
    - DataRange: TEXT（数据范围）
    - UpdateDate: TEXT（更新日期）
    """
    cursor = None
    try:
        cursor = conn.cursor()
        # 创建表（若不存在）
        create_sql = """
        CREATE TABLE IF NOT EXISTS ContentList (
            Name VARCHAR(255) NOT NULL PRIMARY KEY,
            FullName TEXT,
            DataRange TEXT,
            UpdateDate TEXT,
            Price INT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """
        cursor.execute(create_sql)

        # 统一已存在表的字符集/排序规则
        try:
            cursor.execute("ALTER TABLE ContentList CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        except Exception:
            pass

        # 无论是否新建，检查并补齐缺失列（针对旧库）
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            """,
            (DB_CONFIG["DB_NAME"], "ContentList"),
        )
        existing_cols = {row[0] for row in cursor.fetchall()}

        if "FullName" not in existing_cols:
            cursor.execute("ALTER TABLE ContentList ADD COLUMN FullName TEXT")
        if "DataRange" not in existing_cols:
            cursor.execute("ALTER TABLE ContentList ADD COLUMN DataRange TEXT")
        if "UpdateDate" not in existing_cols:
            cursor.execute("ALTER TABLE ContentList ADD COLUMN UpdateDate TEXT")
        if "Price" not in existing_cols:
            cursor.execute("ALTER TABLE ContentList ADD COLUMN Price INT")
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def get_data_subfolders(data_dir: str) -> List[str]:
    """
    读取 Data 目录下的子文件夹名称，返回列表（仅目录名）
    """
    if not os.path.isdir(data_dir):
        return []
    names: List[str] = []
    for entry in os.listdir(data_dir):
        path = os.path.join(data_dir, entry)
        if os.path.isdir(path):
            names.append(entry)
    return names


def insert_content_names(conn, paper_info_dict: Dict[str, Dict[str, Any]]) -> int:
    """
    将期刊/会议信息插入或更新 ContentList 表（按 Name 主键）。
    使用 REPLACE INTO 实现幂等 upsert：存在则覆盖 FullName/DataRange/UpdateDate；不存在则插入。
    返回受影响的条数。
    """
    if not paper_info_dict:
        return 0
    cursor = None
    affected = 0
    try:
        cursor = conn.cursor()
        sql = """
        REPLACE INTO ContentList (Name, FullName, DataRange, UpdateDate, Price)
        VALUES (%s, %s, %s, %s, %s)
        """
        data = []
        for name, info in paper_info_dict.items():
            price_val = info.get('Price')
            try:
                price_val = int(price_val) if price_val is not None else None
            except Exception:
                price_val = None
            data.append((
                name,
                info.get('Full Name', ''),
                info.get('Data Range', ''),
                info.get('Update Date', ''),
                price_val
            ))
        
        cursor.executemany(sql, data)
        affected = cursor.rowcount
        return affected
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def ensure_paperinfo_table(conn):
    """
    确保 PaperInfo 表存在。
    列定义：
    - Name: TEXT NOT NULL（会议/期刊名字）
    - Year: INT NOT NULL（从文件名提取，如 CHI2016.bib -> 2016）
    - Title: TEXT NOT NULL UNIQUE
    - Author: TEXT NOT NULL
    - DOI: VARCHAR(512) NOT NULL PRIMARY KEY
    - Abstract: TEXT NOT NULL
    - Bib: TEXT NOT NULL（完整的 BibTeX 条目文本）
    """
    cursor = None
    try:
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS PaperInfo (
            Name TEXT NOT NULL,
            Year INT NOT NULL,
            Title TEXT NOT NULL,
            Author TEXT NOT NULL,
            DOI VARCHAR(512) NOT NULL,
            URL TEXT NOT NULL,
            Abstract TEXT NOT NULL,
            Bib TEXT NOT NULL,
            PRIMARY KEY (DOI),
            UNIQUE KEY uniq_title (Title(768)),
            INDEX idx_name (Name(255)),
            INDEX idx_year (Year)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """
        cursor.execute(create_sql)

        # 统一已存在表的字符集/排序规则
        try:
            cursor.execute("ALTER TABLE PaperInfo CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        except Exception:
            pass

        # 补齐缺失列（针对旧库）
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            """,
            (DB_CONFIG["DB_NAME"], "PaperInfo"),
        )
        existing_cols = {row[0] for row in cursor.fetchall()}
        if "URL" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE PaperInfo ADD COLUMN URL TEXT AFTER DOI")
            except Exception:
                cursor.execute("ALTER TABLE PaperInfo ADD COLUMN URL TEXT")
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def extract_year_from_filename(filename: str) -> Optional[int]:
    """
    从文件名中提取年份，如：CHI2016.bib -> 2016
    """
    # 避免使用正则，简单的字符串处理
    for i in range(len(filename) - 3):
        substr = filename[i:i+4]
        if substr.isdigit():
            year = int(substr)
            if 1900 <= year <= 2100:  # 合理的年份范围
                return year
    return None


def _load_bibtexparser() -> Tuple[Any, Any, Any]:
    """
    延迟导入 bibtexparser，并返回 (bibtexparser, BibTexParser, customization)
    """
    try:
        import bibtexparser
        from bibtexparser.bparser import BibTexParser
        from bibtexparser import customization
        return bibtexparser, BibTexParser, customization
    except ImportError:
        print("未找到 bibtexparser，请先安装：pip install bibtexparser")
        raise


def _read_text(file_path: str) -> str:
    """
    读取文件内容，优先使用 utf-8，失败时使用 latin-1
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()


def _parse_with_bibtexparser_file(file_path: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    使用 bibtexparser 解析 .bib 文件
    返回 (parsed_entries, error_message)
    """
    bibtexparser, BibTexParser, customization = _load_bibtexparser()
    try:
        content = _read_text(file_path)
        
        # 使用 bibtexparser 解析
        parser = BibTexParser(common_strings=True)
        parser.customization = None
        db = bibtexparser.loads(content, parser=parser)
        entries = db.entries or []
        
        return entries, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def _entry_to_bibtex_string(entry: Dict[str, Any]) -> str:
    """
    将单个条目转换为 BibTeX 字符串
    """
    bibtexparser, BibTexParser, customization = _load_bibtexparser()
    try:
        from bibtexparser.bwriter import BibTexWriter
        
        # 创建数据库对象
        db = bibtexparser.bibdatabase.BibDatabase()
        db.entries = [entry]
        
        # 创建写入器
        writer = BibTexWriter()
        writer.indent = '    '  # 使用4个空格缩进
        writer.align_values = True
        writer.order_entries_by = None
        writer.add_trailing_comma = True
        
        return bibtexparser.dumps(db, writer).strip()
    except Exception as e:
        print(f"转换条目为 BibTeX 字符串时出错: {e}")
        return ""


def _normalize_year(year_val: Optional[str]) -> Optional[int]:
    """
    标准化年份字段，提取 4 位数字年份
    """
    if year_val is None:
        return None
    val = str(year_val).strip()
    # 简单的数字提取，避免使用正则
    for i in range(len(val) - 3):
        substr = val[i:i+4]
        if substr.isdigit():
            year = int(substr)
            if 1900 <= year <= 2100:  # 合理的年份范围
                return year
    return None


def _split_authors(author_field: str) -> str:
    """
    将 author 字段标准化为以逗号+空格分隔的作者列表。
    BibTeX 通常以 ' and ' 分隔作者。
    """
    if not author_field:
        return ""
    
    # 简单的字符串分割，避免使用正则
    parts = []
    current_part = ""
    i = 0
    while i < len(author_field):
        if i <= len(author_field) - 5 and author_field[i:i+5].lower() == ' and ':
            if current_part.strip():
                parts.append(current_part.strip())
            current_part = ""
            i += 5
        else:
            current_part += author_field[i]
            i += 1
    
    if current_part.strip():
        parts.append(current_part.strip())
    
    return ", ".join(parts)


def parse_bib_entries_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    使用 bibtexparser 读取 .bib 文件并返回解析后的条目列表
    返回 parsed_entries
    """
    entries, error = _parse_with_bibtexparser_file(file_path)
    if error:
        print(f"解析文件 {file_path} 时出错: {error}")
        return []
    return entries


def _clean_text_for_db(text: str) -> str:
    """
    清理文本中可能导致 SQL 问题的字符
    """
    if not text:
        return ""
    
    # 去除多余空白
    text = text.strip()
    
    # 替换可能有问题的字符
    # 注意：mysql-connector-python 会自动处理转义，但我们还是做一些基本清理
    text = text.replace('\x00', '')  # 移除 null 字符
    text = re.sub(r'\s+', ' ', text)  # 将多个空白字符替换为单个空格
    
    return text


def _clean_bib_text_for_db(bib_text: str) -> str:
    """
    专门清理 BibTeX 文本用于数据库存储
    """
    if not bib_text:
        return ""
    
    # 去除首尾空白
    text = bib_text.strip()
    
    # 移除可能有问题的字符
    text = text.replace('\x00', '')  # 移除 null 字符
    text = text.replace('\r\n', '\n')  # 统一换行符
    text = text.replace('\r', '\n')
    
    # 不要压缩空白，保持 BibTeX 格式
    return text


def build_paper_rows_from_folder(folder_path: str, folder_name: str) -> List[tuple]:
    """
    遍历子文件夹中的 .bib 文件，使用 bibtexparser 解析条目并生成待插入 PaperInfo 的记录
    记录格式：(Name, Year, Title, Author, DOI, Abstract, Bib)
    仅保留字段完整且非空的条目（确保插入时无 NULL）
    """
    rows: List[tuple] = []
    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(".bib"):
            continue
        year = extract_year_from_filename(filename)
        file_path = os.path.join(folder_path, filename)
        entries = parse_bib_entries_from_file(file_path)
        
        print(f"文件 {filename} 解析到 {len(entries)} 个条目")
        
        for entry in entries:
            # 从 bibtexparser 解析结果中提取字段
            title = entry.get("title")
            abstract = entry.get("abstract")
            author_field = entry.get("author")
            doi = entry.get("doi")
            url_field = entry.get("url")
            entry_year = entry.get("year")
            
            # 处理年份：优先使用文件名中的年份，其次使用条目中的年份
            entry_year_int = _normalize_year(entry_year)
            final_year = year or entry_year_int

            # 标准化作者
            authors = _split_authors(author_field) if author_field else None

            # PaperInfo 中不能有空值：字段缺失或空字符串则跳过
            if not (folder_name and final_year and title and authors and doi and abstract):
                continue

            # 生成 BibTeX 文本
            bib_text = _entry_to_bibtex_string(entry)
            if not bib_text:
                continue

            # 清洗：去除多余空白和特殊字符
            try:
                row = (
                    _clean_text_for_db(folder_name),
                    int(final_year),
                    _clean_text_for_db(title),
                    _clean_text_for_db(authors),
                    _clean_text_for_db(doi),
                    _clean_text_for_db(url_field) if url_field else "",
                    _clean_text_for_db(abstract),
                    _clean_bib_text_for_db(bib_text),
                )
                # 再次确认必要列非空（允许 URL 为空）
                required_values = [row[0], row[1], row[2], row[3], row[4], row[6], row[7]]
                if any((str(v).strip() == "" for v in required_values)):
                    continue
                
                # 检查DOI长度限制
                if len(row[4]) > 512:  # DOI
                    print(f"跳过DOI过长的记录: {row[2][:50]}...")
                    continue

                rows.append(row)
            except Exception as e:
                print(f"处理条目时出错: {e}, 跳过该条目")
                continue
    return rows


def insert_paperinfo_rows(conn, rows: List[tuple]) -> int:
    """
    批量插入 PaperInfo 记录。使用 INSERT IGNORE 以忽略重复（按 DOI 主键或 Title 唯一）。
    返回尝试插入的行数（注意：被 IGNORE 的不计入真正新增）。
    """
    if not rows:
        return 0
    cursor = None
    try:
        cursor = conn.cursor()
        sql = """
        INSERT IGNORE INTO PaperInfo (Name, Year, Title, Author, DOI, URL, Abstract, Bib)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        # 逐条插入以便更好地处理错误
        attempted = 0
        for row in rows:
            try:
                cursor.execute(sql, row)
                attempted += 1
            except Exception as e:
                print(f"插入记录时出错: {e}")
                print(f"问题记录: Name={row[0]}, Title={row[2][:50]}...")
                continue
        return attempted
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass


def main():
    # 解析 Data 目录（与本文件同级目录下的 Data）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "Data")
    csv_path = os.path.join(script_dir, "PaperAndTagInfo", "InfoList.Paper.csv")

    # 读取 CSV 文件获取期刊/会议信息
    print(f"读取 CSV 文件：{csv_path}")
    paper_info_dict = load_paper_info_csv(csv_path)
    if not paper_info_dict:
        print("CSV 文件读取失败或为空，程序退出。")
        return
    print(f"从 CSV 文件读取到 {len(paper_info_dict)} 个期刊/会议信息")

    print(f"连接到 MySQL：{DB_CONFIG['DB_HOST']}:{DB_CONFIG['DB_PORT']}，数据库：{DB_CONFIG['DB_NAME']}")
    conn = get_connection()

    # 初始化处理结果收集列表，避免未定义异常
    failed_folders: List[str] = []
    processed_folders: List[str] = []

    try:
        # 1) 确认/创建 ContentList，并始终执行列补齐
        exists = table_exists(conn, DB_CONFIG['DB_NAME'], "ContentList")
        if exists:
            print("表 ContentList 已存在，检查并补齐缺失列...")
        else:
            print("表 ContentList 不存在，正在创建...")
        ensure_contentlist_table(conn)
        print("表 ContentList 已就绪。")

        # 2) 读取 Data 子文件夹名并验证
        subfolders = get_data_subfolders(data_dir)
        print(f"在 Data 目录下发现子文件夹：{subfolders}")
        
        # 验证哪些子文件夹在 CSV 中存在
        valid_folders = []
        for folder_name in subfolders:
            if folder_name in paper_info_dict:
                valid_folders.append(folder_name)
                processed_folders.append(folder_name)
            else:
                failed_folders.append(folder_name)
                print(f"警告：子文件夹 '{folder_name}' 在 CSV 文件中未找到对应记录，将跳过处理。")

        print(f"有效的子文件夹（在 CSV 中存在）：{valid_folders}")

        # 3) 将有效的期刊/会议信息插入 ContentList
        if valid_folders:
            valid_paper_info = {name: paper_info_dict[name] for name in valid_folders}
            affected = insert_content_names(conn, valid_paper_info)
            print(f"ContentList：已插入/更新 {affected} 条记录。")
        else:
            print("未发现任何有效的子文件夹可插入到 ContentList。")

        # 4) 确认/创建 PaperInfo
        ensure_paperinfo_table(conn)
        print("表 PaperInfo 已就绪。")

        # 5) 解析 .bib 并写入 PaperInfo（仅处理有效文件夹）
        total_attempted = 0
        for folder_name in valid_folders:
            folder_path = os.path.join(data_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue
            rows = build_paper_rows_from_folder(folder_path, folder_name)
            if not rows:
                print(f"[{folder_name}] 未解析到可插入的论文条目。")
                continue
            attempted = insert_paperinfo_rows(conn, rows)
            total_attempted += attempted
            print(f"[{folder_name}] 解析 {len(rows)} 条，尝试插入 {attempted} 条（重复将被忽略）。")

        # 6) 打印统计
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM PaperInfo")
        total_in_db = cursor.fetchone()[0]
        print(f"PaperInfo 表当前共有 {total_in_db} 条记录。")
        cursor.close()

        # 可选：抽样查看几条
        cursor = conn.cursor()
        cursor.execute("SELECT Name, Year, LEFT(Title, 80), LEFT(Author, 80), DOI FROM PaperInfo ORDER BY Year DESC, Name ASC LIMIT 5")
        samples = cursor.fetchall()
        if samples:
            print("示例数据（前 5 条）：")
            for s in samples:
                print(f"  Name={s[0]}, Year={s[1]}, Title={s[2]}, Author={s[3]}, DOI={s[4]}")
        cursor.close()

        # 7) 汇报处理结果
        print("\n" + "="*50)
        print("处理结果汇报：")
        print(f"成功处理的文件夹数量：{len(processed_folders)}")
        if processed_folders:
            print(f"成功处理的文件夹：{', '.join(processed_folders)}")
        
        print(f"失败/跳过的文件夹数量：{len(failed_folders)}")
        if failed_folders:
            print(f"失败/跳过的文件夹：{', '.join(failed_folders)}")
            print("失败原因：这些文件夹在 CSV 文件中未找到对应的期刊/会议信息")
        print("="*50)

    finally:
        try:
            conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()