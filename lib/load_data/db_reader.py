"""
数据库读取器主模块 (新架构)
整合所有数据访问功能

新架构变更:
- 移除了 task_dao, app_settings_dao, queue_dao (已废弃)
- 移除了 redis_aggregates (已废弃)
- 简化导入，只暴露实际存在的函数
"""

# ============================================================
# 基础功能
# ============================================================
from .db_base import (
    _get_connection,
    _get_thread_connection,
    close_thread_connection,
    _table_exists,
    utc_now_str,
    _parse_utc_prefixed,
    _schema_managed_externally
)

# ============================================================
# 论文相关功能
# ============================================================
from .paper_dao import (
    get_paper_by_doi,
    get_papers_by_block,
    get_block_dois,
    get_paper_title_abstract_by_doi,
    fetch_papers_by_dois,
    count_papers_by_journals,
    paper_exists,
    get_total_paper_count
)

# ============================================================
# 搜索结果相关功能
# ============================================================
from .search_dao import (
    save_result,
    get_result,
    get_all_results,
    get_relevant_dois,
    get_result_count,
    archive_results_to_mysql,
    fetch_results_with_paperinfo,
    delete_results,
    result_exists
)

# ============================================================
# 查询任务相关功能
# ============================================================
from .query_dao import (
    generate_query_id,
    create_query_log,
    get_query_log,
    get_query_logs_by_uid,
    update_query_status,
    update_query_cost,
    mark_query_completed,
    get_active_queries,
    get_query_progress,
    pause_query,
    resume_query
)

# ============================================================
# 用户管理相关功能
# ============================================================
from .user_dao import (
    get_user_by_uid,
    get_user_by_username,
    get_all_users,
    get_balance,
    get_permission,
    update_user_balance,
    deduct_balance_redis,
    update_user_permission,
    create_user,
    invalidate_user_cache,
    sync_balance_to_mysql,
    get_billing_records_by_uid
)

# ============================================================
# 标签和期刊相关功能
# ============================================================
from .journal_dao import (
    get_all_tags,
    get_tags_by_type,
    get_tags_by_type_filtered,
    get_journals_by_tag,
    get_journals_by_filters,
    get_journal_price,
    get_journal_prices,
    get_year_number,
    count_papers_by_filters
    # get_prices_by_dois 已废弃，被 query_api._calculate_distill_cost 替代
)

# ============================================================
# 管理员相关功能
# ============================================================
from .admin_dao import (
    get_admin_by_username,
    get_admin_by_uid,
    create_admin,
    update_admin_password,
    update_admin_role,
    delete_admin,
    admin_exists,
    count_admins,
    get_all_admins
)


# ============================================================
# 注意：此模块不再包含兼容性函数
# 系统配置请使用 lib.redis.system_cache.SystemCache
# API使用量请使用 lib.redis.sliding_window.SlidingWindow
# ============================================================
