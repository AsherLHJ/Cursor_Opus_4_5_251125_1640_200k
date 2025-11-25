"""
限流器门面：根据开关选择 Redis 或 MySQL 实现。
- 单一真源：lib.config.config_loader（config.json）中的 USE_REDIS_RATELIMITER
- 不再读取环境变量兜底，避免掩盖配置问题；若 Redis 版不可用，回退到 MySQL 版。
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple
from ..config import config_loader as config

from . import rate_limiter as mysql_rl

try:
    from . import redis_rate_limiter as redis_rl
except Exception:
    redis_rl = None  # type: ignore


def _use_redis() -> bool:
    """是否启用 Redis 限流：要求配置开启且 Redis 健康(ping)。"""
    try:
        flag = bool(getattr(config, 'USE_REDIS_RATELIMITER', False))
    except Exception:
        flag = False
    if not (bool(flag) and (redis_rl is not None)):
        return False
    try:
        if hasattr(redis_rl, 'redis_ping') and bool(redis_rl.redis_ping()):  # type: ignore[attr-defined]
            return True
    except Exception:
        pass
    return False


def redis_enabled() -> bool:
    return _use_redis()


def redis_ping() -> bool:
    try:
        if hasattr(redis_rl, 'redis_ping'):
            return bool(redis_rl.redis_ping())  # type: ignore[attr-defined]
    except Exception:
        return False
    return False


def calc_effective_capacity_per_min(tokens_per_req: int) -> Dict:
    """兼容旧接口：返回 {'effective_req_per_min': max_capacity, 'accounts': <count>}。
    实际含义已转为系统最大容量（max_capacity_per_min）。
    """
    if _use_redis():
        try:
            return dict(redis_rl.calc_effective_capacity_per_min(tokens_per_req))  # type: ignore
        except Exception:
            pass
    return dict(mysql_rl.calc_effective_capacity_per_min(tokens_per_req))


def calc_max_capacity_per_min(tokens_per_req: int) -> Dict:
    """新的显式接口：返回与旧 calc_effective_capacity_per_min 相同结构，用于前端/后端迁移。
    字段含义：effective_req_per_min == max_capacity_per_min。
    """
    return calc_effective_capacity_per_min(tokens_per_req)


def try_acquire_for_any_account(tokens: int) -> Tuple[bool, Optional[Dict]]:
    if _use_redis():
        try:
            return redis_rl.try_acquire_for_any_account(tokens)  # type: ignore
        except Exception:
            pass
    return mysql_rl.try_acquire_for_any_account(tokens)
