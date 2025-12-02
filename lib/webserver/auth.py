import bcrypt

from ..load_data.db_reader import _get_connection
from ..load_data import db_reader
from ..redis.user_session import UserSession
from ..redis.connection import redis_ping


def hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码（替代旧的 SHA-256）。"""
    pw_bytes = password.encode("utf-8")
    # 使用默认 rounds = 12（合理范围：4-16，越大越慢）
    rounds = 12
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """验证密码（仅支持 bcrypt）。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def register_user(username: str, password: str, initial_balance: int = 0, initial_permission: int = 2) -> dict:
    """
    注册新用户
    返回: {'success': bool, 'message': str, 'uid': int}
    """
    if not username or not password:
        return {'success': False, 'message': '用户名和密码不能为空'}
    
    if len(username) > 16:
        return {'success': False, 'message': '用户名长度不能超过16个字符'}
    
    if len(password) < 6:
        return {'success': False, 'message': '密码长度不能少于6个字符'}
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            # 检查用户名是否已存在
            cursor.execute("SELECT uid FROM user_info WHERE username = %s", (username,))
            if cursor.fetchone():
                return {'success': False, 'message': '用户名已存在'}
            
            # 插入新用户，包含balance和permission字段
            # 新注册用户统一使用 bcrypt 存储
            hashed_password = hash_password(password)
            cursor.execute(
                "INSERT INTO user_info (username, password, balance, permission) VALUES (%s, %s, %s, %s)",
                (username, hashed_password, initial_balance, initial_permission)
            )
            conn.commit()
            uid = cursor.lastrowid
            
            return {'success': True, 'message': '注册成功', 'uid': uid}
    except Exception as e:
        return {'success': False, 'message': f'注册失败: {str(e)}'}
    finally:
        conn.close()

def login_user(username: str, password: str) -> dict:
    """
    用户登录 (修复37: 使用Redis存储会话token)
    
    返回: {'success': bool, 'message': str, 'uid': int, 'token': str, 'balance': int, 'permission': int}
    """
    if not username or not password:
        return {'success': False, 'message': '用户名和密码不能为空'}
    
    # 检查Redis可用性
    if not redis_ping():
        return {'success': False, 'message': '系统服务暂时不可用，请稍后重试'}
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT uid, password, balance, permission FROM user_info WHERE username = %s",
                (username,)
            )
            user = cursor.fetchone()
            
            if not user:
                return {'success': False, 'message': '用户名不存在'}
            
            uid, stored_password, balance, permission = user
            # 仅使用 bcrypt 验证
            if not verify_password(password, stored_password):
                return {'success': False, 'message': '密码错误'}
            
            # 修复37: 使用UserSession创建会话并存储到Redis
            # Token存储在Redis中，服务器端可验证
            token = UserSession.create_session(uid)
            
            if not token:
                return {'success': False, 'message': '创建会话失败，请稍后重试'}
            
            return {
                'success': True, 
                'message': '登录成功', 
                'uid': uid,
                'token': token,
                'balance': balance,
                'permission': permission
            }
    except Exception as e:
        return {'success': False, 'message': f'登录失败: {str(e)}'}
    finally:
        conn.close()

def get_user_info(uid: int) -> dict:
    """
    获取用户信息
    返回: {'success': bool, 'message': str, 'user_info': dict}
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT uid, username, balance, permission FROM user_info WHERE uid = %s",
                (uid,)
            )
            user = cursor.fetchone()
            
            if not user:
                return {'success': False, 'message': '用户不存在'}
            
            uid, username, balance, permission = user
            return {
                'success': True,
                'message': '获取用户信息成功',
                'user_info': {
                    'uid': uid,
                    'username': username,
                    'balance': balance,
                    'permission': permission
                }
            }
    except Exception as e:
        return {'success': False, 'message': f'获取用户信息失败: {str(e)}'}
    finally:
        conn.close()


# 注意：以下历史遗留函数已删除（2025-11-29）
# - update_balance, add_balance, deduct_balance: 新架构使用 UserCache.deduct_balance()
# - update_permission: 新架构使用 user_dao.update_user_permission()
# - check_thread_permission: 新架构使用 Redis 缓存的用户权限