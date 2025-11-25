import threading
import time
from datetime import datetime, timedelta
from ..process import data
from ..config import config_loader as config

def print_and_log(message="", thread_id=None):
    """
    同时打印到控制台（已移除写入完整日志文件）
    """
    if thread_id is not None:
        message = f"[Thread-{thread_id}] {message}"
    
    with data.file_write_lock:
        print(message)

def progress_monitor():
    """新版进度监控：仅展示当前聚焦 (data.current_uid, data.current_query_index) 的隔离进度。
    优先以 DB query_log.start_time 为起点；定期校正 total/processed 以防回滚或服务重启。"""
    while not data.progress_stop_event.is_set():
        # 节流，避免忙等（300-500ms）
        time.sleep(0.5)
        try:
            uid = getattr(data, 'current_uid', None)
            qidx = getattr(data, 'current_query_index', None)
            if uid is None or qidx is None:
                continue  # 没有聚焦查询

            # 读取桶（内存）
            bucket = data.read_bucket(uid, qidx)
            if not bucket:
                continue
            processed = int(bucket.get('processed') or 0)
            total_hint = int(bucket.get('total') or 0)

            # 定期（每6次循环≈3s）用 DB 校正 total/processed，避免回滚缺口或服务重启后丢失
            try:
                tick = int(time.time())
                if tick % 3 == 0:  # 简单节流：大约每3秒校正一次
                    from ..load_data import db_reader
                    # 获取表名与 total/completed
                    row = db_reader.get_query_log_by_index(int(qidx)) or {}
                    table_name = row.get('query_table') or ''
                    if table_name:
                        prog = db_reader.compute_query_progress(table_name, int(qidx)) or {}
                        db_total = int(prog.get('total') or 0)
                        db_completed = int(prog.get('completed') or 0)
                        # 若 DB total > 内存 total，更新桶 total
                        if db_total > total_hint:
                            data.update_bucket_total(uid, qidx, db_total)
                            total_hint = db_total
                        # 若 DB completed > 内存 processed（服务重启或首次初始化），提升 processed
                        if db_completed > processed:
                            # 直接写回桶（差值不追溯单篇 times）
                            with data.progress_map_lock:
                                b2 = data.progress_map.get((uid, qidx))
                                if b2:
                                    b2['processed'] = db_completed
                            processed = db_completed
                        # 若 DB completed == total 并 >0，证明已完成，可考虑后续停止进度线程（由调度器完成）
            except Exception:
                pass

            if processed <= 0:
                continue

            # 进度百分比（夹取）
            if total_hint > 0:
                current_progress = (processed / total_hint) * 100.0
            else:
                current_progress = 0.0

            # 使用 DB start_time 优先
            elapsed_time = None
            try:
                from ..load_data import db_reader
                db_st = db_reader.get_query_start_time(int(qidx))
            except Exception:
                db_st = None
            if db_st is not None:
                elapsed_time = max(0.0, time.time() - db_st.timestamp())
            else:
                # 回退桶内 start_time（若尚未设置则初始化）
                if bucket.get('start_time') is None:
                    data.set_bucket_start_time_if_absent(uid, qidx, time.time())
                    bucket = data.read_bucket(uid, qidx) or bucket
                st_local = bucket.get('start_time') or time.time()
                elapsed_time = max(0.0, time.time() - float(st_local))

            hours_elapsed = int(elapsed_time // 3600)
            minutes_elapsed = int((elapsed_time % 3600) // 60)
            seconds_elapsed = int(elapsed_time % 60)

            # 平均单篇耗时（优先最近窗口）
            recent_times = bucket.get('times') or []
            if recent_times:
                avg_time_per_paper = sum(recent_times) / len(recent_times)
            else:
                avg_time_per_paper = elapsed_time / processed if processed > 0 else 0

            # 考虑并发的实际速度/单篇耗时反推
            actual_papers_per_second = processed / elapsed_time if elapsed_time > 0 else 0
            actual_time_per_paper = 1 / actual_papers_per_second if actual_papers_per_second > 0 else avg_time_per_paper

            remaining = max(0, (total_hint if total_hint > 0 else 0) - processed)
            if data.active_threads > 0:
                estimated_remaining_time = (remaining * avg_time_per_paper) / data.active_threads
            else:
                estimated_remaining_time = remaining * avg_time_per_paper

            hours_remaining = int(estimated_remaining_time // 3600)
            minutes_remaining = int((estimated_remaining_time % 3600) // 60)
            seconds_remaining = int(estimated_remaining_time % 60)

            estimated_completion_time = datetime.now() + timedelta(seconds=estimated_remaining_time)
            formatted_completion_time = estimated_completion_time.strftime("%Y_%m_%d %H:%M:%S")

            # Token 统计仍使用全局（当前查询期间基本对应该查询）
            current_total_tokens = data.token_used
            avg_tokens_per_paper = current_total_tokens / processed if processed > 0 else 0
            estimated_total_tokens = avg_tokens_per_paper * (total_hint if total_hint > 0 else processed)
            avg_prompt_tokens = data.prompt_tokens_used / processed if processed > 0 else 0
            avg_completion_tokens = data.completion_tokens_used / processed if processed > 0 else 0
            
            # 导入语言模块
            from language import language
            from ..config import config_loader as config
            lang = language.get_text(config.LANGUAGE)
            
            # 进度显示夹取，避免显示超过100%（例如任务重复或其他查询的进度被合并计数时）
            display_processed = processed if not total_hint or total_hint <= 0 else min(processed, total_hint)
            display_progress = min(current_progress, 100.0)

            # 构建进度信息（移除价格信息）
            progress_message = f"""
==========
{lang['current_progress'].format(progress=display_progress, processed=display_processed, total=total_hint)}
{lang['threads_used'].format(count=data.active_threads)}
-----
{lang['time_estimation']}
{lang['avg_time_per_paper'].format(time=actual_time_per_paper, threads=data.active_threads)}
{lang['elapsed_time'].format(hours=hours_elapsed, minutes=minutes_elapsed, seconds=seconds_elapsed)}
{lang['remaining_time'].format(hours=hours_remaining, minutes=minutes_remaining, seconds=seconds_remaining)}
{lang['completion_time'].format(time=formatted_completion_time)}
-----
{lang['token_usage']}
{lang['avg_tokens'].format(input=int(avg_prompt_tokens), output=int(avg_completion_tokens))}
{lang['total_tokens'].format(count=current_total_tokens)}
{lang['estimated_total_tokens'].format(count=int(estimated_total_tokens))}
++++++++++++++++++++
"""
            print_and_log(progress_message)
        except Exception as e:
            # 避免监控线程因异常退出，仅记录摘要信息
            try:
                print_and_log(f"[progress] monitor exception: {e}")
            except Exception:
                pass

def reset_progress_tracking(uid: int = None, query_index: int = None, total: int = 0):
    """重置（或初始化）某个查询的隔离进度桶 + 全局token统计归零（仅在新查询启动时调用）。"""
    # 初始化桶
    if uid is not None and query_index is not None:
        data.init_progress_bucket(uid, query_index, total)
        data.current_uid = uid
        data.current_query_index = query_index
    # 记录查询起始时间用于最终统计（进度显示优先 DB start_time）
    try:
        data.start_time = time.time()
    except Exception:
        pass
    # 重置全局 token 累计（跨查询不共享）
    data.token_used = 0
    data.prompt_tokens_used = 0
    data.completion_tokens_used = 0
    data.prompt_cache_hit_tokens_used = 0
    data.prompt_cache_miss_tokens_used = 0

def update_progress(single_elapsed_time, uid: int, query_index: int):
    """按会话隔离更新进度（仅正常完成的任务调用）。"""
    try:
        data.bump_progress(uid, query_index, single_elapsed_time)
    except Exception:
        pass
