import json
import os
from language import language

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.json')

# 全局变量，用于存储配置
save_full_log = True
include_requirements_in_prompt = True
DATA_FOLDER = ''
APIKEY_FOLDER = ''
RESULT_FOLDER = ''
LOG_FOLDER = ''
LANGUAGE = 'zh_CN'
DARK_MODE = False  # 主题设置，False为亮色主题，True为暗色主题
# 年份范围设置
YEAR_RANGE_START = 2000  # 起始年份
YEAR_RANGE_END = 2025    # 结束年份
INCLUDE_ALL_YEARS = True  # 是否包含所有年份（包括不带年份的文件）
ResearchQuestion = ''
Requirements = ''
system_prompt = ''
model_name = ''
api_base_url = ''
api_timeout = 180
API_KEYS = []
local_develop_mode = False  # 新增：本地开发者模式开关 20251028
DB_HOST = ''
DB_PORT = 3306
DB_USER = ''
DB_PASSWORD = ''
DB_NAME = ''
unit_test_mode = False
enable_debug_website_console = False
TOKENS_PER_REQ = 400
USE_REDIS_QUEUE = True
USE_REDIS_RATELIMITER = True
REDIS_URL = ''
# 共享 Key 并发固定为项目默认架构，不再提供开关


def _to_bool(value):
    """Convert truthy configuration values into a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)

def _in_container() -> bool:
    """检测是否运行在容器内（用于本地开发时主机映射）。"""
    try:
        if os.path.exists('/.dockerenv'):
            return True
        cgroup = '/proc/1/cgroup'
        if os.path.exists(cgroup):
            with open(cgroup, 'r', encoding='utf-8', errors='ignore') as f:
                txt = f.read()
                if 'docker' in txt or 'kubepods' in txt or 'containerd' in txt:
                    return True
    except Exception:
        pass
    return False

def load_config():
    """加载配置文件"""
    global save_full_log, include_requirements_in_prompt
    global DATA_FOLDER, APIKEY_FOLDER, RESULT_FOLDER, LOG_FOLDER, LANGUAGE, DARK_MODE
    global YEAR_RANGE_START, YEAR_RANGE_END, INCLUDE_ALL_YEARS
    global ResearchQuestion, Requirements, system_prompt
    global model_name, api_base_url, api_timeout, API_KEYS
    global DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    global unit_test_mode, local_develop_mode, enable_debug_website_console
    global TOKENS_PER_REQ
    global USE_REDIS_QUEUE, USE_REDIS_RATELIMITER, REDIS_URL
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8-sig') as f:
            config = json.load(f)
        
        # 加载基本配置
        save_full_log = _to_bool(config.get('save_full_log', True))
        include_requirements_in_prompt = _to_bool(config.get('include_requirements_in_prompt', True))
        
        # 加载文件夹路径
        DATA_FOLDER = config.get('DATA_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Data'))
        APIKEY_FOLDER = config.get('APIKEY_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'APIKey'))
        RESULT_FOLDER = config.get('RESULT_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Result'))
        LOG_FOLDER = config.get('LOG_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Log'))
        
        # 加载语言设置
        LANGUAGE = config.get('LANGUAGE', 'zh_CN')
        
        # 加载主题设置
        DARK_MODE = _to_bool(config.get('DARK_MODE', False))
        
        # 加载年份范围设置
        YEAR_RANGE_START = config.get('YEAR_RANGE_START', 2000)
        YEAR_RANGE_END = config.get('YEAR_RANGE_END', 2025)
        INCLUDE_ALL_YEARS = _to_bool(config.get('INCLUDE_ALL_YEARS', True))
        
        # 加载研究问题和关键词
        ResearchQuestion = config.get('ResearchQuestion', '')
        Requirements = config.get('Requirements', '')
        
        # 加载系统提示词
        system_prompt = config.get('system_prompt', '')
        
    # 加载API配置（已切换为火山引擎 Ark OpenAI 兼容接口）
        model_name = config.get('model_name', 'ep-20251105185121-w8d2z')
        api_base_url = config.get('api_base_url', 'https://ark.cn-beijing.volces.com/api/v3')
        api_timeout = config.get('api_timeout', 180)  # 默认180秒
        API_KEYS = config.get('API_KEYS', [])
        # 新增：本地开发者模式
        local_develop_mode = _to_bool(config.get('local_develop_mode', False))
        
        # 固定功能：单一路径（队列 + 调度 + 共享Key）
        try:
            TOKENS_PER_REQ = int(config.get('TOKENS_PER_REQ', 400) or 400)
        except Exception:
            TOKENS_PER_REQ = 400
    # 已取消单 Leader 策略，不再读取 PROGRESS_LEADER
    # 共享 Key 并发固定为默认，不提供动态切换

        # 结构化数据库与 Redis 配置（local/cloud 二选一）
        db_cfg = config.get('database', {})
        redis_cfg = config.get('redis', {})

        if local_develop_mode:
            db_local = db_cfg.get('local', {})
            DB_HOST = db_local.get('host', '127.0.0.1')
            try:
                DB_PORT = int(db_local.get('port', 3306) or 3306)
            except Exception:
                DB_PORT = 3306
            DB_USER = db_local.get('user', 'root')
            DB_PASSWORD = db_local.get('password', '')
            DB_NAME = db_local.get('name', 'PaperDB')

            USE_REDIS_QUEUE = _to_bool(redis_cfg.get('use_queue', True))
            USE_REDIS_RATELIMITER = _to_bool(redis_cfg.get('use_rate_limiter', True))
            REDIS_URL = redis_cfg.get('local_url', '') or 'redis://redis:6379/0'
        else:
            db_cloud = db_cfg.get('cloud', {})
            DB_HOST = db_cloud.get('host', '127.0.0.1')
            try:
                DB_PORT = int(db_cloud.get('port', 3306) or 3306)
            except Exception:
                DB_PORT = 3306
            DB_USER = db_cloud.get('user', 'root')
            DB_PASSWORD = db_cloud.get('password', '')
            DB_NAME = db_cloud.get('name', 'PaperDB')

            USE_REDIS_QUEUE = _to_bool(redis_cfg.get('use_queue', True))
            USE_REDIS_RATELIMITER = _to_bool(redis_cfg.get('use_rate_limiter', True))
            REDIS_URL = redis_cfg.get('cloud_url', '')

        unit_test_mode = _to_bool(config.get('unit_test_mode', False))
        enable_debug_website_console = _to_bool(config.get('enable_debug_website_console', False))

        # 本地开发模式下，容器内访问宿主机 MySQL 的友好映射
        if local_develop_mode and _in_container() and str(DB_HOST).strip().lower() in ('127.0.0.1', 'localhost'):
            DB_HOST = 'host.docker.internal'
        from ..log import debug_console  # pylint: disable=import-outside-toplevel
        debug_console.init_debug_console()
        lang = language.get_text(LANGUAGE)
        print(lang['config_load_success'].format(file=CONFIG_FILE))
        # 打印关键信息便于定位（不包含敏感密码）
        try:
            print(f"[config] local_develop_mode={local_develop_mode}, DB_HOST={DB_HOST}, DB_PORT={DB_PORT}, DB_NAME={DB_NAME}")
            if REDIS_URL:
                # 屏蔽可能的密码，仅打印主机与库索引
                _ru = REDIS_URL
                try:
                    from urllib.parse import urlparse as _urlparse
                    _p = _urlparse(_ru)
                    redishost = _p.hostname or 'unknown'
                    redisport = _p.port or 6379
                    redisdb = (_p.path or '/0').lstrip('/') or '0'
                    print(f"[config] REDIS -> host={redishost}, port={redisport}, db={redisdb}")
                except Exception:
                    print("[config] REDIS_URL set")
        except Exception:
            pass
    except Exception as e:
        from ..log import debug_console  # pylint: disable=import-outside-toplevel
        debug_console.init_debug_console()
        lang = language.get_text(LANGUAGE)
        print(lang['config_load_failed'].format(error=e))
        print(lang['using_default_config'])

def save_config():
    # 将当前内存态配置写回结构化 config.json（仅用于开发场景）
    config = {
        'save_full_log': save_full_log,
        'include_requirements_in_prompt': include_requirements_in_prompt,
        'DATA_FOLDER': DATA_FOLDER,
        'APIKEY_FOLDER': APIKEY_FOLDER,
        'RESULT_FOLDER': RESULT_FOLDER,
        'LOG_FOLDER': LOG_FOLDER,
        'LANGUAGE': LANGUAGE,
        'DARK_MODE': DARK_MODE,
        'YEAR_RANGE_START': YEAR_RANGE_START,
        'YEAR_RANGE_END': YEAR_RANGE_END,
        'INCLUDE_ALL_YEARS': INCLUDE_ALL_YEARS,
        'ResearchQuestion': ResearchQuestion,
        'Requirements': Requirements,
        'system_prompt': system_prompt,
        'model_name': model_name,
        'api_base_url': api_base_url,
        'api_timeout': api_timeout,
        'unit_test_mode': unit_test_mode,
        'enable_debug_website_console': enable_debug_website_console,
        'local_develop_mode': local_develop_mode,
    # 固定开关无需写回
        'TOKENS_PER_REQ': TOKENS_PER_REQ,
    # 已取消单 Leader 策略：不再写回 PROGRESS_LEADER
    # 共享 Key 架构为默认，不写回任何开关
        'database': {
            'local': {
                'host': DB_HOST if local_develop_mode else '127.0.0.1',
                'port': DB_PORT if local_develop_mode else 3306,
                'user': DB_USER if local_develop_mode else 'root',
                'password': DB_PASSWORD if local_develop_mode else '',
                'name': DB_NAME if local_develop_mode else 'PaperDB',
            },
            'cloud': {
                'host': DB_HOST if not local_develop_mode else '127.0.0.1',
                'port': DB_PORT if not local_develop_mode else 3306,
                'user': DB_USER if not local_develop_mode else 'root',
                'password': DB_PASSWORD if not local_develop_mode else '',
                'name': DB_NAME if not local_develop_mode else 'PaperDB',
            },
        },
        'redis': {
            'use_queue': USE_REDIS_QUEUE,
            'use_rate_limiter': USE_REDIS_RATELIMITER,
            'local_url': 'redis://redis:6379/0',
            'cloud_url': REDIS_URL if not local_develop_mode else '',
        }
    }

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        lang = language.get_text(LANGUAGE)
        print(lang['config_save_success'].format(file=CONFIG_FILE))
    except Exception as e:
        lang = language.get_text(LANGUAGE)
        print(lang['config_save_failed'].format(error=e))

# 初始加载配置
load_config()
