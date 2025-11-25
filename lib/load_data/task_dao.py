"""
任务调度数据访问对象
处理任务调度和API管理相关操作
"""

from typing import Optional, List, Dict, Any
from .db_base import _get_connection, _get_thread_connection
from .search_dao import check_search_table_exists


def count_pending_tasks_in_table(table_name: str) -> int:
    """统计指定表中未完成的任务数量"""
    if not table_name:
        return 0
    
    try:
        if not check_search_table_exists(table_name):
            return 0
    except Exception:
        return 0
    
    conn = _get_thread_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM `{table_name}` s
                WHERE s.result_time IS NULL
                  AND EXISTS (
                    SELECT 1 
                    FROM query_log q
                    WHERE q.query_table = %s
                      AND q.query_index = s.query_index
                      AND q.end_time IS NULL
                      AND q.should_pause = FALSE
                  )
            """, (table_name,))
            (cnt,) = cursor.fetchone()
            return int(cnt or 0)
    finally:
        pass


def count_pending_tasks_across_active() -> int:
    """统计所有活跃查询的剩余未完成任务总数"""
    from .query_dao import list_active_query_tables
    tables = list_active_query_tables()
    total = 0
    for t in tables:
        total += count_pending_tasks_in_table(t)
    return total


def count_pending_tasks_for_uid(uid: int) -> int:
    """统计某用户的待处理任务数量"""
    if not uid or uid <= 0:
        return 0
    
    from .query_dao import list_active_query_tables
    tables = list_active_query_tables()
    total = 0
    
    conn = _get_thread_connection()
    try:
        with conn.cursor() as cursor:
            for t in tables:
                try:
                    cursor.execute(f"""
                        SELECT COUNT(*)
                        FROM `{t}` s
                        WHERE s.result_time IS NULL 
                          AND s.uid=%s
                          AND EXISTS (
                            SELECT 1 
                            FROM query_log q
                            WHERE q.query_table = %s
                              AND q.query_index = s.query_index
                              AND q.end_time IS NULL
                              AND q.should_pause = FALSE
                          )
                    """, (uid, t))
                    (cnt,) = cursor.fetchone() or (0,)
                    total += int(cnt or 0)
                except Exception:
                    pass
        return total
    finally:
        pass


# 已移除：DB 直领路径（reserve_next_task / reserve_next_task_for_uid）——统一走队列


def list_uids_with_pending_tasks() -> set:
    """列出有待处理任务的用户ID集合"""
    from .query_dao import get_active_queries_info
    
    uids = set()
    active = get_active_queries_info()
    
    conn = _get_thread_connection()
    try:
        with conn.cursor() as cursor:
            for q in active:
                uid = q.get("uid")
                table = q.get("query_table")
                if not uid or not table:
                    continue
                
                try:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM `{table}` WHERE uid=%s AND result_time IS NULL",
                        (uid,)
                    )
                    (cnt,) = cursor.fetchone() or (0,)
                    if int(cnt or 0) > 0:
                        uids.add(int(uid))
                except Exception:
                    pass
        
        return uids
    finally:
        pass


def sum_permissions_for_uids(uids: List[int]) -> int:
    """计算用户权限总和"""
    if not uids:
        return 0
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(uids))
            cursor.execute(
                f"SELECT SUM(permission) FROM user_info WHERE uid IN ({placeholders})",
                uids
            )
            (total,) = cursor.fetchone() or (0,)
            return int(total or 0)
    finally:
        conn.close()


# 已废弃：按 Key 预留/绑定/释放逻辑（Stage3 移除）


def count_available_api_keys() -> int:
    """统计可用API密钥数量"""
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM api_list
                WHERE up=1 
                  AND (query_table IS NULL OR query_table='')
                  AND (search_id IS NULL OR search_id=0)
            """)
            (cnt,) = cursor.fetchone()
            return int(cnt or 0)
    finally:
        conn.close()


def get_active_api_accounts() -> List[Dict]:
    """获取活跃API账户列表"""
    rows: List[Dict] = []
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            try:
                cursor.execute(
                    """
                    SELECT 
                        api_index, api_key,
                        COALESCE(api_name, '') AS api_name,
                        COALESCE(is_active, up) AS is_active,
                        COALESCE(rpm_limit, 30000) AS rpm_limit,
                        COALESCE(tpm_limit, 5000000) AS tpm_limit
                    FROM api_list
                    WHERE COALESCE(is_active, up)=1
                    ORDER BY api_index ASC
                    """
                )
            except Exception:
                cursor.execute(
                    "SELECT api_index, api_key, COALESCE(api_name,'') AS api_name, up AS is_active FROM api_list WHERE up=1 ORDER BY api_index ASC"
                )
            for r in cursor.fetchall() or []:
                r['rpm_limit'] = int(r.get('rpm_limit', 30000) or 30000)
                r['tpm_limit'] = int(r.get('tpm_limit', 5000000) or 5000000)
                rows.append(r)
    except Exception:
        return []
    finally:
        conn.close()
    return rows


def update_api_limits(api_index: int, rpm_limit: int, tpm_limit: int) -> bool:
    """更新API限额"""
    if not api_index or api_index <= 0:
        return False
    try:
        rpm = int(rpm_limit)
        tpm = int(tpm_limit)
        if rpm < 0 or tpm < 0:
            return False
    except Exception:
        return False
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    "UPDATE api_list SET rpm_limit=%s, tpm_limit=%s WHERE api_index=%s", 
                    (rpm, tpm, api_index)
                )
            except Exception:
                ok = True
                try:
                    cursor.execute("UPDATE api_list SET rpm_limit=%s WHERE api_index=%s", (rpm, api_index))
                except Exception:
                    ok = False
                try:
                    cursor.execute("UPDATE api_list SET tpm_limit=%s WHERE api_index=%s", (tpm, api_index))
                    ok = ok or True
                except Exception:
                    pass
                if not ok:
                    conn.rollback()
                    return False
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


def sum_api_tpm_total() -> int:
    """汇总活跃 API 的 tpm_limit 总和（共享池总容量）。"""
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            try:
                cursor.execute("SELECT SUM(COALESCE(tpm_limit,0)) FROM api_list WHERE COALESCE(is_active, up)=1")
            except Exception:
                cursor.execute("SELECT SUM(5000000) FROM api_list WHERE up=1")  # 兜底：老字段仅 up 时用默认
            (total,) = cursor.fetchone() or (0,)
            try:
                return int(total or 0)
            except Exception:
                return 0
    finally:
        conn.close()
