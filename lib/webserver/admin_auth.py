"""
管理员鉴权模块 (新架构)
提供管理员登录、会话验证等功能

独立于用户鉴权系统
"""

import bcrypt
from typing import Optional, Dict, Tuple
from ..load_data.admin_dao import (
    get_admin_by_username,
    get_admin_by_uid,
    create_admin,
    admin_exists
)
from ..redis.admin import AdminSession
from ..redis.connection import redis_ping


def admin_login(username: str, password: str) -> Tuple[bool, Optional[str], str]:
    """
    管理员登录
    
    Args:
        username: 用户名
        password: 密码
        
    Returns:
        (success, token, message) 元组
    """
    if not username or not password:
        return False, None, "用户名和密码不能为空"
    
    # 获取管理员信息
    admin = get_admin_by_username(username)
    if not admin:
        return False, None, "用户名或密码错误"
    
    # 验证密码
    stored_hash = admin.get('password', '')
    if not stored_hash:
        return False, None, "账户异常"
    
    try:
        if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            return False, None, "用户名或密码错误"
    except Exception as e:
        print(f"[AdminAuth] 密码验证异常: {e}")
        return False, None, "认证失败"
    
    # 创建会话
    if not redis_ping():
        return False, None, "系统服务不可用"
    
    uid = admin['uid']
    token = AdminSession.create_session(uid)
    
    if not token:
        return False, None, "创建会话失败"
    
    # 缓存管理员信息
    AdminSession.set_admin_info(
        uid,
        admin['username'],
        admin.get('role', 'admin')
    )
    
    return True, token, "登录成功"


def admin_logout(token: str) -> bool:
    """
    管理员登出
    
    Args:
        token: 会话Token
    """
    if not token:
        return False
    return AdminSession.destroy_session(token)


def verify_admin_token(token: str) -> Optional[Dict]:
    """
    验证管理员Token
    
    Args:
        token: 会话Token
        
    Returns:
        管理员信息字典，或None（无效Token）
    """
    if not token:
        return None
    
    if not redis_ping():
        return None
    
    uid = AdminSession.get_session_uid(token)
    if not uid:
        return None
    
    return get_admin_by_uid(uid)


def is_valid_admin_token(token: str) -> bool:
    """检查Token是否有效"""
    return verify_admin_token(token) is not None


def get_admin_from_request(headers: Dict) -> Optional[Dict]:
    """
    从请求头获取管理员信息
    
    支持两种方式:
    - Authorization: Bearer <token>
    - X-Admin-Token: <token>
    """
    token = None
    
    # 方式1: Authorization头
    auth_header = headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    
    # 方式2: X-Admin-Token头
    if not token:
        token = headers.get('X-Admin-Token', '')
    
    if not token:
        return None
    
    return verify_admin_token(token)


def create_initial_admin(username: str = 'admin', 
                        password: str = 'admin123') -> Optional[int]:
    """
    创建初始管理员账户
    
    仅在没有管理员时调用
    """
    from ..load_data.admin_dao import count_admins
    
    if count_admins() > 0:
        print("[AdminAuth] 已存在管理员账户")
        return None
    
    if admin_exists(username):
        print(f"[AdminAuth] 用户名 {username} 已存在")
        return None
    
    # 生成密码哈希
    password_hash = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    
    uid = create_admin(username, password_hash, 'superadmin')
    
    if uid:
        print(f"[AdminAuth] 创建初始管理员: {username} (uid={uid})")
    
    return uid


def change_admin_password(uid: int, old_password: str, 
                          new_password: str) -> Tuple[bool, str]:
    """
    修改管理员密码
    
    Returns:
        (success, message) 元组
    """
    from ..load_data.admin_dao import update_admin_password
    
    if not uid or uid <= 0:
        return False, "无效的管理员ID"
    
    if not old_password or not new_password:
        return False, "密码不能为空"
    
    if len(new_password) < 6:
        return False, "新密码长度至少6位"
    
    # 获取当前管理员
    admin = get_admin_by_username_with_password(uid)
    if not admin:
        return False, "管理员不存在"
    
    # 验证旧密码
    stored_hash = admin.get('password', '')
    try:
        if not bcrypt.checkpw(old_password.encode('utf-8'), stored_hash.encode('utf-8')):
            return False, "原密码错误"
    except Exception:
        return False, "验证失败"
    
    # 生成新密码哈希
    new_hash = bcrypt.hashpw(
        new_password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    
    if update_admin_password(uid, new_hash):
        return True, "密码修改成功"
    else:
        return False, "密码修改失败"


def get_admin_by_username_with_password(uid: int) -> Optional[Dict]:
    """获取管理员信息（包含密码哈希）"""
    from ..load_data.db_base import _get_connection
    
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, password, role FROM admin_info WHERE uid = %s",
            (uid,)
        )
        result = cursor.fetchone()
        cursor.close()
        return result
    finally:
        conn.close()

