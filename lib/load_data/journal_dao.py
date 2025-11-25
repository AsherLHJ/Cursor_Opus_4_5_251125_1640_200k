"""
期刊和标签管理数据访问对象
处理ContentList、info_tag、info_paper_with_tag表相关操作
"""

from typing import List, Dict, Optional
from .db_base import _get_connection


def get_tags_by_type(tag_type: str) -> List[str]:
    """根据标签类型获取所有标签"""
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT pt.Tag "
                "FROM info_paper_with_tag pt "
                "JOIN info_tag t ON pt.Tag = t.tag "
                "WHERE t.tagtype = %s "
                "ORDER BY pt.Tag",
                (tag_type,)
            )
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_tags_by_type_filtered(tag_type: str, selected_tags: Dict) -> List[str]:
    """在已选标签约束下返回该类型的标签集合"""
    if not isinstance(selected_tags, dict) or not selected_tags:
        return get_tags_by_type(tag_type)

    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            base_sql = (
                "SELECT DISTINCT pt.Tag "
                "FROM info_paper_with_tag pt "
                "JOIN info_tag t ON pt.Tag = t.tag "
                "WHERE t.tagtype = %s "
            )
            params = [tag_type]
            where_clauses = []

            for flt_type, tags in (selected_tags or {}).items():
                if flt_type == tag_type:
                    continue
                if not tags:
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
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_journals_by_filters(time_range: Dict = None, selected_tags: Dict = None) -> List[Dict]:
    """根据筛选条件获取期刊/会议信息"""
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            base_sql = """
                SELECT DISTINCT c.Name, c.FullName, c.DataRange, c.UpdateDate
                FROM ContentList c
            """
            
            where_clauses = []
            params = []
            
            if selected_tags:
                tag_conditions = []
                for tag_type, tags in selected_tags.items():
                    if tags:
                        placeholders = ", ".join(["%s"] * len(tags))
                        tag_conditions.append(f"""
                            c.Name IN (
                                SELECT DISTINCT pt.Name 
                                FROM info_paper_with_tag pt 
                                JOIN info_tag t ON pt.Tag = t.tag 
                                WHERE t.tagtype = %s AND pt.Tag IN ({placeholders})
                            )
                        """)
                        params.append(tag_type)
                        params.extend(tags)
                
                if tag_conditions:
                    where_clauses.extend(tag_conditions)
            
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
            
            return [{
                "name": row["Name"] or "",
                "full_name": row["FullName"] or "",
                "data_range": row["DataRange"] or "",
                "update_date": row["UpdateDate"] or ""
            } for row in results]
    finally:
        conn.close()


def count_papers_by_filters(selected_names: List[str], time_range: Dict = None) -> int:
    """根据选中的期刊名称和时间范围统计论文数量"""
    if not selected_names:
        return 0
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(selected_names))
            where_clauses = [f"Name IN ({placeholders})"]
            params = list(selected_names)
            
            if time_range and not time_range.get("include_all", True):
                start_year = time_range.get("start_year")
                end_year = time_range.get("end_year")
                if start_year and end_year:
                    where_clauses.append("Year BETWEEN %s AND %s")
                    params.extend([start_year, end_year])
            
            where_sql = " AND ".join(where_clauses)
            sql = f"SELECT COUNT(*) FROM PaperInfo WHERE {where_sql}"
            
            cursor.execute(sql, params)
            (count,) = cursor.fetchone()
            return int(count or 0)
    finally:
        conn.close()


def get_journal_prices(journal_names: List[str]) -> Dict[str, int]:
    """批量获取期刊价格"""
    if not journal_names:
        return {}
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(journal_names))
            cursor.execute(
                f"SELECT Name, COALESCE(Price, 1) FROM ContentList WHERE Name IN ({placeholders})",
                journal_names
            )
            return dict(cursor.fetchall())
    finally:
        conn.close()


def count_papers_by_journals(journal_names: List[str], time_range: Dict = None) -> Dict[str, int]:
    """统计每个期刊的论文数量"""
    if not journal_names:
        return {}
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(journal_names))
            
            if time_range and not time_range.get("include_all", True):
                start_year = time_range.get("start_year")
                end_year = time_range.get("end_year")
                if start_year and end_year:
                    cursor.execute(
                        f"SELECT Name, COUNT(*) FROM PaperInfo WHERE Name IN ({placeholders}) "
                        f"AND Year BETWEEN %s AND %s GROUP BY Name",
                        journal_names + [start_year, end_year]
                    )
                else:
                    cursor.execute(
                        f"SELECT Name, COUNT(*) FROM PaperInfo WHERE Name IN ({placeholders}) GROUP BY Name",
                        journal_names
                    )
            else:
                cursor.execute(
                    f"SELECT Name, COUNT(*) FROM PaperInfo WHERE Name IN ({placeholders}) GROUP BY Name",
                    journal_names
                )
            
            return dict(cursor.fetchall())
    finally:
        conn.close()


def get_prices_by_dois(doi_list: List[str]) -> Dict[str, float]:
    """根据DOI列表返回价格映射"""
    if not doi_list:
        return {}
    
    valid_dois = [d for d in doi_list if d and str(d).strip()]
    if not valid_dois:
        return {}
    
    placeholders = ", ".join(["%s"] * len(valid_dois))
    sql = f"""
        SELECT p.DOI, COALESCE(c.Price, 1)
        FROM PaperInfo p
        LEFT JOIN ContentList c ON p.Name = c.Name
        WHERE p.DOI IN ({placeholders})
    """
    
    result: Dict[str, float] = {}
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, valid_dois)
            rows = cursor.fetchall() or []
            for row in rows:
                doi = row[0]
                try:
                    price_val = float(row[1]) if row[1] is not None else 1.0
                except Exception:
                    price_val = 1.0
                result[str(doi)] = price_val
            return result
    finally:
        conn.close()


def ensure_price_columns():
    """确保所有必要的价格相关列存在"""
    from ..price_calculate import PriceCalculator
    
    calculator = PriceCalculator()
    try:
        calculator.add_price_column_to_contentlist()
        calculator.add_cost_column_to_query_log()
        calculator.add_actual_cost_column_to_query_log()
    finally:
        calculator.close()
