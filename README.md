# AutoPaperWeb 新架构

> 最后更新时间：2025-11-26

## 访问地址

### 本地开发环境

启动容器后（`docker compose up -d --build`），可通过以下地址访问：

| 页面 | URL | 说明 |
|------|-----|------|
| 首页 | http://localhost:18080/ | 主搜索页面 |
| 用户登录 | http://localhost:18080/login.html | 普通用户登录 |
| 用户注册 | http://localhost:18080/register.html | 新用户注册 |
| 查询历史 | http://localhost:18080/history.html | 查看历史查询记录 |
| 账单记录 | http://localhost:18080/billing.html | 查看消费明细 |
| 蒸馏任务 | http://localhost:18080/distill.html | 对已完成查询进行蒸馏 |
| **管理员登录** | http://localhost:18080/admin/login.html | 管理员入口 |
| 管理员仪表板 | http://localhost:18080/admin/dashboard.html | 系统监控 |
| 用户管理 | http://localhost:18080/admin/users.html | 管理用户账户 |
| 任务管理 | http://localhost:18080/admin/tasks.html | 管理查询任务 |

### 服务器部署环境

部署到服务器后，将 `localhost:18080` 替换为您的域名或服务器IP：

| 页面 | URL |
|------|-----|
| 首页 | https://autopapersearch.com/ |
| 用户登录 | https://autopapersearch.com/login.html |
| 管理员登录 | https://autopapersearch.com/admin/login.html |

---

## 项目概述

AutoPaperWeb 是一个基于AI的学术论文相关性筛选系统。用户输入研究问题和筛选要求，系统自动从文献数据库中筛选相关论文。

### 新架构特性

- **Redis优先**：高频数据操作使用Redis缓存，提升性能
- **异步计费**：实时Redis扣费 + 后台MySQL对账
- **任务池模式**：Worker预抢占任务，提高并发效率
- **滑动窗口限流**：TPM/RPM精确控制，避免API超限
- **管理员系统**：独立的后台管理界面

## 环境要求

- Python 3.9+
- Docker & Docker Compose
- MySQL 8.0+
- Redis 7.0+

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
# 或使用
python install_requirements.py
```

### 2. 配置文件

编辑 `config.json`：

```json
{
    "local_develop_mode": true,  // 本地开发模式
    "unit_test_mode": false,     // 单元测试模式（模拟AI响应）
    "database": {
        "local": {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "password": "your_password",
            "name": "paperdb"
        }
    },
    "redis": {
        "local_url": "redis://apw-redis:6379/0"
    }
}
```

### 3. 初始化数据库

```bash
# 创建数据库表
python DB_tools/init_database.py

# 创建管理员账户（先修改脚本中的用户名和密码）
python scripts/create_admin.py
```

### 如果是开发测试且需要清理Redis数据，则要在启动服务之前清除Redis持久化数据：

```bash
python scripts/clear_redis_data.py
```

### 4. 启动服务

```bash
# 启动所有容器（Redis会自动先启动并进行健康检查）
docker compose up -d --build

# 查看日志
docker logs -f apw-backend-1
```

### 5. 运行测试

```bash
python tests/FullTest_20251125_2106.py
```

## 配置说明

### 运行模式

| 配置项 | 说明 |
|--------|------|
| `local_develop_mode` | `true`: 使用本地数据库和Redis<br>`false`: 使用云端配置 |
| `unit_test_mode` | `true`: AI返回模拟响应，不消耗API额度<br>`false`: 正常调用AI API |

### Redis配置

- **容器内访问**：`redis://apw-redis:6379/0`
- **宿主机访问**：`redis://localhost:6379/0`

### 数据库配置

支持本地和云端两套配置，根据 `local_develop_mode` 自动切换。

## 部署指南

### 云服务器部署

1. 将项目打包为 `AutoPaperWeb_Server.zip`
2. 上传到服务器 `/opt/` 目录
3. 上传部署脚本 `deploy_autopaperweb.sh` 到 `/opt/`
4. 执行部署：

```bash
sudo chmod +x /opt/deploy_autopaperweb.sh
sudo /opt/deploy_autopaperweb.sh
```

### 部署脚本功能

- 自动安装Nginx（如未安装）
- 停止并清理旧容器
- 解压更新包
- 设置为云端模式
- 启动Docker容器（Redis优先）
- 配置Nginx反向代理

## 运维操作指南

### 查看服务状态

```bash
docker ps
docker logs apw-backend-1
docker logs apw-redis
```

### 清理Redis数据

开发测试时，清除Redis持久化数据：

```bash
python scripts/clear_redis_data.py
```

### 创建管理员

1. 编辑 `scripts/create_admin.py`，修改用户名和密码
2. 运行脚本：

```bash
python scripts/create_admin.py
```

### 压力测试

使用Selenium自动化测试工具：

```bash
# 本地测试
python scripts/autopaper_scraper.py --base-url http://localhost:18080 --start-id 1 --end-id 5

# 生产测试
python scripts/autopaper_scraper.py --start-id 1 --end-id 10 --headless
```

### Redis数据过期策略

| 数据类型 | 过期时间 | 说明 |
|----------|----------|------|
| 用户信息 | 8小时 | `user:{uid}:info` |
| 用户余额 | 8小时 | `user:{uid}:balance` |
| 管理员会话 | 24小时 | `admin:session:{token}` |
| 文献Block | 7天 | `paper:block:{uid}:{qid}:*` |

## 目录结构

```
├── config.json              # 主配置文件
├── docker-compose.yml       # Docker编排文件
├── deploy_autopaperweb.sh   # 部署脚本
├── DB_tools/                # 数据库工具
│   ├── init_database.py     # 数据库初始化入口
│   └── lib/                 # 数据库模块
├── lib/                     # 核心库
│   ├── config/              # 配置加载
│   ├── redis/               # Redis操作模块
│   ├── load_data/           # DAO层
│   ├── process/             # 业务处理
│   └── webserver/           # Web服务
├── scripts/                 # 运维脚本
│   ├── create_admin.py      # 创建管理员
│   ├── clear_redis_data.py  # 清理Redis数据
│   └── autopaper_scraper.py # 压力测试工具
├── tests/                   # 测试脚本
│   └── FullTest_*.py        # 综合测试
├── deploy/                  # 部署配置
│   └── autopaperweb.conf    # Nginx配置
└── RefactoryDocs/           # 重构文档
    ├── PROGRESS_LOG.md      # 进度日志
    └── INTERFACE_SUMMARY.md # 接口文档
```

## 常见问题

### Q: Redis连接失败

确保Docker容器正在运行：
```bash
docker compose up -d redis
```

### Q: 数据库连接失败

1. 检查MySQL服务是否运行
2. 检查 `config.json` 中的数据库配置
3. 本地开发时确保 `local_develop_mode: true`

### Q: 首次启动很慢

首次启动会进行Redis数据预加载（从MySQL加载标签、期刊、文献元数据），时间取决于数据量，可能需要几分钟。

### Q: 如何切换到单元测试模式

编辑 `config.json`，设置 `"unit_test_mode": true`，AI调用将返回模拟响应。

## 技术支持

如遇问题，请查看：
- `RefactoryDocs/INTERFACE_SUMMARY.md` - 接口文档
- `RefactoryDocs/PROGRESS_LOG.md` - 开发日志
- `需要手动操作的事项.txt` - 手动操作清单

