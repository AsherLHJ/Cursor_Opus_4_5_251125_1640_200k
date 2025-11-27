import secrets

import bcrypt

from ..load_data.db_reader import _get_connection
from ..load_data import db_reader


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
    用户登录
    返回: {'success': bool, 'message': str, 'uid': int, 'token': str, 'balance': int, 'permission': int}
    """
    if not username or not password:
        return {'success': False, 'message': '用户名和密码不能为空'}
    
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
            
            # 生成简单的会话token（实际项目中应使用更安全的方式）
            token = secrets.token_hex(32)
            
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

def update_balance(uid: int, new_balance: int) -> dict:
    """
    更新用户余额
    返回: {'success': bool, 'message': str}
    """
    if new_balance < 0:
        return {'success': False, 'message': '余额不能为负数'}
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE user_info SET balance = %s WHERE uid = %s",
                (new_balance, uid)
            )
            
            if cursor.rowcount == 0:
                return {'success': False, 'message': '用户不存在'}
            
            conn.commit()
            return {'success': True, 'message': '余额更新成功'}
    except Exception as e:
        return {'success': False, 'message': f'余额更新失败: {str(e)}'}
    finally:
        conn.close()

def add_balance(uid: int, amount: int) -> dict:
    """
    增加用户余额
    返回: {'success': bool, 'message': str, 'new_balance': int}
    """
    if amount <= 0:
        return {'success': False, 'message': '充值金额必须大于0'}
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取当前余额
            cursor.execute("SELECT balance FROM user_info WHERE uid = %s", (uid,))
            result = cursor.fetchone()
            
            if not result:
                return {'success': False, 'message': '用户不存在'}
            
            current_balance = result[0]
            new_balance = current_balance + amount
            
            # 更新余额
            cursor.execute(
                "UPDATE user_info SET balance = %s WHERE uid = %s",
                (new_balance, uid)
            )
            conn.commit()
            
            return {
                'success': True, 
                'message': f'充值成功，余额增加{amount}',
                'new_balance': new_balance
            }
    except Exception as e:
        return {'success': False, 'message': f'充值失败: {str(e)}'}
    finally:
        conn.close()

def deduct_balance(uid: int, amount: int) -> dict:
    """
    扣除用户余额
    返回: {'success': bool, 'message': str, 'new_balance': int}
    """
    if amount <= 0:
        return {'success': False, 'message': '扣除金额必须大于0'}
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取当前余额
            cursor.execute("SELECT balance FROM user_info WHERE uid = %s", (uid,))
            result = cursor.fetchone()
            
            if not result:
                return {'success': False, 'message': '用户不存在'}
            
            current_balance = result[0]
            
            if current_balance < amount:
                return {'success': False, 'message': '余额不足'}
            
            new_balance = current_balance - amount
            
            # 更新余额
            cursor.execute(
                "UPDATE user_info SET balance = %s WHERE uid = %s",
                (new_balance, uid)
            )
            conn.commit()
            
            return {
                'success': True, 
                'message': f'扣费成功，余额减少{amount}',
                'new_balance': new_balance
            }
    except Exception as e:
        return {'success': False, 'message': f'扣费失败: {str(e)}'}
    finally:
        conn.close()

def update_permission(uid: int, new_permission: int) -> dict:
    """
    更新用户权限（最大线程数量）
    返回: {'success': bool, 'message': str}
    """
    if new_permission < 1:
        return {'success': False, 'message': '最大线程数量不能小于1'}
    
    if new_permission > 100:
        return {'success': False, 'message': '最大线程数量不能超过100'}
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE user_info SET permission = %s WHERE uid = %s",
                (new_permission, uid)
            )
            
            if cursor.rowcount == 0:
                return {'success': False, 'message': '用户不存在'}
            
            conn.commit()
            return {'success': True, 'message': f'权限更新成功，最大线程数量设置为{new_permission}'}
    except Exception as e:
        return {'success': False, 'message': f'权限更新失败: {str(e)}'}
    finally:
        conn.close()

def check_thread_permission(uid: int, requested_threads: int) -> dict:
    """
    检查用户是否有权限使用指定数量的线程
    返回: {'success': bool, 'message': str, 'allowed': bool, 'max_threads': int}
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT permission FROM user_info WHERE uid = %s", (uid,))
            result = cursor.fetchone()
            
            if not result:
                return {'success': False, 'message': '用户不存在'}
            
            max_threads = result[0]
            allowed = requested_threads <= max_threads
            
            return {
                'success': True,
                'message': '权限检查完成',
                'allowed': allowed,
                'max_threads': max_threads
            }
    except Exception as e:
        return {'success': False, 'message': f'权限检查失败: {str(e)}'}
    finally:
        conn.close()