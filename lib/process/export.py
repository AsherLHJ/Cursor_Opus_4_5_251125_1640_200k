"""
结果导出模块 (新架构)
负责将查询结果导出为BIB和CSV格式

新架构变更:
- 使用 query_id 代替 query_index
- 使用 search_dao 的 fetch_results_with_paperinfo
"""

import re
from typing import Optional
from ..load_data import db_reader
from ..load_data.query_dao import get_query_log
from ..load_data.search_dao import fetch_results_with_paperinfo


def export_results_from_db(query_id: str, 
                          bib_out_path: str, csv_out_path: str):
    """
    从数据库导出查询结果
    生成BIB和CSV文件
    
    Args:
        query_id: 查询ID
        bib_out_path: BIB输出文件路径
        csv_out_path: CSV输出文件路径
    """
    # 读取查询信息
    query_info = get_query_log(query_id) if query_id else {}
    
    # 构建header
    header = {}
    if query_info:
        search_params = query_info.get('search_params', {})
        header = {
            'query_time': str(query_info.get('start_time', '')),
            'selected_folders': ', '.join(search_params.get('selected_journals', [])),
            'year_range': search_params.get('year_range', 'All years'),
            'research_question': search_params.get('research_question', ''),
            'requirements': search_params.get('requirements', ''),
        }

    # 读取结果数据
    rows = fetch_results_with_paperinfo(query_id) if query_id else []

    # 导出BIB文件
    export_bib(bib_out_path, header, rows)
    
    # 导出CSV文件
    export_csv(csv_out_path, rows)


def export_bib(filepath: str, header: dict, rows: list):
    """导出BIB格式文件（修复36补充：移除所有头信息，只输出BIB条目）"""
    with open(filepath, 'w', encoding='utf-8') as f:
        # 只输出相关条目（不输出任何头信息）
        entries = []
        for r in rows:
            if r.get('search_result') in (1, True, '1', 'Y', 'y'):
                bib_text = r.get('bib', '')
                if bib_text.strip():
                    entries.append(bib_text.strip())
        
        if entries:
            f.write('\n\n'.join(entries))
            f.write('\n')


def export_csv(filepath: str, rows: list):
    """导出CSV格式文件"""
    with open(filepath, 'w', encoding='gbk', newline='') as f:
        # 写入表头
        f.write('"Title","Source","Relevance","Reason","URL"\n')
        
        # 先输出相关条目，再输出不相关条目
        rows_sorted = (
            [r for r in rows if r.get('search_result') in (1, True, '1', 'Y', 'y')] +
            [r for r in rows if r.get('search_result') not in (1, True, '1', 'Y', 'y')]
        )
        
        for r in rows_sorted:
            title = (r.get('title', '') or '').replace('"', '""')
            source = r.get('source', 'Unknown')
            relevance = 'Y' if r.get('search_result') in (1, True, '1', 'Y', 'y') else 'N'
            reason = (r.get('reason', '') or '').replace('"', '""')
            
            # 提取URL
            url = extract_url_from_entry(r.get('bib', ''))
            if not url:
                doi = r.get('doi', '')
                if doi:
                    url = f"https://doi.org/{doi}"
            
            f.write(f'"{title}","{source}","{relevance}","{reason}","{url}"\n')


def extract_url_from_entry(entry: str) -> str:
    """从BibTeX条目中提取URL"""
    if not entry:
        return ""
    
    try:
        # 优先匹配url字段
        m = re.search(r'(?mi)^\s*url\s*=\s*[{"]([^}"]+)[}"]', entry)
        if m:
            return m.group(1).strip().rstrip(',')
        
        # 其次匹配doi字段
        m = re.search(r'(?mi)^\s*doi\s*=\s*[{"]([^}"]+)[}"]', entry)
        if m:
            doi = m.group(1).strip().rstrip(',')
            if doi.lower().startswith('http'):
                return doi
            return f"https://doi.org/{doi}"
            
    except Exception:
        pass
    
    return ""
