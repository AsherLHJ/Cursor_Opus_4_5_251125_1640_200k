# 新架构重构进度日志

## 项目概述
- **开始时间**: 2025-11-25 16:40
- **重构完成时间**: 2025-11-25 17:50
- **最后修复时间**: 2025-12-02
- **指导文件**: 新架构项目重构完整指导文件20251130.txt
- **目标**: 按照新架构指导，彻底重构整个项目
- **状态**: ✅ 重构完成 + 三十七轮Bug修复

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
  - [x] `新架构项目重构完整指导文件20251130.txt`: 规则R2后补充Worker数量优化说明

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

## 修复轮次二十二：高并发测试脚本重构 (2025-11-30)

- **时间**: 2025-11-30
- **问题**:
  1. **Selenium效率低**: 使用浏览器模拟，50并发需要50个Chrome实例，资源消耗大
  2. **无法设置用户权限和余额**: 缺少管理员API调用功能
  3. **顺序执行无并发**: 一个账号完成后才处理下一个，无法测试高并发
  4. **测试流程不符合需求**: 需要分阶段执行（前50查询完成 → 后50查询 + 前50下载）
- **解决方案**:
  - 完全重写脚本，从 Selenium 改为 HTTP API 直接调用
  - 使用 `requests` 库进行 HTTP 调用
  - 使用 `concurrent.futures.ThreadPoolExecutor` 实现并发
  - 通过管理员API设置用户权限和余额
- **实现的功能**:
  - **APIClient类**: 封装所有API调用（管理员登录、用户注册/登录、查询、异步下载）
  - **TestAccount类**: 测试账户状态管理
  - **ConcurrencyTest类**: 并发测试控制器
    - 阶段0: 初始化100个账户，设置权限=2，余额=30000
    - 阶段1: 前50用户同时发起查询，等待全部完成
    - 阶段2: 后50用户查询 + 前50用户下载（并行执行）
  - **命令行参数**: --base-url, --production, --start-id, --end-id, --download-dir
  - **测试报告**: test_report.csv 详细记录每个账户的测试结果
- **修复**:
  - [x] `scripts/autopaper_scraper.py`: 完全重写，从426行Selenium代码改为~900行HTTP API代码
  - [x] 新增 `APIClient` 类，封装15+个API方法
  - [x] 新增 `ConcurrencyTest` 类，实现分阶段测试逻辑
  - [x] 支持异步下载API（create_task/poll_status/download_file）
  - [x] 兼容旧版同步下载API作为备选
- **测试配置**:
  - 管理员账号: admin / Paper2025
  - 测试用户: autoTest1 ~ autoTest100
  - 用户权限: 2, 余额: 30000
  - 查询参数: "人机交互相关的任何研究", ANNU REV NEUROSCI/TRENDS NEUROSCI/ISMAR, 2020-2025
  - 下载目录: C:\Users\Asher\Downloads\testDownloadFile

---

## 修复轮次二十三：Result缓存TTL优化 (2025-11-30)

- **时间**: 2025-11-30
- **背景**:
  - 并发测试后发现 `result:*` 缓存占用 34.8MB（101个查询）
  - 当前设计无过期时间，随查询累积会无限占用 Redis 内存
  - 业务场景：每日70,000篇查询量、16GB内存、500万文献
- **分析**:
  - 每个查询结果平均占用 ~345KB
  - 不设置TTL时，143天后内存占满
  - 蒸馏功能需要读取父查询的 result:* 数据
- **解决方案**:
  - `result:*` 设置 7天 TTL，稳态占用 ~341MB
  - 蒸馏时若 Redis MISS，从 MySQL `search_result` 表回源
- **修复**:
  - [x] `lib/redis/connection.py`: TTL_RESULT 常量已存在（7天）
  - [x] `lib/redis/result_cache.py`: set_result/batch_set_results 已添加 TTL
  - [x] `lib/load_data/search_dao.py`: get_relevant_dois_from_mysql 方法已存在
  - [x] `lib/process/distill.py`: estimate_distill_cost 添加 MySQL 回源逻辑
- **预期效果**:
  | 指标 | 优化前 | 优化后 |
  |------|--------|--------|
  | result:* TTL | 无限 | 7天 |
  | 稳态内存占用 | 持续增长 | ~341MB |
  | 蒸馏7天后 | 正常 | 回源MySQL |
  | 内存安全 | 143天后占满 | 永不占满 |

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
|| 2025-11-30 | 修复22 | 高并发测试脚本重构(Selenium→HTTP API/50并发/分阶段测试) | scripts/autopaper_scraper.py(完全重写) |
|| 2025-11-30 | 修复23 | Result缓存TTL优化(7天TTL+蒸馏MySQL回源) | connection.py, result_cache.py, search_dao.py, distill.py, 新架构指导文件, 数据库关联图 |
|| 2025-11-30 | 修复24 | 前端功能增强与Bug修复（8项） | query_api.py, search_dao.py, user_dao.py, index.html, billing.html, i18n.js, data-table.js(新), data-table.css(新), admin/*.html |
|| 2025-11-30 | 修复30 | 蒸馏功能深度修复（代码清理+研究问题传递+is_distillation修复+前端显示） | distill.py, paper_processor.py, query_api.py, index.html, i18n.js |
|| 2025-11-30 | 修复31 | 蒸馏功能深度修复（API字段补全+扣费IOPS优化+颜色改橙色） | query_api.py, paper_processor.py, distill.py, index.html, i18n.js |
|| 2025-12-02 | 修复32 | 管理员页面DataTable增强与批量操作 | data-table.js, data-table.css, i18n.js, admin_api.py, dashboard.html, users.html, tasks.html |
|| 2025-12-02 | 修复33 | 管理员页面刷新控制功能迁移（列名+自动刷新） | i18n.js, dashboard.html, users.html, tasks.html |
|| 2025-12-02 | 修复34 | 压力测试脚本蒸馏功能扩展（查询->蒸馏->下载完整流程） | scripts/autopaper_scraper.py |
|| 2025-12-02 | 修复35 | 公告栏、维护模式与页面样式统一 | db_schema.py, system_settings_dao.py, system_api.py, admin_api.py, server.py, control.html, login.html, index.html, billing.html, maintenance.html(新), i18n.js |
|| 2025-12-02 | 修复36 | AI回复语言适配（中/英）+CSV排序（相关在前）+清理前端遗留旧API调用 | index.html, query_api.py, paper_processor.py, search_paper.py, download_worker.py, server.py, export.py |
|| 2025-12-02 | 修复37 | 用户Token认证安全加固（修复严重安全漏洞） | user_session.py(新), user_auth.py(新), connection.py, auth.py, user_api.py, query_api.py, server.py, index.html, billing.html |
|| 2025-12-02 | 文档同步 | 架构文档同步更新（修复24-37内容） | 数据库关联图, 端到端时序图, 管理员时序图, 项目重构指导文件 |

---

## 架构文档同步更新 (2025-12-02)

### 任务背景
根据修复24-37的内容，同步更新4个架构设计文档，确保文档与代码实现保持一致。

### 更新内容

#### 1. 新架构数据库关联图20251202.mmd
- **新增MySQL表**: SystemSettings（系统配置表）
- **新增Redis Key**:
  - `UserSession`: `user:session:{token}` (String, TTL 24h) - 用户登录Token
  - `DOIIndex`: `idx:doi_to_block` (Hash) - DOI反向索引
  - `DistillBlock`: `distill:{uid}:{qid}:{index}` (Hash, TTL 7天) - 蒸馏专用Block
  - `TerminateSignal`: `query:{uid}:{qid}:terminate_signal` (String, TTL 7天) - 任务终止信号
  - `SystemConfig`: `sys:config:{key}` (String) - 系统配置缓存
- **新增数据流关系**:
  - UserInfo → UserSession (Login Create Token)
  - DOIIndex → PaperBlock (Index Lookup)
  - DistillBlock → QueryResultCache (Distill Worker)
  - SystemSettings → SystemConfig (Preload Script)

#### 2. 新架构端到端业务时序图20251202.mmd
- **更新第1章**: 用户登录流程添加Token创建和Redis存储
- **新增第1.5章**: 公告栏与维护模式检查
- **更新第3章**: 提交查询任务添加language参数
- **更新第4章**: 任务执行循环添加AI语言适配逻辑
- **更新第6章**: 蒸馏任务流程重写，添加蒸馏专用Block创建
- **更新第7章**: 结果下载添加Token验证、CSV排序、Is_Relevant本地化
- **新增第8章**: API请求Token认证通用流程

#### 3. 新架构管理员时序图20251202.mmd
- **更新第4章**: 任务管理使用terminate_signal替代pause_signal进行终止
- **新增第5章**: 批量操作（5个批量API: batch_balance/batch_permission/batch_terminate/batch_pause/batch_resume）
- **新增第6章**: 系统配置管理（公告栏/维护模式/蒸馏系数/权限范围/注册开关/调试开关）

#### 4. 新架构项目重构完整指导文件20251130.txt
- **更新第1章**: 添加用户Token认证机制说明
- **新增第9.5章**: API请求Token认证规范
- **新增第9.6章**: 公告栏与维护模式
- **更新第9章**: 废弃旧下载API说明
- **更新第14章**: 蒸馏专用Block设计 + DOI反向索引 + 蒸馏费率传递优化
- **更新第16章**: 批量操作API + DataTable组件 + 刷新控制功能
- **新增第17.5章**: AI语言适配机制
- **新增第17.6章**: Redis Key完整汇总
- **更新第17.4章**: system_settings表SQL定义

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 6 |
| 新增 | 0 |

### 修改文件清单
- `新架构数据库关联图20251202.mmd` - 新增Redis Key和MySQL表
- `新架构端到端业务时序图20251202.mmd` - 更新/新增7个章节
- `新架构管理员时序图20251202.mmd` - 更新/新增3个章节
- `新架构项目重构完整指导文件20251130.txt` - 更新/新增8个章节
- `RefactoryDocs/INTERFACE_SUMMARY.md` - 补充修复37内容和架构文档更新记录
- `RefactoryDocs/PROGRESS_LOG.md` - 添加架构文档同步更新记录

---

## 修复轮次二十四：前端功能增强与Bug修复 (2025-11-30)

### 问题清单
1. 蒸馏功能点击"开始蒸馏"后无反应
2. billing.html 账单显示为空
3. admin/users.html 余额显示人民币符号
4. 多个列表页面需添加分页/排序/搜索/筛选
5. admin/dashboard.html 版块顺序调整
6. 管理员页面添加中英文切换
7. index.html 显示 "{count}" bug
8. index.html 中英文切换不完整（标签）

### 修复内容

#### 24a: 蒸馏功能 MySQL 回源
- **问题**: `_calculate_distill_cost` 函数在 Redis 缓存过期时返回空数据
- **修复**: 
  - `query_api.py`: 添加 MySQL 回源逻辑
  - `search_dao.py`: 新增 `get_all_results_from_mysql` 函数
  - `index.html`: 增强错误提示（no_relevant_papers）
  - `i18n.js`: 添加 `distill_no_relevant_papers` 翻译

#### 24b: billing.html 账单显示
- **问题**: 后端返回字段与前端期望不匹配
- **修复**: `user_dao.py` 修改 `get_billing_records_by_uid`，返回 `query_time`, `is_distillation`, `total_papers_count`, `actual_cost`

#### 24c: 余额符号修复
- **问题**: 显示人民币符号 ¥，但余额单位是"检索点"
- **修复**: `admin/users.html` 删除 ¥ 符号

#### 24d: 版块顺序调整
- **修复**: `admin/dashboard.html` 将"系统健康状态"移到"活跃任务队列"上方

#### 24e: 选择文章数显示 bug
- **问题**: 显示 `{count}` 占位符未被替换
- **修复**: `index.html` 移除 `data-i18n` 属性，由 JS 动态更新

#### 24f: 标签中英文切换
- **修复**: 
  - `i18n.js`: 添加 `tags` 翻译映射 + `translateTag` 函数 + `clear_tags` 英文翻译
  - `index.html`: 标签渲染使用 `i18n.translateTag()`，语言切换时更新标签

#### 24g: DataTable 组件
- **新建文件**:
  - `lib/html/static/js/data-table.js`: 可复用数据表格组件（分页/排序/搜索/筛选）
  - `lib/html/static/css/data-table.css`: 组件样式
- **应用**: `billing.html` 集成 DataTable

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 7 |
| 新增 | 2 |

---

## 修复轮次二十五：前端功能增强与Bug修复 - 第三轮 (2025-11-30)

### 问题清单
1. 蒸馏功能报错 `Unknown column 'block_key'`
2. billing.html 深色主题样式问题
3. Major/Minor Category 标签翻译不完整
4. 管理员页面中英文切换支持
5. 管理员页面 DataTable 集成

### 修复内容

#### 25a: 蒸馏功能 block_key 修复
- **问题**: MySQL `search_result` 表不存在 `block_key` 列
- **修复**: 
  - `search_dao.py`: `get_all_results_from_mysql` 函数移除 `block_key` 查询
  - 使用 `PaperBlocks.get_paper_by_doi(doi)` 从 Redis 获取 block_key
  - 文献Block永不过期，所以总能找到

#### 25b: billing.html 深色主题
- **问题**: 表格背景深黑、表头刺眼、下拉菜单白底白字
- **修复**: 
  - `billing.html`: body 添加 `class="dark-theme"`
  - `data-table.css`: 完善深色主题样式（搜索框、下拉菜单、表格、分页按钮）

#### 25c: 标签翻译补全
- **问题**: 12个 Major Category 和所有 Minor Category 未翻译
- **修复**: 
  - `i18n.js`: 添加 12 个大类学科英文翻译
  - `i18n.js`: 添加 282 个二级分类（Minor Category）英文翻译

#### 25d: 管理员页面多语言支持
- **修复的页面**:
  - `admin/login.html`
  - `admin/dashboard.html`
  - `admin/users.html`
  - `admin/tasks.html`
  - `admin/control.html`
  - `admin/debug.html`
- **修改内容**:
  - 引入 `i18n.js`
  - 为所有静态文本添加 `data-i18n` 属性
  - 添加语言切换按钮（🌐 EN/中）
  - 添加 `apw_afterLangChange` 回调刷新动态内容
  - 语言偏好通过 localStorage 跨页面保持
- **新增翻译词条**:
  - `i18n.js`: 添加完整的 `admin` 命名空间翻译（中英文）
  - 包含：导航、登录、仪表板、用户管理、任务管理、系统控制、调试日志等

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 9 |
| 新增 | 0 |

### 修改文件清单
- `lib/load_data/search_dao.py` - 修复 block_key 查询
- `lib/html/billing.html` - 添加 dark-theme class
- `lib/html/static/css/data-table.css` - 完善深色主题样式
- `lib/html/static/js/i18n.js` - 添加标签翻译 + 管理员页面翻译
- `lib/html/admin/login.html` - 多语言支持
- `lib/html/admin/dashboard.html` - 多语言支持
- `lib/html/admin/users.html` - 多语言支持
- `lib/html/admin/tasks.html` - 多语言支持
- `lib/html/admin/control.html` - 多语言支持
- `lib/html/admin/debug.html` - 多语言支持

---

## 修复轮次二十六：蒸馏功能超时与管理员登录Bug (2025-11-30)

### 问题清单
1. 蒸馏功能点击后长期显示"加载中..."，最终变成"获取失败"（504超时）
2. 管理员登录页面有两个语言切换按钮
3. 管理员登录后URL变成`?username=admin&password=Paper2025`暴露密码
4. INTERFACE_SUMMARY.md 和 PROGRESS_LOG.md 标号不统一

### 问题分析

#### 26a: 蒸馏功能超时
- **根因**: `get_all_results_from_mysql` 对每个DOI调用 `PaperBlocks.get_paper_by_doi(doi)`
- **性能瓶颈**: `get_paper_by_doi` 遍历所有Block（约数百个）查找一个DOI，复杂度O(n*m)
- **表现**: 当需要查询数百个相关DOI时，请求超时（>5分钟）

#### 26b: 管理员登录页面Bug
- **Bug1**: `admin/login.html` 手动添加了语言按钮，`i18n.js` 又自动创建了一个
- **Bug2**: `<form>` 标签无 `action` 和 `method` 属性，JS执行失败时表单以GET方式提交

### 修复内容

#### 26a: DOI反向索引与批量查询优化
- **新增Redis Key**: `idx:doi_to_block` (Hash) - DOI反向索引
  - Field: DOI
  - Value: block_key (如 "meta:NATURE:2024")
- **paper_blocks.py 修改**:
  - 新增 `KEY_DOI_INDEX = "idx:doi_to_block"` 常量
  - 修改 `set_paper()`: 写入文献时同步更新反向索引
  - 修改 `set_block()`: 批量写入时同步更新反向索引
  - 优化 `get_paper_by_doi()`: 优先查反向索引(O(1))，不存在时才回退遍历
  - 新增 `get_block_key_by_doi()`: O(1)获取单个DOI的block_key
  - 新增 `batch_get_block_keys()`: Pipeline批量获取多个DOI的block_key
  - 新增 `build_doi_index()`: 为所有已有数据构建反向索引
  - 新增 `get_doi_index_size()`: 获取索引大小
- **init_loader.py 修改**:
  - 阶段3后新增阶段3.5：调用 `build_doi_index()` 构建DOI索引
  - `check_redis_data_loaded()` 新增 `doi_index_loaded` 检查
- **search_dao.py 修改**:
  - 重构 `get_all_results_from_mysql()`: 使用 `batch_get_block_keys()` 批量查询
  - 复杂度从O(n*m)优化到O(n)

#### 26b: 管理员登录页面修复
- **删除重复按钮**: 移除 `login-container` 内的手动语言按钮
- **修复表单提交**: 添加 `action="javascript:void(0)" method="POST"`
- **清理代码**: 移除手动按钮事件监听器，使用 `apw_afterLangChange` 回调

#### 26c: 文档同步
- **INTERFACE_SUMMARY.md**: 补充修复25内容，新增修复26
- **PROGRESS_LOG.md**: 新增修复轮次二十六

### 性能对比
| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| 单DOI查询 | O(m) 遍历所有Block | O(1) 索引查找 |
| n个DOI批量查询 | O(n*m) 逐个遍历 | O(n) Pipeline批量 |
| 蒸馏费用估算 | >5分钟超时 | <1秒响应 |

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 5 |
| 新增 | 0 |

### 修改文件清单
- `lib/redis/paper_blocks.py` - DOI反向索引支持
- `lib/redis/init_loader.py` - 启动时构建DOI索引
- `lib/load_data/search_dao.py` - 批量查询优化
- `lib/html/admin/login.html` - 修复登录页面Bug
- `RefactoryDocs/INTERFACE_SUMMARY.md` - 补充修复25和26
- `RefactoryDocs/PROGRESS_LOG.md` - 添加修复轮次二十六

---

## 修复轮次二十七：蒸馏功能前端Bug修复 (2025-11-30)

### 问题清单
1. 点击"开始蒸馏"按钮没有任何反应或反馈
2. 在蒸馏研究问题输入框中每输入一个字符，后端就会打印一次"从MySQL回源获取5864条结果"日志

### 问题分析

#### 27a: 点击"开始蒸馏"按钮无反应
- **根因**: `index.html` 第4868行的onclick属性：
  ```javascript
  onclick="startDistillation('${cardId}', ${queryIndex})"
  ```
- **问题**: `queryIndex` 是字符串类型（如 "Q20251130073938_411822a1"），但没有被引号包裹
- **结果**: JavaScript将其解析为变量名而非字符串字面量，触发 `ReferenceError: Q20251130073938_411822a1 is not defined`
- **受影响位置**: 共4处onclick属性

#### 27b: input事件导致API频繁调用
- **根因**: 第4886-4894行的input事件监听器每次输入都调用 `estimateDistillationCost()`
- **问题**: 蒸馏费用只取决于父查询的"相关"论文数量和价格，与用户输入的研究问题无关
- **结果**: 每输入一个字符就发送一次HTTP请求，后端每次都从MySQL回源获取数千条结果

### 修复内容

#### 27a: onclick属性添加引号
修复4处动态生成的onclick属性中的queryIndex参数：
- 第4868行: `startDistillation('${cardId}', '${queryIndex}')`
- 第5224行: `downloadDistillationCSV('${queryIndex}')`
- 第5227行: `downloadDistillationBIB('${queryIndex}')`
- 第5230行: `createDistillInputCard('${queryIndex}')`

#### 27b: 重构input事件处理
1. 修改 `estimateDistillationCost` 函数：
   - 获取费用数据后，将其缓存到 `activeDistillCards.get(cardId).costData`
2. 修改 input 事件监听器：
   - 移除 `estimateDistillationCost` 调用
   - 改为从缓存中读取费用数据，仅做本地状态检查
3. 效果：费用估算API只在卡片创建时调用一次，用户输入时不再发送任何HTTP请求

### 性能对比
| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| 输入10个字符 | 10次API调用，10次MySQL回源 | 0次API调用 |
| 后端负载 | 每字符触发数千条记录查询 | 无额外负载 |

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 1 |
| 新增 | 0 |

### 修改文件清单
- `lib/html/index.html` - 修复4处onclick引号 + 重构input事件处理

---

## 修复轮次二十八：蒸馏计费Bug修复 (2025-11-30)

### 问题清单
1. 蒸馏任务计费使用正常费率（1倍）而非蒸馏费率（0.1倍）

### 问题分析

#### 28a: 蒸馏计费Bug
- **现象**: 用户余额600，预计消耗527.6（2943篇×0.1倍），但Worker报告"余额不足"
- **实际**: 仅处理388条记录后余额清零
- **日志证据**: `[Worker-32] 余额不足，跳过 10.1145/3706598.3713476`

#### 根因追踪
1. **蒸馏费率定义正确**: `distill.py` 第23行 `DISTILL_RATE = 0.1`
2. **DistillWorker实现正确**: `distill.py` 第234行使用 `price * DISTILL_RATE`
3. **问题在Scheduler**: `scheduler.py` 第182行：
   ```python
   workers = spawn_workers(uid, qid, actual_workers, ai_processor)
   ```
   始终使用普通 `BlockWorker`，无论任务是否为蒸馏任务

4. **费用计算差异**:
   - 预计费用（正确）: 2943 × 平均1.79 × 0.1 ≈ 527.6
   - 实际扣费（错误）: 每篇按正常费率扣费，约1.79/篇
   - 结果: 600 ÷ 1.79 ≈ 335篇后余额耗尽

### 修复内容

#### 28a: 新增 get_query_by_id 函数
- **文件**: `lib/load_data/query_dao.py`
- **功能**: 根据 query_id 获取查询信息（包含 search_params）
- **用途**: 供 Scheduler 判断任务类型

#### 28b: 修改 _start_query_workers 函数
- **文件**: `lib/process/scheduler.py`
- **修改**:
  1. 从 `query_dao.get_query_by_id(qid)` 获取查询信息
  2. 解析 `search_params.is_distillation` 判断任务类型
  3. 蒸馏任务调用 `spawn_distill_workers()` 使用 `DistillWorker`
  4. 普通查询调用 `spawn_workers()` 使用 `BlockWorker`

### 修改后的流程
```
蒸馏任务提交 -> Scheduler检测is_distillation=True 
  -> spawn_distill_workers() -> DistillWorker (0.1倍费率)
普通查询提交 -> Scheduler检测is_distillation=False
  -> spawn_workers() -> BlockWorker (正常费率)
```

### 预期效果
- 蒸馏任务使用 `DistillWorker`，每篇扣费 = 基础价格 × 0.1
- 2943篇文献，预计费用527.6，用户余额600足够完成
- 任务正常完成，不再出现"余额不足"

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 2 |
| 新增 | 0 |

### 修改文件清单
- `lib/load_data/query_dao.py` - 新增 `get_query_by_id()` 函数
- `lib/process/scheduler.py` - 修改 `_start_query_workers()` 区分任务类型

---

## 修复轮次二十九：蒸馏任务Scheduler异常与超额计费修复 (2025-11-30)

### 问题清单
1. Scheduler循环异常: `'DistillWorker' object has no attribute '_running'`
2. 蒸馏超额计费: 预估527.6（2943篇），实际扣费530.0（3272篇）

### 问题分析

#### 29a: Scheduler异常
- **现象**: 日志持续报错 `[Scheduler] 循环异常: 'DistillWorker' object has no attribute '_running'`
- **位置**: `scheduler.py` 第236行访问 `w._running`
- **根因**: `DistillWorker` 类没有暴露 `_running` 和 `_thread` 属性，它们在 `_inner_worker` 中

#### 29b: 蒸馏超额计费
- **现象**: 
  - 预估费用: 527.6（2943篇 × 0.1倍费率）
  - 实际费用: 530.0（全部余额）
  - 归档记录: 3272条（而非2943条）
- **日志证据**: 
  ```
  [BillingSyncer] 同步 uid=1: 2000 条记录, 金额 304.30
  [BillingSyncer] 同步 uid=1: 1272 条记录, 金额 225.70
  [SearchDAO] 归档完成: Q20251130111112_6aa7cf00 -> 3272 条记录
  ```
- **根因**: `distillation_producer` 入队的是 `meta:JOURNAL:YEAR` 格式的完整Block，Worker处理时会处理整个Block中的所有论文（3272篇），而非仅相关DOI（2943篇）

### 修复方案

#### 29a修复: DistillWorker属性代理
在 `DistillWorker` 类中添加 `@property` 方法代理 `_inner_worker` 属性：
```python
@property
def _running(self):
    return self._inner_worker._running

@property
def _thread(self):
    return self._inner_worker._thread
```

#### 29b修复: 蒸馏专用Block
重构 `distillation_producer` 函数：
1. 不再直接入队 `meta:` 格式的完整Block
2. 创建 `distill:{uid}:{qid}:{index}` 格式的蒸馏专用Block
3. 蒸馏Block只包含相关DOI的Bib数据（精确到2943篇）
4. 修改 `get_block_by_key` 支持 `distill:` 前缀的Block

### 新增Redis Key格式
- `distill:{uid}:{qid}:{block_index}` (Hash, TTL 7天)
  - Field: DOI
  - Value: Bib字符串
  - 每个Block最多100个DOI

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 3 |
| 新增 | 0 |

### 修改文件清单
- `lib/process/distill.py` - DistillWorker添加 `_running` 和 `_thread` 属性代理
- `lib/process/paper_processor.py` - `distillation_producer` 创建蒸馏专用Block
- `lib/redis/paper_blocks.py` - `get_block_by_key` 支持 `distill:` 前缀

### 预期效果
1. Scheduler不再报 `_running` 属性错误
2. 蒸馏任务只处理相关DOI（2943篇），费用约527.6
3. 任务完成后余额 = 530 - 527.6 = 2.4

---

## 修复轮次三十：蒸馏功能深度修复 (2025-11-30)

### 问题清单
1. `distill.py` 包含5个未被调用的函数，与 `paper_processor.py` 和 `query_api.py` 功能重复
2. 蒸馏任务创建时 `research_question=""` 没有传递用户输入的蒸馏研究问题
3. 历史记录的 `is_distillation` 从不存在的数据库列获取，应从 `search_params` JSON 获取
4. 前端蒸馏任务无法与普通查询区分，不显示父任务信息

### 问题分析

#### 30a: 代码重复
- **根因**: 早期修复时在 `distill.py` 创建了独立的蒸馏处理函数，后续在 `paper_processor.py` 又实现了一套
- **实际调用链**: `query_api` → `paper_processor.process_papers_for_distillation` → `distillation_producer`
- **未使用代码**: `create_distill_task`, `_create_distill_blocks`, `get_distill_block`, `calculate_distill_cost`, `estimate_distill_cost`

#### 30b: 研究问题空白
- **根因**: `process_papers_for_distillation` 函数签名不包含研究问题参数
- **代码位置**: 第182行设置 `"research_question": ""`
- **调用位置**: `query_api._handle_start_distillation` 获取了 `question` 但未传递

#### 30c: is_distillation 获取错误
- **根因**: `_handle_get_query_history` 使用 `r.get('is_distillation')` 获取
- **问题**: `query_log` 表无 `is_distillation` 列，该字段在 `search_params` JSON 中
- **同样问题**: `_handle_get_query_info` 也缺少 `is_distillation` 和 `original_query_id` 返回

#### 30d: 前端显示问题
- **现象**: 蒸馏任务与普通查询在历史记录中无法区分，详情卡片不显示父任务
- **根因**: 后端返回的数据缺少字段，前端也未处理

### 修复内容

#### 30a: 清理 distill.py
- **删除函数**: create_distill_task, _create_distill_blocks, get_distill_block, calculate_distill_cost, estimate_distill_cost
- **保留代码**: DISTILL_RATE, DISTILL_BLOCK_SIZE, DistillWorker, spawn_distill_workers
- **代码减少**: ~200行 → ~110行

#### 30b: 修复研究问题传递
- **paper_processor.py**: 添加 `research_question: str = ""`, `requirements: str = ""` 参数
- **query_api.py**: `_handle_start_distillation` 调用时传递 `question`, `requirements`

#### 30c: 修复 is_distillation 获取
- **_handle_get_query_history**: 
  - 从 `search_params` 获取 `is_distillation`
  - 新增 `original_query_id` 返回字段
- **_handle_get_query_info**:
  - 新增 `is_distillation` 返回字段
  - 新增 `original_query_id` 返回字段

#### 30d: 前端显示优化
- **createHistoryItem**: 蒸馏任务标题添加 `🔬` 前缀
- **updateHistoryDescriptionCard**: 蒸馏任务显示"基于任务 XXX"信息
- **i18n.js**: 添加 `distill_prefix`, `distill_based_on` 中英文翻译

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 6 |
| 新增 | 0 |
| 删除 | 0 |

### 修改文件清单
- `lib/process/distill.py` - 清理5个未使用函数（~90行删除），蒸馏费率动态化
- `lib/process/paper_processor.py` - process_papers_for_distillation 添加参数，费率动态化
- `lib/process/scheduler.py` - 更新注释（动态蒸馏费率）
- `lib/webserver/query_api.py` - 修复3处蒸馏相关逻辑
- `lib/html/index.html` - 蒸馏任务显示优化
- `lib/html/static/js/i18n.js` - 添加蒸馏翻译词条

### 补充：蒸馏费率动态化（遵循修复17原则）

#### 问题
以下位置硬编码了蒸馏费率 0.1，违反修复17确立的"动态获取蒸馏系数"原则：
- `distill.py` 第22-23行: `DISTILL_RATE = 0.1`
- `paper_processor.py` 第199行: `estimated_cost=float(paper_count) * 0.1`
- `scheduler.py` 第167、204行: 注释中写死"0.1倍费率"

#### 修复内容
| 文件 | 问题 | 修复 |
|------|------|------|
| `distill.py` | DISTILL_RATE=0.1 硬编码常量 | 删除常量，使用 `SystemConfig.get_distill_rate()` |
| `paper_processor.py` | estimated_cost * 0.1 | 改为 `* SystemConfig.get_distill_rate()` |
| `scheduler.py` | 注释硬编码"0.1倍费率" | 更新为"动态蒸馏费率" |

---

## 修复轮次三十一：蒸馏功能深度修复 (2025-11-30)

### 问题清单
1. 查询任务刷新后"文章总数"和"预计花费"消失
2. 蒸馏任务扣费错误（按1点/篇而非实际价格×蒸馏系数）
3. 蒸馏任务刷新后"相关论文数量"、"开销"、"开始时间"消失
4. 蒸馏任务颜色需从深紫色改为低饱和度橙色

### 问题分析

#### 31a: API返回字段缺失
- **根因**: `_handle_get_query_info` 和 `_handle_get_query_history` 返回数据缺少 `total_papers_count` 和 `estimated_cost` 字段
- **修复**: 从 `search_params` 和 `query_log` 表中提取这些字段并返回

#### 31b: 蒸馏任务扣费错误
- **根因**: 蒸馏Block格式是 `distill:{uid}:{qid}:{index}`，但 `parse_block_key` 只能解析 `meta:` 前缀，导致价格默认为1
- **根因2**: 预估阶段计算的价格信息未传递给Worker
- **IOPS分析**: 预估阶段已是O(1)级别（3次Redis调用），问题在于价格信息未传递

#### 31c: 颜色修改
- **需求**: 将深紫色（#8b5cf6等）改为低饱和度橙色（#b87333等）

### 修复内容

#### 31a: API返回字段修复
- `_handle_get_query_info`: 新增 `total_papers_count` 和 `estimated_cost` 返回字段
- `_handle_get_query_history`: 新增 `estimated_cost` 返回字段

#### 31b: 蒸馏扣费修复（IOPS优化版）
核心思路：让价格信息从预估阶段传递到Worker，避免Worker重复查询

| 步骤 | 文件 | 修改内容 |
|------|------|----------|
| B1 | `query_api.py` | `_calculate_distill_cost` 返回三元组 `(dois, cost, doi_prices)` |
| B2 | `query_api.py` | `_handle_start_distillation` 传递 `doi_prices` |
| B3 | `paper_processor.py` | `process_papers_for_distillation` 新增 `doi_prices` 参数 |
| B4 | `paper_processor.py` | `distillation_producer` 存储格式改为 `{"bib": bib, "price": price}` |
| B5 | `distill.py` | `DistillWorker.__init__` 缓存蒸馏费率 |
| B6 | `distill.py` | `_process_paper_with_distill_rate` 从Block解析价格JSON |

**IOPS效果**:
| 阶段 | Redis调用 |
|------|----------|
| 预估阶段 | 3次（get_all_results + get_all_prices + get_distill_rate） |
| Worker阶段 | 0次额外调用（从Block读取价格） |
| 蒸馏费率 | 1次（Worker初始化时缓存） |

#### 31c: 前端显示修复
- `updateHistoryDescriptionCard`: 显示文章总数和开销
- `i18n.js`: 添加 `actual_cost`("开销") 和 `relevant_papers_count`("相关论文数量") 翻译

#### 31d: CSS颜色修复
配色方案：
- 主色: `#b87333` (古铜色)
- 浅色: `#c9a06a` (沙金色)
- 深色: `#8b6914` (暗金色)
- 背景渐变: `#2a2016` → `#1e1e1e`

修改的选择器：
- `.history-item.distill-type` 及其 `:hover` / `.active` 状态
- `.history-item.distill-type .history-item-title`
- `.history-item.distill-type .history-item-meta`
- `.history-description-card.distill-type` 及其子元素

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 5 |
| 新增 | 0 |

### 修改文件清单
- `lib/webserver/query_api.py` - API返回字段 + _calculate_distill_cost返回doi_prices
- `lib/process/paper_processor.py` - 传递doi_prices参数，distillation_producer存储价格JSON
- `lib/process/distill.py` - 缓存费率，从Block解析价格JSON
- `lib/html/index.html` - 前端显示+CSS颜色修改
- `lib/html/static/js/i18n.js` - 翻译词条

---

## 修复轮次三十二：管理员页面 DataTable 增强与批量操作 (2025-12-02)

### 问题清单
1. 管理员页面列表（dashboard/users/tasks）缺少分页、排序、搜索、筛选功能
2. 缺少全选/勾选和批量操作功能
3. 操作成功后使用 alert 弹窗，用户体验差

### 修复内容

#### 32a: DataTable 组件扩展
- **data-table.js 新增功能**:
  - `selectable: true` 配置项启用勾选列
  - `idKey` 配置项指定行唯一标识字段
  - `batchActions` 配置项定义批量操作按钮
  - `selectedIds` Set 维护选中状态
  - `getSelectedRows()` 获取选中行数据
  - `clearSelection()` 清空选中
  - `selectAllOnPage()` / `deselectAllOnPage()` 全选/取消当前页
  - `DataTable.showToast(message, type, duration)` 静态方法显示 Toast 提示
- **data-table.css 新增样式**:
  - `.data-table-checkbox-col` - checkbox 列样式
  - `.data-table-batch-bar` - 批量操作栏（选中项时显示）
  - `.batch-btn`, `.batch-btn-danger`, `.batch-btn-warning`, `.batch-btn-success` - 批量按钮
  - `.data-table-toast-container`, `.data-table-toast` - Toast 提示
  - 深色主题全面适配

#### 32b: 后端批量操作 API（admin_api.py）
- `POST /api/admin/users/batch_balance` - 批量调整余额
  - 请求：`{items: [{uid}], operation: "increase"|"decrease"|"set", amount: number}`
  - 响应：`{success, message, success_count}`
- `POST /api/admin/users/batch_permission` - 批量调整权限
  - 请求：`{items: [{uid}], permission: number}`
  - 响应：`{success, message, success_count}`
- `POST /api/admin/tasks/batch_terminate` - 批量终止任务
  - 请求：`{items: [{uid, query_id}]}`
  - 响应：`{success, message, success_count, workers_stopped}`
- `POST /api/admin/tasks/batch_pause` - 批量暂停任务
- `POST /api/admin/tasks/batch_resume` - 批量恢复任务

#### 32c: 管理员页面重构

**dashboard.html**:
- 引入 DataTable 组件
- 活跃任务队列使用 DataTable 渲染
- 支持按状态筛选（RUNNING/PAUSED/DONE）
- 批量操作：批量终止
- Toast 替代 alert

**users.html**:
- 用户列表使用 DataTable 渲染
- 支持 UID/用户名搜索、余额/权限排序
- 批量操作：批量调整余额、批量调整权限
- 余额调整支持增加/减少/设为三种模式
- 移除单行操作按钮，统一使用批量操作

**tasks.html**:
- 任务列表使用 DataTable 渲染
- 移除原有 tabs 筛选，改用 DataTable 内置筛选
- 支持按状态筛选、按用户ID筛选
- 批量操作：批量暂停、批量恢复、批量终止
- 智能过滤：暂停只对 RUNNING 任务，恢复只对 PAUSED 任务

#### 32d: i18n 翻译扩展
新增翻译词条（中英文）：
- `admin.batch_selected_count`: "已选择 {count} 项"
- `admin.batch_terminate`: "批量终止"
- `admin.batch_pause`: "批量暂停"
- `admin.batch_resume`: "批量恢复"
- `admin.batch_adjust_balance`: "批量调整余额"
- `admin.batch_adjust_permission`: "批量调整权限"
- `admin.batch_confirm_*`: 批量操作确认提示
- `admin.balance_mode_*`: 增加/减少/设为
- `datatable.*`: DataTable 组件翻译

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 7 |
| 新增 | 0 |

### 修改文件清单
- `lib/html/static/js/data-table.js` - DataTable 组件扩展
- `lib/html/static/css/data-table.css` - 新增样式
- `lib/html/static/js/i18n.js` - 新增翻译词条
- `lib/webserver/admin_api.py` - 新增5个批量操作 API
- `lib/html/admin/dashboard.html` - 集成 DataTable
- `lib/html/admin/users.html` - 集成 DataTable + 批量模态框
- `lib/html/admin/tasks.html` - 集成 DataTable（移除 tabs）

---

## 修复轮次三十三：管理员页面刷新控制功能迁移 (2025-12-02)

### 问题清单
1. dashboard.html、users.html、tasks.html 的"用户"/"用户ID"列名需改为"用户UID"
2. 三个页面需要添加与 debug.html 相同的刷新控制功能（立即刷新、暂停/继续自动刷新、刷新间隔选择）
3. "最后更新"需改为"最后更新时间"

### 问题分析

#### 33a: 列名不统一
- **dashboard.html**: 活跃任务队列中"用户"列标签使用 `admin.task_user`
- **tasks.html**: 任务列表中"用户ID"列标签使用 `admin.tasks_uid`
- **需求**: 统一改为 `admin.task_user_uid`（"用户UID"/"User UID"）

#### 33b: 刷新控制功能缺失
- **debug.html**: 已有完整的刷新控制（立即刷新、暂停/继续、间隔选择1/2/5/10/30秒）
- **dashboard.html**: 仅有单一刷新按钮和 `setInterval(refreshData, 5000)` 固定5秒刷新
- **users.html**: 无刷新按钮和自动刷新
- **tasks.html**: 单一刷新按钮和 `setInterval(loadTasks, 10000)` 固定10秒刷新

### 修复内容

#### 33a: i18n.js 翻译更新
新增翻译词条：
- `admin.task_user_uid`: "用户UID" / "User UID"
- `admin.refresh_now`: "立即刷新" / "Refresh Now"
- `admin.pause_auto_refresh`: "暂停自动刷新" / "Pause Auto Refresh"
- `admin.resume_auto_refresh`: "继续自动刷新" / "Resume Auto Refresh"
- `admin.refresh_interval`: "刷新间隔:" / "Refresh Interval:"
- `admin.interval_1s` / `2s` / `5s` / `10s` / `30s`: 时间间隔选项

修改翻译词条：
- `admin.last_update`: "最后更新" → "最后更新时间" / "Last Update Time"

#### 33b: dashboard.html 修改
- **列名**: `i18n.t('admin.task_user')` → `i18n.t('admin.task_user_uid')`
- **CSS 新增**: `.refresh-controls`、`.btn-secondary`、`.refresh-interval`、`#lastUpdate` 样式
- **HTML**: 替换刷新按钮区域为三控件布局
- **JS 变量**: 添加 `autoRefresh = true`、`timer = null`、`refreshInterval = 5000`
- **JS 函数**: 添加 `schedule()`、`toggleAutoRefresh()`、`updateRefreshInterval()`、`updateAutoToggleText()`
- **初始化**: `setInterval(refreshData, 5000)` → `schedule()`

#### 33c: users.html 修改
- **CSS 新增**: 与 dashboard.html 相同的刷新控制样式
- **HTML**: 在 panel 前添加 `.refresh-controls` 区域
- **JS 变量/函数**: 同上，调用 `loadUsers()` 而非 `refreshData()`
- **初始化**: 添加自动刷新支持，默认间隔 5 秒

#### 33d: tasks.html 修改
- **列名**: `i18n.t('admin.tasks_uid')` → `i18n.t('admin.task_user_uid')`
- **CSS/HTML/JS**: 同上修改
- **初始化**: 默认间隔 10 秒（保持原有行为）

### 刷新控制功能逻辑

```javascript
// 自动刷新控制变量
let autoRefresh = true;
let timer = null;
let refreshInterval = 5000;  // dashboard/users=5s, tasks=10s

// 调度函数
function schedule() {
    clearInterval(timer);
    if (autoRefresh) {
        timer = setInterval(refreshData, refreshInterval);  // 或 loadUsers/loadTasks
    }
}

// 切换自动刷新
function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    updateAutoToggleText();
    schedule();
}

// 更新间隔
function updateRefreshInterval() {
    refreshInterval = parseInt(document.getElementById('refreshInterval').value);
    if (autoRefresh) schedule();
}

// 更新按钮文本（多语言支持）
function updateAutoToggleText() {
    const textSpan = document.getElementById('autoToggleText');
    const btn = document.getElementById('autoToggleBtn');
    if (autoRefresh) {
        btn.innerHTML = '⏸️ <span id="autoToggleText" data-i18n="admin.pause_auto_refresh">' + 
                        i18n.t('admin.pause_auto_refresh') + '</span>';
    } else {
        btn.innerHTML = '▶️ <span id="autoToggleText" data-i18n="admin.resume_auto_refresh">' + 
                        i18n.t('admin.resume_auto_refresh') + '</span>';
    }
}
```

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 4 |
| 新增 | 0 |

### 修改文件清单
- `lib/html/static/js/i18n.js` - 添加/修改翻译词条
- `lib/html/admin/dashboard.html` - 列名 + 刷新控制功能
- `lib/html/admin/users.html` - 添加刷新控制功能
- `lib/html/admin/tasks.html` - 列名 + 刷新控制功能

---

## 修复轮次三十四：压力测试脚本蒸馏功能扩展 (2025-12-02)

### 需求清单
1. 注册300个用户 (autoTest1~autoTest300)，设置权限=2，余额=30000
2. 前100个用户 (autoTest1~100) 同时发起查询任务
3. 每个查询任务完成后，该用户立即发起蒸馏任务
4. 每个蒸馏任务完成后，立即下载 CSV 和 BIB 文件
5. 支持 `--start-id` 和 `--end-id` 参数指定测试用户范围

### 查询参数（保持不变）
- 研究问题: "人机交互相关的任何研究"
- 数据源: ANNU REV NEUROSCI, TRENDS NEUROSCI, ISMAR
- 年份范围: 2020-2025

### 蒸馏参数（新增）
- 蒸馏研究问题: "使用了EEG和EMG的硬件的研究"
- 蒸馏研究要求: (空)

### 修复内容

#### 34a: 配置常量更新
- `TOTAL_USERS`: 100 -> 300（用于注册账户总数）
- `ACTIVE_TEST_USERS`: 新增，值为100（实际参与测试的用户数）
- `DISTILL_QUESTION`: 新增，"使用了EEG和EMG的硬件的研究"
- `DISTILL_REQUIREMENTS`: 新增，空字符串
- `PIPELINE_CONCURRENCY`: 新增，值为100（管道并发数）

#### 34b: TestAccount 数据类扩展
新增字段：
- `distill_query_id: str = ""`：蒸馏查询ID
- `distill_start_time: Optional[datetime] = None`：蒸馏开始时间
- `distill_end_time: Optional[datetime] = None`：蒸馏结束时间
- `distill_completed: bool = False`：蒸馏完成标志
- `@property distill_duration`：蒸馏耗时（秒）

#### 34c: TestResult 数据类扩展
新增字段：
- `successful_distillations: int = 0`：成功蒸馏数
- `failed_distillations: int = 0`：失败蒸馏数

#### 34d: APIClient 蒸馏API支持
新增方法：
```python
def estimate_distillation_cost(self, uid: int, original_query_id: str) -> Dict:
    """估算蒸馏费用"""

def start_distillation(self, uid: int, original_query_id: str,
                       question: str, requirements: str = "") -> str:
    """发起蒸馏任务，返回新的query_id"""
```

#### 34e: 测试流程重构
- **简化为单阶段流程**: 查询 -> 蒸馏 -> 下载
- **移除旧的两阶段流程**: 删除 `_phase1_query()`, `_phase2_query_and_download()` 等方法
- **新增方法**:
  - `_phase1_query_distill_download()`: 统一管理查询->蒸馏->下载流程
  - `_query_distill_download_pipeline()`: 每账户独立执行的完整管道
  - `_start_distillation_for_account()`: 发起单个账户的蒸馏
  - `_wait_for_single_query()`: 等待单个查询完成
  - `_wait_for_distillation()`: 等待蒸馏完成
  - `_download_distill_results()`: 下载蒸馏结果
- **下载方法修改**: `_download_with_async_api()` 和 `_download_with_sync_api()` 支持指定 `query_id` 参数

#### 34f: 报告增强
- 统计信息增加蒸馏成功/失败数
- 增加蒸馏耗时统计（平均/最短/最长）
- CSV报告新增蒸馏相关列：`distill_query_id`, `distill_start_time`, `distill_end_time`, `distill_duration_sec`, `distill_completed`
- 下载文件重命名为 `{username}_Distill_Result.csv/bib`

### 使用示例
```bash
# 测试前10个用户
python scripts/autopaper_scraper.py --start-id 1 --end-id 10

# 测试前50个用户
python scripts/autopaper_scraper.py --start-id 1 --end-id 50

# 测试全部100个活跃用户
python scripts/autopaper_scraper.py
```

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 修改 | 1 |
| 新增 | 0 |

### 修改文件清单
- `scripts/autopaper_scraper.py` - 完整重构支持蒸馏流程（约1050行）

---

## 修复轮次三十五：公告栏、维护模式与页面样式统一 (2025-12-02)

### 需求清单
1. 管理员页面 `/admin/control.html` 新增"公告栏"开关和文本框
2. 管理员页面新增"维护模式"开关和"服务器维护公告"文本框
3. 维护模式开启时用户页面跳转到维护页面
4. `login.html` 语言按钮移至卡片内部（与 `admin/login.html` 一致）
5. `maintenance.html` 改为与 `login.html` 统一的深色纯色风格

### 修复内容

#### 35a-35c: 后端与管理面板
- **db_schema.py**: 新增4个配置项（announcement_enabled/content, maintenance_mode/message）
- **system_settings_dao.py**: 新增8个便捷方法
- **system_api.py**: 新增 `/api/system_announcement`, `/api/maintenance_status`
- **control.html**: 添加开关和文本框

#### 35d: 用户页面公告与维护检查
- **login.html**: 公告栏 + 维护检查 + 语言按钮移至卡片内部（隐藏i18n.js自动创建的按钮）
- **index.html**: 公告栏 + 维护检查
- **billing.html**: 维护检查

#### 35e: 维护页面
- **maintenance.html** (新建): 深色纯色风格（背景`#0a0a0a`，卡片`#1a1a1a`），语言按钮在卡片底部

#### 35f: 国际化翻译
- **i18n.js**: 新增公告栏、维护模式相关翻译词条

### 新增API接口
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/system_announcement` | GET | 获取公告栏状态和内容 |
| `/api/maintenance_status` | GET | 获取维护模式状态 |

### 修改文件清单
- `DB_tools/lib/db_schema.py` - 添加4个默认配置项
- `lib/load_data/system_settings_dao.py` - 添加8个便捷方法
- `lib/webserver/system_api.py` - 新增2个公开API
- `lib/webserver/admin_api.py` - 配置接口返回新字段
- `lib/webserver/server.py` - 添加API路由和维护页面路由
- `lib/html/admin/control.html` - 添加开关和文本框
- `lib/html/login.html` - 公告栏+维护检查+语言按钮移至卡片内部
- `lib/html/index.html` - 添加公告栏和维护检查
- `lib/html/billing.html` - 添加维护检查
- `lib/html/maintenance.html` - 新建（深色纯色风格+语言按钮在卡片内部）
- `lib/html/static/js/i18n.js` - 添加翻译词条

---

## 修复轮次三十六：AI回复语言适配与CSV排序优化 (2025-12-02)

### 需求清单
1. AI回复语言根据页面语言模式自动切换（中文/英文）
2. 下载的CSV文件按相关性排序（相关在前，不相关在后）
3. CSV的Is_Relevant列根据语言显示"符合/不符"或"Relevant/Irrelevant"
4. 删除旧架构同步下载API，统一使用异步下载
5. BIB文件不再包含任何头信息

### 问题分析

#### 36a: AI回复语言自动适配
- **现状**: `config.json` 的 `system_prompt` 包含 `{language}` 占位符，但未被替换
- **根因**: `search_paper.py` 的 `_build_prompt()` 函数未处理语言参数
- **需求**: 前端传递当前语言，后端替换占位符为对应语言名称

#### 36b: CSV下载结果排序
- **现状**: `download_worker.py` 的 `_generate_csv_file()` 按无序字典遍历
- **需求**: 相关文献(Y)排在前面，不相关文献(N)排在后面

#### 36c: 旧架构同步下载残留
- **现状**: `server.py` 存在 `/api/download_csv` 和 `/api/download_bib` 旧接口，硬编码中文"符合/不符"
- **问题**: 前端可能调用旧接口，导致英文模式下仍显示中文
- **解决**: 删除旧架构代码，强制使用新架构异步下载API

#### 36d: BIB文件头信息
- **现状**: `export.py` 的 `export_bib` 函数生成头信息
- **需求**: 无论中英文，BIB文件都不要任何头信息

### 修复内容

#### 36a: AI语言适配
| 文件 | 修改内容 |
|------|----------|
| `lib/html/index.html` | `startSearch` 和 `startDistillation` 添加 `language: i18n.getLang()` |
| `lib/webserver/query_api.py` | 接收 `language` 参数，存入 `search_params` |
| `lib/process/paper_processor.py` | 传递 `language` 参数，存入 `full_search_params` |
| `lib/process/search_paper.py` | 新增 `LANGUAGE_MAP`，替换 `{language}` 占位符 |

#### 36b: CSV排序 + 相关性文本语言适配
| 文件 | 修改内容 |
|------|----------|
| `lib/process/download_worker.py` | 排序（Y在前N在后）+ Is_Relevant列语言适配 |

#### 36c: 删除旧架构同步下载
| 文件 | 修改内容 |
|------|----------|
| `lib/webserver/server.py` | 删除 `/api/download_csv`, `/api/download_bib` 路由 |
| `lib/webserver/server.py` | 删除 `_handle_download`, `_download_csv`, `_download_bib` 方法 |

#### 36d: 移除BIB文件头信息
| 文件 | 修改内容 |
|------|----------|
| `lib/process/export.py` | `export_bib` 函数移除所有头信息，只输出BIB条目 |

**CSV相关性文本映射**:
```python
RELEVANT_TEXT = {
    'zh': {'Y': '符合', 'N': '不符'},
    'en': {'Y': 'Relevant', 'N': 'Irrelevant'}
}
```

### 数据流

```
前端 index.html
  │ i18n.getLang() → 'zh' 或 'en'
  ↓
query_api.py
  │ payload.language → search_params.language
  ↓
paper_processor.py
  │ search_params.language → full_search_params.language
  ↓
query_log (MySQL)
  │ search_params JSON
  ↓
search_paper.py (Worker读取)
  │ LANGUAGE_MAP['zh'] → '中文'
  │ LANGUAGE_MAP['en'] → 'English'
  │ system_prompt.replace('{language}', lang_text)
  ↓
AI API
```

### 语言映射
```python
LANGUAGE_MAP = {
    'zh': '中文',
    'en': 'English'
}
```

### 排序逻辑
```python
def _relevance_sort_key(item):
    doi, data = item
    ai_result = data.get('ai_result', {})
    relevant = ai_result.get('relevant', 'N')
    return 0 if relevant == 'Y' else 1  # Y排前面
```

### 修改文件清单
- `lib/html/index.html` - startSearch/startDistillation 添加 language 参数 + 蒸馏按钮文字居中 + 清理前端遗留旧API调用
- `lib/webserver/query_api.py` - 接收 language 参数
- `lib/process/paper_processor.py` - 传递 language 参数
- `lib/process/search_paper.py` - LANGUAGE_MAP + 占位符替换
- `lib/process/download_worker.py` - CSV 排序 + Is_Relevant列语言适配
- `lib/webserver/server.py` - 删除旧架构同步下载API（3个方法 + 2个路由）
- `lib/process/export.py` - 移除BIB文件头信息
- `lib/html/login.html` - 登录成功消息使用 i18n.t() 本地化
- `lib/html/static/js/i18n.js` - 添加 login.success/failed/invalid_credentials 翻译

### 前端下载代码清理
删除旧架构同步下载API后，同步清理前端遗留代码：
- **删除函数**: `downloadHistoryResults` - 该函数仍调用已删除的旧API (`/api/download_csv`, `/api/download_bib`)
- **替换调用**: `updateHistoryDescriptionCard` 模板中的下载按钮改用 `downloadHistoryCsv` / `downloadHistoryBib`
  - 第4687行: `downloadHistoryResults('${queryIndex}', 'csv')` → `downloadHistoryCsv('${queryIndex}', '')`
  - 第4690行: `downloadHistoryResults('${queryIndex}', 'bib')` → `downloadHistoryBib('${queryIndex}', '')`

### API变更
- **已删除** `/api/download_csv` - 旧架构同步下载CSV（使用 `/api/download/create` 替代）
- **已删除** `/api/download_bib` - 旧架构同步下载BIB（使用 `/api/download/create` 替代）

---

## 修复轮次三十七：用户Token认证安全加固 (2025-12-02)

### 问题清单
1. **严重安全漏洞**: `auth.py` 中生成Token后未存储到Redis，导致后端无法验证Token
2. 前端可随意伪造uid调用任意API，没有真正的认证机制
3. 用户可以访问/操作其他用户的任务和数据

### 问题分析

#### 37a: Token生成但未验证
- **代码位置**: `lib/webserver/auth.py` 第79行
- **问题**: `login_user` 函数使用 `secrets.token_urlsafe(32)` 生成token，但只返回给前端，未存储到Redis
- **后果**: 后端API无法验证token是否有效，任何人只要知道uid就能调用任意API
- **源代码注释**: "实际项目中应使用更安全的方式"表明开发者知道这是问题但未修复

#### 37b: 前端直接传递uid
- **问题**: 所有API调用（查询、下载、余额等）都从localStorage读取uid并传递给后端
- **后果**: 攻击者可以修改localStorage中的userId为任意值，访问其他用户的数据

#### 37c: 没有统一的认证层
- **问题**: 每个API处理函数直接从payload获取uid，没有中间件验证
- **后果**: 无法统一管理认证逻辑，容易出现遗漏

### 修复内容

#### 37a: 新建 Redis 用户会话模块
- **文件**: `lib/redis/user_session.py` (新建)
- **功能**: 
  - `generate_token()`: 生成安全随机Token
  - `create_session(uid)`: 创建会话并存储到Redis (key: `user:session:{token}`, value: uid)
  - `get_session_uid(token)`: 验证Token并获取uid，同时刷新TTL
  - `destroy_session(token)`: 销毁会话（登出时使用）
  - `is_valid_session(token)`: 检查会话是否有效
- **TTL**: 24小时 (TTL_USER_SESSION)

#### 37b: 新建 Redis TTL常量
- **文件**: `lib/redis/connection.py`
- **新增**: `TTL_USER_SESSION = 24 * 3600`

#### 37c: 新建用户认证模块
- **文件**: `lib/webserver/user_auth.py` (新建)
- **功能**:
  - `extract_token_from_headers(headers)`: 从Authorization头提取Token
  - `require_auth(headers)`: 验证Token并返回 (success, uid, error)
  - 支持 `Authorization: Bearer {token}` 格式

#### 37d: 修改登录流程
- **文件**: `lib/webserver/auth.py`
- **修改**: `login_user` 函数调用 `UserSession.create_session(uid)` 存储Token

#### 37e: 修改用户API
- **文件**: `lib/webserver/user_api.py`
- **修改**: 
  - 除 `/api/register` 和 `/api/login` 外，所有端点添加Token验证
  - 使用 `require_auth(headers)` 获取验证后的uid
  - 不再信任payload中的uid

#### 37f: 修改查询API
- **文件**: `lib/webserver/query_api.py`
- **修改**: 
  - 所有需要认证的端点添加Token验证
  - 使用 `require_auth(headers)` 获取验证后的uid
  - 公开数据端点（tags、journals、count_papers）保持不验证

#### 37g: 修改下载API
- **文件**: `lib/webserver/server.py`
- **修改**: 
  - `_handle_download_create`: 添加Token验证
  - `_handle_download_status`: 添加Token验证 + 任务归属验证
  - `_handle_download_file`: 支持URL参数传递Token（因为文件下载是浏览器跳转，无法设置header）

#### 37h: 修改前端 index.html
- **新增**: `authFetch(url, options)` 辅助函数
  - 自动添加 `Authorization: Bearer {token}` 头
  - 401响应自动跳转登录页
- **修改**: 27个fetch调用改用authFetch
- **移除**: payload中不再传递uid参数

#### 37i: 修改前端 billing.html
- **新增**: `authFetch` 辅助函数
- **修改**: 余额获取和账单加载使用authFetch
- **修改**: 登出时同时清除userToken

### 新增 Redis Key 格式
| Key 格式 | 类型 | 说明 | TTL |
|----------|------|------|-----|
| `user:session:{token}` | String | 用户会话Token→uid映射 | 24小时 |

### 安全改进对比
| 方面 | 修复前 | 修复后 |
|------|--------|--------|
| Token验证 | ❌ 无 | ✅ Redis存储验证 |
| uid来源 | payload（可伪造） | Token解析（后端控制） |
| 任务归属 | ❌ 无验证 | ✅ uid必须匹配 |
| 数据隔离 | ❌ 无 | ✅ 只能访问自己的数据 |
| 会话管理 | ❌ 无 | ✅ 24小时过期 |
| 登出安全 | ❌ 仅清除前端 | ✅ 可销毁Redis会话 |

### 修改文件统计
| 类型 | 数量 |
|------|------|
| 新增 | 2 |
| 修改 | 8 |

### 修改文件清单
- `lib/redis/user_session.py` (新建) - 用户会话管理
- `lib/webserver/user_auth.py` (新建) - 用户认证验证
- `lib/redis/connection.py` - 新增 TTL_USER_SESSION
- `lib/webserver/auth.py` - 登录时存储Token到Redis
- `lib/webserver/user_api.py` - 所有端点添加Token验证
- `lib/webserver/query_api.py` - 所有端点添加Token验证
- `lib/webserver/server.py` - 下载API添加Token验证
- `lib/html/index.html` - 所有fetch改用authFetch
- `lib/html/billing.html` - 所有fetch改用authFetch

---

## 注意事项

1. 每个阶段完成后需要生成阶段检查点文档
2. 若Context Window耗尽，使用INTERFACE_SUMMARY.md恢复上下文
3. 废弃的文件需要在"需要手动操作的事项.txt"中标注

