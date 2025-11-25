"""
Redis初始化加载模块
在Redis容器启动后，从MySQL加载静态数据到Redis

功能:
1. 加载标签数据 (info_tag, info_paper_with_tag)
2. 加载期刊数据 (contentlist, contentlist_year_number)
3. 加载文献Block数据 (paperinfo)
"""

import json
import time
from typing import Dict, List, Optional, Callable
from collections import defaultdict

from .connection import get_redis_client, redis_ping
from .system_cache import SystemCache
from .paper_blocks import PaperBlocks


def load_tags_from_mysql(conn) -> bool:
    """
    从MySQL加载标签数据到Redis
    
    Args:
        conn: MySQL连接
    """
    cursor = None
    try:
        cursor = conn.cursor()
        
        # 1. 加载标签元数据 -> sys:tags:info
        cursor.execute("SELECT Tag, TagType FROM info_tag")
        tags = {row[0]: row[1] for row in cursor.fetchall()}
        
        if tags:
            SystemCache.set_tags(tags)
            print(f"[Redis Init] 加载 {len(tags)} 个标签到 sys:tags:info")
        
        # 2. 加载标签-期刊映射 -> sys:tag_journals:{Tag}
        cursor.execute("SELECT Name, Tag FROM info_paper_with_tag")
        tag_journals: Dict[str, set] = defaultdict(set)
        for name, tag in cursor.fetchall():
            tag_journals[tag].add(name)
        
        for tag, journals in tag_journals.items():
            SystemCache.set_tag_journals(tag, journals)
        
        print(f"[Redis Init] 加载 {len(tag_journals)} 个标签的期刊映射")
        return True
        
    except Exception as e:
        print(f"[Redis Init] 加载标签数据失败: {e}")
        return False
    finally:
        if cursor:
            cursor.close()


def load_journals_from_mysql(conn) -> bool:
    """
    从MySQL加载期刊数据到Redis
    
    Args:
        conn: MySQL连接
    """
    cursor = None
    try:
        cursor = conn.cursor()
        
        # 1. 加载期刊基础信息 -> sys:journals:info
        cursor.execute("""
            SELECT Name, FullName, DataRange, UpdateDate, Price 
            FROM contentlist
        """)
        
        journals = {}
        prices = {}
        
        for row in cursor.fetchall():
            name, full_name, data_range, update_date, price = row
            journals[name] = {
                'FullName': full_name or '',
                'DataRange': data_range or '',
                'UpdateDate': update_date or '',
            }
            prices[name] = int(price) if price else 1
        
        if journals:
            SystemCache.set_journals(journals)
            print(f"[Redis Init] 加载 {len(journals)} 个期刊到 sys:journals:info")
        
        # 2. 加载期刊价格 -> sys:journals:price
        if prices:
            SystemCache.set_prices(prices)
            print(f"[Redis Init] 加载 {len(prices)} 个期刊价格到 sys:journals:price")
        
        # 3. 加载年份统计 -> sys:year_number:{Name}
        cursor.execute("SELECT Name, YearNumberJson FROM contentlist_year_number")
        year_data = {}
        
        for name, year_json in cursor.fetchall():
            if year_json:
                try:
                    parsed = json.loads(year_json) if isinstance(year_json, str) else year_json
                    year_data[name] = {int(k): int(v) for k, v in parsed.items()}
                except (json.JSONDecodeError, ValueError):
                    pass
        
        if year_data:
            SystemCache.batch_set_year_numbers(year_data)
            print(f"[Redis Init] 加载 {len(year_data)} 个期刊年份统计")
        
        return True
        
    except Exception as e:
        print(f"[Redis Init] 加载期刊数据失败: {e}")
        return False
    finally:
        if cursor:
            cursor.close()


def load_papers_from_mysql(conn, batch_size: int = 10000,
                           progress_callback: Callable[[int, int], None] = None) -> bool:
    """
    从MySQL加载文献数据到Redis Block
    
    注意: 这是一个耗时操作，500万篇文献可能需要几分钟
    
    Args:
        conn: MySQL连接
        batch_size: 批量处理大小
        progress_callback: 进度回调函数 (loaded, total)
    """
    cursor = None
    try:
        cursor = conn.cursor()
        
        # 获取总数
        cursor.execute("SELECT COUNT(*) FROM paperinfo")
        total = cursor.fetchone()[0]
        print(f"[Redis Init] 开始加载 {total} 篇文献到Redis Block...")
        
        if total == 0:
            print("[Redis Init] paperinfo表为空，跳过")
            return True
        
        # 分批加载
        blocks: Dict[str, Dict[str, str]] = defaultdict(dict)
        loaded = 0
        
        cursor.execute("SELECT DOI, Bib FROM paperinfo")
        
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            
            for doi, bib_data in rows:
                if not doi or not bib_data:
                    continue
                
                # 解析Bib JSON获取期刊名和年份
                try:
                    if isinstance(bib_data, str):
                        bib_obj = json.loads(bib_data)
                    else:
                        bib_obj = bib_data
                    
                    journal = bib_obj.get('name', 'UNKNOWN')
                    year = bib_obj.get('year')
                    bib_str = bib_obj.get('bib', '')
                    
                    if journal and year and bib_str:
                        block_key = f"{journal}:{year}"
                        blocks[block_key][doi] = bib_str
                        
                except (json.JSONDecodeError, TypeError):
                    continue
                
                loaded += 1
            
            if progress_callback:
                progress_callback(loaded, total)
            
            # 定期写入Redis（避免内存占用过大）
            if len(blocks) > 100:
                _flush_blocks_to_redis(blocks)
                blocks.clear()
        
        # 写入剩余数据
        if blocks:
            _flush_blocks_to_redis(blocks)
        
        print(f"[Redis Init] 加载完成: {loaded}/{total} 篇文献")
        return True
        
    except Exception as e:
        print(f"[Redis Init] 加载文献数据失败: {e}")
        return False
    finally:
        if cursor:
            cursor.close()


def _flush_blocks_to_redis(blocks: Dict[str, Dict[str, str]]) -> None:
    """将内存中的Block数据写入Redis"""
    for block_key, papers in blocks.items():
        parts = block_key.split(":")
        if len(parts) >= 2:
            journal = parts[0]
            try:
                year = int(parts[-1])
                PaperBlocks.set_block(journal, year, papers, compress=True)
            except ValueError:
                continue


def init_redis_from_mysql(conn, 
                          load_papers: bool = True,
                          progress_callback: Callable[[str, int, int], None] = None) -> Dict[str, bool]:
    """
    从MySQL初始化所有Redis数据
    
    Args:
        conn: MySQL连接
        load_papers: 是否加载文献数据（耗时操作）
        progress_callback: 进度回调 (stage, loaded, total)
        
    Returns:
        {stage: success} 字典
    """
    results = {}
    
    # 检查Redis连接
    if not redis_ping():
        print("[Redis Init] Redis连接失败，跳过初始化")
        return {'connection': False}
    
    results['connection'] = True
    
    # 1. 加载标签数据
    print("\n[Redis Init] === 阶段1: 加载标签数据 ===")
    results['tags'] = load_tags_from_mysql(conn)
    
    # 2. 加载期刊数据
    print("\n[Redis Init] === 阶段2: 加载期刊数据 ===")
    results['journals'] = load_journals_from_mysql(conn)
    
    # 3. 加载文献数据（可选）
    if load_papers:
        print("\n[Redis Init] === 阶段3: 加载文献数据 ===")
        
        def paper_progress(loaded, total):
            if progress_callback:
                progress_callback('papers', loaded, total)
            if loaded % 50000 == 0:
                print(f"[Redis Init] 进度: {loaded}/{total} ({100*loaded//total}%)")
        
        results['papers'] = load_papers_from_mysql(conn, progress_callback=paper_progress)
    else:
        print("\n[Redis Init] 跳过文献数据加载")
        results['papers'] = True
    
    # 总结
    print("\n[Redis Init] === 初始化完成 ===")
    for stage, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {stage}")
    
    return results


def check_redis_data_loaded() -> Dict[str, bool]:
    """检查Redis数据是否已加载"""
    client = get_redis_client()
    if not client:
        return {'redis_available': False}
    
    results = {
        'redis_available': True,
        'tags_loaded': False,
        'journals_loaded': False,
        'blocks_loaded': False,
    }
    
    try:
        # 检查标签
        results['tags_loaded'] = client.exists("sys:tags:info") > 0
        
        # 检查期刊
        results['journals_loaded'] = client.exists("sys:journals:info") > 0
        
        # 检查Block（扫描是否存在任意meta:*键）
        for _ in client.scan_iter(match="meta:*", count=1):
            results['blocks_loaded'] = True
            break
            
    except Exception:
        pass
    
    return results

