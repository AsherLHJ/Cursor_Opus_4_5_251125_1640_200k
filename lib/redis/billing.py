"""
计费队列模块
实现Redis实时扣费+异步流水对账机制

Key设计:
- billing_queue:{uid} (List) - 消费流水队列
  - Value: JSON {timestamp, qid, doi, cost}
"""

import json
import time
from typing import Optional, Dict, List, Any

from .connection import get_redis_client


class BillingQueue:
    """计费队列管理器"""
    
    @staticmethod
    def _key_billing(uid: int) -> str:
        return f"billing_queue:{uid}"
    
    @classmethod
    def push_billing_record(cls, uid: int, qid: str, doi: str, cost: float) -> bool:
        """
        推送计费记录到队列
        
        Args:
            uid: 用户ID
            qid: 查询ID
            doi: 文献DOI
            cost: 扣费金额
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            record = {
                'timestamp': time.time(),
                'qid': qid,
                'doi': doi,
                'cost': cost,
            }
            client.rpush(cls._key_billing(uid), json.dumps(record))
            return True
        except Exception:
            return False
    
    @classmethod
    def pop_billing_records(cls, uid: int, count: int = 100) -> List[Dict]:
        """
        从队列头部弹出计费记录（LPOP）
        
        Args:
            uid: 用户ID
            count: 最大弹出数量
            
        Returns:
            计费记录列表
        """
        client = get_redis_client()
        if not client or uid <= 0 or count <= 0:
            return []
        
        records = []
        try:
            for _ in range(count):
                data = client.lpop(cls._key_billing(uid))
                if not data:
                    break
                records.append(json.loads(data))
            return records
        except Exception:
            return records
    
    @classmethod
    def peek_billing_records(cls, uid: int, count: int = 100) -> List[Dict]:
        """
        查看队列头部的计费记录（不弹出）
        
        Args:
            uid: 用户ID
            count: 最大查看数量
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return []
        
        try:
            data_list = client.lrange(cls._key_billing(uid), 0, count - 1) or []
            return [json.loads(d) for d in data_list]
        except Exception:
            return []
    
    @classmethod
    def get_queue_length(cls, uid: int) -> int:
        """获取队列长度"""
        client = get_redis_client()
        if not client or uid <= 0:
            return 0
        
        try:
            return client.llen(cls._key_billing(uid)) or 0
        except Exception:
            return 0
    
    @classmethod
    def trim_queue(cls, uid: int, keep_count: int) -> bool:
        """
        截断队列（保留头部keep_count条记录）
        用于BillingSyncer同步成功后删除已处理的记录
        
        Args:
            uid: 用户ID
            keep_count: 保留的记录数（从尾部开始）
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            # LTRIM保留从keep_count到末尾的元素
            # 即删除前keep_count个元素
            if keep_count <= 0:
                return True
            client.ltrim(cls._key_billing(uid), keep_count, -1)
            return True
        except Exception:
            return False
    
    @classmethod
    def clear_queue(cls, uid: int) -> bool:
        """清空队列"""
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            client.delete(cls._key_billing(uid))
            return True
        except Exception:
            return False
    
    @classmethod
    def get_all_active_billing_queues(cls) -> List[int]:
        """
        获取所有有待处理计费记录的用户ID
        
        Returns:
            用户ID列表
        """
        client = get_redis_client()
        if not client:
            return []
        
        try:
            uids = []
            for key in client.scan_iter(match="billing_queue:*"):
                try:
                    uid_str = key.split(":")[-1]
                    uid = int(uid_str)
                    if client.llen(key) > 0:
                        uids.append(uid)
                except (ValueError, IndexError):
                    continue
            return uids
        except Exception:
            return []
    
    @classmethod
    def calculate_total_cost(cls, records: List[Dict]) -> float:
        """计算一批记录的总费用"""
        total = 0.0
        for record in records:
            try:
                cost = float(record.get('cost', 0))
                total += cost
            except (TypeError, ValueError):
                continue
        return total

