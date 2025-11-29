#!/usr/bin/env bash
# =====================================================
# AutoPaperWeb 部署脚本（新架构版 v4 - 支持Redis数据清理）
# 作用：
#   1) 检查并安装Nginx（如未安装）
#   2) 停止并清理现有容器（如果有）
#   3) 清除Redis持久化数据（避免旧数据干扰新部署）
#   4) 解压 /opt/AutoPaperWeb_Server.zip 到 /opt/AutoPaperWeb_Server
#   5) 关闭 config.json 中的 local_develop_mode
#   6) 配置Docker镜像加速器（阿里云专属）
#   7) 加载离线镜像缓存（如果存在）
#   8) 以 docker compose 启动所有服务（带重试机制）
#   9) 等待Redis健康检查
#   10) 配置并启动Nginx
# 使用：
#   sudo /opt/deploy_autopaperweb.sh
# 说明：
#   - 请确保本脚本为 LF 行尾（非 CRLF）；若出现 "No such file or directory"，请执行：
#       sudo sed -i 's/\r$//' /opt/deploy_autopaperweb.sh && sudo chmod +x /opt/deploy_autopaperweb.sh
#       sudo /opt/deploy_autopaperweb.sh
# =====================================================

set -Eeuo pipefail
IFS=$'\n\t'

log() { printf "[INFO] %s\n" "$*"; }
err() { printf "[ERROR] %s\n" "$*" 1>&2; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || { err "缺少命令：$1"; exit 1; }
}

# 检查并安装Nginx
ensure_nginx() {
    log "[1/9] 检查Nginx..."
    if ! command -v nginx >/dev/null 2>&1; then
        log "  Nginx未安装，正在安装..."
        apt-get update -qq
        apt-get install -y nginx
        log "  Nginx安装完成"
    else
        log "  Nginx已安装"
    fi
}

cleanup_containers() {
    log "[2/10] 停止并删除所有 Docker 容器（如存在）..."
    if docker ps -aq >/dev/null 2>&1; then
        ids=$(docker ps -aq)
        if [ -n "$ids" ]; then
            docker stop $ids || true
            docker rm $ids || true
        fi
    fi
}

cleanup_redis_volumes() {
    log "[3/10] 清除 Redis 持久化数据..."
    
    # 重要：清除旧版 Redis 持久化数据，避免对新部署产生干扰
    # 参考 README.md 中 Redis 数据清理说明
    
    # 查找并删除包含 "redis_data" 的 volumes
    redis_volumes=$(docker volume ls -q 2>/dev/null | grep -E "redis_data|redis-data" || true)
    
    if [ -n "$redis_volumes" ]; then
        log "  - 发现 Redis volume(s): $redis_volumes"
        for vol in $redis_volumes; do
            log "  - 删除 volume: $vol"
            docker volume rm "$vol" 2>/dev/null || true
        done
        log "  - Redis 持久化数据已清除"
    else
        log "  - 未发现 Redis volume，跳过清理"
    fi
    
    # 也清理项目特定的 volume（带项目名前缀）
    project_volumes=$(docker volume ls -q 2>/dev/null | grep -E "autopaperweb.*redis|apw.*redis" || true)
    if [ -n "$project_volumes" ]; then
        for vol in $project_volumes; do
            log "  - 删除项目 volume: $vol"
            docker volume rm "$vol" 2>/dev/null || true
        done
    fi
}

unpack_release() {
    log "[4/10] 解压更新包到 /opt/AutoPaperWeb_Server ..."
    cd /opt/
    rm -rf /opt/AutoPaperWeb_Server
    require_cmd unzip
    if [ ! -f /opt/AutoPaperWeb_Server.zip ]; then
        err "/opt/AutoPaperWeb_Server.zip 不存在！请先上传压缩包。"; exit 1
    fi
    unzip -o /opt/AutoPaperWeb_Server.zip -d /opt/
}

patch_config() {
    log "[5/10] 配置：设置为云端模式..."
    cd /opt/AutoPaperWeb_Server
    
    # 强制设置为云端模式
    if command -v jq >/dev/null 2>&1; then
        tmpfile=$(mktemp)
        if jq '.local_develop_mode=false | .unit_test_mode=false' config.json >"$tmpfile"; then
            mv "$tmpfile" config.json
            log "  - 已使用jq将local_develop_mode和unit_test_mode置为false"
        else
            rm -f "$tmpfile"
            log "  - jq修改失败，回退到sed方案"
            sed -i 's/"local_develop_mode"\s*:\s*true/"local_develop_mode": false/g' config.json || true
            sed -i 's/"unit_test_mode"\s*:\s*true/"unit_test_mode": false/g' config.json || true
        fi
    else
        sed -i 's/"local_develop_mode"\s*:\s*true/"local_develop_mode": false/g' config.json || true
        sed -i 's/"unit_test_mode"\s*:\s*true/"unit_test_mode": false/g' config.json || true
        log "  - 未检测到jq，已用sed将配置修改为云端模式"
    fi
}

setup_docker_mirror() {
    log "[6/10] 配置Docker镜像加速器..."
    
    DAEMON_JSON="/etc/docker/daemon.json"
    
    # 检查是否已配置加速器
    if [ -f "$DAEMON_JSON" ] && grep -q "registry-mirrors" "$DAEMON_JSON"; then
        log "  - Docker镜像加速器已配置，跳过"
        return 0
    fi
    
    # 备份现有配置
    if [ -f "$DAEMON_JSON" ]; then
        cp "$DAEMON_JSON" "${DAEMON_JSON}.bak"
        log "  - 已备份原有配置到 ${DAEMON_JSON}.bak"
    fi
    
    # 写入阿里云专属镜像加速器配置
    log "  - 写入阿里云专属镜像加速器配置..."
    mkdir -p /etc/docker
    cat > "$DAEMON_JSON" << 'EOF'
{
    "registry-mirrors": ["https://ap2qz3w9.mirror.aliyuncs.com"]
}
EOF
    
    log "  - 重启Docker服务以应用配置..."
    systemctl daemon-reload
    systemctl restart docker
    
    # 等待Docker就绪
    for i in {1..15}; do
        if docker info >/dev/null 2>&1; then
            log "  - Docker镜像加速器配置完成"
            return 0
        fi
        sleep 2
    done
    
    err "Docker重启超时，请手动检查Docker服务状态"
    return 1
}

load_image_cache() {
    log "[7/10] 加载离线镜像缓存..."
    
    CACHE_DIR="/opt/AutoPaperWeb_Server/docker/image-cache"
    
    # 检查缓存目录是否存在
    if [ ! -d "$CACHE_DIR" ]; then
        log "  - 未检测到离线镜像缓存目录，将尝试在线拉取"
        return 0
    fi
    
    # 检查是否有 tar 文件
    tar_count=$(find "$CACHE_DIR" -name "*.tar" -type f 2>/dev/null | wc -l)
    if [ "$tar_count" -eq 0 ]; then
        log "  - 缓存目录为空，将尝试在线拉取"
        return 0
    fi
    
    log "  - 检测到 $tar_count 个离线镜像包，开始加载..."
    
    loaded=0
    failed=0
    
    for tarfile in "$CACHE_DIR"/*.tar; do
        if [ -f "$tarfile" ]; then
            filename=$(basename "$tarfile")
            log "  - 加载: $filename"
            
            if docker load -i "$tarfile" 2>&1; then
                loaded=$((loaded + 1))
            else
                err "    加载失败: $filename"
                failed=$((failed + 1))
            fi
        fi
    done
    
    log "  - 离线镜像加载完成: 成功 $loaded 个, 失败 $failed 个"
    
    # 显示已加载的镜像
    log "  - 当前可用镜像:"
    docker images --format "    {{.Repository}}:{{.Tag}}" | head -10
    
    return 0
}

compose_up() {
    log "[8/10] 检查docker与compose..."
    require_cmd docker
    
    # 支持 docker compose 或 docker-compose
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD=(docker-compose)
    else
        err "未找到docker compose（或docker-compose）。请安装Docker Compose。"; exit 1
    fi

    log "[8/10] 构建并启动容器（带重试机制）..."
    cd /opt/AutoPaperWeb_Server
    
    MAX_RETRIES=3
    RETRY_DELAY=15
    
    for attempt in $(seq 1 $MAX_RETRIES); do
        log "  - 第 $attempt/$MAX_RETRIES 次尝试构建容器..."
        
        if sudo -E "${COMPOSE_CMD[@]}" up -d --build 2>&1; then
            log "  - 容器构建成功！"
            return 0
        fi
        
        if [ $attempt -lt $MAX_RETRIES ]; then
            log "  - 构建失败，等待 ${RETRY_DELAY}秒 后重试..."
            log "  - 提示：如果持续失败，请检查："
            log "         1) 离线镜像是否已加载: docker images"
            log "         2) Docker服务是否运行: systemctl status docker"
            log "         3) 查看详细错误日志"
            sleep $RETRY_DELAY
        fi
    done
    
    err "=============================================="
    err "容器构建失败（已重试 $MAX_RETRIES 次）"
    err "排错建议："
    err "  1. 检查离线镜像是否存在: ls -la /opt/AutoPaperWeb_Server/docker/image-cache/"
    err "  2. 检查已加载的镜像: docker images"
    err "  3. 手动加载镜像: docker load -i /opt/AutoPaperWeb_Server/docker/image-cache/redis-7-alpine.tar"
    err "  4. 查看Docker日志: journalctl -u docker --since '10 minutes ago'"
    err "=============================================="
    return 1
}

wait_redis_healthy() {
    log "[9/10] 等待Redis服务就绪..."
    for i in {1..30}; do
        if docker exec apw-redis redis-cli ping 2>/dev/null | grep -q PONG; then
            log "  Redis已就绪"
            return 0
        fi
        sleep 2
    done
    err "Redis启动超时（60秒）"
    exit 1
}

setup_nginx() {
    log "[10/10] 配置Nginx..."
    
    # 复制Nginx配置文件
    if [ -f /opt/AutoPaperWeb_Server/deploy/autopaperweb.conf ]; then
        cp /opt/AutoPaperWeb_Server/deploy/autopaperweb.conf /etc/nginx/sites-available/
        
        # 创建软链接（如果不存在）
        if [ ! -L /etc/nginx/sites-enabled/autopaperweb.conf ]; then
            ln -sf /etc/nginx/sites-available/autopaperweb.conf /etc/nginx/sites-enabled/
        fi
        
        # 删除默认配置（如果存在）
        rm -f /etc/nginx/sites-enabled/default
        
        # 测试Nginx配置
        if nginx -t; then
            systemctl reload nginx || systemctl restart nginx
            log "  Nginx配置已更新并重载"
        else
            err "Nginx配置测试失败，请检查配置文件"
            exit 1
        fi
    else
        log "  警告：未找到autopaperweb.conf，跳过Nginx配置"
    fi
}

main() {
    trap 'err "脚本执行失败（行号：$LINENO）"' ERR
    
    ensure_nginx           # [1/10]
    cleanup_containers     # [2/10]
    cleanup_redis_volumes  # [3/10] 清除Redis持久化数据，避免旧数据干扰
    unpack_release         # [4/10]
    patch_config           # [5/10]
    setup_docker_mirror    # [6/10] 配置镜像加速器（备用）
    load_image_cache       # [7/10] 加载离线镜像（主要方式）
    compose_up             # [8/10] 构建并启动容器
    wait_redis_healthy     # [9/10]
    setup_nginx            # [10/10]
    
    log "=============================================="
    log "部署完成！"
    log "  - 使用 'docker ps' 检查运行状态"
    log "  - 使用 'docker logs apw-backend-1' 查看后端日志"
    log "  - 使用 'docker logs apw-redis' 查看Redis日志"
    log "  - 首次启动会进行Redis数据预加载，可能需要几分钟"
    log "=============================================="
}

main "$@"
