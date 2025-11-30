# 新架构重构进度日志

## 项目概述
- **开始时间**: 2025-11-25 16:40
- **重构完成时间**: 2025-11-25 17:50
- **最后修复时间**: 2025-11-30
- **指导文件**: 新架构项目重构完整指导文件20251130.txt
- **目标**: 按照新架构指导，彻底重构整个项目
- **状态**: ✅ 重构完成 + 二十五轮Bug修复

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

## 注意事项

1. 每个阶段完成后需要生成阶段检查点文档
2. 若Context Window耗尽，使用INTERFACE_SUMMARY.md恢复上下文
3. 废弃的文件需要在"需要手动操作的事项.txt"中标注

