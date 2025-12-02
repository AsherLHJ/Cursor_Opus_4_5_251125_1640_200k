"""
用户认证验证模块 (修复37新增)
提供用户Token验证、请求认证等功能

参考设计: lib/webserver/admin_auth.py (管理员认证模块)
"""

from typing import Optional, Dict, Tuple

from ..redis.user_session import UserSession
from ..redis.connection import redis_ping
from ..load_data.user_dao import get_user_by_uid


def verify_user_token(token: str) -> Optional[int]:
    """
    验证用户Token
    
    Args:
        token: 会话Token
        
    Returns:
        用户UID，无效Token返回None
    """
    if not token:
        return None
    
    if not redis_ping():
        return None
    
    return UserSession.get_session_uid(token)


def get_user_from_request(headers: Dict) -> Optional[Dict]:
    """
    从请求头获取用户信息
    
    支持两种方式:
    - Authorization: Bearer <token>
    - X-User-Token: <token>
    
    Args:
        headers: 请求头字典
        
    Returns:
        用户信息字典 {uid, username, balance, permission}，或None
    """
    token = extract_token_from_headers(headers)
    if not token:
        return None
    
    uid = verify_user_token(token)
    if not uid:
        return None
    
    # 获取用户信息
    return get_user_by_uid(uid)


def extract_token_from_headers(headers: Dict) -> Optional[str]:
    """
    从请求头提取Token
    
    Args:
        headers: 请求头字典
        
    Returns:
        Token字符串，或None
    """
    token = None
    
    # 方式1: Authorization头 (标准方式)
    auth_header = headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    
    # 方式2: X-User-Token头 (备用方式)
    if not token:
        token = headers.get('X-User-Token', '')
    
    return token if token else None


def get_uid_from_request(headers: Dict) -> Optional[int]:
    """
    从请求头获取用户UID（简化版，不查询完整用户信息）
    
    Args:
        headers: 请求头字典
        
    Returns:
        用户UID，或None
    """
    token = extract_token_from_headers(headers)
    if not token:
        return None
    
    return verify_user_token(token)


def require_auth(headers: Dict) -> Tuple[bool, Optional[int], str]:
    """
    验证请求是否已认证
    
    Args:
        headers: 请求头字典
        
    Returns:
        (success, uid, error_message) 元组
        - success=True: 认证成功，uid为用户ID
        - success=False: 认证失败，error_message为错误信息
    """
    token = extract_token_from_headers(headers)
    
    if not token:
        return False, None, 'missing_token'
    
    if not redis_ping():
        return False, None, 'service_unavailable'
    
    uid = verify_user_token(token)
    
    if not uid:
        return False, None, 'invalid_token'
    
    return True, uid, ''


def logout_user(headers: Dict) -> bool:
    """
    用户登出（销毁会话）
    
    Args:
        headers: 请求头字典
        
    Returns:
        是否成功
    """
    token = extract_token_from_headers(headers)
    if not token:
        return False
    
    return UserSession.destroy_session(token)


def logout_user_all_devices(uid: int) -> int:
    """
    用户从所有设备登出
    
    Args:
        uid: 用户UID
        
    Returns:
        销毁的会话数量
    """
    return UserSession.destroy_all_sessions_for_uid(uid)


# ==================== 辅助函数 ====================

def is_valid_token(token: str) -> bool:
    """检查Token是否有效"""
    return verify_user_token(token) is not None


def get_session_info(token: str) -> Optional[Dict]:
    """
    获取会话信息
    
    Returns:
        {uid, username, balance, permission} 或 None
    """
    uid = verify_user_token(token)
    if not uid:
        return None
    
    return get_user_by_uid(uid)

