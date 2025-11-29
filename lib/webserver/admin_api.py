"""
管理员API模块 (新架构)
处理所有 /api/admin/* 路由
"""

import json
from typing import Dict, Any, Tuple, Optional
from .admin_auth import (
    admin_login, admin_logout, verify_admin_token, 
    get_admin_from_request, create_initial_admin
)
from ..load_data.admin_dao import get_all_admins
from ..load_data.user_dao import (
    get_all_users, update_user_balance, update_user_permission
)
from ..load_data.query_dao import (
    get_active_queries, get_query_log, pause_query, resume_query
)
from ..redis.task_queue import TaskQueue
from ..redis.connection import redis_ping
from ..redis.billing import BillingQueue
from ..process.sliding_window import get_current_tpm, get_current_rpm
from ..process.worker import get_active_worker_count, stop_workers_for_query


def handle_admin_api(path: str, method: str, headers: Dict, 
                     payload: Dict = None) -> Tuple[int, Dict]:
    """
    处理管理员API请求
    
    Args:
        path: 请求路径（如 /api/admin/login）
        method: 请求方法（GET/POST）
        headers: 请求头
        payload: 请求体数据（已解析的字典）
        
    Returns:
        (status_code, response_dict) 元组
    """
    # 获取请求数据
    data = payload or {}
    
    # 登录接口（无需认证）
    if path == '/api/admin/login' and method == 'POST':
        return _handle_login(data)
    
    # 其他接口需要认证
    admin = get_admin_from_request(headers)
    if not admin:
        return 401, {'success': False, 'error': 'unauthorized', 'message': '请先登录'}
    
    # 路由分发
    if path == '/api/admin/logout' and method == 'POST':
        return _handle_logout(headers)
    
    if path == '/api/admin/dashboard' and method == 'GET':
        return _handle_dashboard()
    
    if path == '/api/admin/users' and method == 'GET':
        return _handle_get_users()
    
    if path == '/api/admin/users/balance' and method == 'POST':
        return _handle_update_balance(data)
    
    if path == '/api/admin/users/permission' and method == 'POST':
        return _handle_update_permission(data)
    
    if path == '/api/admin/tasks' and method == 'GET':
        return _handle_get_tasks()
    
    if path == '/api/admin/tasks/terminate' and method == 'POST':
        return _handle_terminate_task(data)
    
    if path == '/api/admin/tasks/pause' and method == 'POST':
        return _handle_pause_task(data)
    
    if path == '/api/admin/tasks/resume' and method == 'POST':
        return _handle_resume_task(data)
    
    if path == '/api/admin/admins' and method == 'GET':
        return _handle_get_admins()
    
    # 系统配置 API
    if path == '/api/admin/settings' and method == 'GET':
        return _handle_get_settings()
    
    if path == '/api/admin/settings' and method == 'POST':
        return _handle_update_settings(data)
    
    return 404, {'success': False, 'error': 'not_found', 'message': '接口不存在'}


def _handle_login(data: Dict) -> Tuple[int, Dict]:
    """处理登录"""
    username = data.get('username', '')
    password = data.get('password', '')
    
    success, token, message = admin_login(username, password)
    
    if success:
        return 200, {'success': True, 'token': token, 'message': message}
    else:
        return 401, {'success': False, 'message': message}


def _handle_logout(headers: Dict) -> Tuple[int, Dict]:
    """处理登出"""
    token = headers.get('X-Admin-Token', '')
    if not token:
        auth = headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
    
    if token:
        admin_logout(token)
    
    return 200, {'success': True, 'message': '已登出'}


def _handle_dashboard() -> Tuple[int, Dict]:
    """处理监控大盘数据"""
    # 系统统计
    tpm = get_current_tpm()
    rpm = get_current_rpm()
    active_workers = get_active_worker_count()
    
    # 活跃任务
    tasks = []
    active_queries = get_active_queries()
    for q in active_queries:
        uid = q.get('uid')
        qid = q.get('query_id')
        if uid and qid:
            status = TaskQueue.get_status(uid, qid)
            if status:
                tasks.append({
                    'query_id': qid,
                    'uid': uid,
                    'state': status.get('state', 'UNKNOWN'),
                    'total_blocks': status.get('total_blocks', 0),
                    'finished_blocks': status.get('finished_blocks', 0),
                    'pending_blocks': TaskQueue.get_pending_count(uid, qid),
                })
    
    # 健康检查
    health = {
        'redis': redis_ping(),
        'mysql': _check_mysql(),
        'billing_queue_size': _get_total_billing_queue_size(),
    }
    
    return 200, {
        'success': True,
        'tpm': tpm,
        'rpm': rpm,
        'active_workers': active_workers,
        'active_queries': len(tasks),
        'tasks': tasks,
        'health': health,
    }


def _handle_get_users() -> Tuple[int, Dict]:
    """获取用户列表"""
    try:
        users = get_all_users()
        return 200, {'success': True, 'users': users}
    except Exception as e:
        return 500, {'success': False, 'message': str(e)}


def _handle_update_balance(data: Dict) -> Tuple[int, Dict]:
    """更新用户余额"""
    uid = data.get('uid')
    balance = data.get('balance')
    
    if not uid or balance is None:
        return 400, {'success': False, 'message': '参数不完整'}
    
    try:
        uid = int(uid)
        balance = float(balance)
    except (TypeError, ValueError):
        return 400, {'success': False, 'message': '参数格式错误'}
    
    if balance < 0:
        return 400, {'success': False, 'message': '余额不能为负'}
    
    success = update_user_balance(uid, balance)
    if success:
        return 200, {'success': True, 'message': '更新成功'}
    else:
        return 500, {'success': False, 'message': '更新失败'}


def _handle_update_permission(data: Dict) -> Tuple[int, Dict]:
    """更新用户权限"""
    from ..redis.system_config import SystemConfig
    
    uid = data.get('uid')
    permission = data.get('permission')
    
    if not uid or permission is None:
        return 400, {'success': False, 'message': '参数不完整'}
    
    try:
        uid = int(uid)
        permission = int(permission)
    except (TypeError, ValueError):
        return 400, {'success': False, 'message': '参数格式错误'}
    
    # 从配置获取权限范围（动态配置）
    min_perm, max_perm = SystemConfig.get_permission_range()
    if not (min_perm <= permission <= max_perm):
        return 400, {'success': False, 'message': f'权限值范围: {min_perm}-{max_perm}'}
    
    success = update_user_permission(uid, permission)
    if success:
        return 200, {'success': True, 'message': '更新成功'}
    else:
        return 500, {'success': False, 'message': '更新失败'}


def _handle_get_tasks() -> Tuple[int, Dict]:
    """获取任务列表"""
    from ..load_data.db_base import _get_connection
    
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT query_id, uid, status, start_time, end_time, total_cost
            FROM query_log
            ORDER BY start_time DESC
            LIMIT 100
        """)
        tasks = cursor.fetchall() or []
        cursor.close()
        
        # 转换datetime为字符串
        for t in tasks:
            if t.get('start_time'):
                t['start_time'] = str(t['start_time'])
            if t.get('end_time'):
                t['end_time'] = str(t['end_time'])
            if t.get('total_cost'):
                t['total_cost'] = float(t['total_cost'])
        
        return 200, {'success': True, 'tasks': tasks}
    except Exception as e:
        return 500, {'success': False, 'message': str(e)}
    finally:
        conn.close()


def _handle_terminate_task(data: Dict) -> Tuple[int, Dict]:
    """
    终止任务
    
    新架构修复：使用独立的终止信号，区别于暂停信号
    """
    uid = data.get('uid')
    qid = data.get('query_id')
    
    if not uid or not qid:
        return 400, {'success': False, 'message': '参数不完整'}
    
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return 400, {'success': False, 'message': 'uid格式错误'}
    
    # 设置终止信号（区别于暂停信号，Worker会输出不同日志）
    TaskQueue.set_terminate_signal(uid, qid)
    TaskQueue.set_state(uid, qid, 'CANCELLED')
    
    # 停止Workers
    stopped = stop_workers_for_query(uid, qid)
    
    return 200, {'success': True, 'message': f'已发送终止信号，停止了{stopped}个Worker'}


def _handle_pause_task(data: Dict) -> Tuple[int, Dict]:
    """暂停任务"""
    uid = data.get('uid')
    qid = data.get('query_id')
    
    if not uid or not qid:
        return 400, {'success': False, 'message': '参数不完整'}
    
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return 400, {'success': False, 'message': 'uid格式错误'}
    
    pause_query(uid, qid)
    return 200, {'success': True, 'message': '已暂停'}


def _handle_resume_task(data: Dict) -> Tuple[int, Dict]:
    """恢复任务"""
    uid = data.get('uid')
    qid = data.get('query_id')
    
    if not uid or not qid:
        return 400, {'success': False, 'message': '参数不完整'}
    
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return 400, {'success': False, 'message': 'uid格式错误'}
    
    resume_query(uid, qid)
    return 200, {'success': True, 'message': '已恢复'}


def _handle_get_admins() -> Tuple[int, Dict]:
    """获取管理员列表"""
    try:
        admins = get_all_admins()
        return 200, {'success': True, 'admins': admins}
    except Exception as e:
        return 500, {'success': False, 'message': str(e)}


def _check_mysql() -> bool:
    """检查MySQL连接"""
    try:
        from ..load_data.db_base import _get_connection
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return True
    except Exception:
        return False


def _get_total_billing_queue_size() -> int:
    """获取所有计费队列的总大小"""
    try:
        uids = BillingQueue.get_all_active_billing_queues()
        total = 0
        for uid in uids:
            total += BillingQueue.get_queue_length(uid)
        return total
    except Exception:
        return 0


# ============================================================
# 系统配置 API
# ============================================================

def _handle_get_settings() -> Tuple[int, Dict]:
    """获取所有系统配置"""
    from ..load_data.system_settings_dao import (
        get_all_settings, get_permission_range, get_distill_rate,
        is_debug_console_enabled
    )
    
    try:
        # 获取所有配置（从 MySQL）
        all_settings = get_all_settings()
        
        # 也返回当前生效的关键配置值（可能来自 Redis 缓存）
        min_perm, max_perm = get_permission_range()
        distill_rate = get_distill_rate()
        debug_console = is_debug_console_enabled()
        
        return 200, {
            'success': True,
            'settings': all_settings,
            'current_values': {
                'permission_min': min_perm,
                'permission_max': max_perm,
                'distill_rate': distill_rate,
                'debug_console_enabled': 'true' if debug_console else 'false'
            }
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'get_settings_failed', 'message': str(e)}


def _handle_update_settings(data: Dict) -> Tuple[int, Dict]:
    """更新系统配置"""
    from ..load_data.system_settings_dao import set_setting, set_permission_range, set_distill_rate
    
    try:
        settings = data.get('settings', {})
        
        if not settings:
            return 400, {'success': False, 'error': 'missing_settings'}
        
        updated = []
        errors = []
        
        # 处理权限范围
        if 'permission_min' in settings or 'permission_max' in settings:
            min_val = int(settings.get('permission_min', 1))
            max_val = int(settings.get('permission_max', 10))
            
            if min_val < 0:
                errors.append('permission_min 不能小于 0')
            elif max_val < min_val:
                errors.append('permission_max 不能小于 permission_min')
            elif set_permission_range(min_val, max_val):
                updated.append('permission_min')
                updated.append('permission_max')
            else:
                errors.append('权限范围更新失败')
        
        # 处理蒸馏系数
        if 'distill_rate' in settings:
            rate = float(settings.get('distill_rate', 0.1))
            if rate < 0 or rate > 1:
                errors.append('distill_rate 必须在 0-1 之间')
            elif set_distill_rate(rate):
                updated.append('distill_rate')
            else:
                errors.append('蒸馏系数更新失败')
        
        # 处理其他通用配置
        for key, value in settings.items():
            if key not in ('permission_min', 'permission_max', 'distill_rate'):
                if set_setting(key, str(value)):
                    updated.append(key)
                else:
                    errors.append(f'{key} 更新失败')
        
        if errors:
            return 400, {
                'success': False,
                'error': 'partial_update',
                'updated': updated,
                'errors': errors
            }
        
        return 200, {
            'success': True,
            'message': f'已更新 {len(updated)} 个配置项',
            'updated': updated
        }
    except ValueError as e:
        return 400, {'success': False, 'error': 'invalid_value', 'message': str(e)}
    except Exception as e:
        return 500, {'success': False, 'error': 'update_settings_failed', 'message': str(e)}

