"""
任务队列模块
管理查询任务的分发和执行状态

Key设计:
- task:{uid}:{qid}:pending_blocks (List) - 待处理Block队列
- query:{uid}:{qid}:status        (Hash) - 任务状态
- query:{uid}:{qid}:terminate_signal (String) - 终止信号
- progress:{uid}:{qid}:finished_count (String) - 已完成计数
"""

import json
import time
from typing import Optional, Dict, List, Any

from .connection import get_redis_client


class TaskQueue:
    """任务队列管理器"""
    
    @staticmethod
    def _key_pending(uid: int, qid: str) -> str:
        return f"task:{uid}:{qid}:pending_blocks"
    
    @staticmethod
    def _key_status(uid: int, qid: str) -> str:
        return f"query:{uid}:{qid}:status"
    
    @staticmethod
    def _key_terminate(uid: int, qid: str) -> str:
        return f"query:{uid}:{qid}:terminate_signal"
    
    @staticmethod
    def _key_progress(uid: int, qid: str) -> str:
        return f"progress:{uid}:{qid}:finished_count"
    
    # ==================== 任务队列操作 ====================
    
    @classmethod
    def enqueue_blocks(cls, uid: int, qid: str, block_keys: List[str]) -> bool:
        """
        将Block Keys推入任务队列
        
        Args:
            uid: 用户ID
            qid: 查询ID
            block_keys: Block Key列表，如 ["meta:NATURE:2024", ...]
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid or not block_keys:
            return False
        
        try:
            key = cls._key_pending(uid, qid)
            client.rpush(key, *block_keys)
            return True
        except Exception:
            return False
    
    @classmethod
    def pop_block(cls, uid: int, qid: str) -> Optional[str]:
        """
        从队列头部弹出一个Block Key（LPOP）
        
        Returns:
            Block Key，或None（队列为空）
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return None
        
        try:
            return client.lpop(cls._key_pending(uid, qid))
        except Exception:
            return None
    
    @classmethod
    def push_back_block(cls, uid: int, qid: str, block_key: str) -> bool:
        """将Block Key推回队列头部（用于暂停时回退）"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid or not block_key:
            return False
        
        try:
            client.lpush(cls._key_pending(uid, qid), block_key)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_pending_count(cls, uid: int, qid: str) -> int:
        """获取待处理Block数量"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return 0
        
        try:
            return client.llen(cls._key_pending(uid, qid)) or 0
        except Exception:
            return 0
    
    @classmethod
    def get_all_pending(cls, uid: int, qid: str) -> List[str]:
        """获取所有待处理Block"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return []
        
        try:
            return client.lrange(cls._key_pending(uid, qid), 0, -1) or []
        except Exception:
            return []
    
    @classmethod
    def clear_pending(cls, uid: int, qid: str) -> bool:
        """清空待处理队列"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            client.delete(cls._key_pending(uid, qid))
            return True
        except Exception:
            return False
    
    # ==================== 任务状态操作 ====================
    
    @classmethod
    def init_status(cls, uid: int, qid: str, total_blocks: int) -> bool:
        """
        初始化任务状态
        
        Args:
            uid: 用户ID
            qid: 查询ID
            total_blocks: 总Block数
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            key = cls._key_status(uid, qid)
            client.hset(key, mapping={
                'total_blocks': str(total_blocks),
                'finished_blocks': '0',
                'state': 'RUNNING',
                'start_time': str(time.time()),
            })
            return True
        except Exception:
            return False
    
    @classmethod
    def get_status(cls, uid: int, qid: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return None
        
        try:
            data = client.hgetall(cls._key_status(uid, qid))
            if not data:
                return None
            
            result = dict(data)
            # 类型转换
            if 'total_blocks' in result:
                result['total_blocks'] = int(result['total_blocks'])
            if 'finished_blocks' in result:
                result['finished_blocks'] = int(result['finished_blocks'])
            if 'start_time' in result:
                result['start_time'] = float(result['start_time'])
            
            return result
        except Exception:
            return None
    
    @classmethod
    def incr_finished_blocks(cls, uid: int, qid: str) -> int:
        """
        增加已完成Block计数
        
        Returns:
            更新后的计数
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return 0
        
        try:
            return client.hincrby(cls._key_status(uid, qid), 'finished_blocks', 1)
        except Exception:
            return 0
    
    @classmethod
    def set_state(cls, uid: int, qid: str, state: str) -> bool:
        """设置任务状态（RUNNING/DONE/FAILED/CANCELLED）"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            client.hset(cls._key_status(uid, qid), 'state', state)
            if state == 'DONE':
                client.hset(cls._key_status(uid, qid), 'end_time', str(time.time()))
            return True
        except Exception:
            return False
    
    @classmethod
    def is_completed(cls, uid: int, qid: str) -> bool:
        """检查任务是否已完成"""
        status = cls.get_status(uid, qid)
        if not status:
            return False
        
        total = status.get('total_blocks', 0)
        finished = status.get('finished_blocks', 0)
        return total > 0 and finished >= total
    
    # ==================== 终止信号操作 ====================
    
    @classmethod
    def set_terminate_signal(cls, uid: int, qid: str, ttl: int = 604800) -> bool:
        """
        设置终止信号
        
        区别于暂停信号：终止信号表示任务被强制取消，不会恢复
        
        Args:
            uid: 用户ID
            qid: 查询ID
            ttl: 过期时间（默认7天）
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            client.set(cls._key_terminate(uid, qid), "1", ex=ttl)
            return True
        except Exception:
            return False
    
    @classmethod
    def clear_terminate_signal(cls, uid: int, qid: str) -> bool:
        """清除终止信号"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            client.delete(cls._key_terminate(uid, qid))
            return True
        except Exception:
            return False
    
    @classmethod
    def is_terminated(cls, uid: int, qid: str) -> bool:
        """检查是否存在终止信号"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            return client.exists(cls._key_terminate(uid, qid)) > 0
        except Exception:
            return False
    
    # ==================== 进度操作 ====================
    
    @classmethod
    def incr_finished_count(cls, uid: int, qid: str) -> int:
        """增加已完成文献计数"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return 0
        
        try:
            return client.incr(cls._key_progress(uid, qid))
        except Exception:
            return 0
    
    @classmethod
    def get_finished_count(cls, uid: int, qid: str) -> int:
        """获取已完成文献计数"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return 0
        
        try:
            val = client.get(cls._key_progress(uid, qid))
            return int(val) if val else 0
        except Exception:
            return 0
    
    @classmethod
    def reset_finished_count(cls, uid: int, qid: str) -> bool:
        """重置已完成计数"""
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            client.set(cls._key_progress(uid, qid), "0")
            return True
        except Exception:
            return False

