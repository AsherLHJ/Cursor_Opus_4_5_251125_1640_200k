"""
数据库基础模块
提供连接管理和基础工具函数
"""

import mysql.connector
import threading
from typing import Optional, Any
from datetime import datetime, timezone
from ..config import config_loader as config

_thread_local = threading.local()


def _schema_managed_externally() -> bool:
    """检查是否由外部管理数据库结构"""
    try:
        return bool(getattr(config, 'SCHEMA_MANAGED_EXTERNALLY', False))
    except Exception:
        return False


def _get_connection():
    """获取数据库连接"""
    # 优先用 config_loader 中的 DB_*
    host = getattr(config, 'DB_HOST', None)
    port = getattr(config, 'DB_PORT', None)
    user = getattr(config, 'DB_USER', None)
    password = getattr(config, 'DB_PASSWORD', None)
    database = getattr(config, 'DB_NAME', None)

    if not host or not user or not database:
        import json, os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'config.json'
        )
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        host = host or cfg.get('DB_HOST', '127.0.0.1')
        port = port or cfg.get('DB_PORT', 3306)
        user = user or cfg.get('DB_USER', 'root')
        password = password or cfg.get('DB_PASSWORD', '')
        database = database or cfg.get('DB_NAME', 'PaperDB')

    try:
        port = int(port or 3306)
    except Exception:
        port = 3306

    return mysql.connector.connect(
        host=host,
        port=port,
        user=str(user or ''),
        password=str(password or ''),
        database=str(database or '')
    )


def _get_thread_connection():
    """
    返回当前线程的持久 MySQL 连接
    为避免持久连接下的快照不刷新问题，开启 autocommit 并设置 READ COMMITTED
    """
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            if conn.is_connected():
                return conn
            else:
                try:
                    conn.reconnect(attempts=3, delay=1)
                    if conn.is_connected():
                        try:
                            conn.autocommit = True
                            with conn.cursor() as cursor:
                                cursor.execute(
                                    "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"
                                )
                        except Exception:
                            pass
                        return conn
                except Exception:
                    pass
        except Exception:
            pass

    # 新建连接
    new_conn = mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
    )
    
    # 开启 autocommit 并设置读取已提交隔离级别
    try:
        new_conn.autocommit = True
        with new_conn.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
    except Exception:
        pass
    
    _thread_local.conn = new_conn
    return new_conn


def close_thread_connection():
    """关闭并清理当前线程的持久连接"""
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        finally:
            try:
                delattr(_thread_local, "conn")
            except Exception:
                pass


def _table_exists(table_name: str) -> bool:
    """检查表是否存在"""
    if not table_name:
        return False
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT COUNT(*) FROM information_schema.tables 
                   WHERE table_schema=DATABASE() AND table_name=%s""",
                (table_name,)
            )
            (cnt,) = cursor.fetchone() or (0,)
            return int(cnt or 0) > 0
    except Exception:
        return False
    finally:
        conn.close()


def utc_now_str() -> str:
    """返回UTC时间字符串"""
    return 'UTC-' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _parse_utc_prefixed(dt_str: str) -> Optional[datetime]:
    """解析UTC前缀的时间字符串"""
    if not dt_str:
        return None
    try:
        s = str(dt_str)
        if s.startswith('UTC-'):
            s = s[4:]
        dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
