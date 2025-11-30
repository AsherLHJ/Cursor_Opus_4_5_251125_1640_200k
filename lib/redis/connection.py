"""
Redis连接管理模块
提供统一的Redis连接获取和管理功能
"""

from typing import Optional
import threading

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore
    REDIS_AVAILABLE = False

# 线程局部存储
_thread_local = threading.local()

# 全局Redis客户端（连接池）
_global_client: Optional[object] = None
_global_lock = threading.Lock()


def _get_redis_url() -> str:
    """获取Redis URL"""
    try:
        from ..config import config_loader as config
        
        # 直接使用 config_loader 中已解析的 REDIS_URL
        redis_url = getattr(config, 'REDIS_URL', '')
        if redis_url:
            return redis_url
        
        # 回退到默认值
        local_mode = getattr(config, 'local_develop_mode', True)
        if local_mode:
            return 'redis://localhost:6379/0'
        else:
            return ''
    except Exception:
        return 'redis://localhost:6379/0'


def get_redis_client() -> Optional[object]:
    """
    获取Redis客户端（线程安全，使用连接池）
    
    Returns:
        Redis客户端实例，或None（如果不可用）
    """
    global _global_client
    
    if not REDIS_AVAILABLE:
        return None
    
    url = _get_redis_url()
    if not url:
        return None
    
    # 双重检查锁定
    if _global_client is None:
        with _global_lock:
            if _global_client is None:
                try:
                    _global_client = redis.Redis.from_url(
                        url,
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5,
                        retry_on_timeout=True,
                    )
                except Exception as e:
                    print(f"[Redis] 连接失败: {e}")
                    return None
    
    return _global_client


def redis_ping() -> bool:
    """检查Redis连接是否可用"""
    client = get_redis_client()
    if not client:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


def close_redis() -> None:
    """关闭Redis连接"""
    global _global_client
    with _global_lock:
        if _global_client is not None:
            try:
                _global_client.close()
            except Exception:
                pass
            _global_client = None


def execute_lua_script(script: str, keys: list, args: list) -> Optional[any]:
    """
    执行Lua脚本（用于原子操作）
    
    Args:
        script: Lua脚本内容
        keys: KEYS列表
        args: ARGV列表
        
    Returns:
        脚本执行结果
    """
    client = get_redis_client()
    if not client:
        return None
    try:
        lua = client.register_script(script)
        return lua(keys=keys, args=args)
    except Exception as e:
        print(f"[Redis] Lua脚本执行失败: {e}")
        return None


# TTL常量
TTL_USER_INFO = 8 * 3600        # 用户信息缓存: 8小时
TTL_USER_BALANCE = 8 * 3600     # 用户余额缓存: 8小时
TTL_ADMIN_SESSION = 24 * 3600   # 管理员会话: 24小时
TTL_RESULT = 7 * 24 * 3600      # 查询结果缓存: 7天
# 文献Block: 永不过期（已移除TTL_PAPER_BLOCK常量）

