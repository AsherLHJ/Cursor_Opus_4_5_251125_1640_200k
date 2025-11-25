# 新架构重构 - 接口摘要文档

> **用途**: 当Agent会话的Context Window耗尽时，新会话可通过此文档快速恢复上下文

## 当前进度

**最后更新**: 2025-11-25 17:50  
**当前阶段**: 阶段十 - 清理与文档  
**完成阶段**: 阶段一至阶段九（全部完成）

---

## 重构完成摘要

### 已完成的模块

#### 1. DB_tools (阶段二)
- `DB_tools/lib/db_schema.py` - 10个表的CREATE TABLE定义
- `DB_tools/lib/loader_bib.py` - Bib文件解析与导入
- `DB_tools/lib/loader_tags.py` - 标签数据导入
- `DB_tools/lib/loader_api.py` - API Key导入
- `DB_tools/init_database.py` - 统一入口脚本

#### 2. Redis数据层 (阶段三)
- `lib/redis/connection.py` - Redis连接管理
- `lib/redis/user_cache.py` - 用户数据缓存
- `lib/redis/system_cache.py` - 系统元数据缓存
- `lib/redis/paper_blocks.py` - 文献Block存储
- `lib/redis/task_queue.py` - 任务队列
- `lib/redis/result_cache.py` - 结果缓存
- `lib/redis/billing.py` - 计费队列
- `lib/redis/download.py` - 下载队列
- `lib/redis/admin.py` - 管理员会话
- `lib/redis/init_loader.py` - Redis初始化加载

#### 3. DAO层 (阶段四)
- `lib/load_data/user_dao.py` - Redis优先+MySQL回源
- `lib/load_data/journal_dao.py` - 期刊/标签查询
- `lib/load_data/paper_dao.py` - 新paperinfo结构
- `lib/load_data/query_dao.py` - 任务管理
- `lib/load_data/search_dao.py` - 搜索结果
- `lib/load_data/admin_dao.py` - 管理员数据

#### 4. Worker系统 (阶段五)
- `lib/process/worker.py` - BlockWorker任务池+抢占模式
- `lib/process/scheduler.py` - Worker生产器和调度器
- `lib/process/sliding_window.py` - TPM/RPM滑动窗口
- `lib/process/tpm_accumulator.py` - TPM累加器
- `lib/process/search_paper.py` - AI调用封装

#### 5. 计费系统 (阶段六)
- `lib/price_calculate/price_calculator.py` - Redis实时扣费
- `lib/process/billing_syncer.py` - 后台对账线程

#### 6. 管理员系统 (阶段七)
- `lib/load_data/admin_dao.py` - 管理员数据访问
- `lib/webserver/admin_auth.py` - 管理员鉴权
- `lib/html/admin/login.html` - 登录页面
- `lib/html/admin/dashboard.html` - 监控大盘
- `lib/html/admin/users.html` - 用户管理
- `lib/html/admin/tasks.html` - 任务管理

#### 7. API层 (阶段八)
- `lib/webserver/admin_api.py` - 管理员API处理
- `lib/webserver/server.py` - 集成新API

#### 8. 蒸馏系统 (阶段九)
- `lib/process/distill.py` - 蒸馏任务模块

---

## 已删除的废弃文件

```
DB_tools/
- tools_refresh_db_sentence.py

lib/load_data/
- app_settings_dao.py
- task_dao.py
- queue_dao.py

lib/process/
- queue_facade.py
- queue_manager.py
- redis_queue_manager.py
- rate_limiter.py
- rate_limiter_facade.py
- redis_rate_limiter.py
- redis_aggregates.py

lib/html/
- AutoPaperSearchControlPanelAdmin.html
```

---

## MySQL表结构 (新)

| 表名 | 主键 | 说明 |
|------|------|------|
| user_info | uid | 用户信息 |
| admin_info | uid | 管理员信息（新增）|
| contentlist | Name | 期刊列表 |
| contentlist_year_number | Name | 年份统计（新增）|
| paperinfo | DOI | 文献(DOI+Bib JSON) |
| info_tag | Tag | 标签定义 |
| info_paper_with_tag | id | 标签映射 |
| query_log | query_id | 任务日志（重构）|
| search_result | id | 结果归档（新增）|
| api_list | api_index | API密钥 |

---

## Redis Key设计摘要

### 用户数据
- `user:{uid}:info` (Hash, 8h)
- `user:{uid}:balance` (String, 8h)
- `user:{uid}:history` (ZSet)

### 系统元数据
- `sys:tags:info` (Hash)
- `sys:tag_journals:{Tag}` (Set)
- `sys:journals:info` (Hash)
- `sys:journals:price` (Hash)
- `sys:year_number:{Name}` (String)

### 文献Block
- `meta:{Journal}:{Year}` (Hash, 7d)

### 任务队列
- `task:{uid}:{qid}:pending_blocks` (List)
- `query:{uid}:{qid}:status` (Hash)
- `query:{uid}:{qid}:pause_signal` (String)
- `result:{uid}:{qid}` (Hash)

### 计费
- `billing_queue:{uid}` (List)

### 管理员
- `admin:session:{token}` (String, 24h)

---

## 关键接口

### Worker生产
```python
from lib.process.scheduler import submit_query, start_scheduler
start_scheduler()
submit_query(uid, qid, block_keys)
```

### 计费扣减
```python
from lib.redis.user_cache import UserCache
new_balance = UserCache.deduct_balance(uid, amount)
```

### 管理员登录
```python
from lib.webserver.admin_auth import admin_login
success, token, message = admin_login(username, password)
```

### 蒸馏任务
```python
from lib.process.distill import create_distill_task
distill_qid = create_distill_task(uid, parent_qid)
```

---

## 恢复指南

如果你是新的Agent会话，请：
1. 阅读本文档了解重构成果
2. 查看 `RefactoryDocs/PROGRESS_LOG.md` 了解详细进度
3. 查看 `需要手动操作的事项.txt` 了解待完成操作
4. 项目重构已基本完成，可进行测试和集成

---

## 关键参考文件

- `新架构项目重构完整指导文件20251124.txt` - 完整设计指导
- `RefactoryDocs/PROGRESS_LOG.md` - 进度日志
- `需要手动操作的事项.txt` - 人工操作清单
