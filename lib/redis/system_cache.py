"""
系统元数据缓存模块
管理标签、期刊信息等系统级数据的Redis缓存

Key设计:
- sys:tags:info               (Hash) - 标签元数据，Field=标签名，Value=类型
- sys:tag_journals:{Tag}      (Set)  - 标签-期刊反向索引
- sys:journals:info           (Hash) - 期刊基础信息，Field=期刊名，Value=JSON
- sys:journals:price          (Hash) - 期刊价格表，Field=期刊名，Value=价格
- sys:year_number:{Name}      (String) - 期刊年份统计JSON
"""

import json
from typing import Optional, Dict, List, Set, Any

from .connection import get_redis_client


class SystemCache:
    """系统元数据缓存管理器"""
    
    KEY_TAGS_INFO = "sys:tags:info"
    KEY_JOURNALS_INFO = "sys:journals:info"
    KEY_JOURNALS_PRICE = "sys:journals:price"
    
    @staticmethod
    def _key_tag_journals(tag: str) -> str:
        return f"sys:tag_journals:{tag}"
    
    @staticmethod
    def _key_year_number(name: str) -> str:
        return f"sys:year_number:{name}"
    
    # ==================== 标签数据 ====================
    
    @classmethod
    def get_all_tags(cls) -> Dict[str, str]:
        """
        获取所有标签及其类型
        
        Returns:
            {tag_name: tag_type} 字典
        """
        client = get_redis_client()
        if not client:
            return {}
        
        try:
            return client.hgetall(cls.KEY_TAGS_INFO) or {}
        except Exception:
            return {}
    
    @classmethod
    def get_tag_type(cls, tag: str) -> Optional[str]:
        """获取单个标签的类型"""
        client = get_redis_client()
        if not client or not tag:
            return None
        
        try:
            return client.hget(cls.KEY_TAGS_INFO, tag)
        except Exception:
            return None
    
    @classmethod
    def set_tags(cls, tags: Dict[str, str]) -> bool:
        """
        批量设置标签数据
        
        Args:
            tags: {tag_name: tag_type} 字典
        """
        client = get_redis_client()
        if not client or not tags:
            return False
        
        try:
            client.delete(cls.KEY_TAGS_INFO)
            client.hset(cls.KEY_TAGS_INFO, mapping=tags)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_journals_by_tag(cls, tag: str) -> Set[str]:
        """
        获取指定标签下的所有期刊
        
        Args:
            tag: 标签名
            
        Returns:
            期刊名集合
        """
        client = get_redis_client()
        if not client or not tag:
            return set()
        
        try:
            return client.smembers(cls._key_tag_journals(tag)) or set()
        except Exception:
            return set()
    
    @classmethod
    def set_tag_journals(cls, tag: str, journals: Set[str]) -> bool:
        """设置标签对应的期刊集合"""
        client = get_redis_client()
        if not client or not tag:
            return False
        
        try:
            key = cls._key_tag_journals(tag)
            client.delete(key)
            if journals:
                client.sadd(key, *journals)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_journals_intersection(cls, tags: List[str]) -> Set[str]:
        """
        获取多个标签的期刊交集
        
        Args:
            tags: 标签列表
            
        Returns:
            期刊名交集
        """
        client = get_redis_client()
        if not client or not tags:
            return set()
        
        try:
            keys = [cls._key_tag_journals(t) for t in tags]
            return client.sinter(keys) or set()
        except Exception:
            return set()
    
    # ==================== 期刊数据 ====================
    
    @classmethod
    def get_journal_info(cls, name: str) -> Optional[Dict]:
        """获取单个期刊的详细信息"""
        client = get_redis_client()
        if not client or not name:
            return None
        
        try:
            data = client.hget(cls.KEY_JOURNALS_INFO, name)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None
    
    @classmethod
    def get_all_journals(cls) -> Dict[str, Dict]:
        """获取所有期刊信息"""
        client = get_redis_client()
        if not client:
            return {}
        
        try:
            data = client.hgetall(cls.KEY_JOURNALS_INFO) or {}
            return {k: json.loads(v) for k, v in data.items()}
        except Exception:
            return {}
    
    @classmethod
    def set_journals(cls, journals: Dict[str, Dict]) -> bool:
        """
        批量设置期刊信息
        
        Args:
            journals: {name: {FullName, DataRange, ...}} 字典
        """
        client = get_redis_client()
        if not client or not journals:
            return False
        
        try:
            mapping = {k: json.dumps(v, ensure_ascii=False) for k, v in journals.items()}
            client.delete(cls.KEY_JOURNALS_INFO)
            client.hset(cls.KEY_JOURNALS_INFO, mapping=mapping)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_journal_price(cls, name: str) -> Optional[int]:
        """获取期刊单价"""
        client = get_redis_client()
        if not client or not name:
            return None
        
        try:
            val = client.hget(cls.KEY_JOURNALS_PRICE, name)
            return int(val) if val else None
        except Exception:
            return None
    
    @classmethod
    def get_all_prices(cls) -> Dict[str, int]:
        """获取所有期刊价格"""
        client = get_redis_client()
        if not client:
            return {}
        
        try:
            data = client.hgetall(cls.KEY_JOURNALS_PRICE) or {}
            return {k: int(v) for k, v in data.items()}
        except Exception:
            return {}
    
    @classmethod
    def set_prices(cls, prices: Dict[str, int]) -> bool:
        """批量设置期刊价格"""
        client = get_redis_client()
        if not client or not prices:
            return False
        
        try:
            mapping = {k: str(v) for k, v in prices.items()}
            client.delete(cls.KEY_JOURNALS_PRICE)
            client.hset(cls.KEY_JOURNALS_PRICE, mapping=mapping)
            return True
        except Exception:
            return False
    
    # ==================== 年份统计 ====================
    
    @classmethod
    def get_year_number(cls, name: str) -> Optional[Dict[int, int]]:
        """
        获取期刊各年份文献数量
        
        Args:
            name: 期刊名
            
        Returns:
            {year: count} 字典
        """
        client = get_redis_client()
        if not client or not name:
            return None
        
        try:
            data = client.get(cls._key_year_number(name))
            if data:
                raw = json.loads(data)
                return {int(k): int(v) for k, v in raw.items()}
            return None
        except Exception:
            return None
    
    @classmethod
    def set_year_number(cls, name: str, year_counts: Dict[int, int]) -> bool:
        """设置期刊年份统计"""
        client = get_redis_client()
        if not client or not name:
            return False
        
        try:
            data = json.dumps(year_counts, ensure_ascii=False)
            client.set(cls._key_year_number(name), data)
            return True
        except Exception:
            return False
    
    @classmethod
    def batch_set_year_numbers(cls, data: Dict[str, Dict[int, int]]) -> bool:
        """批量设置年份统计"""
        client = get_redis_client()
        if not client or not data:
            return False
        
        try:
            pipe = client.pipeline()
            for name, year_counts in data.items():
                json_str = json.dumps(year_counts, ensure_ascii=False)
                pipe.set(cls._key_year_number(name), json_str)
            pipe.execute()
            return True
        except Exception:
            return False

