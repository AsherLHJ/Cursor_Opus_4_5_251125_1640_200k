"""
查询任务相关API处理模块 (修复37: 添加Token认证)
负责查询任务提交、状态查询、暂停/恢复、结果获取等操作
"""

import json
import datetime
import threading
from typing import Dict, Tuple, Any, List

from ..config import config_loader as config
from ..load_data import db_reader
from ..redis.task_queue import TaskQueue
from ..redis.result_cache import ResultCache
from ..redis.user_cache import UserCache
from ..process.paper_processor import (
    process_papers, 
    process_papers_for_distillation
)
from ..load_data.query_dao import (
    get_query_progress,
    pause_query,
    resume_query,
    cancel_query
)
from .user_auth import require_auth  # 修复37: 导入用户认证模块


# ============================================================
# 费用计算函数（仅限后端内部调用，前端不可访问）
# ============================================================

def _calculate_query_cost(journals: List[str], start_year: int = None,
                          end_year: int = None, include_all: bool = True) -> Tuple[int, float]:
    """
    计算查询任务费用（纯Redis操作）
    
    安全原则: 此函数仅在后端调用，前端不可传递费用参数
    
    Args:
        journals: 期刊名列表
        start_year: 起始年份（include_all=False时有效）
        end_year: 结束年份（include_all=False时有效）
        include_all: 是否包含所有年份
        
    Returns:
        (total_papers, total_cost) 元组
    """
    from ..load_data.journal_dao import get_journal_prices, get_year_number
    
    if not journals:
        return 0, 0.0
    
    prices = get_journal_prices(journals)
    total_count = 0
    total_cost = 0.0
    
    for journal in journals:
        year_counts = get_year_number(journal)
        price = prices.get(journal, 1)
        if year_counts:
            if include_all:
                cnt = sum(year_counts.values())
            else:
                cnt = sum(c for y, c in year_counts.items()
                         if (not start_year or y >= start_year) and
                            (not end_year or y <= end_year))
            total_count += cnt
            total_cost += cnt * price
    
    return total_count, total_cost


def _calculate_distill_cost(uid: int, original_qid: str) -> Tuple[List[str], float, Dict[str, int]]:
    """
    计算蒸馏任务费用（优先Redis，MISS时回源MySQL）
    
    安全原则: 此函数仅在后端调用，从Redis直接获取期刊价格
    
    修复31优化: 返回doi_prices映射，供后续Worker使用，避免重复查询（0额外IOPS）
    
    Args:
        uid: 用户ID
        original_qid: 原始查询ID
        
    Returns:
        (relevant_dois, total_cost, doi_prices) 三元组
        - relevant_dois: 相关DOI列表
        - total_cost: 总费用（已乘以蒸馏系数）
        - doi_prices: {doi: actual_price} 映射（未乘蒸馏系数的原始价格）
    """
    from ..redis.result_cache import ResultCache
    from ..redis.system_cache import SystemCache
    from ..redis.paper_blocks import PaperBlocks
    from ..redis.system_config import SystemConfig
    
    all_results = ResultCache.get_all_results(uid, original_qid)
    
    # Redis MISS时从MySQL回源（可能因为7天TTL过期）
    if not all_results:
        from ..load_data.search_dao import get_all_results_from_mysql
        all_results = get_all_results_from_mysql(uid, original_qid)
        if all_results:
            print(f"[DistillCost] Redis MISS，从MySQL回源获取 {len(all_results)} 条结果")
    
    all_prices = SystemCache.get_all_prices()
    distill_rate = SystemConfig.get_distill_rate()  # 动态获取蒸馏系数
    
    relevant_dois = []
    total_cost = 0.0
    doi_prices = {}  # 修复31: 收集每个DOI的原始价格
    
    for doi, data in all_results.items():
        ai_result = data.get('ai_result', {})
        # 判断是否为相关文献
        is_relevant = False
        if isinstance(ai_result, dict):
            is_relevant = ai_result.get('relevant', '').upper() == 'Y'
        elif ai_result in (True, 1, '1', 'Y', 'y'):
            is_relevant = True
        
        if is_relevant:
            relevant_dois.append(doi)
            block_key = data.get('block_key', '')
            if block_key:
                parsed = PaperBlocks.parse_block_key(block_key)
                if parsed:
                    journal, _ = parsed
                    price = all_prices.get(journal, 1)
                    doi_prices[doi] = price  # 存储原始价格（未乘系数）
                    total_cost += price * distill_rate  # 蒸馏费率（动态配置）
                else:
                    doi_prices[doi] = 1  # 默认价格
                    total_cost += distill_rate  # 默认费用（使用蒸馏系数）
            else:
                doi_prices[doi] = 1  # 无block_key时默认价格
                total_cost += distill_rate  # 无block_key时使用蒸馏系数
    
    return relevant_dois, total_cost, doi_prices


def handle_query_api(path: str, method: str, headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    处理查询任务相关的API请求 (修复37: 添加Token认证)
    
    Args:
        path: 请求路径
        method: HTTP方法
        headers: 请求头
        payload: 请求体数据
        
    Returns:
        (status_code, response_dict)
    """
    # ============================================================
    # POST 请求（需要认证的端点）
    # ============================================================
    if method == 'POST':
        if path == '/api/start_search':
            return _handle_start_search(headers, payload)
        
        if path == '/api/start_distillation':
            return _handle_start_distillation(headers, payload)
        
        if path == '/api/estimate_distillation_cost':
            return _handle_estimate_distillation_cost(headers, payload)
        
        if path == '/api/update_pause_status':
            return _handle_update_pause_status(headers, payload)
        
        if path == '/api/pause_query':
            return _handle_pause_query(headers, payload)
        
        if path == '/api/resume_query':
            return _handle_resume_query(headers, payload)
        
        if path == '/api/cancel_query':
            return _handle_cancel_query(headers, payload)
        
        # 以下端点不需要认证（公开数据）
        if path == '/api/update':
            return _handle_update_config(payload)
        
        if path == '/api/journals':
            return _handle_get_journals(payload)
        
        if path == '/api/count_papers':
            return _handle_count_papers(payload)
        
        if path == '/api/query_status':
            return _handle_get_query_status(headers, payload)
    
    # ============================================================
    # GET 请求
    # ============================================================
    if method == 'GET':
        if path == '/api/query_status':
            return _handle_get_query_status(headers, payload)
        
        if path == '/api/query_result':
            return _handle_get_query_result(headers, payload)
        
        if path == '/api/query_history':
            return _handle_get_query_history(headers)
        
        if path == '/api/query_progress':
            return _handle_get_query_progress(headers, payload)
        
        if path == '/api/get_query_info':
            return _handle_get_query_info(headers, payload)
        
        # 以下端点不需要认证（公开数据）
        if path == '/api/tags':
            return _handle_get_tags(payload)
        
        if path == '/api/journals':
            return _handle_get_journals(payload)
    
    return 404, {'success': False, 'error': 'not_found'}


def _handle_start_search(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    处理开始搜索请求 (修复37: 需要Token认证)
    
    用户只能使用自己的账户发起查询
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        question = str(payload.get('question') or '').strip()
        requirements = str(payload.get('requirements') or '').strip()
        include_all_years = bool(payload.get('include_all_years'))
        language = str(payload.get('language') or 'zh').strip()  # 修复36: 接收语言参数
        
        # 校验研究问题
        if not question:
            return 400, {'success': False, 'error': 'missing_question'}
        
        # 解析年份
        start_year_val = payload.get('start_year')
        end_year_val = payload.get('end_year')
        
        if not include_all_years:
            def _valid_year(v):
                try:
                    s = str(v).strip()
                    return len(s) == 4 and s.isdigit()
                except Exception:
                    return False
            
            if not _valid_year(start_year_val) or not _valid_year(end_year_val):
                return 400, {'success': False, 'error': 'invalid_year'}
            
            try:
                start_year = int(str(start_year_val).strip())
                end_year = int(str(end_year_val).strip())
            except Exception:
                return 400, {'success': False, 'error': 'invalid_year'}
            
            if end_year < start_year:
                return 400, {'success': False, 'error': 'invalid_year_order'}
        else:
            start_year = config.YEAR_RANGE_START
            end_year = config.YEAR_RANGE_END
        
        # 解析期刊/文件夹选择
        selected_journals = payload.get('selected_journals')
        selected_folders = payload.get('selected_folders')
        
        if selected_journals is not None:
            if not isinstance(selected_journals, list):
                selected_journals = []
            selected_items = selected_journals
            if not selected_journals:
                return 400, {'success': False, 'error': 'no_selected_journals'}
        else:
            selected_folders = selected_folders or []
            if not isinstance(selected_folders, list):
                selected_folders = []
            selected_items = selected_folders
            if not selected_folders:
                return 400, {'success': False, 'error': 'no_selected_folders'}
        
        # 构建搜索参数
        search_params = {
            'journals': selected_items,
            'year_range': 'all' if include_all_years else f'{start_year}-{end_year}',
            'research_question': question,
            'requirements': requirements,
            'start_year': start_year,
            'end_year': end_year,
            'include_all_years': include_all_years,
            'language': language  # 修复36: 存储语言参数
        }
        
        # 后端独立计算费用（安全原则：不信任前端传来的任何费用数据）
        paper_count, estimated_cost = _calculate_query_cost(
            selected_items,
            start_year if not include_all_years else None,
            end_year if not include_all_years else None,
            include_all_years
        )
        
        # 余额检查
        if estimated_cost > 0:
            user_balance = UserCache.get_balance(uid)
            if user_balance is None:
                user_balance = db_reader.get_balance(uid) or 0
            
            if user_balance < estimated_cost:
                return 400, {
                    'success': False, 
                    'error': 'insufficient_balance',
                    'message': f'余额不足（需要 {estimated_cost}，当前 {user_balance}）'
                }
        
        # 调用新架构的处理函数（修复31c：传递正确的estimated_cost）
        success, result = process_papers(uid, search_params, estimated_cost=estimated_cost)
        
        if success:
            return 200, {
                'success': True,
                'query_id': result,
                'article_count': paper_count,
                'estimated_cost': estimated_cost,
                'message': 'Query submitted successfully. Processing in background.'
            }
        else:
            return 400, {'success': False, 'error': 'search_failed', 'message': result}
            
    except Exception as e:
        return 500, {'success': False, 'error': 'start_search_failed', 'message': str(e)}


def _handle_start_distillation(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    处理开始蒸馏请求 (修复37: 需要Token认证)
    
    安全原则：使用后端 _calculate_distill_cost 函数计算费用（纯Redis操作）
    用户只能使用自己的账户发起蒸馏
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        question = str(payload.get('question') or '').strip()
        requirements = str(payload.get('requirements') or '').strip()
        language = str(payload.get('language') or 'zh').strip()  # 修复36: 接收语言参数
        
        # 同时支持 original_query_id 和 original_query_index 参数名
        original_query_id = payload.get('original_query_id') or payload.get('original_query_index')
        if not original_query_id:
            return 400, {'success': False, 'error': 'missing_original_query_id'}
        
        # 保持字符串类型（新架构格式如 Q20251127102812_74137bb4）
        original_query_id = str(original_query_id)
        
        # 使用后端费用计算函数（纯Redis操作，替代get_prices_by_dois）
        # 修复31: 返回doi_prices，传递给Worker避免重复查询
        try:
            relevant_dois, estimated_cost, doi_prices = _calculate_distill_cost(uid, original_query_id)
        except Exception as e:
            return 500, {'success': False, 'error': 'calculate_cost_failed', 'message': str(e)}
        
        if not relevant_dois:
            return 400, {'success': False, 'error': 'no_relevant_papers'}
        
        # 获取用户余额
        user_balance = UserCache.get_balance(uid)
        if user_balance is None:
            user_balance = db_reader.get_balance(uid) or 0
        
        # 余额不足检查
        if user_balance < estimated_cost:
            return 400, {
                'success': False,
                'error': 'insufficient_balance',
                'message': f'余额不足（需要 {estimated_cost:.1f}，当前 {user_balance}）'
            }
        
        # 调用蒸馏处理函数（修复31b：传递doi_prices和正确的estimated_cost）
        success, result = process_papers_for_distillation(
            uid, original_query_id, relevant_dois,
            research_question=question,
            requirements=requirements,
            doi_prices=doi_prices,
            estimated_cost=estimated_cost,  # 传递正确的预估费用（考虑实际期刊价格）
            user_language=language  # 修复36/38: 传递语言参数（修复38：避免与language模块名冲突）
        )
        
        if success:
            return 200, {
                'success': True,
                'query_id': result,
                'doi_count': len(relevant_dois),
                'estimated_cost': round(estimated_cost, 1),
                'message': 'Distillation submitted successfully.'
            }
        else:
            return 400, {'success': False, 'error': 'distillation_failed', 'message': result}
            
    except Exception as e:
        return 500, {'success': False, 'error': 'start_distillation_failed', 'message': str(e)}


def _handle_estimate_distillation_cost(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    估算蒸馏费用 (修复37: 需要Token认证)
    
    安全原则：使用后端 _calculate_distill_cost 函数计算费用（纯Redis操作）
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        # 同时支持 original_query_id 和 original_query_index 参数名
        original_query_id = payload.get('original_query_id') or payload.get('original_query_index')
        
        if not original_query_id:
            return 400, {'success': False, 'error': 'missing_original_query_id'}
        
        # 保持字符串类型（新架构格式如 Q20251127102812_74137bb4）
        original_query_id = str(original_query_id)
        
        # 使用后端费用计算函数（纯Redis操作，替代get_prices_by_dois）
        # 修复31: _calculate_distill_cost 现在返回三元组，这里只使用前两个
        try:
            relevant_dois, estimated_cost, _ = _calculate_distill_cost(uid, original_query_id)
        except Exception:
            relevant_dois = []
            estimated_cost = 0.0
        
        if not relevant_dois:
            return 200, {
                'success': True,
                'doi_count': 0,
                'relevant_count': 0,
                'estimated_cost': 0,
                'user_balance': UserCache.get_balance(uid) or 0,
                'insufficient': False
            }
        
        user_balance = UserCache.get_balance(uid) or db_reader.get_balance(uid) or 0
        
        return 200, {
            'success': True,
            'doi_count': len(relevant_dois),
            'relevant_count': len(relevant_dois),
            'estimated_cost': round(estimated_cost, 1),
            'user_balance': float(user_balance),
            'insufficient': user_balance < estimated_cost
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'estimate_distillation_failed', 'message': str(e)}


def _handle_get_query_status(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    获取查询状态 (修复37: 需要Token认证)
    
    用户只能查看自己的任务状态
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        status = get_query_progress(uid, str(qid))
        return 200, {'success': True, **(status or {})}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_status_failed', 'message': str(e)}


def _handle_get_query_result(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    获取查询结果 (修复37: 需要Token认证)
    
    用户只能查看自己的任务结果
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        # 先从 Redis 获取结果
        results = ResultCache.get_all_results(uid, str(qid))
        
        # 如果 Redis 没有，从 MySQL 获取
        if not results:
            results = db_reader.fetch_results_with_paperinfo(str(qid))
        
        return 200, {'success': True, 'results': results or []}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_result_failed', 'message': str(e)}


def _handle_update_pause_status(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    更新暂停状态 (修复37: 需要Token认证)
    
    新架构修复：同时支持 query_id 和 query_index 参数名，
    不再强制转int，使用字符串类型的query_id
    用户只能操作自己的任务
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        # 同时支持 query_id 和 query_index 参数名
        query_id = payload.get('query_id') or payload.get('query_index')
        should_pause = payload.get('should_pause')
        
        if not query_id or should_pause is None:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        try:
            should_pause = bool(should_pause)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_parameters'}
        
        # query_id 保持字符串类型（新架构格式如 Q20251127102812_74137bb4）
        qid = str(query_id)
        
        if should_pause:
            op_success = pause_query(uid, qid)
            msg = 'paused' if op_success else 'pause_failed'
        else:
            op_success = resume_query(uid, qid)
            msg = 'resumed' if op_success else 'resume_failed'
        
        if op_success:
            return 200, {'success': True, 'message': 'pause_status_updated'}
        else:
            return 400, {'success': False, 'error': 'update_failed', 'message': msg}
            
    except Exception as e:
        return 500, {'success': False, 'error': 'update_failed', 'message': str(e)}


def _handle_update_config(payload: Dict) -> Tuple[int, Dict]:
    """更新搜索配置并返回统计"""
    try:
        question = str(payload.get('question') or '').strip()
        requirements = str(payload.get('requirements') or '').strip()
        include_all_years = bool(payload.get('include_all_years'))
        
        start_year = payload.get('start_year')
        end_year = payload.get('end_year')
        try:
            start_year = int(start_year) if start_year not in (None, '') else config.YEAR_RANGE_START
        except Exception:
            start_year = config.YEAR_RANGE_START
        try:
            end_year = int(end_year) if end_year not in (None, '') else config.YEAR_RANGE_END
        except Exception:
            end_year = config.YEAR_RANGE_END
        
        selected_journals = payload.get('selected_journals')
        selected_folders = payload.get('selected_folders')
        
        if selected_journals is not None:
            if not isinstance(selected_journals, list):
                selected_journals = []
            selected_items = selected_journals
        else:
            selected_folders = selected_folders or []
            if not isinstance(selected_folders, list):
                selected_folders = []
            selected_items = selected_folders
        
        # 更新配置
        config.ResearchQuestion = question
        config.Requirements = requirements
        config.INCLUDE_ALL_YEARS = include_all_years
        config.YEAR_RANGE_START = start_year
        config.YEAR_RANGE_END = end_year
        try:
            config.save_config()
        except Exception:
            pass
        
        # 统计论文数量和费用（使用实际期刊价格）
        try:
            if selected_items:
                # 使用后端费用计算函数（不信任前端数据）
                count, estimated_cost = _calculate_query_cost(
                    selected_items,
                    start_year if not include_all_years else None,
                    end_year if not include_all_years else None,
                    include_all_years
                )
            else:
                count = 0
                estimated_cost = 0
        except Exception:
            count = 0
            estimated_cost = 0
        
        return 200, {'selected_count': count, 'estimated_cost': estimated_cost}
    except Exception as e:
        return 500, {'success': False, 'error': 'update_failed', 'message': str(e)}


def _handle_get_journals(payload: Dict) -> Tuple[int, Dict]:
    """获取期刊列表"""
    try:
        selected_tags = payload.get('selected_tags', {})
        if not isinstance(selected_tags, dict):
            selected_tags = {}
        
        db_time_range = {"include_all": True}
        journals = db_reader.get_journals_by_filters(db_time_range, selected_tags)
        
        return 200, {'journals': journals}
    except Exception as e:
        return 500, {'error': 'get_journals_failed', 'message': str(e)}


def _handle_count_papers(payload: Dict) -> Tuple[int, Dict]:
    """统计论文数量"""
    try:
        selected_journals = payload.get('selected_journals', [])
        start_year = payload.get('start_year')
        end_year = payload.get('end_year')
        
        if not isinstance(selected_journals, list):
            selected_journals = []
        
        if start_year is not None:
            try:
                start_year = int(start_year)
            except (ValueError, TypeError):
                return 400, {'error': 'invalid_start_year'}
        
        if end_year is not None:
            try:
                end_year = int(end_year)
            except (ValueError, TypeError):
                return 400, {'error': 'invalid_end_year'}
        
        time_range = None
        if start_year is not None and end_year is not None:
            time_range = {
                "start_year": start_year,
                "end_year": end_year,
                "include_all": False
            }
        else:
            time_range = {"include_all": True}
        
        count = db_reader.count_papers_by_filters(selected_journals, time_range)
        
        return 200, {'count': count}
    except Exception as e:
        return 500, {'error': 'count_papers_failed', 'message': str(e)}


def _handle_get_tags(payload: Dict = None) -> Tuple[int, Dict]:
    """获取标签"""
    try:
        if payload is None:
            payload = {}
        
        tag_type = payload.get('type', '')
        selected_raw = payload.get('selected', '')
        
        # 解析 selected 参数
        selected_tags = {}
        if selected_raw:
            try:
                import json
                selected_tags = json.loads(selected_raw)
            except Exception:
                selected_tags = {}
        
        if tag_type:
            if isinstance(selected_tags, dict) and any(selected_tags.get(k) for k in selected_tags.keys()):
                tags = db_reader.get_tags_by_type_filtered(tag_type, selected_tags)
            else:
                tags = db_reader.get_tags_by_type(tag_type)
        else:
            tags = db_reader.get_all_tags()
        
        return 200, {'success': True, 'tags': tags}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_tags_failed', 'message': str(e)}


def _handle_pause_query(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    暂停查询任务 (修复37: 需要Token认证)
    
    用户只能暂停自己的任务
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        op_success = pause_query(uid, str(qid))
        msg = 'Query paused' if op_success else 'Failed to pause'
        if op_success:
            return 200, {'success': True, 'message': msg}
        else:
            return 400, {'success': False, 'error': 'pause_failed', 'message': msg}
    except Exception as e:
        return 500, {'success': False, 'error': 'pause_query_failed', 'message': str(e)}


def _handle_resume_query(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    恢复查询任务 (修复37: 需要Token认证)
    
    用户只能恢复自己的任务
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        op_success = resume_query(uid, str(qid))
        msg = 'Query resumed' if op_success else 'Failed to resume'
        if op_success:
            return 200, {'success': True, 'message': msg}
        else:
            return 400, {'success': False, 'error': 'resume_failed', 'message': msg}
    except Exception as e:
        return 500, {'success': False, 'error': 'resume_query_failed', 'message': str(e)}


def _handle_cancel_query(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    取消查询任务 (修复37: 需要Token认证)
    
    用户只能取消自己的任务
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        op_success = cancel_query(uid, str(qid))
        msg = 'Query cancelled' if op_success else 'Failed to cancel'
        if op_success:
            return 200, {'success': True, 'message': msg}
        else:
            return 400, {'success': False, 'error': 'cancel_failed', 'message': msg}
    except Exception as e:
        return 500, {'success': False, 'error': 'cancel_query_failed', 'message': str(e)}


def _handle_get_query_history(headers: Dict) -> Tuple[int, Dict]:
    """
    获取查询历史 (修复37: 需要Token认证)
    
    用户只能查看自己的查询历史
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        # 获取查询历史
        logs = db_reader.get_query_logs_by_uid(uid)
        
        def fmt_time(v):
            import datetime
            if v is None:
                return None
            if isinstance(v, datetime.datetime):
                return v.strftime("%Y-%m-%d %H:%M:%S")
            return str(v)
        
        formatted_logs = []
        for r in logs:
            # 从 search_params 中提取字段（新架构）
            sp = r.get('search_params') or {}
            if isinstance(sp, str):
                try:
                    sp = json.loads(sp)
                except Exception:
                    sp = {}
            
            # 修复30：从 search_params 获取 is_distillation 和 original_query_id
            is_distillation = bool(sp.get('is_distillation'))
            original_query_id = sp.get('original_query_id', '')
            
            formatted_logs.append({
                'query_id': r.get('query_id') or r.get('query_index'),
                'uid': r.get('uid'),
                'query_time': fmt_time(r.get('query_time') or r.get('start_time')),
                'selected_folders': sp.get('selected_journals') or sp.get('journals') or r.get('selected_folders') or '',
                'year_range': sp.get('year_range') or r.get('year_range') or '',
                'research_question': sp.get('research_question') or r.get('research_question') or '',
                'requirements': sp.get('requirements') or r.get('requirements') or '',
                'query_table': r.get('query_table') or '',
                'start_time': fmt_time(r.get('start_time')),
                'end_time': fmt_time(r.get('end_time')),
                'completed': bool(r.get('end_time') or r.get('status') == 'COMPLETED' or r.get('status') == 'DONE'),
                'total_papers_count': r.get('total_papers_count') or sp.get('max_papers') or sp.get('doi_count') or 0,
                'estimated_cost': r.get('estimated_cost') or r.get('total_cost') or 0,  # 修复31: 添加开销
                'is_distillation': is_distillation,
                'original_query_id': original_query_id,
                'is_visible': r.get('is_visible', True),
                'should_pause': bool(r.get('should_pause')),
            })
        
        return 200, {'success': True, 'logs': formatted_logs}
    except Exception as e:
        return 500, {'success': False, 'error': 'history_failed', 'message': str(e)}


def _handle_get_query_progress(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    获取查询进度 (修复37: 需要Token认证)
    
    用户只能查看自己的任务进度
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        qid = payload.get('query_index') or payload.get('query_id')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_query_index'}
        
        # 获取进度（使用Token认证后的uid）
        status = get_query_progress(uid, str(qid)) or {}
        
        return 200, {
            'success': True,
            'progress': status.get('progress', 0),
            'completed': status.get('state') in ('DONE', 'COMPLETED'),
            'total_blocks': status.get('total_blocks', 0),
            'finished_blocks': status.get('finished_blocks', 0),
            'finished_papers': status.get('finished_papers', 0),
            'is_paused': status.get('is_paused', False),
            'current_balance': UserCache.get_balance(uid)
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'progress_failed', 'message': str(e)}


def _handle_get_query_info(headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    获取查询详情 (修复37: 需要Token认证)
    
    用户只能查看自己的任务详情
    """
    try:
        # 修复37: 验证认证，从Token获取uid
        success, uid, error = require_auth(headers)
        if not success:
            return 401, {'success': False, 'error': error, 'message': '请先登录'}
        
        qid = payload.get('query_index') or payload.get('query_id')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_query_index'}
        
        # 从数据库获取查询信息
        from ..load_data.query_dao import get_query_log
        
        row = get_query_log(str(qid))
        if not row:
            return 404, {'success': False, 'error': 'query_not_found'}
        
        # 验证归属（确保用户只能访问自己的任务）
        if row.get('uid') != uid:
            return 403, {'success': False, 'error': 'access_denied'}
        
        def fmt_time(v):
            import datetime
            if v is None:
                return None
            if isinstance(v, datetime.datetime):
                return v.strftime("%Y-%m-%d %H:%M:%S")
            return str(v)
        
        # 从 search_params 中提取字段（新架构）
        sp = row.get('search_params') or {}
        if isinstance(sp, str):
            try:
                sp = json.loads(sp)
            except Exception:
                sp = {}
        
        # 修复30：从 search_params 获取 is_distillation 和 original_query_id
        is_distillation = bool(sp.get('is_distillation'))
        original_query_id = sp.get('original_query_id', '')
        
        return 200, {
            'success': True,
            'query_info': {
                'query_id': row.get('query_id') or row.get('query_index'),
                'uid': row.get('uid'),
                'query_time': fmt_time(row.get('start_time')),
                'selected_folders': sp.get('selected_journals') or sp.get('journals') or row.get('selected_folders') or '',
                'year_range': sp.get('year_range') or row.get('year_range') or '',
                'research_question': sp.get('research_question') or row.get('research_question') or '',
                'requirements': sp.get('requirements') or row.get('requirements') or '',
                'query_table': row.get('query_table') or '',
                'start_time': fmt_time(row.get('start_time')),
                'end_time': fmt_time(row.get('end_time')),
                'completed': bool(row.get('end_time') or row.get('status') == 'COMPLETED' or row.get('status') == 'DONE'),
                'should_pause': bool(row.get('should_pause')),  # 修复10: 添加暂停状态字段
                'is_distillation': is_distillation,  # 修复30: 添加蒸馏标识
                'original_query_id': original_query_id,  # 修复30: 添加父任务ID
                'total_papers_count': sp.get('max_papers') or sp.get('doi_count') or 0,  # 修复31: 添加文章总数
                'estimated_cost': row.get('estimated_cost') or row.get('total_cost') or 0,  # 修复31: 添加开销
            }
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'get_query_info_failed', 'message': str(e)}

