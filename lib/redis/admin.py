"""
管理员会话模块
管理管理员登录会话和信息缓存

Key设计:
- admin:session:{token} (String) - 管理员会话，Value=uid
- admin:{uid}:info      (Hash)   - 管理员信息缓存
"""

import json
import time
import secrets
from typing import Optional, Dict, Any

from .connection import get_redis_client, TTL_ADMIN_SESSION


class AdminSession:
    """管理员会话管理器"""
    
    @staticmethod
    def _key_session(token: str) -> str:
        return f"admin:session:{token}"
    
    @staticmethod
    def _key_info(uid: int) -> str:
        return f"admin:{uid}:info"
    
    @classmethod
    def generate_token(cls) -> str:
        """生成安全的会话Token"""
        return secrets.token_urlsafe(32)
    
    # ==================== 会话管理 ====================
    
    @classmethod
    def create_session(cls, uid: int, ttl: int = None) -> Optional[str]:
        """
        创建管理员会话
        
        Args:
            uid: 管理员UID
            ttl: 会话过期时间（秒），默认24小时
            
        Returns:
            会话Token
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return None
        
        try:
            token = cls.generate_token()
            expire = ttl or TTL_ADMIN_SESSION
            client.set(cls._key_session(token), str(uid), ex=expire)
            return token
        except Exception:
            return None
    
    @classmethod
    def get_session_uid(cls, token: str) -> Optional[int]:
        """
        验证会话Token并获取管理员UID
        
        Args:
            token: 会话Token
            
        Returns:
            管理员UID，或None（无效Token）
        """
        client = get_redis_client()
        if not client or not token:
            return None
        
        try:
            uid_str = client.get(cls._key_session(token))
            if uid_str:
                # 刷新会话TTL
                client.expire(cls._key_session(token), TTL_ADMIN_SESSION)
                return int(uid_str)
            return None
        except Exception:
            return None
    
    @classmethod
    def destroy_session(cls, token: str) -> bool:
        """销毁会话"""
        client = get_redis_client()
        if not client or not token:
            return False
        
        try:
            client.delete(cls._key_session(token))
            return True
        except Exception:
            return False
    
    @classmethod
    def is_valid_session(cls, token: str) -> bool:
        """检查会话是否有效"""
        return cls.get_session_uid(token) is not None
    
    # ==================== 管理员信息缓存 ====================
    
    @classmethod
    def get_admin_info(cls, uid: int) -> Optional[Dict[str, Any]]:
        """获取管理员信息"""
        client = get_redis_client()
        if not client or uid <= 0:
            return None
        
        try:
            data = client.hgetall(cls._key_info(uid))
            if not data:
                return None
            
            result = dict(data)
            if 'uid' in result:
                result['uid'] = int(result['uid'])
            return result
        except Exception:
            return None
    
    @classmethod
    def set_admin_info(cls, uid: int, username: str, role: str = "admin") -> bool:
        """设置管理员信息缓存"""
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            key = cls._key_info(uid)
            client.hset(key, mapping={
                'uid': str(uid),
                'username': username,
                'role': role,
            })
            client.expire(key, TTL_ADMIN_SESSION)
            return True
        except Exception:
            return False
    
    @classmethod
    def delete_admin_info(cls, uid: int) -> bool:
        """删除管理员信息缓存"""
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            client.delete(cls._key_info(uid))
            return True
        except Exception:
            return False
    
    # ==================== 会话列表管理 ====================
    
    @classmethod
    def get_all_sessions(cls) -> Dict[str, int]:
        """
        获取所有活跃的管理员会话
        
        Returns:
            {token: uid} 字典
        """
        client = get_redis_client()
        if not client:
            return {}
        
        try:
            sessions = {}
            for key in client.scan_iter(match="admin:session:*"):
                token = key.replace("admin:session:", "")
                uid_str = client.get(key)
                if uid_str:
                    sessions[token] = int(uid_str)
            return sessions
        except Exception:
            return {}
    
    @classmethod
    def destroy_all_sessions_for_uid(cls, uid: int) -> int:
        """
        销毁指定管理员的所有会话
        
        Returns:
            销毁的会话数量
        """
        sessions = cls.get_all_sessions()
        count = 0
        for token, session_uid in sessions.items():
            if session_uid == uid:
                if cls.destroy_session(token):
                    count += 1
        return count

