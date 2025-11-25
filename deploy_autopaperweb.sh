#!/usr/bin/env bash
# =====================================================
# AutoPaperWeb 部署脚本（新架构版）
# 作用：
#   1) 检查并安装Nginx（如未安装）
#   2) 停止并清理现有容器（如果有）
#   3) 解压 /opt/AutoPaperWeb_Server.zip 到 /opt/AutoPaperWeb_Server
#   4) 关闭 config.json 中的 local_develop_mode
#   5) 以 docker compose 启动所有服务（Redis先启动并健康检查）
#   6) 配置并启动Nginx
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
    log "[1/7] 检查Nginx..."
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
    log "[2/7] 停止并删除所有 Docker 容器（如存在）..."
    if docker ps -aq >/dev/null 2>&1; then
        ids=$(docker ps -aq)
        if [ -n "$ids" ]; then
            docker stop $ids || true
            docker rm $ids || true
        fi
    fi
}

unpack_release() {
    log "[3/7] 解压更新包到 /opt/AutoPaperWeb_Server ..."
    cd /opt/
    rm -rf /opt/AutoPaperWeb_Server
    require_cmd unzip
    if [ ! -f /opt/AutoPaperWeb_Server.zip ]; then
        err "/opt/AutoPaperWeb_Server.zip 不存在！请先上传压缩包。"; exit 1
    fi
    unzip -o /opt/AutoPaperWeb_Server.zip -d /opt/
}

patch_config() {
    log "[4/7] 配置：设置为云端模式..."
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

compose_up() {
    log "[5/7] 检查docker与compose..."
    require_cmd docker
    
    # 支持 docker compose 或 docker-compose
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD=(docker-compose)
    else
        err "未找到docker compose（或docker-compose）。请安装Docker Compose。"; exit 1
    fi

    log "[6/7] 构建并启动容器..."
    cd /opt/AutoPaperWeb_Server
    sudo -E "${COMPOSE_CMD[@]}" up -d --build
}

wait_redis_healthy() {
    log "  等待Redis服务就绪..."
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
    log "[7/7] 配置Nginx..."
    
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
    
    ensure_nginx
    cleanup_containers
    unpack_release
    patch_config
    compose_up
    wait_redis_healthy
    setup_nginx
    
    log "=============================================="
    log "✅ 部署完成！"
    log "  - 使用 'docker ps' 检查运行状态"
    log "  - 使用 'docker logs apw-backend-1' 查看后端日志"
    log "  - 使用 'docker logs apw-redis' 查看Redis日志"
    log "  - 首次启动会进行Redis数据预加载，可能需要几分钟"
    log "=============================================="
}

main "$@"
