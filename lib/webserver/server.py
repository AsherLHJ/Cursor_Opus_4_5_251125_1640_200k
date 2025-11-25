import os
import json
import datetime
from decimal import Decimal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as HTTPServer
from urllib.parse import urlparse
from ..config import config_loader as config
from ..log import debug_console
from .auth import register_user, login_user, get_user_info
from ..load_data import db_reader
from ..process.paper_processor import process_papers, process_papers_for_distillation
from .admin_api import handle_admin_api

# 兼容旧代码
try:
    from ..process import queue_facade
except ImportError:
    queue_facade = None

LIB_DIR = os.path.dirname(os.path.dirname(__file__))
HTML_DIR = os.path.join(LIB_DIR, 'html')
STATIC_DIR = os.path.join(HTML_DIR, 'static')


def safe_join(base, *paths):
    final_path = os.path.normpath(os.path.join(base, *paths))
    if os.path.commonprefix([final_path, base]) != base:
        raise ValueError("Unsafe path")
    return final_path


class RequestHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # 处理 CORS 预检请求
        self.send_response(204)
        self._add_cors_headers()
        self.end_headers()
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/ping':
            return self._send_json(200, {'pong': True})
        
        # 新版管理员API (GET)
        if parsed.path.startswith('/api/admin/') and parsed.path not in ('/api/admin/tokens_per_req',):
            headers_dict = {k: v for k, v in self.headers.items()}
            status, response = handle_admin_api(parsed.path, 'GET', headers_dict, None)
            return self._send_json(status, response)
        # 获取 tokens_per_req（必须为 GET，且从数据库读取）
        if parsed.path == '/api/admin/tokens_per_req':
            try:
                v = int(db_reader.get_tokens_per_req(400))
                return self._send_json(200, {'success': True, 'tokens_per_req': v})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'get_tokens_per_req_failed', 'message': str(e)})
        # --- 管理接口 (GET) ---
        if parsed.path == '/admin/settings/worker_req_per_min':
            try:
                wrpm = int(db_reader.get_worker_req_per_min(default=120))
            except Exception:
                wrpm = 120
            return self._send_json(200, {'success': True, 'worker_req_per_min': wrpm})
        if parsed.path == '/admin/settings/auto_refresh_interval':
            # 页面自动刷新间隔（毫秒），存放于 app_settings.admin_auto_refresh_ms
            try:
                ms = int(db_reader.get_int_app_setting('admin_auto_refresh_ms', default=5000))
            except Exception:
                ms = 5000
            return self._send_json(200, {'success': True, 'auto_refresh_ms': ms})
        if parsed.path in ('/', '/index.html'):
            return self._serve_file(os.path.join(HTML_DIR, 'index.html'), 'text/html; charset=utf-8')
        if parsed.path == '/login.html':
            return self._serve_file(os.path.join(HTML_DIR, 'login.html'), 'text/html; charset=utf-8')
        if parsed.path == '/register.html':
            return self._serve_file(os.path.join(HTML_DIR, 'register.html'), 'text/html; charset=utf-8')
        if parsed.path == '/history.html':
            return self._serve_file(os.path.join(HTML_DIR, 'history.html'), 'text/html; charset=utf-8')
        if parsed.path == '/distill.html':
            return self._serve_file(os.path.join(HTML_DIR, 'distill.html'), 'text/html; charset=utf-8')
        if parsed.path == '/billing.html':
            return self._serve_file(os.path.join(HTML_DIR, 'billing.html'), 'text/html; charset=utf-8')
        # 新版管理员页面
        if parsed.path.startswith('/admin/'):
            admin_file = parsed.path[7:]  # 去掉 /admin/
            if not admin_file:
                admin_file = 'login.html'
            try:
                file_path = safe_join(HTML_DIR, 'admin', admin_file)
                if os.path.exists(file_path):
                    return self._serve_file(file_path, 'text/html; charset=utf-8')
            except ValueError:
                pass
            return self._send_text(404, 'text/plain', 'Not Found')
        
        # 兼容旧路径
        if parsed.path == '/admin.html':
            return self._send_redirect('/admin/login.html')
        if parsed.path == '/debugLog.html':
            if not getattr(config, 'enable_debug_website_console', False):
                return self._send_text(403, 'text/plain; charset=utf-8', 'Debug console disabled')
            return self._serve_file(os.path.join(HTML_DIR, 'debugLog.html'), 'text/html; charset=utf-8')
        if parsed.path == '/api/folders':
            folders = db_reader.get_subfolders()
            return self._send_json(200, {'folders': folders})
        # 已删除共享单 Key 并发开关接口：架构固定为共享池，无需任何动态切换；若前端仍请求旧路径返回 404
        if parsed.path == '/admin/settings/allow_shared_api_key':
            return self._send_json(404, {'success': False, 'error': 'deprecated_endpoint'})
        if parsed.path == '/api/debug-log':
            if not getattr(config, 'enable_debug_website_console', False):
                return self._send_json(403, {'success': False, 'error': 'debug_console_disabled'})
            log_path = debug_console.get_debug_log_path()
            if not log_path or not os.path.exists(log_path):
                return self._send_json(200, {'success': True, 'content': '', 'lines': 0, 'bytes': 0, 'truncated': False})
            try:
                max_bytes = 256 * 1024  # keep response manageable
                file_size = os.path.getsize(log_path)
                truncated = file_size > max_bytes
                with open(log_path, 'rb') as fh:
                    if truncated:
                        fh.seek(-max_bytes, os.SEEK_END)
                    else:
                        fh.seek(0)
                    content_bytes = fh.read()
                content = content_bytes.decode('utf-8', errors='replace')
                line_count = content.count('\n')
                if content and not content.endswith('\n'):
                    line_count += 1
                return self._send_json(200, {
                    'success': True,
                    'content': content,
                    'lines': line_count,
                    'bytes': len(content_bytes),
                    'truncated': truncated,
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'debug_log_read_failed', 'message': str(e)})
        if parsed.path == '/api/queue/stats':
            # 只读观测：队列与容量状态（无任何动态模式开关，架构固定）
            try:
                tpr = int(db_reader.get_tokens_per_req(400))
            except Exception:
                tpr = 400
            try:
                stats = queue_facade.backlog_stats()
            except Exception:
                stats = {'backlog': 0, 'active_uids': [], 'user_capacity_sum': 0}
            # 估算容量（保持兼容：effective_capacity_per_min 同义于系统最大容量）
            try:
                from ..process import rate_limiter_facade as rate_limiter
                eff = rate_limiter.calc_effective_capacity_per_min(tpr)
            except Exception:
                eff = {'accounts': 0, 'effective_req_per_min': 0}

            # 从 Redis 读取系统最大/已占用/剩余容量（篇/分钟）
            try:
                from ..process import redis_aggregates as ragg
                max_cap = float(ragg.get_max_capacity_per_min(0.0))
                occ_cap = float(ragg.get_occupied_capacity_per_min(0.0))
                rem_cap = float(ragg.get_remaining_capacity_per_min(0.0))
                run_perm_sum = int(ragg.get_running_perm_sum())
            except Exception:
                max_cap = float(eff.get('effective_req_per_min', 0) or 0)
                occ_cap = 0.0
                rem_cap = max_cap
                run_perm_sum = 0

            # Redis 配置与健康状态（配置与实际使用解耦）
            try:
                redis_queue_config = bool(getattr(config, 'USE_REDIS_QUEUE', False))
            except Exception:
                redis_queue_config = False
            try:
                from ..process import rate_limiter_facade as _rlf
                redis_rl_config = bool(getattr(config, 'USE_REDIS_RATELIMITER', False))
            except Exception:
                redis_rl_config = False
            try:
                redis_queue_ping = bool(queue_facade.redis_ping()) if redis_queue_config else False
            except Exception:
                redis_queue_ping = False
            try:
                redis_rl_ping = bool(rate_limiter.redis_ping()) if redis_rl_config else False
            except Exception:
                redis_rl_ping = False

            # RDS/MySQL 健康检测（端到端：尝试连接并执行 SELECT 1 与 VERSION()）
            db_ping = False
            db_version = ''
            try:
                conn = db_reader._get_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        _ = cursor.fetchone()
                        try:
                            cursor.execute("SELECT VERSION()")
                            row = cursor.fetchone()
                            if row:
                                db_version = str(row[0])
                        except Exception:
                            db_version = ''
                    db_ping = True
                finally:
                    conn.close()
            except Exception:
                db_ping = False

            return self._send_json(200, {
                'success': True,
                'backlog': stats.get('backlog', 0),
                'active_uids': stats.get('active_uids', []),
                'user_capacity_sum': stats.get('user_capacity_sum', 0),
                'effective_capacity_per_min': eff.get('effective_req_per_min', 0),
                'max_capacity_per_min': max_cap,
                'occupied_capacity_per_min': occ_cap,
                'remaining_capacity_per_min': rem_cap,
                'running_perm_sum': run_perm_sum,
                'accounts': eff.get('accounts', 0),
                'redis': {
                    'queue_enabled': redis_queue_config,
                    'ratelimiter_enabled': redis_rl_config,
                    'queue_ping': redis_queue_ping,
                    'ratelimiter_ping': redis_rl_ping
                },
                'db': {
                    'ping': db_ping,
                    'version': db_version
                }
            })
        if parsed.path == '/api/tags':
            # 获取标签数据（支持按当前筛选上下文过滤）
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or '')
                tag_type = (qs.get('type') or [''])[0]
                
                if not tag_type:
                    return self._send_json(400, {'success': False, 'error': 'missing_type'})
                
                # 可选：selected 传入 JSON 字符串，包含当前 selected_tags
                selected_raw = (qs.get('selected') or [''])[0]
                selected_tags = {}
                if selected_raw:
                    try:
                        selected_tags = json.loads(selected_raw)
                    except Exception:
                        selected_tags = {}

                if isinstance(selected_tags, dict) and any(selected_tags.get(k) for k in selected_tags.keys()):
                    tags = db_reader.get_tags_by_type_filtered(tag_type, selected_tags)
                else:
                    tags = db_reader.get_tags_by_type(tag_type)

                return self._send_json(200, {'success': True, 'tags': tags})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'get_tags_failed', 'message': str(e)})
        if parsed.path == '/api/admin/users':
            # 获取所有用户信息
            try:
                users = db_reader.get_all_users()
                return self._send_json(200, {'success': True, 'users': users})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'get_users_failed', 'message': str(e)})
        if parsed.path == '/api/admin/capacity':
            # 只读展示：账户配额与当前分钟使用量（Redis 优先，其次回退 MySQL）。
            # 不提供任何“分配/绑定/切换”语义，前端仅用于观测有效容量与各账号速率消耗。
            try:
                # 读取所有账户（包含 is_active=0）
                rows = []
                conn = db_reader._get_connection()
                try:
                    with conn.cursor(dictionary=True) as cursor:
                        try:
                            cursor.execute("SELECT api_index, COALESCE(api_name,'') AS api_name, COALESCE(is_active, up) AS is_active, COALESCE(rpm_limit,30000) AS rpm_limit, COALESCE(tpm_limit,5000000) AS tpm_limit FROM api_list ORDER BY api_index")
                        except Exception:
                            cursor.execute("SELECT api_index, COALESCE(api_name,'') AS api_name, up AS is_active FROM api_list ORDER BY api_index")
                        rows = cursor.fetchall() or []
                finally:
                    conn.close()

                # 当分钟用量
                try:
                    from ..process import rate_limiter_facade as rlf
                    use_redis = bool(rlf.redis_enabled())
                except Exception:
                    use_redis = False
                minute = datetime.datetime.utcnow().strftime('%Y%m%d%H%M')
                items = []
                for r in rows:
                    api_index = r.get('api_index')
                    api_name = r.get('api_name') or str(api_index)
                    rpm_limit = int(r.get('rpm_limit') or 30000)
                    tpm_limit = int(r.get('tpm_limit') or 5000000)
                    used_req = 0
                    used_tok = 0
                    if use_redis:
                        try:
                            from ..process import redis_rate_limiter as rrl
                            client = rrl._get_redis_client()  # type: ignore
                            if client is not None:
                                used_req = int(client.get(f"apw:rl:{api_name}:rpm:{minute}") or 0)
                                used_tok = int(client.get(f"apw:rl:{api_name}:tpm:{minute}") or 0)
                        except Exception:
                            used_req = 0
                            used_tok = 0
                    else:
                        try:
                            usage = db_reader.get_api_usage_minute(api_name, datetime.datetime.utcnow())
                            used_req = int(usage.get('used_req') or 0)
                            used_tok = int(usage.get('used_tokens') or 0)
                        except Exception:
                            used_req = 0
                            used_tok = 0
                    items.append({
                        'api_index': api_index,
                        'api_name': api_name,
                        'is_active': bool(r.get('is_active')),
                        'rpm_limit': rpm_limit,
                        'tpm_limit': tpm_limit,
                        'used_req': used_req,
                        'used_tokens': used_tok
                    })
                # 附带当前 tokens_per_req 与估算有效容量，便于前端展示
                try:
                    tpr = int(db_reader.get_tokens_per_req(400))
                except Exception:
                    tpr = 400
                try:
                    from ..process import rate_limiter_facade as rlf2
                    eff_cap = int(rlf2.calc_effective_capacity_per_min(tpr).get('effective_req_per_min', 0))
                except Exception:
                    eff_cap = 0
                # 读取 Redis 中的容量三元组
                try:
                    from ..process import redis_aggregates as ragg
                    max_cap = float(ragg.get_max_capacity_per_min(0.0))
                    occ_cap = float(ragg.get_occupied_capacity_per_min(0.0))
                    rem_cap = float(ragg.get_remaining_capacity_per_min(0.0))
                except Exception:
                    max_cap = float(eff_cap)
                    occ_cap = 0.0
                    rem_cap = max_cap
                return self._send_json(200, {
                    'success': True,
                    'accounts': items,              # 账号静态配额与本分钟使用
                    'redis_enabled': use_redis,     # 是否使用 Redis 统计
                    'tokens_per_req': tpr,          # 用于容量公式 min(sum(RPM), floor(sum(TPM)/tokens_per_req))
                    'effective_capacity_per_min': eff_cap,  # 兼容：最大容量
                    'max_capacity_per_min': max_cap,
                    'occupied_capacity_per_min': occ_cap,
                    'remaining_capacity_per_min': rem_cap
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'capacity_failed', 'message': str(e)})
        if parsed.path == '/api/registration_status':
            # 获取注册功能状态（优先从数据库共享设置读取，确保多容器一致）
            try:
                reg_enabled = db_reader.get_registration_enabled_db(default=True)
            except Exception:
                reg_enabled = True
            return self._send_json(200, {
                'success': True,
                'registration_enabled': bool(reg_enabled)
            })
        if parsed.path == '/api/admin/bcrypt_rounds':
            # 获取当前 bcrypt rounds 设置（来自 app_settings）
            try:
                rounds = db_reader.get_int_app_setting('bcrypt_rounds', default=12)
                # 统一对外返回限定范围（4-16），避免异常值
                if rounds < 4:
                    rounds = 4
                if rounds > 16:
                    rounds = 16
                return self._send_json(200, {'success': True, 'rounds': rounds})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'get_rounds_failed', 'message': str(e)})
        if parsed.path == '/api/query_history':
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or '')
                uid_raw = (qs.get('uid') or ['0'])[0]
                try:
                    uid = int(uid_raw)
                except Exception:
                    uid = 0
                if uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})


                logs = []
                try:
                    rows = db_reader.list_query_logs_by_uid(uid, limit=100)
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'db_error', 'message': str(e)})

                def fmt_time(v):
                    if v is None:
                        return None
                    if isinstance(v, datetime.datetime):
                        return v.strftime("%Y-%m-%d %H:%M:%S")
                    return str(v)

                for r in rows:
                    logs.append({
                        'query_index': r.get('query_index'),
                        'uid': r.get('uid'),
                        'query_time': fmt_time(r.get('query_time')),
                        'selected_folders': r.get('selected_folders') or '',
                        'year_range': r.get('year_range') or '',
                        'research_question': r.get('research_question') or '',
                        'requirements': r.get('requirements') or '',
                        'query_table': r.get('query_table') or '',
                        'start_time': fmt_time(r.get('start_time')),
                        'end_time': fmt_time(r.get('end_time')),
                        'completed': bool(r.get('end_time')),
                        'total_papers_count': r.get('total_papers_count') or 0,
                        'is_distillation': bool(r.get('is_distillation')),
                        'is_visible': bool(r.get('is_visible')),
                        'should_pause': bool(r.get('should_pause')),
                    })

                return self._send_json(200, {'success': True, 'logs': logs})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'history_failed', 'message': str(e)})
        if parsed.path == '/api/query_progress':
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or '')
                qid_raw = (qs.get('query_index') or ['0'])[0]
                try:
                    query_index = int(qid_raw)
                except Exception:
                    query_index = 0
                if query_index <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_query_index'})

                # 基于成本的进度计算
                stats = db_reader.compute_query_cost_progress(query_index)
                return self._send_json(200, {
                    'success': True,
                    'progress': stats.get('progress', 0.0),
                    'completed': stats.get('completed', False),
                    'total_cost': stats.get('total_cost', 0.0),
                    'actual_cost': stats.get('actual_cost', 0.0)
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'progress_failed', 'message': str(e)})
        
        if parsed.path == '/api/random_sentences':
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or '')
                count_raw = (qs.get('count') or ['10'])[0]
                try:
                    count = int(count_raw)
                except Exception:
                    count = 10
                
                # 获取随机句子
                sentences = db_reader.get_random_sentences(count)
                return self._send_json(200, {
                    'success': True,
                    'sentences': sentences
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'sentences_failed', 'message': str(e)})
        
        if parsed.path == '/api/get_query_info':
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or '')
                qid_raw = (qs.get('query_index') or ['0'])[0]
                uid_raw = (qs.get('uid') or ['0'])[0]
                
                try:
                    query_index = int(qid_raw)
                except Exception:
                    query_index = 0
                if query_index <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_query_index'})

                try:
                    uid = int(uid_raw)
                except Exception:
                    uid = 0
                if uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})

                # 获取查询信息
                try:
                    row = db_reader.get_query_log_by_index(query_index) or {}
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'db_error', 'message': str(e)})

                if not row:
                    return self._send_json(404, {'success': False, 'error': 'query_not_found'})

                # 验证查询记录是否属于当前用户
                if row.get('uid') != uid:
                    return self._send_json(403, {'success': False, 'error': 'access_denied'})

                def fmt_time(v):
                    if v is None:
                        return None
                    if isinstance(v, datetime.datetime):
                        return v.strftime("%Y-%m-%d %H:%M:%S")
                    return str(v)

                return self._send_json(200, {
                    'success': True,
                    'query_info': {
                        'query_index': row.get('query_index'),
                        'uid': row.get('uid'),
                        'query_time': fmt_time(row.get('query_time')),
                        'selected_folders': row.get('selected_folders') or '',
                        'year_range': row.get('year_range') or '',
                        'research_question': row.get('research_question') or '',
                        'requirements': row.get('requirements') or '',
                        'query_table': row.get('query_table') or '',
                        'start_time': fmt_time(row.get('start_time')),
                        'end_time': fmt_time(row.get('end_time')),
                        'completed': bool(row.get('end_time'))
                    }
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'get_query_info_failed', 'message': str(e)})
        if parsed.path == '/api/download_csv':
            try:
                from urllib.parse import parse_qs
                import io, csv
                qs = parse_qs(parsed.query or '')
                qid_raw = (qs.get('query_index') or ['0'])[0]
                try:
                    query_index = int(qid_raw)
                except Exception:
                    query_index = 0
                if query_index <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_query_index'})

                row = db_reader.get_query_log_by_index(query_index) or {}
                table_name = row.get('query_table') or ''
                if not table_name or not db_reader.check_search_table_exists(table_name):
                    return self._send_json(404, {'success': False, 'error': 'table_not_found'})

                results = db_reader.fetch_search_results_with_paperinfo(table_name, query_index) or []
                # 导出全部记录：优先输出“符合”，再输出“其他（不符/未判定）”
                relevant_rows = [r for r in results if r.get('search_result') in (1, True, '1')]
                other_rows = [r for r in results if r.get('search_result') not in (1, True, '1')]
                ordered_rows = relevant_rows + other_rows

                buf = io.StringIO()
                writer = csv.writer(buf)
                # 保持表头不变
                writer.writerow(['source', 'year', 'title', 'url', 'search_result', 'reason'])
                for r in ordered_rows:
                    search_result_value = r.get('search_result')
                    if search_result_value in (1, True, '1'):
                        search_result_display = '符合'
                    elif search_result_value in (0, False, '0'):
                        search_result_display = '不符'
                    else:
                        search_result_display = '未判定'
                    year = r.get('year') or ''
                    doi = r.get('doi') or ''
                    paper_url = (r.get('paper_url') or '').strip()
                    if paper_url:
                        url = paper_url
                    elif doi:
                        url = f"https://doi.org/{doi}"
                    else:
                        # 兜底：尝试从 bib 中提取
                        url = self._extract_url_from_bib(r.get('bib') or '')
                    writer.writerow([
                        r.get('source') or '',
                        year,
                        r.get('title') or '',
                        url,
                        search_result_display,
                        r.get('reason') or ''
                    ])
                
                # 仍用 UTF-8 BOM，便于 Excel
                csv_content = buf.getvalue()
                data = '\ufeff'.encode('utf-8') + csv_content.encode('utf-8')
                filename = f'Overall_{query_index}.csv'
                return self._send_bytes(200, 'text/csv; charset=utf-8', data, {
                    'Content-Disposition': f'attachment; filename="{filename}"'
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'csv_failed', 'message': str(e)})
        if parsed.path == '/api/download_bib':
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or '')
                qid_raw = (qs.get('query_index') or ['0'])[0]
                try:
                    query_index = int(qid_raw)
                except Exception:
                    query_index = 0
                if query_index <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_query_index'})

                row = db_reader.get_query_log_by_index(query_index) or {}
                table_name = row.get('query_table') or ''
                if not table_name or not db_reader.check_search_table_exists(table_name):
                    return self._send_json(404, {'success': False, 'error': 'table_not_found'})

                # 构建BIB文件表头
                query_time = row.get('query_time') or ''
                selected_folders = row.get('selected_folders') or ''
                year_range = row.get('year_range') or ''
                research_question = row.get('research_question') or ''
                requirements = row.get('requirements') or ''
                
                header_lines = []
                if query_time or selected_folders or year_range or research_question or requirements:
                    header_lines.append(f"% Query Time: {query_time}")
                    header_lines.append(f"% Selected Folders: {selected_folders}")
                    header_lines.append(f"% Year Range: {year_range}")
                    header_lines.append(f"% Research Question: {research_question}")
                    if requirements:
                        header_lines.append(f"% Requirements: {requirements}")
                    header_lines.append(f"\n% Search Topic {{{research_question}}}\n")

                results = db_reader.fetch_search_results_with_paperinfo(table_name, query_index) or []
                # 仅导出已处理记录且search_result=1的记录，且有bib内容
                entries = []
                for r in results:
                    if r.get('search_result') in (1, True, '1'):
                        bib = (r.get('bib') or '').strip()
                        if bib:
                            entries.append(bib)
                
                # 组合表头和条目
                content_parts = []
                if header_lines:
                    content_parts.extend(header_lines)
                if entries:
                    content_parts.append("\n\n".join(entries))
                
                data = "\n".join(content_parts).encode('utf-8')
                filename = f'Result_{query_index}.bib'
                return self._send_bytes(200, 'application/x-bibtex; charset=utf-8', data, {
                    'Content-Disposition': f'attachment; filename="{filename}"'
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'bib_failed', 'message': str(e)})

        if parsed.path.startswith('/static/'):
            rel = parsed.path[len('/static/'):]
            try:
                file_path = safe_join(STATIC_DIR, rel)
            except Exception:
                return self._send_text(403, 'text/plain; charset=utf-8', 'Forbidden')
            mime = 'text/plain'
            if file_path.endswith('.css'):
                mime = 'text/css; charset=utf-8'
            elif file_path.endswith('.js'):
                mime = 'application/javascript; charset=utf-8'
            elif file_path.endswith('.html'):
                mime = 'text/html; charset=utf-8'
            return self._serve_file(file_path, mime)
        # 未匹配的 GET 请求返回 404
        # 新增：获取用户信息（余额）
        if parsed.path == '/api/billing':
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or '')
                uid_raw = (qs.get('uid') or ['0'])[0]
                try:
                    uid = int(uid_raw)
                except Exception:
                    uid = 0
                if uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})

                # 获取该用户的账单记录（只显示actual_cost不为0的记录）
                try:
                    records = db_reader.get_billing_records_by_uid(uid)
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'db_error', 'message': str(e)})

                def fmt_time(v):
                    if v is None:
                        return None
                    if isinstance(v, datetime.datetime):
                        return v.strftime("%Y-%m-%d %H:%M:%S")
                    return str(v)

                billing_records = []
                for r in records:
                    billing_records.append({
                        'query_index': r.get('query_index'),
                        'query_time': fmt_time(r.get('query_time')),
                        'is_distillation': bool(r.get('is_distillation')),
                        'total_papers_count': r.get('total_papers_count') or 0,
                        'actual_cost': float(r.get('actual_cost') or 0)
                    })

                return self._send_json(200, {'success': True, 'records': billing_records})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'billing_failed', 'message': str(e)})
        
        if parsed.path == '/api/user_info':
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or '')
                uid_raw = (qs.get('uid') or ['0'])[0]
                try:
                    uid = int(uid_raw)
                except Exception:
                    uid = 0
                if uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})
                result = get_user_info(uid)
                return self._send_json(200, result)
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'user_info_failed', 'message': str(e)})

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length > 0 else ''
        
        # 新版管理员API
        if parsed.path.startswith('/api/admin/'):
            headers_dict = {k: v for k, v in self.headers.items()}
            status, response = handle_admin_api(parsed.path, 'POST', headers_dict, body)
            return self._send_json(status, response)
        
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            return self._send_json(400, {'error': 'invalid_json'})

        if parsed.path == '/api/register':
            # 检查注册功能是否开启（从数据库读取，保证多容器一致）
            try:
                reg_enabled = db_reader.get_registration_enabled_db(default=True)
            except Exception:
                reg_enabled = True
            if not reg_enabled:
                return self._send_json(403, {
                    'success': False, 
                    'message': '注册功能暂时关闭，请联系管理员',
                    'error': 'registration_disabled'
                })
            
            username = str(payload.get('username', '')).strip()
            password = str(payload.get('password', '')).strip()
            result = register_user(username, password)
            return self._send_json(200, result)
        
        if parsed.path == '/api/login':
            username = str(payload.get('username', '')).strip()
            password = str(payload.get('password', '')).strip()
            result = login_user(username, password)
            return self._send_json(200, result)

        if parsed.path == '/api/update':
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

            # 支持新的期刊选择方式和旧的文件夹选择方式
            selected_journals = payload.get('selected_journals')
            selected_folders = payload.get('selected_folders')
            
            if selected_journals is not None:
                # 新的期刊选择方式
                if not isinstance(selected_journals, list):
                    selected_journals = []
                selected_items = selected_journals
            else:
                # 旧的文件夹选择方式（向后兼容）
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

            # 返回"已选择文章数"和"预计花费点数"
            try:
                if selected_journals is not None:
                    # 使用新的统计方法
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
                    
                    # 计算预计花费
                    try:
                        from ..price_calculate import PriceCalculator
                        calculator = PriceCalculator()
                        
                        # 获取每个期刊的论文数量
                        paper_counts = db_reader.count_papers_by_journals(selected_journals, time_range)
                        
                        # 计算总花费
                        cost_info = calculator.calculate_total_cost(selected_journals, paper_counts)
                        estimated_cost = cost_info["total_cost"]
                        
                        calculator.close()
                    except Exception as e:
                        print(f"计算预计花费失败: {e}")
                        estimated_cost = 0
                else:
                    # 使用旧的统计方法（向后兼容）
                    count = db_reader.count_papers(selected_folders, include_all_years, start_year, end_year)
                    estimated_cost = count  # 旧方法默认每篇1点
            except Exception:
                count = 0
                estimated_cost = 0

            return self._send_json(200, {'selected_count': count, 'estimated_cost': estimated_cost})
        if parsed.path == '/api/start_search':
            # 接收参数并创建带uid的查询日志，然后启动后台检索线程
            try:
                question = str(payload.get('question') or '').strip()
                requirements = str(payload.get('requirements') or '').strip()
                include_all_years = bool(payload.get('include_all_years'))

                # 校验三条件：研究问题、年份范围（或全选）、已选择数据源
                if not question:
                    return self._send_json(400, {'success': False, 'error': 'missing_question'})

                start_year_val = payload.get('start_year')
                end_year_val = payload.get('end_year')
                # 解析并校验年份
                if not include_all_years:
                    def _valid_year(v):
                        try:
                            s = str(v).strip()
                            return len(s) == 4 and s.isdigit()
                        except Exception:
                            return False
                    if not _valid_year(start_year_val) or not _valid_year(end_year_val):
                        return self._send_json(400, {'success': False, 'error': 'invalid_year'})
                    try:
                        start_year = int(str(start_year_val).strip())
                        end_year = int(str(end_year_val).strip())
                    except Exception:
                        return self._send_json(400, {'success': False, 'error': 'invalid_year'})
                    if end_year < start_year:
                        return self._send_json(400, {'success': False, 'error': 'invalid_year_order'})
                else:
                    # 使用配置的默认值以供后续保存
                    start_year = config.YEAR_RANGE_START
                    end_year = config.YEAR_RANGE_END

                selected_journals = payload.get('selected_journals')
                selected_folders = payload.get('selected_folders')
                
                if selected_journals is not None:
                    # 新的期刊选择方式
                    if not isinstance(selected_journals, list):
                        selected_journals = []
                    selected_items = selected_journals
                    if not selected_journals:
                        return self._send_json(400, {'success': False, 'error': 'no_selected_journals'})
                else:
                    # 旧的文件夹选择方式（向后兼容）
                    selected_folders = selected_folders or []
                    if not isinstance(selected_folders, list):
                        selected_folders = []
                    selected_items = selected_folders
                    if not selected_folders:
                        return self._send_json(400, {'success': False, 'error': 'no_selected_folders'})
                    return self._send_json(400, {'success': False, 'error': 'no_selected_folders'})

                uid_raw = payload.get('uid')
                try:
                    uid = int(uid_raw)
                except Exception:
                    uid = 0
                if uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})

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

                # 日志字段
                query_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                folder_info = ", ".join(selected_items)  # 使用统一的selected_items
                year_range = "ALL" if include_all_years else f"{start_year}-{end_year}"

                # 准备今日搜索表
                today_table = db_reader.get_search_table_name()
                try:
                    if not db_reader.check_search_table_exists(today_table):
                        db_reader.create_search_table(today_table)
                except Exception:
                    pass

                # 计算文献总数和预计花费
                try:
                    if selected_journals is not None:
                        # 新的期刊选择方式
                        if not include_all_years:
                            time_range = {
                                "start_year": start_year,
                                "end_year": end_year,
                                "include_all": False
                            }
                        else:
                            time_range = {"include_all": True}
                        total_papers_count = db_reader.count_papers_by_filters(selected_journals, time_range)
                        
                        # 计算预计花费
                        from ..price_calculate import PriceCalculator
                        calculator = PriceCalculator()
                        
                        # 获取每个期刊的论文数量
                        paper_counts = db_reader.count_papers_by_journals(selected_journals, time_range)
                        
                        # 计算总花费
                        cost_info = calculator.calculate_total_cost(selected_journals, paper_counts)
                        estimated_cost = cost_info["total_cost"]
                        
                        # 检查用户余额是否充足
                        user_balance = calculator.get_user_balance(uid)
                        if user_balance < estimated_cost:
                            calculator.close()
                            return self._send_json(400, {
                                'success': False, 
                                'error': 'insufficient_balance',
                                'message': f'余额不足，需要 {estimated_cost} 检索点，当前余额 {user_balance} 检索点'
                            })
                        
                        calculator.close()
                    else:
                        # 使用旧的统计方法（向后兼容）
                        total_papers_count = db_reader.count_papers(selected_folders, include_all_years, start_year, end_year)
                        estimated_cost = total_papers_count  # 旧方法默认每篇1点
                        
                        # 检查用户余额
                        from ..price_calculate import PriceCalculator
                        calculator = PriceCalculator()
                        user_balance = calculator.get_user_balance(uid)
                        if user_balance < estimated_cost:
                            calculator.close()
                            return self._send_json(400, {
                                'success': False, 
                                'error': 'insufficient_balance',
                                'message': f'余额不足，需要 {estimated_cost} 检索点，当前余额 {user_balance} 检索点'
                            })
                        calculator.close()
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'cost_calculation_failed', 'message': str(e)})

                # 插入一条记录（带uid和total_cost）；query_log 结构由外部管理
                try:
                    # 确保数据库表结构支持价格功能
                    db_reader.ensure_price_columns()
                    
                    query_index = db_reader.insert_searching_log(
                        query_time=query_time,
                        selected_folders=folder_info,
                        year_range=year_range,
                        research_question=question,
                        requirements=requirements,
                        query_table=today_table,
                        uid=uid,
                        total_papers_count=total_papers_count,
                        is_distillation=False,
                        is_visible=True,
                        total_cost=estimated_cost
                    )
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'log_insert_failed', 'message': str(e)})

                # 启动后台检索线程（传入uid与复用的query_index）
                def _run_processing():
                    try:
                        year_range_info = "包含所有年份" if include_all_years else f"{start_year}-{end_year}"
                        process_papers(
                            question,
                            requirements,
                            -1,
                            selected_items,  # 使用统一的selected_items
                            year_range_info,
                            uid=uid,
                            query_index=query_index
                        )
                    except Exception as e:
                        # 打印异常，避免静默失败
                        import traceback
                        traceback.print_exc()
                        print(f"后台检索异常: {e}")
                        # 确保异常时也更新查询状态
                        try:
                            db_reader.mark_searching_log_completed(query_index)
                        except Exception:
                            pass

                threading.Thread(target=_run_processing, daemon=True).start()

                # 立即返回响应，不等待处理完成
                return self._send_json(200, {
                    'success': True,
                    'query_index': query_index,
                    'query_table': today_table,
                    'article_count': total_papers_count,
                    'estimated_cost': estimated_cost,
                    'message': 'Query submitted successfully. Processing in background.'
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'start_search_failed', 'message': str(e)})

        if parsed.path == '/api/start_distillation':
            # 蒸馏API：基于原始查询的相关论文进行二次筛选
            try:
                from ..process.paper_processor import process_papers_for_distillation

                question = str(payload.get('question') or '').strip()
                requirements = str(payload.get('requirements') or '').strip()
                original_query_index_raw = payload.get('original_query_index')
                
                try:
                    original_query_index = int(original_query_index_raw)
                except Exception:
                    original_query_index = 0
                if original_query_index <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_original_query_index'})

                uid_raw = payload.get('uid')
                try:
                    uid = int(uid_raw)
                except Exception:
                    uid = 0
                if uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})

                # 获取原始查询信息
                try:
                    original_query = db_reader.get_query_log_by_index(original_query_index) or {}
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'get_original_query_failed', 'message': str(e)})

                if not original_query:
                    return self._send_json(404, {'success': False, 'error': 'original_query_not_found'})

                # 验证原始查询记录是否属于当前用户
                if original_query.get('uid') != uid:
                    return self._send_json(403, {'success': False, 'error': 'access_denied'})

                # 获取原始查询的相关DOI列表
                try:
                    relevant_dois = db_reader.get_relevant_dois_from_query(original_query_index)
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'get_relevant_dois_failed', 'message': str(e)})

                if not relevant_dois:
                    return self._send_json(400, {'success': False, 'error': 'no_relevant_papers'})

                # 准备查询时间和表名
                query_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # selected_folders列：存储被蒸馏的原始查询的研究问题和研究要求
                original_research_question = original_query.get('research_question', '')
                original_requirements = original_query.get('requirements', '')
                if original_requirements:
                    folder_info = f"{original_research_question} | {original_requirements}"
                else:
                    folder_info = original_research_question
                
                # year_range列：存储被蒸馏的原始查询的查询时间
                original_query_time = original_query.get('query_time', '')
                if original_query_time:
                    # 如果是datetime对象，转换为字符串
                    if hasattr(original_query_time, 'strftime'):
                        year_range = original_query_time.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        year_range = str(original_query_time)
                else:
                    year_range = "Unknown Time"

                # 准备今日搜索表
                today_table = db_reader.get_search_table_name()
                try:
                    if not db_reader.check_search_table_exists(today_table):
                        db_reader.create_search_table(today_table)
                except Exception:
                    pass

                # 计算蒸馏预计费用：基价*0.1，一位小数
                try:
                    db_reader.ensure_price_columns()  # 确保 total_cost 列存在并为 DECIMAL(10,1)
                except Exception:
                    pass
                try:
                    price_map = db_reader.get_prices_by_dois(relevant_dois)
                    total_cost = 0.0
                    for doi in relevant_dois:
                        base = float(price_map.get(doi, 1.0))
                        total_cost += base * 0.1
                    estimated_cost = round(total_cost, 1)
                except Exception:
                    estimated_cost = 0.0

                # 插入一条蒸馏记录（带 total_cost）；query_log 结构由外部管理
                try:
                    query_index = db_reader.insert_searching_log(
                        query_time=query_time,
                        selected_folders=folder_info,  # 原始查询的研究问题+要求
                        year_range=year_range,         # 原始查询的查询时间
                        research_question=question,    # 新的蒸馏研究问题
                        requirements=requirements,     # 新的蒸馏研究要求
                        query_table=today_table,
                        uid=uid,
                        total_papers_count=len(relevant_dois),  # 蒸馏的文献数量
                        is_distillation=True,
                        is_visible=True,
                        total_cost=estimated_cost
                    )
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'log_insert_failed', 'message': str(e)})

                # 启动后台蒸馏线程
                def _run_distillation():
                    try:
                        process_papers_for_distillation(
                            question,
                            requirements,
                            relevant_dois,
                            uid=uid,
                            query_index=query_index,
                            original_query_index=original_query_index
                        )
                    except Exception as e:
                        print(f"蒸馏处理异常: {e}")
                        try:
                            db_reader.mark_searching_log_completed(query_index)
                        except Exception:
                            pass

                threading.Thread(target=_run_distillation, daemon=True).start()

                return self._send_json(200, {
                    'success': True,
                    'query_index': query_index,
                    'query_table': today_table
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'start_distillation_failed', 'message': str(e)})

        if parsed.path == '/api/estimate_distillation_cost':
            try:
                uid_raw = payload.get('uid')
                original_query_index_raw = payload.get('original_query_index')
                try:
                    uid = int(uid_raw)
                except Exception:
                    uid = 0
                try:
                    original_query_index = int(original_query_index_raw)
                except Exception:
                    original_query_index = 0
                if uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})
                if original_query_index <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_original_query_index'})

                # 校验原始查询归属
                try:
                    original_query = db_reader.get_query_log_by_index(original_query_index) or {}
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'get_original_query_failed', 'message': str(e)})
                if not original_query:
                    return self._send_json(404, {'success': False, 'error': 'original_query_not_found'})
                if original_query.get('uid') != uid:
                    return self._send_json(403, {'success': False, 'error': 'access_denied'})

                # 获取相关DOI
                try:
                    relevant_dois = db_reader.get_relevant_dois_from_query(original_query_index) or []
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'get_relevant_dois_failed', 'message': str(e)})
                if not relevant_dois:
                    # 返回余额
                    try:
                        from ..price_calculate import PriceCalculator
                        calculator = PriceCalculator()
                        user_balance = float(calculator.get_user_balance(uid))
                        calculator.close()
                    except Exception:
                        user_balance = 0.0
                    return self._send_json(200, {'success': True, 'doi_count': 0, 'estimated_cost': 0.0, 'user_balance': user_balance, 'insufficient': False})

                # 直接按 DOI JOIN 取价格
                try:
                    price_map = db_reader.get_prices_by_dois(relevant_dois) or {}
                except Exception:
                    price_map = {}

                # 计算蒸馏费用：基价*0.1，合并为一位小数
                total_cost = 0.0
                for doi in relevant_dois:
                    base = float(price_map.get(doi, 1.0))
                    total_cost += base * 0.1
                estimated_cost = round(total_cost, 1)

                # 返回用户余额
                try:
                    from ..price_calculate import PriceCalculator
                    calculator = PriceCalculator()
                    user_balance = float(calculator.get_user_balance(uid))
                    calculator.close()
                except Exception:
                    user_balance = 0.0

                return self._send_json(200, {
                    'success': True,
                    'doi_count': len(relevant_dois),
                    'estimated_cost': estimated_cost,
                    'user_balance': user_balance,
                    'insufficient': user_balance < estimated_cost
                })
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'estimate_distillation_failed', 'message': str(e)})

        if parsed.path == '/api/admin/update_balance':
            # 管理员更新用户余额
            try:
                uid = payload.get('uid')
                balance = payload.get('balance')
                
                if not isinstance(uid, int) or uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})
                
                if not isinstance(balance, (int, float)) or balance < 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_balance'})
                
                success = db_reader.update_user_balance(uid, float(balance))
                if success:
                    return self._send_json(200, {'success': True})
                else:
                    return self._send_json(404, {'success': False, 'error': 'user_not_found'})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'update_balance_failed', 'message': str(e)})

        if parsed.path == '/api/admin/update_permission':
            # 管理员更新用户权限
            try:
                uid = payload.get('uid')
                permission = payload.get('permission')
                
                if not isinstance(uid, int) or uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_uid'})
                
                if not isinstance(permission, int) or permission < 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_permission'})
                
                success = db_reader.update_user_permission(uid, permission)
                if success:
                    return self._send_json(200, {'success': True})
                else:
                    return self._send_json(404, {'success': False, 'error': 'user_not_found'})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'update_permission_failed', 'message': str(e)})

        if parsed.path == '/api/admin/account-toggle':
            # 管理员切换 API 账户启用状态（is_active 或回退为 up）
            try:
                api_index = payload.get('api_index')
                enabled = payload.get('enabled')
                if not isinstance(api_index, int) or api_index <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_api_index'})
                if enabled is None:
                    return self._send_json(400, {'success': False, 'error': 'missing_enabled'})
                enabled_val = 1 if bool(enabled) else 0
                conn = db_reader._get_connection()
                try:
                    with conn.cursor() as cursor:
                        try:
                            cursor.execute("UPDATE api_list SET is_active=%s WHERE api_index=%s", (enabled_val, api_index))
                        except Exception:
                            # 回退：旧结构仅有 up 字段
                            cursor.execute("UPDATE api_list SET up=%s WHERE api_index=%s", (enabled_val, api_index))
                    conn.commit()
                finally:
                    conn.close()
                return self._send_json(200, {'success': True})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'account_toggle_failed', 'message': str(e)})

        if parsed.path == '/api/journals':
            # 根据过滤条件获取期刊/会议列表（忽略时间范围）
            try:
                selected_tags = payload.get('selected_tags', {})
                if not isinstance(selected_tags, dict):
                    selected_tags = {}

                # 强制忽略时间范围，不让其影响第二列数据库选择
                db_time_range = {"include_all": True}

                journals = db_reader.get_journals_by_filters(db_time_range, selected_tags)
                return self._send_json(200, {'journals': journals})
            except Exception as e:
                return self._send_json(500, {'error': 'get_journals_failed', 'message': str(e)})

        if parsed.path == '/api/count_papers':
            # 统计选定期刊/会议的论文数量
            try:
                selected_journals = payload.get('selected_journals', [])
                start_year = payload.get('start_year')
                end_year = payload.get('end_year')
                
                # 验证期刊列表参数
                if not isinstance(selected_journals, list):
                    selected_journals = []
                
                # 验证年份参数
                if start_year is not None:
                    try:
                        start_year = int(start_year)
                    except (ValueError, TypeError):
                        return self._send_json(400, {'error': 'invalid_start_year'})
                
                if end_year is not None:
                    try:
                        end_year = int(end_year)
                    except (ValueError, TypeError):
                        return self._send_json(400, {'error': 'invalid_end_year'})
                
                # 构建时间范围参数
                time_range = None
                if start_year is not None and end_year is not None:
                    time_range = {
                        "start_year": start_year,
                        "end_year": end_year,
                        "include_all": False
                    }
                else:
                    time_range = {"include_all": True}
                
                # 统计论文数量
                count = db_reader.count_papers_by_filters(selected_journals, time_range)
                
                return self._send_json(200, {'count': count})
            except Exception as e:
                return self._send_json(500, {'error': 'count_papers_failed', 'message': str(e)})

        if parsed.path == '/api/delete_history':
            try:
                query_index = payload.get('query_index')
                uid = payload.get('uid')
                hard = payload.get('hard', True)
                
                # 参数验证
                if not query_index or not uid:
                    return self._send_json(400, {'success': False, 'error': 'missing_parameters'})
                
                try:
                    query_index = int(query_index)
                    uid = int(uid)
                except (ValueError, TypeError):
                    return self._send_json(400, {'success': False, 'error': 'invalid_parameters'})
                
                if query_index <= 0 or uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_parameters'})
                
                # 根据参数选择隐藏或硬删除
                perform_hard = bool(hard)
                if perform_hard:
                    success = db_reader.delete_query_log(query_index, uid)
                else:
                    success = db_reader.hide_query_log(query_index, uid)
                
                if success:
                    return self._send_json(200, {'success': True, 'message': 'history_deleted', 'hard': perform_hard})
                else:
                    return self._send_json(404, {'success': False, 'error': 'record_not_found'})
                    
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'delete_failed', 'message': str(e)})

        if parsed.path == '/api/update_pause_status':
            try:
                query_index = payload.get('query_index')
                uid = payload.get('uid')
                should_pause = payload.get('should_pause')
                
                # 参数验证
                if query_index is None or uid is None or should_pause is None:
                    return self._send_json(400, {'success': False, 'error': 'missing_parameters'})
                
                try:
                    query_index = int(query_index)
                    uid = int(uid)
                    should_pause = bool(should_pause)
                except (ValueError, TypeError):
                    return self._send_json(400, {'success': False, 'error': 'invalid_parameters'})
                
                if query_index <= 0 or uid <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_parameters'})
                
                # 调用数据库函数更新暂停状态
                success = db_reader.update_query_pause_status(query_index, uid, should_pause)
                
                if success:
                    return self._send_json(200, {'success': True, 'message': 'pause_status_updated'})
                else:
                    return self._send_json(404, {'success': False, 'error': 'record_not_found'})
                    
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'update_failed', 'message': str(e)})

        if parsed.path == '/api/admin/toggle_registration':
            # 管理员切换注册功能开关（仅写入数据库，所有容器即时生效）
            try:
                enabled = payload.get('enabled')
                if enabled is None:
                    return self._send_json(400, {'success': False, 'error': 'missing_enabled_parameter'})

                enabled = bool(enabled)

                # 写入数据库共享设置
                try:
                    db_reader.set_registration_enabled_db(enabled)
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'save_db_failed', 'message': str(e)})

                return self._send_json(200, {
                    'success': True,
                    'message': f'注册功能已{"开启" if enabled else "关闭"}',
                    'registration_enabled': enabled
                })

            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'toggle_failed', 'message': str(e)})

        if parsed.path == '/api/admin/set_bcrypt_rounds':
            # 设置 bcrypt rounds（写 app_settings），仅影响之后新生成的密码哈希
            try:
                val = payload.get('rounds')
                try:
                    rounds = int(val)
                except Exception:
                    return self._send_json(400, {'success': False, 'error': 'invalid_rounds'})
                # 合理范围保护
                if rounds < 4:
                    rounds = 4
                if rounds > 16:
                    rounds = 16
                try:
                    db_reader.set_app_setting('bcrypt_rounds', str(rounds))
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'save_db_failed', 'message': str(e)})
                return self._send_json(200, {'success': True, 'rounds': rounds, 'message': 'bcrypt rounds 已更新'})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'set_rounds_failed', 'message': str(e)})

        # ============ 新增：容量模型相关管理接口 ============
        if parsed.path == '/api/admin/tokens_per_req':
            # 获取单篇文献 token 总消耗（来自 app_settings）
            try:
                v = int(db_reader.get_tokens_per_req(400))
                return self._send_json(200, {'success': True, 'tokens_per_req': v})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'get_tokens_per_req_failed', 'message': str(e)})

        if parsed.path == '/api/admin/set_tokens_per_req':
            # 设置单篇文献 token 总消耗（写 app_settings）
            try:
                v = int(payload.get('tokens_per_req'))
                if v <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_tokens_per_req'})
                ok = db_reader.set_tokens_per_req(v)
                if not ok:
                    return self._send_json(500, {'success': False, 'error': 'save_failed'})
                return self._send_json(200, {'success': True, 'tokens_per_req': v})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'set_tokens_per_req_failed', 'message': str(e)})

        # --- 管理接口 (POST) ---
        if parsed.path == '/admin/settings/worker_req_per_min':
            try:
                val_raw = payload.get('worker_req_per_min')
                if val_raw is None:
                    return self._send_json(400, {'success': False, 'error': 'missing_worker_req_per_min'})
                try:
                    wrpm = int(val_raw)
                except Exception:
                    return self._send_json(400, {'success': False, 'error': 'invalid_worker_req_per_min'})
                if wrpm <= 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_worker_req_per_min'})
                try:
                    db_reader.set_app_setting('worker_req_per_min', str(wrpm))
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'db_update_failed', 'message': str(e)})
                return self._send_json(200, {'success': True, 'worker_req_per_min': wrpm})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'update_failed', 'message': str(e)})

        if parsed.path == '/admin/settings/auto_refresh_interval':
            # 设置管理员页面自动刷新间隔（毫秒）
            try:
                val_raw = payload.get('auto_refresh_ms')
                if val_raw is None:
                    return self._send_json(400, {'success': False, 'error': 'missing_auto_refresh_ms'})
                try:
                    ms = int(val_raw)
                except Exception:
                    return self._send_json(400, {'success': False, 'error': 'invalid_auto_refresh_ms'})
                if ms < 1000:
                    ms = 1000  # 最小 1 秒
                if ms > 60000:
                    ms = 60000  # 最大 60 秒
                try:
                    db_reader.set_app_setting('admin_auto_refresh_ms', str(ms))
                except Exception as e:
                    return self._send_json(500, {'success': False, 'error': 'db_update_failed', 'message': str(e)})
                return self._send_json(200, {'success': True, 'auto_refresh_ms': ms})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'update_failed', 'message': str(e)})

        if parsed.path == '/api/admin/update_api_limits':
            # 更新某个 API 账户的 rpm/tpm 限额
            try:
                api_index = int(payload.get('api_index'))
                rpm_limit = int(payload.get('rpm_limit'))
                tpm_limit = int(payload.get('tpm_limit'))
                if api_index <= 0 or rpm_limit < 0 or tpm_limit < 0:
                    return self._send_json(400, {'success': False, 'error': 'invalid_parameters'})
                ok = db_reader.update_api_limits(api_index, rpm_limit, tpm_limit)
                if not ok:
                    return self._send_json(500, {'success': False, 'error': 'update_limits_failed'})
                return self._send_json(200, {'success': True})
            except Exception as e:
                return self._send_json(500, {'success': False, 'error': 'update_limits_failed', 'message': str(e)})

        # 已移除：共享单 Key 并发开关（POST）
        if parsed.path == '/admin/settings/allow_shared_api_key':
            return self._send_json(404, {'success': False, 'error': 'deprecated_endpoint'})

        return self._send_json(404, {'error': 'not_found'})

    def log_message(self, format, *args):
        return  # 静默日志

    def _serve_file(self, path, content_type):
        try:
            with open(path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self._add_cors_headers()
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self._send_text(404, 'text/plain; charset=utf-8', 'Not Found')

    def _send_text(self, status, content_type, text):
        data = text.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self._add_cors_headers()
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # 自定义 JSON 编码器，支持 Decimal、datetime
    class _EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            try:
                if isinstance(o, Decimal):
                    return float(o)
                if isinstance(o, (datetime.datetime, datetime.date)):
                    return o.isoformat()
            except Exception:
                pass
            return super().default(o)

    # 恢复为纯粹的JSON写回方法（使用增强编码器）
    def _send_json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False, cls=self._EnhancedJSONEncoder).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._add_cors_headers()
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _extract_url_from_bib(self, bib_text):
        """从BIB条目中提取URL"""
        if not bib_text:
            return ''
        
        import re
        # 查找url字段
        url_match = re.search(r'url\s*=\s*[{"]([^}"]+)[}"]', bib_text, re.IGNORECASE)
        if url_match:
            return url_match.group(1)
        
        # 查找doi字段并构造URL
        doi_match = re.search(r'doi\s*=\s*[{"]([^}"]+)[}"]', bib_text, re.IGNORECASE)
        if doi_match:
            return f"https://doi.org/{doi_match.group(1)}"
        
        return ''

    def _send_bytes(self, status, content_type, data, extra_headers=None):
        # 通用二进制返回（用于文件下载）
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self._add_cors_headers()
        self.send_header('Content-Length', str(len(data)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(str(k), str(v))
        self.end_headers()
        self.wfile.write(data)

    def _add_cors_headers(self):
        # 允许跨源访问（前端与后端分离部署时使用）
        allow_origin = os.getenv('CORS_ALLOW_ORIGIN', '*')
        self.send_header('Access-Control-Allow-Origin', allow_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

def run_server(host='127.0.0.1', port=8080):
    """
    启动HTTP服务
    """
    try:
        # 启动后台调度器
        try:
            from ..process.paper_processor import start_background_scheduler
            start_background_scheduler()
        except Exception:
            pass
        # 启动HTTP服务器
        httpd = HTTPServer((host, port), RequestHandler)
        # 确保线程以守护模式运行，减少退出阻塞
        try:
            httpd.daemon_threads = True
        except Exception:
            pass
        print(f"WebServer running at http://{host}:{port}/")
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass
