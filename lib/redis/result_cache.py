"""
结果缓存模块
存储查询任务的AI分析结果

Key设计:
- result:{uid}:{qid} (Hash) - 查询结果
  - Field: DOI
  - Value: JSON {ai_result, block_key, ...}
"""

import json
from typing import Optional, Dict, List, Any

from .connection import get_redis_client


class ResultCache:
    """查询结果缓存管理器"""
    
    @staticmethod
    def _key_result(uid: int, qid: str) -> str:
        return f"result:{uid}:{qid}"
    
    @classmethod
    def set_result(cls, uid: int, qid: str, doi: str, 
                   ai_result: Dict, block_key: str = None) -> bool:
        """
        存储单篇文献的分析结果
        
        Args:
            uid: 用户ID
            qid: 查询ID
            doi: 文献DOI
            ai_result: AI分析结果 {relevant: "Y"/"N", reason: "..."}
            block_key: 所属Block Key（用于蒸馏时快速找到原始Bib）
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid or not doi:
            return False
        
        try:
            value = {
                'ai_result': ai_result,
                'block_key': block_key or '',
            }
            client.hset(
                cls._key_result(uid, qid),
                doi,
                json.dumps(value, ensure_ascii=False)
            )
            return True
        except Exception:
            return False
    
    @classmethod
    def get_result(cls, uid: int, qid: str, doi: str) -> Optional[Dict]:
        """获取单篇文献的分析结果"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid or not doi:
            return None
        
        try:
            data = client.hget(cls._key_result(uid, qid), doi)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None
    
    @classmethod
    def get_all_results(cls, uid: int, qid: str) -> Dict[str, Dict]:
        """
        获取查询的所有结果
        
        Returns:
            {DOI: result_dict} 字典
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return {}
        
        try:
            data = client.hgetall(cls._key_result(uid, qid)) or {}
            return {doi: json.loads(val) for doi, val in data.items()}
        except Exception:
            return {}
    
    @classmethod
    def get_relevant_dois(cls, uid: int, qid: str) -> List[str]:
        """
        获取所有判定为相关的DOI
        
        Returns:
            相关文献的DOI列表
        """
        results = cls.get_all_results(uid, qid)
        relevant = []
        
        for doi, data in results.items():
            ai_result = data.get('ai_result', {})
            if isinstance(ai_result, dict):
                if ai_result.get('relevant', '').upper() == 'Y':
                    relevant.append(doi)
            elif ai_result in (True, 1, '1', 'Y', 'y'):
                relevant.append(doi)
        
        return relevant
    
    @classmethod
    def get_result_count(cls, uid: int, qid: str) -> int:
        """获取结果数量"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return 0
        
        try:
            return client.hlen(cls._key_result(uid, qid)) or 0
        except Exception:
            return 0
    
    @classmethod
    def result_exists(cls, uid: int, qid: str, doi: str) -> bool:
        """检查某篇文献是否已有结果"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid or not doi:
            return False
        
        try:
            return client.hexists(cls._key_result(uid, qid), doi)
        except Exception:
            return False
    
    @classmethod
    def delete_results(cls, uid: int, qid: str) -> bool:
        """删除查询的所有结果"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            client.delete(cls._key_result(uid, qid))
            return True
        except Exception:
            return False
    
    @classmethod
    def batch_set_results(cls, uid: int, qid: str, 
                          results: Dict[str, Dict]) -> bool:
        """
        批量设置结果
        
        Args:
            uid: 用户ID
            qid: 查询ID
            results: {DOI: {ai_result, block_key}} 字典
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid or not results:
            return False
        
        try:
            key = cls._key_result(uid, qid)
            mapping = {
                doi: json.dumps(val, ensure_ascii=False)
                for doi, val in results.items()
            }
            client.hset(key, mapping=mapping)
            return True
        except Exception:
            return False

