# 新架构重构 - 接口摘要文档

> **用途**: 当Agent会话的Context Window耗尽时，新会话可通过此文档快速恢复上下文

## 当前进度

**最后更新**: 2025-11-30  
**当前阶段**: Bug修复与测试  
**完成阶段**: 阶段一至阶段十（全部完成）+ 二十三轮Bug修复

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
| system_settings | setting_key | 系统配置（修复17新增）|

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

### 系统配置（修复17新增）
- `sys:config:permission_min` (String) - 权限最小值
- `sys:config:permission_max` (String) - 权限最大值
- `sys:config:distill_rate` (String) - 蒸馏系数

### 文献Block
- `meta:{Journal}:{Year}` (Hash, 永不过期)

### 任务队列
- `task:{uid}:{qid}:pending_blocks` (List)
- `query:{uid}:{qid}:status` (Hash)
- `query:{uid}:{qid}:pause_signal` (String) - 暂停信号
- `query:{uid}:{qid}:terminate_signal` (String) - 终止信号（新增）
- `result:{uid}:{qid}` (Hash, **TTL 7天**) - 查询结果缓存（修复23）

### 计费
- `billing_queue:{uid}` (List)

### 下载队列（修复21新增）
- `download_queue` (List) - 全局下载任务队列
- `download:{task_id}:status` (Hash) - 任务状态 {state, uid, qid, type, created_at}
  - state: PENDING/PROCESSING/READY/FAILED
- `download:{task_id}:file` (String, TTL 5min) - 生成的文件内容

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

### 异步下载（修复21新增）
```python
from lib.redis.download import DownloadQueue
from lib.process.download_worker import start_download_workers

# 启动下载Worker池（main.py中调用）
start_download_workers(pool_size=10)

# 创建下载任务（返回task_id）
task_id = DownloadQueue.create_task(uid, qid, download_type='csv')

# 查询任务状态
status = DownloadQueue.get_task_status(task_id)
# 返回: {state: 'PENDING'|'PROCESSING'|'READY'|'FAILED', uid, qid, type, error}

# 获取文件内容（状态为READY后）
content = DownloadQueue.get_file_content(task_id)
```

### 批量获取文献数据（修复21新增）
```python
from lib.redis.paper_blocks import PaperBlocks

# 批量获取指定DOI的Bib数据（Pipeline优化）
block_dois = {'meta:NATURE:2024': ['doi1', 'doi2'], 'meta:SCIENCE:2023': ['doi3']}
all_bibs = PaperBlocks.batch_get_papers(block_dois)
# 返回: {doi: bib_str}

# 批量获取整个Block数据
blocks = PaperBlocks.batch_get_blocks(['meta:NATURE:2024', 'meta:SCIENCE:2023'])
# 返回: {block_key: {doi: bib_str}}
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

### 修复12: 普通用户终止任务功能 (2025-11-27)
| 文件 | 问题 | 修复 |
|------|------|------|
| `i18n.js` | 缺少终止相关翻译 | 添加terminate/terminate_confirm/terminate_success/terminate_fail/terminate_complete翻译 |
| `index.html` | 普通用户无法主动终止任务 | 主进度区域和历史详情卡片添加终止按钮(.btn-danger) |
| `index.html` | 缺少终止处理函数 | 添加handleTerminate和terminateHistoryTask函数 |
| `index.html` | 终止后页面不显示下载界面 | 添加showTerminatedSection和updateHistoryCardAsTerminated函数 |
| `index.html` | 终止后历史卡片不更新 | 添加downloadHistoryCsv和downloadHistoryBib辅助函数 |
| `query_dao.py` | cancel_query使用pause_signal | 改用terminate_signal以区分暂停和终止 |
| `query_dao.py` | **修复12c** cancel_query未停止Worker线程 | 添加stop_workers_for_query调用，确保Worker线程真正停止 |
| `auth.py` | 新用户默认permission过高(50) | 修改register_user默认permission为2 |

### 修复14: Docker镜像拉取失败修复 (2025-11-28)
| 文件 | 问题 | 修复 |
|------|------|------|
| `deploy_autopaperweb.sh` | 中国大陆无法访问Docker Hub | 新增 `load_image_cache()` 加载离线镜像 |
| `scripts/package_images.py` | 需要离线镜像生成工具 | 新建镜像打包脚本（本地开发机执行）|
| `docker/image-cache/README.md` | 缺少使用说明 | 新建离线缓存使用说明 |

### 修复15: 费用估算安全修复+Redis数据清理 (2025-11-29)
| 文件 | 问题 | 修复 |
|------|------|------|
| `query_api.py` | 后端信任前端传递的 `estimated_cost` | 新增 `_calculate_query_cost()` 后端独立计算 |
| `query_api.py` | `_handle_update_config` 每篇按1点计算 | 使用 `_calculate_query_cost()` 按实际价格计算 |
| `query_api.py` | 蒸馏API使用低效的MySQL查询 | 新增 `_calculate_distill_cost()` 纯Redis操作 |
| `index.html` | `startSearch()` 传递 `estimated_cost` | 删除费用参数传递 |
| `journal_dao.py` | `get_prices_by_dois` 已无调用者 | 删除废弃函数 |
| `deploy_autopaperweb.sh` | 未清除Redis持久化数据 | 新增 `cleanup_redis_volumes()` 步骤 |

### 修复16: 余额实时更新功能 (2025-11-29)
| 文件 | 问题 | 修复 |
|------|------|------|
| `query_api.py` | 任务运行时前端余额不实时更新 | `/api/query_progress` 返回值增加 `current_balance` 字段 |
| `index.html` | 余额显示有60秒缓存 | 进度轮询回调中实时更新余额显示 |

### 修复17: 系统配置优化 (2025-11-29)
| 文件 | 问题 | 修复 |
|------|------|------|
| `auth.py` | 第137-298行存在无调用者的历史遗留代码 | 删除5个废弃函数 |
| `db_schema.py` | 缺少系统配置表 | 新增 `system_settings` 表定义 |
| `system_config.py` | 新建 | 系统配置 Redis 缓存层 |
| `system_settings_dao.py` | 新建 | MySQL + Redis 双写 DAO |
| `admin_api.py` | 权限范围硬编码 0-10 | 改为动态读取配置 |
| `system_api.py` | 权限验证无范围检查 | 添加动态范围验证 |
| `query_api.py` | 蒸馏系数硬编码 0.1 | 改为动态获取 `distill_rate` |
| `admin_api.py` | 缺少配置管理 API | 新增 `GET/POST /api/admin/settings` |
| `control.html` | 缺少配置管理 UI | 新增权限范围和蒸馏系数配置界面 |
| `main.py` | 启动时未加载配置 | 添加配置预热到 Redis |

### 修复18: 蒸馏按钮JS错误与注册页面风格统一 (2025-11-29)
| 文件 | 问题 | 修复 |
|------|------|------|
| `index.html` | 蒸馏onclick属性中queryIndex未加引号 | 4处添加引号：`'${queryIndex}'` |
| `register.html` | 紫色渐变浅色主题与login不统一 | 改为深色主题(#0a0a0a/#1a1a1a/#4a90d9) |

### 修复19: 调试页面整合与配置迁移 (2025-11-29)
| 文件 | 问题 | 修复 |
|------|------|------|
| `前端重构设计文档20251129.md` | 新建 | 前端重构完整规划文档（Vue.js方案） |
| `admin/debug.html` | 新建 | 调试日志页面（管理员风格） |
| `system_settings_dao.py` | 缺少调试控制台配置 | 新增 `debug_console_enabled` 配置和便捷方法 |
| `system_api.py` | 调试日志使用config.json配置 | 改为从Redis读取配置（MISS则回源MySQL），删除旧架构兼容 |
| `admin_api.py` | 配置接口未返回调试控制台状态 | 新增 `debug_console_enabled` 返回值 |
| `control.html` | 缺少调试日志开关 | 新增调试日志控制台开关界面 |
| `server.py` | 包含旧页面路由 | 移除 `/debugLog.html`、`/history.html`、`/distill.html` 路由 |
| `config.json` | 包含已迁移的配置项 | 删除 `enable_debug_website_console` |
| `config_loader.py` | 包含已迁移的配置代码 | 清理 `enable_debug_website_console` 相关代码 |
| `debugLog.html` | 旧的调试页面 | 删除（功能已迁移到admin/debug.html） |
| `distill.html` | 冗余页面 | 删除（功能已整合到index.html） |
| `history.html` | 冗余页面 | 删除（功能已整合到index.html） |
| `db_schema.py` | 缺少调试控制台默认配置 | 添加 `debug_console_enabled` 到 `SYSTEM_SETTINGS_DEFAULTS` |
| 所有admin页面 | 导航栏缺少调试日志入口 | 添加"调试日志"导航链接 |

### 修复20: 回滚index.html重构 (2025-11-29)
| 文件 | 问题 | 修复 |
|------|------|------|
| `index.html` | CSS/JS提取导致严重BUG（登录失败、用户名显示错误、按钮无响应） | 选择性回退到commit 9a431c2原始版本（5202行） |
| `static/css/index.css` | 重构产物，已不需要 | 删除 |
| `static/js/index.js` | 重构产物，已不需要 | 删除 |

**注**: index.html代码优化任务暂时搁置，需要更谨慎的重构方案（如采用Vue.js渐进式迁移）

### 修复21: 下载系统重构与计费同步优化 (2025-11-30)
| 文件 | 问题 | 修复 |
|------|------|------|
| `新架构指导文件` | 第9章下载设计过于简略 | 重写第9章，新增异步队列、Pipeline批量获取、高并发分析 |
| `新架构端到端时序图` | 第7节下载流程不完整 | 重写下载流程，展示异步队列模式 |
| `新架构数据库关联图` | 缺少下载相关Redis Key | 新增DownloadTaskStatus和DownloadTaskFile |
| `lib/redis/download.py` | DownloadQueue功能不完整 | 扩展：create_task、任务状态管理、文件存储 |
| `lib/process/download_worker.py` | 不存在 | 新建：DownloadWorker和DownloadWorkerPool(10 Workers) |
| `lib/redis/paper_blocks.py` | 缺少批量获取方法 | 新增batch_get_papers和batch_get_blocks(Pipeline优化) |
| `lib/load_data/search_dao.py` | fetch_results逐个获取Bib | 重构使用Pipeline批量获取(O(n)→O(1)) |
| `lib/webserver/server.py` | 缺少异步下载API | 新增/api/download/create、status、file端点 |
| `main.py` | 未启动DownloadWorkerPool | 添加start_download_workers(10)调用 |
| `lib/html/static/js/i18n.js` | 缺少下载相关翻译 | 新增download_generating等6个翻译(中英文) |
| `lib/html/index.html` | 下载按钮同步阻塞 | 重构所有下载按钮为异步轮询模式，添加spinner样式 |
| `lib/process/billing_syncer.py` | 同步参数(5秒/100条)导致积压 | 优化为1秒/2000条 |

### 修复22: 高并发测试脚本重构 (2025-11-30)
| 文件 | 问题 | 修复 |
|------|------|------|
| `scripts/autopaper_scraper.py` | 使用Selenium效率低 | 完全重写为HTTP API直接调用模式 |
| `scripts/autopaper_scraper.py` | 无法设置用户权限和余额 | 新增管理员API调用(admin_login/update_balance/update_permission) |
| `scripts/autopaper_scraper.py` | 顺序执行无并发 | 使用ThreadPoolExecutor实现50并发查询/下载 |
| `scripts/autopaper_scraper.py` | 测试流程不符合需求 | 实现分阶段测试(前50查询→后50查询+前50下载) |
| `scripts/autopaper_scraper.py` | 无异步下载支持 | 集成异步下载API(create_task/poll_status/download_file) |

### 修复23: Result缓存TTL优化 (2025-11-30)
| 文件 | 问题 | 修复 |
|------|------|------|
| `lib/redis/connection.py` | result:*无过期时间 | 新增TTL_RESULT常量(7天) |
| `lib/redis/result_cache.py` | 缓存无限增长导致内存占满 | set_result/batch_set_results添加7天TTL |
| `lib/load_data/search_dao.py` | 蒸馏7天后无法获取父查询结果 | 新增get_relevant_dois_from_mysql回源方法 |
| `lib/process/distill.py` | 蒸馏功能依赖Redis不支持回源 | create_distill_task/estimate_distill_cost支持MySQL回源 |

---

## 高并发测试脚本

### 使用方法
```bash
# 本地测试 (默认端口18080)
python scripts/autopaper_scraper.py

# 指定服务器地址
python scripts/autopaper_scraper.py --base-url http://localhost:18080

# 生产环境测试
python scripts/autopaper_scraper.py --production

# 测试部分用户 (只测试前10个)
python scripts/autopaper_scraper.py --start-id 1 --end-id 10

# 自定义下载目录
python scripts/autopaper_scraper.py --download-dir "D:\\Downloads\\test"
```

### 测试流程
1. **阶段0**: 初始化100个账户(autoTest1~100)，设置权限=2，余额=30000
2. **阶段1**: 前50用户(1~50)同时发起查询，等待全部完成
3. **阶段2**: 后50用户(51~100)开始查询 + 前50用户同时下载CSV/BIB

### 查询参数
- 研究问题: 人机交互相关的任何研究
- 数据源: ANNU REV NEUROSCI, TRENDS NEUROSCI, ISMAR
- 年份范围: 2020-2025

### 输出文件
- `test_report.csv`: 详细测试报告
- `C:\Users\Asher\Downloads\testDownloadFile\`: 下载的CSV/BIB文件

---

## 离线镜像部署流程

由于中国大陆无法稳定访问 Docker Hub，需要使用离线镜像缓存：

1. **在本地开发机**（能访问 Docker Hub）执行：
```bash
python scripts/package_images.py
```

2. 生成的文件位于 `docker/image-cache/`:
   - `redis-7-alpine.tar` (~15 MB)
   - `python-3.10-slim.tar` (~130 MB)
   - `nginx-alpine.tar` (~45 MB)

3. 将整个项目打包为 `AutoPaperWeb_Server.zip` 上传到服务器

4. 执行部署脚本，会自动加载离线镜像：
```bash
sudo /opt/deploy_autopaperweb.sh
```

---

## 恢复指南

如果你是新的Agent会话，请：
1. 阅读本文档了解重构成果和修复历史
2. 查看 `RefactoryDocs/PROGRESS_LOG.md` 了解详细进度
3. 查看 `RefactoryDocs/前端重构设计文档20251129.md` 了解前端重构规划
4. 查看 `需要手动操作的事项.txt` 了解待完成操作
5. 项目重构已基本完成，经过二十三轮Bug修复，可进行测试

---

## 关键参考文件

- `新架构项目重构完整指导文件20251130.txt` - 完整设计指导
- `RefactoryDocs/PROGRESS_LOG.md` - 进度日志
- `需要手动操作的事项.txt` - 人工操作清单
