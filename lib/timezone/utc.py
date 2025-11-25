from datetime import datetime, timezone

def utc_now_str() -> str:
    """
    返回统一格式的 UTC 时间字符串："UTC-YYYY-MM-DD HH:MM:SS"
    """
    return 'UTC-' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def to_local_str(utc_str: str) -> str:
    """
    将 "UTC-YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DD HH:MM:SS" 视为 UTC，转换为本地时间字符串。
    仅供后端需要时使用；前端通常会自行转换。
    """
    if not utc_str:
        return ''
    try:
        s = utc_str
        if s.startswith('UTC-'):
            s = s[4:]
        dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(utc_str)
