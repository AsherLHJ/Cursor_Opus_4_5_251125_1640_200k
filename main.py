import os
from lib.config import config_loader as config
from lib.log.debug_console import init_debug_console
from lib.webserver.server import run_server

if __name__ == "__main__":
    config.load_config()
    init_debug_console()
    # 打印 Feature Flags（来自 config.json 单一真源）
    try:
        q = bool(getattr(config, 'QUEUE_ENABLED', True))
        s = bool(getattr(config, 'SCHEDULER_ENABLED', True))
        tpr = int(getattr(config, 'TOKENS_PER_REQ', 550))
        print(f"[flags] queue_enabled={q}, scheduler_enabled={s}, tokens_per_req={tpr}")
    except Exception:
        pass
    # Start backend web service
    # - Local developer mode: listen on 127.0.0.1
    # - Production/container mode: listen on 0.0.0.0 to expose the port
    
    # 初始化价格系统
    try:
        from lib.price_calculate.init_db import initialize_price_system
        initialize_price_system()
    except Exception as e:
        print(f"价格系统初始化失败: {e}")
    
    # 从MySQL同步数据到Redis（新架构关键步骤）
    try:
        from lib.redis.connection import redis_ping
        from lib.redis.init_loader import init_redis_from_mysql
        from lib.load_data.db_base import _get_connection
        
        if redis_ping():
            print("[Init] 开始从MySQL同步数据到Redis...")
            conn = _get_connection()
            result = init_redis_from_mysql(conn, load_papers=True)
            conn.close()
            print(f"[Init] Redis数据同步完成: {result}")
        else:
            print("[Init] Redis不可用，跳过数据同步")
    except Exception as e:
        print(f"[Init] Redis数据初始化失败: {e}")
    
    # 预热系统配置到Redis（权限范围、蒸馏系数等）
    try:
        from lib.load_data.system_settings_dao import ensure_defaults, reload_cache
        ensure_defaults()  # 确保MySQL中有默认配置
        reload_cache()     # 加载配置到Redis缓存
        print("[Init] 系统配置已加载到Redis")
    except Exception as e:
        print(f"[Init] 系统配置加载失败: {e}")
    
    # 启动BillingSyncer后台线程（新架构：异步计费同步）
    try:
        from lib.process.billing_syncer import start_billing_syncer
        start_billing_syncer()
        print("[Init] BillingSyncer已启动")
    except Exception as e:
        print(f"[Init] BillingSyncer启动失败: {e}")
    
    # 启动后端 Web 服务：
    # - 本地开发者模式：仅监听本机 127.0.0.1
    # - 生产/容器环境：监听 0.0.0.0（容器可暴露端口）
    port = int(os.getenv("PORT", "8080"))
    # 在容器内即便是本地开发模式也应监听 0.0.0.0，供其它容器/宿主机访问
    try:
        in_container = bool(config._in_container())  # type: ignore[attr-defined]
    except Exception:
        in_container = False
    host = "127.0.0.1" if (getattr(config, "local_develop_mode", False) and not in_container) else "0.0.0.0"
    run_server(host=host, port=port)
