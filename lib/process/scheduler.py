"""
后台调度器模块
负责管理工作线程和任务分配
"""

import time
import threading
from typing import Dict, List
from ..load_data import db_reader
from ..log import utils
from . import data
from . import worker
from ..config import config_loader as config
from . import rate_limiter_facade as rate_limiter
from . import redis_aggregates as agg
from ..load_data import task_dao
from ..load_data import app_settings_dao

# 全局变量
SCHEDULER_THREAD = None
PROGRESS_THREAD = None
PERMISSION_CACHE = {}  # 用户权限缓存

# 调度器状态
BACKGROUND_SCHEDULER_STARTED = False

def start_background_scheduler():
    """启动后台调度器"""
    global BACKGROUND_SCHEDULER_STARTED
    
    if BACKGROUND_SCHEDULER_STARTED:
        return
    
    
    BACKGROUND_SCHEDULER_STARTED = True
    # 冷启动初始化 Redis 聚合键（tokens_per_req, api_tpm_total, active_uids 初始重建）
    try:
        _cold_start_init()
    except Exception as e:
        utils.print_and_log(f"[scheduler] Cold start init error: {e}")

    threading.Thread(target=_scheduler_loop, daemon=True).start()
    utils.print_and_log("[scheduler] Started")


def _scheduler_loop():
    """调度器主循环 (更新：周期计算系统最大容量与剩余容量)"""
    global PROGRESS_THREAD
    check_interval = 0
    last_status_log = 0
    last_max_calc = 0.0
    last_remaining = 0.0
    cap_log_interval = 0

    while True:
        try:
            # 获取待处理任务数
            pending_total = db_reader.count_pending_tasks_across_active()

            # 每30秒输出一次状态
            last_status_log += 1
            if last_status_log >= 60:  # 30秒
                last_status_log = 0
                utils.print_and_log(f"[scheduler] Status: pending_total={pending_total}, active_workers={len(worker.ACTIVE_WORKERS)}")

            # 周期计算系统最大容量与剩余容量 (每 ~2s，一般 1~3s 范围内)
            cap_log_interval += 1
            if cap_log_interval >= 4:  # 约2秒（主循环 sleep 0.5s）
                cap_log_interval = 0
                mx = agg.compute_and_set_max_capacity_per_min()
                rem = agg.compute_and_set_remaining_capacity_per_min()
                if abs(mx - last_max_calc) > 1e-6 or abs(rem - last_remaining) > 1e-6:
                    last_max_calc = mx
                    last_remaining = rem
                    utils.print_and_log(f"[scheduler] max_capacity updated -> {mx:.4f}, remaining -> {rem:.4f}")

            # 管理进度监控线程
            manage_progress_thread(pending_total)

            # 定期检查完成状态
            check_interval += 1
            if check_interval >= 10:  # 每5秒检查一次
                check_interval = 0
                check_all_queries_completion()

            # 如果没有待处理任务，也要检查是否有查询需要完成
            if pending_total <= 0:
                finalize_completed_queries()
            else:
                # 有待处理任务时，获取活跃用户并管理工作线程
                active_users = get_active_users_ordered()
                if active_users:
                    # 刷新权限缓存（懒加载）
                    try:
                        refresh_user_permissions(active_users)
                    except Exception:
                        pass
                    utils.print_and_log(f"[scheduler] Active users: {active_users}, pending: {pending_total}")
                    manage_worker_threads(active_users, pending_total)

            # 清理已结束的线程
            cleanup_finished_workers()

        except Exception as e:
            utils.print_and_log(f"[scheduler] Error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            time.sleep(0.5)


def _cold_start_init():
    """冷启动初始化 Redis 聚合：
    - tokens_per_req: 从 app_settings 读取并写入 Redis
    - api_tpm_total: 汇总 api_list.tpm_limit 写入 Redis
    - active_uids: 扫描未结束查询，按 uid 写入 permission，并维护 perm_sum_active
    """
    # tokens_per_req
    try:
        tpr = int(app_settings_dao.get_tokens_per_req())
        agg.set_tokens_per_req(tpr)
        utils.print_and_log(f"[scheduler:init] tokens_per_req -> {tpr}")
    except Exception as e:
        utils.print_and_log(f"[scheduler:init] tokens_per_req init failed: {e}")

    # api_tpm_total
    try:
        total_tpm = int(task_dao.sum_api_tpm_total())
        agg.set_api_tpm_total(total_tpm)
        utils.print_and_log(f"[scheduler:init] api_tpm_total -> {total_tpm}")
    except Exception as e:
        utils.print_and_log(f"[scheduler:init] api_tpm_total init failed: {e}")

    # active_uids 重建
    try:
        conn = db_reader._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT u.uid, COALESCE(u.permission, 0) AS permission
                    FROM query_log q
                    JOIN user_info u ON q.uid = u.uid
                    WHERE q.end_time IS NULL AND q.should_pause = FALSE
                    """
                )
                rows = cursor.fetchall() or []
                count_added = 0
                for row in rows:
                    try:
                        uid = int(row[0] or 0)
                        perm = int(row[1] or 0)
                        if uid > 0:
                            if agg.add_or_update_active_uid(uid, perm):
                                count_added += 1
                    except Exception:
                        pass
                utils.print_and_log(f"[scheduler:init] active_uids rebuilt, added/updated={count_added}")
        finally:
            conn.close()
    except Exception as e:
        utils.print_and_log(f"[scheduler:init] active_uids rebuild failed: {e}")

    # 预计算一次容量，避免冷启动初值为0导致worker等待
    try:
        mx = agg.compute_and_set_max_capacity_per_min()
        rem = agg.compute_and_set_remaining_capacity_per_min()
        utils.print_and_log(f"[scheduler:init] max_capacity -> {mx:.4f}, remaining -> {rem:.4f}")
    except Exception as e:
        utils.print_and_log(f"[scheduler:init] capacity precompute failed: {e}")


def manage_progress_thread(pending_total: int):
    """管理进度监控线程"""
    global PROGRESS_THREAD
    
    if pending_total > 0:
        if PROGRESS_THREAD is None or not PROGRESS_THREAD.is_alive():
            data.progress_stop_event.clear()
            PROGRESS_THREAD = threading.Thread(
                target=utils.progress_monitor, 
                daemon=True
            )
            PROGRESS_THREAD.start()
            utils.print_and_log("[scheduler] Progress thread started")
    
    elif pending_total <= 0:
        if PROGRESS_THREAD and PROGRESS_THREAD.is_alive():
            data.progress_stop_event.set()
            utils.print_and_log("[scheduler] Progress thread stopped")


def check_all_queries_completion():
    """检查所有活跃查询是否已完成"""
    try:
        active_queries = db_reader.get_active_queries_info()
        
        for query_info in active_queries:
            query_index = query_info.get('query_index')
            table_name = query_info.get('query_table')
            
            if not query_index or not table_name:
                continue
            
            # 计算进度
            progress = db_reader.compute_query_progress(table_name, query_index)
            
            # 如果所有任务都已完成（或没有任务），标记查询为完成
            if progress['total'] == 0 or progress['completed'] >= progress['total']:
                utils.print_and_log(f"[scheduler] Query {query_index} completed: {progress['completed']}/{progress['total']}")
                db_reader.finalize_query_if_done(table_name, query_index)
                
    except Exception as e:
        utils.print_and_log(f"[scheduler] Error checking query completion: {e}")


def finalize_completed_queries():
    """完成所有已经完成但未标记的查询"""
    try:
        # 获取所有未完成的查询
        active_infos = db_reader.get_active_queries_info()
        
        for info in active_infos:
            table_name = info.get('query_table')
            query_index = info.get('query_index')
            
            if not table_name or not query_index:
                continue
            
            # 强制检查并完成
            try:
                db_reader.finalize_query_if_done(table_name, query_index)
            except Exception:
                pass
                
    except Exception as e:
        utils.print_and_log(f"[scheduler] Error finalizing queries: {e}")


def get_active_users_ordered() -> List[int]:
    """获取有活跃任务的用户列表"""
    try:
        active_infos = db_reader.get_active_queries_info()
        
        # 收集所有有待处理任务的用户
        active_users = set()
        for info in active_infos:
            uid = info.get('uid')
            if uid:
                # 检查该用户是否真的有待处理任务
                pending = db_reader.count_pending_tasks_for_uid(uid)
                if pending > 0:
                    active_users.add(uid)
                    utils.print_and_log(f"[scheduler] User {uid} has {pending} pending tasks")
        
        # 按用户权限排序（高权限优先）
        if active_users:
            users_with_permission = []
            for uid in active_users:
                permission = PERMISSION_CACHE.get(uid, 50)
                users_with_permission.append((uid, permission))
            
            # 按权限降序排序
            users_with_permission.sort(key=lambda x: x[1], reverse=True)
            result = [uid for uid, _ in users_with_permission]
            
            utils.print_and_log(f"[scheduler] Active users ordered by permission: {result}")
            return result
        
        return []
        
    except Exception as e:
        utils.print_and_log(f"[scheduler] Error getting active users: {e}")
        import traceback
        traceback.print_exc()
        return []


def manage_worker_threads(active_users: List[int], pending_total: int):
    """管理工作线程"""
    # 清理已结束的线程
    cleanup_finished_workers()
    
    current_workers = len(worker.ACTIVE_WORKERS)
    from ..config import config_loader as config

    # 并发上限策略（固定共享池）：
    # - 忽略 Key 数量，由系统最大容量控制总并发（旧称 effective_capacity）
    # - 线程数根据最大容量与每线程速率估算
    try:
        tokens_per_req = int(getattr(config, 'TOKENS_PER_REQ', 400) or 400)
    except Exception:
        tokens_per_req = 400
    # 兼容旧函数：calc_effective_capacity_per_min 实际返回 max_capacity（effective_req_per_min 字段）
    cap_info = rate_limiter.calc_max_capacity_per_min(tokens_per_req) or {}
    eff_per_min = int(cap_info.get('effective_req_per_min') or 0)  # 字段含义：max_capacity_per_min
    worker_rate = db_reader.get_worker_req_per_min(60)
    cap_threads = eff_per_min // max(worker_rate, 1) if eff_per_min > 0 else 1
    threads_by_user = calculate_desired_threads(active_users, pending_total, 10**9)
    desired = min(pending_total, max(1, cap_threads), threads_by_user)
    available_keys = 10**9  # 逻辑上视为无上限（共享池）
    # 至少保持 1 个工作线程（如果有任务）
    if pending_total > 0:
        desired = max(desired, 1)

    target_workers = desired
    utils.print_and_log(f"[scheduler] Current workers={current_workers}, desired={desired}, pending={pending_total}, capacity_threads={cap_threads}, max_capacity_per_min={eff_per_min}")

    delta = target_workers - current_workers
    if delta > 0:
        utils.print_and_log(f"[scheduler] Spawning {delta} workers")
        create_new_workers(active_users, delta)
    elif delta < 0:
        # 过量线程不强制终止：让其在完成后自然退出
        utils.print_and_log(f"[scheduler] Oversubscribed by {-delta} workers (will shrink naturally)")


def cleanup_finished_workers():
    """清理已结束的工作线程"""
    finished = [t for t in worker.ACTIVE_WORKERS.keys() if not t.is_alive()]
    
    for t in finished:
        uid = worker.ACTIVE_WORKERS.pop(t, None)
        if uid:
            utils.print_and_log(f"[scheduler] Worker for user {uid} finished")


def refresh_user_permissions(uids: List[int]):
    """刷新用户权限缓存"""
    global PERMISSION_CACHE
    
    conn = db_reader._get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            for uid in uids:
                if uid not in PERMISSION_CACHE:
                    cursor.execute(
                        "SELECT permission FROM user_info WHERE uid=%s",
                        (uid,)
                    )
                    row = cursor.fetchone()
                    if row:
                        PERMISSION_CACHE[uid] = row.get('permission', 50)
    finally:
        conn.close()


def calculate_desired_threads(users: List[int], pending: int, available_keys: int) -> int:
    """计算理想的线程数"""
    # 实现线程数计算逻辑
    worker_rate = db_reader.get_worker_req_per_min(60)
    total_user_rate = sum(PERMISSION_CACHE.get(u, 50) for u in users)
    threads_by_user = max(0, (total_user_rate + worker_rate - 1) // worker_rate)
    
    return min(pending, available_keys, threads_by_user)


def create_new_workers(users: List[int], count: int):
    """创建新的工作线程"""
    if not users:
        utils.print_and_log(f"[scheduler] No active users to create workers for")
        return
    
    created = 0
    # 预先计算每用户现有线程数量
    per_user_active: Dict[int, int] = {}
    for th, u in worker.ACTIVE_WORKERS.items():
        per_user_active[u] = per_user_active.get(u, 0) + (1 if th.is_alive() else 0)

    worker_rate = db_reader.get_worker_req_per_min(60)  # 每线程近似处理速率（req/min）

    # 轮询分配：避免单用户耗尽所有并发
    user_ptr = 0
    unique_id_seed = int(time.time() * 1000)
    while created < count and users:
        uid = users[user_ptr % len(users)]
        user_ptr += 1

        # 剩余任务校验
        try:
            pending = db_reader.count_pending_tasks_for_uid(uid)
        except Exception:
            pending = 0
        if pending <= 0:
            continue

        # 权限 -> 最大线程估算（permission / worker_rate，向上取整，至少1）
        perm = PERMISSION_CACHE.get(uid, 50)
        max_threads_for_user = max(1, (perm + worker_rate - 1) // max(worker_rate, 1))
        current_for_user = per_user_active.get(uid, 0)
        if current_for_user >= max_threads_for_user:
            # 该用户已达并发上限，尝试其他用户
            continue

        # 统一采用队列模式
        target_func = worker.worker_queue_loop_for_user
        worker_type = "queue"

        thread_name = f"Worker-{worker_type}-{uid}-{unique_id_seed}-{current_for_user+1}"
        t = threading.Thread(
            target=target_func,
            args=(uid,),
            daemon=True,
            name=thread_name
        )
        t.start()
        worker.ACTIVE_WORKERS[t] = uid
        per_user_active[uid] = current_for_user + 1
        created += 1
        utils.print_and_log(
            f"[scheduler] Spawned {worker_type} worker thread for user {uid} (#{per_user_active[uid]}/{max_threads_for_user}), name={thread_name}, pending={pending}"
        )
    
    if created > 0:
        utils.print_and_log(f"[scheduler] Successfully created {created} new workers, total active: {len(worker.ACTIVE_WORKERS)}")
    else:
        utils.print_and_log(f"[scheduler] No workers created")


# 已移除 Leader 判定：多实例部署下各实例可同时运行调度器与进度线程，由共享 Redis/DB 保障幂等与门控
