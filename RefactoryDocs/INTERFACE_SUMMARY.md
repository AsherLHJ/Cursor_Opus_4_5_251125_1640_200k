# 新架构重构 - 接口摘要文档

> **用途**: 当Agent会话的Context Window耗尽时，新会话可通过此文档快速恢复上下文

## 当前进度

**最后更新**: 2025-12-18  
**当前阶段**: Bug修复与测试  
**完成阶段**: 阶段一至阶段十（全部完成）+ 四十二轮Bug修复 + 架构文档同步更新

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
- `lib/redis/user_session.py` - 用户会话管理（修复37新增）
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
- `lib/webserver/user_auth.py` - 用户Token认证验证（修复37新增）
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
- `query:{uid}:{qid}:terminate_signal` (String) - 终止信号（修复41：删除pause_signal，只保留terminate_signal）
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

### 用户会话（修复37新增）
- `user:session:{token}` (String, 24h) - 用户会话Token→uid映射

### DOI反向索引（修复26新增）
- `idx:doi_to_block` (Hash) - DOI→block_key映射，O(1)查询

### 蒸馏专用Block（修复29新增）
- `distill:{uid}:{qid}:{index}` (Hash, TTL 7天) - 蒸馏专用Block，Value为JSON{"bib", "price"}

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

## 高并发测试脚本 (含蒸馏功能)

### 使用方法
```bash
# 本地测试 (全部100个活跃用户)
python scripts/autopaper_scraper.py

# 指定服务器地址
python scripts/autopaper_scraper.py --base-url http://localhost:18080

# 生产环境测试
python scripts/autopaper_scraper.py --production

# 测试前10个用户
python scripts/autopaper_scraper.py --start-id 1 --end-id 10

# 测试前50个用户
python scripts/autopaper_scraper.py --start-id 1 --end-id 50

# 自定义下载目录
python scripts/autopaper_scraper.py --download-dir "D:\\Downloads\\test"
```

### 测试流程
1. **阶段0**: 初始化账户(autoTest1~300)，设置权限=2，余额=30000
2. **阶段1**: 前100用户同时发起查询 -> 每个查询完成后自动发起蒸馏 -> 蒸馏完成后下载CSV/BIB

### 查询参数
- 研究问题: 人机交互相关的任何研究
- 数据源: ANNU REV NEUROSCI, TRENDS NEUROSCI, ISMAR
- 年份范围: 2020-2025

### 蒸馏参数
- 蒸馏研究问题: 使用了EEG和EMG的硬件的研究
- 蒸馏研究要求: (空)

### 输出文件
- `test_report.csv`: 详细测试报告（含查询、蒸馏、下载耗时统计）
- `C:\Users\Asher\Downloads\testDownloadFile\`: 下载的蒸馏结果CSV/BIB文件

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

## 修复24: 前端功能增强与Bug修复

### 修复内容（8项）
1. **蒸馏功能 MySQL 回源**: `query_api.py` + `search_dao.py` - Redis MISS时回源MySQL
2. **billing.html 账单显示**: `user_dao.py` - 修复字段映射
3. **余额符号修复**: `admin/users.html` - 删除 ¥ 符号
4. **版块顺序调整**: `admin/dashboard.html` - 系统健康状态移到上方
5. **选择文章数 bug**: `index.html` - 修复 {count} 显示
6. **标签中英文切换**: `i18n.js` + `index.html` - 添加标签翻译映射
7. **DataTable 组件**: 新建 `data-table.js` + `data-table.css` - 可复用表格组件
8. **billing.html 表格增强**: 集成 DataTable（分页/排序/搜索/筛选）

### 新增文件
- `lib/html/static/js/data-table.js` - 数据表格组件
- `lib/html/static/css/data-table.css` - 组件样式

---

## 修复25: 前端功能增强与Bug修复 - 第三轮

### 修复内容（5项）
1. **蒸馏功能 block_key 修复**: `search_dao.py` - MySQL表无block_key列，改用PaperBlocks获取
2. **billing.html 深色主题**: 完善深色主题样式（搜索框、下拉菜单、表格、分页按钮）
3. **标签翻译补全**: `i18n.js` - 添加12个大类 + 282个二级分类英文翻译
4. **管理员页面多语言**: 6个admin页面添加多语言支持（登录、仪表板、用户、任务、控制、调试）
5. **i18n.js翻译扩展**: 添加完整的`admin`命名空间翻译（中英文）

### 修改文件
- `lib/load_data/search_dao.py`
- `lib/html/billing.html`
- `lib/html/static/css/data-table.css`
- `lib/html/static/js/i18n.js`
- `lib/html/admin/login.html`
- `lib/html/admin/dashboard.html`
- `lib/html/admin/users.html`
- `lib/html/admin/tasks.html`
- `lib/html/admin/control.html`
- `lib/html/admin/debug.html`

---

## 修复26: 蒸馏功能超时与管理员登录Bug (2025-11-30)

### 问题分析
1. **蒸馏功能超时**: 点击蒸馏后长期显示"加载中..."，最终"获取失败"(504超时)
2. **管理员登录Bug**: 双重语言按钮 + 表单GET提交暴露密码

### 根因
1. `get_paper_by_doi` 遍历所有Block查找DOI，复杂度O(n*m)，导致请求超时
2. `admin/login.html` 手动添加了语言按钮，i18n.js又自动创建一个；表单无action属性

### 修复内容（6项）
| 文件 | 问题 | 修复 |
|------|------|------|
| `paper_blocks.py` | `get_paper_by_doi`遍历所有Block | 添加DOI反向索引`idx:doi_to_block`实现O(1)查询 |
| `paper_blocks.py` | 缺少批量查询block_key方法 | 新增`batch_get_block_keys` Pipeline方法 |
| `init_loader.py` | 启动时未构建DOI索引 | 阶段3.5调用`build_doi_index()` |
| `search_dao.py` | `get_all_results_from_mysql`逐个查询DOI | 改用`batch_get_block_keys`批量查询 |
| `admin/login.html` | 重复语言按钮 | 删除手动按钮，保留i18n.js自动创建 |
| `admin/login.html` | 表单GET提交暴露密码 | 添加`action="javascript:void(0)" method="POST"` |

### 新增Redis Key
- `idx:doi_to_block` (Hash) - DOI反向索引，Field=DOI，Value=block_key

### 性能提升
- 蒸馏费用估算从分钟级超时优化到秒级响应
- DOI查询从O(n*m)遍历优化到O(1)索引查找

---

## 修复27: 蒸馏功能前端Bug修复 (2025-11-30)

### 问题分析
1. **点击"开始蒸馏"无反应**: onclick属性中queryIndex字符串参数缺少引号导致JS ReferenceError
2. **输入框每次输入都调用API**: input事件监听器缺少防抖，每输入一个字符就调用一次费用估算API

### 修复内容（2项）
| 位置 | 问题 | 修复 |
|------|------|------|
| `index.html` 第4868行等4处 | `onclick="fn(${queryIndex})"` 缺引号 | 添加引号 `onclick="fn('${queryIndex}')"` |
| `index.html` input事件 | 每次输入调用API浪费资源 | 费用数据缓存到activeDistillCards，input事件只做本地状态检查 |

### 修改文件
- `lib/html/index.html` - 修复4处onclick引号 + 重构input事件处理

---

## 修复28: 蒸馏计费Bug修复 (2025-11-30)

### 问题分析
- **现象**: 用户余额600，预计消耗527.6，但Worker报告"余额不足"，仅处理388条
- **根因**: Scheduler启动Worker时没有区分普通查询和蒸馏任务，统一使用 `BlockWorker`（正常费率）
- **费用差异**: 预计0.1倍费率 vs 实际1倍费率

### 修复内容（2项）
| 文件 | 问题 | 修复 |
|------|------|------|
| `query_dao.py` | 缺少按ID查询函数 | 新增 `get_query_by_id()` 函数 |
| `scheduler.py` | `_start_query_workers` 不区分任务类型 | 检查 `is_distillation`，蒸馏任务使用 `spawn_distill_workers` |

### 修改文件
- `lib/load_data/query_dao.py` - 新增 `get_query_by_id()` 函数
- `lib/process/scheduler.py` - 修改 `_start_query_workers()` 区分任务类型

---

## 恢复指南

## 修复29: 蒸馏任务Scheduler异常与超额计费修复 (2025-11-30)

### 问题分析
1. **Scheduler异常**: `'DistillWorker' object has no attribute '_running'`
2. **超额计费**: 预估527.6（2943篇），实际扣费530.0（3272篇）

### 根因
1. `DistillWorker` 类没有暴露 `_running` 和 `_thread` 属性
2. `distillation_producer` 入队的是 `meta:` 格式的完整Block，Worker处理整个Block而非仅相关DOI

### 修复内容（3项）
| 文件 | 问题 | 修复 |
|------|------|------|
| `distill.py` | DistillWorker缺少属性 | 添加 `@property _running` 和 `_thread` 代理 |
| `paper_processor.py` | 入队完整Block | `distillation_producer` 创建 `distill:` 前缀专用Block |
| `paper_blocks.py` | 不支持distill:前缀 | `get_block_by_key` 支持 `distill:` 前缀Block |

### 新增Redis Key格式
- `distill:{uid}:{qid}:{block_index}` (Hash, TTL 7天) - 蒸馏专用Block，只包含相关DOI的Bib数据

### 修改文件
- `lib/process/distill.py` - DistillWorker属性代理
- `lib/process/paper_processor.py` - distillation_producer重构
- `lib/redis/paper_blocks.py` - get_block_by_key支持distill:前缀

---

## 修复30: 蒸馏功能深度修复 (2025-11-30)

### 问题分析
1. **代码重复**: `distill.py` 包含未被调用的函数（与 paper_processor 和 query_api 功能重复）
2. **研究问题空白**: 蒸馏任务创建时 research_question="" 未传递用户输入
3. **历史记录标识**: is_distillation 从不存在的数据库列获取，应从 search_params JSON 获取
4. **前端显示**: 蒸馏任务无法区分，不显示父任务信息

### 修复内容（10项）
| 文件 | 问题 | 修复 |
|------|------|------|
| `distill.py` | 5个未使用的函数 | 删除 create_distill_task, _create_distill_blocks, get_distill_block, calculate_distill_cost, estimate_distill_cost |
| `distill.py` | DISTILL_RATE=0.1 硬编码 | 改为 SystemConfig.get_distill_rate() 动态获取 |
| `paper_processor.py` | process_papers_for_distillation 不接收研究问题 | 添加 research_question, requirements 参数 |
| `paper_processor.py` | estimated_cost 使用硬编码 0.1 | 改为 SystemConfig.get_distill_rate() 动态获取 |
| `scheduler.py` | 注释中硬编码"0.1倍费率" | 更新为"动态蒸馏费率" |
| `query_api.py` | _handle_start_distillation 不传递研究问题 | 传递 question, requirements 参数 |
| `query_api.py` | _handle_get_query_history 从数据库列获取 is_distillation | 改为从 search_params JSON 获取，添加 original_query_id |
| `query_api.py` | _handle_get_query_info 缺少蒸馏相关字段 | 添加 is_distillation 和 original_query_id 返回 |
| `index.html` | 历史记录和详情卡片不区分蒸馏任务 | 添加蒸馏前缀，显示父任务ID |
| `i18n.js` | 缺少蒸馏相关翻译 | 添加 distill_prefix 和 distill_based_on 中英文翻译 |

### 新增API返回字段
- `_handle_get_query_history` 返回: `is_distillation`, `original_query_id`
- `_handle_get_query_info` 返回: `is_distillation`, `original_query_id`

### 修改文件清单
- `lib/process/distill.py` - 清理5个未使用函数，蒸馏费率动态化
- `lib/process/paper_processor.py` - process_papers_for_distillation 添加参数，费率动态化
- `lib/process/scheduler.py` - 更新注释
- `lib/webserver/query_api.py` - 修复3处蒸馏相关逻辑
- `lib/html/index.html` - 蒸馏任务显示优化
- `lib/html/static/js/i18n.js` - 添加蒸馏翻译词条

---

## 修复31: 蒸馏功能深度修复 (2025-11-30)

### 问题清单
1. 查询任务刷新后"文章总数"和"预计花费"消失
2. 蒸馏任务扣费错误（按1点/篇而非实际价格×蒸馏系数）
3. 蒸馏任务刷新后"相关论文数量"、"开销"、"开始时间"消失
4. 蒸馏任务颜色需从深紫色改为低饱和度橙色

### 根因分析
1. `/api/get_query_info` 和 `/api/get_query_history` 返回数据缺少 `total_papers_count` 和 `estimated_cost` 字段
2. 蒸馏Block格式是 `distill:` 前缀，`parse_block_key` 只能解析 `meta:` 前缀，导致价格默认为1
3. 预估阶段计算的价格信息未传递给Worker，导致Worker每次处理都需查询

### 修复内容（IOPS优化版）

#### A. API层修复
- `_handle_get_query_info`: 新增 `total_papers_count` 和 `estimated_cost` 返回字段
- `_handle_get_query_history`: 新增 `estimated_cost` 返回字段

#### B. 蒸馏扣费修复（0额外IOPS）
- `_calculate_distill_cost`: 返回三元组 `(dois, cost, doi_prices)`，在预估遍历时收集价格信息
- `_handle_start_distillation`: 传递 `doi_prices` 给处理函数
- `process_papers_for_distillation`: 新增 `doi_prices` 参数
- `distillation_producer`: 蒸馏Block存储格式改为JSON `{"bib": bib, "price": price}`
- `DistillWorker.__init__`: 缓存蒸馏费率（1次调用）
- `_process_paper_with_distill_rate`: 从Block解析价格JSON（0次额外查询）

**IOPS效果**:
- 预估阶段: 3次Redis调用（与文献数量N无关）
- Worker阶段: 0次额外Redis调用
- 蒸馏费率: 1次（初始化时缓存）

#### C. 前端显示修复
- `updateHistoryDescriptionCard`: 显示文章总数和开销
- `i18n.js`: 添加 `actual_cost`("开销") 和 `relevant_papers_count`("相关论文数量") 翻译

#### D. CSS颜色修复
将所有 `.distill-type` 相关CSS从紫色系改为低饱和度橙色系：
- 主色: `#b87333` (古铜色)
- 浅色: `#c9a06a` (沙金色)
- 深色: `#8b6914` (暗金色)
- 背景渐变: `#2a2016` → `#1e1e1e`

### 修改文件清单
| 文件 | 说明 |
|------|------|
| `lib/webserver/query_api.py` | API返回字段 + _calculate_distill_cost返回doi_prices |
| `lib/process/paper_processor.py` | 传递doi_prices参数，distillation_producer存储价格JSON |
| `lib/process/distill.py` | 缓存费率，从Block解析价格JSON |
| `lib/html/index.html` | 前端显示+CSS颜色修改 |
| `lib/html/static/js/i18n.js` | 翻译词条 |

---

## 修复32: 管理员页面 DataTable 增强与批量操作 (2025-12-02)

### 问题清单
1. 管理员页面列表需要分页、排序、搜索、筛选功能
2. 需要全选/勾选和批量操作功能
3. 操作成功后应使用 Toast 提示而非 alert 弹窗

### 修复内容

#### 32a: DataTable 组件扩展
- **data-table.js 新增功能**:
  - `selectable: true` - 启用勾选列
  - `idKey: 'uid'` - 行唯一标识字段
  - `batchActions: [...]` - 批量操作按钮配置
  - `getSelectedRows()` - 获取选中行数据
  - `clearSelection()` - 清空选中
  - `DataTable.showToast()` - 静态方法显示 Toast 提示
- **data-table.css 新增样式**:
  - `.data-table-checkbox-col` - checkbox 列样式
  - `.data-table-batch-bar` - 批量操作栏样式
  - `.data-table-toast-container`, `.data-table-toast` - Toast 样式
  - 深色主题适配

#### 32b: 后端批量操作 API
- `POST /api/admin/users/batch_balance` - 批量调整余额（支持增加/减少/设为）
- `POST /api/admin/users/batch_permission` - 批量调整权限
- `POST /api/admin/tasks/batch_terminate` - 批量终止任务
- `POST /api/admin/tasks/batch_pause` - 批量暂停任务
- `POST /api/admin/tasks/batch_resume` - 批量恢复任务

#### 32c: 管理员页面重构
- **dashboard.html**: 活跃任务队列集成 DataTable，支持批量终止
- **users.html**: 用户列表集成 DataTable，支持批量调整余额/权限
- **tasks.html**: 任务列表集成 DataTable（移除原有 tabs），支持批量暂停/恢复/终止

#### 32d: i18n 翻译扩展
- 新增 `admin.batch_*` 系列翻译（中英文）
- 新增 `datatable.*` 组件翻译

### 修改文件清单
| 文件 | 说明 |
|------|------|
| `lib/html/static/js/data-table.js` | 扩展：selectable、batchActions、Toast |
| `lib/html/static/css/data-table.css` | 新增：checkbox、批量操作栏、Toast 样式 |
| `lib/html/static/js/i18n.js` | 新增翻译词条 |
| `lib/webserver/admin_api.py` | 新增5个批量操作 API |
| `lib/html/admin/dashboard.html` | 重构：集成 DataTable |
| `lib/html/admin/users.html` | 重构：集成 DataTable + 批量模态框 |
| `lib/html/admin/tasks.html` | 重构：集成 DataTable（移除 tabs）|

---

## 修复33: 管理员页面刷新控制功能迁移 (2025-12-02)

### 问题清单
1. dashboard.html、users.html、tasks.html 的"用户"/"用户ID"列名需改为"用户UID"
2. 三个页面需要添加与 debug.html 相同的刷新控制功能（立即刷新、暂停/继续自动刷新、刷新间隔选择）
3. "最后更新"需改为"最后更新时间"

### 修复内容

#### 33a: i18n.js 翻译更新
| 词条 | 中文 | 英文 |
|------|------|------|
| `admin.task_user_uid` | 用户UID | User UID |
| `admin.last_update` | 最后更新时间 | Last Update Time |
| `admin.refresh_now` | 立即刷新 | Refresh Now |
| `admin.pause_auto_refresh` | 暂停自动刷新 | Pause Auto Refresh |
| `admin.resume_auto_refresh` | 继续自动刷新 | Resume Auto Refresh |
| `admin.refresh_interval` | 刷新间隔: | Refresh Interval: |
| `admin.interval_1s/2s/5s/10s/30s` | 1秒/2秒/5秒/10秒/30秒 | 1s/2s/5s/10s/30s |

#### 33b: dashboard.html 修改
- 列名从 `admin.task_user` 改为 `admin.task_user_uid`
- 添加刷新控制功能：三个控件（立即刷新、暂停/继续、间隔选择）
- 添加 JS 变量：`autoRefresh`、`timer`、`refreshInterval`
- 添加 JS 函数：`schedule()`、`toggleAutoRefresh()`、`updateRefreshInterval()`、`updateAutoToggleText()`
- 将 `setInterval(refreshData, 5000)` 改为 `schedule()` 函数

#### 33c: users.html 修改
- 添加刷新控制功能（原本没有刷新按钮和自动刷新）
- 添加 CSS 样式和 JS 逻辑
- 默认刷新间隔 5 秒

#### 33d: tasks.html 修改
- 列名从 `admin.tasks_uid` 改为 `admin.task_user_uid`
- 将单一刷新按钮替换为三控件区域
- 将 `setInterval(loadTasks, 10000)` 改为 `schedule()` 函数
- 默认刷新间隔保持 10 秒

### 修改文件清单
| 文件 | 说明 |
|------|------|
| `lib/html/static/js/i18n.js` | 添加/修改翻译词条 |
| `lib/html/admin/dashboard.html` | 列名 + 刷新控制功能 |
| `lib/html/admin/users.html` | 添加刷新控制功能 |
| `lib/html/admin/tasks.html` | 列名 + 刷新控制功能 |

---

## 修复34: 压力测试脚本蒸馏功能扩展 (2025-12-02)

### 需求
1. 注册300个用户 (autoTest1~autoTest300)，设置权限=2，余额=30000
2. 前100个用户 (autoTest1~100) 同时发起查询任务
3. 每个查询任务完成后，该用户立即发起蒸馏任务
4. 每个蒸馏任务完成后，立即下载 CSV 和 BIB 文件

### 修改内容

#### 34a: 配置常量更新
- `TOTAL_USERS`: 100 -> 300
- `ACTIVE_TEST_USERS`: 新增，值为100
- `DISTILL_QUESTION`: 新增，"使用了EEG和EMG的硬件的研究"
- `DISTILL_REQUIREMENTS`: 新增，空字符串

#### 34b: TestAccount 数据类扩展
新增字段：
- `distill_query_id`: 蒸馏查询ID
- `distill_start_time`/`distill_end_time`: 蒸馏时间
- `distill_completed`: 蒸馏完成标志
- `distill_duration`: 蒸馏耗时属性

#### 34c: TestResult 数据类扩展
新增字段：
- `successful_distillations`: 成功蒸馏数
- `failed_distillations`: 失败蒸馏数

#### 34d: APIClient 蒸馏API支持
新增方法：
- `estimate_distillation_cost(uid, original_query_id)`: 估算蒸馏费用
- `start_distillation(uid, original_query_id, question, requirements)`: 发起蒸馏

#### 34e: 测试流程重构
- 简化为单阶段流程: 查询 -> 蒸馏 -> 下载
- 新增 `_phase1_query_distill_download()` 方法
- 新增 `_query_distill_download_pipeline()` 方法（每账户独立管道）
- 新增蒸馏相关方法：`_start_distillation_for_account`, `_wait_for_distillation`, `_download_distill_results`
- 下载方法支持指定 `query_id` 参数

#### 34f: 报告增强
- 包含蒸馏成功/失败统计
- 包含蒸馏耗时统计（平均/最短/最长）
- CSV报告新增蒸馏相关列

### 修改文件清单
| 文件 | 说明 |
|------|------|
| `scripts/autopaper_scraper.py` | 完整重构支持蒸馏流程 |

---

## 修复35: 公告栏、维护模式与页面样式统一 (2025-12-02)

### 功能概述
1. **公告栏功能**: 管理员可在 `control.html` 开启公告栏，设置公告内容
2. **维护模式功能**: 管理员可开启维护模式，用户页面跳转到维护页面
3. **页面样式统一**: `login.html` 语言按钮移至卡片内部，`maintenance.html` 深色纯色风格

### 新增系统配置项
| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `announcement_enabled` | `false` | 公告栏开关 |
| `announcement_content` | `""` | 公告栏内容 |
| `maintenance_mode` | `false` | 维护模式开关 |
| `maintenance_message` | 中英文双语默认文本 | 维护公告内容 |

### 新增API接口
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/system_announcement` | GET | 获取公告栏状态和内容 |
| `/api/maintenance_status` | GET | 获取维护模式状态 |

### 修改文件清单
| 文件 | 说明 |
|------|------|
| `DB_tools/lib/db_schema.py` | 添加4个默认配置项 |
| `lib/load_data/system_settings_dao.py` | 添加8个便捷方法 |
| `lib/webserver/system_api.py` | 新增2个公开API |
| `lib/webserver/admin_api.py` | 配置接口返回新字段 |
| `lib/webserver/server.py` | 添加API路由和维护页面路由 |
| `lib/html/admin/control.html` | 添加开关和文本框 |
| `lib/html/login.html` | 公告栏+维护检查+语言按钮移至卡片内部 |
| `lib/html/index.html` | 添加公告栏和维护检查 |
| `lib/html/billing.html` | 添加维护检查 |
| `lib/html/maintenance.html` | 新建（深色纯色风格+语言按钮在卡片内部）|
| `lib/html/static/js/i18n.js` | 添加翻译词条 |

---

## 修复36: AI回复语言适配与CSV排序优化 (2025-12-02)

### 功能概述
1. **AI回复语言自动适配**: 根据用户界面语言模式（中文/英文）自动控制AI回复的语言
2. **CSV下载结果排序**: 下载的CSV文件按相关性排序，相关(Y)在前，不相关(N)在后
3. **CSV相关性文本语言适配**: Is_Relevant列根据语言显示"符合/不符"或"Relevant/Irrelevant"
4. **删除旧架构同步下载API**: 移除 `/api/download_csv` 和 `/api/download_bib` 旧接口
5. **BIB文件无头信息**: 所有BIB文件不再包含任何头信息注释

### 数据流（AI语言适配）
```
前端 index.html (i18n.getLang() → 'zh'/'en')
  ↓ payload.language
query_api.py (存入 search_params.language)
  ↓ search_params
paper_processor.py (存入 full_search_params)
  ↓ query_log
search_paper.py (替换 {language} → '中文'/'English')
  ↓ system_prompt
AI API
```

### 语言映射
| 代码 | 语言名称 |
|------|----------|
| `zh` | 中文 |
| `en` | English |

### 修改文件清单
| 文件 | 说明 |
|------|------|
| `lib/html/index.html` | startSearch/startDistillation 添加 language 参数 + 蒸馏按钮文字居中 + 清理前端遗留旧API调用 |
| `lib/webserver/query_api.py` | 接收 language 参数，存入 search_params |
| `lib/process/paper_processor.py` | 传递 language 参数，存入 full_search_params |
| `lib/process/search_paper.py` | LANGUAGE_MAP 映射，替换 {language} 占位符 |
| `lib/process/download_worker.py` | CSV 排序 + Is_Relevant列语言适配（符合/不符 或 Relevant/Irrelevant）|
| `lib/webserver/server.py` | 删除旧架构同步下载API（/api/download_csv, /api/download_bib）|
| `lib/process/export.py` | 移除BIB文件头信息 |
| `lib/html/login.html` | 登录成功消息使用 i18n.t() 本地化 |
| `lib/html/static/js/i18n.js` | 添加 login.success/failed/invalid_credentials 翻译 |

### 前端下载代码清理
删除旧架构同步下载API后，同步清理前端遗留代码：
- **删除函数**: `downloadHistoryResults` - 该函数仍调用已删除的旧API
- **替换调用**: `updateHistoryDescriptionCard` 模板中的下载按钮改用 `downloadHistoryCsv` / `downloadHistoryBib`

### CSV相关性文本映射
| 语言 | 相关 | 不相关 |
|------|------|--------|
| `zh` | 符合 | 不符 |
| `en` | Relevant | Irrelevant |

### API变更
- `POST /api/start_search` - 新增 `language` 参数（可选，默认 'zh'）
- `POST /api/start_distillation` - 新增 `language` 参数（可选，默认 'zh'）
- **已删除** `/api/download_csv` - 旧架构同步下载CSV（使用 `/api/download/create` 替代）
- **已删除** `/api/download_bib` - 旧架构同步下载BIB（使用 `/api/download/create` 替代）

---

## 修复37: 用户Token认证安全加固 (2025-12-02)

### 问题清单
1. **严重安全漏洞**: `auth.py` 中生成Token后未存储到Redis，导致后端无法验证Token
2. 前端可随意伪造uid调用任意API，没有真正的认证机制
3. 用户可以访问/操作其他用户的任务和数据

### 修复内容

#### 37a: 新建 Redis 用户会话模块
- **文件**: `lib/redis/user_session.py` (新建)
- **功能**:
  - `generate_token()`: 生成安全随机Token
  - `create_session(uid)`: 创建会话并存储到Redis
  - `get_session_uid(token)`: 验证Token并获取uid
  - `destroy_session(token)`: 销毁会话
  - `is_valid_session(token)`: 检查会话是否有效
- **TTL**: 24小时

#### 37b-37i: 认证机制集成
|| 文件 | 修改内容 |
||------|----------|
|| `lib/redis/connection.py` | 新增 `TTL_USER_SESSION = 24 * 3600` |
|| `lib/webserver/user_auth.py` (新建) | Token提取和验证函数 |
|| `lib/webserver/auth.py` | 登录时调用 `UserSession.create_session(uid)` |
|| `lib/webserver/user_api.py` | 所有端点添加Token验证 |
|| `lib/webserver/query_api.py` | 所有端点添加Token验证 |
|| `lib/webserver/server.py` | 下载API添加Token验证 |
|| `lib/html/index.html` | 27个fetch调用改用authFetch |
|| `lib/html/billing.html` | fetch调用改用authFetch |

### 安全改进对比
|| 方面 | 修复前 | 修复后 |
||------|--------|--------|
|| Token验证 | 无 | Redis存储验证 |
|| uid来源 | payload（可伪造） | Token解析（后端控制） |
|| 任务归属 | 无验证 | uid必须匹配 |
|| 数据隔离 | 无 | 只能访问自己的数据 |
|| 会话管理 | 无 | 24小时过期 |

### 新增Redis Key
- `user:session:{token}` (String, TTL 24h) - 用户会话Token→uid映射

---

## 修复38: 蒸馏功能语言参数变量名遮蔽问题 (2025-12-02)

### 问题分析
- **现象**: 蒸馏功能点击"开始蒸馏"后报错 `'str' object has no attribute 'get_text'`
- **根因**: 变量名遮蔽（Variable Shadowing）
  - 第25行 `from language import language` 导入模块
  - 第166行函数参数 `language: str = "zh"` 遮蔽了模块名
  - 第194行 `language.get_text()` 时，`language` 已变成字符串而非模块

### 修复内容
将 `process_papers_for_distillation` 函数的参数名从 `language` 改为 `user_language`，避免与导入的模块名冲突。

| 文件 | 修改内容 |
|------|----------|
| `lib/process/paper_processor.py` | 参数名 `language` → `user_language`（第166、188行）|
| `lib/process/paper_processor.py` | 注释更新（第177-178行）|
| `lib/process/paper_processor.py` | 字典赋值 `"language": user_language`（第216行）|
| `lib/webserver/query_api.py` | 调用参数 `user_language=language`（第394行）|

### 修改文件清单
- `lib/process/paper_processor.py` - 参数名 language → user_language
- `lib/webserver/query_api.py` - 调用参数名更新

---

## 修复39: 查询/蒸馏任务结果文件BUG修复与query_id显示功能 (2025-12-02)

### 问题清单
1. **BUG 1-2**: 查询/蒸馏任务CSV的"Title"列显示booktitle而非实际文章标题
2. **BUG 3**: 蒸馏任务BIB文件格式错误，每条被包裹在JSON `{"bib": "...", "price": N}` 中
3. **BUG 4**: 蒸馏任务CSV的"Source"列为空
4. **BUG 5**: 蒸馏任务CSV的"Year"列格式错误（如"2024}\n}"）
5. **新功能**: index.html显示query_id

### 根因分析
1. **Title列错误**: `_extract_bib_field()` 正则 `rf'{field}\s*=\s*...'` 会匹配到booktitle中的title子串
2. **BIB/Source/Year错误**: 蒸馏Block存储JSON格式 `{"bib": "...", "price": N}`，但读取时未解析JSON
3. **Source列空白**: 蒸馏结果的block_key是`distill:`格式，`parse_block_key`只能解析`meta:`格式

### 修复内容

#### 39a: 修复 `_extract_bib_field()` 正则表达式
| 文件 | 修改内容 |
|------|----------|
| `lib/process/download_worker.py` | 正则添加字段名前边界匹配 `(?:^|[\n\r,])\s*{field}...` |

#### 39b: 修复蒸馏Block JSON解析
| 文件 | 修改内容 |
|------|----------|
| `lib/redis/paper_blocks.py` | 新增 `_parse_distill_block_value()` 方法解析JSON提取bib |
| `lib/redis/paper_blocks.py` | `get_block_by_key()` 对distill:前缀调用JSON解析 |
| `lib/redis/paper_blocks.py` | `batch_get_papers()` 区分distill:/meta:前缀使用不同解析 |
| `lib/redis/paper_blocks.py` | `batch_get_blocks()` 区分distill:/meta:前缀使用不同解析 |

#### 39c: 修复蒸馏任务Source列提取
| 文件 | 修改内容 |
|------|----------|
| `lib/process/download_worker.py` | distill:前缀block_key使用DOI反向索引获取原始meta:block_key |

#### 39d: 新增query_id显示功能
| 文件 | 修改内容 |
|------|----------|
| `lib/html/index.html` | 搜索概览卡片新增query_id显示行 |
| `lib/html/index.html` | 历史详情卡片新增query_id显示行 |
| `lib/html/index.html` | 新增CSS样式（.query-id-row, .query-id-value）|
| `lib/html/index.html` | `showSearchSummary()` 填充summaryQueryId字段 |
| `lib/html/static/js/i18n.js` | 新增 `query_id_label` 翻译（中：任务ID / 英：Task ID）|

### 修改文件清单
| 文件 | 说明 |
|------|------|
| `lib/process/download_worker.py` | 正则表达式修复 + Source提取逻辑 |
| `lib/redis/paper_blocks.py` | 蒸馏Block JSON解析 |
| `lib/html/index.html` | 添加query_id显示 + CSS样式 |
| `lib/html/static/js/i18n.js` | 添加翻译词条 |
| `RefactoryDocs/INTERFACE_SUMMARY.md` | 文档更新 |
| `RefactoryDocs/PROGRESS_LOG.md` | 进度日志更新 |

---

## 修复40: 下载功能MySQL回源机制 (2025-12-02)

### 问题描述
- **现象**: 用户执行 `deploy_autopaperweb.sh` 清空 Redis 持久化数据后，历史查询任务结果无法下载
- **日志**: `[DownloadWorker-1] 失败: DL... (无结果数据)`
- **根因**: `download_worker.py` 直接使用 `ResultCache.get_all_results()`，该方法只从 Redis 读取，无 MySQL 回源

### Redis TTL 设置
| 参数 | 值 | 说明 |
|------|-----|------|
| `TTL_RESULT` | 7天 | `result:{uid}:{qid}` Redis 缓存过期时间 |
| MySQL 归档 | 任务完成时 | 任务完成后异步归档到 `search_result` 表 |

### 修复内容

#### 40a: 修改 `download_worker.py` 使用支持回源的方法
| 文件 | 修改内容 |
|------|----------|
| `lib/process/download_worker.py` | 导入 `search_dao` 模块 |
| `lib/process/download_worker.py` | `_generate_csv_file()` 改用 `search_dao.get_all_results()` |
| `lib/process/download_worker.py` | `_generate_bib_file()` 改用 `search_dao.get_all_results()` |

#### 40b: 增强 `search_dao.get_all_results()` 的MySQL回源逻辑
| 文件 | 修改内容 |
|------|----------|
| `lib/load_data/search_dao.py` | MySQL回源时使用DOI反向索引批量获取 `block_key` |
| `lib/load_data/search_dao.py` | 返回数据结构包含 `ai_result` 和 `block_key` 两个字段 |

### 修复后的数据流
```
下载请求 → search_dao.get_all_results(uid, qid)
    ↓
  [Step 1] 查询 Redis result:{uid}:{qid}
    ↓ (MISS)
  [Step 2] 回源 MySQL search_result 表
    ↓
  [Step 3] 使用 DOI 反向索引补充 block_key
    ↓
返回完整数据 {doi: {ai_result, block_key}}
```

### 修改文件清单
| 文件 | 说明 |
|------|------|
| `lib/process/download_worker.py` | 导入search_dao + 替换get_all_results调用 |
| `lib/load_data/search_dao.py` | 增强MySQL回源时的block_key获取 |

### 修复效果
- ✅ Redis 数据过期后（7天TTL），下载仍可从 MySQL 回源
- ✅ Redis 被清空后，已归档的历史任务仍可下载
- ✅ 回源时自动补充 `block_key`，确保 CSV 的 Source/Year 字段正确

---

## 修复41: 删除暂停/恢复功能并增强终止确认 (2025-12-18)

### 问题描述
- **BUG现象**: 用户点击暂停按钮后，进度条从0跳到100，任务无法正确暂停；点击恢复后任务无法恢复执行
- **根因**: `resume_query` 函数无法正确重启已暂停的 Worker 线程，且 pause_signal 与 terminate_signal 交互存在冲突
- **解决方案**: 彻底删除暂停/恢复功能，只保留终止功能

### 修复内容

#### 41a: 后端 Redis 层
| 文件 | 修改内容 |
|------|----------|
| `lib/redis/task_queue.py` | 删除 `_key_pause()`, `set_pause_signal()`, `clear_pause_signal()`, `is_paused()` |

#### 41b: 后端 Query DAO
| 文件 | 修改内容 |
|------|----------|
| `lib/load_data/query_dao.py` | 删除 `pause_query()`, `resume_query()` 函数 |
| `lib/load_data/query_dao.py` | `get_query_progress()` 删除 `is_paused` 字段 |

#### 41c: 后端 Scheduler
| 文件 | 修改内容 |
|------|----------|
| `lib/process/scheduler.py` | 删除 `pause_query()`, `resume_query()` 函数 |
| `lib/process/scheduler.py` | `_check_completions()` 删除 PAUSED 状态处理 |

#### 41d: 后端 Worker
| 文件 | 修改内容 |
|------|----------|
| `lib/process/worker.py` | 删除 `_run_loop()` 中 pause_signal 检查 |
| `lib/process/worker.py` | `stop_workers_for_query()` 改用 `set_terminate_signal` |

#### 41e: 后端 API
| 文件 | 修改内容 |
|------|----------|
| `lib/webserver/query_api.py` | 删除 `/api/update_pause_status`, `/api/pause_query`, `/api/resume_query` 路由和处理函数 |
| `lib/webserver/admin_api.py` | 删除 `/api/admin/tasks/pause`, `/api/admin/tasks/resume`, `/api/admin/tasks/batch_pause`, `/api/admin/tasks/batch_resume` 路由和处理函数 |
| `lib/webserver/server.py` | 删除暂停/恢复相关 POST 路由 |

#### 41f: 前端用户页面
| 文件 | 修改内容 |
|------|----------|
| `lib/html/index.html` | 删除暂停/恢复按钮和相关 JS 函数 |
| `lib/html/index.html` | 新增终止确认弹窗（HTML+CSS+JS）|
| `lib/html/index.html` | 弹窗支持中英文切换 |

#### 41g: 管理员页面
| 文件 | 修改内容 |
|------|----------|
| `lib/html/admin/tasks.html` | 删除批量暂停/恢复按钮和相关 JS 函数 |
| `lib/html/admin/tasks.html` | 删除 PAUSED 状态筛选选项 |

#### 41h: 国际化翻译
| 文件 | 修改内容 |
|------|----------|
| `lib/html/static/js/i18n.js` | 删除所有暂停/恢复相关翻译 |
| `lib/html/static/js/i18n.js` | 新增终止确认弹窗翻译 |

### 终止确认弹窗设计
- 标题: "警告" / "Warning"
- 消息: "任务终止后无法恢复，且消耗的点数不会退回，是否确认终止该任务？"
- 左侧按钮【否】: 蓝色主题高亮
- 右侧按钮【是】: 灰色背景

### 删除的 Redis Key
- `query:{uid}:{qid}:pause_signal` - 暂停信号（已删除）

### 保留的 Redis Key
- `query:{uid}:{qid}:terminate_signal` - 终止信号（保留）

---

## 修复42: 管理员终止任务功能修复 (2025-12-18)

### 问题描述
- **现象**: 管理员页面（dashboard.html/tasks.html）点击终止按钮后，后端 Worker 确实终止了，但用户页面进度条显示 100% 且永远卡住，不会自动切换到"已完成"界面
- **根因1**: 管理员 API 终止逻辑不完整，缺少 `clear_pending` 和 `update_query_status` 调用
- **根因2**: 前端进度判断只检查 `DONE`/`COMPLETED`，不检查 `CANCELLED` 状态

### 修复内容

#### 42a: 管理员 API 调用统一的终止函数
| 文件 | 修改内容 |
|------|----------|
| `lib/webserver/admin_api.py` | 添加 `cancel_query` 导入 |
| `lib/webserver/admin_api.py` | `_handle_terminate_task()` 改为调用 `cancel_query()` |
| `lib/webserver/admin_api.py` | `_handle_batch_terminate_tasks()` 改为调用 `cancel_query()` |

#### 42b: 前端进度判断添加 CANCELLED 状态
| 文件 | 修改内容 |
|------|----------|
| `lib/webserver/query_api.py` | `_handle_get_query_progress()` 的 `completed` 判断添加 `CANCELLED` 状态 |

### 修复后的数据流
```
管理员点击"终止"
  ↓
admin_api._handle_terminate_task
  ↓
query_dao.cancel_query(uid, qid)
  ├── TaskQueue.set_terminate_signal  ✓
  ├── TaskQueue.set_state('CANCELLED')  ✓
  ├── TaskQueue.clear_pending  ✓
  ├── stop_workers_for_query  ✓
  └── update_query_status  ✓
  ↓
前端轮询 /api/query_progress
  └── completed = state in ('DONE','COMPLETED','CANCELLED')  ✓
  ↓
前端停止轮询，显示终止完成界面  ✓
```

---

## 架构文档同步更新 (2025-12-02)

根据修复24-40的内容，同步更新了以下架构文档：

### 更新的文件
1. `新架构数据库关联图20251202.mmd`
   - 新增 UserSession、DOIIndex、DistillBlock、TerminateSignal Redis Key
   - 新增 SystemSettings MySQL表
   - 新增数据流关系

2. `新架构端到端业务时序图20251202.mmd`
   - 更新用户登录流程（Token认证）
   - 新增公告栏与维护模式检查章节
   - 更新任务执行循环（AI语言适配）
   - 更新蒸馏任务流程（蒸馏专用Block）
   - 更新结果下载（Token验证+CSV排序）
   - 新增API请求Token认证通用流程章节

3. `新架构管理员时序图20251202.mmd`
   - 更新任务管理（使用terminate_signal）
   - 新增批量操作章节（5个批量API）
   - 新增系统配置管理章节（公告栏/维护模式）

4. `新架构项目重构完整指导文件20251130.txt`
   - 更新第1章：用户Token认证机制
   - 新增第9.5章：API请求Token认证规范
   - 新增第9.6章：公告栏与维护模式
   - 更新第14章：蒸馏专用Block设计+DOI反向索引
   - 更新第16章：批量操作API+DataTable+刷新控制
   - 新增第17.5章：AI语言适配机制
   - 新增第17.6章：Redis Key完整汇总
   - 更新第17.4章：system_settings表SQL定义

---

## 恢复指南

如果你是新的Agent会话，请：
1. 阅读本文档了解重构成果和修复历史
2. 查看 `RefactoryDocs/PROGRESS_LOG.md` 了解详细进度
3. 查看 `RefactoryDocs/前端重构设计文档20251129.md` 了解前端重构规划
4. 查看 `需要手动操作的事项.txt` 了解待完成操作
5. 项目重构已基本完成，经过四十二轮Bug修复，可进行测试

---

## 关键参考文件

- `新架构项目重构完整指导文件20251130.txt` - 完整设计指导
- `RefactoryDocs/PROGRESS_LOG.md` - 进度日志
- `需要手动操作的事项.txt` - 人工操作清单
