#!/usr/bin/env bash
# =====================================================
# AutoPaperWeb 部署脚本（健壮版）
# 作用：
#   1) 停止并清理现有容器（如果有）
#   2) 解压 /opt/AutoPaperWeb_Server.zip 到 /opt/AutoPaperWeb_Server
#   3) 关闭 config.json 中的 local_develop_mode
#   4) 以 docker compose 启动所有服务
# 使用：
#   sudo /opt/deploy_autopaperweb.sh
# 说明：
#   - 请确保本脚本为 LF 行尾（非 CRLF）；若出现 “No such file or directory”，请执行：
#       sudo sed -i 's/\r$//' /opt/deploy_autopaperweb.sh && sudo chmod +x /opt/deploy_autopaperweb.sh
#       sudo /opt/deploy_autopaperweb.sh
# =====================================================

set -Eeuo pipefail
IFS=$'\n\t'

log() { printf "%s\n" "$*"; }
err() { printf "[ERROR] %s\n" "$*" 1>&2; }

require_cmd() {
	command -v "$1" >/dev/null 2>&1 || { err "缺少命令：$1"; exit 1; }
}

cleanup_containers() {
	log "[1/5] 停止并删除所有 Docker 容器（如存在）..."
	if docker ps -aq >/dev/null 2>&1; then
		ids=$(docker ps -aq)
		if [ -n "$ids" ]; then
			docker stop $ids || true
			docker rm $ids || true
		fi
	fi
}

unpack_release() {
	log "[2/5] 解压更新包到 /opt/AutoPaperWeb_Server ..."
	cd /opt/
	rm -rf /opt/AutoPaperWeb_Server
	require_cmd unzip
	if [ ! -f /opt/AutoPaperWeb_Server.zip ]; then
		err "/opt/AutoPaperWeb_Server.zip 不存在！请先上传压缩包。"; exit 1
	fi
	unzip -o /opt/AutoPaperWeb_Server.zip -d /opt/
}

patch_config() {
	log "[3/5] 配置检查与模式选择 (local / cloud) ..."
	cd /opt/AutoPaperWeb_Server
	# 是否强制云模式（例如在 ECS 上部署）
	if [ "${APW_FORCE_CLOUD:-}" = "true" ]; then
		if command -v jq >/dev/null 2>&1; then
			tmpfile=$(mktemp)
			if jq '.local_develop_mode=false' config.json >"$tmpfile"; then
				mv "$tmpfile" config.json
				log "  - APW_FORCE_CLOUD=true，已使用 jq 将 local_develop_mode 置为 false"
			else
				rm -f "$tmpfile"
				log "  - jq 修改失败，回退到 sed 方案"
				sed -i 's/"local_develop_mode"\s*:\s*true/"local_develop_mode": false/g' config.json || true
			fi
		else
			sed -i 's/"local_develop_mode"\s*:\s*true/"local_develop_mode": false/g' config.json || true
			log "  - APW_FORCE_CLOUD=true，未检测到 jq，已用 sed 将 true 改为 false（若本已为 false 则无改动）"
		fi
	else
		log "  - 未设置 APW_FORCE_CLOUD，保留 config.json 中的 local_develop_mode 原值"
	fi
}

compose_up() {
	log "[4/5] 检查 docker 与 compose ..."
	require_cmd docker
	# 支持 docker compose 或 docker-compose
	if docker compose version >/dev/null 2>&1; then
		COMPOSE_CMD=(docker compose)
	elif command -v docker-compose >/dev/null 2>&1; then
		COMPOSE_CMD=(docker-compose)
	else
		err "未找到 docker compose（或 docker-compose）。请安装 Docker Compose。"; exit 1
	fi

	# 检查当前模式
	MODE="cloud"
	if command -v jq >/dev/null 2>&1; then
		if jq -e '.local_develop_mode == true' config.json >/dev/null 2>&1; then
			MODE="local"
		fi
	else
		# 简单 grep 判断（容错）
		if grep -E '"local_develop_mode"\s*:\s*true' config.json >/dev/null 2>&1; then
			MODE="local"
		fi
	fi

	log "[5/5] 构建并启动容器（模式：$MODE）..."
	if [ "$MODE" = "local" ]; then
		# 本地开发：叠加本地覆盖文件，自动启用 redis 容器
		if [ -f docker-compose.local.yml ]; then
			sudo -E "${COMPOSE_CMD[@]}" -f docker-compose.yml -f docker-compose.local.yml up -d --build
		else
			sudo -E "${COMPOSE_CMD[@]}" up -d --build
		fi
	else
		# 云端：只用主 compose，后端读取 config.json 中的 cloud 配置并直连云 Redis/RDS
		sudo -E "${COMPOSE_CMD[@]}" up -d --build
	fi
}

main() {
	trap 'err "脚本执行失败（行号：$LINENO）"' ERR
	cleanup_containers
	unpack_release
	patch_config
	compose_up
	log "✅ 部署完成！使用 'docker ps' 检查运行状态。"
}

main "$@"
