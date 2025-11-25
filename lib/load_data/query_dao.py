"""
查询和任务管理数据访问对象
处理query_log和任务调度相关操作
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from .db_base import _get_connection, _get_thread_connection, utc_now_str, _parse_utc_prefixed


def get_query_log_by_index(query_index: int):
    """根据索引获取查询日志"""
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT uid, query_time, selected_folders, year_range, 
                       research_question, requirements, query_table,
                       total_papers_count, is_distillation, is_visible, 
                       should_pause, start_time, end_time
                FROM query_log
                WHERE query_index=%s
                """,
                (query_index,)
            )
            row = cursor.fetchone()
            return row or {}
    finally:
        conn.close()


def list_query_logs_by_uid(uid: int, limit: int = 100):
    """按用户列出查询历史"""
    if not uid or uid <= 0:
        return []
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT 
                    query_index, uid, query_time, selected_folders, year_range,
                    research_question, requirements, query_table, start_time, end_time,
                    total_papers_count, is_distillation, is_visible, should_pause
                FROM query_log
                WHERE uid=%s AND is_visible=TRUE
                ORDER BY start_time DESC
                LIMIT %s
                """,
                (uid, int(limit or 100))
            )
            rows = cursor.fetchall() or []
            return rows
    finally:
        conn.close()


def get_query_start_time(query_index: int) -> Optional[datetime]:
    """读取查询开始时间"""
    if not query_index or query_index <= 0:
        return None
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT start_time FROM query_log WHERE query_index=%s", 
                (query_index,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return _parse_utc_prefixed(row[0])
    finally:
        conn.close()


def set_query_start_time_if_absent(query_index: int) -> bool:
    """设置查询开始时间（如果为空）"""
    if not query_index or query_index <= 0:
        return False
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE query_log 
                SET start_time = %s
                WHERE query_index = %s AND (start_time IS NULL OR start_time = '')
                """,
                (utc_now_str(), query_index)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def hide_query_log(query_index: int, uid: int) -> bool:
    """隐藏查询日志"""
    if not query_index or query_index <= 0 or not uid or uid <= 0:
        return False
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE query_log SET is_visible=FALSE WHERE query_index=%s AND uid=%s AND is_visible=TRUE",
                (query_index, uid)
            )
            affected_rows = cursor.rowcount
            conn.commit()
            return affected_rows > 0
    except Exception:
        return False
    finally:
        conn.close()


def delete_query_log(query_index: int, uid: int) -> bool:
    """删除查询日志"""
    if not query_index or query_index <= 0 or not uid or uid <= 0:
        return False

    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM query_log WHERE query_index=%s AND uid=%s",
                (query_index, uid)
            )
            affected_rows = cursor.rowcount
            conn.commit()
            return affected_rows > 0
    except Exception:
        return False
    finally:
        conn.close()


def update_query_pause_status(query_index: int, uid: int, should_pause: bool) -> bool:
    """更新查询暂停状态"""
    if not query_index or query_index <= 0 or not uid or uid <= 0:
        return False
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE query_log SET should_pause=%s WHERE query_index=%s AND uid=%s",
                (should_pause, query_index, uid)
            )
            affected_rows = cursor.rowcount
            conn.commit()
            return affected_rows > 0
    except Exception:
        return False
    finally:
        conn.close()


def finalize_query_if_done(table_name: str, query_index: int):
    """检查并完成查询"""
    if not table_name or query_index is None:
        return
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            # 检查总任务数
            cursor.execute(
                f"SELECT COUNT(*) FROM `{table_name}` WHERE query_index=%s",
                (query_index,)
            )
            (total_count,) = cursor.fetchone() or (0,)
            
            if int(total_count or 0) == 0:
                return
            
            # 检查完成数
            cursor.execute(
                f"""SELECT COUNT(*) FROM `{table_name}` 
                   WHERE query_index=%s 
                   AND (search_result IS NOT NULL OR result_time IS NOT NULL)""",
                (query_index,)
            )
            (completed_count,) = cursor.fetchone() or (0,)
            
            # 如果全部完成
            if int(total_count) > 0 and int(completed_count) >= int(total_count):
                cursor.execute(
                    "SELECT end_time FROM query_log WHERE query_index=%s",
                    (query_index,)
                )
                (current_end_time,) = cursor.fetchone() or (None,)
                
                if current_end_time is None:
                    end_utc = utc_now_str()
                    cursor.execute(
                        "UPDATE query_log SET end_time=%s WHERE query_index=%s AND end_time IS NULL",
                        (end_utc, query_index)
                    )
                    conn.commit()
                    
                    # 记录日志
                    try:
                        from ..log import utils as _utils
                        _utils.print_and_log(
                            f"[finalize] Query {query_index} completed. "
                            f"Total: {total_count}, Completed: {completed_count}"
                        )
                    except Exception:
                        pass
                    
                    # 清理进度桶
                    try:
                        from ..process import data as _data
                        row = get_query_log_by_index(query_index) or {}
                        uid_val = int(row.get('uid') or 0)
                        if uid_val > 0:
                            _data.remove_bucket(uid_val, query_index)
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error in finalize_query_if_done: {e}")
    finally:
        conn.close()


def compute_query_progress(table_name: str, query_index: int) -> dict:
    """计算查询进度"""
    result = {'total': 0, 'completed': 0, 'pending': 0, 'percentage': 0.0}
    if not table_name or query_index is None:
        return result

    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM `{table_name}` WHERE query_index=%s", 
                (query_index,)
            )
            (total_count,) = cursor.fetchone() or (0,)

            cursor.execute(
                f"""SELECT COUNT(*) FROM `{table_name}`
                   WHERE query_index=%s 
                   AND (result_time IS NOT NULL OR search_result IS NOT NULL)""",
                (query_index,)
            )
            (completed_count,) = cursor.fetchone() or (0,)

            total = int(total_count or 0)
            completed = int(completed_count or 0)
            pending = max(0, total - completed)
            percentage = (completed * 100.0 / total) if total > 0 else 0.0
            
            result['total'] = total
            result['completed'] = completed
            result['pending'] = pending
            result['percentage'] = round(percentage, 2)
            
            return result
    finally:
        conn.close()


def get_active_queries_info() -> list:
    """返回所有活跃查询的基本信息"""
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT uid, query_table, start_time, query_index
                FROM query_log
                WHERE end_time IS NULL 
                  AND query_table IS NOT NULL 
                  AND query_table <> '' 
                  AND should_pause = FALSE
                ORDER BY start_time ASC
            """)
            return cursor.fetchall() or []
    finally:
        conn.close()


def list_active_query_tables() -> list:
    """列出所有活跃查询对应的表名"""
    from .search_dao import check_search_table_exists
    conn = _get_thread_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT query_table
                FROM query_log
                WHERE end_time IS NULL 
                  AND query_table IS NOT NULL 
                  AND query_table <> '' 
                  AND should_pause = FALSE
            """)
            rows = cursor.fetchall()
            tables = [r[0] for r in rows if r and r[0]]
            
            # 过滤不存在的表
            filtered = []
            for t in tables:
                try:
                    if check_search_table_exists(t):
                        filtered.append(t)
                except Exception:
                    pass
            return filtered
    finally:
        pass
