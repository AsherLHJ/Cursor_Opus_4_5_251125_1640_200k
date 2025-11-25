"""
数据库读取器主模块
整合所有数据访问功能
（Stage5 扩展）
- 对 insert_searching_log / finalize_query_if_done 提供包装：
    在查询生命周期节点维护 Redis 聚合键（active_uids、uid:perm、perm_sum_active）。
"""

# 导入基础功能
from .db_base import (
    _get_connection,
    _get_thread_connection,
    close_thread_connection,
    _table_exists,
    utc_now_str,
    _parse_utc_prefixed,
    _schema_managed_externally
)

# 导入论文相关功能
from .paper_dao import (
    get_subfolders,
    count_papers_by_folder,
    count_papers,
    fetch_papers,
    fetch_papers_iter,
    get_paper_title_abstract_by_doi,
    fetch_papers_by_dois,
    count_papers_by_dois,
    get_random_sentences
)

# 导入搜索相关功能
from .search_dao import (
    insert_searching_log,
    mark_searching_log_completed,
    create_search_table,
    check_search_table_exists,
    get_search_table_name,
    insert_search_doi,
    insert_search_doi_bulk,
    update_search_result,
    fetch_search_results_with_paperinfo,
    get_relevant_dois_from_query,
    reset_task_to_unprocessed,
    get_search_id_by_doi
)

# 导入查询相关功能
from .query_dao import (
    get_query_log_by_index,
    list_query_logs_by_uid,
    get_query_start_time,
    set_query_start_time_if_absent,
    hide_query_log,
    delete_query_log,
    update_query_pause_status,
    finalize_query_if_done,
    compute_query_progress,
    get_active_queries_info,
    list_active_query_tables
)

# 导入任务调度相关功能
from .task_dao import (
    count_pending_tasks_in_table,
    count_pending_tasks_across_active,
    count_pending_tasks_for_uid,
    list_uids_with_pending_tasks,
    sum_permissions_for_uids,
    count_available_api_keys,
    get_active_api_accounts,
    update_api_limits
)

# 导入应用设置相关功能
from .app_settings_dao import (
    ensure_app_settings_table,
    get_app_setting,
    set_app_setting,
    get_bool_app_setting,
    set_bool_app_setting,
    get_int_app_setting,
    ensure_default_bcrypt_rounds,
    get_registration_enabled_db,
    set_registration_enabled_db,
    ensure_default_registration_enabled,
    get_tokens_per_req,
    set_tokens_per_req,
    get_worker_req_per_min,
    ensure_default_worker_req_per_min
)

# 导入用户管理相关功能
from .user_dao import (
    get_all_users,
    update_user_balance,
    update_user_permission,
    get_user_by_uid,
    get_billing_records_by_uid
)

# 导入标签和期刊相关功能
from .journal_dao import (
    get_tags_by_type,
    get_tags_by_type_filtered,
    get_journals_by_filters,
    count_papers_by_filters,
    get_journal_prices,
    count_papers_by_journals,
    get_prices_by_dois,
    ensure_price_columns
)

# 导入队列相关功能
from .queue_dao import (
    enqueue_ready,
    enqueue_ready_bulk,
    push_back_ready,
    mark_done,
    mark_failed,
    backlog_size,
    user_backlog_size,
    upsert_api_usage_minute,
    get_api_usage_minute
)


# 已废弃：release_reserved_keys_if_no_pending（Stage3 移除按 Key 预留机制）

# ---- Stage5 需要的底层模块引用（避免递归覆盖） ----
from . import search_dao as _search_dao
from . import query_dao as _query_dao
from ..process import redis_aggregates as _agg

# 保留直接使用的工具函数

def compute_query_cost_progress(query_index: int) -> dict:
    """基于成本计算进度"""
    result = {'total_cost': 0.0, 'actual_cost': 0.0, 'progress': 0.0, 'completed': False}
    if not query_index or query_index <= 0:
        return result

    conn = _get_thread_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT total_cost, actual_cost, end_time FROM query_log WHERE query_index=%s",
                (query_index,)
            )
            row = cursor.fetchone()
            if not row:
                return result

            total_cost = float(row[0] or 0.0)
            actual_cost = float(row[1] or 0.0)
            end_time = row[2]

            progress = 0.0
            if total_cost > 0:
                progress = round(min(actual_cost, total_cost) * 100.0 / total_cost, 2)

            completed = (total_cost > 0 and actual_cost >= total_cost) or (end_time is not None)

            result['total_cost'] = total_cost
            result['actual_cost'] = actual_cost
            result['progress'] = progress
            result['completed'] = bool(completed)
            return result
    finally:
        pass


# =============================
# Stage5 包装：查询生命周期 Redis 聚合维护
# =============================

def insert_searching_log(query_time: str, selected_folders: str, year_range: str,
                         research_question: str, requirements: str, query_table: str,
                         uid: int = 1, total_papers_count: int = 0,
                         is_distillation: bool = False, is_visible: bool = True,
                         should_pause: bool = False, total_cost: float = 0.0):
    """包装原 insert_searching_log：成功后将 uid 计入 active_uids，并维护 perm_sum_active。"""
    qidx = _search_dao.insert_searching_log(
        query_time, selected_folders, year_range,
        research_question, requirements, query_table,
        uid, total_papers_count, is_distillation, is_visible, should_pause, total_cost
    )
    try:
        if uid and int(uid) > 0:
            info = get_user_by_uid(int(uid)) or {}
            perm = int(info.get('permission') or 0)
            _agg.add_or_update_active_uid(int(uid), int(perm))
    except Exception:
        pass
    return qidx


def finalize_query_if_done(table_name: str, query_index: int):
    """包装原 finalize_query_if_done：当查询真正结束时，从 active_uids 移除 uid 并回收 perm_sum_active。"""
    _query_dao.finalize_query_if_done(table_name, query_index)
    # 检查是否已完成（end_time 已写入）
    try:
        row = _query_dao.get_query_log_by_index(int(query_index)) or {}
        uid_val = int(row.get('uid') or 0)
        end_time_val = row.get('end_time')
        if uid_val > 0 and end_time_val is not None:
            # 仅当该 uid 已无其它活跃查询时再移除
            conn = _get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT COUNT(*) FROM query_log WHERE uid=%s AND end_time IS NULL",
                        (uid_val,)
                    )
                    (remain_cnt,) = cursor.fetchone() or (0,)
                    if int(remain_cnt or 0) <= 0:
                        _agg.remove_active_uid(uid_val)
            finally:
                conn.close()
    except Exception:
        pass