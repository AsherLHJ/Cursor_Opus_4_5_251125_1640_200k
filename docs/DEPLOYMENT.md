# AutoPaperWeb 部署与运维指南

适用环境：Linux 服务器 (Ubuntu/CentOS)，Docker 部署。

## 1. 架构说明

新架构采用单后端容器 + Nginx 前端分离模式：
- **Backend (Python)**: 运行在容器内，监听 8080 端口。
- **Frontend (Nginx)**: 运行在容器内，监听 80 端口 (宿主机映射 18080)。
- **Redis**: 必须组件，用于缓存、队列和会话管理。
- **MySQL**: 持久化存储。

## 2. 部署步骤

### 2.1 准备配置

编辑 `config.json`，设置生产环境数据库连接：

```json
{
  "local_develop_mode": false,
  "database": {
    "cloud": {
      "host": "your-rds-host",
      "port": 3306,
      "user": "paper_user",
      "password": "your-password",
      "name": "paperdb"
    }
  },
  "redis": {
    "cloud_url": "redis://:password@your-redis-host:6379/0"
  }
}
```

### 2.2 启动服务

使用 Docker Compose 一键启动：

```bash
# 停止旧容器
docker compose down

# 构建并启动 (后台运行)
docker compose up -d --build
```

### 2.3 初始化/更新数据库

**注意**: 新架构不再需要手动执行 SQL。请在部署后运行一次初始化脚本（即使是更新部署，脚本也会自动处理表结构迁移）。

进入后端容器执行初始化：

```bash
# 进入容器
docker exec -it apw-backend-1 bash

# 运行初始化脚本
python DB_tools/init_database.py --only-schema
```

如果需要导入数据，请去掉 `--only-schema` 参数，并确保数据文件已挂载到容器中。

## 3. Nginx 反向代理配置

建议在宿主机安装 Nginx 作为网关，将流量转发到 Docker 容器。

配置示例参见 `docs/NginxDeploy.md`。

## 4. 运维管理

### 4.1 查看日志

```bash
docker compose logs -f backend
```

### 4.2 系统监控

访问管理员面板 `/admin/login.html` 查看：
- 实时 TPM/RPM
- 队列积压情况
- Worker 线程状态
- Redis/MySQL 健康状态

### 4.3 常见操作

- **重启服务**: `docker compose restart backend`
- **强制停止任务**: 在管理员面板 "任务管理" 页操作。
- **开关注册**: 在管理员面板 "系统控制" 页操作。
