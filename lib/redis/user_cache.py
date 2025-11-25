"""
用户数据缓存模块
管理用户信息、余额和历史记录的Redis缓存

Key设计:
- user:{uid}:info    (Hash) - 用户基本信息，TTL 8小时
- user:{uid}:balance (String) - 用户余额，TTL 8小时
- user:{uid}:history (ZSet) - 查询历史，Score=时间戳
"""

import json
import time
from typing import Optional, Dict, List, Any

from .connection import get_redis_client, TTL_USER_INFO, TTL_USER_BALANCE


class UserCache:
    """用户数据缓存管理器"""
    
    @staticmethod
    def _key_info(uid: int) -> str:
        return f"user:{uid}:info"
    
    @staticmethod
    def _key_balance(uid: int) -> str:
        return f"user:{uid}:balance"
    
    @staticmethod
    def _key_history(uid: int) -> str:
        return f"user:{uid}:history"
    
    # ==================== 用户信息 ====================
    
    @classmethod
    def get_user_info(cls, uid: int) -> Optional[Dict[str, Any]]:
        """
        获取用户信息
        
        Returns:
            用户信息字典，或None（缓存未命中）
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return None
        
        try:
            data = client.hgetall(cls._key_info(uid))
            if not data:
                return None
            
            # 访问延期（刷新TTL）
            client.expire(cls._key_info(uid), TTL_USER_INFO)
            
            # 转换数据类型
            result = dict(data)
            if 'uid' in result:
                result['uid'] = int(result['uid'])
            if 'permission' in result:
                result['permission'] = int(result['permission'])
            
            return result
        except Exception:
            return None
    
    @classmethod
    def set_user_info(cls, uid: int, username: str, permission: int) -> bool:
        """设置用户信息（从MySQL加载后写入Redis）"""
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            key = cls._key_info(uid)
            client.hset(key, mapping={
                'uid': str(uid),
                'username': username,
                'permission': str(permission),
            })
            client.expire(key, TTL_USER_INFO)
            return True
        except Exception:
            return False
    
    @classmethod
    def update_permission(cls, uid: int, permission: int) -> bool:
        """更新用户权限"""
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            key = cls._key_info(uid)
            if client.exists(key):
                client.hset(key, 'permission', str(permission))
                return True
            return False
        except Exception:
            return False
    
    @classmethod
    def delete_user_info(cls, uid: int) -> bool:
        """删除用户信息缓存"""
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            client.delete(cls._key_info(uid))
            return True
        except Exception:
            return False
    
    # ==================== 用户余额 ====================
    
    @classmethod
    def get_balance(cls, uid: int) -> Optional[float]:
        """
        获取用户余额
        
        Returns:
            余额值，或None（缓存未命中）
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return None
        
        try:
            val = client.get(cls._key_balance(uid))
            if val is None:
                return None
            
            # 访问延期
            client.expire(cls._key_balance(uid), TTL_USER_BALANCE)
            
            return float(val)
        except Exception:
            return None
    
    @classmethod
    def set_balance(cls, uid: int, balance: float) -> bool:
        """设置用户余额"""
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            key = cls._key_balance(uid)
            client.set(key, str(balance), ex=TTL_USER_BALANCE)
            return True
        except Exception:
            return False
    
    @classmethod
    def deduct_balance(cls, uid: int, amount: float) -> Optional[float]:
        """
        原子扣减余额
        
        Args:
            uid: 用户ID
            amount: 扣减金额
            
        Returns:
            扣减后的余额，或None（扣减失败）
        """
        client = get_redis_client()
        if not client or uid <= 0 or amount <= 0:
            return None
        
        # 使用Lua脚本实现原子扣减
        lua_script = """
        local key = KEYS[1]
        local amount = tonumber(ARGV[1])
        local current = tonumber(redis.call('GET', key) or '0')
        if current >= amount then
            local new_balance = current - amount
            redis.call('SET', key, tostring(new_balance))
            redis.call('EXPIRE', key, ARGV[2])
            return tostring(new_balance)
        else
            return nil
        end
        """
        
        try:
            from .connection import execute_lua_script
            result = execute_lua_script(
                lua_script,
                keys=[cls._key_balance(uid)],
                args=[str(amount), str(TTL_USER_BALANCE)]
            )
            if result is not None:
                return float(result)
            return None
        except Exception:
            return None
    
    @classmethod
    def delete_balance(cls, uid: int) -> bool:
        """删除余额缓存（强制下次从MySQL读取）"""
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            client.delete(cls._key_balance(uid))
            return True
        except Exception:
            return False
    
    # ==================== 查询历史 ====================
    
    @classmethod
    def add_history(cls, uid: int, query_id: str, timestamp: Optional[float] = None) -> bool:
        """
        添加查询历史记录
        
        Args:
            uid: 用户ID
            query_id: 查询ID
            timestamp: 时间戳（默认当前时间）
        """
        client = get_redis_client()
        if not client or uid <= 0 or not query_id:
            return False
        
        try:
            ts = timestamp or time.time()
            client.zadd(cls._key_history(uid), {query_id: ts})
            return True
        except Exception:
            return False
    
    @classmethod
    def get_history(cls, uid: int, limit: int = 10) -> List[str]:
        """
        获取最近的查询历史
        
        Args:
            uid: 用户ID
            limit: 返回数量限制
            
        Returns:
            查询ID列表（按时间倒序）
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return []
        
        try:
            # ZREVRANGE: 按分数倒序返回
            return client.zrevrange(cls._key_history(uid), 0, limit - 1) or []
        except Exception:
            return []
    
    @classmethod
    def rebuild_history(cls, uid: int, history_items: List[tuple]) -> bool:
        """
        重建历史记录（从MySQL加载后）
        
        Args:
            uid: 用户ID
            history_items: [(query_id, timestamp), ...] 列表
        """
        client = get_redis_client()
        if not client or uid <= 0:
            return False
        
        try:
            key = cls._key_history(uid)
            client.delete(key)
            if history_items:
                mapping = {qid: ts for qid, ts in history_items}
                client.zadd(key, mapping)
            return True
        except Exception:
            return False

