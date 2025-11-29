"""
系统配置 DAO 模块
实现 MySQL + Redis 双写策略，确保配置持久化和高性能读取

数据流:
- 读取: Redis (缓存) → MySQL (回源)
- 写入: MySQL (持久化) → Redis (缓存更新)
"""

from typing import Optional, Dict, Tuple
from .db_base import _get_connection
from ..redis.system_config import SystemConfig
from ..redis.connection import redis_ping


def get_setting(key: str, default: str = None) -> Optional[str]:
    """
    获取配置项（先查 Redis，MISS 则回源 MySQL）
    
    Args:
        key: 配置键名
        default: 默认值
        
    Returns:
        配置值，或默认值
    """
    # 1. 先查 Redis
    if redis_ping():
        value = SystemConfig.get(key)
        if value is not None:
            return value
    
    # 2. Redis MISS，回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT setting_value FROM system_settings WHERE setting_key = %s",
            (key,)
        )
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            value = result[0]
            # 写入 Redis 缓存
            if redis_ping():
                SystemConfig.set(key, value)
            return value
        
        return default
    except Exception as e:
        print(f"[system_settings_dao] get_setting 失败: {e}")
        return default
    finally:
        conn.close()


def set_setting(key: str, value: str, description: str = None) -> bool:
    """
    设置配置项（先写 MySQL，再更新 Redis）
    
    Args:
        key: 配置键名
        value: 配置值
        description: 配置描述（可选）
        
    Returns:
        是否成功
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        if description:
            # 带描述的插入/更新
            cursor.execute(
                """
                INSERT INTO system_settings (setting_key, setting_value, description)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE setting_value = %s, description = %s
                """,
                (key, value, description, value, description)
            )
        else:
            # 仅更新值
            cursor.execute(
                """
                INSERT INTO system_settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = %s
                """,
                (key, value, value)
            )
        
        conn.commit()
        cursor.close()
        
        # 更新 Redis 缓存
        if redis_ping():
            SystemConfig.set(key, value)
        
        return True
    except Exception as e:
        print(f"[system_settings_dao] set_setting 失败: {e}")
        return False
    finally:
        conn.close()


def delete_setting(key: str) -> bool:
    """删除配置项"""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM system_settings WHERE setting_key = %s",
            (key,)
        )
        conn.commit()
        cursor.close()
        
        # 删除 Redis 缓存
        if redis_ping():
            SystemConfig.delete(key)
        
        return True
    except Exception as e:
        print(f"[system_settings_dao] delete_setting 失败: {e}")
        return False
    finally:
        conn.close()


def get_all_settings() -> Dict[str, Dict[str, str]]:
    """
    获取所有配置项（从 MySQL）
    
    Returns:
        {key: {'value': str, 'description': str}} 字典
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT setting_key, setting_value, description FROM system_settings"
        )
        
        result = {}
        for key, value, desc in cursor.fetchall():
            result[key] = {
                'value': value,
                'description': desc or ''
            }
        cursor.close()
        return result
    except Exception as e:
        print(f"[system_settings_dao] get_all_settings 失败: {e}")
        return {}
    finally:
        conn.close()


def reload_cache() -> bool:
    """
    从 MySQL 重新加载所有配置到 Redis（启动时调用）
    
    Returns:
        是否成功
    """
    if not redis_ping():
        print("[system_settings_dao] Redis 不可用，跳过缓存预热")
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT setting_key, setting_value FROM system_settings"
        )
        
        settings = {}
        for key, value in cursor.fetchall():
            settings[key] = value
        cursor.close()
        
        if settings:
            SystemConfig.set_all(settings)
            print(f"[system_settings_dao] 已加载 {len(settings)} 个配置到 Redis")
        else:
            print("[system_settings_dao] MySQL 中无配置，使用默认值")
        
        return True
    except Exception as e:
        print(f"[system_settings_dao] reload_cache 失败: {e}")
        return False
    finally:
        conn.close()


def ensure_defaults() -> bool:
    """
    确保默认配置存在（仅写入 MySQL 中不存在的配置）
    
    Returns:
        是否成功
    """
    defaults = {
        'permission_min': ('1', '用户权限最小值'),
        'permission_max': ('10', '用户权限最大值'),
        'distill_rate': ('0.1', '蒸馏任务价格系数（相对于查询任务）'),
    }
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        for key, (value, description) in defaults.items():
            # 仅在不存在时插入
            cursor.execute(
                """
                INSERT IGNORE INTO system_settings (setting_key, setting_value, description)
                VALUES (%s, %s, %s)
                """,
                (key, value, description)
            )
        
        conn.commit()
        cursor.close()
        print("[system_settings_dao] 默认配置已确保存在")
        return True
    except Exception as e:
        print(f"[system_settings_dao] ensure_defaults 失败: {e}")
        return False
    finally:
        conn.close()


# ============================================================
# 便捷方法（带类型转换）
# ============================================================

def get_int_setting(key: str, default: int = 0) -> int:
    """获取整数类型配置"""
    value = get_setting(key)
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_float_setting(key: str, default: float = 0.0) -> float:
    """获取浮点数类型配置"""
    value = get_setting(key)
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_permission_range() -> Tuple[int, int]:
    """获取用户权限范围"""
    min_val = get_int_setting('permission_min', 1)
    max_val = get_int_setting('permission_max', 10)
    return (min_val, max_val)


def set_permission_range(min_val: int, max_val: int) -> bool:
    """设置用户权限范围"""
    if min_val < 0 or max_val < min_val:
        return False
    return (
        set_setting('permission_min', str(min_val), '用户权限最小值') and
        set_setting('permission_max', str(max_val), '用户权限最大值')
    )


def get_distill_rate() -> float:
    """获取蒸馏系数"""
    return get_float_setting('distill_rate', 0.1)


def set_distill_rate(rate: float) -> bool:
    """设置蒸馏系数"""
    if rate < 0 or rate > 1:
        return False
    return set_setting('distill_rate', str(rate), '蒸馏任务价格系数（相对于查询任务）')


