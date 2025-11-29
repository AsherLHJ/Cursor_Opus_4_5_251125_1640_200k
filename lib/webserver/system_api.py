"""
系统配置和状态API处理模块
负责系统配置读写、健康检查、状态监控等操作
"""

import os
import json
from typing import Dict, Tuple, Any

from ..config import config_loader as config
from ..log import debug_console
from ..load_data import db_reader
from ..redis.system_cache import SystemCache
from ..redis.connection import redis_ping, get_redis_client


def handle_system_api(path: str, method: str, headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    处理系统相关的API请求
    
    Args:
        path: 请求路径
        method: HTTP方法
        headers: 请求头
        payload: 请求体数据
        
    Returns:
        (status_code, response_dict)
    """
    # ============================================================
    # GET 请求
    # ============================================================
    if method == 'GET':
        if path == '/api/health':
            return _handle_health_check()
        
        if path == '/api/system_status':
            return _handle_system_status()
        
        if path == '/api/debug-log':
            return _handle_debug_log()
        
        if path == '/api/registration_status':
            return _handle_get_registration_status()
        
        if path == '/api/admin/tokens_per_req':
            return _handle_get_tokens_per_req()
        
        if path == '/admin/settings/worker_req_per_min':
            return _handle_get_worker_req_per_min()
        
        if path == '/admin/settings/auto_refresh_interval':
            return _handle_get_auto_refresh_interval()
        
        if path == '/admin/settings/bcrypt_rounds':
            return _handle_get_bcrypt_rounds()
    
    # ============================================================
    # POST 请求
    # ============================================================
    if method == 'POST':
        if path == '/api/admin/tokens_per_req':
            return _handle_set_tokens_per_req(payload)
        
        if path == '/api/admin/set_tokens_per_req':
            return _handle_set_tokens_per_req(payload)
        
        if path == '/admin/settings/worker_req_per_min':
            return _handle_set_worker_req_per_min(payload)
        
        if path == '/admin/settings/bcrypt_rounds':
            return _handle_set_bcrypt_rounds(payload)
        
        if path == '/api/admin/toggle_registration':
            return _handle_toggle_registration(payload)
        
        if path == '/api/admin/update_balance':
            return _handle_update_user_balance(payload)
        
        if path == '/api/admin/update_permission':
            return _handle_update_user_permission(payload)
        
        if path == '/api/admin/account-toggle':
            return _handle_toggle_api_account(payload)
    
    return 404, {'success': False, 'error': 'not_found'}


def _handle_health_check() -> Tuple[int, Dict]:
    """系统健康检查"""
    try:
        # MySQL 检查
        db_ok = False
        db_version = ''
        try:
            conn = db_reader._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    cursor.execute("SELECT VERSION()")
                    row = cursor.fetchone()
                    if row:
                        db_version = str(row[0])
                db_ok = True
            finally:
                conn.close()
        except Exception:
            pass
        
        # Redis 检查
        redis_ok = redis_ping()
        
        return 200, {
            'success': True,
            'mysql': {
                'connected': db_ok,
                'version': db_version
            },
            'redis': {
                'connected': redis_ok
            }
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'health_check_failed', 'message': str(e)}


def _handle_system_status() -> Tuple[int, Dict]:
    """获取系统整体状态"""
    try:
        # MySQL 检查
        db_ok = False
        db_version = ''
        try:
            conn = db_reader._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    cursor.execute("SELECT VERSION()")
                    row = cursor.fetchone()
                    if row:
                        db_version = str(row[0])
                db_ok = True
            finally:
                conn.close()
        except Exception:
            pass
        
        # Redis 检查
        redis_ok = redis_ping()
        
        # Worker 数量（从 paper_processor 获取）
        worker_count = 0
        try:
            from ..process.paper_processor import ACTIVE_WORKERS
            worker_count = len(ACTIVE_WORKERS)
        except Exception:
            pass
        
        return 200, {
            'success': True,
            'mysql_connected': db_ok,
            'mysql_version': db_version,
            'redis_connected': redis_ok,
            'active_workers': worker_count
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'system_status_failed', 'message': str(e)}


def _handle_debug_log() -> Tuple[int, Dict]:
    """获取调试日志内容"""
    try:
        if not getattr(config, 'enable_debug_website_console', False):
            return 403, {'success': False, 'error': 'debug_console_disabled'}
        
        log_path = debug_console.get_debug_log_path()
        if not log_path or not os.path.exists(log_path):
            return 200, {'success': True, 'content': '', 'lines': 0, 'bytes': 0, 'truncated': False}
        
        max_bytes = 256 * 1024  # 最大256KB
        file_size = os.path.getsize(log_path)
        truncated = file_size > max_bytes
        
        with open(log_path, 'rb') as fh:
            if truncated:
                fh.seek(-max_bytes, os.SEEK_END)
            else:
                fh.seek(0)
            content_bytes = fh.read()
        
        content = content_bytes.decode('utf-8', errors='replace')
        line_count = content.count('\n')
        if content and not content.endswith('\n'):
            line_count += 1
        
        return 200, {
            'success': True,
            'content': content,
            'lines': line_count,
            'bytes': len(content_bytes),
            'truncated': truncated
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'debug_log_read_failed', 'message': str(e)}


def _handle_get_registration_status() -> Tuple[int, Dict]:
    """获取注册功能状态"""
    try:
        reg_enabled = SystemCache.get_registration_enabled(default=True)
        return 200, {'success': True, 'registration_enabled': reg_enabled}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_status_failed', 'message': str(e)}


def _handle_toggle_registration(payload: Dict) -> Tuple[int, Dict]:
    """切换注册功能开关"""
    try:
        enabled = payload.get('enabled')
        if enabled is None:
            return 400, {'success': False, 'error': 'missing_enabled_parameter'}
        
        enabled_val = bool(enabled)
        success = SystemCache.set_registration_enabled(enabled_val)
        
        if success:
            return 200, {'success': True, 'registration_enabled': enabled_val}
        else:
            return 500, {'success': False, 'error': 'update_failed'}
    except Exception as e:
        return 500, {'success': False, 'error': 'toggle_registration_failed', 'message': str(e)}


def _handle_get_tokens_per_req() -> Tuple[int, Dict]:
    """获取 tokens_per_req 配置"""
    try:
        v = SystemCache.get_tokens_per_req(default=400)
        return 200, {'success': True, 'tokens_per_req': v}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_tokens_per_req_failed', 'message': str(e)}


def _handle_set_tokens_per_req(payload: Dict) -> Tuple[int, Dict]:
    """设置 tokens_per_req 配置"""
    try:
        v = payload.get('tokens_per_req')
        if v is None:
            return 400, {'success': False, 'error': 'missing_tokens_per_req'}
        
        try:
            v = int(v)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_tokens_per_req'}
        
        if v <= 0:
            return 400, {'success': False, 'error': 'invalid_tokens_per_req'}
        
        success = SystemCache.set_tokens_per_req(v)
        if success:
            return 200, {'success': True, 'tokens_per_req': v}
        else:
            return 500, {'success': False, 'error': 'save_failed'}
    except Exception as e:
        return 500, {'success': False, 'error': 'set_tokens_per_req_failed', 'message': str(e)}


def _handle_get_worker_req_per_min() -> Tuple[int, Dict]:
    """获取 worker_req_per_min 配置"""
    try:
        wrpm = SystemCache.get_worker_req_per_min(default=120)
        return 200, {'success': True, 'worker_req_per_min': wrpm}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_worker_req_per_min_failed', 'message': str(e)}


def _handle_set_worker_req_per_min(payload: Dict) -> Tuple[int, Dict]:
    """设置 worker_req_per_min 配置"""
    try:
        val_raw = payload.get('worker_req_per_min')
        if val_raw is None:
            return 400, {'success': False, 'error': 'missing_worker_req_per_min'}
        
        try:
            wrpm = int(val_raw)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_worker_req_per_min'}
        
        if wrpm <= 0:
            return 400, {'success': False, 'error': 'invalid_worker_req_per_min'}
        
        success = SystemCache.set_worker_req_per_min(wrpm)
        if success:
            return 200, {'success': True, 'worker_req_per_min': wrpm}
        else:
            return 500, {'success': False, 'error': 'save_failed'}
    except Exception as e:
        return 500, {'success': False, 'error': 'set_worker_req_per_min_failed', 'message': str(e)}


def _handle_get_auto_refresh_interval() -> Tuple[int, Dict]:
    """获取管理面板自动刷新间隔"""
    try:
        # 使用 SystemCache 的通用配置方法
        ms = SystemCache.get_config('config:admin_auto_refresh_ms', default=5000)
        try:
            ms = int(ms)
        except (ValueError, TypeError):
            ms = 5000
        return 200, {'success': True, 'auto_refresh_ms': ms}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_auto_refresh_failed', 'message': str(e)}


def _handle_get_bcrypt_rounds() -> Tuple[int, Dict]:
    """获取 bcrypt 轮数配置"""
    try:
        rounds = SystemCache.get_bcrypt_rounds(default=12)
        return 200, {'success': True, 'bcrypt_rounds': rounds}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_bcrypt_rounds_failed', 'message': str(e)}


def _handle_set_bcrypt_rounds(payload: Dict) -> Tuple[int, Dict]:
    """设置 bcrypt 轮数配置"""
    try:
        rounds_raw = payload.get('bcrypt_rounds')
        if rounds_raw is None:
            return 400, {'success': False, 'error': 'missing_bcrypt_rounds'}
        
        try:
            rounds = int(rounds_raw)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_bcrypt_rounds'}
        
        if rounds < 4 or rounds > 16:
            return 400, {'success': False, 'error': 'bcrypt_rounds_out_of_range'}
        
        success = SystemCache.set_bcrypt_rounds(rounds)
        if success:
            return 200, {'success': True, 'bcrypt_rounds': rounds, 'message': 'bcrypt rounds 已更新'}
        else:
            return 500, {'success': False, 'error': 'save_failed'}
    except Exception as e:
        return 500, {'success': False, 'error': 'set_bcrypt_rounds_failed', 'message': str(e)}


def _handle_update_user_balance(payload: Dict) -> Tuple[int, Dict]:
    """管理员更新用户余额"""
    try:
        uid = payload.get('uid')
        balance = payload.get('balance')
        
        if not isinstance(uid, int) or uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        if not isinstance(balance, (int, float)) or balance < 0:
            return 400, {'success': False, 'error': 'invalid_balance'}
        
        success = db_reader.update_user_balance(uid, float(balance))
        if success:
            return 200, {'success': True}
        else:
            return 404, {'success': False, 'error': 'user_not_found'}
    except Exception as e:
        return 500, {'success': False, 'error': 'update_balance_failed', 'message': str(e)}


def _handle_update_user_permission(payload: Dict) -> Tuple[int, Dict]:
    """管理员更新用户权限"""
    from ..redis.system_config import SystemConfig
    
    try:
        uid = payload.get('uid')
        permission = payload.get('permission')
        
        if not isinstance(uid, int) or uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        if not isinstance(permission, int) or permission < 0:
            return 400, {'success': False, 'error': 'invalid_permission'}
        
        # 从配置获取权限范围（动态配置）
        min_perm, max_perm = SystemConfig.get_permission_range()
        if not (min_perm <= permission <= max_perm):
            return 400, {'success': False, 'error': 'permission_out_of_range', 
                        'message': f'权限值范围: {min_perm}-{max_perm}'}
        
        success = db_reader.update_user_permission(uid, permission)
        if success:
            return 200, {'success': True}
        else:
            return 404, {'success': False, 'error': 'user_not_found'}
    except Exception as e:
        return 500, {'success': False, 'error': 'update_permission_failed', 'message': str(e)}


def _handle_toggle_api_account(payload: Dict) -> Tuple[int, Dict]:
    """切换API账户启用状态"""
    try:
        api_index = payload.get('api_index')
        enabled = payload.get('enabled')
        
        if not isinstance(api_index, int) or api_index <= 0:
            return 400, {'success': False, 'error': 'invalid_api_index'}
        
        if enabled is None:
            return 400, {'success': False, 'error': 'missing_enabled'}
        
        enabled_val = 1 if bool(enabled) else 0
        
        conn = db_reader._get_connection()
        try:
            with conn.cursor() as cursor:
                try:
                    cursor.execute("UPDATE api_list SET is_active=%s WHERE api_index=%s", (enabled_val, api_index))
                except Exception:
                    # 回退：旧结构仅有 up 字段
                    cursor.execute("UPDATE api_list SET up=%s WHERE api_index=%s", (enabled_val, api_index))
            conn.commit()
        finally:
            conn.close()
        
        return 200, {'success': True}
    except Exception as e:
        return 500, {'success': False, 'error': 'account_toggle_failed', 'message': str(e)}

