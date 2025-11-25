"""
队列管理数据访问对象
处理task_queue和api_usage_minute表相关操作
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from .db_base import _get_connection, _table_exists


def _task_table_ready() -> bool:
    """检查任务队列表是否存在"""
    return _table_exists('task_queue')


def enqueue_ready(uid: int, query_index: int, doi: str, 
                  eta_start_at: Optional[datetime] = None) -> bool:
    """添加就绪任务（直接 ready，已无 waiting/promote 流程）"""
    if not _task_table_ready():
        return False
    if not doi or not query_index:
        return False
    
    conn = _get_connection()
    try:
        eta = (eta_start_at or datetime.utcnow()).replace(microsecond=0)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO task_queue(uid, query_index, doi, state, eta_start_at, attempt_count)
                VALUES (%s, %s, %s, 'ready', %s, 0)
                """,
                (int(uid or 0), int(query_index), str(doi), eta)
            )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def enqueue_ready_bulk(rows: List[Dict]) -> int:
    """批量添加就绪任务（直接 ready）"""
    if not _task_table_ready():
        return 0
    if not rows:
        return 0
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            vals = []
            for r in rows:
                uid = int(r.get('uid', 0) or 0)
                qidx = int(r.get('query_index') or 0)
                doi = str(r.get('doi') or '')
                if not doi or qidx <= 0:
                    continue
                eta = r.get('eta_start_at') or datetime.utcnow()
                eta = eta.replace(microsecond=0)
                vals.append((uid, qidx, doi, eta))
            
            if not vals:
                return 0
            
            cursor.executemany(
                """
                INSERT INTO task_queue(uid, query_index, doi, state, eta_start_at, attempt_count)
                VALUES (%s, %s, %s, 'ready', %s, 0)
                """,
                vals
            )
        conn.commit()
        return len(vals)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()




# 已移除：直接弹出接口，统一通过 peek_head_for_user + conditional_pop 实现原子领取


def push_back_ready(task_id: int) -> bool:
    """将任务推回就绪状态"""
    if not _task_table_ready() or not task_id:
        return False
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE task_queue SET state='ready', running_since=NULL WHERE id=%s",
                (int(task_id),)
            )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def mark_done(task_id: int) -> bool:
    """标记任务完成"""
    if not _task_table_ready() or not task_id:
        return False
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE task_queue SET state='done' WHERE id=%s", (int(task_id),))
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def mark_failed(task_id: int, reason: str = "") -> bool:
    """标记任务失败"""
    if not _task_table_ready() or not task_id:
        return False
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE task_queue SET state='failed', last_error=%s WHERE id=%s", 
                (reason, int(task_id))
            )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def backlog_size() -> int:
    """获取积压任务数量"""
    if not _task_table_ready():
        return 0
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM task_queue WHERE state='ready'")
            (cnt,) = cursor.fetchone() or (0,)
            return int(cnt or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def user_backlog_size(uid: int) -> int:
    """获取用户积压任务数量"""
    if not _task_table_ready():
        return 0
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM task_queue WHERE uid=%s AND state='ready'", 
                (int(uid or 0),)
            )
            (cnt,) = cursor.fetchone() or (0,)
            return int(cnt or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def upsert_api_usage_minute(account_name: str, minute_ts: datetime, 
                           used_req_inc: int, used_tokens_inc: int) -> bool:
    """更新API使用统计"""
    if not _table_exists('api_usage_minute'):
        return False
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO api_usage_minute(account_name, minute_ts, used_req, used_tokens)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    used_req = used_req + VALUES(used_req), 
                    used_tokens = used_tokens + VALUES(used_tokens)
                """,
                (account_name, minute_ts.replace(second=0, microsecond=0), 
                 int(used_req_inc or 0), int(used_tokens_inc or 0))
            )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_api_usage_minute(account_name: str, minute_ts: datetime) -> Dict:
    """获取API使用统计"""
    if not _table_exists('api_usage_minute'):
        return {'used_req': 0, 'used_tokens': 0}
    
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT used_req, used_tokens FROM api_usage_minute WHERE account_name=%s AND minute_ts=%s",
                (account_name, minute_ts.replace(second=0, microsecond=0))
            )
            row = cursor.fetchone() or {}
            return {
                'used_req': int(row.get('used_req') or 0),
                'used_tokens': int(row.get('used_tokens') or 0)
            }
    except Exception:
        return {'used_req': 0, 'used_tokens': 0}
    finally:
        conn.close()
