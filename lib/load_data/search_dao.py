"""
搜索和查询数据访问对象
处理 search_* 表和 query_log 表的操作
"""

from typing import Optional, List
from datetime import datetime
from .db_base import _get_connection, _get_thread_connection, utc_now_str


def insert_searching_log(query_time: str, selected_folders: str, year_range: str,
                         research_question: str, requirements: str, query_table: str,
                         uid: int = 1, total_papers_count: int = 0,
                         is_distillation: bool = False, is_visible: bool = True,
                         should_pause: bool = False, total_cost: float = 0.0):
    """新增一条检索日志"""
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            utc_now = utc_now_str()
            sql = """
                INSERT INTO query_log
                (`query_index`, uid, query_time, selected_folders, year_range,
                 research_question, requirements, query_table, start_time, end_time,
                 total_papers_count, is_distillation, is_visible, should_pause, total_cost)
                VALUES (NULL, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                uid, utc_now, selected_folders, year_range, research_question,
                requirements, query_table, utc_now, total_papers_count,
                is_distillation, is_visible, should_pause, total_cost
            ))
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()


def mark_searching_log_completed(log_index: int):
    """标记检索完成"""
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            end_utc = utc_now_str()
            cursor.execute(
                "UPDATE query_log SET end_time=%s WHERE `query_index`=%s AND end_time IS NULL",
                (end_utc, log_index)
            )
        conn.commit()
    finally:
        conn.close()


def create_search_table(table_name: str):
    """创建或确保搜索表存在"""
    if not table_name:
        return
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    search_id INT AUTO_INCREMENT PRIMARY KEY,
                    uid INT NOT NULL DEFAULT 1,
                    query_index INT NOT NULL,
                    doi VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                    insert_time DATETIME(2) NOT NULL,
                    search_time DATETIME(2) NULL,
                    result_time DATETIME(2) NULL,
                    run_time DECIMAL(10,3) NULL COMMENT '运行时间(秒)',
                    prompt_tokens INT NULL,
                    completion_tokens INT NULL,
                    total_tokens INT NULL,
                    cache_hit_tokens INT NULL,
                    cache_miss_tokens INT NULL,
                    search_result TINYINT(1) NULL,
                    reason TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
                    price DECIMAL(10,1) NOT NULL DEFAULT 1.0 COMMENT '检索点价格',
                    INDEX idx_uid (uid),
                    INDEX idx_query_index (query_index),
                    INDEX idx_doi (doi),
                    INDEX idx_search_result (search_result)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            """)
        conn.commit()
    finally:
        conn.close()


def check_search_table_exists(table_name: str) -> bool:
    """检查搜索表是否存在"""
    if not table_name:
        return False
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s",
                (table_name,)
            )
            (count,) = cursor.fetchone()
            return int(count) > 0
    finally:
        conn.close()


def get_search_table_name() -> str:
    """获取当前日期的搜索表名"""
    today = datetime.now().strftime("%Y%m%d")
    return f"search_{today}"


def insert_search_doi(table_name: str, doi: str, uid: int = 1,
                      query_index: int = None, price: float = 1.0) -> Optional[int]:
    """插入单条 DOI，成功返回 search_id"""
    if not table_name or not doi or query_index is None:
        return None
    conn = _get_thread_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO `{table_name}` (uid, query_index, doi, insert_time, price)
                    VALUES (%s, %s, %s, NOW(2), %s)""",
                (uid, query_index, doi, float(price))
            )
            search_id = cursor.lastrowid
        try:
            conn.commit()
        except Exception:
            pass
        return int(search_id)
    except Exception as e:
        print(f"插入DOI到搜索表失败: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        pass


def insert_search_doi_bulk(table_name: str, rows: list, batch_size: int = 1000) -> int:
    """批量插入 DOI 到搜索表"""
    if not table_name or not rows:
        return 0

    values = []
    for r in rows:
        try:
            if isinstance(r, dict):
                uid = int(r.get('uid', 1))
                qidx = int(r.get('query_index'))
                doi = str(r.get('doi'))
                price = float(r.get('price', 1.0))
            else:
                uid = int(r[0]); qidx = int(r[1]); doi = str(r[2]); price = float(r[3])
            if not doi or qidx <= 0:
                continue
            values.append((uid, qidx, doi, price))
        except Exception:
            continue

    if not values:
        return 0

    sql = f"""INSERT INTO `{table_name}`
              (uid, query_index, doi, insert_time, price)
              VALUES (%s, %s, %s, NOW(2), %s)"""

    conn = _get_thread_connection()
    inserted = 0
    prev_autocommit = getattr(conn, "autocommit", True)

    try:
        try:
            conn.autocommit = False
        except Exception:
            pass

        with conn.cursor() as cursor:
            for i in range(0, len(values), int(batch_size or 1000)):
                chunk = values[i:i + int(batch_size or 1000)]
                try:
                    cursor.executemany(sql, chunk)
                    conn.commit(); inserted += len(chunk)
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    for v in chunk:
                        try:
                            cursor.execute(sql, v); inserted += 1
                        except Exception:
                            pass
                    try:
                        conn.commit()
                    except Exception:
                        pass
    finally:
        try:
            conn.autocommit = prev_autocommit
        except Exception:
            pass

    return inserted


def get_search_id_by_doi(table_name: str, query_index: int, doi: str) -> Optional[int]:
    """根据 (query_index, doi) 查询对应的 search_id；找不到返回 None"""
    if not table_name or not doi or not query_index:
        return None
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT search_id FROM `{table_name}` WHERE query_index=%s AND doi=%s LIMIT 1",
                (int(query_index), str(doi))
            )
            row = cursor.fetchone()
            if not row:
                return None
            try:
                return int(row[0])
            except Exception:
                return None
    finally:
        conn.close()


def update_search_result(table_name: str, search_id: int, search_result: bool, reason: str,
                         prompt_tokens: int, completion_tokens: int, total_tokens: int,
                         cache_hit_tokens: int, cache_miss_tokens: int):
    """更新搜索结果，并扣费/累积 actual_cost"""
    if not table_name or not search_id:
        return

    conn = _get_thread_connection()
    query_index = None  # 在外部作用域声明
    try:
        with conn.cursor() as cursor:
            # 获取任务信息
            cursor.execute(
                f"SELECT uid, price, query_index FROM `{table_name}` WHERE search_id=%s",
                (search_id,)
            )
            task_info = cursor.fetchone()

            # 规范化任务信息
            uid_val = 0
            price_val = 0.0
            if task_info:
                try:
                    uid_val = int(task_info[0] or 0)
                except Exception:
                    uid_val = 0
                try:
                    price_val = float(task_info[1] or 0.0)
                except Exception:
                    price_val = 0.0
                try:
                    query_index = int(task_info[2] or 0)
                except Exception:
                    query_index = 0

            # 更新搜索结果
            cursor.execute(
                f"""UPDATE `{table_name}` SET
                       result_time=NOW(2), search_result=%s, reason=%s,
                       prompt_tokens=%s, completion_tokens=%s, total_tokens=%s,
                       cache_hit_tokens=%s, cache_miss_tokens=%s,
                       run_time=TIMESTAMPDIFF(MICROSECOND, search_time, NOW(2))/1000000
                   WHERE search_id=%s""",
                (
                    1 if search_result else 0,
                    reason or "",
                    int(prompt_tokens or 0),
                    int(completion_tokens or 0),
                    int(total_tokens or 0),
                    int(cache_hit_tokens or 0),
                    int(cache_miss_tokens or 0),
                    int(search_id),
                ),
            )

            # 扣费与实际成本累积
            if uid_val > 0 and price_val > 0:
                cursor.execute(
                    "UPDATE user_info SET balance = balance - %s WHERE uid = %s AND balance >= %s",
                    (price_val, uid_val, price_val),
                )
                if cursor.rowcount == 0:
                    print(f"警告: 用户 {uid_val} 余额不足")
                elif query_index and query_index > 0:
                    try:
                        cursor.execute(
                            "UPDATE query_log SET actual_cost = COALESCE(actual_cost,0) + %s WHERE query_index = %s",
                            (price_val, int(query_index)),
                        )
                    except Exception as e:
                        print(f"更新 actual_cost 失败: {e}")

        try:
            conn.commit()
        except Exception:
            pass

        # 检查该查询是否全部完成
        if query_index is not None and int(query_index) > 0:
            try:
                # 统计总任务与完成任务
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT COUNT(*) AS total,
                               SUM(CASE WHEN result_time IS NOT NULL THEN 1 ELSE 0 END) AS finished
                        FROM `{table_name}`
                        WHERE query_index=%s
                        """,
                        (int(query_index),),
                    )
                    row = cursor.fetchone()
                    total = int(row[0] or 0) if row else 0
                    finished = int(row[1] or 0) if row else 0

                    if total > 0 and finished >= total:
                        # 标记 query_log 完成时间
                        cursor.execute(
                            "UPDATE query_log SET end_time=%s WHERE query_index=%s AND end_time IS NULL",
                            (utc_now_str(), int(query_index)),
                        )
                try:
                    conn.commit()
                except Exception:
                    pass
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"检查查询完成状态失败: {e}")

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"更新搜索结果失败: {e}")


# =============================
# 补全缺失的对外访问函数（被其他模块引用）
# =============================

def fetch_search_results_with_paperinfo(table_name: str, query_index: int) -> list:
    """按 query_index 获取搜索结果并附带 PaperInfo 信息。
    返回字段：source(Name), year, title, doi, bib, paper_url, search_result, reason
    若某字段缺失使用合理兜底，避免前端 KeyError。
    """
    if not table_name or not query_index or query_index <= 0:
        return []

    conn = _get_connection()
    rows = []
    try:
        with conn.cursor(dictionary=True) as cursor:
            try:
                cursor.execute(
                    f"""
                    SELECT s.search_id, s.uid, s.query_index, s.doi,
                           s.search_result, s.reason,
                           p.Name AS source, p.Year AS year, p.Title AS title,
                           p.Abstract AS abstract, p.DOI AS paper_doi
                    FROM `{table_name}` AS s
                    LEFT JOIN PaperInfo AS p ON s.doi = p.DOI
                    WHERE s.query_index=%s
                    ORDER BY s.search_id ASC
                    """,
                    (int(query_index),)
                )
            except Exception as e:
                print(f"fetch_search_results_with_paperinfo 查询失败: {e}")
                return []

            for r in cursor.fetchall() or []:
                doi = r.get('doi') or r.get('paper_doi') or ''
                title = r.get('title') or '标题缺失'
                year = r.get('year')
                source = r.get('source') or ''
                abstract = r.get('abstract') or ''
                # 构造最小 bib（若后端未写入 bib 字段，可用此合成）
                bib_key = f"auto_{source}_{year}_{abs(hash(title)) % (10**8)}"
                bib_lines = [f"@article{{{bib_key},"]
                bib_lines.append(f"  title={{ {title} }},")
                if year is not None:
                    bib_lines.append(f"  year={{ {year} }},")
                if doi:
                    bib_lines.append(f"  doi={{ {doi} }},")
                if abstract:
                    bib_lines.append(f"  abstract={{ {abstract[:500]} }}")  # 截断避免过长
                bib_lines.append("}")
                bib = "\n".join(bib_lines)

                paper_url = ''
                if doi:
                    paper_url = f"https://doi.org/{doi}" if not str(doi).lower().startswith('http') else doi

                rows.append({
                    'search_id': r.get('search_id'),
                    'uid': r.get('uid'),
                    'query_index': r.get('query_index'),
                    'doi': doi,
                    'source': source,
                    'year': year,
                    'title': title,
                    'bib': bib,
                    'paper_url': paper_url,
                    'search_result': r.get('search_result'),
                    'reason': r.get('reason') or '',
                })
    finally:
        conn.close()
    return rows


def get_relevant_dois_from_query(query_index: int) -> list:
    """获取指定 query_index 下判定为相关(search_result=1)的 DOI 列表。
    通过 query_log 查询对应的 query_table，再读取该表。"""
    if not query_index or query_index <= 0:
        return []
    conn = _get_connection()
    table_name = None
    try:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    "SELECT query_table FROM query_log WHERE query_index=%s LIMIT 1",
                    (int(query_index),)
                )
                row = cursor.fetchone()
                if row:
                    table_name = row[0]
            except Exception as e:
                print(f"get_relevant_dois_from_query 获取表名失败: {e}")
                return []
    finally:
        conn.close()

    if not table_name:
        return []

    # 读取相关 DOI
    conn2 = _get_connection()
    dois = []
    try:
        with conn2.cursor() as cursor:
            try:
                cursor.execute(
                    f"SELECT doi FROM `{table_name}` WHERE query_index=%s AND search_result=1",
                    (int(query_index),)
                )
                for (doi,) in cursor.fetchall() or []:
                    if doi and isinstance(doi, str):
                        dois.append(doi)
            except Exception as e:
                print(f"get_relevant_dois_from_query 查询 DOI 失败: {e}")
                return []
    finally:
        conn2.close()
    return dois


def reset_task_to_unprocessed(table_name: str, search_id: int) -> bool:
    """将指定 search_id 的任务还原为未处理状态（用于超时/会话不一致重试）。"""
    if not table_name or not search_id:
        return False
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE `{table_name}` SET
                    search_time=NULL,
                    result_time=NULL,
                    search_result=NULL,
                    reason=NULL,
                    run_time=NULL,
                    prompt_tokens=NULL,
                    completion_tokens=NULL,
                    total_tokens=NULL,
                    cache_hit_tokens=NULL,
                    cache_miss_tokens=NULL
                WHERE search_id=%s
                """,
                (int(search_id),)
            )
        conn.commit()
        return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"reset_task_to_unprocessed 失败: {e}")
        return False
    finally:
        conn.close()
