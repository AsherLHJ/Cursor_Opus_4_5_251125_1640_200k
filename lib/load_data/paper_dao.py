"""
文献数据访问对象 (新架构)
适配新的 paperinfo 表结构 (仅 DOI, Bib 两列)

新架构数据流:
- MySQL paperinfo: 仅存储 DOI 和完整 Bib JSON
- Redis Block: meta:{Journal}:{Year} (Hash) 存储按刊物年份分组的文献
"""

import json
from typing import List, Dict, Optional, Any, Iterator
from .db_base import _get_connection
from ..redis.paper_blocks import PaperBlocks
from ..redis.connection import redis_ping


def get_paper_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    """
    根据 DOI 获取文献信息
    
    Returns:
        包含 doi, name, year, title, author, abstract, bib 的字典
    """
    if not doi:
        return None
    
    # 1. 优先从 Redis Block 查找
    if redis_ping():
        result = PaperBlocks.get_paper_by_doi(doi)
        if result:
            block_key, bib_str = result
            return _parse_bib_to_dict(doi, bib_str, block_key)
    
    # 2. 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DOI, Bib FROM paperinfo WHERE DOI = %s", (doi,))
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            return None
        
        doi_val, bib_data = row
        return _parse_paperinfo_row(doi_val, bib_data)
    finally:
        conn.close()


def _parse_paperinfo_row(doi: str, bib_data: Any) -> Dict[str, Any]:
    """解析 paperinfo 表的行数据"""
    try:
        if isinstance(bib_data, str):
            bib_obj = json.loads(bib_data)
        else:
            bib_obj = bib_data or {}
        
        return {
            'doi': doi,
            'name': bib_obj.get('name', ''),
            'year': bib_obj.get('year'),
            'title': bib_obj.get('title', ''),
            'author': bib_obj.get('author', ''),
            'abstract': bib_obj.get('abstract', ''),
            'bib': bib_obj.get('bib', ''),
            'url': bib_obj.get('url', ''),
        }
    except Exception:
        return {'doi': doi}


def _parse_bib_to_dict(doi: str, bib_str: str, block_key: str = None) -> Dict[str, Any]:
    """从 BibTeX 字符串解析出结构化数据"""
    result = {
        'doi': doi,
        'bib': bib_str,
        'block_key': block_key,
    }
    
    # 从 block_key 提取期刊和年份
    if block_key:
        parsed = PaperBlocks.parse_block_key(block_key)
        if parsed:
            result['name'] = parsed[0]
            result['year'] = parsed[1]
    
    # 简单解析 BibTeX 提取字段
    try:
        import re
        
        # 提取 title
        title_match = re.search(r'title\s*=\s*[{"]([^}"]+)[}"]', bib_str, re.IGNORECASE)
        if title_match:
            result['title'] = title_match.group(1).strip()
        
        # 提取 author
        author_match = re.search(r'author\s*=\s*[{"]([^}"]+)[}"]', bib_str, re.IGNORECASE)
        if author_match:
            result['author'] = author_match.group(1).strip()
        
        # 提取 abstract
        abstract_match = re.search(r'abstract\s*=\s*[{"]([^}"]+)[}"]', bib_str, re.IGNORECASE)
        if abstract_match:
            result['abstract'] = abstract_match.group(1).strip()
        
    except Exception:
        pass
    
    return result


def get_papers_by_block(journal: str, year: int) -> Dict[str, str]:
    """
    获取指定 Block 的所有文献
    
    Args:
        journal: 期刊名
        year: 年份
        
    Returns:
        {DOI: Bib字符串} 字典
    """
    # 优先从 Redis
    if redis_ping():
        cached = PaperBlocks.get_block(journal, year)
        if cached:
            return cached
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DOI, Bib FROM paperinfo")
        
        result = {}
        for doi, bib_data in cursor.fetchall():
            try:
                if isinstance(bib_data, str):
                    bib_obj = json.loads(bib_data)
                else:
                    bib_obj = bib_data or {}
                
                if bib_obj.get('name') == journal and bib_obj.get('year') == year:
                    result[doi] = bib_obj.get('bib', '')
            except Exception:
                continue
        
        cursor.close()
        
        # 写入 Redis Block
        if redis_ping() and result:
            PaperBlocks.set_block(journal, year, result)
        
        return result
    finally:
        conn.close()


def get_block_dois(journal: str, year: int) -> List[str]:
    """获取 Block 中所有 DOI"""
    if redis_ping():
        return PaperBlocks.get_block_dois(journal, year)
    
    papers = get_papers_by_block(journal, year)
    return list(papers.keys())


def get_paper_title_abstract_by_doi(doi: str) -> Optional[Dict[str, str]]:
    """获取文献的标题和摘要"""
    paper = get_paper_by_doi(doi)
    if paper:
        return {
            'title': paper.get('title', ''),
            'abstract': paper.get('abstract', ''),
        }
    return None


def fetch_papers_by_dois(doi_list: List[str]) -> List[Dict]:
    """
    批量获取多篇文献信息
    """
    if not doi_list:
        return []
    
    result = []
    for doi in doi_list:
        paper = get_paper_by_doi(doi)
        if paper:
            result.append(paper)
    
    return result


def count_papers_by_journals(journal_names: List[str], 
                             time_range: Dict = None) -> Dict[str, int]:
    """
    统计每个期刊的论文数量
    
    新架构使用 contentlist_year_number 表
    """
    if not journal_names:
        return {}
    
    from .journal_dao import get_year_number
    
    start_year = None
    end_year = None
    if time_range and not time_range.get("include_all", True):
        start_year = time_range.get("start_year")
        end_year = time_range.get("end_year")
    
    result = {}
    for name in journal_names:
        year_counts = get_year_number(name)
        if year_counts:
            if start_year and end_year:
                count = sum(c for y, c in year_counts.items() 
                           if start_year <= y <= end_year)
            else:
                count = sum(year_counts.values())
            result[name] = count
        else:
            result[name] = 0
    
    return result


def paper_exists(doi: str) -> bool:
    """检查文献是否存在"""
    if not doi:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM paperinfo WHERE DOI = %s LIMIT 1", (doi,))
        result = cursor.fetchone() is not None
        cursor.close()
        return result
    finally:
        conn.close()


def get_total_paper_count() -> int:
    """获取文献总数"""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM paperinfo")
        row = cursor.fetchone()
        cursor.close()
        return int(row[0]) if row else 0
    finally:
        conn.close()
