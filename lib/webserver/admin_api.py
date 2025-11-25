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
                     body: Optional[str] = None) -> Tuple[int, Dict]:
    """
    处理管理员API请求
    
    Args:
        path: 请求路径（如 /api/admin/login）
        method: 请求方法（GET/POST）
        headers: 请求头
        body: 请求体（JSON字符串）
        
    Returns:
        (status_code, response_dict) 元组
    """
    # 解析请求体
    data = {}
    if body:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            pass
    
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
    uid = data.get('uid')
    permission = data.get('permission')
    
    if not uid or permission is None:
        return 400, {'success': False, 'message': '参数不完整'}
    
    try:
        uid = int(uid)
        permission = int(permission)
    except (TypeError, ValueError):
        return 400, {'success': False, 'message': '参数格式错误'}
    
    if permission < 0 or permission > 10:
        return 400, {'success': False, 'message': '权限值范围: 0-10'}
    
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
    """终止任务"""
    uid = data.get('uid')
    qid = data.get('query_id')
    
    if not uid or not qid:
        return 400, {'success': False, 'message': '参数不完整'}
    
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return 400, {'success': False, 'message': 'uid格式错误'}
    
    # 设置暂停信号
    TaskQueue.set_pause_signal(uid, qid)
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

