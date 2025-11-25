"""
论文数据访问对象
处理PaperInfo和ContentList表的操作
"""

from typing import List, Dict
from .db_base import _get_connection


def get_subfolders() -> List[str]:
    """从数据库 ContentList 读取所有 Name"""
    names: List[str] = []
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT Name FROM ContentList ORDER BY Name ASC")
            for (name,) in cursor.fetchall():
                if name and isinstance(name, str):
                    names.append(name)
    finally:
        conn.close()
    return names


def count_papers_by_folder(name: str, include_all_years: bool, 
                          start_year: int, end_year: int) -> int:
    """统计指定 Name 的论文数量"""
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            if include_all_years:
                sql = "SELECT COUNT(*) FROM PaperInfo WHERE Name = %s"
                params = (name,)
            else:
                sql = "SELECT COUNT(*) FROM PaperInfo WHERE Name = %s AND Year BETWEEN %s AND %s"
                params = (name, start_year, end_year)
            cursor.execute(sql, params)
            (cnt,) = cursor.fetchone()
            return int(cnt or 0)
    finally:
        conn.close()


def count_papers(selected_folders: List[str], include_all_years: bool, 
                start_year: int, end_year: int) -> int:
    """统计指定 Name 列表下的论文总数"""
    if not selected_folders:
        return 0

    placeholders = ", ".join(["%s"] * len(selected_folders))
    where_clauses = [f"Name IN ({placeholders})"]
    params: List = list(selected_folders)

    if not include_all_years:
        where_clauses.append("Year BETWEEN %s AND %s")
        params.extend([start_year, end_year])

    where_sql = " AND ".join(where_clauses)
    sql = f"SELECT COUNT(*) FROM PaperInfo WHERE {where_sql}"

    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            (cnt,) = cursor.fetchone()
            return int(cnt or 0)
    finally:
        conn.close()


def fetch_papers(selected_folders: List[str], include_all_years: bool, 
                start_year: int, end_year: int) -> List[Dict]:
    """一次性从 PaperInfo 取回指定 Name 列表的数据"""
    if not selected_folders:
        return []

    placeholders = ", ".join(["%s"] * len(selected_folders))
    where_clauses = [f"Name IN ({placeholders})"]
    params: List = list(selected_folders)

    if not include_all_years:
        where_clauses.append("Year BETWEEN %s AND %s")
        params.extend([start_year, end_year])

    where_sql = " AND ".join(where_clauses)
    sql = f"""
        SELECT Name, Year, Title, Author, DOI, Abstract
        FROM PaperInfo
        WHERE {where_sql}
        ORDER BY Name ASC, Year ASC, Title ASC
    """

    rows: List[Dict] = []
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, params)
            for r in cursor.fetchall():
                name = r.get("Name") or ""
                year = r.get("Year")
                title = r.get("Title") or "标题未知"
                author = r.get("Author") or ""
                doi = r.get("DOI") or ""
                abstract = r.get("Abstract") or "摘要未知"

                # 构造最小 bib entry
                key = f"auto_{name}_{year}_{abs(hash(title)) % (10**8)}"
                entry_lines = [f"@article{{{key},"]
                entry_lines.append(f"  title={{ {title} }},")
                if author:
                    entry_lines.append(f"  author={{ {author} }},")
                if year is not None:
                    entry_lines.append(f"  year={{ {year} }},")
                if doi:
                    entry_lines.append(f"  doi={{ {doi} }},")
                if abstract:
                    entry_lines.append(f"  abstract={{ {abstract} }},")
                entry_lines.append("}")
                entry = "\n".join(entry_lines)

                rows.append({
                    "title": title,
                    "abstract": abstract,
                    "entry": entry,
                    "source_folder": name,
                    "source_file": "",
                    "name": name,
                    "year": year,
                    "doi": doi,
                })
    finally:
        conn.close()
    return rows


def fetch_papers_iter(selected_folders: List[str], include_all_years: bool, 
                     start_year: int, end_year: int, batch_size: int = 500):
    """流式从 PaperInfo 取回数据"""
    if not selected_folders:
        return  # 这会返回None，不是生成器！

    placeholders = ", ".join(["%s"] * len(selected_folders))
    where_clauses = [f"Name IN ({placeholders})"]
    params: List = list(selected_folders)

    if not include_all_years:
        where_clauses.append("Year BETWEEN %s AND %s")
        params.extend([start_year, end_year])

    where_sql = " AND ".join(where_clauses)
    sql = f"""
        SELECT Name, Year, Title, Author, DOI, Abstract
        FROM PaperInfo
        WHERE {where_sql}
        ORDER BY Name ASC, Year ASC, Title ASC
    """

    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, params)
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                for r in rows:
                    name = r.get("Name") or ""
                    year = r.get("Year")
                    title = r.get("Title") or "标题未知"
                    author = r.get("Author") or ""
                    doi = r.get("DOI") or ""
                    abstract = r.get("Abstract") or "摘要未知"

                    key = f"auto_{name}_{year}_{abs(hash(title)) % (10**8)}"
                    entry_lines = [f"@article{{{key},"]
                    entry_lines.append(f"  title={{ {title} }},")
                    if author:
                        entry_lines.append(f"  author={{ {author} }},")
                    if year is not None:
                        entry_lines.append(f"  year={{ {year} }},")
                    if doi:
                        entry_lines.append(f"  doi={{ {doi} }},")
                    if abstract:
                        entry_lines.append(f"  abstract={{ {abstract} }},")
                    entry_lines.append("}")
                    entry = "\n".join(entry_lines)

                    yield {
                        "title": title,
                        "abstract": abstract,
                        "entry": entry,
                        "source_folder": name,
                        "source_file": "",
                        "name": name,
                        "year": year,
                        "doi": doi,
                    }
    finally:
        conn.close()


def get_paper_title_abstract_by_doi(doi: str):
    """通过 DOI 从 PaperInfo 获取 Title/Abstract"""
    if not doi:
        return None
    from .db_base import _get_thread_connection
    conn = _get_thread_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT Title AS title, Abstract AS abstract
                FROM PaperInfo
                WHERE DOI=%s
            """, (doi,))
            return cursor.fetchone()
    finally:
        pass  # 不关闭线程连接


def fetch_papers_by_dois(doi_list: List[str]) -> List[Dict]:
    """根据DOI列表从PaperInfo表获取论文详细信息"""
    if not doi_list:
        return []
    
    valid_dois = [doi for doi in doi_list if doi and doi.strip()]
    if not valid_dois:
        return []
    
    placeholders = ", ".join(["%s"] * len(valid_dois))
    sql = f"""
        SELECT Name, Year, Title, Author, DOI, Abstract
        FROM PaperInfo
        WHERE DOI IN ({placeholders})
        ORDER BY Year ASC, Title ASC
    """
    
    rows: List[Dict] = []
    conn = _get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, valid_dois)
            for r in cursor.fetchall():
                name = r.get("Name") or ""
                year = r.get("Year")
                title = r.get("Title") or "标题未知"
                author = r.get("Author") or ""
                doi = r.get("DOI") or ""
                abstract = r.get("Abstract") or "摘要未知"

                entry = f"""@article{{{doi.replace('/', '_').replace('.', '_')},
    title={{{title}}},
    author={{{author}}},
    year={{{year}}},
    doi={{{doi}}}
}}"""

                rows.append({
                    "title": title,
                    "abstract": abstract,
                    "entry": entry,
                    "source_folder": name,
                    "source_file": f"{name}.bib",
                    "doi": doi
                })
    finally:
        conn.close()
    
    return rows


def count_papers_by_dois(doi_list: List[str]) -> int:
    """根据DOI列表统计PaperInfo表中对应的论文数量"""
    if not doi_list:
        return 0
    
    valid_dois = [doi for doi in doi_list if doi and doi.strip()]
    if not valid_dois:
        return 0
    
    placeholders = ", ".join(["%s"] * len(valid_dois))
    sql = f"SELECT COUNT(*) FROM PaperInfo WHERE DOI IN ({placeholders})"
    
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, valid_dois)
            (count,) = cursor.fetchone() or (0,)
            return int(count or 0)
    finally:
        conn.close()


def get_random_sentences(count: int = 10):
    """从sentence表中随机获取指定数量的句子"""
    if count <= 0:
        count = 10
    if count > 100:
        count = 100
        
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sentence 
                FROM sentence 
                ORDER BY RAND() 
                LIMIT %s
            """, (count,))
            results = cursor.fetchall()
            return [row[0] for row in results] if results else []
    except Exception as e:
        print(f"获取随机句子失败: {e}")
        return []
    finally:
        conn.close()
