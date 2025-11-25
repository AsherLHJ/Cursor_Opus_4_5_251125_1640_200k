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
    # 启动时：确保注册开关在数据库中存在；若缺失则初始化为开启('1')
    try:
        from lib.load_data import db_reader
        db_reader.ensure_default_registration_enabled(True)
    except Exception:
        pass
    
    # 初始化价格系统
    try:
        from lib.price_calculate.init_db import initialize_price_system
        initialize_price_system()
    except Exception as e:
        print(f"价格系统初始化失败: {e}")
    
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
    # 确保 bcrypt_rounds 默认存在
    try:
        from lib.load_data import db_reader
        db_reader.ensure_default_bcrypt_rounds(12)
        # 启动时确保 worker_req_per_min 存在，默认 120（仅初始化，不覆盖已有设置）
        db_reader.ensure_default_worker_req_per_min(120)
    except Exception:
        pass
    run_server(host=host, port=port)
