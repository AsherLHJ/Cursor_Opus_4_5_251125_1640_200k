"""
用户相关API处理模块 (修复37: 添加Token认证)
负责用户注册、登录、余额、历史记录等操作
"""

import json
from typing import Dict, Tuple, Any

from ..load_data import db_reader
from ..redis.system_cache import SystemCache
from ..redis.user_cache import UserCache
from .auth import register_user, login_user, get_user_info
from .user_auth import (
    require_auth, get_uid_from_request, logout_user, extract_token_from_headers
)


def handle_user_api(path: str, method: str, headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    处理用户相关的API请求
    
    Args:
        path: 请求路径
        method: HTTP方法
        headers: 请求头
        payload: 请求体数据
        
    Returns:
        (status_code, response_dict)
    """
    # ============================================================
    # POST 请求
    # ============================================================
    if method == 'POST':
        if path == '/api/register':
            return _handle_register(payload)
        
        if path == '/api/login':
            return _handle_login(payload)
        
        if path == '/api/logout':
            return _handle_logout(headers)
    
    # ============================================================
    # GET 请求 (需要认证)
    # ============================================================
    if method == 'GET':
        if path == '/api/user_info':
            return _handle_get_user_info(headers)
        
        if path == '/api/history' or path == '/api/user_history':
            return _handle_get_history(headers, payload)
        
        if path == '/api/balance' or path == '/api/user_balance':
            return _handle_get_balance(headers)
        
        if path == '/api/billing':
            return _handle_get_billing(headers)
    
    return 404, {'success': False, 'error': 'not_found'}


def _handle_register(payload: Dict) -> Tuple[int, Dict]:
    """处理用户注册"""
    # 检查注册功能是否开启
    reg_enabled = SystemCache.get_registration_enabled(default=True)
    if not reg_enabled:
        return 403, {
            'success': False, 
            'message': '由于当前算力资源已达上限，为保障现有用户体验，暂时暂停新用户注册。',
            'error': 'registration_disabled'
        }
    
    username = str(payload.get('username', '')).strip()
    password = str(payload.get('password', '')).strip()
    
    result = register_user(username, password)
    return 200, result


def _handle_login(payload: Dict) -> Tuple[int, Dict]:
    """处理用户登录"""
    username = str(payload.get('username', '')).strip()
    password = str(payload.get('password', '')).strip()
    
    result = login_user(username, password)
    return 200, result


def _handle_logout(headers: Dict) -> Tuple[int, Dict]:
    """
    处理用户登出 (修复37: 销毁Redis会话)
    """
    token = extract_token_from_headers(headers)
    if token:
        logout_user(headers)
    
    return 200, {'success': True, 'message': '已登出'}


def _handle_get_user_info(headers: Dict) -> Tuple[int, Dict]:
    """
    获取用户信息 (修复37: 需要Token认证)
    
    用户只能获取自己的信息，uid从Token中提取
    """
    try:
        # 验证认证
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        # get_user_info 已经返回包含 success 和 user_info 的完整响应
        result = get_user_info(uid)
        if result.get('success'):
            return 200, result
        else:
            return 404, result
    except Exception as e:
        return 500, {'success': False, 'error': 'get_user_info_failed', 'message': str(e)}


def _handle_get_balance(headers: Dict) -> Tuple[int, Dict]:
    """
    获取用户余额 (修复37: 需要Token认证)
    
    用户只能获取自己的余额
    """
    try:
        # 验证认证
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        # 优先从Redis获取，回退MySQL
        balance = UserCache.get_balance(uid)
        if balance is None:
            balance = db_reader.get_balance(uid)
        
        if balance is not None:
            return 200, {'success': True, 'balance': float(balance)}
        else:
            return 404, {'success': False, 'error': 'user_not_found'}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_balance_failed', 'message': str(e)}


def _handle_get_history(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    获取用户历史记录 (修复37: 需要Token认证)
    
    用户只能获取自己的历史记录
    """
    try:
        # 验证认证
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        # 分页参数
        page = int(payload.get('page', 1))
        page_size = int(payload.get('page_size', 20))
        
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        
        # 从数据库获取历史记录
        history = db_reader.get_query_logs_by_uid(uid, page=page, page_size=page_size)
        
        return 200, {
            'success': True,
            'history': history.get('records', []),
            'total': history.get('total', 0),
            'page': page,
            'page_size': page_size
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'get_history_failed', 'message': str(e)}


def _handle_get_billing(headers: Dict) -> Tuple[int, Dict]:
    """
    获取用户账单记录 (修复37: 需要Token认证)
    
    用户只能获取自己的账单
    """
    import datetime
    
    try:
        # 验证认证
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        # 获取账单记录
        try:
            records = db_reader.get_billing_records_by_uid(uid)
        except Exception as e:
            return 500, {'success': False, 'error': 'db_error', 'message': str(e)}
        
        def fmt_time(v):
            if v is None:
                return None
            if isinstance(v, datetime.datetime):
                return v.strftime("%Y-%m-%d %H:%M:%S")
            return str(v)
        
        billing_records = []
        for r in records:
            billing_records.append({
                'query_index': r.get('query_index') or r.get('query_id'),
                'query_time': fmt_time(r.get('query_time') or r.get('created_at')),
                'is_distillation': bool(r.get('is_distillation')),
                'total_papers_count': r.get('total_papers_count') or r.get('paper_count') or 0,
                'actual_cost': float(r.get('actual_cost') or r.get('cost') or 0)
            })
        
        return 200, {'success': True, 'records': billing_records}
    except Exception as e:
        return 500, {'success': False, 'error': 'billing_failed', 'message': str(e)}
