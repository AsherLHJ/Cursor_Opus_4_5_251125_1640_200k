"""
API Key导入模块
负责加载api_list表数据
"""

import os
from typing import List, Dict, Optional


def load_api_keys(conn, api_key_dir: str) -> int:
    """
    从目录加载API Key到api_list表
    
    Args:
        conn: MySQL连接
        api_key_dir: APIKey目录路径
        
    Returns:
        导入的记录数
    """
    if not os.path.isdir(api_key_dir):
        print(f"[ERROR] API Key目录不存在: {api_key_dir}")
        return 0
    
    api_keys: List[Dict] = []
    
    for filename in os.listdir(api_key_dir):
        if not filename.endswith('.txt'):
            continue
        
        file_path = os.path.join(api_key_dir, filename)
        api_name = os.path.splitext(filename)[0]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    key = line.strip()
                    if key and not key.startswith('#'):
                        api_keys.append({
                            'api_key': key,
                            'api_name': api_name,
                        })
        except Exception as e:
            print(f"[WARN] 读取 {filename} 失败: {e}")
    
    if not api_keys:
        print(f"[WARN] 未从 {api_key_dir} 读取到API Key")
        return 0
    
    # 去重
    seen = set()
    unique_keys = []
    for item in api_keys:
        if item['api_key'] not in seen:
            seen.add(item['api_key'])
            unique_keys.append(item)
    
    cursor = None
    inserted = 0
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO api_list (api_key, api_name, rpm_limit, tpm_limit, is_active)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                api_name = VALUES(api_name),
                is_active = VALUES(is_active)
        """
        for item in unique_keys:
            try:
                cursor.execute(sql, (
                    item['api_key'],
                    item['api_name'],
                    3000,   # 默认 RPM 限制
                    500000, # 默认 TPM 限制
                    1,      # 默认激活
                ))
                inserted += 1
            except Exception as e:
                print(f"[WARN] 插入API Key失败: {e}")
        conn.commit()
        print(f"[OK] api_list: 导入 {inserted} 条记录")
    except Exception as e:
        print(f"[ERROR] 导入api_list失败: {e}")
    finally:
        if cursor:
            cursor.close()
    
    return inserted


def get_active_api_keys(conn) -> List[Dict]:
    """获取所有激活的API Key"""
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT api_index, api_key, api_name, rpm_limit, tpm_limit
            FROM api_list
            WHERE is_active = 1
            ORDER BY api_index
        """)
        return cursor.fetchall() or []
    except Exception:
        return []
    finally:
        if cursor:
            cursor.close()


def update_api_key_status(conn, api_index: int, is_active: bool) -> bool:
    """更新API Key激活状态"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE api_list SET is_active = %s WHERE api_index = %s",
            (1 if is_active else 0, api_index)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        if cursor:
            cursor.close()


def update_api_limits(conn, api_index: int, rpm_limit: int, tpm_limit: int) -> bool:
    """更新API Key限额"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE api_list SET rpm_limit = %s, tpm_limit = %s WHERE api_index = %s",
            (rpm_limit, tpm_limit, api_index)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        if cursor:
            cursor.close()


def get_total_tpm_limit(conn) -> int:
    """获取所有激活API Key的TPM总限额"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(tpm_limit), 0) FROM api_list WHERE is_active = 1"
        )
        result = cursor.fetchone()
        return int(result[0]) if result else 0
    except Exception:
        return 0
    finally:
        if cursor:
            cursor.close()

