"""队列管理门面：根据配置选择 Redis 或 MySQL 实现（已无状态晋级流程）。"""
from __future__ import annotations
from typing import List, Dict, Optional
from ..config import config_loader as config
from ..load_data import db_reader
from . import redis_aggregates as agg

from . import queue_manager as mysql_q

# 尝试导入 Redis 版
try:
    from . import redis_queue_manager as redis_q
except Exception:  # 未安装 redis 或其他导入失败
    redis_q = None  # type: ignore


def _use_redis() -> bool:
    """是否启用 Redis 队列：要求配置开启且 Redis 健康(ping)。"""
    try:
        flag = bool(getattr(config, 'USE_REDIS_QUEUE', False))
    except Exception:
        flag = False
    if not (bool(flag) and (redis_q is not None)):
        return False
    # 健康检测，失败则不使用 Redis（回退 MySQL 实现）
    try:
        if hasattr(redis_q, 'redis_ping') and bool(redis_q.redis_ping()):  # type: ignore[attr-defined]
            return True
    except Exception:
        pass
    return False


def redis_enabled() -> bool:
    """是否实际使用 Redis（配置开启且健康）。"""
    return _use_redis()


def redis_ping() -> bool:
    try:
        if hasattr(redis_q, 'redis_ping'):
            return bool(redis_q.redis_ping())  # type: ignore[attr-defined]
    except Exception:
        return False
    return False


def is_operational() -> bool:
    """队列层是否可用：Redis 可用 或 MySQL 队列表存在。"""
    if _use_redis():
        return True
    try:
        from ..load_data import db_reader
        return bool(getattr(db_reader, '_task_table_ready')())  # type: ignore[attr-defined]
    except Exception:
        return False


# 统一导出接口

def enqueue_tasks_for_query(uid: int, query_index: int, dois: List[str]) -> int:
    # 入队前确保 Redis 中存在该 uid 的 permission 映射，避免 worker 侧频繁访问数据库
    try:
        uid_i = int(uid or 0)
        if uid_i > 0:
            perm_in_redis = int(agg.get_uid_permission(uid_i) or 0)  # type: ignore[attr-defined]
            if perm_in_redis <= 0:
                # 回退读取一次数据库（仅一次/uid），并写入 Redis 活跃集
                try:
                    info = db_reader.get_user_info_by_uid(uid_i) or {}
                    perm_db = int(info.get('permission') or 0)
                except Exception:
                    perm_db = 0
                if perm_db > 0:
                    try:
                        agg.add_or_update_active_uid(uid_i, perm_db)  # type: ignore[attr-defined]
                    except Exception:
                        pass
    except Exception:
        pass
    if _use_redis():
        try:
            return int(redis_q.enqueue_tasks_for_query(uid, query_index, dois))  # type: ignore
        except Exception:
            pass
    return int(mysql_q.enqueue_tasks_for_query(uid, query_index, dois))




# 已移除直接弹出接口：统一使用 peek_head_for_user + conditional_pop 保证门控与 FIFO 原子性


def push_back_ready(task_id: int) -> bool:
    if _use_redis():
        try:
            return bool(redis_q.push_back_ready(task_id))  # type: ignore
        except Exception:
            pass
    return bool(mysql_q.push_back_ready(task_id))


def mark_done(task_id: int) -> bool:
    if _use_redis():
        try:
            return bool(redis_q.mark_done(task_id))  # type: ignore
        except Exception:
            pass
    return bool(mysql_q.mark_done(task_id))


def mark_failed(task_id: int, reason: str = "") -> bool:
    if _use_redis():
        try:
            return bool(redis_q.mark_failed(task_id, reason))  # type: ignore
        except Exception:
            pass
    return bool(mysql_q.mark_failed(task_id, reason))


def backlog_stats() -> Dict:
    if _use_redis():
        try:
            return dict(redis_q.backlog_stats())  # type: ignore
        except Exception:
            pass
    return dict(mysql_q.backlog_stats())


def total_backlog() -> int:
    if _use_redis():
        try:
            return int(redis_q.total_backlog())  # type: ignore
        except Exception:
            pass
    return int(mysql_q.total_backlog())


def user_backlog_size(uid: int) -> int:
    if _use_redis():
        try:
            return int(redis_q.user_backlog_size(uid))  # type: ignore
        except Exception:
            pass
    return int(mysql_q.user_backlog_size(uid))


def peek_head_for_user(uid: int) -> Optional[Dict]:
    """查看指定用户队列头（不弹出）。"""
    if _use_redis():
        try:
            return redis_q.peek_head_for_user(uid)  # type: ignore
        except Exception:
            pass
    return mysql_q.peek_head_for_user(uid)


def conditional_pop(task_id: int, uid: int) -> Optional[Dict]:
    """仅当 task 为该用户队头时，原子弹出并转 running，返回任务；否则 None。"""
    if _use_redis():
        try:
            return redis_q.conditional_pop(task_id, uid)  # type: ignore
        except Exception:
            pass
    return mysql_q.conditional_pop(task_id, uid)
