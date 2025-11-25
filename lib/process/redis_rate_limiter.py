"""
Redis 版限流器（Stage3）
- 使用分钟窗口计数键：
  apw:rl:{account}:rpm:{yyyyMMddHHmm} -> int（本分钟已用请求数）
  apw:rl:{account}:tpm:{yyyyMMddHHmm} -> int（本分钟已用tokens）
- 原子性：Lua 脚本一次性判定并递增。
- 回退：Redis 不可用时，上层应回退至 MySQL 版；本模块也提供软失败（返回 True, None）。
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple
from datetime import datetime

try:
    import redis  # type: ignore
except Exception:
    redis = None  # type: ignore

from ..load_data import db_reader
from ..config import config_loader as config


_LUA_ACQUIRE = """
local rpm_key = KEYS[1]
local tpm_key = KEYS[2]
local rpm_limit = tonumber(ARGV[1])
local tpm_limit = tonumber(ARGV[2])
local tokens = tonumber(ARGV[3])
-- 读取当前值
local used_req = tonumber(redis.call('GET', rpm_key) or '0')
local used_tok = tonumber(redis.call('GET', tpm_key) or '0')
if used_req + 1 > rpm_limit then return 0 end
if used_tok + tokens > tpm_limit then return 0 end
-- 通过校验，分别自增并设置TTL（90s）
used_req = redis.call('INCR', rpm_key)
used_tok = redis.call('INCRBY', tpm_key, tokens)
redis.call('PEXPIRE', rpm_key, 90000)
redis.call('PEXPIRE', tpm_key, 90000)
return 1
"""


def _get_redis_client():
    if redis is None:
        return None
    # 单一真源：使用 config.REDIS_URL，不再读取环境变量
    url = getattr(config, 'REDIS_URL', '') or ''
    try:
        if not url:
            return None
        return redis.Redis.from_url(url, decode_responses=True)
    except Exception:
        return None


def redis_ping() -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False


def _minute_key(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.utcnow()
    return dt.strftime('%Y%m%d%H%M')


def calc_effective_capacity_per_min(tokens_per_req: int) -> Dict:
    """依然基于 MySQL 账户配置计算有效容量（近似）。"""
    try:
        from . import rate_limiter as mysql_rl  # 直接复用已有逻辑
        return mysql_rl.calc_effective_capacity_per_min(tokens_per_req)
    except Exception:
        return {"accounts": 0, "effective_req_per_min": 0}


def try_acquire_for_any_account(tokens: int) -> Tuple[bool, Optional[Dict]]:
    r = _get_redis_client()
    if not r:
        # 无 Redis 时放行，交由上层回退
        return True, None
    try:
        accounts = db_reader.get_active_api_accounts() or []
        if not accounts:
            return True, None
        # 简单挑选：随机两选由数据库层处理，这里直接按顺序尝试即可（实现简化）
        minute = _minute_key()
        for a in accounts:
            aname = a.get('api_name') or str(a.get('api_index'))
            rpm = int(a.get('rpm_limit') or 0) or 30000
            tpm = int(a.get('tpm_limit') or 0) or 5000000
            keys = [f"apw:rl:{aname}:rpm:{minute}", f"apw:rl:{aname}:tpm:{minute}"]
            try:
                ok = r.eval(_LUA_ACQUIRE, 2, *keys, rpm, tpm, int(tokens or 0))
            except Exception:
                ok = 0
            if int(ok or 0) == 1:
                return True, a
        return False, None
    except Exception:
        return True, None
