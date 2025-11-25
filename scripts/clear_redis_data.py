#!/usr/bin/env python3
"""
清理Redis持久化数据脚本

用途：
    在开发测试环境中，清除Redis容器的持久化数据，
    确保下一次测试开始时Redis数据是干净的。

使用方法：
    python scripts/clear_redis_data.py

注意：
    - 此脚本会停止并删除Redis容器
    - 清除Docker volume中的Redis数据
    - 需要在项目根目录下运行
    - 需要Docker和docker compose权限
"""

import subprocess
import sys
import time


def run_command(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """执行命令并返回结果"""
    print(f"[执行] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"[错误] {result.stderr}")
    return result


def get_compose_cmd() -> list:
    """获取docker compose命令"""
    # 尝试 docker compose (v2)
    result = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return ["docker", "compose"]
    
    # 尝试 docker-compose (v1)
    result = subprocess.run(
        ["docker-compose", "version"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return ["docker-compose"]
    
    print("[错误] 未找到docker compose或docker-compose命令")
    sys.exit(1)


def main():
    print("=" * 50)
    print("Redis数据清理工具")
    print("=" * 50)
    print()
    
    compose_cmd = get_compose_cmd()
    
    # 1. 停止Redis容器
    print("[步骤1] 停止Redis容器...")
    run_command([*compose_cmd, "stop", "redis"], check=False)
    
    # 2. 删除Redis容器
    print("\n[步骤2] 删除Redis容器...")
    run_command([*compose_cmd, "rm", "-f", "redis"], check=False)
    
    # 3. 删除Redis数据卷
    print("\n[步骤3] 删除Redis数据卷...")
    # 获取项目名称（默认为当前目录名）
    volume_patterns = [
        "redis_data",
        "cursor_opus_4_5_251125_1640_200k_redis_data",  # 可能的完整卷名
    ]
    
    # 列出所有卷
    result = run_command(["docker", "volume", "ls", "-q"], check=False)
    if result.returncode == 0:
        volumes = result.stdout.strip().split('\n')
        for vol in volumes:
            if vol and any(pattern in vol.lower() for pattern in ["redis", "apw"]):
                print(f"  发现Redis相关卷: {vol}")
                run_command(["docker", "volume", "rm", "-f", vol], check=False)
    
    # 也尝试直接删除可能的卷名
    for pattern in volume_patterns:
        run_command(["docker", "volume", "rm", "-f", pattern], check=False)
    
    print("\n[步骤4] 清理完成!")
    print()
    print("提示：")
    print("  - 使用 'docker compose up -d redis' 重新启动Redis")
    print("  - 或使用 'docker compose up -d' 启动所有服务")
    print("  - 首次启动会进行Redis数据预加载")
    print()


if __name__ == "__main__":
    main()

