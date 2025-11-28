"""
文献Block存储模块
以Block为单位存储文献数据，支持高效的批量查询

Key设计:
- meta:{JournalName}:{Year} (Hash) - 文献Block
  - Field: DOI
  - Value: 压缩后的Bib字符串
"""

import json
import zlib
from typing import Optional, Dict, List, Tuple

from .connection import get_redis_client


class PaperBlocks:
    """文献Block存储管理器"""
    
    @staticmethod
    def _key_block(journal: str, year: int) -> str:
        return f"meta:{journal}:{year}"
    
    @staticmethod
    def parse_block_key(block_key: str) -> Optional[Tuple[str, int]]:
        """
        解析Block Key
        
        Args:
            block_key: 如 "meta:NATURE:2024"
            
        Returns:
            (journal, year) 元组，或None
        """
        if not block_key or not block_key.startswith("meta:"):
            return None
        
        try:
            parts = block_key.split(":")
            if len(parts) >= 3:
                journal = parts[1]
                year = int(parts[-1])
                return (journal, year)
        except Exception:
            pass
        return None
    
    @staticmethod
    def _compress_bib(bib: str) -> str:
        """压缩Bib字符串"""
        try:
            compressed = zlib.compress(bib.encode('utf-8'))
            # 使用base64编码以便存储为字符串
            import base64
            return base64.b64encode(compressed).decode('ascii')
        except Exception:
            return bib  # 压缩失败则返回原文
    
    @staticmethod
    def _decompress_bib(data: str) -> str:
        """解压Bib字符串"""
        try:
            import base64
            compressed = base64.b64decode(data.encode('ascii'))
            return zlib.decompress(compressed).decode('utf-8')
        except Exception:
            return data  # 解压失败则假设是原文
    
    @classmethod
    def get_paper(cls, journal: str, year: int, doi: str) -> Optional[str]:
        """
        获取单篇文献的Bib数据
        
        Returns:
            Bib字符串，或None
        """
        client = get_redis_client()
        if not client or not journal or not year or not doi:
            return None
        
        try:
            data = client.hget(cls._key_block(journal, year), doi)
            if data:
                return cls._decompress_bib(data)
            return None
        except Exception:
            return None
    
    @classmethod
    def get_block(cls, journal: str, year: int) -> Dict[str, str]:
        """
        获取整个Block的所有文献
        
        Returns:
            {DOI: Bib} 字典
        """
        client = get_redis_client()
        if not client or not journal or not year:
            return {}
        
        try:
            data = client.hgetall(cls._key_block(journal, year)) or {}
            return {doi: cls._decompress_bib(bib) for doi, bib in data.items()}
        except Exception:
            return {}
    
    @classmethod
    def get_block_by_key(cls, block_key: str) -> Dict[str, str]:
        """
        根据Block Key获取所有文献
        
        Args:
            block_key: 如 "meta:NATURE:2024"
        """
        parsed = cls.parse_block_key(block_key)
        if not parsed:
            return {}
        return cls.get_block(parsed[0], parsed[1])
    
    @classmethod
    def get_block_dois(cls, journal: str, year: int) -> List[str]:
        """获取Block中所有DOI"""
        client = get_redis_client()
        if not client or not journal or not year:
            return []
        
        try:
            return list(client.hkeys(cls._key_block(journal, year)) or [])
        except Exception:
            return []
    
    @classmethod
    def get_block_size(cls, journal: str, year: int) -> int:
        """获取Block中的文献数量"""
        client = get_redis_client()
        if not client or not journal or not year:
            return 0
        
        try:
            return client.hlen(cls._key_block(journal, year)) or 0
        except Exception:
            return 0
    
    @classmethod
    def set_paper(cls, journal: str, year: int, doi: str, bib: str,
                  compress: bool = True) -> bool:
        """设置单篇文献"""
        client = get_redis_client()
        if not client or not journal or not year or not doi or not bib:
            return False
        
        try:
            key = cls._key_block(journal, year)
            value = cls._compress_bib(bib) if compress else bib
            client.hset(key, doi, value)
            # 文献Block永不过期，不设置TTL
            return True
        except Exception:
            return False
    
    @classmethod
    def set_block(cls, journal: str, year: int, papers: Dict[str, str],
                  compress: bool = True) -> bool:
        """
        批量设置Block数据
        
        Args:
            journal: 期刊名
            year: 年份
            papers: {DOI: Bib} 字典
            compress: 是否压缩Bib
        """
        client = get_redis_client()
        if not client or not journal or not year or not papers:
            return False
        
        try:
            key = cls._key_block(journal, year)
            if compress:
                mapping = {doi: cls._compress_bib(bib) for doi, bib in papers.items()}
            else:
                mapping = papers
            
            # 使用pipeline批量写入（文献Block永不过期）
            pipe = client.pipeline()
            pipe.delete(key)
            pipe.hset(key, mapping=mapping)
            pipe.execute()
            return True
        except Exception:
            return False
    
    @classmethod
    def block_exists(cls, journal: str, year: int) -> bool:
        """检查Block是否存在"""
        client = get_redis_client()
        if not client or not journal or not year:
            return False
        
        try:
            return client.exists(cls._key_block(journal, year)) > 0
        except Exception:
            return False
    
    @classmethod
    def delete_block(cls, journal: str, year: int) -> bool:
        """删除Block"""
        client = get_redis_client()
        if not client or not journal or not year:
            return False
        
        try:
            client.delete(cls._key_block(journal, year))
            return True
        except Exception:
            return False
    
    @classmethod
    def list_blocks(cls, pattern: str = "meta:*") -> List[str]:
        """列出所有Block Key"""
        client = get_redis_client()
        if not client:
            return []
        
        try:
            return list(client.scan_iter(match=pattern))
        except Exception:
            return []
    
    @classmethod
    def get_paper_by_doi(cls, doi: str) -> Optional[Tuple[str, str]]:
        """
        根据DOI查找文献（需要遍历，性能较低）
        
        Returns:
            (block_key, bib) 元组，或None
        """
        client = get_redis_client()
        if not client or not doi:
            return None
        
        try:
            # 遍历所有Block
            for block_key in cls.list_blocks():
                data = client.hget(block_key, doi)
                if data:
                    return (block_key, cls._decompress_bib(data))
            return None
        except Exception:
            return None

