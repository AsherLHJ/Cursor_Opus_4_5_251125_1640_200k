"""
管理员数据访问对象 (新架构)
管理 admin_info 表的操作

admin_info 表结构:
- uid (INT, PK) - 管理员ID
- username (VARCHAR 255, UNIQUE) - 用户名
- password (VARCHAR 255) - 密码哈希
- role (VARCHAR 50) - 角色
- created_at (TIMESTAMP) - 创建时间
"""

from typing import List, Dict, Optional, Any
from .db_base import _get_connection
from ..redis.admin import AdminSession
from ..redis.connection import redis_ping


def get_admin_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    根据用户名获取管理员信息（包括密码哈希，用于登录验证）
    """
    if not username:
        return None
    
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, password, role FROM admin_info WHERE username = %s",
            (username,)
        )
        result = cursor.fetchone()
        cursor.close()
        return result
    finally:
        conn.close()


def get_admin_by_uid(uid: int) -> Optional[Dict[str, Any]]:
    """
    根据UID获取管理员信息
    """
    if not uid or uid <= 0:
        return None
    
    # 优先从Redis缓存读取
    if redis_ping():
        cached = AdminSession.get_admin_info(uid)
        if cached:
            return cached
    
    # 回源MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, role FROM admin_info WHERE uid = %s",
            (uid,)
        )
        result = cursor.fetchone()
        cursor.close()
        
        if result and redis_ping():
            AdminSession.set_admin_info(
                result['uid'],
                result['username'],
                result.get('role', 'admin')
            )
        
        return result
    finally:
        conn.close()


def get_all_admins() -> List[Dict]:
    """获取所有管理员信息"""
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, role, created_at FROM admin_info ORDER BY uid"
        )
        result = cursor.fetchall()
        cursor.close()
        return result or []
    finally:
        conn.close()


def create_admin(username: str, password_hash: str, 
                 role: str = 'admin') -> Optional[int]:
    """
    创建新管理员
    
    Returns:
        新管理员的UID，或None（创建失败）
    """
    if not username or not password_hash:
        return None
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO admin_info (username, password, role) VALUES (%s, %s, %s)",
            (username, password_hash, role)
        )
        conn.commit()
        uid = cursor.lastrowid
        cursor.close()
        return uid
    except Exception as e:
        print(f"[AdminDAO] 创建管理员失败: {e}")
        return None
    finally:
        conn.close()


def update_admin_password(uid: int, password_hash: str) -> bool:
    """更新管理员密码"""
    if not uid or uid <= 0 or not password_hash:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE admin_info SET password = %s WHERE uid = %s",
            (password_hash, uid)
        )
        conn.commit()
        success = cursor.rowcount > 0
        cursor.close()
        return success
    finally:
        conn.close()


def update_admin_role(uid: int, role: str) -> bool:
    """更新管理员角色"""
    if not uid or uid <= 0 or not role:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE admin_info SET role = %s WHERE uid = %s",
            (role, uid)
        )
        conn.commit()
        success = cursor.rowcount > 0
        cursor.close()
        
        # 更新Redis缓存
        if success and redis_ping():
            AdminSession.delete_admin_info(uid)
        
        return success
    finally:
        conn.close()


def delete_admin(uid: int) -> bool:
    """删除管理员"""
    if not uid or uid <= 0:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admin_info WHERE uid = %s", (uid,))
        conn.commit()
        success = cursor.rowcount > 0
        cursor.close()
        
        # 清除Redis缓存和会话
        if success and redis_ping():
            AdminSession.delete_admin_info(uid)
            AdminSession.destroy_all_sessions_for_uid(uid)
        
        return success
    finally:
        conn.close()


def admin_exists(username: str) -> bool:
    """检查管理员用户名是否存在"""
    if not username:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM admin_info WHERE username = %s LIMIT 1",
            (username,)
        )
        result = cursor.fetchone() is not None
        cursor.close()
        return result
    finally:
        conn.close()


def count_admins() -> int:
    """获取管理员总数"""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM admin_info")
        row = cursor.fetchone()
        cursor.close()
        return int(row[0]) if row else 0
    finally:
        conn.close()

