# 新架构重构 - 接口摘要文档

> **用途**: 当Agent会话的Context Window耗尽时，新会话可通过此文档快速恢复上下文

## 当前进度

**最后更新**: 2025-11-27  
**当前阶段**: Bug修复与测试  
**完成阶段**: 阶段一至阶段十（全部完成）+ 十一轮Bug修复

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
- `lib/html/admin/control.html` - 系统控制（注册开关）

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
- `query:{uid}:{qid}:pause_signal` (String) - 暂停信号
- `query:{uid}:{qid}:terminate_signal` (String) - 终止信号（新增）
- `result:{uid}:{qid}` (Hash)

### 计费
- `billing_queue:{uid}` (List)

### 管理员
- `admin:session:{token}` (String, 24h)

---

## 关键接口

### 论文处理（新架构 - 2025-11-26更新）
```python
from lib.process.paper_processor import process_papers, process_papers_for_distillation

# 普通查询
success, query_id = process_papers(uid, search_params)
# search_params: {research_question, requirements, journals, start_year, end_year, include_all_years}

# 蒸馏查询
success, query_id = process_papers_for_distillation(uid, original_query_id, relevant_dois)
```

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

### 管理员会话验证
```python
from lib.redis.admin import AdminSession
token = AdminSession.create_session(uid)  # 创建会话
admin_uid = AdminSession.get_session_uid(token)  # 验证会话
AdminSession.destroy_session(token)  # 销毁会话
```

### 蒸馏任务
```python
from lib.process.distill import create_distill_task
distill_qid = create_distill_task(uid, parent_qid)
```

---

## Bug修复记录 (2025-11-26)

### 修复1: 启动错误
| 文件 | 问题 | 修复 |
|------|------|------|
| `server.py` | `debug_console.info/warn` 不存在 | 替换为 `print()` |
| `init_db.py` | `add_price_column_*` 方法不存在 | 简化函数 |
| `main.py` | `ensure_default_*` 方法不存在 | 移除调用 |

### 修复2: Redis与管理员API
| 文件 | 问题 | 修复 |
|------|------|------|
| `admin_api.py` | 期望str但收到dict | 改为 `payload: Dict` |
| `tests/*.py` | Redis URL替换错误 | 修正替换逻辑 |

### 修复3: 接口适配新架构
| 文件 | 问题 | 修复 |
|------|------|------|
| `paper_processor.py` | 旧签名 `(rq, requirements, n, ...)` | 新签名 `(uid, search_params) -> (bool, str)` |
| `paper_processor.py` | 蒸馏旧签名 | 新签名 `(uid, original_query_id, dois) -> (bool, str)` |
| `tests/*.py` | `validate_session` 不存在 | 使用 `get_session_uid` |

### 修复4: 前端修复与功能完善
| 文件 | 问题 | 修复 |
|------|------|------|
| `user_api.py` | get_user_info 返回格式双重包装 | 移除多余的包装层 |
| `index.html` | 引用不存在的 estimatedCost/articleCount 元素 | 移除无效引用 |
| `index.html` | 队列轮询代码 queueEta 已废弃 | 删除相关 HTML 和 JS 代码 |

### 修复5: 管理员系统控制页面
| 文件 | 问题 | 修复 |
|------|------|------|
| `admin/control.html` | 系统控制页面缺失 | 新建页面，含注册开关功能 |
| `admin/*.html` | 导航缺少系统控制链接 | 在 dashboard/users/tasks 添加链接 |
| `server.py` | `/api/registration_status` 未路由 | 添加到 GET 路由 |
| `server.py` | `/api/admin/toggle_registration` 路由错误 | 添加到 system_api 处理 |

### 修复6: 登录页面优化
| 文件 | 问题 | 修复 |
|------|------|------|
| `login.html` | 注册链接默认隐藏 | 改为默认显示，仅 API 明确关闭时隐藏 |
| `login.html` | 页面风格与 admin 不统一 | CSS 改为深色主题 |
| `login.html` | 注册链接位置不佳 | 移到密码框下方、登录按钮上方 |
| `control.html` | 开关默认状态与后端不一致 | 默认状态改为开启 |

### 修复7: 核心业务Bug修复 (2025-11-27)
| 文件 | 问题 | 修复 |
|------|------|------|
| `main.py` | BillingSyncer未启动导致计费队列积压 | 添加 `start_billing_syncer()` 调用 |
| `index.html` | 进度轮询缺少uid参数 | 3处fetch调用添加uid参数 |
| `history.html` | 进度轮询缺少uid参数 | 1处fetch调用添加uid参数 |
| `query_api.py` | `_handle_get_query_progress` 用uid=0 | 从payload获取uid参数 |
| `search_dao.py` | `fetch_results_with_paperinfo` 返回嵌套结构 | 重构为扁平化结构(策略B) |
| `search_dao.py` | 缺少bib解析函数 | 新增 `_parse_bib_fields()` |
| `server.py` | `_download_csv` 判断条件错误 | 适配新的 'Y'/'N' 字段值 |
| `server.py` | `_download_bib` 判断条件错误 | 适配新的 'Y'/'N' 字段值 |
| `scheduler.py` | Worker数量不考虑Block数量 | 实际Worker数=min(permission, blocks) |
| `distill.py` | spawn_distill_workers无数量限制 | 添加min(count, blocks)限制 |
| `新架构指导文件` | 缺少Worker数量优化说明 | 规则R2后补充说明 |

### 修复8: 暂停/终止功能与蒸馏API修复 (2025-11-27)
| 文件 | 问题 | 修复 |
|------|------|------|
| `query_api.py` | `_handle_update_pause_status`参数名不匹配 | 同时支持query_id和query_index，不强制转int |
| `query_api.py` | `_handle_start_distillation`参数缺失 | 支持original_query_id，修正get_relevant_dois调用 |
| `query_api.py` | `_handle_estimate_distillation_cost`参数缺失 | 同上修复 |
| `distill.html` | parseInt对字符串query_id返回NaN | 移除parseInt，使用字符串类型 |
| `scheduler.py` | `_check_completions`暂停后标记完成 | 检查PAUSED/CANCELLED状态再决定是否标记完成 |
| `task_queue.py` | 缺少终止信号类型 | 新增set_terminate_signal/is_terminated方法 |
| `worker.py` | 终止显示"暂停信号" | 优先检查终止信号，输出"收到终止信号" |
| `admin_api.py` | 终止操作用pause_signal | 改用terminate_signal |

### 修复9: 暂停功能深度修复 (2025-11-27)
| 文件 | 问题 | 修复 |
|------|------|------|
| `server.py` | POST路由遗漏`/api/update_pause_status` | 添加到查询API路由列表 |
| `worker.py` | 完成判定时未检查暂停信号导致暂停后被标记完成 | 完成判定前再次检查暂停/终止信号 |

### 修复10: 历史状态显示与蒸馏按钮修复 (2025-11-27)
| 文件 | 问题 | 修复 |
|------|------|------|
| `index.html` | 暂停后历史记录状态仍显示"进行中" | `createHistoryItem`状态判断改为三态(完成>暂停>进行中) |
| `index.html` | 语言切换时状态不更新暂停状态 | 添加`data-paused`属性并在语言切换时判断 |
| `index.html` | 历史详情卡片不显示暂停状态 | 添加三态状态判断 |
| `index.html` | 进行中任务错误显示蒸馏按钮 | 删除未完成任务的蒸馏按钮 |
| `query_api.py` | `get_query_info`缺少暂停状态字段 | 返回值添加`should_pause`字段 |

### 修复11: 侧边栏状态刷新与任务完成检测修复 (2025-11-27)
| 文件 | 问题 | 修复 |
|------|------|------|
| `index.html` | 暂停后侧边栏历史记录状态不更新 | `handlePauseResume`成功后添加`loadHistory()`调用 |
| `index.html` | 任务完成后页面不自动切换到完成状态 | 历史进度轮询完成时正确更新卡片UI并刷新侧边栏 |
| `index.html` | 历史卡片缺少查找属性 | 创建卡片时添加`data-history-qid`属性 |

---

## 恢复指南

如果你是新的Agent会话，请：
1. 阅读本文档了解重构成果和修复历史
2. 查看 `RefactoryDocs/PROGRESS_LOG.md` 了解详细进度
3. 查看 `需要手动操作的事项.txt` 了解待完成操作
4. 项目重构已基本完成，经过十一轮Bug修复，可进行测试

---

## 关键参考文件

- `新架构项目重构完整指导文件20251124.txt` - 完整设计指导
- `RefactoryDocs/PROGRESS_LOG.md` - 进度日志
- `需要手动操作的事项.txt` - 人工操作清单
