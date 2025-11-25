"""
结果导出模块
负责将查询结果导出为BIB和CSV格式
"""

import re
from typing import Optional
from ..load_data import db_reader


def export_results_from_db(search_table_name: str, query_index: int, 
                          bib_out_path: str, csv_out_path: str):
    """
    从数据库导出查询结果
    生成BIB和CSV文件
    """
    # 读取查询信息
    header = db_reader.get_query_log_by_index(query_index) if query_index else {}
    query_time = header.get('query_time', '')
    selected_folders = header.get('selected_folders', '')
    year_range = header.get('year_range', '')
    research_question = header.get('research_question', '')
    requirements = header.get('requirements', '')

    # 读取结果数据
    rows = db_reader.fetch_search_results_with_paperinfo(search_table_name, query_index)

    # 导出BIB文件
    export_bib(bib_out_path, header, rows)
    
    # 导出CSV文件
    export_csv(csv_out_path, rows)


def export_bib(filepath: str, header: dict, rows: list):
    """导出BIB格式文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        # 写入文件头
        if header:
            f.write(f"% Query Time: {header.get('query_time', '')}\n")
            f.write(f"% Selected Folders: {header.get('selected_folders', '')}\n")
            f.write(f"% Year Range: {header.get('year_range', '')}\n")
            f.write(f"% Research Question: {header.get('research_question', '')}\n")
            
            requirements = header.get('requirements', '')
            if requirements:
                f.write(f"% Requirements: {requirements}\n")
            
            f.write(f"\n% Search Topic {{{header.get('research_question', '')}}}\n\n")
        
        # 只输出相关条目
        for r in rows:
            if r.get('search_result') in (1, True, '1'):
                bib_text = r.get('bib', '')
                if bib_text.strip():
                    f.write(bib_text)
                    f.write('\n\n')


def export_csv(filepath: str, rows: list):
    """导出CSV格式文件"""
    with open(filepath, 'w', encoding='gbk', newline='') as f:
        # 写入表头
        f.write('"Title","Source","Relevance","Reason","URL"\n')
        
        # 先输出相关条目，再输出不相关条目
        rows_sorted = (
            [r for r in rows if r.get('search_result') in (1, True, '1')] +
            [r for r in rows if r.get('search_result') not in (1, True, '1')]
        )
        
        for r in rows_sorted:
            title = (r.get('title', '') or '').replace('"', '""')
            source = r.get('source', 'Unknown')
            relevance = 'Y' if r.get('search_result') in (1, True, '1') else 'N'
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
