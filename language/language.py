# 语言配置文件
import json
import os

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 缓存语言数据
_language_cache = {}

def _load_language_data(language_code):
    """加载指定语言的数据"""
    if language_code in _language_cache:
        return _language_cache[language_code]
    
    json_file = os.path.join(current_dir, f"{language_code}.json")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            _language_cache[language_code] = data
            return data
    except FileNotFoundError:
        # 如果找不到对应的语言文件，返回中文作为默认
        if language_code != 'zh_CN':
            return _load_language_data('zh_CN')
        else:
            raise FileNotFoundError(f"Language file {json_file} not found")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {json_file}: {e}")

# function get_text()
def get_text(language_code=None):
    # 固定仅返回中文文案
    return _load_language_data('zh_CN')

# 为了保持向后兼容性，提供直接访问的变量
zh_CN = _load_language_data('zh_CN')
en_US = _load_language_data('en_US')