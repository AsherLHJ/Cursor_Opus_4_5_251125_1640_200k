"""
Redis 聚合键管理模块（Stage5）

负责维护以下键：
- apw:tokens_per_req (int)
- apw:api_tpm_total (int)
- apw:active_uids (set)
- apw:uid:perm:{uid} (int)
- apw:perm_sum_active (int)
- apw:max_capacity_per_min (float)  # 系统最大容量（篇/分钟，req/min）= api_tpm_total / tokens_per_req
- apw:running_tasks_count (int)     # 正在执行中的任务数量（分布式计数）
- apw:running_perm_sum (int)        # 正在执行中的任务对应用户 permission 求和
- apw:occupied_capacity_per_min (float)  # 已占用容量（篇/分钟，req/min）= running_perm_sum
- apw:remaining_capacity_per_min (float) # 剩余容量（篇/分钟，req/min）= max_capacity_per_min - occupied_capacity_per_min

注意：本模块仅提供最小必要的读写与增量维护函数；
复杂的初始化/校验由 scheduler 周期任务补全。
"""
from __future__ import annotations
from typing import Optional

try:
    import redis  # type: ignore
except Exception:  # 允许未安装时被安全导入
    redis = None  # type: ignore

from ..config import config_loader as config


def _get_redis_client() -> Optional[object]:
    if redis is None:
        return None
    url = getattr(config, 'REDIS_URL', '') or ''
    if not url:
        return None
    try:
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


# -------------------------
# 基础 get/set 助手
# -------------------------

def set_tokens_per_req(val: int) -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        r.set("apw:tokens_per_req", int(val or 0))
        return True
    except Exception:
        return False


def get_tokens_per_req(default: int = 0) -> int:
    r = _get_redis_client()
    if not r:
        return int(default or 0)
    try:
        v = r.get("apw:tokens_per_req")
        return int(v) if v is not None else int(default or 0)
    except Exception:
        return int(default or 0)


def set_api_tpm_total(val: int) -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        r.set("apw:api_tpm_total", int(val or 0))
        return True
    except Exception:
        return False


def get_api_tpm_total(default: int = 0) -> int:
    r = _get_redis_client()
    if not r:
        return int(default or 0)
    try:
        v = r.get("apw:api_tpm_total")
        return int(v) if v is not None else int(default or 0)
    except Exception:
        return int(default or 0)


def get_perm_sum_active() -> int:
    r = _get_redis_client()
    if not r:
        return 0
    try:
        v = r.get("apw:perm_sum_active")
        return int(v) if v is not None else 0
    except Exception:
        return 0


# -------------------------
# 兼容旧版（effective_capacity）占位：不再使用
# 保留仅为兼容旧代码路径调用，不再写入真实业务含义
# -------------------------
def set_effective_capacity(val: float) -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        # 兼容旧键，仍然写入但不再被读取使用
        r.set("apw:effective_capacity", float(val or 0.0))
        return True
    except Exception:
        return False


def get_effective_capacity(default: float = 0.0) -> float:
    r = _get_redis_client()
    if not r:
        return float(default or 0.0)
    try:
        v = r.get("apw:effective_capacity")
        return float(v) if v is not None else float(default or 0.0)
    except Exception:
        return float(default or 0.0)


def get_uid_permission(uid: int) -> int:
    """读取单个 uid 的权限值（若不存在返回 0）。"""
    r = _get_redis_client()
    if not r or int(uid or 0) <= 0:
        return 0
    try:
        v = r.get(f"apw:uid:perm:{int(uid)}")
        return int(v) if v is not None else 0
    except Exception:
        return 0


# -------------------------
# active_uids 与 permission 维护
# -------------------------

def add_or_update_active_uid(uid: int, permission: int) -> bool:
    """将 uid 加入 active_uids，并设置 apw:uid:perm:{uid}；
    - 若新加入：perm_sum_active += permission
    - 若已存在：若权限变化，则 perm_sum_active += (new - old)
    """
    r = _get_redis_client()
    if not r or int(uid or 0) <= 0:
        return False
    uid = int(uid)
    perm = int(permission or 0)
    try:
        pipe = r.pipeline()
        key_perm = f"apw:uid:perm:{uid}"
        pipe.sismember("apw:active_uids", str(uid))
        pipe.get(key_perm)
        existed, old_perm = pipe.execute()

        # 更新权限缓存
        r.set(key_perm, perm)

        if not bool(existed):
            # 新增：加入集合并累加
            pipe = r.pipeline()
            pipe.sadd("apw:active_uids", str(uid))
            if perm != 0:
                pipe.incrby("apw:perm_sum_active", perm)
            pipe.execute()
        else:
            try:
                old = int(old_perm) if old_perm is not None else 0
            except Exception:
                old = 0
            delta = perm - old
            if delta != 0:
                r.incrby("apw:perm_sum_active", delta)
        return True
    except Exception:
        return False


def remove_active_uid(uid: int) -> bool:
    """将 uid 从 active_uids 移除，且 perm_sum_active -= uid:perm（若存在）。"""
    r = _get_redis_client()
    if not r or int(uid or 0) <= 0:
        return False
    uid = int(uid)
    try:
        key_perm = f"apw:uid:perm:{uid}"
        pipe = r.pipeline()
        pipe.get(key_perm)
        pipe.srem("apw:active_uids", str(uid))
        old_perm, removed = pipe.execute()
        try:
            perm = int(old_perm) if old_perm is not None else 0
        except Exception:
            perm = 0
        if int(removed or 0) > 0 and perm != 0:
            try:
                r.incrby("apw:perm_sum_active", -perm)
            except Exception:
                pass
        try:
            r.delete(key_perm)
        except Exception:
            pass
        return True
    except Exception:
        return False


# -------------------------
# 新版容量计算：max/occupied/remaining（篇/分钟）
# -------------------------

def set_max_capacity_per_min(val: float) -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        r.set("apw:max_capacity_per_min", float(val or 0.0))
        return True
    except Exception:
        return False


def get_max_capacity_per_min(default: float = 0.0) -> float:
    r = _get_redis_client()
    if not r:
        return float(default or 0.0)
    try:
        v = r.get("apw:max_capacity_per_min")
        return float(v) if v is not None else float(default or 0.0)
    except Exception:
        return float(default or 0.0)


def compute_and_set_max_capacity_per_min() -> float:
    """计算并写入 apw:max_capacity_per_min。
    max_capacity = api_tpm_total / tokens_per_req
    """
    r = _get_redis_client()
    if not r:
        return 0.0
    try:
        tpr = get_tokens_per_req(0)
        api_tpm = get_api_tpm_total(0)
        if tpr <= 0 or api_tpm <= 0:
            set_max_capacity_per_min(0.0)
            return 0.0
        mx = float(api_tpm) / float(max(tpr, 1))
        set_max_capacity_per_min(mx)
        return float(mx)
    except Exception:
        try:
            set_max_capacity_per_min(0.0)
        except Exception:
            pass
        return 0.0


# 运行中任务统计（分布式）
def get_running_tasks_count() -> int:
    r = _get_redis_client()
    if not r:
        return 0
    try:
        v = r.get("apw:running_tasks_count")
        return int(v) if v is not None else 0
    except Exception:
        return 0


def get_running_perm_sum() -> int:
    r = _get_redis_client()
    if not r:
        return 0
    try:
        v = r.get("apw:running_perm_sum")
        return int(v) if v is not None else 0
    except Exception:
        return 0


def incr_running_stats(perm: int) -> bool:
    r = _get_redis_client()
    if not r:
        return False


def incr_running_for_uid(uid: int, perm: int) -> bool:
    """为指定 uid 增加一个运行中任务计数；
    当该 uid 从 0 -> 1 时，才将其 permission 计入 running_perm_sum。
    无论如何，running_tasks_count 总体计数都会 +1。
    """
    r = _get_redis_client()
    if not r or int(uid or 0) <= 0:
        return False
    try:
        uid_key = f"apw:uid:running_count:{int(uid)}"
        # 先增加全局运行任务数
        try:
            r.incr("apw:running_tasks_count")
        except Exception:
            pass
        # 再增加该 uid 的运行计数，并根据返回值判断是否第一次从 0 -> 1
        new_cnt = 0
        try:
            new_cnt = int(r.incr(uid_key) or 0)
        except Exception:
            new_cnt = 0
        if new_cnt == 1 and int(perm or 0) != 0:
            try:
                r.incrby("apw:running_perm_sum", int(perm))
            except Exception:
                pass
        return True
    except Exception:
        return False
    try:
        p = int(perm or 0)
        pipe = r.pipeline()
        pipe.incr("apw:running_tasks_count")
        if p != 0:
            pipe.incrby("apw:running_perm_sum", p)
        pipe.execute()
        return True
    except Exception:
        return False


def decr_running_stats(perm: int) -> bool:
    r = _get_redis_client()
    if not r:
        return False


def decr_running_for_uid(uid: int, perm: int) -> bool:
    """为指定 uid 减少一个运行中任务计数；
    当该 uid 计数从 1 -> 0 时，才将其 permission 从 running_perm_sum 中扣除。
    无论如何，running_tasks_count 总体计数都会 -1。
    """
    r = _get_redis_client()
    if not r or int(uid or 0) <= 0:
        return False
    try:
        uid_key = f"apw:uid:running_count:{int(uid)}"
        # 先减少全局运行任务数
        try:
            r.decr("apw:running_tasks_count")
        except Exception:
            pass
        # 再减少该 uid 的运行计数，并根据返回值判断是否从 1 -> 0
        new_cnt = 0
        try:
            new_cnt = int(r.decr(uid_key) or 0)
        except Exception:
            new_cnt = 0
        if new_cnt < 0:
            try:
                r.set(uid_key, 0)
            except Exception:
                pass
            new_cnt = 0
        if new_cnt == 0 and int(perm or 0) != 0:
            try:
                r.decrby("apw:running_perm_sum", int(perm))
            except Exception:
                pass
        # 防御性修正：避免负数
        try:
            cnt = int(r.get("apw:running_tasks_count") or 0)
            if cnt < 0:
                r.set("apw:running_tasks_count", 0)
        except Exception:
            pass
        try:
            s = int(r.get("apw:running_perm_sum") or 0)
            if s < 0:
                r.set("apw:running_perm_sum", 0)
        except Exception:
            pass
        return True
    except Exception:
        return False
    try:
        p = int(perm or 0)
        pipe = r.pipeline()
        pipe.decr("apw:running_tasks_count")
        if p != 0:
            pipe.decrby("apw:running_perm_sum", p)
        res = pipe.execute()
        # 防御性修正：避免负数
        try:
            cnt = int(r.get("apw:running_tasks_count") or 0)
            if cnt < 0:
                r.set("apw:running_tasks_count", 0)
        except Exception:
            pass
        try:
            s = int(r.get("apw:running_perm_sum") or 0)
            if s < 0:
                r.set("apw:running_perm_sum", 0)
        except Exception:
            pass
        return True
    except Exception:
        return False


def set_occupied_capacity_per_min(val: float) -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        r.set("apw:occupied_capacity_per_min", float(val or 0.0))
        return True
    except Exception:
        return False


def get_occupied_capacity_per_min(default: float = 0.0) -> float:
    r = _get_redis_client()
    if not r:
        return float(default or 0.0)
    try:
        v = r.get("apw:occupied_capacity_per_min")
        return float(v) if v is not None else float(default or 0.0)
    except Exception:
        return float(default or 0.0)


def set_remaining_capacity_per_min(val: float) -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        r.set("apw:remaining_capacity_per_min", float(val or 0.0))
        return True
    except Exception:
        return False


def get_remaining_capacity_per_min(default: float = 0.0) -> float:
    r = _get_redis_client()
    if not r:
        return float(default or 0.0)
    try:
        v = r.get("apw:remaining_capacity_per_min")
        return float(v) if v is not None else float(default or 0.0)
    except Exception:
        return float(default or 0.0)


def compute_and_set_remaining_capacity_per_min() -> float:
    """根据当前运行中任务的 permission 求和计算 occupied 与 remaining（单位：篇/分钟，req/min）。

    统一单位为 req/min：
    - max_capacity_per_min = api_tpm_total / tokens_per_req
    - occupied_capacity_per_min = running_perm_sum
    - remaining_capacity_per_min = max - occupied
    """
    r = _get_redis_client()
    if not r:
        return 0.0
    try:
        mx = get_max_capacity_per_min(0.0)
        running_sum = get_running_perm_sum()
        if mx <= 0:
            set_occupied_capacity_per_min(0.0)
            set_remaining_capacity_per_min(0.0)
            return 0.0
        # 占用等于运行中任务的 permission 求和（req/min）
        occupied = float(max(0, int(running_sum or 0)))
        remaining = float(mx) - float(occupied)
        if remaining < 0:
            remaining = 0.0
        set_occupied_capacity_per_min(occupied)
        set_remaining_capacity_per_min(remaining)
        return float(remaining)
    except Exception:
        try:
            set_occupied_capacity_per_min(0.0)
            set_remaining_capacity_per_min(0.0)
        except Exception:
            pass
        return 0.0
