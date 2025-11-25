"""
标签与映射导入模块
负责加载info_tag和info_paper_with_tag表数据
"""

import csv
import os
from typing import Dict, List, Set, Tuple


def load_tags_data(conn, info_tag_csv: str, paper_with_tag_csv: str) -> Tuple[int, int]:
    """
    加载标签和标签映射数据
    
    Args:
        conn: MySQL连接
        info_tag_csv: InfoList.Tag.csv 路径
        paper_with_tag_csv: InfoList.PaperWithTag.csv 路径
        
    Returns:
        (tag_count, mapping_count) 元组
    """
    tag_count = _load_info_tag(conn, info_tag_csv)
    mapping_count = _load_paper_with_tag(conn, paper_with_tag_csv)
    return tag_count, mapping_count


def _load_info_tag(conn, csv_path: str) -> int:
    """加载标签表"""
    if not os.path.exists(csv_path):
        print(f"[ERROR] 标签文件不存在: {csv_path}")
        return 0
    
    tags: List[Tuple[str, str]] = []
    encodings = ("utf-8-sig", "utf-8", "gb2312")
    
    for enc in encodings:
        try:
            with open(csv_path, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tag = (row.get('tag') or row.get('Tag') or '').strip()
                    tagtype = (row.get('tagtype') or row.get('TagType') or '').strip()
                    if tag and tagtype:
                        tags.append((tag, tagtype))
            break
        except UnicodeDecodeError:
            continue
    
    if not tags:
        print(f"[WARN] 未从 {csv_path} 读取到标签数据")
        return 0
    
    cursor = None
    inserted = 0
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO info_tag (Tag, TagType)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE TagType = VALUES(TagType)
        """
        for tag, tagtype in tags:
            try:
                cursor.execute(sql, (tag, tagtype))
                inserted += 1
            except Exception as e:
                print(f"[WARN] 插入标签 {tag} 失败: {e}")
        conn.commit()
        print(f"[OK] info_tag: 导入 {inserted} 条记录")
    except Exception as e:
        print(f"[ERROR] 导入info_tag失败: {e}")
    finally:
        if cursor:
            cursor.close()
    
    return inserted


def _load_paper_with_tag(conn, csv_path: str) -> int:
    """加载标签映射表"""
    if not os.path.exists(csv_path):
        print(f"[ERROR] 映射文件不存在: {csv_path}")
        return 0
    
    mappings: List[Tuple[str, str]] = []
    encodings = ("utf-8-sig", "utf-8", "gb2312")
    
    for enc in encodings:
        try:
            with open(csv_path, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get('Name') or row.get('name') or '').strip()
                    tag = (row.get('Tag') or row.get('tag') or '').strip()
                    if name and tag:
                        mappings.append((name, tag))
            break
        except UnicodeDecodeError:
            continue
    
    if not mappings:
        print(f"[WARN] 未从 {csv_path} 读取到映射数据")
        return 0
    
    cursor = None
    inserted = 0
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO info_paper_with_tag (Name, Tag)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE Name = VALUES(Name)
        """
        for name, tag in mappings:
            try:
                cursor.execute(sql, (name, tag))
                inserted += 1
            except Exception as e:
                print(f"[WARN] 插入映射 {name}-{tag} 失败: {e}")
        conn.commit()
        print(f"[OK] info_paper_with_tag: 导入 {inserted} 条记录")
    except Exception as e:
        print(f"[ERROR] 导入info_paper_with_tag失败: {e}")
    finally:
        if cursor:
            cursor.close()
    
    return inserted


def get_all_tags(conn) -> Dict[str, str]:
    """获取所有标签及其类型"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT Tag, TagType FROM info_tag")
        return {row[0]: row[1] for row in cursor.fetchall()}
    except Exception:
        return {}
    finally:
        if cursor:
            cursor.close()


def get_journals_by_tag(conn, tag: str) -> Set[str]:
    """获取指定标签下的所有期刊"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT Name FROM info_paper_with_tag WHERE Tag = %s",
            (tag,)
        )
        return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()
    finally:
        if cursor:
            cursor.close()


def get_tags_by_journal(conn, journal_name: str) -> Set[str]:
    """获取指定期刊的所有标签"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT Tag FROM info_paper_with_tag WHERE Name = %s",
            (journal_name,)
        )
        return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()
    finally:
        if cursor:
            cursor.close()

