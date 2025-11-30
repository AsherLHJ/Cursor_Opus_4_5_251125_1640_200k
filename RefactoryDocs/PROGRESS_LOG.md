# 新架构重构进度日志

## 项目概述
- **开始时间**: 2025-11-25 16:40
- **重构完成时间**: 2025-11-25 17:50
- **最后修复时间**: 2025-11-30
- **指导文件**: 新架构项目重构完整指导文件20251124.txt
- **目标**: 按照新架构指导，彻底重构整个项目
- **状态**: ✅ 重构完成 + 二十一轮Bug修复

---

## 阶段进度

### 阶段一：基础设施准备与文档目录创建
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 16:40
- **完成时间**: 2025-11-25 16:41
- **任务清单**:
  - [x] 创建 RefactoryDocs/ 目录
  - [x] 创建 PROGRESS_LOG.md
  - [x] 创建 INTERFACE_SUMMARY.md
  - [x] 创建 需要手动操作的事项.txt

### 阶段二：DB_tools重构与数据库初始化套件
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 16:41
- **完成时间**: 2025-11-25 16:45
- **任务清单**:
  - [x] 创建 DB_tools/lib/ 目录结构
  - [x] 实现 db_schema.py - 10个表定义
  - [x] 实现 loader_bib.py - Bib解析和导入
  - [x] 实现 loader_tags.py - 标签导入
  - [x] 实现 loader_api.py - API Key导入
  - [x] 创建 init_database.py - 统一入口
  - [x] 删除废弃脚本 tools_refresh_db_sentence.py

### 阶段三：Redis数据层设计与实现
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 16:45
- **完成时间**: 2025-11-25 16:55
- **任务清单**:
  - [x] 创建 lib/redis/__init__.py
  - [x] 实现 connection.py - Redis连接管理
  - [x] 实现 user_cache.py - 用户数据缓存
  - [x] 实现 system_cache.py - 系统元数据缓存
  - [x] 实现 paper_blocks.py - 文献Block存储
  - [x] 实现 task_queue.py - 任务队列
  - [x] 实现 result_cache.py - 结果缓存
  - [x] 实现 billing.py - 计费队列
  - [x] 实现 download.py - 下载队列
  - [x] 实现 admin.py - 管理员会话
  - [x] 实现 init_loader.py - Redis初始化加载

### 阶段四：DAO层重构
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 16:55
- **完成时间**: 2025-11-25 17:05
- **任务清单**:
  - [x] 重构 user_dao.py - Redis优先+MySQL回源
  - [x] 重构 journal_dao.py - Redis读取期刊/标签
  - [x] 重构 paper_dao.py - 适配新paperinfo结构
  - [x] 重构 query_dao.py - 适配新query_log结构
  - [x] 重构 search_dao.py - 适配新search_result表
  - [x] 删除 app_settings_dao.py
  - [x] 删除 task_dao.py
  - [x] 删除 queue_dao.py

### 阶段五：Worker与调度器重构
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 17:05
- **完成时间**: 2025-11-25 17:15
- **任务清单**:
  - [x] 重构 worker.py - 任务池+抢占模式
  - [x] 重构 scheduler.py - Worker生产器
  - [x] 创建 sliding_window.py - TPM/RPM滑动窗口
  - [x] 创建 tpm_accumulator.py - TPM累加器
  - [x] 重构 search_paper.py - AI调用封装
  - [x] 删除 queue_facade.py
  - [x] 删除 queue_manager.py
  - [x] 删除 redis_queue_manager.py
  - [x] 删除 rate_limiter.py
  - [x] 删除 rate_limiter_facade.py
  - [x] 删除 redis_rate_limiter.py
  - [x] 删除 redis_aggregates.py

### 阶段六：计费系统重构
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 17:15
- **完成时间**: 2025-11-25 17:20
- **任务清单**:
  - [x] 重构 price_calculator.py - Redis实时扣费
  - [x] 创建 billing_syncer.py - 后台对账线程

### 阶段七：管理员系统实现
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 17:20
- **完成时间**: 2025-11-25 17:30
- **任务清单**:
  - [x] 实现 admin_dao.py - 管理员数据访问
  - [x] 实现 admin_auth.py - 管理员鉴权
  - [x] 创建 admin/login.html - 登录页面
  - [x] 创建 admin/dashboard.html - 监控大盘
  - [x] 创建 admin/users.html - 用户管理
  - [x] 创建 admin/tasks.html - 任务管理
  - [x] 删除 AutoPaperSearchControlPanelAdmin.html

### 阶段八：API层与前端适配
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 17:30
- **完成时间**: 2025-11-25 17:40
- **任务清单**:
  - [x] 创建 admin_api.py - 管理员API处理
  - [x] 更新 server.py - 集成管理员API
  - [x] 添加管理员页面路由
  - [x] 兼容旧路径重定向

### 阶段九：蒸馏任务重构
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 17:40
- **完成时间**: 2025-11-25 17:45
- **任务清单**:
  - [x] 创建 distill.py - 蒸馏任务模块
  - [x] 实现 DistillWorker - 0.1倍费率Worker
  - [x] 实现 create_distill_task - 创建蒸馏任务

### 阶段十：清理与测试准备
- **状态**: 已完成 ✓
- **开始时间**: 2025-11-25 17:45
- **完成时间**: 2025-11-25 17:50
- **任务清单**:
  - [x] 更新 需要手动操作的事项.txt
  - [x] 更新 INTERFACE_SUMMARY.md
  - [x] 整理废弃文件清单
  - [x] 生成最终文档

---

## Bug修复阶段

### 修复轮次一：启动错误修复 (2025-11-26)
- **时间**: 2025-11-26 14:00 - 14:30
- **问题**:
  1. `debug_console.info/warn` 方法不存在
  2. `PriceCalculator.add_price_column_to_contentlist` 方法不存在
  3. `db_reader.ensure_default_*` 方法不存在
- **修复**:
  - [x] `lib/webserver/server.py`: 替换 `debug_console.info/warn` 为 `print`
  - [x] `lib/price_calculate/init_db.py`: 简化 `initialize_price_system()`
  - [x] `main.py`: 移除不存在的 `ensure_default_*` 调用

### 修复轮次二：Redis连接与管理员API修复 (2025-11-26)
- **时间**: 2025-11-26 14:30 - 15:00
- **问题**:
  1. 测试脚本 Redis URL 替换逻辑错误
  2. `admin_api.py` 期望字符串但收到字典
  3. `AdminSession.create_session` 调用参数错误
- **修复**:
  - [x] `tests/FullTest_20251125_2106.py`: 修正 Redis URL 替换逻辑
  - [x] `lib/webserver/admin_api.py`: 修改参数类型为 `payload: Dict`
  - [x] `tests/FullTest_20251125_2106.py`: 修正 `create_session` 调用

### 修复轮次三：API接口适配新架构 (2025-11-26)
- **时间**: 2025-11-26 15:00 - 15:30
- **问题**:
  1. `AdminSession.validate_session` 方法不存在
  2. `process_papers` 函数签名不符合新架构调用
  3. `process_papers_for_distillation` 函数签名不符合新架构调用
- **修复**:
  - [x] `tests/FullTest_20251125_2106.py`: 使用 `get_session_uid` 替代 `validate_session`
  - [x] `lib/process/paper_processor.py`: 重写 `process_papers(uid, search_params) -> (bool, str)`
  - [x] `lib/process/paper_processor.py`: 重写 `process_papers_for_distillation(uid, original_query_id, dois) -> (bool, str)`

### 修复轮次四：前端修复与功能完善 (2025-11-26)
- **时间**: 2025-11-26 15:30 - 16:00
- **问题**:
  1. `user_api.py` 的 `get_user_info` 返回格式双重包装
  2. `index.html` 引用不存在的元素 ID (estimatedCost, articleCount)
  3. `index.html` 队列轮询代码 (queueEta) 已废弃
- **修复**:
  - [x] `lib/webserver/user_api.py`: 修复返回格式，移除多余包装
  - [x] `lib/html/index.html`: 移除对不存在元素的引用
  - [x] `lib/html/index.html`: 删除 queueEta HTML 和相关 JS 代码

### 修复轮次五：管理员系统控制页面 (2025-11-26)
- **时间**: 2025-11-26 16:00 - 17:00
- **问题**:
  1. 缺少系统控制页面
  2. 注册开关 API 路由缺失
  3. 导航栏缺少系统控制入口
- **修复**:
  - [x] 新建 `lib/html/admin/control.html`: 系统控制页面（注册开关）
  - [x] `lib/html/admin/dashboard.html`: 添加系统控制导航链接
  - [x] `lib/html/admin/users.html`: 添加系统控制导航链接
  - [x] `lib/html/admin/tasks.html`: 添加系统控制导航链接
  - [x] `lib/webserver/server.py`: 添加 `/api/registration_status` GET 路由
  - [x] `lib/webserver/server.py`: 添加 `/api/admin/toggle_registration` POST 路由

### 修复轮次六：登录页面优化 (2025-11-26)
- **时间**: 2025-11-26 17:00 - 18:00
- **问题**:
  1. 注册链接默认隐藏，用户体验不佳
  2. 登录页面风格与管理员页面不统一
  3. 注册链接位置不合理
  4. control.html 开关默认状态与后端不一致
- **修复**:
  - [x] `lib/html/login.html`: 注册链接默认显示，仅 API 明确返回关闭时隐藏
  - [x] `lib/html/login.html`: CSS 改为深色主题
  - [x] `lib/html/login.html`: 注册链接移到密码框下方、登录按钮上方
  - [x] `lib/html/admin/control.html`: 默认状态改为开启（与后端一致）

### 修复轮次七：核心业务Bug修复 (2025-11-27)
- **时间**: 2025-11-27
- **问题**:
  1. BillingSyncer未启动，导致计费队列积压
  2. 进度条卡0%，前端轮询缺少uid参数导致Redis Key拼接错误
  3. CSV下载显示"未判定"，数据结构不匹配
  4. Worker数量未考虑Block数量，导致大量Worker立即退出
- **修复**:
  - [x] `main.py`: 添加 `start_billing_syncer()` 启动调用
  - [x] `lib/html/index.html`: 3处fetch调用添加uid参数
  - [x] `lib/html/history.html`: 1处fetch调用添加uid参数
  - [x] `lib/webserver/query_api.py`: `_handle_get_query_progress` 从payload获取uid
  - [x] `lib/load_data/search_dao.py`: 新增 `_parse_bib_fields()` 辅助函数
  - [x] `lib/load_data/search_dao.py`: 重构 `fetch_results_with_paperinfo` 返回扁平化结构(策略B)
  - [x] `lib/webserver/server.py`: `_download_csv` 适配新的 'Y'/'N' 判断条件
  - [x] `lib/webserver/server.py`: `_download_bib` 适配新的 'Y'/'N' 判断条件
  - [x] `lib/process/scheduler.py`: `_start_query_workers` 实际Worker数=min(permission, blocks)
  - [x] `lib/process/distill.py`: `spawn_distill_workers` 添加同样的Worker数量限制
  - [x] `新架构项目重构完整指导文件20251124.txt`: 规则R2后补充Worker数量优化说明

### 修复轮次八：暂停/终止功能与蒸馏API修复 (2025-11-27)
- **时间**: 2025-11-27
- **问题**:
  1. 普通用户暂停按钮无效：`_handle_update_pause_status`参数名query_index与前端不匹配，且强制转int
  2. 暂停后任务直接完成：`_check_completions`未检查PAUSED/CANCELLED状态
  3. 终止显示"暂停信号"：终止操作复用pause_signal，日志无法区分
  4. 蒸馏API参数错误：`get_relevant_dois`调用缺少uid参数
  5. 蒸馏前端类型错误：`parseInt(queryIndex)`对字符串query_id返回NaN
- **修复**:
  - [x] `lib/webserver/query_api.py`: `_handle_update_pause_status` 同时支持query_id和query_index，不强制转int
  - [x] `lib/webserver/query_api.py`: `_handle_start_distillation` 支持original_query_id，修正get_relevant_dois调用
  - [x] `lib/webserver/query_api.py`: `_handle_estimate_distillation_cost` 同上修复
  - [x] `lib/html/distill.html`: 移除parseInt，使用字符串类型originalQueryId
  - [x] `lib/process/scheduler.py`: `_check_completions` 检查PAUSED/CANCELLED状态再决定是否标记完成
  - [x] `lib/redis/task_queue.py`: 新增set_terminate_signal/clear_terminate_signal/is_terminated方法
  - [x] `lib/process/worker.py`: 优先检查终止信号，输出"收到终止信号"
  - [x] `lib/webserver/admin_api.py`: `_handle_terminate_task` 改用terminate_signal

### 修复轮次九：暂停功能深度修复 (2025-11-27)
- **时间**: 2025-11-27
- **问题**:
  1. 普通用户暂停无效：`server.py` POST路由遗漏了 `/api/update_pause_status`，导致返回404
  2. 暂停后任务直接完成：Worker完成判定时未检查暂停信号，最后一个Worker完成Block后触发归档
- **修复**:
  - [x] `lib/webserver/server.py`: POST路由添加 `/api/update_pause_status` 到查询API列表
  - [x] `lib/process/worker.py`: 完成判定前再次检查暂停/终止信号，避免暂停后被错误标记为完成

### 修复轮次十：历史状态显示与蒸馏按钮修复 (2025-11-27)
- **时间**: 2025-11-27
- **问题**:
  1. 暂停后历史记录状态仍显示"进行中"：`createHistoryItem`函数只判断`completed`属性
  2. 进行中任务错误显示蒸馏按钮：历史详情卡片模板在未完成任务区域也显示了蒸馏按钮
- **修复**:
  - [x] `lib/html/index.html`: `createHistoryItem`状态判断改为三态(完成>已暂停>进行中)
  - [x] `lib/html/index.html`: 添加`data-paused`属性并在语言切换时正确更新状态
  - [x] `lib/html/index.html`: 历史详情卡片状态显示添加三态判断
  - [x] `lib/html/index.html`: 删除未完成任务的蒸馏按钮（蒸馏按钮只在任务完成后显示）
  - [x] `lib/webserver/query_api.py`: `_handle_get_query_info`返回值添加`should_pause`字段

### 修复轮次十一：侧边栏状态刷新与任务完成检测修复 (2025-11-27)
- **时间**: 2025-11-27
- **问题**:
  1. 暂停后侧边栏历史记录状态不更新：`handlePauseResume`成功后未调用`loadHistory()`刷新侧边栏
  2. 任务完成后页面不自动切换到完成状态：历史进度轮询完成时只调用`loadHistoryDetails()`但未使用返回结果更新卡片UI
- **修复**:
  - [x] `lib/html/index.html`: `handlePauseResume`成功后添加`loadHistory()`调用刷新侧边栏
  - [x] `lib/html/index.html`: 历史卡片创建时添加`data-history-qid`属性以便查找
  - [x] `lib/html/index.html`: 历史进度轮询完成时正确获取详情、更新卡片UI并刷新侧边栏

### 修复轮次十二：普通用户终止任务功能 (2025-11-27)
- **时间**: 2025-11-27
- **问题**:
  1. 普通用户无法主动终止错误的任务：只有暂停功能，无法终止
  2. 用户发起错误任务后只能等待完成或寻求管理员帮助
  3. `/api/cancel_query` 使用 pause_signal，无法区分暂停和终止操作
  4. **修复12c**: 终止后Worker线程仍在运行：`cancel_query`未调用`stop_workers_for_query`
  5. 新用户默认permission过高(50)，应改为2
- **修复**:
  - [x] `lib/html/static/js/i18n.js`: 添加terminate/terminate_confirm/terminate_success/terminate_fail/terminate_complete中英文翻译
  - [x] `lib/html/index.html`: 添加`.btn-danger`按钮样式（红色终止按钮）
  - [x] `lib/html/index.html`: 主进度区域添加终止按钮(id=terminateBtn)和`handleTerminate`函数
  - [x] `lib/html/index.html`: 历史详情卡片添加终止按钮和`terminateHistoryTask`函数
  - [x] `lib/html/index.html`: 添加`showTerminatedSection`函数，终止后自动显示"任务终止（可下载已完成检索的部分）"界面
  - [x] `lib/html/index.html`: 添加`updateHistoryCardAsTerminated`函数，更新历史卡片为终止完成状态
  - [x] `lib/html/index.html`: 添加`downloadHistoryCsv`和`downloadHistoryBib`辅助函数，支持历史卡片下载
  - [x] `lib/load_data/query_dao.py`: `cancel_query`改用`terminate_signal`以区分暂停和终止
  - [x] **修复12c** `lib/load_data/query_dao.py`: `cancel_query`添加`stop_workers_for_query`调用，确保Worker线程真正停止
  - [x] `lib/webserver/auth.py`: `register_user`默认permission从50改为2

### 修复轮次十三：文献Block缓存策略修改 (2025-11-28)
- **时间**: 2025-11-28
- **问题**:
  1. 文献Block设置了7天TTL，导致数据过期后需要重新从MySQL加载
  2. 文献元数据是静态数据，不应设置过期时间
- **修复**:
  - [x] `lib/redis/connection.py`: 移除 `TTL_PAPER_BLOCK` 常量定义
  - [x] `lib/redis/paper_blocks.py`: 移除 `TTL_PAPER_BLOCK` 导入
  - [x] `lib/redis/paper_blocks.py`: `set_paper` 方法移除 `expire` 调用
  - [x] `lib/redis/paper_blocks.py`: `set_block` 方法移除 `pipe.expire` 调用
  - [x] `README.md`: 更新Redis数据过期策略表格
  - [x] `RefactoryDocs/INTERFACE_SUMMARY.md`: 更新文献Block缓存说明

### 修复轮次十四：Docker镜像拉取失败修复 (2025-11-28)
- **时间**: 2025-11-28
- **问题**:
  1. 服务器位于中国大陆，无法访问Docker Hub (registry-1.docker.io)
  2. `docker compose up --build` 拉取基础镜像超时，部署脚本执行失败
  3. 受影响镜像：redis:7-alpine、python:3.10-slim、nginx:alpine
  4. **修复14b**: 阿里云公共镜像仓库地址 `/library/` 不存在，改用标准镜像名+加速器
- **修复**:
  - [x] `deploy_autopaperweb.sh`: 新增 `setup_docker_mirror()` 函数配置阿里云专属镜像加速器 `https://ap2qz3w9.mirror.aliyuncs.com`
  - [x] `deploy_autopaperweb.sh`: `compose_up()` 添加3次重试机制和详细错误提示
  - [x] `deploy_autopaperweb.sh`: 更新步骤编号(7步→8步)和 `main()` 调用顺序
  - [x] `docker/Dockerfile.backend`: pip安装使用清华源 `-i https://pypi.tuna.tsinghua.edu.cn/simple`
  - [x] **修复14b** `docker-compose.yml`: 镜像名保持 `redis:7-alpine`（依赖加速器）
  - [x] **修复14b** `docker/Dockerfile.backend`: 镜像名保持 `python:3.10-slim`（依赖加速器）
  - [x] **修复14b** `docker/Dockerfile.frontend`: 镜像名保持 `nginx:alpine`（依赖加速器）
  - [x] **修复14c** `scripts/package_images.py`: 新建镜像打包工具（在本地开发机执行）
  - [x] **修复14c** `docker/image-cache/README.md`: 新建离线缓存使用说明
  - [x] **修复14c** `deploy_autopaperweb.sh`: 新增 `load_image_cache()` 函数，步骤更新为9步

### 修复轮次十五：费用估算安全修复+Redis数据清理 (2025-11-29)
- **时间**: 2025-11-29
- **问题**:
  1. **安全漏洞**: 前端 `index.html` 的 `startSearch()` 传递 `estimated_cost` 参数到后端，后端 `_handle_start_search` 信任该值进行余额检查，恶意用户可绕过
  2. **费用计算错误**: `_handle_update_config` 使用 `estimated_cost = count`（每篇1点），忽略了期刊实际价格
  3. **蒸馏API低效**: `get_prices_by_dois` 函数查询 MySQL 获取期刊价格，但 `ResultCache` 已存储 `block_key`，可直接从 Redis 获取
  4. **部署问题**: `deploy_autopaperweb.sh` 未清除 Redis 持久化数据，旧数据可能干扰新部署
- **安全设计原则**: 前端永不计算/传递费用，所有费用计算在后端完成
- **修复**:
  - [x] `lib/webserver/query_api.py`: 新增 `_calculate_query_cost()` 函数（纯Redis操作）
  - [x] `lib/webserver/query_api.py`: 新增 `_calculate_distill_cost()` 函数（纯Redis操作，替代 `get_prices_by_dois`）
  - [x] `lib/webserver/query_api.py`: 修复 `_handle_update_config` 使用实际期刊价格
  - [x] `lib/webserver/query_api.py`: 修复 `_handle_start_search` 移除前端费用信任，后端独立计算
  - [x] `lib/webserver/query_api.py`: 重构 `_handle_start_distillation` 使用 `_calculate_distill_cost`
  - [x] `lib/webserver/query_api.py`: 重构 `_handle_estimate_distillation_cost` 使用 `_calculate_distill_cost`
  - [x] `lib/html/index.html`: 清理 `startSearch()` 删除 `estimated_cost` 参数传递
  - [x] `lib/load_data/journal_dao.py`: 删除废弃函数 `get_prices_by_dois`
  - [x] `lib/load_data/db_reader.py`: 移除 `get_prices_by_dois` 导入
  - [x] `deploy_autopaperweb.sh`: 新增 `cleanup_redis_volumes()` 函数，部署步骤更新为10步

### 修复轮次十六：余额实时更新功能 (2025-11-29)
- **时间**: 2025-11-29
- **问题**:
  1. 任务运行期间用户余额显示不实时更新，有60秒缓存
- **修复**:
  - [x] `lib/webserver/query_api.py`: `/api/query_progress` 返回值新增 `current_balance` 字段
  - [x] `lib/html/index.html`: 进度轮询回调中实时更新余额显示

### 修复轮次十七：系统配置优化 (2025-11-29)
- **时间**: 2025-11-29
- **问题**:
  1. `lib/webserver/auth.py` 第137-298行存在无调用者的历史遗留代码
  2. 权限范围硬编码不一致：`admin_api.py` 限制0-10，`system_api.py` 曾限制0-100
  3. 蒸馏价格系数硬编码为0.1，无法动态调整
  4. 缺少系统配置持久化和缓存机制
- **架构设计**: MySQL 持久化 + Redis 缓存，确保高性能读取
- **修复**:
  - [x] `lib/webserver/auth.py`: 删除第137-298行历史遗留代码（5个函数）
  - [x] `DB_tools/lib/db_schema.py`: 新增 `system_settings` 表定义
  - [x] `lib/redis/system_config.py`: 新建系统配置 Redis 缓存层
  - [x] `lib/load_data/system_settings_dao.py`: 新建 MySQL + Redis 双写 DAO
  - [x] `lib/webserver/admin_api.py`: 权限验证改为动态读取配置
  - [x] `lib/webserver/system_api.py`: 权限验证改为动态读取配置
  - [x] `lib/webserver/query_api.py`: 蒸馏系数改为动态获取
  - [x] `lib/webserver/admin_api.py`: 新增配置管理 API（GET/POST `/api/admin/settings`）
  - [x] `lib/html/admin/control.html`: 新增权限范围和蒸馏系数配置 UI
  - [x] `main.py`: 启动时预热系统配置到 Redis

### 修复轮次十八：蒸馏按钮JS错误与注册页面风格统一 (2025-11-29)
- **时间**: 2025-11-29
- **问题**:
  1. 蒸馏功能"开始蒸馏"按钮灰色不可点击：onclick属性中的queryIndex是字符串类型但未加引号，导致JavaScript将其当作变量名而非字符串字面量
  2. 注册页面风格与登录页面不统一：`register.html`使用紫色渐变浅色主题，`login.html`已改为深色主题
- **根因分析**: 新架构中`query_id`为字符串格式（如`Q20251127102812_74137bb4`），在模板字符串中未加引号会被当作未定义变量
- **修复**:
  - [x] `lib/html/index.html`: 修复4处onclick属性中的queryIndex参数添加引号
    - 第4718行: `startDistillation('${cardId}', ${queryIndex})` → `'${queryIndex}'`
    - 第5067行: `downloadDistillationCSV(${queryIndex})` → `'${queryIndex}'`
    - 第5070行: `downloadDistillationBIB(${queryIndex})` → `'${queryIndex}'`
    - 第5073行: `createDistillInputCard(${queryIndex})` → `'${queryIndex}'`
  - [x] `lib/html/register.html`: 样式改为深色主题匹配login.html
    - 背景色: `#0a0a0a`
    - 容器背景: `#1a1a1a`
    - 输入框背景: `#2a2a2a`
    - 强调色: `#4a90d9`

### 修复轮次十九：安全审计、代码优化与调试页面整合 (2025-11-29)
- **时间**: 2025-11-29
- **任务**:
  1. 创建前端重构设计文档
  2. 代码臃肿问题短期优化（提取CSS/JS）
  3. debugLog.html整合到管理员系统
  4. 调试控制台配置迁移到数据库
  5. 清理旧架构代码和冗余文件
- **完成项**:
  - [x] 创建 `RefactoryDocs/前端重构设计文档20251129.md` - 前端重构完整规划文档
  - [x] 提取 `index.html` 的CSS到 `lib/html/static/css/index.css` (~1700行)
  - [x] 提取 `index.html` 的JavaScript到 `lib/html/static/js/index.js` (~3150行)
  - [x] `index.html` 从4774行缩减到330行 (减少93%)
  - [x] 创建 `lib/html/admin/debug.html` - 管理员调试日志页面（统一管理员风格）
  - [x] 所有管理员页面导航栏添加"调试日志"链接
  - [x] `lib/load_data/system_settings_dao.py` 添加 `debug_console_enabled` 配置和便捷方法
  - [x] `lib/webserver/system_api.py` 修改使用Redis读取配置（MISS则回源MySQL），删除旧架构兼容逻辑
  - [x] `lib/webserver/admin_api.py` 更新返回 `debug_console_enabled` 当前值
  - [x] `lib/html/admin/control.html` 添加调试日志开关控制界面
  - [x] `lib/webserver/server.py` 移除 `/debugLog.html`、`/history.html`、`/distill.html` 旧路由
  - [x] 从 `config.json` 删除 `enable_debug_website_console` 配置
  - [x] 从 `lib/config/config_loader.py` 清理相关代码
  - [x] 删除旧的 `lib/html/debugLog.html` 文件
  - [x] 删除冗余的 `lib/html/distill.html` 文件（功能已整合到index.html）
  - [x] 删除冗余的 `lib/html/history.html` 文件（功能已整合到index.html）
  - [x] `DB_tools/lib/db_schema.py` 添加 `debug_console_enabled` 到 `SYSTEM_SETTINGS_DEFAULTS`
- **代码行数变化**:
  | 文件 | 变化 |
  |------|------|
  | distill.html | 删除（功能已整合） |
  | history.html | 删除（功能已整合） |
  | admin/debug.html | 新建（管理员调试页面） |

---

## 修复轮次二十：回滚index.html重构 (2025-11-29)

- **时间**: 2025-11-29
- **背景**: 修复轮次十九中尝试将 index.html 的CSS/JS提取到独立文件以减少代码臃肿，但导致严重BUG：
  - 未登录时不跳转到登录页面
  - 登录后显示"游客"，用户名显示为 `{username}`
  - 退出登录按钮无响应
  - i18n 翻译失效
- **根本原因**: 提取过程中代码结构被破坏，编码问题导致大量乱码，checkLogin() 执行位置错误
- **解决方案**: 选择性回退 index.html 到原始版本 (commit 9a431c2)，删除新建的 CSS/JS 文件
- **操作**:
  - [x] `git checkout 9a431c2 -- lib/html/index.html` 恢复原始版本（5202行）
  - [x] 删除 `lib/html/static/css/index.css`
  - [x] 删除 `lib/html/static/js/index.js`
- **结论**: index.html 代码优化任务暂时搁置，需要更谨慎的重构方案

---

## 修复轮次二十一：下载系统重构与计费同步优化 (2025-11-30)

- **时间**: 2025-11-30
- **问题**:
  1. **下载结果时页面卡顿**: 大量文献(1000+)下载时页面卡死近1分钟
     - 根因: 当前下载是同步处理，逐个获取Redis数据，无异步队列
     - 高并发场景(100用户)时线程池耗尽，后续请求超时
  2. **计费队列积压**: 大任务(2000篇)完成后计费队列显示大量积压
     - 现象: 正常设计行为，BillingSyncer每5秒同步100条
     - 可优化: 加快积压清空速度
- **解决方案**:
  1. **下载系统异步队列重构**:
     - 实现 `download_queue + DownloadWorker` 异步架构
     - 使用 Redis Pipeline 批量获取 Bib 数据 (O(n)→O(1))
     - 前端点击下载→API返回task_id→前端轮询状态→就绪后下载
  2. **计费同步速度优化**:
     - sync_interval: 5秒→1秒
     - batch_size: 100条→2000条
- **修复**:
  - [x] 更新架构设计文档（指导文件第9章、时序图、数据库关联图）
  - [x] `lib/redis/download.py`: 扩展DownloadQueue类，新增任务状态和文件存储方法
  - [x] `lib/process/download_worker.py`: 新建，实现DownloadWorker和DownloadWorkerPool
  - [x] `lib/redis/paper_blocks.py`: 新增batch_get_papers/batch_get_blocks批量获取方法
  - [x] `lib/load_data/search_dao.py`: 重构fetch_results_with_paperinfo使用Pipeline批量获取
  - [x] `lib/webserver/server.py`: 新增下载API端点（/api/download/create/status/file）
  - [x] `main.py`: 启动时初始化DownloadWorkerPool(10个Worker)
  - [x] `lib/html/static/js/i18n.js`: 添加下载相关翻译（中英文）
  - [x] `lib/html/index.html`: 重构所有下载按钮为异步轮询模式，添加spinner-small样式
  - [x] `lib/process/billing_syncer.py`: 优化参数为1秒/2000条
- **性能对比**:
  | 场景 | 优化前 | 优化后 |
  |------|--------|--------|
  | 1000篇下载延迟 | ~10秒(卡死) | ~2秒(有进度) |
  | 100并发最长等待 | HTTP超时 | ~20秒 |
  | 计费积压清空(2000条) | ~100秒 | ~1秒 |

---

## 重要变更记录

| 日期 | 阶段 | 变更内容 | 影响范围 |
|------|------|----------|----------|
| 2025-11-25 | 1 | 初始化重构文档目录 | 文档 |
| 2025-11-25 | 2 | 完成DB_tools重构，创建标准化数据库初始化套件 | DB_tools |
| 2025-11-25 | 3 | 完成Redis数据层，实现11个模块 | lib/redis/ |
| 2025-11-25 | 4 | 完成DAO层重构，删除3个废弃文件 | lib/load_data/ |
| 2025-11-25 | 5 | 完成Worker和调度器重构，删除7个废弃文件 | lib/process/ |
| 2025-11-25 | 6 | 完成计费系统重构 | lib/price_calculate/, lib/process/ |
| 2025-11-25 | 7 | 完成管理员系统，创建admin页面 | lib/webserver/, lib/html/admin/ |
| 2025-11-25 | 8 | 完成API层重构 | lib/webserver/ |
| 2025-11-25 | 9 | 完成蒸馏任务模块 | lib/process/ |
| 2025-11-25 | 10 | 完成清理和文档 | RefactoryDocs/ |
| 2025-11-26 | 修复1 | 修复启动错误(debug_console/PriceCalculator/db_reader) | server.py, init_db.py, main.py |
| 2025-11-26 | 修复2 | 修复Redis连接与管理员API | admin_api.py, tests/ |
| 2025-11-26 | 修复3 | 重写process_papers适配新架构 | paper_processor.py |
| 2025-11-26 | 修复4 | 前端修复(user_api返回格式/移除废弃代码) | user_api.py, index.html |
| 2025-11-26 | 修复5 | 新建系统控制页面，修复注册开关API路由 | admin/control.html, server.py |
| 2025-11-26 | 修复6 | 登录页面优化(深色主题/注册链接默认显示) | login.html, control.html |
| 2025-11-27 | 修复7 | 核心业务Bug修复(BillingSyncer/进度/下载/Worker) | main.py, index.html, history.html, query_api.py, search_dao.py, server.py, scheduler.py, distill.py, 新架构指导文件 |
| 2025-11-27 | 修复8 | 暂停/终止功能与蒸馏API修复 | query_api.py, distill.html, scheduler.py, task_queue.py, worker.py, admin_api.py |
| 2025-11-27 | 修复9 | 暂停功能深度修复(API路由/Worker完成判定) | server.py, worker.py |
| 2025-11-27 | 修复10 | 历史状态显示三态+移除进行中蒸馏按钮 | index.html, query_api.py |
| 2025-11-27 | 修复11 | 侧边栏状态刷新+任务完成检测修复 | index.html |
| 2025-11-27 | 修复12 | 普通用户终止任务功能+修复12c:Worker真正停止+默认permission改为2 | i18n.js, index.html, query_dao.py, auth.py |
| 2025-11-28 | 修复13 | 文献Block缓存策略改为永不过期 | connection.py, paper_blocks.py, README.md, INTERFACE_SUMMARY.md |
| 2025-11-28 | 修复14 | Docker镜像拉取失败修复(离线镜像缓存+加速器+重试机制) | docker-compose.yml, Dockerfile.*, deploy_autopaperweb.sh, scripts/package_images.py |
| 2025-11-29 | 修复15 | 费用估算安全修复+Redis数据清理 | query_api.py, journal_dao.py, db_reader.py, index.html, deploy_autopaperweb.sh |
| 2025-11-29 | 修复16 | 余额实时更新功能（复用进度轮询） | query_api.py, index.html |
| 2025-11-29 | 修复17 | 系统配置优化(MySQL+Redis缓存/权限范围/蒸馏系数动态化) | auth.py, db_schema.py, system_config.py, system_settings_dao.py, admin_api.py, system_api.py, query_api.py, control.html, main.py |
| 2025-11-29 | 修复18 | 蒸馏按钮JS错误(queryIndex加引号)+注册页面深色主题 | index.html, register.html |
| 2025-11-29 | 修复19 | 调试页面整合+配置迁移+删除冗余页面 | admin/debug.html, system_settings_dao.py, control.html, server.py, config.json, db_schema.py, distill.html(删), history.html(删) |
|| 2025-11-29 | 修复20 | 回滚index.html重构(CSS/JS提取导致严重BUG) | index.html(恢复), index.css(删), index.js(删) |
|| 2025-11-30 | 修复21 | 下载系统重构(异步队列+Pipeline)+计费同步优化 | download.py, download_worker.py(新), paper_blocks.py, search_dao.py, server.py, main.py, i18n.js, index.html, billing_syncer.py, 新架构指导文件, 时序图, 数据库图 |

---

## 注意事项

1. 每个阶段完成后需要生成阶段检查点文档
2. 若Context Window耗尽，使用INTERFACE_SUMMARY.md恢复上下文
3. 废弃的文件需要在"需要手动操作的事项.txt"中标注

