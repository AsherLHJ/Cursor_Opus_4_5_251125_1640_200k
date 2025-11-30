"""
搜索结果数据访问对象 (新架构)
管理 search_result 表的操作

新架构变更:
- 废弃动态 search_YYYYMMDD 表，使用统一的 search_result 表
- 实时结果存储在 Redis: result:{uid}:{qid}
- MySQL search_result 表仅用于归档（异步写入）
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from .db_base import _get_connection
from ..redis.result_cache import ResultCache
from ..redis.connection import redis_ping


def _parse_bib_fields(bib_str: str) -> Dict[str, str]:
    """
    从Bib字符串提取title、url等字段
    
    Args:
        bib_str: BibTeX格式字符串
        
    Returns:
        {'title': '...', 'url': '...'}
    """
    result = {'title': '', 'url': ''}
    
    if not bib_str:
        return result
    
    try:
        # 提取title（支持花括号和引号）
        title_match = re.search(
            r'title\s*=\s*[{"](.+?)[}"]',
            bib_str, re.IGNORECASE | re.DOTALL
        )
        if title_match:
            result['title'] = title_match.group(1).strip()
        
        # 提取url
        url_match = re.search(
            r'url\s*=\s*[{"]([^}"]+)[}"]',
            bib_str, re.IGNORECASE
        )
        if url_match:
            result['url'] = url_match.group(1).strip()
    except Exception:
        pass
    
    return result


def save_result(uid: int, query_id: str, doi: str, 
                ai_result: Dict, block_key: str = None) -> bool:
    """
    保存单条搜索结果到 Redis
    
    Args:
        uid: 用户ID
        query_id: 查询ID
        doi: 文献DOI
        ai_result: AI分析结果 {relevant: "Y"/"N", reason: "..."}
        block_key: 所属Block Key
    """
    return ResultCache.set_result(uid, query_id, doi, ai_result, block_key)


def get_result(uid: int, query_id: str, doi: str) -> Optional[Dict]:
    """获取单条搜索结果"""
    return ResultCache.get_result(uid, query_id, doi)


def get_all_results(uid: int, query_id: str) -> Dict[str, Dict]:
    """
    获取查询的所有结果
    
    优先从 Redis 读取，未命中则从 MySQL 读取
    """
    # 优先从 Redis
    if redis_ping():
        cached = ResultCache.get_all_results(uid, query_id)
        if cached:
            return cached
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT doi, ai_result
            FROM search_result 
            WHERE uid = %s AND query_id = %s
        """, (uid, query_id))
        
        results = {}
        for row in cursor.fetchall():
            doi = row['doi']
            ai_result = row['ai_result']
            if isinstance(ai_result, str):
                try:
                    ai_result = json.loads(ai_result)
                except Exception:
                    pass
            results[doi] = {'ai_result': ai_result}
        
        cursor.close()
        return results
    finally:
        conn.close()


def get_relevant_dois(uid: int, query_id: str) -> List[str]:
    """获取所有判定为相关的DOI"""
    return ResultCache.get_relevant_dois(uid, query_id)


def get_result_count(uid: int, query_id: str) -> int:
    """获取结果数量"""
    if redis_ping():
        count = ResultCache.get_result_count(uid, query_id)
        if count > 0:
            return count
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM search_result WHERE uid = %s AND query_id = %s",
            (uid, query_id)
        )
        row = cursor.fetchone()
        cursor.close()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def archive_results_to_mysql(uid: int, query_id: str) -> int:
    """
    将 Redis 中的结果归档到 MySQL
    
    仅在查询状态变为 DONE 时调用（异步归档）
    
    Returns:
        归档的记录数
    """
    if not redis_ping():
        return 0
    
    results = ResultCache.get_all_results(uid, query_id)
    if not results:
        return 0
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        archived = 0
        
        for doi, data in results.items():
            ai_result = data.get('ai_result', {})
            try:
                cursor.execute("""
                    INSERT INTO search_result (uid, query_id, doi, ai_result)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE ai_result = VALUES(ai_result)
                """, (
                    uid,
                    query_id,
                    doi,
                    json.dumps(ai_result, ensure_ascii=False)
                ))
                archived += 1
            except Exception as e:
                print(f"[SearchDAO] 归档结果失败 {doi}: {e}")
        
        conn.commit()
        cursor.close()
        
        print(f"[SearchDAO] 归档完成: {query_id} -> {archived} 条记录")
        return archived
    finally:
        conn.close()


def fetch_results_with_paperinfo(uid: int, query_id: str, 
                                  only_relevant: bool = False) -> List[Dict]:
    """
    获取查询结果及对应的文献信息（扁平化结构）
    
    使用 Redis Pipeline 批量获取优化，将 O(n) 次网络往返优化为 O(1) 次
    
    用于下载 CSV/Bib 文件
    
    Args:
        uid: 用户ID
        query_id: 查询ID
        only_relevant: 是否只返回相关的结果
        
    Returns:
        扁平化的结果列表，每个元素包含:
        - doi: 文献DOI
        - search_result: 'Y' 或 'N'（相关性判断）
        - reason: 判断理由
        - source: 期刊名
        - year: 发表年份
        - title: 论文标题
        - bib: 完整bib字符串
        - paper_url: 论文URL
    """
    from .paper_dao import get_paper_by_doi
    from ..redis.paper_blocks import PaperBlocks
    
    results = get_all_results(uid, query_id)
    if not results:
        return []
    
    # ========================================
    # 第一遍：收集所有 block_key -> [dois] 映射
    # ========================================
    block_dois: Dict[str, List[str]] = {}  # {block_key: [doi1, doi2, ...]}
    doi_metadata: Dict[str, Dict] = {}     # {doi: {ai_result, block_key, source, year, ...}}
    
    for doi, data in results.items():
        ai_result = data.get('ai_result', {})
        
        # 提取相关性判断（支持多种格式）
        if isinstance(ai_result, dict):
            relevant = ai_result.get('relevant', 'N')
            reason = ai_result.get('reason', '')
        else:
            relevant = 'Y' if ai_result in (True, 1, '1', 'Y', 'y') else 'N'
            reason = ''
        
        # 标准化 search_result 字段
        search_result = 'Y' if str(relevant).upper() in ('Y', 'YES', '1', 'TRUE') else 'N'
        
        # 过滤非相关结果
        if only_relevant and search_result != 'Y':
            continue
        
        # 收集 block_key
        block_key = data.get('block_key', '')
        source = ''
        year = ''
        
        if block_key:
            parsed = PaperBlocks.parse_block_key(block_key)
            if parsed:
                source, year = parsed
                # 添加到 block_dois 映射
                if block_key not in block_dois:
                    block_dois[block_key] = []
                block_dois[block_key].append(doi)
        
        # 保存元数据
        doi_metadata[doi] = {
            'search_result': search_result,
            'reason': reason,
            'source': str(source),
            'year': str(year),
            'block_key': block_key,
        }
    
    # ========================================
    # 批量获取所有 Bib 数据 (Pipeline优化)
    # ========================================
    all_bibs: Dict[str, str] = {}
    
    if block_dois and redis_ping():
        # 使用 Pipeline 批量获取
        all_bibs = PaperBlocks.batch_get_papers(block_dois)
    
    # ========================================
    # 第二遍：组装结果
    # ========================================
    output = []
    missing_dois = []  # 需要从数据库回退的DOI
    
    for doi, meta in doi_metadata.items():
        bib_str = all_bibs.get(doi, '')
        
        if not bib_str:
            # 记录需要从数据库获取的DOI
            missing_dois.append(doi)
            continue
        
        # 从bib解析title和url
        bib_fields = _parse_bib_fields(bib_str)
        title = bib_fields.get('title', '')
        paper_url = bib_fields.get('url', '')
        
        # 如果没有url，从doi生成
        if not paper_url and doi:
            paper_url = f"https://doi.org/{doi}"
        
        output.append({
            'doi': doi,
            'search_result': meta['search_result'],
            'reason': meta['reason'],
            'source': meta['source'],
            'year': meta['year'],
            'title': title,
            'bib': bib_str,
            'paper_url': paper_url,
        })
    
    # ========================================
    # 处理需要从数据库回退的DOI
    # ========================================
    for doi in missing_dois:
        meta = doi_metadata[doi]
        paper_info = get_paper_by_doi(doi)
        
        if paper_info:
            source = paper_info.get('name', '') or paper_info.get('source', '') or meta['source']
            year = paper_info.get('year', '') or meta['year']
            bib_str = paper_info.get('bib', '')
        else:
            source = meta['source']
            year = meta['year']
            bib_str = ''
        
        # 从bib解析title和url
        bib_fields = _parse_bib_fields(bib_str)
        title = bib_fields.get('title', '')
        paper_url = bib_fields.get('url', '')
        
        # 如果没有url，从doi生成
        if not paper_url and doi:
            paper_url = f"https://doi.org/{doi}"
        
        output.append({
            'doi': doi,
            'search_result': meta['search_result'],
            'reason': meta['reason'],
            'source': source,
            'year': year,
            'title': title,
            'bib': bib_str,
            'paper_url': paper_url,
        })
    
    return output


def delete_results(uid: int, query_id: str) -> bool:
    """删除查询的所有结果（Redis + MySQL）"""
    # 删除 Redis 缓存
    if redis_ping():
        ResultCache.delete_results(uid, query_id)
    
    # 删除 MySQL 记录
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM search_result WHERE uid = %s AND query_id = %s",
            (uid, query_id)
        )
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"[SearchDAO] 删除结果失败: {e}")
        return False
    finally:
        conn.close()


def result_exists(uid: int, query_id: str, doi: str) -> bool:
    """检查某篇文献是否已有结果"""
    return ResultCache.result_exists(uid, query_id, doi)
