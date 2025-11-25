"""
MySQL 版队列管理（Stage2）
- 依赖 lib.load_data.db_reader 中的 task_queue CRUD
- 提供更高层封装，便于 paper_processor 调用
- 若表不存在或功能关闭，方法返回保守值而不抛异常
"""
from __future__ import annotations
from typing import List, Dict, Optional
from datetime import datetime

from ..load_data import db_reader


def enqueue_tasks_for_query(uid: int, query_index: int, dois: List[str]) -> int:
    """批量将 DOI 入队到 task_queue（直接 state=ready）。表不存在时返回 0。"""
    try:
        rows = [
            {"uid": int(uid or 0), "query_index": int(query_index or 0), "doi": str(d or "")} for d in (dois or [])
            if d
        ]
        return db_reader.enqueue_ready_bulk(rows)
    except Exception:
        return 0




# 已移除：直接弹出接口，使用 peek_head_for_user + conditional_pop


def push_back_ready(task_id: int) -> bool:
    try:
        return db_reader.push_back_ready(int(task_id or 0))
    except Exception:
        return False


def mark_done(task_id: int) -> bool:
    try:
        return db_reader.mark_done(int(task_id or 0))
    except Exception:
        return False


def mark_failed(task_id: int, reason: str = "") -> bool:
    try:
        return db_reader.mark_failed(int(task_id or 0), str(reason or ""))
    except Exception:
        return False


def backlog_stats() -> Dict:
    """返回最小可视化指标：总待处理、每用户上限聚合（近似）。"""
    try:
        total = db_reader.backlog_size()
    except Exception:
        total = 0
    try:
        # 聚合所有活跃用户的 permission 之和，作为吞吐上限近似
        uids = db_reader.list_uids_with_pending_tasks()
        # list_uids_with_pending_tasks 返回 set，需转为 list 以便 JSON 序列化
        if isinstance(uids, set):
            uids_list = list(sorted(uids))  # 排序保证稳定性
        else:
            uids_list = list(uids or [])
        cap = db_reader.sum_permissions_for_uids(uids_list)
    except Exception:
        uids_list = []
        cap = 0
    return {"backlog": int(total or 0), "active_uids": uids_list, "user_capacity_sum": int(cap or 0)}


def total_backlog() -> int:
    """返回队列总待处理任务数（MySQL 版）。"""
    try:
        return int(db_reader.backlog_size() or 0)
    except Exception:
        return 0


def user_backlog_size(uid: int) -> int:
    """返回指定用户待处理任务数（MySQL 版）。"""
    try:
        return int(db_reader.user_backlog_size(int(uid or 0)) or 0)
    except Exception:
        return 0


def peek_head_for_user(uid: int) -> Optional[Dict]:
    """查看用户 ready 队列的队头（不弹出）。"""
    try:
        # 复用 pop SQL 结构，改为不更新状态
        conn = db_reader._get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT id, query_index, doi FROM task_queue
                    WHERE uid=%s AND state='ready'
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (int(uid or 0),)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return {'task_id': row['id'], 'uid': int(uid or 0), 'query_index': row['query_index'], 'doi': row['doi']}
        finally:
            conn.close()
    except Exception:
        return None


def conditional_pop(task_id: int, uid: int) -> Optional[Dict]:
    """仅当任务仍为该用户队头时，将其转为 running 并返回任务；否则返回 None。"""
    try:
        conn = db_reader._get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                conn.start_transaction()
                cursor.execute(
                    """
                    SELECT id, query_index, doi FROM task_queue
                    WHERE uid=%s AND state='ready'
                    ORDER BY id ASC
                    LIMIT 1 FOR UPDATE
                    """,
                    (int(uid or 0),)
                )
                head = cursor.fetchone()
                if (not head) or int(head['id']) != int(task_id or 0):
                    conn.rollback()
                    return None
                cursor.execute(
                    "UPDATE task_queue SET state='running', running_since=NOW(2) WHERE id=%s",
                    (int(task_id or 0),)
                )
                conn.commit()
                return {'task_id': head['id'], 'uid': int(uid or 0), 'query_index': head['query_index'], 'doi': head['doi']}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return None
        finally:
            conn.close()
    except Exception:
        return None
