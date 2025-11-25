"""
工作线程管理模块
负责具体的论文处理任务执行
"""

import time
import threading
from typing import Dict, Optional
from ..load_data import db_reader
from ..log import utils
from . import data
from . import search_paper
from . import queue_facade as queue_manager  # 兼容测试期望的 worker.queue_manager 名称
from . import redis_aggregates as agg
from . import rate_limiter_facade as rate_limiter

# 工作线程跟踪
ACTIVE_WORKERS: Dict[threading.Thread, int] = {}


def gate_permits(permission: int, tokens_per_req: int,
                 max_capacity_per_min: float,
                 running_perm_sum: int,
                 running_tasks_count: int) -> bool:
    """门控判定（统一单位：请求/分钟，req/min）：
    - expected_used_capacity = permission
    - occupied_capacity = running_perm_sum
    - remaining_capacity = max_capacity_per_min - occupied_capacity
    放行条件：expected_used_capacity < remaining_capacity
    注意：tokens_per_req 在门控中不参与计算，仅用于速率额度申请。
    """
    try:
        p = int(permission)
        mx = float(max_capacity_per_min)
        s = int(running_perm_sum)
        if mx <= 0:
            return False
        occupied = float(max(0, s))
        remaining = mx - occupied
        expected = float(max(0, p))
        return expected < remaining
    except Exception:
        return False


def _gate_source_debug(uid: int, perm_val: int) -> str:
    """构造门控来源的调试字符串，便于排查。
    显示：perm(uid)=X, running_tasks, api_tpm_total, tpr, max, occupied, remaining, expected
    注：occupied=Σ(运行中任务的 permission)；expected=permission（不乘 tokens）。
    """
    try:
        # 运行中任务统计
        running_cnt = 0
        running_sum = 0
        # 配置聚合
        api_tpm = 0
        tpr = 0
        try:
            running_cnt = int(agg.get_running_tasks_count())  # type: ignore[attr-defined]
        except Exception:
            running_cnt = 0
        try:
            running_sum = int(agg.get_running_perm_sum())  # type: ignore[attr-defined]
        except Exception:
            running_sum = 0
        try:
            api_tpm = int(agg.get_api_tpm_total(0))  # type: ignore[attr-defined]
        except Exception:
            api_tpm = 0
        try:
            tpr = int(agg.get_tokens_per_req(0))  # type: ignore[attr-defined]
        except Exception:
            tpr = 0
        try:
            mx = float(agg.get_max_capacity_per_min(0.0))  # type: ignore[attr-defined]
        except Exception:
            mx = 0.0
        # occupied 统一为 req/min：使用 running_perm_sum
        occupied = float(max(0, running_sum))
        remaining = mx - occupied
        expected = float(max(0, perm_val))
        return (
            f"src: perm(uid)={perm_val}, running_tasks={running_cnt}, "
            f"api_tpm_total={api_tpm}, tpr={tpr}, max={mx:.4f}, occupied={occupied:.4f}, remaining={remaining:.4f}, expected={expected:.4f}"
        )
    except Exception:
        return f"src: perm(uid)={perm_val}"


def worker_queue_loop_for_user(uid: int) -> int:
    """
    基于队列的工作线程循环（Stage3/Stage2）
    - 从队列领取任务 -> 获取API Key -> 调用模型 -> 更新结果 -> 标记队列完成
    - 在任何异常路径确保 API Key 释放，任务在必要时放回 ready
    """
    relevant_count = 0
    # 优先从Redis获取 tokens_per_req，回退到DB
    try:
        tokens_per_req = agg.get_tokens_per_req(400)  # type: ignore[attr-defined]
    except Exception:
        tokens_per_req = db_reader.get_tokens_per_req(400)
    idle_rounds = 0
    processed_count = 0  # 处理计数

    utils.print_and_log(f"[worker-queue-{uid}] Starting for user {uid}")

    try:
        while True:
            # 队列是否还有属于该用户的任务（若无则退出）
            backlog_size = queue_manager.user_backlog_size(uid)
            if backlog_size <= 0:
                utils.print_and_log(f"[worker-queue-{uid}] No more tasks (pure queue mode), exiting")
                break

            # 门控：查看该用户队头，并判断 expected_used_capacity 与 remaining_capacity 条件
            head_task = queue_manager.peek_head_for_user(uid)  # 对该用户的队头
            if not head_task:
                time.sleep(0.2)
                continue

            # 读取 Redis 聚合容量与本用户权限
            max_cap = float(agg.get_max_capacity_per_min(0.0))
            perm_val = int(agg.get_uid_permission(uid) or 0)
            running_sum = int(agg.get_running_perm_sum())
            running_cnt = int(agg.get_running_tasks_count())

            # 条件：permission < remaining_capacity（统一单位 req/min）
            if not gate_permits(perm_val, tokens_per_req, max_cap, running_sum, running_cnt):
                # 不满足门控：等待并记录（频率控制）
                if idle_rounds % 20 == 0:  # 每 20 次输出一次等待日志
                    src = _gate_source_debug(uid, perm_val)
                    utils.print_and_log(
                        f"[gate-wait-{uid}] head_task={head_task['task_id']} (expected>=remaining) | {src}"
                    )
                    # 安全日志：若 permission 或 expected_used_capacity 异常偏大，额外提示（降低频率）
                    try:
                        if idle_rounds % 100 == 0 and max_cap > 0:
                            expected = float(max(0, perm_val))
                            if expected >= max_cap * 2:
                                utils.print_and_log(
                                    f"[warn-perm] uid={uid} permission({perm_val}) >> max_capacity({max_cap:.1f}); consider lowering permission or raising capacity"
                                )
                    except Exception:
                        pass
                idle_rounds += 1
                time.sleep(0.3)
                continue

            # 门控通过后再申请速率额度
            ok, _acc = rate_limiter.try_acquire_for_any_account(tokens_per_req)
            if not ok:
                time.sleep(0.2)
                continue

            # 获取 API Key（共享池，无预留/绑定）
            from ..config import config_loader as config
            api_key = None
            if getattr(config, 'unit_test_mode', False):
                api_key = "test-key"
                utils.print_and_log(f"[worker-queue-{uid}] Using unit test mode")
            else:
                # 优先使用配置文件中的第一条
                try:
                    keys_cfg = getattr(config, 'API_KEYS', []) or []
                except Exception:
                    keys_cfg = []
                if keys_cfg:
                    api_key = keys_cfg[0]
                else:
                    # 回退到数据库中的活跃账户列表（非独占读取）
                    try:
                        accounts = db_reader.get_active_api_accounts() or []
                        if accounts:
                            api_key = accounts[0].get('api_key')
                    except Exception:
                        api_key = None
            if not api_key:
                idle_rounds += 1
                if idle_rounds > 10:
                    utils.print_and_log(f"[worker-queue-{uid}] No API key available after retries, exiting")
                    break
                time.sleep(0.3)
                continue
            
            task = None
            running_incremented = False
            try:
                # 原子条件弹出（若 head 仍是队头）
                task = queue_manager.conditional_pop(int(head_task['task_id']), uid)
                if not task:
                    # 可能并发竞争失败或队头变化，重试
                    time.sleep(0.15)
                    continue

                idle_rounds = 0
                # 计入运行中统计（用于 occupied/remaining 实时计算）
                try:
                    # 以 uid 维度计数：仅在该 uid 首次从0->1个运行任务时，累计其 permission
                    try:
                        agg.incr_running_for_uid(uid, perm_val)  # type: ignore[attr-defined]
                    except Exception:
                        # 兼容回退
                        agg.incr_running_stats(perm_val)  # type: ignore[attr-defined]
                    running_incremented = True
                    # 顺带刷新一次剩余容量，便于观察
                    try:
                        agg.compute_and_set_remaining_capacity_per_min()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                except Exception:
                    pass

                utils.print_and_log(f"[worker-queue-{uid}] Processing task: {task} (perm={perm_val}, tpr={tokens_per_req})")
                
                # 处理任务
                processed_relevant = process_queue_task(task, api_key, uid)
                relevant_count += 1 if processed_relevant else 0
                processed_count += 1
                
                # 每处理10个任务输出一次进度
                if processed_count % 10 == 0:
                    utils.print_and_log(f"[worker-queue-{uid}] Processed {processed_count} tasks, {relevant_count} relevant")
                
            except Exception as e:
                # 处理失败：尝试将任务推回 ready
                utils.print_and_log(f"[worker-queue-{uid}] Unhandled error: {e}")
                import traceback
                traceback.print_exc()
                try:
                    if task and task.get('task_id'):
                        queue_manager.push_back_ready(int(task['task_id']))
                except Exception:
                    pass
            finally:
                # 共享模式下无需释放 API Key
                # 从运行中统计移除
                try:
                    if running_incremented:
                        try:
                            agg.decr_running_for_uid(uid, perm_val)  # type: ignore[attr-defined]
                        except Exception:
                            # 兼容回退
                            agg.decr_running_stats(perm_val)  # type: ignore[attr-defined]
                        try:
                            agg.compute_and_set_remaining_capacity_per_min()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                except Exception:
                    pass

    finally:
        # 线程结束前做一次收尾：关闭连接并尝试完成该用户的所有查询
        utils.print_and_log(f"[worker-queue-{uid}] Finalizing, processed={processed_count}, relevant={relevant_count}")
        try:
            finalize_user_queries(uid)
        except Exception as e:
            utils.print_and_log(f"[worker-queue-{uid}] Error finalizing queries: {e}")
        db_reader.close_thread_connection()

    return relevant_count


def check_and_finalize_query(query_table: str, query_index: int):
    """检查并完成查询"""
    try:
        progress = db_reader.compute_query_progress(query_table, query_index)
        
        # 每处理10个任务输出一次进度
        if progress['completed'] % 10 == 0:
            utils.print_and_log(
                f"[worker] Query {query_index} progress: "
                f"{progress['completed']}/{progress['total']} "
                f"({progress.get('percentage', 0):.1f}%)"
            )
        
        if progress['total'] > 0 and progress['completed'] >= progress['total']:
            db_reader.finalize_query_if_done(query_table, query_index)
            utils.print_and_log(f"[worker] Query {query_index} completed: all {progress['total']} tasks done")
    except Exception as e:
        utils.print_and_log(f"[worker] Failed to finalize query {query_index}: {e}")


def restore_thread_quota(uid: int):
    """恢复线程配额"""
    # 实现线程配额恢复逻辑
    pass


def finalize_user_queries(uid: int):
    """完成用户的所有查询"""
    try:
        infos = db_reader.get_active_queries_info()
        for info in infos:
            if info.get('uid') == uid:
                table_name = info.get('query_table')
                query_index = info.get('query_index')
                if table_name and query_index:
                    check_and_finalize_query(table_name, query_index)
    except Exception:
        pass


def process_queue_task(task: dict, api_key: str, uid: int) -> bool:
    """
    处理队列任务：
    - 输入: task {task_id, query_index, doi}
    - 流程: 查表名 -> 取论文信息 -> 调用模型 -> 写回结果 -> 标记队列完成
    - 返回: 是否相关（True/False）
    错误处理: 任意失败将尝试标记失败并返回 False。
    """
    task_id = int(task.get('task_id') or 0)
    query_index = int(task.get('query_index') or 0)
    doi = str(task.get('doi') or '')
    
    utils.print_and_log(f"[process_task] Starting: task_id={task_id}, query_index={query_index}, doi={doi[:30]}...")
    
    if task_id <= 0 or query_index <= 0 or not doi:
        utils.print_and_log(f"[process_task] Invalid task data")
        return False

    # 查找查询表名与条件
    qinfo = db_reader.get_query_log_by_index(query_index) or {}
    query_table = qinfo.get('query_table')
    rq_val = qinfo.get('research_question', '')
    req_val = qinfo.get('requirements', '')
    
    if not query_table:
        # 无法定位表，任务失败 (throttled logging + incremental backoff)
        utils.print_and_log(f"[process_task] Missing query_table for query_index={query_index}")
        try:
            queue_manager.mark_failed(task_id, "missing query_table")
        except Exception:
            pass
        return False

    # 获取论文信息
    info = db_reader.get_paper_title_abstract_by_doi(doi) or {}
    title = info.get('title', '')
    abstract = info.get('abstract', '')

    # 获取 search_id（用于结果回写）
    search_id = 0
    try:
        sid = db_reader.get_search_id_by_doi(query_table, query_index, doi)
        if sid:
            search_id = int(sid)
            utils.print_and_log(f"[process_task] Found search_id={search_id}")
    except Exception as e:
        utils.print_and_log(f"[process_task] Error getting search_id: {e}")
        search_id = 0

    if not title and not abstract:
        utils.print_and_log(f"[process_task] No paper information for doi={doi}")
        # 无论文信息，直接记为不相关并完成
        if search_id > 0:
            db_reader.update_search_result(
                query_table,
                search_id,
                False, "No paper information available",
                0, 0, 0, 0, 0
            )
        try:
            queue_manager.mark_done(task_id)
        except Exception:
            pass
        # 检查查询是否完成
        check_and_finalize_query(query_table, query_index)
        return False

    # 调用模型（单元测试模式或真实模式）
    from ..config import config_loader as config
    if getattr(config, 'unit_test_mode', False):
        # 单元测试模式：模拟结果
        import random
        is_rel = random.random() > 0.5
        reason = "Unit test mode result"
        prompt_tokens = 100
        completion_tokens = 50
        total_tokens = 150
        cache_hit_tokens = 0
        cache_miss_tokens = 100
        utils.print_and_log(f"[process_task] Unit test mode: relevant={is_rel}")
    else:
        try:
            result_dict = search_paper.search_relevant_papers(
                title, abstract, rq_val, req_val, api_key
            )
            is_rel = bool(result_dict.get('is_relevant', False))
            reason = result_dict.get('reason', '')
            prompt_tokens = int(result_dict.get('prompt_tokens', 0) or 0)
            completion_tokens = int(result_dict.get('completion_tokens', 0) or 0)
            total_tokens = prompt_tokens + completion_tokens
            cache_hit_tokens = int(result_dict.get('cache_hit_tokens', 0) or 0)
            cache_miss_tokens = int(result_dict.get('cache_miss_tokens', 0) or 0)
            utils.print_and_log(f"[process_task] Model result: relevant={is_rel}, tokens={total_tokens}")
        except Exception as e:
            utils.print_and_log(f"[process_task] Model call failed: {e}")
            is_rel = False
            reason = str(e)
            prompt_tokens = completion_tokens = total_tokens = 0
            cache_hit_tokens = cache_miss_tokens = 0

    # 将结果写回搜索表（修复缩进与异常处理）
    try:
        if search_id > 0:
            utils.print_and_log(f"[process_task] Updating search_id={search_id} with result={is_rel}")
            db_reader.update_search_result(
                query_table, search_id, is_rel, reason,
                prompt_tokens, completion_tokens, total_tokens,
                cache_hit_tokens, cache_miss_tokens
            )
        else:
            utils.print_and_log(f"[process_task] WARNING: No search_id found for doi={doi}")
        # 标记队列完成
        try:
            queue_manager.mark_done(task_id)
        except Exception:
            pass
        # 更新进度
        data.bump_progress(uid, query_index, 0.1)
        # 检查并在必要时完成查询
        check_and_finalize_query(query_table, query_index)
        utils.print_and_log(f"[process_task] Completed: task_id={task_id}, relevant={is_rel}")
        return bool(is_rel)
    except Exception as e:
        utils.print_and_log(f"[process_task] Writeback failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            queue_manager.mark_failed(task_id, str(e))
        except Exception:
            pass
        return False
