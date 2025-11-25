"""
下载队列模块
管理下载任务的队列化处理

Key设计:
- download_queue (List) - 全局下载队列
  - Value: JSON {uid, qid, type, timestamp}
"""

import json
import time
from typing import Optional, Dict, List, Any

from .connection import get_redis_client


class DownloadQueue:
    """下载队列管理器"""
    
    KEY_DOWNLOAD_QUEUE = "download_queue"
    
    @classmethod
    def enqueue_download(cls, uid: int, qid: str, 
                         download_type: str = "csv") -> bool:
        """
        将下载任务加入队列
        
        Args:
            uid: 用户ID
            qid: 查询ID
            download_type: 下载类型 ("csv" 或 "bib")
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return False
        
        try:
            task = {
                'uid': uid,
                'qid': qid,
                'type': download_type,
                'timestamp': time.time(),
            }
            client.rpush(cls.KEY_DOWNLOAD_QUEUE, json.dumps(task))
            return True
        except Exception:
            return False
    
    @classmethod
    def dequeue_download(cls) -> Optional[Dict]:
        """
        从队列中取出一个下载任务
        
        Returns:
            下载任务字典，或None
        """
        client = get_redis_client()
        if not client:
            return None
        
        try:
            data = client.lpop(cls.KEY_DOWNLOAD_QUEUE)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None
    
    @classmethod
    def peek_download(cls) -> Optional[Dict]:
        """查看队列头部任务（不弹出）"""
        client = get_redis_client()
        if not client:
            return None
        
        try:
            data_list = client.lrange(cls.KEY_DOWNLOAD_QUEUE, 0, 0)
            if data_list:
                return json.loads(data_list[0])
            return None
        except Exception:
            return None
    
    @classmethod
    def get_queue_length(cls) -> int:
        """获取队列长度"""
        client = get_redis_client()
        if not client:
            return 0
        
        try:
            return client.llen(cls.KEY_DOWNLOAD_QUEUE) or 0
        except Exception:
            return 0
    
    @classmethod
    def get_all_tasks(cls) -> List[Dict]:
        """获取所有待处理任务"""
        client = get_redis_client()
        if not client:
            return []
        
        try:
            data_list = client.lrange(cls.KEY_DOWNLOAD_QUEUE, 0, -1) or []
            return [json.loads(d) for d in data_list]
        except Exception:
            return []
    
    @classmethod
    def clear_queue(cls) -> bool:
        """清空队列"""
        client = get_redis_client()
        if not client:
            return False
        
        try:
            client.delete(cls.KEY_DOWNLOAD_QUEUE)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_user_tasks_count(cls, uid: int) -> int:
        """获取指定用户的待处理下载任务数"""
        tasks = cls.get_all_tasks()
        return sum(1 for t in tasks if t.get('uid') == uid)

