"""
下载队列模块
管理下载任务的队列化处理

Key设计:
- download_queue (List) - 全局下载队列
  - Value: JSON {task_id, uid, qid, type, timestamp}
- download:{task_id}:status (Hash) - 任务状态
  - Fields: state, uid, qid, type, created_at, error
  - state: PENDING/PROCESSING/READY/FAILED
- download:{task_id}:file (String) - 生成的文件内容，TTL 5分钟
"""

import json
import time
import uuid
from typing import Optional, Dict, List, Any

from .connection import get_redis_client


# 任务状态常量
DOWNLOAD_STATE_PENDING = "PENDING"
DOWNLOAD_STATE_PROCESSING = "PROCESSING"
DOWNLOAD_STATE_READY = "READY"
DOWNLOAD_STATE_FAILED = "FAILED"

# 文件缓存TTL（秒）
DOWNLOAD_FILE_TTL = 300  # 5分钟


class DownloadQueue:
    """下载队列管理器"""
    
    KEY_DOWNLOAD_QUEUE = "download_queue"
    KEY_PREFIX_STATUS = "download:"
    KEY_SUFFIX_STATUS = ":status"
    KEY_SUFFIX_FILE = ":file"
    
    # ============================================================
    # 任务创建与队列管理
    # ============================================================
    
    @classmethod
    def create_task(cls, uid: int, qid: str, download_type: str = "csv") -> Optional[str]:
        """
        创建下载任务，返回task_id
        
        Args:
            uid: 用户ID
            qid: 查询ID
            download_type: 下载类型 ("csv" 或 "bib")
            
        Returns:
            task_id 字符串，失败返回 None
        """
        client = get_redis_client()
        if not client or uid <= 0 or not qid:
            return None
        
        try:
            # 生成唯一任务ID
            task_id = f"DL{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # 创建任务状态
            status_key = cls._status_key(task_id)
            status_data = {
                'state': DOWNLOAD_STATE_PENDING,
                'uid': str(uid),
                'qid': qid,
                'type': download_type,
                'created_at': str(time.time()),
                'error': '',
            }
            client.hset(status_key, mapping=status_data)
            
            # 将任务加入队列
            task = {
                'task_id': task_id,
                'uid': uid,
                'qid': qid,
                'type': download_type,
                'timestamp': time.time(),
            }
            client.rpush(cls.KEY_DOWNLOAD_QUEUE, json.dumps(task))
            
            return task_id
        except Exception as e:
            print(f"[DownloadQueue] 创建任务失败: {e}")
            return None
    
    @classmethod
    def enqueue_download(cls, uid: int, qid: str, 
                         download_type: str = "csv") -> bool:
        """
        将下载任务加入队列（旧接口，兼容性保留）
        
        Args:
            uid: 用户ID
            qid: 查询ID
            download_type: 下载类型 ("csv" 或 "bib")
        """
        task_id = cls.create_task(uid, qid, download_type)
        return task_id is not None
    
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
    
    # ============================================================
    # 任务状态管理
    # ============================================================
    
    @classmethod
    def _status_key(cls, task_id: str) -> str:
        """生成状态Key"""
        return f"{cls.KEY_PREFIX_STATUS}{task_id}{cls.KEY_SUFFIX_STATUS}"
    
    @classmethod
    def _file_key(cls, task_id: str) -> str:
        """生成文件Key"""
        return f"{cls.KEY_PREFIX_STATUS}{task_id}{cls.KEY_SUFFIX_FILE}"
    
    @classmethod
    def get_task_status(cls, task_id: str) -> Optional[Dict]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            状态字典 {state, uid, qid, type, created_at, error}
        """
        client = get_redis_client()
        if not client or not task_id:
            return None
        
        try:
            data = client.hgetall(cls._status_key(task_id))
            if data:
                return {
                    'state': data.get('state', DOWNLOAD_STATE_PENDING),
                    'uid': int(data.get('uid', 0)),
                    'qid': data.get('qid', ''),
                    'type': data.get('type', 'csv'),
                    'created_at': float(data.get('created_at', 0)),
                    'error': data.get('error', ''),
                }
            return None
        except Exception:
            return None
    
    @classmethod
    def set_task_state(cls, task_id: str, state: str, error: str = None) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            state: 新状态 (PENDING/PROCESSING/READY/FAILED)
            error: 错误信息（可选）
        """
        client = get_redis_client()
        if not client or not task_id:
            return False
        
        try:
            updates = {'state': state}
            if error is not None:
                updates['error'] = error
            client.hset(cls._status_key(task_id), mapping=updates)
            return True
        except Exception:
            return False
    
    @classmethod
    def set_processing(cls, task_id: str) -> bool:
        """将任务标记为处理中"""
        return cls.set_task_state(task_id, DOWNLOAD_STATE_PROCESSING)
    
    @classmethod
    def set_ready(cls, task_id: str) -> bool:
        """将任务标记为已就绪"""
        return cls.set_task_state(task_id, DOWNLOAD_STATE_READY)
    
    @classmethod
    def set_failed(cls, task_id: str, error: str = "Unknown error") -> bool:
        """将任务标记为失败"""
        return cls.set_task_state(task_id, DOWNLOAD_STATE_FAILED, error)
    
    # ============================================================
    # 文件内容存储
    # ============================================================
    
    @classmethod
    def store_file_content(cls, task_id: str, content: bytes, 
                           ttl: int = DOWNLOAD_FILE_TTL) -> bool:
        """
        存储生成的文件内容
        
        Args:
            task_id: 任务ID
            content: 文件内容（bytes）
            ttl: 过期时间（秒），默认5分钟
        """
        client = get_redis_client()
        if not client or not task_id or not content:
            return False
        
        try:
            file_key = cls._file_key(task_id)
            client.set(file_key, content, ex=ttl)
            return True
        except Exception as e:
            print(f"[DownloadQueue] 存储文件失败: {e}")
            return False
    
    @classmethod
    def get_file_content(cls, task_id: str) -> Optional[bytes]:
        """
        获取文件内容
        
        Args:
            task_id: 任务ID
            
        Returns:
            文件内容（bytes），不存在返回None
        """
        client = get_redis_client()
        if not client or not task_id:
            return None
        
        try:
            file_key = cls._file_key(task_id)
            content = client.get(file_key)
            if content:
                # 如果是字符串，转换为bytes
                if isinstance(content, str):
                    return content.encode('utf-8')
                return content
            return None
        except Exception:
            return None
    
    @classmethod
    def delete_task(cls, task_id: str) -> bool:
        """
        删除任务相关的所有数据
        
        Args:
            task_id: 任务ID
        """
        client = get_redis_client()
        if not client or not task_id:
            return False
        
        try:
            client.delete(cls._status_key(task_id))
            client.delete(cls._file_key(task_id))
            return True
        except Exception:
            return False
    
    # ============================================================
    # 工具方法
    # ============================================================
    
    @classmethod
    def is_task_ready(cls, task_id: str) -> bool:
        """检查任务是否已就绪"""
        status = cls.get_task_status(task_id)
        return status is not None and status.get('state') == DOWNLOAD_STATE_READY
    
    @classmethod
    def is_task_failed(cls, task_id: str) -> bool:
        """检查任务是否失败"""
        status = cls.get_task_status(task_id)
        return status is not None and status.get('state') == DOWNLOAD_STATE_FAILED
    
    @classmethod
    def validate_task_owner(cls, task_id: str, uid: int) -> bool:
        """
        验证任务所有者
        
        Args:
            task_id: 任务ID
            uid: 用户ID
            
        Returns:
            是否是任务所有者
        """
        status = cls.get_task_status(task_id)
        if not status:
            return False
        return status.get('uid') == uid
