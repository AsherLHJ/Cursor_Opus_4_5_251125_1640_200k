#!/usr/bin/env python3
"""
镜像打包工具 - 生成离线部署所需的 Docker 镜像 tar 包

使用方法（在本地开发机上执行）：
    python scripts/package_images.py

前提条件：
    - 本地已安装 Docker
    - 本地网络可以正常访问 Docker Hub

输出：
    - docker/image-cache/redis-7-alpine.tar
    - docker/image-cache/python-3.10-slim.tar
    - docker/image-cache/nginx-alpine.tar

然后将整个项目（包含 docker/image-cache/ 目录）打包上传到服务器
"""
import subprocess
import os
import sys

# 需要缓存的镜像列表
IMAGES = [
    ("redis:7-alpine", "redis-7-alpine.tar"),
    ("python:3.10-slim", "python-3.10-slim.tar"),
    ("nginx:alpine", "nginx-alpine.tar"),
]

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docker", "image-cache")


def run_cmd(cmd, description):
    """执行命令并显示进度"""
    print(f"[INFO] {description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] 命令执行失败: {cmd}")
        print(f"[ERROR] {result.stderr}")
        return False
    return True


def main():
    print("=" * 60)
    print("Docker 镜像离线打包工具")
    print("=" * 60)
    
    # 检查 Docker 是否可用
    if not run_cmd("docker info > NUL 2>&1" if sys.platform == "win32" else "docker info > /dev/null 2>&1", 
                   "检查 Docker 是否可用"):
        print("[ERROR] Docker 未运行或未安装，请先启动 Docker Desktop")
        sys.exit(1)
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[INFO] 输出目录: {OUTPUT_DIR}")
    
    success_count = 0
    
    for image, filename in IMAGES:
        output_path = os.path.join(OUTPUT_DIR, filename)
        print()
        print(f"[{success_count + 1}/{len(IMAGES)}] 处理镜像: {image}")
        print("-" * 40)
        
        # 拉取镜像
        if not run_cmd(f"docker pull {image}", f"拉取 {image}"):
            print(f"[WARN] 跳过 {image}")
            continue
        
        # 导出镜像
        if not run_cmd(f'docker save -o "{output_path}" {image}', f"导出到 {filename}"):
            print(f"[WARN] 导出 {image} 失败")
            continue
        
        # 显示文件大小
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[OK] {filename} ({size_mb:.1f} MB)")
        success_count += 1
    
    print()
    print("=" * 60)
    print(f"完成！成功打包 {success_count}/{len(IMAGES)} 个镜像")
    print()
    print("下一步操作：")
    print("1. 将整个项目目录打包为 AutoPaperWeb_Server.zip")
    print("2. 上传到服务器 /opt/AutoPaperWeb_Server.zip")
    print("3. 执行: sudo /opt/deploy_autopaperweb.sh")
    print("=" * 60)


if __name__ == "__main__":
    main()

