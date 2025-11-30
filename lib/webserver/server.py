"""
Web Server 主模块 (新架构)

职责:
- HTTP 请求路由分发
- 调用各 API 模块处理请求
- 静态文件服务
"""

import os
import json
import datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as HTTPServer
from urllib.parse import urlparse, parse_qs

from ..config import config_loader as config
from ..log import debug_console
from ..load_data import system_settings_dao

# API 处理模块
from .user_api import handle_user_api
from .query_api import handle_query_api
from .system_api import handle_system_api
from .admin_api import handle_admin_api
from .static_handler import serve_static_file, HTML_DIR, STATIC_DIR, safe_join


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(204)
        self._add_cors_headers()
        self.end_headers()

    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query or '')
        
        # 将 query_params 转换为简单字典
        payload = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
        headers_dict = {k: v for k, v in self.headers.items()}
        
        # ============================================================
        # API 路由
        # ============================================================
        
        # 系统 API
        if path == '/api/ping':
            return self._send_json(200, {'pong': True})
        
        if path in ('/api/system_status', '/api/debug-log', '/api/registration_status'):
            status, response = handle_system_api(path, 'GET', headers_dict, payload)
            return self._send_json(status, response)
        
        # 管理员 API
        if path.startswith('/api/admin/'):
            status, response = handle_admin_api(path, 'GET', headers_dict, payload)
            return self._send_json(status, response)
        
        # 用户 API
        if path in ('/api/user_info', '/api/user_balance', '/api/user_history', '/api/billing'):
            status, response = handle_user_api(path, 'GET', headers_dict, payload)
            return self._send_json(status, response)
        
        # 查询 API
        if path in ('/api/query_history', '/api/query_progress', '/api/query_status',
                    '/api/tags', '/api/journals', '/api/get_query_info',
                    '/api/download_csv', '/api/download_bib'):
            # 旧版下载接口需要特殊处理（同步等待模式，兼容保留）
            if path in ('/api/download_csv', '/api/download_bib'):
                return self._handle_download(path, payload)
            status, response = handle_query_api(path, 'GET', headers_dict, payload)
            return self._send_json(status, response)
        
        # 新版下载 API（异步队列模式）
        if path == '/api/download/status':
            return self._handle_download_status(payload)
        if path == '/api/download/file':
            return self._handle_download_file(payload)
        
        # ============================================================
        # 静态文件服务
        # ============================================================
        
        # HTML 页面
        html_pages = {
            '/': 'index.html',
            '/index.html': 'index.html',
            '/login.html': 'login.html',
            '/register.html': 'register.html',
            '/billing.html': 'billing.html',
        }
        
        if path in html_pages:
            return self._serve_file(os.path.join(HTML_DIR, html_pages[path]), 'text/html; charset=utf-8')
        
        
        # 管理员页面
        if path.startswith('/admin/'):
            admin_file = path[7:] or 'login.html'
            try:
                file_path = safe_join(HTML_DIR, 'admin', admin_file)
                if os.path.exists(file_path):
                    return self._serve_file(file_path, 'text/html; charset=utf-8')
            except ValueError:
                pass
            return self._send_text(404, 'text/plain', 'Not Found')
        
        # 兼容旧路径
        if path == '/admin.html':
            return self._send_redirect('/admin/login.html')
        
        # 静态资源
        if path.startswith('/static/'):
            rel = path[len('/static/'):]
            try:
                file_path = safe_join(STATIC_DIR, rel)
            except Exception:
                return self._send_text(403, 'text/plain; charset=utf-8', 'Forbidden')
            mime = self._get_mime_type(file_path)
            return self._serve_file(file_path, mime)
        
        # 未匹配的请求
        return self._send_json(404, {'error': 'not_found'})

    def do_POST(self):
        """处理 POST 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # 读取请求体
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length > 0 else ''
        headers_dict = {k: v for k, v in self.headers.items()}
        
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            return self._send_json(400, {'error': 'invalid_json'})
        
        # ============================================================
        # API 路由
        # ============================================================
        
        # 系统 API（需要在 admin 通用路由前处理）
        if path == '/api/admin/toggle_registration':
            status, response = handle_system_api(path, 'POST', headers_dict, payload)
            return self._send_json(status, response)
        
        # 管理员 API
        if path.startswith('/api/admin/'):
            status, response = handle_admin_api(path, 'POST', headers_dict, payload)
            return self._send_json(status, response)
        
        # 用户 API
        if path in ('/api/register', '/api/login', '/api/logout'):
            status, response = handle_user_api(path, 'POST', headers_dict, payload)
            return self._send_json(status, response)
        
        # 查询 API
        if path in ('/api/update', '/api/start_search', '/api/start_distillation',
                    '/api/estimate_distillation_cost', '/api/query_status',
                    '/api/update_pause_status',  # 修复9: 添加普通用户暂停API路由
                    '/api/pause_query', '/api/resume_query', '/api/cancel_query',
                    '/api/journals', '/api/count_papers'):
            status, response = handle_query_api(path, 'POST', headers_dict, payload)
            return self._send_json(status, response)
        
        # 新版下载 API（异步队列模式）
        if path == '/api/download/create':
            return self._handle_download_create(payload)
        
        # 系统 API
        if path == '/api/admin/config':
            status, response = handle_system_api(path, 'POST', headers_dict, payload)
            return self._send_json(status, response)
        
        # 未匹配的请求
        return self._send_json(404, {'error': 'not_found'})

    def log_message(self, format, *args):
        """静默日志"""
        return

    def _get_mime_type(self, file_path: str) -> str:
        """根据文件扩展名获取 MIME 类型"""
        if file_path.endswith('.css'):
            return 'text/css; charset=utf-8'
        elif file_path.endswith('.js'):
            return 'application/javascript; charset=utf-8'
        elif file_path.endswith('.html'):
            return 'text/html; charset=utf-8'
        elif file_path.endswith('.png'):
            return 'image/png'
        elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
            return 'image/jpeg'
        elif file_path.endswith('.svg'):
            return 'image/svg+xml'
        elif file_path.endswith('.ico'):
            return 'image/x-icon'
        elif file_path.endswith('.json'):
            return 'application/json; charset=utf-8'
        return 'text/plain'

    def _serve_file(self, path: str, content_type: str):
        """提供静态文件服务"""
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

    def _send_text(self, status: int, content_type: str, text: str):
        """发送纯文本响应"""
        data = text.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self._add_cors_headers()
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_redirect(self, location: str):
        """发送重定向响应"""
        self.send_response(302)
        self.send_header('Location', location)
        self._add_cors_headers()
        self.end_headers()

    class _EnhancedJSONEncoder(json.JSONEncoder):
        """增强的 JSON 编码器，支持 Decimal 和 datetime"""
        def default(self, o):
            if isinstance(o, Decimal):
                return float(o)
            if isinstance(o, (datetime.datetime, datetime.date)):
                return o.isoformat()
            return super().default(o)

    def _send_json(self, status: int, obj: dict):
        """发送 JSON 响应"""
        data = json.dumps(obj, ensure_ascii=False, cls=self._EnhancedJSONEncoder).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._add_cors_headers()
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, status: int, content_type: str, data: bytes, extra_headers: dict = None):
        """发送二进制响应（用于文件下载）"""
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
        """添加 CORS 头"""
        allow_origin = os.getenv('CORS_ALLOW_ORIGIN', '*')
        self.send_header('Access-Control-Allow-Origin', allow_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def _handle_download(self, path: str, payload: dict):
        """处理文件下载请求"""
        from ..load_data import query_dao, search_dao
        import io
        import csv
        import re
        
        query_id = payload.get('query_id') or payload.get('query_index')
        if not query_id:
            return self._send_json(400, {'success': False, 'error': 'missing_query_id'})
        
        # 获取查询信息
        query_log = query_dao.get_query_log(str(query_id))
        if not query_log:
            return self._send_json(404, {'success': False, 'error': 'query_not_found'})
        
        # 获取结果数据
        uid = query_log.get('uid')
        results = search_dao.fetch_results_with_paperinfo(uid, str(query_id)) or []
        
        if path == '/api/download_csv':
            return self._download_csv(query_id, query_log, results)
        else:  # /api/download_bib
            return self._download_bib(query_id, query_log, results)

    def _download_csv(self, query_id: str, query_log: dict, results: list):
        """生成并下载 CSV 文件（新架构：扁平化数据结构）"""
        import io
        import csv
        
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['source', 'year', 'title', 'url', 'search_result', 'reason'])
        
        # 判断相关性（新架构使用 'Y'/'N' 字符串）
        def is_relevant(r):
            val = r.get('search_result', '')
            return str(val).upper() in ('Y', 'YES', '1', 'TRUE')
        
        # 先输出相关，再输出其他
        relevant = [r for r in results if is_relevant(r)]
        others = [r for r in results if not is_relevant(r)]
        
        for r in relevant + others:
            result_val = r.get('search_result', '')
            if str(result_val).upper() in ('Y', 'YES', '1', 'TRUE'):
                result_display = '符合'
            elif str(result_val).upper() in ('N', 'NO', '0', 'FALSE'):
                result_display = '不符'
            else:
                result_display = '未判定'
            
            doi = r.get('doi') or ''
            url = r.get('paper_url') or ''
            if not url and doi:
                url = f"https://doi.org/{doi}"
            
            writer.writerow([
                r.get('source') or '',
                r.get('year') or '',
                r.get('title') or '',
                url,
                result_display,
                r.get('reason') or ''
            ])
        
        csv_content = buf.getvalue()
        data = '\ufeff'.encode('utf-8') + csv_content.encode('utf-8')
        filename = f'Overall_{query_id}.csv'
        return self._send_bytes(200, 'text/csv; charset=utf-8', data, {
            'Content-Disposition': f'attachment; filename="{filename}"'
        })

    def _download_bib(self, query_id: str, query_log: dict, results: list):
        """生成并下载 BIB 文件（新架构：扁平化数据结构）"""
        header_lines = []
        
        query_time = query_log.get('start_time') or ''
        search_params = query_log.get('search_params', {})
        journals = search_params.get('journals', [])
        year_range = search_params.get('year_range', '')
        research_question = search_params.get('research_question', '')
        requirements = search_params.get('requirements', '')
        
        if query_time or journals or research_question:
            header_lines.append(f"% Query Time: {query_time}")
            header_lines.append(f"% Selected Journals: {', '.join(journals)}")
            header_lines.append(f"% Year Range: {year_range}")
            header_lines.append(f"% Research Question: {research_question}")
            if requirements:
                header_lines.append(f"% Requirements: {requirements}")
            header_lines.append(f"\n% Search Topic {{{research_question}}}\n")
        
        # 只输出相关条目（新架构使用 'Y'/'N' 字符串）
        entries = []
        for r in results:
            result_val = r.get('search_result', '')
            if str(result_val).upper() in ('Y', 'YES', '1', 'TRUE'):
                bib = (r.get('bib') or '').strip()
                if bib:
                    entries.append(bib)
        
        content_parts = []
        if header_lines:
            content_parts.extend(header_lines)
        if entries:
            content_parts.append("\n\n".join(entries))
        
        data = "\n".join(content_parts).encode('utf-8')
        filename = f'Result_{query_id}.bib'
        return self._send_bytes(200, 'application/x-bibtex; charset=utf-8', data, {
            'Content-Disposition': f'attachment; filename="{filename}"'
        })

    # ============================================================
    # 新版下载 API 处理方法（异步队列模式）
    # ============================================================
    
    def _handle_download_create(self, payload: dict):
        """
        创建下载任务
        
        POST /api/download/create
        请求：{query_id, type: "csv"|"bib"}
        响应：{success: true, task_id: "..."}
        """
        from ..redis.download import DownloadQueue
        
        query_id = payload.get('query_id') or payload.get('query_index')
        download_type = payload.get('type', 'csv')
        uid = payload.get('uid')
        
        if not query_id:
            return self._send_json(400, {
                'success': False, 
                'error': 'missing_query_id'
            })
        
        if not uid:
            return self._send_json(400, {
                'success': False, 
                'error': 'missing_uid'
            })
        
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return self._send_json(400, {
                'success': False, 
                'error': 'invalid_uid'
            })
        
        # 创建下载任务
        task_id = DownloadQueue.create_task(uid, str(query_id), download_type)
        
        if task_id:
            return self._send_json(200, {
                'success': True,
                'task_id': task_id,
                'message': 'Download task created'
            })
        else:
            return self._send_json(500, {
                'success': False,
                'error': 'create_task_failed'
            })
    
    def _handle_download_status(self, payload: dict):
        """
        查询下载任务状态
        
        GET /api/download/status?task_id=xxx
        响应：{success: true, state: "PENDING"|"PROCESSING"|"READY"|"FAILED", ...}
        """
        from ..redis.download import DownloadQueue
        
        task_id = payload.get('task_id')
        
        if not task_id:
            return self._send_json(400, {
                'success': False,
                'error': 'missing_task_id'
            })
        
        status = DownloadQueue.get_task_status(task_id)
        
        if status:
            return self._send_json(200, {
                'success': True,
                'state': status.get('state', 'UNKNOWN'),
                'uid': status.get('uid'),
                'qid': status.get('qid'),
                'type': status.get('type'),
                'error': status.get('error', ''),
            })
        else:
            return self._send_json(404, {
                'success': False,
                'error': 'task_not_found'
            })
    
    def _handle_download_file(self, payload: dict):
        """
        下载已生成的文件
        
        GET /api/download/file?task_id=xxx
        响应：文件内容（带 Content-Disposition 头）
        """
        from ..redis.download import DownloadQueue, DOWNLOAD_STATE_READY
        
        task_id = payload.get('task_id')
        
        if not task_id:
            return self._send_json(400, {
                'success': False,
                'error': 'missing_task_id'
            })
        
        # 检查任务状态
        status = DownloadQueue.get_task_status(task_id)
        
        if not status:
            return self._send_json(404, {
                'success': False,
                'error': 'task_not_found'
            })
        
        if status.get('state') != DOWNLOAD_STATE_READY:
            return self._send_json(400, {
                'success': False,
                'error': 'file_not_ready',
                'state': status.get('state')
            })
        
        # 获取文件内容
        content = DownloadQueue.get_file_content(task_id)
        
        if not content:
            return self._send_json(404, {
                'success': False,
                'error': 'file_not_found'
            })
        
        # 确定文件类型和名称
        download_type = status.get('type', 'csv')
        qid = status.get('qid', 'download')
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if download_type == 'bib':
            content_type = 'application/x-bibtex; charset=utf-8'
            filename = f'Result_{qid}_{timestamp}.bib'
        else:
            content_type = 'text/csv; charset=utf-8'
            filename = f'Overall_{qid}_{timestamp}.csv'
        
        return self._send_bytes(200, content_type, content, {
            'Content-Disposition': f'attachment; filename="{filename}"'
        })


def run_server(host: str = '127.0.0.1', port: int = 8080):
    """
    启动 HTTP 服务器
    
    Args:
        host: 监听地址
        port: 监听端口
    """
    try:
        # 启动后台调度器
        try:
            from ..process.scheduler import start_scheduler
            start_scheduler()
            print("[Init] 后台调度器已启动")
        except Exception as e:
            print(f"[Init] 启动后台调度器失败: {e}")
        
        # 启动 HTTP 服务器
        httpd = HTTPServer((host, port), RequestHandler)
        httpd.daemon_threads = True
        print(f"WebServer running at http://{host}:{port}/")
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass
