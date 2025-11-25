"""Redis 队列管理（简化：直接 ready 阶段）"""
from __future__ import annotations
from typing import List, Dict, Optional
import time

try:
    import redis  # type: ignore
except Exception:  # 允许未安装时被安全导入
    redis = None  # type: ignore

from ..load_data import db_reader
from ..config import config_loader as config


def _get_redis_client() -> Optional[object]:
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


def enqueue_tasks_for_query(uid: int, query_index: int, dois: List[str]) -> int:
    r = _get_redis_client()
    if not r:
        return 0
    now = time.time()
    pipe = r.pipeline()
    count = 0
    try:
        for d in (dois or []):
            d = (d or "").strip()
            if not d:
                continue
            task_id = r.incr("apw:q:task_id")
            key_task = f"apw:q:task:{task_id}"
            # 直接入就绪队列（Stage3 简化：不再使用 waiting -> ready 提升流程）
            pipe.hset(key_task, mapping={
                "uid": int(uid or 0),
                "query_index": int(query_index or 0),
                "doi": d,
                "state": "ready",
                "created_at": int(now),
            })
            ready_key = f"apw:q:ready:uid:{int(uid or 0)}"
            pipe.zadd(ready_key, {str(task_id): now})
            pipe.zadd("apw:q:ready:uids", {str(int(uid or 0)): now})
            count += 1
        pipe.execute()
        return count
    except Exception:
        try:
            pipe.reset()
        except Exception:
            pass
        return 0




# 已移除：直接弹出接口，统一通过 peek_head_for_user + conditional_pop 实现原子领取


def peek_head_for_user(uid: int) -> Optional[Dict]:
    """查看用户就绪队列队头但不弹出。"""
    r = _get_redis_client()
    if not r:
        return None
    ready_key = f"apw:q:ready:uid:{int(uid or 0)}"
    try:
        top = r.zrange(ready_key, 0, 0, withscores=False)
        if not top:
            # 若该 uid 队列空，从 ready:uids 移除
            try:
                if r.zcard(ready_key) == 0:
                    r.zrem("apw:q:ready:uids", str(int(uid or 0)))
            except Exception:
                pass
            return None
        tid = top[0]
        key_task = f"apw:q:task:{tid}"
        info = r.hgetall(key_task) or {}
        if not info:
            return None
        return {
            "task_id": int(tid),
            "uid": int(info.get("uid") or 0),
            "query_index": int(info.get("query_index") or 0),
            "doi": info.get("doi") or "",
        }
    except Exception:
        return None


def conditional_pop(task_id: int, uid: int) -> Optional[Dict]:
    """仅当 task_id 仍是该 uid 队列头时，原子地弹出并转为 running，返回任务体；否则返回 None。
    使用 Lua 保证原子性。
    """
    r = _get_redis_client()
    if not r:
        return None
    ready_key = f"apw:q:ready:uid:{int(uid or 0)}"
    key_task = f"apw:q:task:{int(task_id or 0)}"
    lua = """
    local ready = KEYS[1]
    local taskKey = KEYS[2]
    local targetId = ARGV[1]
    -- 取队头 ID
    local head = redis.call('ZRANGE', ready, 0, 0)
    if head == nil or #head == 0 then
        return {0}
    end
    if head[1] ~= targetId then
        return {0}
    end
    -- 弹出队头
    local popped = redis.call('ZPOPMIN', ready, 1)
    if popped == nil or #popped == 0 then
        return {0}
    end
    -- 标记 running
    redis.call('HSET', taskKey, 'state', 'running')
    return {1}
    """
    try:
        res = r.eval(lua, 2, ready_key, key_task, str(int(task_id or 0)))
        if isinstance(res, list) and len(res) >= 1 and int(res[0] or 0) == 1:
            info = r.hgetall(key_task) or {}
            if not info:
                return None
            return {
                "task_id": int(task_id),
                "uid": int(info.get("uid") or 0),
                "query_index": int(info.get("query_index") or 0),
                "doi": info.get("doi") or "",
            }
        return None
    except Exception:
        return None


def push_back_ready(task_id: int) -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        key_task = f"apw:q:task:{int(task_id or 0)}"
        info = r.hgetall(key_task) or {}
        uid = int(info.get("uid") or 0)
        if uid <= 0:
            return False
        ready_key = f"apw:q:ready:uid:{uid}"
        now = time.time()
        r.zadd(ready_key, {str(int(task_id or 0)): now})
        r.zadd("apw:q:ready:uids", {str(uid): now})
        r.hset(key_task, "state", "ready")
        return True
    except Exception:
        return False


def mark_done(task_id: int) -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        key_task = f"apw:q:task:{int(task_id or 0)}"
        info = r.hgetall(key_task) or {}
        uid = int(info.get("uid") or 0)
        r.hset(key_task, "state", "done")
        # 从 ready 队列中删除残留
        if uid > 0:
            r.zrem(f"apw:q:ready:uid:{uid}", str(int(task_id or 0)))
        # 也可以删除任务体避免堆积
        r.delete(key_task)
        return True
    except Exception:
        return False


def mark_failed(task_id: int, reason: str = "") -> bool:
    r = _get_redis_client()
    if not r:
        return False
    try:
        key_task = f"apw:q:task:{int(task_id or 0)}"
        r.hset(key_task, mapping={"state": "failed", "error": reason or ""})
        return True
    except Exception:
        return False


def total_backlog() -> int:
    r = _get_redis_client()
    if not r:
        return 0
    try:
        w = int(r.zcard("apw:q:waiting") or 0)
        total = w
        # 叠加各 uid ready 队列
        try:
            uids = [int(u) for u in (r.zrange("apw:q:ready:uids", 0, -1) or [])]
        except Exception:
            uids = []
        for uid in uids:
            total += int(r.zcard(f"apw:q:ready:uid:{uid}") or 0)
        return int(total)
    except Exception:
        return 0


def user_backlog_size(uid: int) -> int:
    r = _get_redis_client()
    if not r:
        return 0
    try:
        return int(r.zcard(f"apw:q:ready:uid:{int(uid or 0)}") or 0) + 0  # waiting 队列不区分用户
    except Exception:
        return 0


def backlog_stats() -> Dict:
    try:
        total = total_backlog()
    except Exception:
        total = 0
    # active_uids 从 ready:uids 读取
    r = _get_redis_client()
    uids = []
    try:
        if r:
            uids = [int(u) for u in (r.zrange("apw:q:ready:uids", 0, -1) or [])]
    except Exception:
        uids = []
    try:
        cap = db_reader.sum_permissions_for_uids(uids)
    except Exception:
        cap = 0
    return {"backlog": int(total or 0), "active_uids": uids, "user_capacity_sum": int(cap or 0)}
