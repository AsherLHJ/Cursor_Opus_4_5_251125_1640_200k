"""
查询任务数据访问对象 (新架构)
管理 query_log 表的操作

新架构 query_log 表结构:
- query_id (VARCHAR 64, PK) - 查询唯一标识
- uid (INT) - 用户ID
- search_params (JSON) - 搜索参数
- start_time (DATETIME) - 开始时间
- end_time (DATETIME) - 结束时间
- status (VARCHAR 50) - 状态
- total_cost (DECIMAL) - 总费用
"""

import json
import time
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from .db_base import _get_connection
from ..redis.task_queue import TaskQueue
from ..redis.user_cache import UserCache
from ..redis.connection import redis_ping
from ..process.worker import stop_workers_for_query


def generate_query_id() -> str:
    """生成唯一的查询ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique = uuid.uuid4().hex[:8]
    return f"Q{timestamp}_{unique}"


def create_query_log(uid: int, search_params: Dict, 
                     estimated_cost: float = 0) -> Optional[str]:
    """
    创建新的查询任务记录
    
    Args:
        uid: 用户ID
        search_params: 搜索参数 (期刊、年份、研究问题等)
        estimated_cost: 预估费用
        
    Returns:
        查询ID (query_id)
    """
    if not uid or uid <= 0:
        return None
    
    query_id = generate_query_id()
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO query_log (query_id, uid, search_params, start_time, status, total_cost)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            query_id,
            uid,
            json.dumps(search_params, ensure_ascii=False),
            datetime.now(),
            'PENDING',
            estimated_cost
        ))
        conn.commit()
        cursor.close()
        
        # 添加到用户历史记录 (Redis)
        if redis_ping():
            UserCache.add_history(uid, query_id)
        
        return query_id
    except Exception as e:
        print(f"[QueryDAO] 创建查询记录失败: {e}")
        return None
    finally:
        conn.close()


def get_query_log(query_id: str) -> Optional[Dict[str, Any]]:
    """获取单个查询任务信息"""
    if not query_id:
        return None
    
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT query_id, uid, search_params, start_time, end_time, 
                   status, total_cost
            FROM query_log WHERE query_id = %s
        """, (query_id,))
        result = cursor.fetchone()
        cursor.close()
        
        if result and result.get('search_params'):
            try:
                if isinstance(result['search_params'], str):
                    result['search_params'] = json.loads(result['search_params'])
            except Exception:
                pass
        
        return result
    finally:
        conn.close()


def get_query_logs_by_uid(uid: int, limit: int = 50) -> List[Dict]:
    """
    获取用户的查询历史
    
    优先从 Redis 历史记录获取 query_id 列表
    """
    if not uid or uid <= 0:
        return []
    
    # 尝试从 Redis 获取历史 ID 列表
    query_ids = []
    if redis_ping():
        query_ids = UserCache.get_history(uid, limit)
    
    if query_ids:
        # 批量获取查询详情
        return _get_query_logs_by_ids(query_ids)
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT query_id, uid, search_params, start_time, end_time, 
                   status, total_cost
            FROM query_log 
            WHERE uid = %s 
            ORDER BY start_time DESC 
            LIMIT %s
        """, (uid, limit))
        results = cursor.fetchall() or []
        cursor.close()
        
        # 解析 JSON
        for r in results:
            if r.get('search_params') and isinstance(r['search_params'], str):
                try:
                    r['search_params'] = json.loads(r['search_params'])
                except Exception:
                    pass
        
        # 重建 Redis 历史缓存
        if redis_ping() and results:
            history_items = []
            for r in results:
                ts = r.get('start_time')
                if ts:
                    ts_val = ts.timestamp() if hasattr(ts, 'timestamp') else time.time()
                else:
                    ts_val = time.time()
                history_items.append((r['query_id'], ts_val))
            UserCache.rebuild_history(uid, history_items)
        
        return results
    finally:
        conn.close()


def _get_query_logs_by_ids(query_ids: List[str]) -> List[Dict]:
    """批量获取查询记录"""
    if not query_ids:
        return []
    
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        placeholders = ", ".join(["%s"] * len(query_ids))
        cursor.execute(f"""
            SELECT query_id, uid, search_params, start_time, end_time, 
                   status, total_cost
            FROM query_log 
            WHERE query_id IN ({placeholders})
        """, query_ids)
        results = cursor.fetchall() or []
        cursor.close()
        
        # 解析 JSON 并按原顺序排列
        result_map = {}
        for r in results:
            if r.get('search_params') and isinstance(r['search_params'], str):
                try:
                    r['search_params'] = json.loads(r['search_params'])
                except Exception:
                    pass
            result_map[r['query_id']] = r
        
        return [result_map[qid] for qid in query_ids if qid in result_map]
    finally:
        conn.close()


def update_query_status(query_id: str, status: str) -> bool:
    """更新查询状态"""
    if not query_id:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        update_fields = ["status = %s"]
        params = [status]
        
        # 如果是完成状态，记录结束时间
        if status in ('DONE', 'FAILED', 'CANCELLED'):
            update_fields.append("end_time = %s")
            params.append(datetime.now())
        
        params.append(query_id)
        
        cursor.execute(f"""
            UPDATE query_log SET {', '.join(update_fields)}
            WHERE query_id = %s
        """, params)
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"[QueryDAO] 更新状态失败: {e}")
        return False
    finally:
        conn.close()


def update_query_cost(query_id: str, total_cost: float) -> bool:
    """更新查询总费用"""
    if not query_id:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE query_log SET total_cost = %s WHERE query_id = %s",
            (total_cost, query_id)
        )
        conn.commit()
        cursor.close()
        return True
    finally:
        conn.close()


def mark_query_completed(query_id: str, total_cost: float = None) -> bool:
    """标记查询完成"""
    if not query_id:
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        if total_cost is not None:
            cursor.execute("""
                UPDATE query_log 
                SET status = 'DONE', end_time = %s, total_cost = %s
                WHERE query_id = %s
            """, (datetime.now(), total_cost, query_id))
        else:
            cursor.execute("""
                UPDATE query_log 
                SET status = 'DONE', end_time = %s
                WHERE query_id = %s
            """, (datetime.now(), query_id))
        
        conn.commit()
        cursor.close()
        return True
    finally:
        conn.close()


def get_active_queries() -> List[Dict]:
    """获取所有进行中的查询"""
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT query_id, uid, search_params, start_time, status
            FROM query_log 
            WHERE status IN ('PENDING', 'RUNNING')
            ORDER BY start_time
        """)
        results = cursor.fetchall() or []
        cursor.close()
        return results
    finally:
        conn.close()


def get_query_by_id(query_id: str) -> Optional[Dict]:
    """
    根据 query_id 获取查询信息（修复28新增）
    
    Args:
        query_id: 查询ID
        
    Returns:
        查询信息字典，包含 search_params 等字段
    """
    if not query_id:
        return None
    
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT query_id, uid, search_params, start_time, status
            FROM query_log 
            WHERE query_id = %s
        """, (query_id,))
        result = cursor.fetchone()
        cursor.close()
        return result
    finally:
        conn.close()


def get_query_progress(uid: int, query_id: str) -> Optional[Dict]:
    """
    获取查询进度
    
    从 Redis 获取实时进度
    """
    if not query_id:
        return None
    
    # 从 Redis 获取状态
    if redis_ping():
        status = TaskQueue.get_status(uid, query_id)
        if status:
            total = status.get('total_blocks', 0)
            finished = status.get('finished_blocks', 0)
            finished_count = TaskQueue.get_finished_count(uid, query_id)
            
            progress = (finished / total * 100) if total > 0 else 0
            
            return {
                'query_id': query_id,
                'state': status.get('state', 'UNKNOWN'),
                'total_blocks': total,
                'finished_blocks': finished,
                'finished_papers': finished_count,
                'progress': round(progress, 2),
                'is_paused': TaskQueue.is_paused(uid, query_id),
            }
    
    # 回退到数据库查询
    query = get_query_log(query_id)
    if query:
        return {
            'query_id': query_id,
            'state': query.get('status', 'UNKNOWN'),
            'progress': 100 if query.get('status') == 'DONE' else 0,
        }
    
    return None


def pause_query(uid: int, query_id: str) -> bool:
    """暂停查询"""
    if redis_ping():
        TaskQueue.set_pause_signal(uid, query_id)
        TaskQueue.set_state(uid, query_id, 'PAUSED')
    return update_query_status(query_id, 'PAUSED')


def resume_query(uid: int, query_id: str) -> bool:
    """恢复查询"""
    if redis_ping():
        TaskQueue.clear_pause_signal(uid, query_id)
        TaskQueue.set_state(uid, query_id, 'RUNNING')
    return update_query_status(query_id, 'RUNNING')


def cancel_query(uid: int, query_id: str) -> bool:
    """
    取消/终止查询任务
    
    新架构修复12：使用 terminate_signal 而不是 pause_signal，
    以区分用户主动终止和暂停操作
    
    新架构修复12c：必须调用 stop_workers_for_query 停止Worker线程，
    否则Worker会继续运行直到完成
    
    Args:
        uid: 用户ID
        query_id: 查询ID
    
    Returns:
        True 如果取消成功
    """
    if redis_ping():
        # 设置终止信号（Worker会检测并退出，日志显示"终止"而非"暂停"）
        TaskQueue.set_terminate_signal(uid, query_id)
        TaskQueue.set_state(uid, query_id, 'CANCELLED')
        # 清理待处理队列
        TaskQueue.clear_pending(uid, query_id)
    
    # 修复12c: 必须停止Worker线程，否则任务会继续运行
    stopped = stop_workers_for_query(uid, query_id)
    print(f"[cancel_query] 已停止 {stopped} 个Worker线程 (uid={uid}, qid={query_id})")
    
    return update_query_status(query_id, 'CANCELLED')
