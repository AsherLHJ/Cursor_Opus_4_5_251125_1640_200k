# AutoPaperWeb 部署与运维指南（Ubuntu 22.04｜阿里云 ECS）

适用环境：
- 服务器：2 核 4G，Ubuntu 22.04（x86_64），公网 IP：8.138.45.108，私网 IP：172.31.142.94
- Nginx 作为反向代理与负载均衡
- 应用运行在 Docker 容器，MySQL 使用宿主机服务（非容器）

本文包含：镜像构建/分发、Docker 启动、Nginx 安装与配置、日常运维命令、安全与常见问题。

---

## 1. 项目镜像打包与分发

建议直接在服务器本地构建镜像并使用本地镜像启动容器（避免上传到 Docker Hub 暴露风险）。如需跨机分发，可将镜像导出为 tar 并传输。

### 1.1 在服务器本地构建镜像（推荐）
```bash
# 安装 Docker（若未安装）
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 克隆或上传本项目到服务器，例如：/opt/AutoPaperWeb
git clone <your-repo> /opt/AutoPaperWeb  # 或直接用 SFTP 上传本地代码
cd /opt/AutoPaperWeb

# 构建镜像（使用 docker-compose.yml 中定义的上下文）
sudo docker compose build
```

### 1.2 在本地构建并以文件分发（可选）
```bash
# 本地机器上构建
cd /path/to/AutoPaperWeb
docker compose build

# 导出镜像（示例导出 backend 与 frontend）
docker save -o backend.tar autopaperweb-backend1:latest  # 或按实际镜像名
docker save -o frontend.tar autopaperweb-frontend:latest

# 上传到服务器（示例）
scp backend.tar ubuntu@8.138.45.108:/opt/AutoPaperWeb/
scp frontend.tar ubuntu@8.138.45.108:/opt/AutoPaperWeb/

# 服务器端加载
cd /opt/AutoPaperWeb
sudo docker load -i backend.tar
sudo docker load -i frontend.tar
```

---

## 2. 容器启动（使用宿主机已有 MySQL｜内网 IP 访问）

当前服务器已安装 MySQL（数据位于宿主机 `/var/lib/mysql`），后端容器通过内网 IP 直连数据库，无需启动 Compose 内置的 db 容器。

- 已在 `docker-compose.yml` 中将三个后端的数据库配置指向宿主机私网 IP：`DB_HOST=172.31.142.94`，并统一使用：
  - 数据库名：`PaperDB`
  - 用户名：`paper_user`
  - 密码：`Paper2025`

授权说明（关键）：容器访问 MySQL 需要为容器所在 Docker 子网授权。不同主机的默认 Docker 子网可能不同（常见为 172.17.0.0/16 或 172.18.0.0/16）。
- 如何确认你的 Docker 子网：
```bash
ip -4 addr | grep docker0 | awk '{print $2}'   # 或
sudo docker network inspect bridge | grep Subnet
```
- 授权示例（任选与你实际子网匹配的条目执行）：
```sql
-- 如为 172.17.0.0/16
CREATE USER IF NOT EXISTS 'paper_user'@'172.17.%' IDENTIFIED BY 'Paper2025';
GRANT ALL PRIVILEGES ON PaperDB.* TO 'paper_user'@'172.17.%';

-- 如为 172.18.0.0/16
CREATE USER IF NOT EXISTS 'paper_user'@'172.18.%' IDENTIFIED BY 'Paper2025';
GRANT ALL PRIVILEGES ON PaperDB.* TO 'paper_user'@'172.18.%';

FLUSH PRIVILEGES;
```

并确保 mysqld 监听私网地址或 0.0.0.0（/etc/mysql/mysql.conf.d/mysqld.cnf）：
```bash
sudo sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
sudo systemctl restart mysql
```

如启用了 UFW/防火墙，请放通来自 Docker 网段的 3306：
```bash
# 替换为你的实际子网
sudo ufw allow from 172.17.0.0/16 to any port 3306
# 或者
sudo ufw allow from 172.18.0.0/16 to any port 3306
```

### 2.1 启动服务
```bash
cd /opt/AutoPaperWeb
# 如需限制前端跨域（一般由宿主 Nginx 转发，此项可忽略）
export CORS_ALLOW_ORIGIN='http://8.138.45.108'

sudo -E docker compose up -d --build
```

说明：
- 本方案不再启动 db 容器，避免与宿主机 MySQL 的 3306 端口冲突。
- 三个后端副本将直接连接 172.31.142.94:3306 上的 `PaperDB`。

### 2.5 Redis 与运行时开关（Stage3 能力）

Stage3 引入可选的 Redis 用于“令牌桶限流（RPM/TPM）+ 就绪/等待队列”。运行时开关建议：

- 连接信息（建议用 ENV 注入）：
  - REDIS_URL（优先，如：`redis://:password@127.0.0.1:6379/0`）
  - 或 REDIS_HOST、REDIS_PORT、REDIS_DB、REDIS_PASSWORD

- 功能开关（优先使用 app_settings 热更新，config.json 仅作默认值）：
  - USE_REDIS_QUEUE（默认 false）
  - USE_REDIS_RATELIMITER（默认 false）
  - scheduler_enabled / queue_enabled（默认 false，灰度开启）

- 容量参数（app_settings 全局动态配置）：
  - tokens_per_req（默认 400）
  - worker_req_per_min（默认 60）

开关优先级：运行时以 app_settings 为准（热加载，缓存约 10s）；config.json 为默认值；ENV 主要用于连接串与容器级默认。切换开关时建议短暂停止调度循环以避免中间状态。

### 2.2 查看容器与日志
```bash
sudo docker compose ps
sudo docker compose logs -f backend1
sudo docker compose logs -f backend2
sudo docker compose logs -f backend3
sudo docker compose logs -f frontend
```

### 2.3 常用容器操作
```bash
# 停止 / 启动 / 重启
audp='sudo docker compose'
$audp stop
$audp start
$audp restart

# 只重启后端某个副本
$audp restart backend2

# 清理（不会删除 mysql_data 卷的数据）
$audp down

# 进入容器（名称以实际为准）
sudo docker ps
sudo docker exec -it <container_name> bash
```

### 2.4 代码修改后的重建与重启（常用）

当你修改了项目代码（前端静态页面或后端 Python 代码）后，按下列方式在服务器上重建并重新拉起容器：

```bash
# 进入项目目录
cd /opt/AutoPaperWeb

# 构建所有服务并以守护进程方式启动/重启（推荐）
sudo -E docker compose build
sudo -E docker compose up -d
```

仅构建/重启指定服务：
```bash
# 仅后端三个副本
sudo -E docker compose build backend1 backend2 backend3
sudo -E docker compose up -d backend1 backend2 backend3

# 仅前端（静态资源改动建议不使用缓存）
sudo -E docker compose build --no-cache frontend
sudo -E docker compose up -d frontend

# 只重启某一个后端副本（不重建镜像）
sudo -E docker compose restart backend2
```

查看状态与日志（排错常用）：
```bash
sudo docker compose ps
sudo docker compose logs -f backend1
sudo docker compose logs -f frontend
```

快速健康探测（按你的端口映射调整）：
```bash
curl -I http://127.0.0.1:18080
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18081/api/folders
```

提示：若你的环境仍使用旧版命令，将以上的 `docker compose` 替换为 `docker-compose` 即可。

---

## 3. 宿主机安装与配置 Nginx（反向代理 + 负载均衡）

为保持本文简洁，本节迁移至独立文档并覆盖 HTTPS/SSL 配置与域名变更提示：

- 请参见：`docs/NginxDeploy.md`

该文档包含：最小化安装步骤、HTTP/HTTPS 配置示例（含 80 跳转 443）、证书放置与权限、启用站点、重载校验、DNS/安全组、防火墙、域名变更时需同步修改的项等。更深入说明与可选参数请参考上文链接的阿里云官方手册。

---

## 4. 数据库运维（宿主机 MySQL｜内网访问）

- 数据位置：宿主机 `/var/lib/mysql`（非容器卷）。
- 访问方式：后端容器通过内网 IP `172.31.142.94:3306` 访问。
- 账号与库：`paper_user` / `Paper2025` / `PaperDB`。

备份示例（在宿主机执行）：
```bash
mysqldump -upaper_user -p'Paper2025' PaperDB > PaperDB_$(date +%F).sql
```

连接测试（在容器内）：
```bash
sudo docker exec -it <backend_container_name> python - <<'PY'
import os, mysql.connector
cnx = mysql.connector.connect(
  host=os.getenv("DB_HOST"),
  port=int(os.getenv("DB_PORT",3306)),
  user=os.getenv("DB_USER"),
  password=os.getenv("DB_PASSWORD"),
  database=os.getenv("DB_NAME")
)
print("MySQL OK"); cnx.close()
PY
```

---

## 5. 日常服务器运维命令

### 5.1 进程与端口
```bash
# 查看占用端口的进程
sudo lsof -i:80
sudo lsof -i:18080
sudo lsof -i:18081-18083

# 查看进程并结束
ps aux | grep nginx
sudo kill -9 <PID>
```

### 5.2 Docker 常用
```bash
sudo docker ps -a
sudo docker stop <container>
sudo docker rm <container>
sudo docker images
sudo docker rmi <image>
```

### 5.3 系统服务
```bash
sudo systemctl status nginx
sudo systemctl restart nginx

sudo systemctl status docker
sudo systemctl restart docker
```

---

## 6. 安全与优化建议

- 强制使用强密码：`MYSQL_ROOT_PASSWORD`、应用用户密码；
- Nginx 仅对外暴露 80/443，后端端口 18081-18083 与 18080 仅供本机访问；
- 如需要 HTTPS，建议申请证书（Let’s Encrypt）并配置 `listen 443 ssl`；
- 如需跨站调用 API，可在后端设置 `CORS_ALLOW_ORIGIN` 为具体前端域名；
- 结合 Fail2ban、防火墙（UFW）限制来源 IP；
- 定期备份数据库并验证恢复流程。

---

## 7. 常见问题排查

- 网页打不开：
  - `systemctl status nginx` 确认 Nginx 正常；
  - `docker compose ps` 查看容器；
  - `curl -I http://127.0.0.1:18080` 验证前端容器；
  - `curl -I http://127.0.0.1:18081/api/folders` 验证后端 API。

- 连接数据库失败（宿主机 MySQL 场景）：
  - 确认宿主机 MySQL 服务运行：`systemctl status mysql`；
  - 确认容器环境变量 `DB_HOST/DB_USER/DB_PASSWORD/DB_NAME` 正确；
  - 确认已为“你的 Docker 子网”授权（见上文授权说明）；
  - 容器内执行“连接测试”代码块，查看具体异常堆栈。

- 负载不均衡：
  - 调整 Nginx upstream 策略（如 `least_conn`、`ip_hash`）并 reload。

- 容量/队列指标异常：
  - 访问 `/api/queue/stats` 检查字段：`backend`（redis/mysql）、`effective_rate_per_min`（papers/min）、`tokens_per_req`、`redis_enabled`、`redis_info`
  - 如 Redis 断连，系统会回退至 MySQL，观测到 backend=MySQL。

---

## 8. 版本与目录说明

- Dockerfile：`docker/` 目录
- docker-compose：项目根目录 `docker-compose.yml`
- 宿主机 Nginx 示例配置：`deploy/nginx_host.conf`
- 部署与运维指南：本文件 `docs/DEPLOYMENT.md`

如需进一步自动化（systemd/Watchtower/CI），可另行扩展。

---

## 9. 阿里云 VPC 私网部署（ECS + Redis/RDS 内网直连）

适用场景：后端部署在阿里云 ECS，同 VPC 内使用云 Redis 与云 RDS MySQL。强烈建议使用内网地址与白名单，禁止公网直连数据库。

### 9.1 前提与网络

- 确认 ECS、Redis、RDS 在同一 VPC（例如：vpc-7xv1cy2uqg5g8xwbjfann）。
- 记录 ECS 所在交换机（VSwitch）网段（示例：vsw-7xvazmix0nvlpywhr0uht，CIDR：172.31.128.0/20）。

### 9.2 Redis 与 RDS 白名单

- Redis（内网地址示例）：r-7xvuz53fhs94ar5668.redis.rds.aliyuncs.com
  - 在“访问白名单”中添加：172.31.128.0/20（或你的 ECS 私网 IP：172.31.142.94）
  - 如为 ACL 账号模式，使用“用户名+密码”认证（示例用户：user_20251028 / 密码：PaperUser2025）

- RDS MySQL（内网地址示例）：rm-7xv09hqbxb55odlr3.mysql.rds.aliyuncs.com
  - 在“白名单”中添加：172.31.128.0/20（或 ECS 私网 IP）
  - 准备业务账号并授予目标库权限（SELECT/INSERT/UPDATE/DELETE）

白名单保存后通常几十秒内生效。

### 9.3 配置 config.json（单一真源）

本项目将基础连接信息与默认值放在 `config.json`，运行时功能开关与容量参数优先通过 app_settings 管理（热更新）。根据部署环境切换：

- 云端模式：
  - `local_develop_mode`: false
  - `database.cloud`：填写 RDS 内网域名、端口、账号、库名
  - `redis.cloud_url`：填写 Redis ACL 连接串，例如：
    `redis://user_20251028:PaperUser2025@r-7xvuz53fhs94ar5668.redis.rds.aliyuncs.com:6379/0`

- 本地开发模式（如需）：
  - `local_develop_mode`: true
  - `database.local`：填写本机 MySQL（默认 127.0.0.1:3306）
  - `redis.local_url`: `redis://redis:6379/0`

### 9.4 启动方式（脚本自动选择本地/云端）

在服务器（或本地）执行：

```bash
sudo -E APW_FORCE_CLOUD=true /opt/deploy_autopaperweb.sh
```

- 设定 `APW_FORCE_CLOUD=true` 时，脚本会将 `local_develop_mode` 置为 false 并按云端模式启动。
- 若不设该环境变量，脚本按 `config.json` 原值判断：
  - local 模式：叠加 `docker-compose.local.yml` 启动本地 Redis 容器用于开发联调；
  - cloud 模式：仅使用 `docker-compose.yml`，后端直连云 Redis/RDS。

### 9.5 联通性验证

- 在 ECS 上测试 Redis（ACL 模式）：
```bash
redis-cli -h r-7xvuz53fhs94ar5668.redis.rds.aliyuncs.com -p 6379 --user user_20251028 --pass "PaperUser2025" ping
# 返回 PONG 即成功
```

- 在 ECS 上测试 MySQL：
```bash
mysql -h rm-7xv09hqbxb55odlr3.mysql.rds.aliyuncs.com -P 3306 -u user_20251028 -p -e "SELECT 1"
```

### 9.6 常见问题

- 认证失败：Redis 多为 ACL 账号模式，需“用户名+密码”；仅设置 `-a 密码` 会提示 NOAUTH。
- 连接超时：多半为不在同一 VPC 或白名单未包含 ECS 网段/IP；或 ECS 安全组收紧了出站。
- 数据库无权限：确认已为业务账号授予目标库权限并刷新（FLUSH PRIVILEGES）。

---

## 10. 健康检查与观测（Stage3/Stage4）

- 健康接口：
  - GET /healthz → {status:"ok"}
  - GET /readyz → { db:"ok"|"fail", redis:"ok"|"fail" }（任一失败返回 503）

- 队列与容量：
  - GET /api/queue/stats → 返回 `effective_rate_per_min`（papers/min）、`backlog_total`、`tokens_per_req`、`backend`、`redis_enabled`、`redis_info`

- 管理编辑：
  - GET /api/admin/tokens_per_req / POST /api/admin/set_tokens_per_req
  - POST /api/admin/update_api_limits（合并 is_active/rpm_limit/tpm_limit）

单位一致性：
- permission：req/min（每分钟可查询篇数）
- effective_rate_per_min：papers/min（每分钟处理篇数）

