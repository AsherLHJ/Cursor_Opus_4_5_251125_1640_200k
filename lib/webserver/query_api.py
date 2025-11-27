"""
查询任务相关API处理模块
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


def handle_query_api(path: str, method: str, headers: Dict, payload: Dict) -> Tuple[int, Dict]:
    """
    处理查询任务相关的API请求
    
    Args:
        path: 请求路径
        method: HTTP方法
        headers: 请求头
        payload: 请求体数据
        
    Returns:
        (status_code, response_dict)
    """
    # ============================================================
    # POST 请求
    # ============================================================
    if method == 'POST':
        if path == '/api/start_search':
            return _handle_start_search(payload)
        
        if path == '/api/start_distillation':
            return _handle_start_distillation(payload)
        
        if path == '/api/estimate_distillation_cost':
            return _handle_estimate_distillation_cost(payload)
        
        if path == '/api/update_pause_status':
            return _handle_update_pause_status(payload)
        
        if path == '/api/pause_query':
            return _handle_pause_query(payload)
        
        if path == '/api/resume_query':
            return _handle_resume_query(payload)
        
        if path == '/api/cancel_query':
            return _handle_cancel_query(payload)
        
        if path == '/api/update':
            return _handle_update_config(payload)
        
        if path == '/api/journals':
            return _handle_get_journals(payload)
        
        if path == '/api/count_papers':
            return _handle_count_papers(payload)
        
        if path == '/api/query_status':
            return _handle_get_query_status(payload)
    
    # ============================================================
    # GET 请求
    # ============================================================
    if method == 'GET':
        if path == '/api/query_status':
            return _handle_get_query_status(payload)
        
        if path == '/api/query_result':
            return _handle_get_query_result(payload)
        
        if path == '/api/query_history':
            return _handle_get_query_history(payload)
        
        if path == '/api/query_progress':
            return _handle_get_query_progress(payload)
        
        if path == '/api/get_query_info':
            return _handle_get_query_info(payload)
        
        if path == '/api/tags':
            return _handle_get_tags(payload)
        
        if path == '/api/journals':
            return _handle_get_journals(payload)
    
    return 404, {'success': False, 'error': 'not_found'}


def _handle_start_search(payload: Dict) -> Tuple[int, Dict]:
    """处理开始搜索请求"""
    try:
        question = str(payload.get('question') or '').strip()
        requirements = str(payload.get('requirements') or '').strip()
        include_all_years = bool(payload.get('include_all_years'))
        
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
        
        # 验证 UID
        uid_raw = payload.get('uid')
        try:
            uid = int(uid_raw)
        except Exception:
            uid = 0
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        # 构建搜索参数
        search_params = {
            'journals': selected_items,
            'year_range': 'all' if include_all_years else f'{start_year}-{end_year}',
            'research_question': question,
            'requirements': requirements,
            'start_year': start_year,
            'end_year': end_year,
            'include_all_years': include_all_years
        }
        
        # 余额检查（使用前端传来的预估费用）
        estimated_cost = payload.get('estimated_cost') or 0
        try:
            estimated_cost = float(estimated_cost)
        except (ValueError, TypeError):
            estimated_cost = 0
        
        if estimated_cost > 0:
            from ..redis.user_cache import UserCache
            user_balance = UserCache.get_balance(uid)
            if user_balance is None:
                user_balance = db_reader.get_balance(uid) or 0
            
            if user_balance < estimated_cost:
                return 400, {
                    'success': False, 
                    'error': 'insufficient_balance',
                    'message': f'余额不足'
                }
        
        # 调用新架构的处理函数
        success, result = process_papers(uid, search_params)
        
        if success:
            return 200, {
                'success': True,
                'query_id': result,
                'message': 'Query submitted successfully. Processing in background.'
            }
        else:
            return 400, {'success': False, 'error': 'search_failed', 'message': result}
            
    except Exception as e:
        return 500, {'success': False, 'error': 'start_search_failed', 'message': str(e)}


def _handle_start_distillation(payload: Dict) -> Tuple[int, Dict]:
    """
    处理开始蒸馏请求
    
    新架构修复：同时支持 original_query_id 和 original_query_index 参数名，
    使用字符串类型的query_id，修正 get_relevant_dois 调用参数
    """
    try:
        question = str(payload.get('question') or '').strip()
        requirements = str(payload.get('requirements') or '').strip()
        
        # 同时支持 original_query_id 和 original_query_index 参数名
        original_query_id = payload.get('original_query_id') or payload.get('original_query_index')
        if not original_query_id:
            return 400, {'success': False, 'error': 'missing_original_query_id'}
        
        # 保持字符串类型（新架构格式如 Q20251127102812_74137bb4）
        original_query_id = str(original_query_id)
        
        uid_raw = payload.get('uid')
        try:
            uid = int(uid_raw)
        except Exception:
            uid = 0
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        # 获取原始查询的相关DOI列表（修正：传入uid和query_id两个参数）
        try:
            relevant_dois = db_reader.get_relevant_dois(uid, original_query_id)
        except Exception as e:
            return 500, {'success': False, 'error': 'get_relevant_dois_failed', 'message': str(e)}
        
        if not relevant_dois:
            return 400, {'success': False, 'error': 'no_relevant_papers'}
        
        # 计算蒸馏费用（基价*0.1）并检查余额
        try:
            price_map = db_reader.get_prices_by_dois(relevant_dois)
            estimated_cost = sum(float(price_map.get(doi, 1.0)) * 0.1 for doi in relevant_dois)
        except Exception:
            estimated_cost = len(relevant_dois) * 0.1  # 默认每篇0.1
        
        # 获取用户余额
        from ..redis.user_cache import UserCache
        user_balance = UserCache.get_balance(uid)
        if user_balance is None:
            user_balance = db_reader.get_balance(uid) or 0
        
        # 余额不足检查
        if user_balance < estimated_cost:
            return 400, {
                'success': False,
                'error': 'insufficient_balance',
                'message': f'余额不足'
            }
        
        # 调用蒸馏处理函数
        success, result = process_papers_for_distillation(uid, original_query_id, relevant_dois)
        
        if success:
            return 200, {
                'success': True,
                'query_id': result,
                'message': 'Distillation submitted successfully.'
            }
        else:
            return 400, {'success': False, 'error': 'distillation_failed', 'message': result}
            
    except Exception as e:
        return 500, {'success': False, 'error': 'start_distillation_failed', 'message': str(e)}


def _handle_estimate_distillation_cost(payload: Dict) -> Tuple[int, Dict]:
    """
    估算蒸馏费用
    
    新架构修复：同时支持 original_query_id 和 original_query_index 参数名，
    使用字符串类型的query_id，修正 get_relevant_dois 调用参数
    """
    try:
        uid_raw = payload.get('uid')
        # 同时支持 original_query_id 和 original_query_index 参数名
        original_query_id = payload.get('original_query_id') or payload.get('original_query_index')
        
        try:
            uid = int(uid_raw)
        except Exception:
            uid = 0
        
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        if not original_query_id:
            return 400, {'success': False, 'error': 'missing_original_query_id'}
        
        # 保持字符串类型（新架构格式如 Q20251127102812_74137bb4）
        original_query_id = str(original_query_id)
        
        # 获取相关DOI（修正：传入uid和query_id两个参数）
        relevant_dois = db_reader.get_relevant_dois(uid, original_query_id)
        if not relevant_dois:
            return 200, {
                'success': True,
                'relevant_count': 0,
                'estimated_cost': 0,
                'user_balance': UserCache.get_balance(uid) or 0,
                'insufficient': False
            }
        
        # 计算蒸馏费用（基价*0.1）
        try:
            price_map = db_reader.get_prices_by_dois(relevant_dois)
            total_cost = 0.0
            for doi in relevant_dois:
                base = float(price_map.get(doi, 1.0))
                total_cost += base * 0.1
            estimated_cost = round(total_cost, 1)
        except Exception:
            estimated_cost = 0.0
        
        user_balance = UserCache.get_balance(uid) or db_reader.get_balance(uid) or 0
        
        return 200, {
            'success': True,
            'relevant_count': len(relevant_dois),
            'estimated_cost': estimated_cost,
            'user_balance': float(user_balance),
            'insufficient': user_balance < estimated_cost
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'estimate_distillation_failed', 'message': str(e)}


def _handle_get_query_status(payload: Dict) -> Tuple[int, Dict]:
    """获取查询状态"""
    try:
        uid = payload.get('uid')
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not uid or not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        status = get_query_progress(uid, str(qid))
        return 200, {'success': True, **(status or {})}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_status_failed', 'message': str(e)}


def _handle_get_query_result(payload: Dict) -> Tuple[int, Dict]:
    """获取查询结果"""
    try:
        uid = payload.get('uid')
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not uid or not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        # 先从 Redis 获取结果
        results = ResultCache.get_all_results(uid, str(qid))
        
        # 如果 Redis 没有，从 MySQL 获取
        if not results:
            results = db_reader.fetch_results_with_paperinfo(str(qid))
        
        return 200, {'success': True, 'results': results or []}
    except Exception as e:
        return 500, {'success': False, 'error': 'get_result_failed', 'message': str(e)}


def _handle_update_pause_status(payload: Dict) -> Tuple[int, Dict]:
    """
    更新暂停状态
    
    新架构修复：同时支持 query_id 和 query_index 参数名，
    不再强制转int，使用字符串类型的query_id
    """
    try:
        # 同时支持 query_id 和 query_index 参数名
        query_id = payload.get('query_id') or payload.get('query_index')
        uid = payload.get('uid')
        should_pause = payload.get('should_pause')
        
        if not query_id or uid is None or should_pause is None:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        try:
            uid = int(uid)
            should_pause = bool(should_pause)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_parameters'}
        
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        # query_id 保持字符串类型（新架构格式如 Q20251127102812_74137bb4）
        qid = str(query_id)
        
        if should_pause:
            success = pause_query(uid, qid)
            msg = 'paused' if success else 'pause_failed'
        else:
            success = resume_query(uid, qid)
            msg = 'resumed' if success else 'resume_failed'
        
        if success:
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
        
        # 统计论文数量和费用
        try:
            if selected_journals is not None:
                time_range = None
                if not include_all_years:
                    time_range = {
                        "start_year": start_year,
                        "end_year": end_year,
                        "include_all": False
                    }
                else:
                    time_range = {"include_all": True}
                count = db_reader.count_papers_by_filters(selected_journals, time_range)
                estimated_cost = count  # 简化：每篇1点
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


def _handle_pause_query(payload: Dict) -> Tuple[int, Dict]:
    """暂停查询任务"""
    try:
        uid = payload.get('uid')
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not uid or not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        success = pause_query(uid, str(qid))
        msg = 'Query paused' if success else 'Failed to pause'
        if success:
            return 200, {'success': True, 'message': msg}
        else:
            return 400, {'success': False, 'error': 'pause_failed', 'message': msg}
    except Exception as e:
        return 500, {'success': False, 'error': 'pause_query_failed', 'message': str(e)}


def _handle_resume_query(payload: Dict) -> Tuple[int, Dict]:
    """恢复查询任务"""
    try:
        uid = payload.get('uid')
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not uid or not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        success = resume_query(uid, str(qid))
        msg = 'Query resumed' if success else 'Failed to resume'
        if success:
            return 200, {'success': True, 'message': msg}
        else:
            return 400, {'success': False, 'error': 'resume_failed', 'message': msg}
    except Exception as e:
        return 500, {'success': False, 'error': 'resume_query_failed', 'message': str(e)}


def _handle_cancel_query(payload: Dict) -> Tuple[int, Dict]:
    """取消查询任务"""
    try:
        uid = payload.get('uid')
        qid = payload.get('query_id') or payload.get('query_index')
        
        if not uid or not qid:
            return 400, {'success': False, 'error': 'missing_parameters'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        success = cancel_query(uid, str(qid))
        msg = 'Query cancelled' if success else 'Failed to cancel'
        if success:
            return 200, {'success': True, 'message': msg}
        else:
            return 400, {'success': False, 'error': 'cancel_failed', 'message': msg}
    except Exception as e:
        return 500, {'success': False, 'error': 'cancel_query_failed', 'message': str(e)}


def _handle_get_query_history(payload: Dict) -> Tuple[int, Dict]:
    """获取查询历史"""
    try:
        uid = payload.get('uid')
        if not uid:
            return 400, {'success': False, 'error': 'missing_uid'}
        
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return 400, {'success': False, 'error': 'invalid_uid'}
        
        if uid <= 0:
            return 400, {'success': False, 'error': 'invalid_uid'}
        
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
                'total_papers_count': r.get('total_papers_count') or sp.get('max_papers') or 0,
                'is_distillation': bool(r.get('is_distillation')),
                'is_visible': r.get('is_visible', True),
                'should_pause': bool(r.get('should_pause')),
            })
        
        return 200, {'success': True, 'logs': formatted_logs}
    except Exception as e:
        return 500, {'success': False, 'error': 'history_failed', 'message': str(e)}


def _handle_get_query_progress(payload: Dict) -> Tuple[int, Dict]:
    """获取查询进度"""
    try:
        qid = payload.get('query_index') or payload.get('query_id')
        uid_raw = payload.get('uid')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_query_index'}
        
        # 从前端获取uid（新架构：前端传递uid以正确构建Redis Key）
        try:
            uid = int(uid_raw) if uid_raw else 0
        except (ValueError, TypeError):
            uid = 0
        
        # 获取进度
        status = get_query_progress(uid, str(qid)) or {}
        
        return 200, {
            'success': True,
            'progress': status.get('progress', 0),
            'completed': status.get('state') in ('DONE', 'COMPLETED'),
            'total_blocks': status.get('total_blocks', 0),
            'finished_blocks': status.get('finished_blocks', 0),
            'finished_papers': status.get('finished_papers', 0),
            'is_paused': status.get('is_paused', False)
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'progress_failed', 'message': str(e)}


def _handle_get_query_info(payload: Dict) -> Tuple[int, Dict]:
    """获取查询详情"""
    try:
        qid = payload.get('query_index') or payload.get('query_id')
        uid = payload.get('uid')
        
        if not qid:
            return 400, {'success': False, 'error': 'missing_query_index'}
        
        try:
            uid = int(uid) if uid else 0
        except (ValueError, TypeError):
            uid = 0
        
        # 从数据库获取查询信息
        from ..load_data.query_dao import get_query_log
        
        row = get_query_log(str(qid))
        if not row:
            return 404, {'success': False, 'error': 'query_not_found'}
        
        # 验证归属
        if uid > 0 and row.get('uid') != uid:
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
                'should_pause': bool(row.get('should_pause'))  # 修复10: 添加暂停状态字段
            }
        }
    except Exception as e:
        return 500, {'success': False, 'error': 'get_query_info_failed', 'message': str(e)}

