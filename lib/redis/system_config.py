"""
系统配置 Redis 缓存模块
存储动态系统配置项，支持高频读取

Key设计:
- sys:config:{setting_key} (String) - 配置值

默认配置项:
- permission_min: 用户权限最小值 (默认 1)
- permission_max: 用户权限最大值 (默认 10)
- distill_rate: 蒸馏任务价格系数 (默认 0.1)
"""

from typing import Optional, Tuple, Dict
from .connection import get_redis_client


class SystemConfig:
    """系统配置 Redis 缓存管理器"""
    
    # 配置 Key 前缀
    PREFIX = "sys:config:"
    
    # 默认值（Redis 未命中且 MySQL 回源失败时使用）
    DEFAULTS = {
        'permission_min': '1',
        'permission_max': '10',
        'distill_rate': '0.1',
    }
    
    @classmethod
    def _key(cls, setting_key: str) -> str:
        """生成 Redis Key"""
        return f"{cls.PREFIX}{setting_key}"
    
    @classmethod
    def get(cls, key: str, default: str = None) -> Optional[str]:
        """
        获取配置值
        
        Args:
            key: 配置键名
            default: 默认值（Redis 未命中时返回）
            
        Returns:
            配置值字符串，或默认值
        """
        client = get_redis_client()
        if not client:
            return default or cls.DEFAULTS.get(key)
        
        try:
            value = client.get(cls._key(key))
            if value is not None:
                return value
            return default or cls.DEFAULTS.get(key)
        except Exception:
            return default or cls.DEFAULTS.get(key)
    
    @classmethod
    def set(cls, key: str, value: str) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键名
            value: 配置值
            
        Returns:
            是否成功
        """
        client = get_redis_client()
        if not client:
            return False
        
        try:
            client.set(cls._key(key), value)
            return True
        except Exception:
            return False
    
    @classmethod
    def delete(cls, key: str) -> bool:
        """删除配置项"""
        client = get_redis_client()
        if not client:
            return False
        
        try:
            client.delete(cls._key(key))
            return True
        except Exception:
            return False
    
    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        """获取整数类型配置值"""
        value = cls.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def get_float(cls, key: str, default: float = 0.0) -> float:
        """获取浮点数类型配置值"""
        value = cls.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def get_all(cls) -> Dict[str, str]:
        """
        获取所有配置项（从 Redis）
        
        Returns:
            {key: value} 字典
        """
        client = get_redis_client()
        if not client:
            return cls.DEFAULTS.copy()
        
        try:
            result = {}
            # 扫描所有配置 Key
            for redis_key in client.scan_iter(match=f"{cls.PREFIX}*"):
                key = redis_key.replace(cls.PREFIX, '')
                value = client.get(redis_key)
                if value is not None:
                    result[key] = value
            return result if result else cls.DEFAULTS.copy()
        except Exception:
            return cls.DEFAULTS.copy()
    
    @classmethod
    def set_all(cls, settings: Dict[str, str]) -> bool:
        """
        批量设置配置项
        
        Args:
            settings: {key: value} 字典
        """
        client = get_redis_client()
        if not client:
            return False
        
        try:
            pipe = client.pipeline()
            for key, value in settings.items():
                pipe.set(cls._key(key), str(value))
            pipe.execute()
            return True
        except Exception:
            return False
    
    # ============================================================
    # 便捷方法（常用配置项的快捷访问）
    # ============================================================
    
    @classmethod
    def get_permission_range(cls) -> Tuple[int, int]:
        """
        获取用户权限范围
        
        Returns:
            (min_permission, max_permission) 元组
        """
        min_val = cls.get_int('permission_min', 1)
        max_val = cls.get_int('permission_max', 10)
        return (min_val, max_val)
    
    @classmethod
    def get_distill_rate(cls) -> float:
        """
        获取蒸馏任务价格系数
        
        Returns:
            蒸馏系数（相对于查询任务），默认 0.1
        """
        return cls.get_float('distill_rate', 0.1)
    
    @classmethod
    def set_permission_range(cls, min_val: int, max_val: int) -> bool:
        """设置用户权限范围"""
        if min_val < 0 or max_val < min_val:
            return False
        return cls.set('permission_min', str(min_val)) and cls.set('permission_max', str(max_val))
    
    @classmethod
    def set_distill_rate(cls, rate: float) -> bool:
        """设置蒸馏系数"""
        if rate < 0 or rate > 1:
            return False
        return cls.set('distill_rate', str(rate))


