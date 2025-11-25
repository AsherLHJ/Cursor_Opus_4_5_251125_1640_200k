"""
Bib文件解析与导入模块
负责解析.bib文件并导入到paperinfo表和contentlist表
同时生成contentlist_year_number统计数据
"""

import os
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

try:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser
    from bibtexparser.bwriter import BibTexWriter
    BIBTEXPARSER_AVAILABLE = True
except ImportError:
    BIBTEXPARSER_AVAILABLE = False
    print("[WARN] bibtexparser 未安装，请运行: pip install bibtexparser")


def _read_text(file_path: str) -> str:
    """读取文件内容，优先使用utf-8，失败时使用latin-1"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()


def _extract_year_from_filename(filename: str) -> Optional[int]:
    """从文件名中提取年份"""
    for i in range(len(filename) - 3):
        substr = filename[i:i+4]
        if substr.isdigit():
            year = int(substr)
            if 1900 <= year <= 2100:
                return year
    return None


def _normalize_year(year_val: Any) -> Optional[int]:
    """标准化年份字段"""
    if year_val is None:
        return None
    val = str(year_val).strip()
    for i in range(len(val) - 3):
        substr = val[i:i+4]
        if substr.isdigit():
            year = int(substr)
            if 1900 <= year <= 2100:
                return year
    return None


def _sanitize_for_json(text: str) -> str:
    """
    清理字符串中的LaTeX特殊字符，使其可安全序列化为JSON
    
    LaTeX中的转义符（如 \\% \\& 等）在JSON中会被解释为无效转义序列，
    需要将它们转换为普通字符。
    """
    if not text:
        return text
    
    # 替换LaTeX转义符为普通字符
    replacements = [
        ('\\%', '%'),
        ('\\&', '&'),
        ('\\_', '_'),
        ('\\#', '#'),
        ('\\$', '$'),
        ('\\{', '{'),
        ('\\}', '}'),
        ('\\~', '~'),
        ('\\^', '^'),
        ('\\textasciitilde', '~'),
        ('\\textasciicircum', '^'),
    ]
    
    for old, new in replacements:
        text = text.replace(old, new)
    
    # 移除其他可能导致问题的控制字符 (ASCII 0-31, 除了换行和制表符)
    cleaned = []
    for char in text:
        code = ord(char)
        if code < 32 and code not in (9, 10, 13):  # 保留 tab, newline, carriage return
            continue
        cleaned.append(char)
    
    return ''.join(cleaned)


def _entry_to_bib_string(entry: Dict[str, Any]) -> str:
    """将单个条目转换为BibTeX字符串"""
    if not BIBTEXPARSER_AVAILABLE:
        # 简单的回退实现
        entry_type = entry.get('ENTRYTYPE', 'article')
        entry_id = entry.get('ID', 'unknown')
        lines = [f"@{entry_type}{{{entry_id},"]
        for key, val in entry.items():
            if key not in ('ENTRYTYPE', 'ID') and val:
                lines.append(f"  {key} = {{{val}}},")
        lines.append("}")
        return "\n".join(lines)
    
    try:
        db = bibtexparser.bibdatabase.BibDatabase()
        db.entries = [entry]
        writer = BibTexWriter()
        writer.indent = '    '
        writer.align_values = True
        return bibtexparser.dumps(db, writer).strip()
    except Exception as e:
        print(f"[WARN] 转换BibTeX字符串失败: {e}")
        return ""


def parse_bib_file(file_path: str) -> List[Dict[str, Any]]:
    """解析单个.bib文件"""
    if not BIBTEXPARSER_AVAILABLE:
        print("[ERROR] bibtexparser 未安装")
        return []
    
    try:
        content = _read_text(file_path)
        parser = BibTexParser(common_strings=True)
        parser.customization = None
        db = bibtexparser.loads(content, parser=parser)
        return db.entries or []
    except Exception as e:
        print(f"[ERROR] 解析文件 {file_path} 失败: {e}")
        return []


def build_paperinfo_record(entry: Dict[str, Any], journal_name: str, 
                           file_year: Optional[int]) -> Optional[Tuple[str, Dict]]:
    """
    从bib条目构建paperinfo记录
    
    新架构下paperinfo表仅包含两列:
    - DOI: VARCHAR(255) PRIMARY KEY
    - Bib: JSON (包含完整BibTex字符串及元数据)
    
    Returns:
        (doi, bib_json) 元组，或 None（如果缺少必要字段）
    """
    doi = entry.get('doi', '').strip()
    if not doi:
        return None
    
    # 提取元数据并清理LaTeX特殊字符
    title = _sanitize_for_json(entry.get('title', '').strip())
    abstract = _sanitize_for_json(entry.get('abstract', '').strip())
    author = _sanitize_for_json(entry.get('author', '').strip())
    url = entry.get('url', '').strip()
    entry_year = _normalize_year(entry.get('year'))
    year = file_year or entry_year
    
    # 生成BibTeX字符串并清理
    bib_string = _entry_to_bib_string(entry)
    if not bib_string:
        return None
    bib_string = _sanitize_for_json(bib_string)
    
    # 构建JSON对象
    bib_json = {
        "bib": bib_string,
        "name": journal_name,
        "year": year,
        "title": title,
        "author": author,
        "abstract": abstract,
        "url": url,
        "doi": doi,
    }
    
    return (doi, bib_json)


def load_bib_data(conn, data_dir: str, journal_info: Dict[str, Dict]) -> Tuple[Dict[str, int], List[Dict]]:
    """
    加载所有bib数据到paperinfo表
    
    Args:
        conn: MySQL连接
        data_dir: Data目录路径
        journal_info: 期刊信息字典 {Name: {Full Name, Data Range, ...}}
        
    Returns:
        元组 (stats, failed_records)
        - stats: 统计信息 {journal_name: paper_count}
        - failed_records: 失败记录列表 [{'doi': ..., 'file': ..., 'error': ...}, ...]
    """
    if not os.path.isdir(data_dir):
        print(f"[ERROR] Data目录不存在: {data_dir}")
        return {}, []
    
    stats = {}
    failed_records = []
    year_counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    
    for folder_name in os.listdir(data_dir):
        folder_path = os.path.join(data_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        
        # 只处理在journal_info中存在的文件夹
        if folder_name not in journal_info:
            print(f"[SKIP] 文件夹 {folder_name} 不在期刊列表中")
            continue
        
        inserted = 0
        for filename in os.listdir(folder_path):
            if not filename.lower().endswith('.bib'):
                continue
            
            file_path = os.path.join(folder_path, filename)
            file_year = _extract_year_from_filename(filename)
            
            entries = parse_bib_file(file_path)
            print(f"  [INFO] {filename}: 解析到 {len(entries)} 个条目")
            
            for entry in entries:
                result = build_paperinfo_record(entry, folder_name, file_year)
                if not result:
                    continue
                
                doi, bib_json = result
                year = bib_json.get('year')
                
                # 插入数据库
                success, error_msg = _insert_paperinfo(conn, doi, bib_json)
                if success:
                    inserted += 1
                    if year:
                        year_counts[folder_name][year] += 1
                else:
                    # 记录失败
                    failed_records.append({
                        'doi': doi,
                        'file': os.path.join(folder_name, filename),
                        'error': error_msg or 'Unknown error'
                    })
        
        stats[folder_name] = inserted
        print(f"[OK] {folder_name}: 插入 {inserted} 条记录")
    
    # 更新contentlist_year_number
    _update_year_number_table(conn, year_counts)
    
    return stats, failed_records


def _insert_paperinfo(conn, doi: str, bib_json: Dict) -> Tuple[bool, Optional[str]]:
    """
    插入单条paperinfo记录
    
    Returns:
        (success, error_message) 元组
    """
    cursor = None
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO paperinfo (DOI, Bib)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE Bib = VALUES(Bib)
        """
        json_str = json.dumps(bib_json, ensure_ascii=False)
        cursor.execute(sql, (doi, json_str))
        conn.commit()
        return True, None
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] 插入DOI {doi} 失败: {error_msg}")
        return False, error_msg
    finally:
        if cursor:
            cursor.close()


def _update_year_number_table(conn, year_counts: Dict[str, Dict[int, int]]) -> None:
    """更新contentlist_year_number表"""
    cursor = None
    try:
        cursor = conn.cursor()
        for name, counts in year_counts.items():
            year_json = json.dumps(counts, ensure_ascii=False)
            sql = """
                INSERT INTO contentlist_year_number (Name, YearNumberJson)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE YearNumberJson = VALUES(YearNumberJson)
            """
            cursor.execute(sql, (name, year_json))
        conn.commit()
        print(f"[OK] 更新 contentlist_year_number: {len(year_counts)} 条记录")
    except Exception as e:
        print(f"[ERROR] 更新 contentlist_year_number 失败: {e}")
    finally:
        if cursor:
            cursor.close()


def build_contentlist_year_number(conn, data_dir: str) -> Dict[str, Dict[int, int]]:
    """
    仅统计年份数量（不导入paperinfo）
    用于单独更新contentlist_year_number表
    """
    if not os.path.isdir(data_dir):
        return {}
    
    year_counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    
    for folder_name in os.listdir(data_dir):
        folder_path = os.path.join(data_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        
        for filename in os.listdir(folder_path):
            if not filename.lower().endswith('.bib'):
                continue
            
            file_path = os.path.join(folder_path, filename)
            file_year = _extract_year_from_filename(filename)
            
            entries = parse_bib_file(file_path)
            for entry in entries:
                doi = entry.get('doi', '').strip()
                if not doi:
                    continue
                
                entry_year = _normalize_year(entry.get('year'))
                year = file_year or entry_year
                if year:
                    year_counts[folder_name][year] += 1
    
    # 更新数据库
    _update_year_number_table(conn, year_counts)
    
    return dict(year_counts)


def load_contentlist(conn, csv_path: str) -> Dict[str, Dict]:
    """
    从CSV加载期刊列表到contentlist表
    
    Args:
        conn: MySQL连接
        csv_path: InfoList.Paper.csv 路径
        
    Returns:
        期刊信息字典 {Name: {Full Name, Data Range, Update Date, Price}}
    """
    import csv
    
    journal_info = {}
    encodings = ("utf-8-sig", "utf-8", "gb2312")
    
    for enc in encodings:
        try:
            with open(csv_path, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get('Name') or '').strip()
                    if not name:
                        continue
                    
                    price_raw = (row.get('Price') or '').strip()
                    try:
                        price_val = int(price_raw) if price_raw else 1
                    except ValueError:
                        price_val = 1
                    
                    journal_info[name] = {
                        'Full Name': (row.get('Full Name') or '').strip(),
                        'Data Range': (row.get('Data Range') or '').strip(),
                        'Update Date': (row.get('Update Date') or '').strip(),
                        'Price': price_val,
                    }
            break
        except UnicodeDecodeError:
            continue
    
    if not journal_info:
        print(f"[ERROR] 无法读取CSV文件: {csv_path}")
        return {}
    
    # 插入数据库
    cursor = None
    try:
        cursor = conn.cursor()
        sql = """
            REPLACE INTO contentlist (Name, FullName, DataRange, UpdateDate, Price)
            VALUES (%s, %s, %s, %s, %s)
        """
        for name, info in journal_info.items():
            cursor.execute(sql, (
                name,
                info.get('Full Name', ''),
                info.get('Data Range', ''),
                info.get('Update Date', ''),
                info.get('Price', 1)
            ))
        conn.commit()
        print(f"[OK] ContentList: 导入 {len(journal_info)} 条记录")
    except Exception as e:
        print(f"[ERROR] 导入ContentList失败: {e}")
    finally:
        if cursor:
            cursor.close()
    
    return journal_info
