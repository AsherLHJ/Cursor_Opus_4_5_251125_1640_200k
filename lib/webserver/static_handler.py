"""
静态文件服务处理模块
负责HTML、CSS、JS、图片等静态文件的服务
"""

import os
import mimetypes
from typing import Optional, Tuple
from urllib.parse import unquote

# 确保 mimetypes 正确识别常见文件类型
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/json', '.json')
mimetypes.add_type('image/svg+xml', '.svg')
mimetypes.add_type('font/woff', '.woff')
mimetypes.add_type('font/woff2', '.woff2')

# 目录常量（供 server.py 使用）
LIB_DIR = os.path.dirname(os.path.dirname(__file__))
HTML_DIR = os.path.join(LIB_DIR, 'html')
STATIC_DIR = os.path.join(HTML_DIR, 'static')

# 静态文件根目录 (相对于项目根目录)
STATIC_ROOTS = [
    'lib/html',
    'static',
    'public',
]


def safe_join(base: str, *paths: str) -> str:
    """
    安全地拼接路径，防止目录遍历攻击
    
    Args:
        base: 基础目录
        paths: 要拼接的路径组件
        
    Returns:
        拼接后的绝对路径
        
    Raises:
        ValueError: 如果检测到目录遍历攻击
    """
    final_path = os.path.normpath(os.path.join(base, *paths))
    if os.path.commonprefix([final_path, base]) != base:
        raise ValueError("Unsafe path: attempted directory traversal")
    return final_path


def get_content_type(path: str) -> str:
    """
    根据文件扩展名获取 MIME 类型
    
    Args:
        path: 文件路径
    
    Returns:
        MIME 类型字符串
    """
    content_type, _ = mimetypes.guess_type(path)
    if content_type is None:
        # 默认为二进制流
        content_type = 'application/octet-stream'
    
    # 为文本类型添加 UTF-8 编码
    if content_type.startswith('text/') or content_type in (
        'application/javascript',
        'application/json',
        'application/xml',
    ):
        content_type += '; charset=utf-8'
    
    return content_type


def find_static_file(request_path: str) -> Optional[str]:
    """
    在静态文件目录中查找请求的文件
    
    Args:
        request_path: 请求路径 (如 '/index.html', '/css/style.css')
    
    Returns:
        文件的绝对路径，如果未找到则返回 None
    """
    # URL 解码
    path = unquote(request_path)
    
    # 移除开头的斜杠
    if path.startswith('/'):
        path = path[1:]
    
    # 默认文件
    if path == '' or path == '/':
        path = 'index.html'
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 遍历静态文件根目录查找文件
    for root in STATIC_ROOTS:
        full_path = os.path.join(project_root, root, path)
        
        # 安全检查：防止目录遍历攻击
        real_path = os.path.realpath(full_path)
        real_root = os.path.realpath(os.path.join(project_root, root))
        
        if not real_path.startswith(real_root):
            continue
        
        if os.path.isfile(real_path):
            return real_path
    
    return None


def serve_static_file(request_path: str) -> Tuple[int, bytes, str]:
    """
    提供静态文件服务
    
    Args:
        request_path: 请求路径
    
    Returns:
        (status_code, content_bytes, content_type)
    """
    file_path = find_static_file(request_path)
    
    if file_path is None:
        return 404, b'Not Found', 'text/plain; charset=utf-8'
    
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        content_type = get_content_type(file_path)
        return 200, content, content_type
    
    except PermissionError:
        return 403, b'Forbidden', 'text/plain; charset=utf-8'
    except Exception as e:
        return 500, f'Internal Server Error: {str(e)}'.encode('utf-8'), 'text/plain; charset=utf-8'


def serve_html_page(page_name: str) -> Tuple[int, bytes, str]:
    """
    提供HTML页面
    
    Args:
        page_name: 页面名称 (如 'index', 'login', 'history')
    
    Returns:
        (status_code, content_bytes, content_type)
    """
    # 确保扩展名
    if not page_name.endswith('.html'):
        page_name = page_name + '.html'
    
    return serve_static_file('/' + page_name)


def is_static_request(path: str) -> bool:
    """
    判断是否为静态文件请求
    
    Args:
        path: 请求路径
    
    Returns:
        True 如果是静态文件请求
    """
    # API 请求不是静态文件
    if path.startswith('/api/') or path.startswith('/admin/'):
        return False
    
    # 常见静态文件扩展名
    static_extensions = (
        '.html', '.htm', '.css', '.js', '.json',
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
        '.woff', '.woff2', '.ttf', '.eot',
        '.pdf', '.txt', '.xml',
        '.map',
    )
    
    # 有扩展名的路径
    if any(path.lower().endswith(ext) for ext in static_extensions):
        return True
    
    # 根路径或无扩展名的路径（可能是HTML页面）
    if path == '/' or '.' not in os.path.basename(path):
        return True
    
    return False


def list_available_pages() -> list:
    """
    列出所有可用的 HTML 页面
    
    Returns:
        页面名称列表
    """
    pages = []
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    for root in STATIC_ROOTS:
        root_path = os.path.join(project_root, root)
        if not os.path.isdir(root_path):
            continue
        
        for file in os.listdir(root_path):
            if file.endswith('.html') and not file.startswith('_'):
                pages.append(file)
    
    return sorted(set(pages))

