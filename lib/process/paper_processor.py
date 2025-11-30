"""
论文处理主模块 (新架构)
协调各个子模块完成论文处理任务

新架构变更:
- 使用 TaskQueue 管理任务队列
- 使用 query_dao 管理查询记录
- 使用 PaperBlocks 获取文献数据
- 移除了 queue_facade, rate_limiter_facade
"""

import os
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from . import data
from . import search_paper
from . import worker
from . import scheduler
from . import export
from ..log import utils
from ..config import config_loader as config
from language import language
from ..load_data import db_reader
from ..load_data.query_dao import (
    create_query_log, get_query_log, update_query_status,
    mark_query_completed, get_query_progress
)
from ..load_data.journal_dao import (
    get_journals_by_filters, count_papers_by_filters,
    get_journal_prices, get_year_number
)
from ..redis.task_queue import TaskQueue
from ..redis.paper_blocks import PaperBlocks
from ..redis.system_cache import SystemCache
from ..redis.system_config import SystemConfig
from ..redis.connection import redis_ping

# 导出兼容性
from .worker import ACTIVE_WORKERS
from .export import export_results_from_db, extract_url_from_entry
from .scheduler import start_background_scheduler


def process_papers(uid: int, search_params: dict, estimated_cost: float = None) -> Tuple[bool, str]:
    """
    处理论文的主函数 (新架构)
    
    Args:
        uid: 用户ID
        search_params: 搜索参数字典，包含:
            - research_question: 研究问题
            - requirements: 筛选要求
            - journals: 选中的期刊列表
            - start_year, end_year: 年份范围
            - include_all_years: 是否包含所有年份
        estimated_cost: 预估费用（修复31c：使用预估阶段计算的正确值）
        
    Returns:
        (success, query_id 或 error_message)
    """
    try:
        lang = language.get_text(config.LANGUAGE)
        ensure_directories(lang)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        data.result_file_name = f"Result_{timestamp}"

        # 从 search_params 提取参数
        rq = search_params.get('research_question', '')
        requirements = search_params.get('requirements', '')
        selected_folders = search_params.get('journals', [])
        start_year = search_params.get('start_year')
        end_year = search_params.get('end_year')
        include_all_years = search_params.get('include_all_years', True)
        year_range_info = search_params.get('year_range', 'All years')

        # 构建时间范围
        time_range = {
            "include_all": include_all_years,
            "start_year": start_year,
            "end_year": end_year,
        }

        # 获取期刊列表
        if not selected_folders:
            journals = get_journals_by_filters(time_range=time_range)
            selected_folders = [j['name'] for j in journals]

        # 统计论文数量
        paper_count = count_papers_by_filters(selected_folders, time_range)
        max_papers = paper_count  # 新架构默认处理全部
        data.total_papers_to_process = max_papers

        print_statistics(lang, max_papers, paper_count)

        if max_papers <= 0:
            utils.print_and_log(lang.get('no_paper_to_process', '无可处理的论文'))
            return False, "No papers to process"

        # 构建完整搜索参数（用于存储）
        full_search_params = {
            "research_question": rq,
            "requirements": requirements or "",
            "selected_journals": selected_folders,
            "year_range": year_range_info,
            "max_papers": max_papers,
        }

        # 修复31c：使用传入的正确estimated_cost，否则回退到简单计算
        if estimated_cost is None:
            estimated_cost = float(max_papers)
        
        # 创建查询记录
        query_id = create_query_log(
            uid=uid,
            search_params=full_search_params,
            estimated_cost=estimated_cost  # 使用正确的预估费用
        )

        if not query_id:
            utils.print_and_log("[ERROR] 创建查询记录失败")
            return False, "Failed to create query log"

        utils.print_and_log(f"[main] 创建查询: {query_id}")

        # 初始化进度跟踪
        utils.reset_progress_tracking(uid=uid, query_index=query_id, total=max_papers)
        setup_progress_context(uid, query_id)

        # 计算线程数
        num_threads = compute_worker_thread_count(max_papers, uid)
        utils.print_and_log(
            f"{lang['actual_threads_used'].format(threads=num_threads, avg=max_papers/num_threads if num_threads else 0)}"
        )

        # 启动处理
        start_processing(
            selected_folders, time_range, max_papers,
            query_id, uid, rq, requirements
        )

        utils.print_and_log(f"\n{lang.get('tasks_submitted', 'Tasks submitted for processing')}")
        utils.print_and_log(f"Query ID: {query_id}")
        utils.print_and_log(f"Total papers to process: {max_papers}")

        return True, query_id

    except Exception as e:
        utils.print_and_log(f"[ERROR] process_papers failed: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def process_papers_for_distillation(uid: int, original_query_id: str, 
                                   relevant_dois: List[str],
                                   research_question: str = "",
                                   requirements: str = "",
                                   doi_prices: Dict[str, int] = None,
                                   estimated_cost: float = None) -> Tuple[bool, str]:
    """
    蒸馏处理函数 (新架构)
    
    修复30：添加 research_question 和 requirements 参数，
    将用户在蒸馏时输入的研究问题存储到 search_params 中
    
    修复31：添加 doi_prices 和 estimated_cost 参数
    - doi_prices: 传递给Worker以避免重复查询价格
    - estimated_cost: 使用预估阶段计算的正确费用（考虑实际期刊价格）
    
    Args:
        uid: 用户ID
        original_query_id: 原始查询ID
        relevant_dois: 相关DOI列表
        research_question: 蒸馏研究问题（用户输入）
        requirements: 蒸馏筛选要求（用户输入）
        doi_prices: {doi: price} 映射（修复31：预估阶段收集的价格信息）
        estimated_cost: 预估费用（修复31b：使用预估阶段计算的正确值）
        
    Returns:
        (success, query_id 或 error_message)
    """
    try:
        lang = language.get_text(config.LANGUAGE)
        ensure_directories(lang)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        data.result_file_name = f"Distill_{timestamp}"

        paper_count = len(relevant_dois)
        data.total_papers_to_process = paper_count

        utils.print_and_log(f"\n开始蒸馏处理 {paper_count} 篇论文")

        if paper_count <= 0:
            utils.print_and_log("无可处理的论文")
            return False, "No papers to process for distillation"

        # 创建查询记录（修复30：存储用户输入的蒸馏研究问题）
        search_params = {
            "research_question": research_question,
            "requirements": requirements,
            "is_distillation": True,
            "original_query_id": original_query_id,
            "doi_count": paper_count,
        }

        # 修复31b：使用传入的正确estimated_cost，否则回退到简单计算
        if estimated_cost is None:
            distill_rate = SystemConfig.get_distill_rate()
            estimated_cost = float(paper_count) * distill_rate
        
        query_id = create_query_log(
            uid=uid,
            search_params=search_params,
            estimated_cost=estimated_cost  # 使用正确的预估费用
        )

        if not query_id:
            utils.print_and_log("[ERROR] 创建蒸馏查询记录失败")
            return False, "Failed to create distillation query log"

        # 初始化进度跟踪
        utils.reset_progress_tracking(uid=uid, query_index=query_id, total=paper_count)

        # 计算线程数
        num_threads = compute_worker_thread_count(paper_count, uid)
        utils.print_and_log(f"使用线程数: {num_threads}")

        # 启动进度监控
        start_progress_monitor(num_threads)

        # 执行蒸馏处理（修复31：传递doi_prices）
        def run_distillation():
            try:
                distillation_producer(relevant_dois, query_id, uid, 
                                     research_question, requirements, doi_prices)
                scheduler.start_background_scheduler()
            except Exception as e:
                utils.print_and_log(f"[distill] Error in distillation: {e}")
                try:
                    mark_query_completed(query_id)
                except Exception:
                    pass
        
        distill_thread = threading.Thread(target=run_distillation, daemon=True)
        distill_thread.start()

        setup_progress_context(uid, query_id)
        utils.print_and_log(f"蒸馏任务已提交: {query_id}")

        return True, query_id

    except Exception as e:
        utils.print_and_log(f"[ERROR] process_papers_for_distillation failed: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


# === 辅助函数 ===

def ensure_directories(lang):
    """确保必要的目录存在"""
    result_folder = config.RESULT_FOLDER
    if not os.path.exists(result_folder):
        os.makedirs(result_folder)

    log_folder = config.LOG_FOLDER
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)
        utils.print_and_log(f"{lang['log_folder_created'].format(path=log_folder)}")


def print_statistics(lang, max_papers, paper_count):
    """输出统计信息"""
    utils.print_and_log(f"\n{lang['start_processing_papers'].format(count=max_papers)}")
    utils.print_and_log(f"{lang['total_papers'].format(count=paper_count)}")
    
    try:
        perm = get_user_max_threads(1)
        utils.print_and_log(f"{lang['max_parallel_config'].format(count=perm)}")
    except Exception:
        pass


def get_user_max_threads(uid: int) -> int:
    """获取用户最大线程数限制"""
    user_max_threads = 50
    try:
        from ..webserver.auth import get_user_info
        user_info_result = get_user_info(uid)
        if user_info_result.get('success') and user_info_result.get('user_info'):
            user_max_threads = user_info_result['user_info'].get('permission', 50)
    except Exception as e:
        utils.print_and_log(f"获取用户权限失败，使用默认值: {e}")
    return user_max_threads


def compute_worker_thread_count(total_tasks: int, uid: int) -> int:
    """计算工作线程数量"""
    if total_tasks <= 0:
        return 0
    user_limit = get_user_max_threads(uid)
    return min(int(total_tasks or 0), int(user_limit or 0))


def setup_progress_context(uid: int, query_id: str):
    """设置进度上下文"""
    try:
        data.current_query_index = query_id
        data.current_uid = uid
    except Exception:
        pass


def start_progress_monitor(num_threads: int):
    """启动进度监控"""
    data.progress_stop_event.clear()
    data.active_threads = num_threads
    try:
        progress_thread = threading.Thread(target=utils.progress_monitor, daemon=True)
        progress_thread.start()
    except Exception:
        pass


def start_processing(selected_folders: List[str], time_range: Dict, 
                    max_papers: int, query_id: str, uid: int,
                    rq: str, requirements: str):
    """启动处理任务"""
    producer_done = threading.Event()
    producer_exception = [None]
    
    def producer():
        try:
            produce_tasks(
                selected_folders, time_range, max_papers,
                query_id, uid, rq, requirements
            )
        except Exception as e:
            producer_exception[0] = e
            utils.print_and_log(f"[producer] Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            producer_done.set()
    
    producer_thread = threading.Thread(target=producer, daemon=True)
    producer_thread.start()
    
    # 启动调度器
    try:
        scheduler.start_background_scheduler()
    except Exception:
        pass
    utils.print_and_log(f"[main] Scheduler started (background)")
    
    producer_done.wait(timeout=0.1)
    
    if producer_exception[0]:
        utils.print_and_log(f"[main] Producer failed: {producer_exception[0]}")
        mark_query_completed(query_id)
        return
    
    time.sleep(0.5)
    
    # 检查进度
    if redis_ping():
        status = TaskQueue.get_status(uid, query_id)
        if status:
            utils.print_and_log(f"[main] Query {query_id} status: {status.get('state')}")
    
    utils.print_and_log(f"[main] Tasks submitted for query {query_id}")


def produce_tasks(selected_folders: List[str], time_range: Dict,
                 max_papers: int, query_id: str, uid: int,
                 rq: str, requirements: str):
    """生产任务到Redis队列"""
    utils.print_and_log(f"[producer] Starting task production for query {query_id}")
    
    start_year = time_range.get("start_year")
    end_year = time_range.get("end_year")
    include_all = time_range.get("include_all", True)
    
    block_keys = []
    total_papers = 0
    
    # 遍历期刊，收集Block Keys
    for journal in selected_folders:
        year_counts = get_year_number(journal)
        if not year_counts:
            continue
        
        for year, count in year_counts.items():
            # 年份过滤
            if not include_all:
                if start_year and year < start_year:
                    continue
                if end_year and year > end_year:
                    continue
            
            block_key = f"meta:{journal}:{year}"
            block_keys.append(block_key)
            total_papers += count
            
            if total_papers >= max_papers:
                break
        
        if total_papers >= max_papers:
            break
    
    utils.print_and_log(f"[producer] Collected {len(block_keys)} blocks, ~{total_papers} papers")
    
    if not block_keys:
        utils.print_and_log("[producer] No blocks to process")
        mark_query_completed(query_id)
        return
    
    # 初始化任务状态
    TaskQueue.init_status(uid, query_id, len(block_keys))
    
    # 将Block Keys推入队列
    TaskQueue.enqueue_blocks(uid, query_id, block_keys)
    
    # 更新查询状态
    update_query_status(query_id, 'RUNNING')
    
    utils.print_and_log(f"[producer] Enqueued {len(block_keys)} blocks for query {query_id}")


def distillation_producer(relevant_dois: List[str], query_id: str, 
                          uid: int, rq: str, requirements: str,
                          doi_prices: Dict[str, int] = None):
    """
    蒸馏任务生产者（修复29重构）
    
    修复29：创建蒸馏专用Block（distill:前缀），只包含相关DOI的Bib数据
    避免处理整个meta:Block导致超额计费
    
    修复31：在Block中存储价格信息，Worker直接读取无需再次查询
    存储格式：{doi: json.dumps({"bib": bib, "price": price})}
    """
    from ..redis.connection import get_redis_client
    import json
    
    utils.print_and_log(f"[distill] Starting distillation for {len(relevant_dois)} DOIs")
    
    client = get_redis_client()
    if not client:
        utils.print_and_log("[distill] Redis client not available")
        mark_query_completed(query_id)
        return
    
    # 确保doi_prices是字典
    if doi_prices is None:
        doi_prices = {}
    
    # 按每100个DOI划分为一个蒸馏Block
    DISTILL_BLOCK_SIZE = 100
    block_keys = []
    
    for i in range(0, len(relevant_dois), DISTILL_BLOCK_SIZE):
        batch_dois = relevant_dois[i:i + DISTILL_BLOCK_SIZE]
        block_index = len(block_keys)
        distill_block_key = f"distill:{uid}:{query_id}:{block_index}"
        
        # 收集这批DOI的Bib数据和价格
        block_data = {}
        for doi in batch_dois:
            # 从meta:Block获取Bib数据
            result = PaperBlocks.get_paper_by_doi(doi)
            if result:
                _, bib = result
                if bib:
                    # 修复31：存储格式包含bib和price
                    price = doi_prices.get(doi, 1)  # 从预估阶段获取价格，默认1
                    block_data[doi] = json.dumps({"bib": bib, "price": price})
        
        if block_data:
            try:
                # 存储蒸馏专用Block
                client.hset(distill_block_key, mapping=block_data)
                # 设置7天过期
                client.expire(distill_block_key, 7 * 24 * 3600)
                block_keys.append(distill_block_key)
            except Exception as e:
                utils.print_and_log(f"[distill] 存储Block失败: {e}")
    
    if not block_keys:
        utils.print_and_log("[distill] No blocks created for DOIs")
        mark_query_completed(query_id)
        return
    
    # 初始化任务状态
    TaskQueue.init_status(uid, query_id, len(block_keys))
    
    # 将Block Keys推入队列
    TaskQueue.enqueue_blocks(uid, query_id, block_keys)
    
    # 更新查询状态
    update_query_status(query_id, 'RUNNING')
    
    utils.print_and_log(f"[distill] Enqueued {len(block_keys)} blocks for distillation")


def output_final_statistics(lang, uid, query_id):
    """输出最终统计信息"""
    total_elapsed_time = time.time() - (data.start_time or time.time())
    hours = int(total_elapsed_time // 3600)
    minutes = int((total_elapsed_time % 3600) // 60)
    seconds = int(total_elapsed_time % 60)
    
    processed_count = get_processed_count(uid, query_id)
    
    average_time = total_elapsed_time / processed_count if processed_count > 0 else 0
    actual_speed = processed_count / total_elapsed_time if total_elapsed_time > 0 else 0
    
    utils.print_and_log(lang['time_statistics'])
    utils.print_and_log(lang['total_time'].format(
        hours=hours, minutes=minutes, seconds=seconds
    ))
    utils.print_and_log(lang['avg_time_per_paper'].format(
        time=average_time, threads=data.active_threads or 0
    ))
    utils.print_and_log(lang['processing_speed'].format(speed=actual_speed))
    
    if data.full_log_file:
        data.full_log_file.close()


def get_processed_count(uid: int, query_id: str) -> int:
    """获取已处理数量"""
    try:
        if redis_ping():
            return TaskQueue.get_finished_count(uid, query_id)
        return 0
    except Exception:
        return 0
