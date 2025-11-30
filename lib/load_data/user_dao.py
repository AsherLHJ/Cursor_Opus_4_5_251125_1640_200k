"""
用户管理数据访问对象 (新架构)
实现 Redis 优先、MySQL 回源的 Lazy Loading 策略

策略说明:
1. 读取: 先查 Redis，未命中则回源 MySQL 并写入 Redis (TTL 8h)
2. 余额更新: 更新 MySQL 后同步更新/删除 Redis 缓存
3. 余额扣减: 高频操作走 Redis 原子扣减，异步回写 MySQL
"""

from typing import List, Dict, Optional, Any
from .db_base import _get_connection
from ..redis.user_cache import UserCache
from ..redis.connection import redis_ping


def get_user_by_uid(uid: int) -> Optional[Dict[str, Any]]:
    """
    根据 UID 获取用户信息 (Redis 优先)
    
    返回字段: uid, username, balance, permission
    """
    if not uid or uid <= 0:
        return None
    
    # 1. 尝试从 Redis 读取
    if redis_ping():
        cached_info = UserCache.get_user_info(uid)
        cached_balance = UserCache.get_balance(uid)
        
        if cached_info is not None and cached_balance is not None:
            return {
                'uid': uid,
                'username': cached_info.get('username', ''),
                'balance': cached_balance,
                'permission': cached_info.get('permission', 0),
            }
    
    # 2. 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, balance, permission FROM user_info WHERE uid = %s",
            (uid,)
        )
        result = cursor.fetchone()
        cursor.close()
        
        if not result:
            return None
        
        # 3. 写入 Redis 缓存
        if redis_ping():
            UserCache.set_user_info(
                uid=result['uid'],
                username=result['username'],
                permission=int(result['permission'] or 0)
            )
            UserCache.set_balance(
                uid=result['uid'],
                balance=float(result['balance'] or 0)
            )
        
        return {
            'uid': result['uid'],
            'username': result['username'],
            'balance': float(result['balance'] or 0),
            'permission': int(result['permission'] or 0),
        }
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """根据用户名获取用户信息（包括密码哈希，用于登录验证）"""
    if not username:
        return None
    
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, password, balance, permission FROM user_info WHERE username = %s",
            (username,)
        )
        result = cursor.fetchone()
        cursor.close()
        return result
    finally:
        conn.close()


def get_all_users() -> List[Dict]:
    """获取所有用户信息（管理员用）"""
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT uid, username, balance, permission FROM user_info "
            "WHERE uid IS NOT NULL AND username IS NOT NULL ORDER BY uid"
        )
        result = cursor.fetchall()
        cursor.close()
        return result or []
    finally:
        conn.close()


def get_balance(uid: int) -> Optional[float]:
    """
    获取用户余额 (Redis 优先)
    """
    if not uid or uid <= 0:
        return None
    
    # 1. 尝试从 Redis 读取
    if redis_ping():
        cached = UserCache.get_balance(uid)
        if cached is not None:
            return cached
    
    # 2. 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM user_info WHERE uid = %s", (uid,))
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            return None
        
        balance = float(row[0] or 0)
        
        # 3. 写入 Redis
        if redis_ping():
            UserCache.set_balance(uid, balance)
        
        return balance
    finally:
        conn.close()


def get_permission(uid: int) -> int:
    """获取用户权限"""
    user = get_user_by_uid(uid)
    return user.get('permission', 0) if user else 0


def update_user_balance(uid: int, new_balance: float) -> bool:
    """
    更新用户余额 (MySQL + Redis 同步)
    用于管理员充值/扣款等非高频操作
    """
    if not uid or uid <= 0:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT uid FROM user_info WHERE uid = %s", (uid,))
        if not cursor.fetchone():
            cursor.close()
            return False
        
        cursor.execute(
            "UPDATE user_info SET balance = %s WHERE uid = %s",
            (new_balance, uid)
        )
        conn.commit()
        cursor.close()
        
        # 同步更新 Redis
        if redis_ping():
            UserCache.set_balance(uid, new_balance)
        
        return True
    finally:
        conn.close()


def deduct_balance_redis(uid: int, amount: float) -> Optional[float]:
    """
    Redis 原子扣减余额 (高频操作)
    用于 Worker 扣费
    
    Returns:
        扣减后的余额，或 None（扣减失败/余额不足）
    """
    if not uid or uid <= 0 or amount <= 0:
        return None
    
    if not redis_ping():
        # Redis 不可用时回退到 MySQL
        return _deduct_balance_mysql(uid, amount)
    
    # 确保 Redis 中有余额数据
    if UserCache.get_balance(uid) is None:
        # 回源加载
        get_balance(uid)
    
    return UserCache.deduct_balance(uid, amount)


def _deduct_balance_mysql(uid: int, amount: float) -> Optional[float]:
    """MySQL 扣减余额（回退方案）"""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user_info SET balance = balance - %s "
            "WHERE uid = %s AND balance >= %s",
            (amount, uid, amount)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            return None  # 余额不足
        
        # 获取更新后的余额
        cursor.execute("SELECT balance FROM user_info WHERE uid = %s", (uid,))
        row = cursor.fetchone()
        cursor.close()
        
        return float(row[0]) if row else None
    finally:
        conn.close()


def update_user_permission(uid: int, new_permission: int) -> bool:
    """更新用户权限 (MySQL + Redis 同步)"""
    if not uid or uid <= 0:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT uid FROM user_info WHERE uid = %s", (uid,))
        if not cursor.fetchone():
            cursor.close()
            return False
        
        cursor.execute(
            "UPDATE user_info SET permission = %s WHERE uid = %s",
            (new_permission, uid)
        )
        conn.commit()
        cursor.close()
        
        # 同步更新 Redis
        if redis_ping():
            UserCache.update_permission(uid, new_permission)
        
        return True
    finally:
        conn.close()


def create_user(username: str, password_hash: str, 
                balance: float = 0.0, permission: int = 0) -> Optional[int]:
    """
    创建新用户
    
    Returns:
        新用户的 UID，或 None（创建失败）
    """
    if not username or not password_hash:
        return None
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_info (username, password, balance, permission) "
            "VALUES (%s, %s, %s, %s)",
            (username, password_hash, balance, permission)
        )
        conn.commit()
        uid = cursor.lastrowid
        cursor.close()
        return uid
    except Exception as e:
        print(f"[UserDAO] 创建用户失败: {e}")
        return None
    finally:
        conn.close()


def invalidate_user_cache(uid: int) -> None:
    """清除用户的 Redis 缓存（强制下次从 MySQL 读取）"""
    if redis_ping() and uid > 0:
        UserCache.delete_user_info(uid)
        UserCache.delete_balance(uid)


def sync_balance_to_mysql(uid: int, balance: float) -> bool:
    """
    将 Redis 中的余额同步回 MySQL
    用于 BillingSyncer 定期对账
    """
    if not uid or uid <= 0:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user_info SET balance = %s WHERE uid = %s",
            (balance, uid)
        )
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"[UserDAO] 同步余额失败: {e}")
        return False
    finally:
        conn.close()


def get_billing_records_by_uid(uid: int, limit: int = 100) -> List[Dict]:
    """
    获取用户账单记录（从 query_log 表）
    
    返回前端期望的字段：
    - query_time: 查询时间
    - is_distillation: 是否为蒸馏检索
    - total_papers_count: 检索文章数
    - actual_cost: 实际花费
    """
    if not uid or uid <= 0:
        return []
    
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        # 使用 JSON_EXTRACT 提取 is_distillation，并联查 search_result 统计文章数
        cursor.execute("""
            SELECT 
                q.query_id,
                q.start_time as query_time,
                COALESCE(JSON_UNQUOTE(JSON_EXTRACT(q.search_params, '$.is_distillation')), 'false') as is_distillation_str,
                q.total_cost as actual_cost,
                COUNT(sr.id) as total_papers_count
            FROM query_log q
            LEFT JOIN search_result sr ON q.query_id = sr.query_id AND q.uid = sr.uid
            WHERE q.uid = %s 
              AND q.total_cost > 0
            GROUP BY q.query_id, q.start_time, q.search_params, q.total_cost
            ORDER BY q.start_time DESC 
            LIMIT %s
        """, (uid, limit))
        rows = cursor.fetchall()
        cursor.close()
        
        # 转换 is_distillation 为布尔值
        result = []
        for row in rows:
            is_distill_str = str(row.get('is_distillation_str', 'false')).lower()
            is_distillation = is_distill_str in ('true', '1', 'yes')
            result.append({
                'query_id': row.get('query_id'),
                'query_time': row.get('query_time'),
                'is_distillation': is_distillation,
                'total_papers_count': row.get('total_papers_count', 0),
                'actual_cost': float(row.get('actual_cost', 0))
            })
        
        return result
    finally:
        conn.close()
