"""
用户相关API处理模块
负责用户注册、登录、余额、历史记录等操作
"""

import json
from typing import Dict, Tuple, Any

from ..load_data import db_reader
from ..redis.system_cache import SystemCache
from ..redis.user_cache import UserCache
from .auth import register_user, login_user, get_user_info


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
            return 200, {'success': True, 'message': '已登出'}
    
    # ============================================================
    # GET 请求
    # ============================================================
    if method == 'GET':
        if path == '/api/user_info':
            return _handle_get_user_info(payload, headers)
        
        if path == '/api/history' or path == '/api/user_history':
            return _handle_get_history(payload)
        
        if path == '/api/balance' or path == '/api/user_balance':
            return _handle_get_balance(payload)
        
        if path == '/api/billing':
            return _handle_get_billing(payload)
    
    return 404, {'success': False, 'error': 'not_found'}


def _handle_register(payload: Dict) -> Tuple[int, Dict]:
    """处理用户注册"""
    # 检查注册功能是否开启
    reg_enabled = SystemCache.get_registration_enabled(default=True)
    if not reg_enabled:
        return 403, {
            'success': False, 
            'message': '注册功能暂时关闭，请联系管理员',
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


def _handle_get_user_info(payload: Dict, headers: Dict) -> Tuple[int, Dict]:
    """获取用户信息"""
    try:
        uid = payload.get('uid')
        if uid is None:
            return 400, {'success': False, 'error': 'missing_uid'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        # get_user_info 已经返回包含 success 和 user_info 的完整响应
        result = get_user_info(uid)
        if result.get('success'):
            return 200, result
        else:
            return 404, result
    except Exception as e:
        return 500, {'success': False, 'error': 'get_user_info_failed', 'message': str(e)}


def _handle_get_balance(payload: Dict) -> Tuple[int, Dict]:
    """获取用户余额"""
    try:
        uid = payload.get('uid')
        if uid is None:
            return 400, {'success': False, 'error': 'missing_uid'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
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


def _handle_get_history(payload: Dict) -> Tuple[int, Dict]:
    """获取用户历史记录"""
    try:
        uid = payload.get('uid')
        if uid is None:
            return 400, {'success': False, 'error': 'missing_uid'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
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


def _handle_get_billing(payload: Dict) -> Tuple[int, Dict]:
    """获取用户账单记录"""
    import datetime
    
    try:
        uid = payload.get('uid')
        if uid is None:
            return 400, {'success': False, 'error': 'missing_uid'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
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

