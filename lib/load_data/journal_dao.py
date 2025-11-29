"""
期刊和标签管理数据访问对象 (新架构)
优先从 Redis 读取数据，提供高性能的标签和期刊查询

新架构数据流:
- 标签数据: sys:tags:info (Hash), sys:tag_journals:{Tag} (Set)
- 期刊数据: sys:journals:info (Hash), sys:journals:price (Hash)
- 年份统计: sys:year_number:{Name} (String/JSON)
"""

from typing import List, Dict, Set, Optional
from .db_base import _get_connection
from ..redis.system_cache import SystemCache
from ..redis.connection import redis_ping


def get_all_tags() -> Dict[str, str]:
    """
    获取所有标签及其类型
    
    Returns:
        {tag_name: tag_type} 字典
    """
    # 优先从 Redis 读取
    if redis_ping():
        cached = SystemCache.get_all_tags()
        if cached:
            return cached
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT Tag, TagType FROM info_tag")
        result = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        
        # 写入 Redis
        if redis_ping() and result:
            SystemCache.set_tags(result)
        
        return result
    finally:
        conn.close()


def get_tags_by_type(tag_type: str) -> List[str]:
    """根据标签类型获取所有标签"""
    all_tags = get_all_tags()
    return [tag for tag, ttype in all_tags.items() if ttype == tag_type]


def get_tags_by_type_filtered(tag_type: str, selected_tags: Dict) -> List[str]:
    """
    在已选标签约束下返回该类型的标签集合
    
    Args:
        tag_type: 要获取的标签类型
        selected_tags: 已选中的标签 {type: [tags]}
    """
    if not isinstance(selected_tags, dict) or not selected_tags:
        return get_tags_by_type(tag_type)
    
    # 使用 Redis 集合交集实现过滤
    if redis_ping():
        # 1. 获取所有约束条件下的期刊交集
        constrained_journals = None
        
        for flt_type, tags in selected_tags.items():
            if flt_type == tag_type or not tags:
                continue
            
            # 获取这些标签对应的期刊
            for tag in tags:
                tag_journals = SystemCache.get_journals_by_tag(tag)
                if constrained_journals is None:
                    constrained_journals = tag_journals
                else:
                    constrained_journals = constrained_journals & tag_journals
        
        # 2. 获取目标类型的所有标签
        all_tags = get_all_tags()
        target_tags = [tag for tag, ttype in all_tags.items() if ttype == tag_type]
        
        if constrained_journals is None:
            return target_tags
        
        # 3. 过滤出与约束期刊有交集的标签
        result = []
        for tag in target_tags:
            tag_journals = SystemCache.get_journals_by_tag(tag)
            if tag_journals & constrained_journals:
                result.append(tag)
        
        return result
    
    # 回退到 MySQL 查询
    return _get_tags_by_type_filtered_mysql(tag_type, selected_tags)


def _get_tags_by_type_filtered_mysql(tag_type: str, selected_tags: Dict) -> List[str]:
    """MySQL 实现的标签过滤"""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        base_sql = (
            "SELECT DISTINCT pt.Tag "
            "FROM info_paper_with_tag pt "
            "JOIN info_tag t ON pt.Tag = t.tag "
            "WHERE t.tagtype = %s "
        )
        params = [tag_type]
        where_clauses = []

        for flt_type, tags in (selected_tags or {}).items():
            if flt_type == tag_type or not tags:
                continue
            placeholders = ", ".join(["%s"] * len(tags))
            where_clauses.append(
                f"""pt.Name IN (
                    SELECT DISTINCT pt2.Name
                    FROM info_paper_with_tag pt2
                    JOIN info_tag t2 ON pt2.Tag = t2.tag
                    WHERE t2.tagtype = %s AND pt2.Tag IN ({placeholders})
                )"""
            )
            params.append(flt_type)
            params.extend(tags)

        if where_clauses:
            base_sql += " AND " + " AND ".join(where_clauses)
        base_sql += " ORDER BY pt.Tag"

        cursor.execute(base_sql, params)
        result = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return result
    finally:
        conn.close()


def get_journals_by_tag(tag: str) -> Set[str]:
    """获取指定标签下的所有期刊"""
    if redis_ping():
        cached = SystemCache.get_journals_by_tag(tag)
        if cached:
            return cached
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT Name FROM info_paper_with_tag WHERE Tag = %s",
            (tag,)
        )
        result = {row[0] for row in cursor.fetchall()}
        cursor.close()
        
        # 写入 Redis
        if redis_ping() and result:
            SystemCache.set_tag_journals(tag, result)
        
        return result
    finally:
        conn.close()


def get_journals_by_filters(time_range: Dict = None, 
                            selected_tags: Dict = None) -> List[Dict]:
    """
    根据筛选条件获取期刊/会议信息
    
    Returns:
        [{name, full_name, data_range, update_date}, ...]
    """
    # 优先使用 Redis
    if redis_ping():
        all_journals = SystemCache.get_all_journals()
        
        if all_journals:
            # 获取满足标签条件的期刊
            if selected_tags:
                filtered_names = None
                for tag_type, tags in selected_tags.items():
                    if not tags:
                        continue
                    for tag in tags:
                        tag_journals = SystemCache.get_journals_by_tag(tag)
                        if filtered_names is None:
                            filtered_names = tag_journals
                        else:
                            filtered_names = filtered_names & tag_journals
                
                if filtered_names is not None:
                    all_journals = {k: v for k, v in all_journals.items() 
                                    if k in filtered_names}
            
            # 时间范围过滤
            if time_range and not time_range.get("include_all", True):
                start_year = time_range.get("start_year")
                end_year = time_range.get("end_year")
                if start_year and end_year:
                    filtered = {}
                    for name, info in all_journals.items():
                        data_range = info.get('DataRange', '')
                        if _check_year_range(data_range, start_year, end_year):
                            filtered[name] = info
                    all_journals = filtered
            
            return [
                {
                    "name": name,
                    "full_name": info.get('FullName', ''),
                    "data_range": info.get('DataRange', ''),
                    "update_date": info.get('UpdateDate', ''),
                }
                for name, info in sorted(all_journals.items())
            ]
    
    # 回退到 MySQL
    return _get_journals_by_filters_mysql(time_range, selected_tags)


def _check_year_range(data_range: str, start_year: int, end_year: int) -> bool:
    """检查期刊的数据范围是否与指定年份范围有交集"""
    try:
        if '-' in data_range:
            parts = data_range.split('-')
            dr_start = int(parts[0].strip())
            dr_end = int(parts[-1].strip())
            return dr_start <= end_year and dr_end >= start_year
    except Exception:
        pass
    return True


def _get_journals_by_filters_mysql(time_range: Dict, selected_tags: Dict) -> List[Dict]:
    """MySQL 实现的期刊过滤"""
    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        base_sql = """
            SELECT DISTINCT c.Name, c.FullName, c.DataRange, c.UpdateDate
            FROM ContentList c
        """
        
        where_clauses = []
        params = []
        
        if selected_tags:
            for tag_type, tags in selected_tags.items():
                if tags:
                    placeholders = ", ".join(["%s"] * len(tags))
                    where_clauses.append(f"""
                        c.Name IN (
                            SELECT DISTINCT pt.Name 
                            FROM info_paper_with_tag pt 
                            JOIN info_tag t ON pt.Tag = t.tag 
                            WHERE t.tagtype = %s AND pt.Tag IN ({placeholders})
                        )
                    """)
                    params.append(tag_type)
                    params.extend(tags)
        
        if time_range and not time_range.get("include_all", True):
            start_year = time_range.get("start_year")
            end_year = time_range.get("end_year")
            if start_year and end_year:
                where_clauses.append("""
                    (c.DataRange REGEXP '[0-9]{4}-[0-9]{4}' AND 
                     CAST(SUBSTRING_INDEX(c.DataRange, '-', 1) AS UNSIGNED) <= %s AND
                     CAST(SUBSTRING_INDEX(c.DataRange, '-', -1) AS UNSIGNED) >= %s)
                """)
                params.extend([end_year, start_year])
        
        if where_clauses:
            sql = base_sql + " WHERE " + " AND ".join(where_clauses)
        else:
            sql = base_sql
        
        sql += " ORDER BY c.Name"
        
        cursor.execute(sql, params)
        results = cursor.fetchall()
        cursor.close()
        
        return [{
            "name": row["Name"] or "",
            "full_name": row["FullName"] or "",
            "data_range": row["DataRange"] or "",
            "update_date": row["UpdateDate"] or ""
        } for row in results]
    finally:
        conn.close()


def get_journal_price(journal_name: str) -> int:
    """获取单个期刊的价格"""
    if redis_ping():
        cached = SystemCache.get_journal_price(journal_name)
        if cached is not None:
            return cached
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(Price, 1) FROM ContentList WHERE Name = %s",
            (journal_name,)
        )
        row = cursor.fetchone()
        cursor.close()
        return int(row[0]) if row else 1
    finally:
        conn.close()


def get_journal_prices(journal_names: List[str]) -> Dict[str, int]:
    """批量获取期刊价格"""
    if not journal_names:
        return {}
    
    if redis_ping():
        all_prices = SystemCache.get_all_prices()
        if all_prices:
            return {name: all_prices.get(name, 1) for name in journal_names}
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ", ".join(["%s"] * len(journal_names))
        cursor.execute(
            f"SELECT Name, COALESCE(Price, 1) FROM ContentList WHERE Name IN ({placeholders})",
            journal_names
        )
        result = dict(cursor.fetchall())
        cursor.close()
        return result
    finally:
        conn.close()


def get_year_number(journal_name: str) -> Optional[Dict[int, int]]:
    """
    获取期刊各年份的文献数量
    
    Returns:
        {year: count} 字典
    """
    if redis_ping():
        cached = SystemCache.get_year_number(journal_name)
        if cached is not None:
            return cached
    
    # 回源 MySQL
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT YearNumberJson FROM contentlist_year_number WHERE Name = %s",
            (journal_name,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if not row or not row[0]:
            return None
        
        import json
        try:
            data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            result = {int(k): int(v) for k, v in data.items()}
            
            # 写入 Redis
            if redis_ping():
                SystemCache.set_year_number(journal_name, result)
            
            return result
        except Exception:
            return None
    finally:
        conn.close()


def count_papers_by_filters(selected_names: List[str], 
                            time_range: Dict = None) -> int:
    """
    估算选中期刊和年份的文献总数
    
    新架构使用 contentlist_year_number 表进行快速估算
    """
    if not selected_names:
        return 0
    
    total = 0
    start_year = None
    end_year = None
    
    if time_range and not time_range.get("include_all", True):
        start_year = time_range.get("start_year")
        end_year = time_range.get("end_year")
    
    for name in selected_names:
        year_counts = get_year_number(name)
        if year_counts:
            if start_year and end_year:
                for year, count in year_counts.items():
                    if start_year <= year <= end_year:
                        total += count
            else:
                total += sum(year_counts.values())
    
    return total


# 注意：get_prices_by_dois 函数已废弃并删除
# 新架构使用 query_api.py 中的 _calculate_distill_cost 函数替代
# 该函数直接从 Redis 的 ResultCache 和 SystemCache 获取数据，无需查询 MySQL
