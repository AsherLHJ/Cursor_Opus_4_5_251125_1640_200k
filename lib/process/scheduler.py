"""
后台调度器模块 (新架构)
负责管理Worker线程生产和系统资源计算

新架构职责:
- 系统资源计算器: 实时TPM/RPM统计
- Worker线程生产器: 根据查询任务和用户权限生产Worker
- 任务完成检查: 定期检查并标记完成的任务
"""

import time
import threading
from typing import Dict, List, Set, Optional
from ..redis.task_queue import TaskQueue
from ..redis.connection import redis_ping
from ..load_data.user_dao import get_permission
from ..load_data.query_dao import get_active_queries, mark_query_completed
from .worker import spawn_workers, get_active_worker_count, BlockWorker
from .sliding_window import get_current_tpm, get_current_rpm
from .tpm_accumulator import start_accumulator

# 全局状态
_scheduler_running = False
_scheduler_thread: Optional[threading.Thread] = None
_managed_queries: Dict[str, List[BlockWorker]] = {}  # qid -> workers
_managed_lock = threading.Lock()


def start_scheduler() -> None:
    """启动后台调度器"""
    global _scheduler_running, _scheduler_thread
    
    if _scheduler_running:
        return
    
    _scheduler_running = True
    
    # 启动TPM累加器
    start_accumulator()
    
    # 启动调度器线程
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        name="Scheduler",
        daemon=True
    )
    _scheduler_thread.start()
    
    print("[Scheduler] 启动")


def stop_scheduler() -> None:
    """停止调度器"""
    global _scheduler_running
    _scheduler_running = False


def _scheduler_loop() -> None:
    """调度器主循环"""
    last_status_log = 0
    last_completion_check = 0
    
    while _scheduler_running:
        try:
            current_time = time.time()
            
            # 每30秒输出状态日志
            if current_time - last_status_log >= 30:
                last_status_log = current_time
                _log_status()
            
            # 每5秒检查任务完成状态
            if current_time - last_completion_check >= 5:
                last_completion_check = current_time
                _check_completions()
            
            # 检查系统资源，决定是否可以处理新查询
            if _can_accept_new_work():
                _process_pending_queries()
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"[Scheduler] 循环异常: {e}")
            time.sleep(1)


def _log_status() -> None:
    """输出状态日志"""
    tpm = get_current_tpm()
    rpm = get_current_rpm()
    workers = get_active_worker_count()
    
    with _managed_lock:
        active_queries = len(_managed_queries)
    
    print(f"[Scheduler] 状态: TPM={tpm}, RPM={rpm}, "
          f"Workers={workers}, ActiveQueries={active_queries}")


def _can_accept_new_work() -> bool:
    """
    检查系统是否可以接受新的工作
    
    基于TPM/RPM限制判断
    """
    # 获取系统TPM/RPM限制
    from ..load_data.journal_dao import get_journal_prices
    from ..redis.system_cache import SystemCache
    
    # 简化实现：检查是否有足够的API资源
    # 实际应该基于api_list表的rpm_limit/tpm_limit
    current_tpm = get_current_tpm()
    current_rpm = get_current_rpm()
    
    # 默认限制
    max_tpm = 500000  # 50万 TPM
    max_rpm = 3000    # 3000 RPM
    
    return current_tpm < max_tpm * 0.9 and current_rpm < max_rpm * 0.9


def _process_pending_queries() -> None:
    """处理等待中的查询任务"""
    if not redis_ping():
        return
    
    # 获取所有等待中的查询
    active_queries = get_active_queries()
    
    for query in active_queries:
        qid = query.get('query_id')
        uid = query.get('uid')
        status = query.get('status')
        
        if not qid or not uid:
            continue
        
        # 检查是否已经在管理中
        with _managed_lock:
            if qid in _managed_queries:
                continue
        
        # 检查是否有待处理的Block
        pending_count = TaskQueue.get_pending_count(uid, qid)
        if pending_count <= 0:
            continue
        
        # 获取用户权限（决定Worker数量）
        permission = get_permission(uid)
        if permission <= 0:
            permission = 1  # 默认至少1个Worker
        
        # 启动Workers
        _start_query_workers(uid, qid, permission)


def _start_query_workers(uid: int, qid: str, worker_count: int) -> None:
    """
    为查询启动Worker
    
    新架构优化：实际启动的Worker数量 = min(permission, 待处理Block数量)
    避免启动多余的Worker（它们会立即退出）
    
    修复28：区分普通查询和蒸馏任务，使用不同的Worker类
    - 普通查询: BlockWorker (正常费率)
    - 蒸馏任务: DistillWorker (动态蒸馏费率，从 SystemConfig 获取)
    """
    from .search_paper import create_ai_processor
    import json
    
    # 获取待处理Block数量
    pending_blocks = TaskQueue.get_pending_count(uid, qid)
    
    # 实际Worker数量 = min(permission, block数量)
    actual_workers = min(worker_count, pending_blocks) if pending_blocks > 0 else 0
    if actual_workers <= 0:
        actual_workers = 1  # 至少1个Worker
    
    print(f"[Scheduler] 任务 {qid}: {pending_blocks} 个Block, "
          f"permission={worker_count}, 实际启动 {actual_workers} 个Worker")
    
    # 创建AI处理器
    ai_processor = create_ai_processor(uid, qid)
    
    # 修复28：检查是否为蒸馏任务
    from ..load_data.query_dao import get_query_by_id
    query_info = get_query_by_id(qid)
    is_distillation = False
    if query_info:
        search_params = query_info.get('search_params')
        if isinstance(search_params, str):
            try:
                search_params = json.loads(search_params)
            except (json.JSONDecodeError, TypeError):
                search_params = {}
        is_distillation = search_params.get('is_distillation', False) if search_params else False
    
    # 根据任务类型选择Worker
    if is_distillation:
        # 蒸馏任务使用 DistillWorker（0.1倍费率）
        from .distill import spawn_distill_workers
        workers = spawn_distill_workers(uid, qid, actual_workers, ai_processor)
        print(f"[Scheduler] 蒸馏任务 {qid}: 使用 DistillWorker (动态蒸馏费率)")
    else:
        # 普通查询使用 BlockWorker
        workers = spawn_workers(uid, qid, actual_workers, ai_processor)
    
    # 更新任务状态
    TaskQueue.set_state(uid, qid, 'RUNNING')
    
    # 记录到管理列表
    with _managed_lock:
        _managed_queries[qid] = workers
    
    print(f"[Scheduler] 启动查询 {qid}: {actual_workers} 个Worker")


def _check_completions() -> None:
    """
    检查并处理完成的查询
    
    修复41：删除暂停状态处理，只区分取消和正常完成
    """
    done_qids = []  # 正常完成的
    cancelled_qids = []  # 取消的
    
    with _managed_lock:
        for qid, workers in list(_managed_queries.items()):
            if not workers:
                continue
            
            # 检查所有Worker是否都已退出
            all_done = all(
                not w._running or not w._thread or not w._thread.is_alive()
                for w in workers
            )
            
            if all_done:
                uid = workers[0].uid
                # 检查任务当前状态
                status = TaskQueue.get_status(uid, qid)
                state = status.get('state', '') if status else ''
                
                if state == 'CANCELLED':
                    # 取消的任务，不标记完成
                    cancelled_qids.append(qid)
                else:
                    # 正常完成
                    done_qids.append(qid)
    
    # 处理取消的查询（只从管理列表移除，保持原状态）
    for qid in cancelled_qids:
        with _managed_lock:
            _managed_queries.pop(qid, None)
        print(f"[Scheduler] 查询已取消: {qid}")
    
    # 处理正常完成的查询
    for qid in done_qids:
        with _managed_lock:
            _managed_queries.pop(qid, None)
        
        # 更新数据库状态
        mark_query_completed(qid)
        print(f"[Scheduler] 查询完成: {qid}")


def submit_query(uid: int, qid: str, block_keys: List[str]) -> bool:
    """
    提交新的查询任务
    
    Args:
        uid: 用户ID
        qid: 查询ID
        block_keys: Block Key列表
        
    Returns:
        是否提交成功
    """
    if not redis_ping():
        print(f"[Scheduler] Redis不可用，无法提交查询")
        return False
    
    if not block_keys:
        print(f"[Scheduler] Block列表为空")
        return False
    
    # 初始化任务状态
    TaskQueue.init_status(uid, qid, len(block_keys))
    
    # 将Block Keys入队
    TaskQueue.enqueue_blocks(uid, qid, block_keys)
    
    # 重置进度计数
    TaskQueue.reset_finished_count(uid, qid)
    
    print(f"[Scheduler] 提交查询 {qid}: {len(block_keys)} 个Blocks")
    return True


def get_system_stats() -> Dict:
    """获取系统统计信息"""
    return {
        'tpm': get_current_tpm(),
        'rpm': get_current_rpm(),
        'active_workers': get_active_worker_count(),
        'active_queries': len(_managed_queries),
    }


# 兼容旧接口
def start_background_scheduler():
    """兼容旧版本的启动函数"""
    start_scheduler()


BACKGROUND_SCHEDULER_STARTED = False

def _ensure_scheduler_started():
    """确保调度器已启动"""
    global BACKGROUND_SCHEDULER_STARTED
    if not BACKGROUND_SCHEDULER_STARTED:
        start_scheduler()
        BACKGROUND_SCHEDULER_STARTED = True
