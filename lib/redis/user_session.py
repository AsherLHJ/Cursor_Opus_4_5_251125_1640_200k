"""
用户会话管理模块 (修复37新增)
管理普通用户登录会话

Key设计:
- user:session:{token} (String, TTL 24h) - Value = uid
- user:{uid}:sessions  (Set)             - 用户的所有会话token（用于多设备管理）

参考设计: lib/redis/admin.py (管理员会话模块)
"""

import secrets
from typing import Optional, Dict, Set

from .connection import get_redis_client, TTL_USER_SESSION


class UserSession:
    """用户会话管理器"""
    
    # 单用户最大会话数（防止会话泄露）
    MAX_SESSIONS_PER_USER = 10
    
    @staticmethod
    def _key_session(token: str) -> str:
        """会话Key"""
        return f"user:session:{token}"
    
    @staticmethod
    def _key_user_sessions(uid: int) -> str:
        """用户会话集合Key"""
        return f"user:{uid}:sessions"
    
    @classmethod
    def generate_token(cls) -> str:
        """生成安全的会话Token（URL安全的Base64编码）"""
        return secrets.token_urlsafe(32)
    
    # ==================== 会话创建与验证 ====================
    
    @classmethod
    def create_session(cls, uid: int, ttl: int = None) -> Optional[str]:
        """
        创建用户会话
        
        Args:
            uid: 用户UID
            ttl: 会话过期时间（秒），默认24小时
            
        Returns:
            会话Token，失败返回None
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return None
        
        try:
            token = cls.generate_token()
            expire = ttl or TTL_USER_SESSION
            
            # 使用Pipeline确保原子性
            pipe = client.pipeline()
            
            # 1. 存储会话 token -> uid
            pipe.set(cls._key_session(token), str(uid), ex=expire)
            
            # 2. 将token添加到用户会话集合
            pipe.sadd(cls._key_user_sessions(uid), token)
            
            # 3. 设置用户会话集合的过期时间（比单个会话长一点，用于清理）
            pipe.expire(cls._key_user_sessions(uid), expire + 3600)
            
            pipe.execute()
            
            # 4. 清理过多的会话（保留最新的N个）
            cls._cleanup_excess_sessions(uid)
            
            return token
        except Exception as e:
            print(f"[UserSession] 创建会话失败: {e}")
            return None
    
    @classmethod
    def get_session_uid(cls, token: str) -> Optional[int]:
        """
        验证会话Token并获取用户UID
        
        Args:
            token: 会话Token
            
        Returns:
            用户UID，无效Token返回None
        """
        client = get_redis_client()
        if not client or not token:
            return None
        
        try:
            uid_str = client.get(cls._key_session(token))
            if uid_str:
                # 刷新会话TTL（活跃用户不会被踢出）
                client.expire(cls._key_session(token), TTL_USER_SESSION)
                return int(uid_str)
            return None
        except Exception as e:
            print(f"[UserSession] 验证会话失败: {e}")
            return None
    
    @classmethod
    def is_valid_session(cls, token: str) -> bool:
        """检查会话是否有效"""
        return cls.get_session_uid(token) is not None
    
    @classmethod
    def refresh_session(cls, token: str) -> bool:
        """
        刷新会话TTL
        
        Returns:
            是否刷新成功
        """
        client = get_redis_client()
        if not client or not token:
            return False
        
        try:
            return bool(client.expire(cls._key_session(token), TTL_USER_SESSION))
        except Exception:
            return False
    
    # ==================== 会话销毁 ====================
    
    @classmethod
    def destroy_session(cls, token: str) -> bool:
        """
        销毁单个会话
        
        Args:
            token: 会话Token
            
        Returns:
            是否销毁成功
        """
        client = get_redis_client()
        if not client or not token:
            return False
        
        try:
            # 获取会话对应的uid
            uid_str = client.get(cls._key_session(token))
            
            pipe = client.pipeline()
            
            # 1. 删除会话
            pipe.delete(cls._key_session(token))
            
            # 2. 从用户会话集合中移除
            if uid_str:
                pipe.srem(cls._key_user_sessions(int(uid_str)), token)
            
            pipe.execute()
            return True
        except Exception as e:
            print(f"[UserSession] 销毁会话失败: {e}")
            return False
    
    @classmethod
    def destroy_all_sessions_for_uid(cls, uid: int) -> int:
        """
        销毁指定用户的所有会话（强制登出所有设备）
        
        Args:
            uid: 用户UID
            
        Returns:
            销毁的会话数量
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return 0
        
        try:
            # 获取用户所有会话
            tokens = client.smembers(cls._key_user_sessions(uid))
            if not tokens:
                return 0
            
            # 批量删除
            pipe = client.pipeline()
            for token in tokens:
                pipe.delete(cls._key_session(token))
            
            # 删除会话集合
            pipe.delete(cls._key_user_sessions(uid))
            
            pipe.execute()
            return len(tokens)
        except Exception as e:
            print(f"[UserSession] 销毁所有会话失败: {e}")
            return 0
    
    # ==================== 会话管理 ====================
    
    @classmethod
    def get_user_sessions(cls, uid: int) -> Set[str]:
        """
        获取用户的所有活跃会话Token
        
        Args:
            uid: 用户UID
            
        Returns:
            会话Token集合
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return set()
        
        try:
            return client.smembers(cls._key_user_sessions(uid)) or set()
        except Exception:
            return set()
    
    @classmethod
    def get_session_count(cls, uid: int) -> int:
        """获取用户活跃会话数量"""
        client = get_redis_client()
        if not client or uid <= 0:
            return 0
        
        try:
            return client.scard(cls._key_user_sessions(uid)) or 0
        except Exception:
            return 0
    
    @classmethod
    def _cleanup_excess_sessions(cls, uid: int) -> int:
        """
        清理过多的会话（保留最新的N个）
        
        Returns:
            清理的会话数量
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return 0
        
        try:
            tokens = client.smembers(cls._key_user_sessions(uid))
            if not tokens or len(tokens) <= cls.MAX_SESSIONS_PER_USER:
                return 0
            
            # 检查每个会话是否有效，无效的直接清理
            valid_tokens = []
            invalid_tokens = []
            
            for token in tokens:
                if client.exists(cls._key_session(token)):
                    valid_tokens.append(token)
                else:
                    invalid_tokens.append(token)
            
            # 如果无效会话清理后仍超过限制，删除最旧的
            cleaned = len(invalid_tokens)
            
            if len(valid_tokens) > cls.MAX_SESSIONS_PER_USER:
                # 无法确定哪个最旧，随机删除超出的部分
                excess = len(valid_tokens) - cls.MAX_SESSIONS_PER_USER
                to_delete = valid_tokens[:excess]
                
                for token in to_delete:
                    client.delete(cls._key_session(token))
                    invalid_tokens.append(token)
                    cleaned += 1
            
            # 从集合中移除无效token
            if invalid_tokens:
                client.srem(cls._key_user_sessions(uid), *invalid_tokens)
            
            return cleaned
        except Exception as e:
            print(f"[UserSession] 清理会话失败: {e}")
            return 0
    
    # ==================== 统计与调试 ====================
    
    @classmethod
    def get_all_sessions(cls) -> Dict[str, int]:
        """
        获取所有活跃的用户会话（仅用于调试/监控）
        
        Returns:
            {token: uid} 字典
        """
        client = get_redis_client()
        if not client:
            return {}
        
        try:
            sessions = {}
            for key in client.scan_iter(match="user:session:*"):
                token = key.replace("user:session:", "")
                uid_str = client.get(key)
                if uid_str:
                    sessions[token] = int(uid_str)
            return sessions
        except Exception:
            return {}
    
    @classmethod
    def get_total_session_count(cls) -> int:
        """获取系统中所有活跃会话总数"""
        client = get_redis_client()
        if not client:
            return 0
        
        try:
            count = 0
            for _ in client.scan_iter(match="user:session:*"):
                count += 1
            return count
        except Exception:
            return 0

