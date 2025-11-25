"""
用户管理数据访问对象
处理user_info表相关操作
"""

from typing import List, Dict
from .db_base import _get_connection


def get_all_users() -> List[Dict]:
    """获取所有用户信息"""
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, balance, permission FROM user_info "
            "WHERE uid IS NOT NULL AND username IS NOT NULL ORDER BY uid"
        )
        return cursor.fetchall()
    finally:
        conn.close()


def update_user_balance(uid: int, new_balance: float) -> bool:
    """更新用户余额"""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT uid FROM user_info WHERE uid = %s", (uid,))
        if not cursor.fetchone():
            return False
        
        cursor.execute("UPDATE user_info SET balance = %s WHERE uid = %s", (new_balance, uid))
        conn.commit()
        return True
    finally:
        conn.close()


def update_user_permission(uid: int, new_permission: int) -> bool:
    """更新用户权限"""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT uid FROM user_info WHERE uid = %s", (uid,))
        if not cursor.fetchone():
            return False
        
        cursor.execute("UPDATE user_info SET permission = %s WHERE uid = %s", (new_permission, uid))
        conn.commit()
        return True
    finally:
        conn.close()


def get_user_by_uid(uid: int) -> Dict:
    """根据UID获取用户信息"""
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, balance, permission FROM user_info WHERE uid = %s", 
            (uid,)
        )
        result = cursor.fetchone()
        return result or {}
    finally:
        conn.close()


def get_billing_records_by_uid(uid: int, limit: int = 100):
    """获取用户账单记录"""
    if not uid or uid <= 0:
        return []
    
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT query_index, query_time, is_distillation, total_papers_count, actual_cost
                FROM query_log 
                WHERE uid = %s 
                  AND actual_cost > 0 
                  AND is_visible = TRUE
                ORDER BY query_time DESC 
                LIMIT %s
            """, (uid, limit))
            return cursor.fetchall() or []
    finally:
        conn.close()
