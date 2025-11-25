"""
应用设置数据访问对象
处理app_settings表和配置相关操作
"""

from typing import Optional
from .db_base import _get_connection


def ensure_app_settings_table():
    """确保应用设置表存在"""
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    k VARCHAR(64) PRIMARY KEY,
                    v VARCHAR(255) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
                """
            )
        conn.commit()
    finally:
        conn.close()


def set_app_setting(key: str, value: str):
    """写入/更新应用设置"""
    if not key:
        return
    ensure_app_settings_table()
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO app_settings (k, v) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE v=VALUES(v), updated_at=CURRENT_TIMESTAMP
                """,
                (key, str(value))
            )
        conn.commit()
    finally:
        conn.close()


def get_app_setting(key: str) -> str:
    """读取应用设置"""
    if not key:
        return ""
    ensure_app_settings_table()
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT v FROM app_settings WHERE k=%s", (key,))
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] is not None else ""
    finally:
        conn.close()


def get_bool_app_setting(key: str, default: bool = False) -> bool:
    """读取布尔应用设置"""
    val = get_app_setting(key)
    if val == "":
        return bool(default)
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "on")


def set_bool_app_setting(key: str, value: bool):
    """写入布尔应用设置"""
    set_app_setting(key, "1" if bool(value) else "0")


def get_int_app_setting(key: str, default: int = 0) -> int:
    """读取整型应用设置"""
    try:
        val = get_app_setting(key)
        if val == "":
            return int(default)
        return int(str(val).strip())
    except Exception:
        return int(default)


def ensure_default_bcrypt_rounds(default_rounds: int = 12):
    """确保bcrypt rounds存在"""
    try:
        if get_app_setting("bcrypt_rounds") == "":
            set_app_setting("bcrypt_rounds", str(int(default_rounds)))
    except Exception:
        pass


def get_registration_enabled_db(default: bool = True) -> bool:
    """读取注册开关"""
    try:
        return get_bool_app_setting("registration_enabled", default)
    except Exception:
        return bool(default)


def set_registration_enabled_db(enabled: bool):
    """设置注册开关"""
    set_bool_app_setting("registration_enabled", bool(enabled))


def ensure_default_registration_enabled(default: bool = True):
    """确保注册开关存在"""
    try:
        if get_app_setting("registration_enabled") == "":
            set_bool_app_setting("registration_enabled", bool(default))
    except Exception:
        pass


# 已移除：队列/调度开关读取（固定单路径，删除动态读取）


def get_tokens_per_req(default: int = 400) -> int:
    """读取单篇文献token消耗"""
    try:
        val = get_int_app_setting('tokens_per_req', 0)
        if int(val) > 0:
            return int(val)
    except Exception:
        pass
    
    try:
        from ..config import config_loader as _config
        return int(getattr(_config, 'TOKENS_PER_REQ', default))
    except Exception:
        return int(default)


def set_tokens_per_req(value: int) -> bool:
    """设置单篇文献token消耗"""
    try:
        v = int(value)
        if v <= 0:
            return False
        set_app_setting('tokens_per_req', str(v))
        return True
    except Exception:
        return False


def get_worker_req_per_min(default: int = 60) -> int:
    """获取工作线程请求速率"""
    try:
        v = get_int_app_setting('worker_req_per_min', default)
        if v < 0:
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def ensure_default_worker_req_per_min(default: int = 120):
    """确保 worker_req_per_min 存在；若缺失则初始化为 default（默认120）。"""
    try:
        if get_app_setting('worker_req_per_min') == "":
            set_app_setting('worker_req_per_min', str(int(default)))
    except Exception:
        pass


# 已移除：共享单 Key 并发开关（固定共享模式）
