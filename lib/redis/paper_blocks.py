"""
文献Block存储模块
以Block为单位存储文献数据，支持高效的批量查询

Key设计:
- meta:{JournalName}:{Year} (Hash) - 文献Block
  - Field: DOI
  - Value: 压缩后的Bib字符串
- idx:doi_to_block (Hash) - DOI反向索引
  - Field: DOI
  - Value: block_key (如 "meta:NATURE:2024")
"""

import json
import zlib
from typing import Optional, Dict, List, Tuple

from .connection import get_redis_client


# DOI反向索引Key（用于O(1)查询DOI对应的block_key）
KEY_DOI_INDEX = "idx:doi_to_block"


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
    def _parse_distill_block_value(cls, value: str) -> str:
        """
        解析蒸馏Block的Value值，提取真正的bib字符串
        
        修复39: 蒸馏Block存储格式为 JSON {"bib": "...", "price": N}
        需要解析JSON提取bib字段
        
        Args:
            value: Redis中存储的原始值
            
        Returns:
            纯bib字符串
        """
        if not value:
            return ''
        
        try:
            data = json.loads(value)
            if isinstance(data, dict) and 'bib' in data:
                return data['bib']
        except (json.JSONDecodeError, TypeError):
            pass
        
        # 如果不是JSON格式或解析失败，返回原值
        return value
    
    @classmethod
    def get_block_by_key(cls, block_key: str) -> Dict[str, str]:
        """
        根据Block Key获取所有文献
        
        Args:
            block_key: 如 "meta:NATURE:2024" 或 "distill:uid:qid:index"
            
        修复29：支持 distill: 前缀的蒸馏专用Block
        修复39：解析蒸馏Block的JSON格式，提取真正的bib字符串
        """
        # 修复29/39：蒸馏专用Block直接从Redis获取，并解析JSON
        if block_key and block_key.startswith("distill:"):
            client = get_redis_client()
            if not client:
                return {}
            try:
                data = client.hgetall(block_key) or {}
                # 修复39: distill block 存储的是 JSON {"bib": "...", "price": N}
                # 需要解析JSON提取真正的bib
                return {doi: cls._parse_distill_block_value(value) for doi, value in data.items()}
            except Exception:
                return {}
        
        # meta: 格式的普通Block
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
                  compress: bool = True, update_index: bool = True) -> bool:
        """
        设置单篇文献
        
        Args:
            journal: 期刊名
            year: 年份
            doi: 文献DOI
            bib: Bib字符串
            compress: 是否压缩Bib
            update_index: 是否更新DOI反向索引
        """
        client = get_redis_client()
        if not client or not journal or not year or not doi or not bib:
            return False
        
        try:
            key = cls._key_block(journal, year)
            value = cls._compress_bib(bib) if compress else bib
            
            # 使用pipeline同时设置文献和更新索引
            pipe = client.pipeline()
            pipe.hset(key, doi, value)
            if update_index:
                pipe.hset(KEY_DOI_INDEX, doi, key)
            pipe.execute()
            # 文献Block永不过期，不设置TTL
            return True
        except Exception:
            return False
    
    @classmethod
    def set_block(cls, journal: str, year: int, papers: Dict[str, str],
                  compress: bool = True, update_index: bool = True) -> bool:
        """
        批量设置Block数据
        
        Args:
            journal: 期刊名
            year: 年份
            papers: {DOI: Bib} 字典
            compress: 是否压缩Bib
            update_index: 是否更新DOI反向索引
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
            
            # 同时更新DOI反向索引
            if update_index and papers:
                index_mapping = {doi: key for doi in papers.keys()}
                pipe.hset(KEY_DOI_INDEX, mapping=index_mapping)
            
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
        根据DOI查找文献
        
        优先使用DOI反向索引实现O(1)查询，索引不存在时回退到遍历模式
        
        Returns:
            (block_key, bib) 元组，或None
        """
        client = get_redis_client()
        if not client or not doi:
            return None
        
        try:
            # 优先从反向索引获取block_key (O(1))
            block_key = client.hget(KEY_DOI_INDEX, doi)
            if block_key:
                data = client.hget(block_key, doi)
                if data:
                    return (block_key, cls._decompress_bib(data))
            
            # 索引不存在时回退到遍历模式（兼容旧数据）
            for block_key in cls.list_blocks():
                data = client.hget(block_key, doi)
                if data:
                    # 顺便更新索引
                    try:
                        client.hset(KEY_DOI_INDEX, doi, block_key)
                    except Exception:
                        pass
                    return (block_key, cls._decompress_bib(data))
            return None
        except Exception:
            return None
    
    @classmethod
    def get_block_key_by_doi(cls, doi: str) -> Optional[str]:
        """
        根据DOI获取对应的block_key（O(1)复杂度）
        
        Args:
            doi: 文献DOI
            
        Returns:
            block_key字符串，如 "meta:NATURE:2024"，或None
        """
        client = get_redis_client()
        if not client or not doi:
            return None
        
        try:
            return client.hget(KEY_DOI_INDEX, doi)
        except Exception:
            return None
    
    @classmethod
    def batch_get_block_keys(cls, dois: List[str]) -> Dict[str, str]:
        """
        批量获取多个DOI对应的block_key（Pipeline优化）
        
        Args:
            dois: DOI列表
            
        Returns:
            {doi: block_key} 字典
        """
        client = get_redis_client()
        if not client or not dois:
            return {}
        
        try:
            pipe = client.pipeline()
            for doi in dois:
                pipe.hget(KEY_DOI_INDEX, doi)
            
            results = pipe.execute()
            
            output = {}
            for i, block_key in enumerate(results):
                if block_key:
                    output[dois[i]] = block_key
            
            return output
        except Exception as e:
            print(f"[PaperBlocks] batch_get_block_keys 失败: {e}")
            return {}
    
    @classmethod
    def build_doi_index(cls) -> int:
        """
        构建DOI反向索引
        
        遍历所有Block，为每个DOI建立到block_key的映射
        在Redis初始化时调用
        
        Returns:
            索引的DOI数量
        """
        client = get_redis_client()
        if not client:
            return 0
        
        try:
            total_count = 0
            block_keys = cls.list_blocks()
            
            # 分批处理，每批1000个Block
            batch_size = 50
            for i in range(0, len(block_keys), batch_size):
                batch_keys = block_keys[i:i + batch_size]
                pipe = client.pipeline()
                
                # 收集所有DOI和对应的block_key
                index_mapping = {}
                for block_key in batch_keys:
                    dois = client.hkeys(block_key) or []
                    for doi in dois:
                        index_mapping[doi] = block_key
                
                # 批量写入索引
                if index_mapping:
                    pipe.hset(KEY_DOI_INDEX, mapping=index_mapping)
                    pipe.execute()
                    total_count += len(index_mapping)
            
            return total_count
        except Exception as e:
            print(f"[PaperBlocks] build_doi_index 失败: {e}")
            return 0
    
    @classmethod
    def get_doi_index_size(cls) -> int:
        """获取DOI索引中的条目数量"""
        client = get_redis_client()
        if not client:
            return 0
        
        try:
            return client.hlen(KEY_DOI_INDEX) or 0
        except Exception:
            return 0
    
    # ============================================================
    # 批量获取方法 (Pipeline优化，用于下载等场景)
    # ============================================================
    
    @classmethod
    def batch_get_papers(cls, block_dois: Dict[str, List[str]]) -> Dict[str, str]:
        """
        批量获取多个Block中指定DOI的Bib数据
        
        使用Redis Pipeline一次性获取所有数据，将O(n)次网络往返优化为O(1)次
        
        修复39: 支持蒸馏Block的JSON格式解析
        
        Args:
            block_dois: {block_key: [doi1, doi2, ...]} 字典
            
        Returns:
            {doi: bib_str} 字典
        """
        client = get_redis_client()
        if not client or not block_dois:
            return {}
        
        try:
            # 构建Pipeline命令
            pipe = client.pipeline()
            
            # 记录每个命令对应的(block_key, doi)
            command_mapping: List[Tuple[str, str]] = []  # [(block_key, doi), ...]
            
            for block_key, dois in block_dois.items():
                for doi in dois:
                    pipe.hget(block_key, doi)
                    command_mapping.append((block_key, doi))
            
            # 执行所有命令
            results = pipe.execute()
            
            # 组装结果
            output: Dict[str, str] = {}
            for i, data in enumerate(results):
                if data:
                    block_key, doi = command_mapping[i]
                    # 修复39: 区分 distill: 和 meta: 前缀的数据格式
                    if block_key.startswith("distill:"):
                        # 蒸馏Block存储JSON格式 {"bib": "...", "price": N}
                        output[doi] = cls._parse_distill_block_value(data)
                    else:
                        # 普通Block存储压缩后的bib
                        output[doi] = cls._decompress_bib(data)
            
            return output
        except Exception as e:
            print(f"[PaperBlocks] batch_get_papers 失败: {e}")
            return {}
    
    @classmethod
    def batch_get_blocks(cls, block_keys: List[str]) -> Dict[str, Dict[str, str]]:
        """
        批量获取多个Block的所有数据
        
        使用Redis Pipeline一次性获取所有Block
        
        修复39: 支持蒸馏Block的JSON格式解析
        
        Args:
            block_keys: Block Key列表，如 ["meta:NATURE:2024", "meta:SCIENCE:2023"]
            
        Returns:
            {block_key: {doi: bib_str}} 嵌套字典
        """
        client = get_redis_client()
        if not client or not block_keys:
            return {}
        
        try:
            # 构建Pipeline命令
            pipe = client.pipeline()
            for block_key in block_keys:
                pipe.hgetall(block_key)
            
            # 执行所有命令
            results = pipe.execute()
            
            # 组装结果
            output: Dict[str, Dict[str, str]] = {}
            for i, data in enumerate(results):
                if data:
                    block_key = block_keys[i]
                    # 修复39: 区分 distill: 和 meta: 前缀的数据格式
                    if block_key.startswith("distill:"):
                        # 蒸馏Block存储JSON格式 {"bib": "...", "price": N}
                        output[block_key] = {
                            doi: cls._parse_distill_block_value(value) 
                            for doi, value in data.items()
                        }
                    else:
                        # 普通Block存储压缩后的bib
                        output[block_key] = {
                            doi: cls._decompress_bib(bib) 
                            for doi, bib in data.items()
                        }
            
            return output
        except Exception as e:
            print(f"[PaperBlocks] batch_get_blocks 失败: {e}")
            return {}
    
    @classmethod
    def batch_get_papers_flat(cls, block_keys: List[str], 
                              filter_dois: List[str] = None) -> Dict[str, str]:
        """
        批量获取多个Block的数据，返回扁平化的DOI->Bib映射
        
        Args:
            block_keys: Block Key列表
            filter_dois: 可选，只返回这些DOI的数据
            
        Returns:
            {doi: bib_str} 字典
        """
        blocks = cls.batch_get_blocks(block_keys)
        
        output: Dict[str, str] = {}
        filter_set = set(filter_dois) if filter_dois else None
        
        for block_key, papers in blocks.items():
            for doi, bib in papers.items():
                if filter_set is None or doi in filter_set:
                    output[doi] = bib
        
        return output

