"""
论文处理主模块
协调各个子模块完成论文处理任务
"""

import os
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import data
from . import search_paper
from . import worker
from . import scheduler
from . import export
from ..log import utils
from ..config import config_loader as config
from language import language
from ..load_data import db_reader
from . import queue_facade
from . import rate_limiter_facade as rate_limiter

# 导出兼容性（保持向后兼容）
# 不再在此导出 scheduler 内部符号以做兼容
from .worker import ACTIVE_WORKERS
from .export import export_results_from_db, extract_url_from_entry


def process_papers(rq, requirements, n, selected_folders=None, 
                   year_range_info=None, uid: int = 1, query_index: int = None):
    """
    处理论文的主函数
    """
    # 获取语言文本
    lang = language.get_text(config.LANGUAGE)

    # 确保目录存在
    ensure_directories(lang)

    # 生成时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    query_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data.result_file_name = f"Result_{timestamp}"

    # 准备查询信息
    folder_info = ", ".join(selected_folders) if selected_folders else "All folders"
    year_info = year_range_info if year_range_info else "All years"
    db_year_info = year_info.replace("当前设置：", "").strip()

    # 获取文件夹列表
    if not selected_folders:
        selected_folders = db_reader.get_subfolders() or []

    # 统计论文数量
    include_all_years = config.INCLUDE_ALL_YEARS
    start_year = config.YEAR_RANGE_START
    end_year = config.YEAR_RANGE_END
    
    paper_count = db_reader.count_papers(
        selected_folders, include_all_years, start_year, end_year
    )

    # 确定处理数量
    max_papers = paper_count if n == -1 else min(n, paper_count)
    data.total_papers_to_process = max_papers

    # 输出统计信息
    print_statistics(lang, max_papers, paper_count)

    # 创建搜索表
    today_table_name = create_search_table()

    # 创建查询日志
    if query_index is None:
        query_index = create_query_log(
            query_time, folder_info, db_year_info, 
            rq, requirements, today_table_name, 
            uid, max_papers
        )

    # 初始化进度跟踪
    utils.reset_progress_tracking(uid=uid, query_index=query_index, total=max_papers)
    setup_progress_context(uid, query_index)

    if max_papers <= 0:
        utils.print_and_log(lang.get('no_paper_to_process', '无可处理的论文'))
        finalize_empty_query(query_index)
        return

    # 计算线程数（共享 Key 池：不再依赖可用 Key 数量）
    num_threads = compute_worker_thread_count(max_papers, uid)

    avg_per_thread = (max_papers / num_threads) if num_threads else 0

    utils.print_and_log(
        f"{lang['actual_threads_used'].format(threads=num_threads, avg=avg_per_thread)}"
    )

    # 启动处理
    start_processing(
        selected_folders, include_all_years, start_year, end_year,
        max_papers, today_table_name, query_index, uid
    )

    # 立即输出统计信息并返回（不等待任务完成）
    utils.print_and_log(f"\n{lang.get('tasks_submitted', 'Tasks submitted for processing')}")
    utils.print_and_log(f"Query index: {query_index}")
    utils.print_and_log(f"Total papers to process: {max_papers}")
    utils.print_and_log(f"Background processing started. You can check progress through the web interface.")
    
    # 注意：不再调用 output_final_statistics，因为任务还没完成
    # 最终统计应该在 worker 或 scheduler 完成所有任务后输出


def process_papers_for_distillation(rq, requirements, relevant_dois, 
                                   uid: int = 1, query_index: int = None, 
                                   original_query_index: int = None):
    """
    蒸馏处理函数：基于DOI列表处理论文
    """
    # 获取语言文本
    lang = language.get_text(config.LANGUAGE)

    # 确保目录存在
    ensure_directories(lang)

    # 生成时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    query_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data.result_file_name = f"Distill_{timestamp}"

    # 统计论文数量
    paper_count = len(relevant_dois)
    data.total_papers_to_process = paper_count

    utils.print_and_log(f"\n开始蒸馏处理 {paper_count} 篇论文")
    utils.print_and_log(f"原始查询索引: {original_query_index}")
    utils.print_and_log(f"蒸馏查询索引: {query_index}")

    # 创建搜索表
    today_table_name = create_search_table()

    if paper_count <= 0:
        utils.print_and_log("无可处理的论文")
        finalize_empty_query(query_index)
        return

    # 初始化进度跟踪
    utils.reset_progress_tracking(uid=uid, query_index=query_index, total=paper_count)

    # 计算线程数
    # 计算线程数（共享 Key 池：不再依赖可用 Key 数量）
    num_threads = compute_worker_thread_count(paper_count, uid)
    utils.print_and_log(f"使用线程数: {num_threads}")

    # 启动进度监控
    start_progress_monitor(num_threads)

    # 执行蒸馏处理（非阻塞）
    def run_distillation():
        try:
            distillation_producer(relevant_dois, today_table_name, query_index, uid)
            
            scheduler.start_background_scheduler()
        except Exception as e:
            utils.print_and_log(f"[distill] Error in distillation: {e}")
            # 确保即使出错也标记查询
            try:
                db_reader.mark_searching_log_completed(query_index)
            except Exception:
                pass
    
    import threading
    distill_thread = threading.Thread(target=run_distillation, daemon=True)
    distill_thread.start()

    # 设置进度上下文
    setup_progress_context(uid, query_index)

    utils.print_and_log("蒸馏任务已提交到后台处理队列")
    utils.print_and_log(f"蒸馏查询索引: {query_index}")
    utils.print_and_log(f"论文数量: {paper_count}")

    # 立即返回，不等待完成


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
    
    # 共享 Key 池下并发由用户权限限制，不再展示“可用 Key 数量”
    try:
        perm = get_user_max_threads(1)
        utils.print_and_log(f"{lang['max_parallel_config'].format(count=perm)}")
    except Exception:
        pass


def get_user_max_threads(uid: int) -> int:
    """获取用户最大线程数限制"""
    user_max_threads = 50  # 默认值
    try:
        from ..webserver.auth import get_user_info
        user_info_result = get_user_info(uid)
        if user_info_result.get('success') and user_info_result.get('user_info'):
            user_max_threads = user_info_result['user_info'].get('permission', 50)
    except Exception as e:
        utils.print_and_log(f"获取用户权限失败，使用默认值: {e}")
    return user_max_threads


# 已移除按 Key 并发：不再提供 get_available_keys，统一共享池模型

def compute_worker_thread_count(total_tasks: int, uid: int, available_keys: Optional[int] = None) -> int:
    """统一计算初始工作线程数量（共享 API Key 池下的简化版）
    逻辑：
    - 仅受总任务数与用户权限（最大线程数）限制；不再受可用 Key 数量限制
    """
    if total_tasks <= 0:
        return 0
    user_limit = get_user_max_threads(uid)
    return min(int(total_tasks or 0), int(user_limit or 0))

def create_search_table() -> str:
    """创建今日搜索表"""
    today_table_name = db_reader.get_search_table_name()
    try:
        db_reader.create_search_table(today_table_name)
        utils.print_and_log(f"确保搜索表存在: {today_table_name}")
    except Exception as e:
        utils.print_and_log(f"创建搜索表失败: {e}")
    return today_table_name


def create_query_log(query_time, folder_info, year_info, rq, requirements, 
                    table_name, uid, max_papers) -> Optional[int]:
    """创建查询日志"""
    try:
        return db_reader.insert_searching_log(
            query_time=query_time,
            selected_folders=folder_info,
            year_range=year_info,
            research_question=rq,
            requirements=requirements or "",
            query_table=table_name,
            uid=uid,
            total_papers_count=max_papers,
            is_distillation=False,
            is_visible=True
        )
    except Exception as e:
        utils.print_and_log(f"初始化检索日志失败：{e}")
        return None


def setup_progress_context(uid: int, query_index: Optional[int]):
    """设置进度上下文"""
    try:
        data.current_query_index = query_index
        data.current_uid = uid
        if query_index:
            db_reader.set_query_start_time_if_absent(int(query_index))
            utils.print_and_log(f"[progress] query_index={query_index} start_time initialized")
    except Exception:
        pass


def finalize_empty_query(query_index: Optional[int]):
    """完成空查询"""
    if query_index is not None:
        try:
            db_reader.mark_searching_log_completed(query_index)
        except Exception:
            pass


def start_progress_monitor(num_threads: int):
    """启动进度监控"""
    data.progress_stop_event.clear()
    data.active_threads = num_threads
    # 取消单 Leader 策略：所有实例可启动进度监控线程
    try:
        import threading
        progress_thread = threading.Thread(target=utils.progress_monitor, daemon=True)
        progress_thread.start()
    except Exception:
        pass


def start_processing(selected_folders, include_all_years, start_year, end_year,
                    max_papers, table_name, query_index, uid):
    """启动处理任务"""
    import threading
    
    # 使用事件来同步生产者完成
    producer_done = threading.Event()
    producer_exception = [None]  # 用列表存储异常，因为闭包中不能直接赋值
    
    # 生产者线程
    def producer():
        try:
            produce_tasks(
                selected_folders, include_all_years, start_year, end_year,
                max_papers, table_name, query_index, uid
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
    
    # 统一由调度器管理消费：立即确保调度器运行，避免因生产耗时而阻塞消费
    try:
        scheduler.start_background_scheduler()
    except Exception:
        pass
    utils.print_and_log(f"[main] Scheduler ensured running (background)")
    
    # 不阻塞等待生产者；允许生产与消费并行推进（仅做极短等待用于日志节奏）
    producer_done.wait(timeout=0.1)
    
    # 检查生产者是否出错
    if producer_exception[0]:
        utils.print_and_log(f"[main] Producer failed with error: {producer_exception[0]}")
        db_reader.mark_searching_log_completed(query_index)
        return
    
    # 可选：短暂等待提升首批可见性（不影响并行推进）
    import time
    time.sleep(0.5)
    
    # 检查是否有任务产生
    progress = db_reader.compute_query_progress(table_name, query_index)
    utils.print_and_log(f"[main] Query {query_index} progress after production: {progress}")
    
    if progress['total'] == 0:
        utils.print_and_log(f"[main] INFO: No tasks visible yet for query {query_index} (production may still be running)")
        # 仅做可见性检查，不做提前完成标记，避免大批量生产时误判
        conn = db_reader._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE query_index=%s", (query_index,))
                (count,) = cursor.fetchone()
                utils.print_and_log(f"[main] Direct table check: {count} rows for query_index={query_index}")
        finally:
            conn.close()
        return
    
    utils.print_and_log(f"[main] Created {progress['total']} tasks for query {query_index}")
    
    # 调度器已启动于前；此处仅记录
    utils.print_and_log(f"[main] Tasks submitted and scheduler is consuming in background")


def produce_tasks(selected_folders, include_all_years, start_year, end_year,
                 max_papers, table_name, query_index, uid):
    """生产任务到搜索表"""
    utils.print_and_log(f"[producer] Starting task production for query {query_index}")
    utils.print_and_log(f"[producer] Parameters: folders={selected_folders}, all_years={include_all_years}, years={start_year}-{end_year}, max={max_papers}")
    
    # 获取价格计算器
    calculator = get_price_calculator(table_name)
    
    paper_count = 0
    rows_buffer = []
    BATCH_SIZE = 100  # 降低批量大小，更快看到效果
    
    task_rows = []
    
    utils.print_and_log(f"[producer] Fetching papers from database...")
    
    try:
        # 使用迭代器逐批获取论文
        paper_iterator = db_reader.fetch_papers_iter(
            selected_folders, include_all_years, start_year, end_year, batch_size=100
        )
        
        for paper in paper_iterator:
            if paper_count >= max_papers:
                utils.print_and_log(f"[producer] Reached max papers limit: {max_papers}")
                break
            paper_count += 1
            
            # 每10篇输出一次进度
            if paper_count % 10 == 0:
                utils.print_and_log(f"[producer] Processing paper {paper_count}/{max_papers}")
            
            # 处理DOI
            doi = paper.get('doi', '')
            if not doi:
                title = paper.get('title', f'paper_{paper_count}')
                doi = f"no_doi_{hashlib.md5(title.encode()).hexdigest()[:10]}"
                paper['doi'] = doi
            
            # 计算价格
            price = calculate_paper_price(calculator, paper)
            
            # 收集数据
            rows_buffer.append((uid, query_index, doi, float(price)))
            task_rows.append({"uid": uid, "query_index": query_index, "doi": doi})
            
            # 批量插入
            if len(rows_buffer) >= BATCH_SIZE:
                inserted = flush_buffer(table_name, rows_buffer, BATCH_SIZE)
                utils.print_and_log(f"[producer] Inserted batch: {inserted} tasks to {table_name}")
                rows_buffer.clear()  # 清空缓冲区
                
                if task_rows:
                    queue_facade.enqueue_tasks_for_query(uid, query_index, 
                        [r["doi"] for r in task_rows])
                    task_rows.clear()
        
        # 处理剩余数据
        if rows_buffer:
            inserted = flush_buffer(table_name, rows_buffer, BATCH_SIZE)
            utils.print_and_log(f"[producer] Inserted final batch: {inserted} tasks to {table_name}")
        if task_rows:
            queue_facade.enqueue_tasks_for_query(uid, query_index, 
                [r["doi"] for r in task_rows])
        
        utils.print_and_log(f"[producer] Production completed: {paper_count} tasks for query {query_index}")
        
        # 验证数据是否写入
        conn = db_reader._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}` WHERE query_index=%s", (query_index,))
                (verified_count,) = cursor.fetchone()
                utils.print_and_log(f"[producer] Verification: {verified_count} rows in {table_name} for query_index={query_index}")
        finally:
            conn.close()
        
    except Exception as e:
        utils.print_and_log(f"[producer] Error producing tasks: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # 关闭计算器
        if calculator:
            calculator.close()


def distillation_producer(relevant_dois, table_name, query_index, uid):
    """蒸馏任务生产者"""
    calculator = get_price_calculator(table_name)
    
    rows_buffer = []
    BATCH_SIZE = 1000
    queue_enabled = True  # 固化队列模式启用
    task_rows = []
    
    for doi in relevant_dois:
        # 获取价格
        price = 1.0
        if calculator:
            prices = db_reader.get_prices_by_dois([doi])
            price = float(prices.get(doi, 1.0))
        
        # 收集数据
        rows_buffer.append((uid, query_index, doi, price))
        if queue_enabled:
            task_rows.append(doi)
        
        # 批量插入
        if len(rows_buffer) >= BATCH_SIZE:
            flush_buffer(table_name, rows_buffer, BATCH_SIZE)
            if queue_enabled and task_rows:
                queue_facade.enqueue_tasks_for_query(uid, query_index, task_rows)
                task_rows.clear()
    
    # 处理剩余数据
    if rows_buffer:
        flush_buffer(table_name, rows_buffer, BATCH_SIZE)
    if queue_enabled and task_rows:
        queue_facade.enqueue_tasks_for_query(uid, query_index, task_rows)
    
    if calculator:
        calculator.close()


def get_price_calculator(table_name):
    """获取价格计算器"""
    try:
        from ..price_calculate import PriceCalculator
        calculator = PriceCalculator()
        calculator.add_price_column_to_search_table(table_name)
        return calculator
    except Exception as e:
        print(f"初始化价格计算器失败: {e}")
        return None


def calculate_paper_price(calculator, paper):
    """计算论文价格"""
    if not calculator:
        return 1.0
    
    source_folder = paper.get('source_folder', '')
    try:
        return float(calculator.get_journal_price(source_folder))
    except Exception:
        return 1.0


def flush_buffer(table_name, buffer, batch_size):
    """批量插入缓冲数据"""
    if not buffer:
        return 0
    
    try:
        utils.print_and_log(f"[flush] Inserting {len(buffer)} rows to {table_name}")
        inserted = db_reader.insert_search_doi_bulk(table_name, buffer, batch_size)
        utils.print_and_log(f"[flush] Successfully inserted {inserted} rows")
        return inserted
    except Exception as e:
        utils.print_and_log(f"[flush] Error inserting batch: {e}")
        # 尝试逐条插入
        inserted = 0
        for row in buffer:
            try:
                uid, query_index, doi, price = row
                sid = db_reader.insert_search_doi(table_name, doi, uid, query_index, price)
                if sid:
                    inserted += 1
            except Exception as e2:
                utils.print_and_log(f"[flush] Failed to insert doi {doi}: {e2}")
        utils.print_and_log(f"[flush] Fallback inserted {inserted} rows one by one")
        return inserted
    finally:
        buffer.clear()


def check_query_completion(table_name, query_index, uid):
    """检查查询是否完成"""
    try:
        db_reader.check_search_table_data(table_name)
        
        # 检查是否已完成
        if query_index:
            progress = db_reader.compute_query_progress(table_name, query_index)
            if progress['total'] > 0 and progress['completed'] >= progress['total']:
                db_reader.finalize_query_if_done(table_name, query_index)
                utils.print_and_log(f"[main] Query {query_index} completed on submission")
    except Exception as e:
        utils.print_and_log(f"完成检查异常：{e}")


def output_final_statistics(lang, uid, query_index):
    """输出最终统计信息"""
    total_elapsed_time = time.time() - (data.start_time or time.time())
    hours = int(total_elapsed_time // 3600)
    minutes = int((total_elapsed_time % 3600) // 60)
    seconds = int(total_elapsed_time % 60)
    
    # 获取处理数量
    processed_count = get_processed_count(uid, query_index)
    
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
    utils.print_and_log(lang['token_statistics'])
    utils.print_and_log(lang['input_tokens'].format(
        total=data.prompt_tokens_used, 
        hit=data.prompt_cache_hit_tokens_used, 
        miss=data.prompt_cache_miss_tokens_used
    ))
    utils.print_and_log(lang['output_tokens'].format(count=data.completion_tokens_used))
    utils.print_and_log(lang['total_tokens'].format(count=data.token_used))
    utils.print_and_log(lang['result_files'])
    utils.print_and_log("  处理完成，结果文件可通过下载功能获取")
    
    if data.full_log_file:
        data.full_log_file.close()


def output_distillation_statistics(paper_count):
    """输出蒸馏统计信息"""
    total_elapsed_time = time.time() - data.start_time
    hours = int(total_elapsed_time // 3600)
    minutes = int((total_elapsed_time % 3600) // 60)
    seconds = int(total_elapsed_time % 60)
    
    utils.print_and_log("蒸馏任务统计:")
    utils.print_and_log(f"提交时间: {hours}小时{minutes}分钟{seconds}秒")
    utils.print_and_log(f"论文数量: {paper_count}")
    utils.print_and_log("蒸馏结果可通过下载功能获取")
    
    if data.full_log_file:
        data.full_log_file.close()


def get_processed_count(uid, query_index):
    """获取已处理数量"""
    try:
        bucket = data.read_bucket(uid, query_index) if query_index else None
        processed_count = bucket.get('processed') if bucket else 0
        
        if processed_count == 0 and query_index:
            # 从数据库获取
            row = db_reader.get_query_log_by_index(int(query_index)) or {}
            table_name = row.get('query_table', '')
            if table_name:
                progress = db_reader.compute_query_progress(table_name, query_index)
                processed_count = progress.get('completed', 0)
                
        return processed_count
    except Exception:
        return 0
