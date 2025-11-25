"""
搜索结果数据访问对象 (新架构)
管理 search_result 表的操作

新架构变更:
- 废弃动态 search_YYYYMMDD 表，使用统一的 search_result 表
- 实时结果存储在 Redis: result:{uid}:{qid}
- MySQL search_result 表仅用于归档（异步写入）
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from .db_base import _get_connection
from ..redis.result_cache import ResultCache
from ..redis.connection import redis_ping


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
    获取查询结果及对应的文献信息
    
    用于下载 CSV/Bib 文件
    
    Args:
        uid: 用户ID
        query_id: 查询ID
        only_relevant: 是否只返回相关的结果
    """
    from .paper_dao import get_paper_by_doi
    from ..redis.paper_blocks import PaperBlocks
    
    results = get_all_results(uid, query_id)
    if not results:
        return []
    
    output = []
    for doi, data in results.items():
        ai_result = data.get('ai_result', {})
        
        # 过滤非相关结果
        if only_relevant:
            is_relevant = False
            if isinstance(ai_result, dict):
                is_relevant = ai_result.get('relevant', '').upper() == 'Y'
            elif ai_result in (True, 1, '1', 'Y', 'y'):
                is_relevant = True
            
            if not is_relevant:
                continue
        
        # 获取文献信息
        block_key = data.get('block_key', '')
        paper_info = None
        
        # 优先从 Block 获取
        if block_key and redis_ping():
            parsed = PaperBlocks.parse_block_key(block_key)
            if parsed:
                journal, year = parsed
                bib_str = PaperBlocks.get_block(journal, year).get(doi)
                if bib_str:
                    paper_info = {
                        'doi': doi,
                        'name': journal,
                        'year': year,
                        'bib': bib_str,
                    }
        
        # 回退到数据库
        if not paper_info:
            paper_info = get_paper_by_doi(doi) or {'doi': doi}
        
        output.append({
            'doi': doi,
            'ai_result': ai_result,
            'paper_info': paper_info,
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
