# AutoPaperWeb 管理员系统使用指南（固定共享池架构）

> 维护说明：系统仅支持 bcrypt 密码哈希。

本指南覆盖管理员控制面板、容量与队列可视化、账户限额与全局 tokens_per_req 在线配置，以及对应 API 契约。系统已固定为“共享账户池 + 单一 FIFO 队列 + 容量门控”架构，不再提供任何“共享单 Key 并发开关”。单位与语义（全部统一为“请求/分钟 req/min”或“篇/分钟 papers/min”，两者在此场景下等价）：
- 用户权限 permission：每分钟可查询的“篇/分钟”额度（整数，req/min）
- 系统最大容量 max capacity：系统理论最大并行处理能力（papers/min），公式：`max_capacity = Σ(tpm_limit_active) / tokens_per_req`
- 已占用容量 occupied capacity：当前正在执行的所有任务所属用户的 permission 之和（papers/min），公式：`occupied_capacity = Σ(permission_running_tasks) = running_perm_sum`
- 剩余容量 remaining capacity：当前仍可放行的新任务容量（papers/min），公式：`remaining_capacity = max_capacity - occupied_capacity` （若为负数归零）
- 门控条件（严格小于）：`permission < remaining_capacity` 才可放行队头任务。

## 面板功能概览

### 用户管理
- 查看用户（UID、用户名、余额、权限）
- 编辑余额（非负数）
- 编辑权限（req/min，非负整数）

### 容量与队列（新）
顶层概览：
  - backend：当前后端使用的存储与限流实现（Redis 优先，失败回退 MySQL）
  - 系统最大容量（papers/min）：Σ(tpm_limit_active) / tokens_per_req
  - 已占用容量 / 剩余容量（papers/min）：根据当前正在运行的任务动态计算
  - 全局排队篇数（backlog）：所有未处理任务的篇数
  - RDS 健康状态：基础连通 + VERSION()
- 全局参数：
  - tokens_per_req（单篇文献 token 总消耗，默认 400，可在线保存）
- 账户维度：
  - 查看/编辑每个 API Key 的 RPM 限额与 TPM 限额
  - 查看本分钟已用 RPM/TPM
  - 切换账户启用/禁用（is_active）

## 使用方法

### 访问管理员面板
1. 启动服务后访问：`http://<host>:<port>/AutoPaperSearchControlPanelAdmin.html`
2. 页面自动加载用户与容量信息；若需要，先在右上角切换语言（中/EN）。

### 常用操作
1) 编辑 tokens_per_req（影响系统最大容量计算）
  - 在“容量与队列状态”中修改数值并点击“保存”
  - 立即生效，/api/queue/stats 的 max_capacity_per_min 将随之变化

2) 编辑每个 API Key 的 RPM/TPM 限额
   - 在表格中对应行输入新值，点击“保存限额”
   - 如需要禁用某账户，点击“禁用”（再次点击可启用）

3) 编辑用户权限（req/min）与余额
   - 在用户表格中编辑数值并点击“更新”；“重置”可恢复原值

## 单位与术语（务必注意）
- permission：req/min（每分钟可查询篇数）
- max_capacity_per_min：papers/min（每分钟可处理篇数的上限）
- occupied_capacity_per_min：papers/min（当前占用）
- remaining_capacity_per_min：papers/min（当前剩余）
- tokens_per_req：全局配置，用于将 TPM 转换为 papers/min

## 管理接口（补充/新增）

用户与余额：
- GET /api/admin/users
- POST /api/admin/update_balance
- POST /api/admin/update_permission

容量与队列：
- GET /api/queue/stats → { backlog, active_uids, user_capacity_sum, effective_capacity_per_min(兼容), max_capacity_per_min, occupied_capacity_per_min, remaining_capacity_per_min, accounts, redis, db }
- GET /api/admin/capacity → { accounts:[{ api_index, api_name, is_active, rpm_limit, tpm_limit, used_req, used_tokens }], tokens_per_req, effective_capacity_per_min(兼容), max_capacity_per_min, occupied_capacity_per_min, remaining_capacity_per_min }

全局参数：
- GET /api/admin/tokens_per_req → { tokens_per_req }
- POST /api/admin/set_tokens_per_req { tokens_per_req:int } → { success:true, tokens_per_req }

账户限额：
- POST /api/admin/update_api_limits { api_index:int, rpm_limit:int, tpm_limit:int } → { success:true }
- POST /api/admin/account-toggle { api_index:int, enabled:bool } → { success:true }

## 错误处理与排查

常见错误代码：
- `invalid_balance`：余额必须是非负数
- `invalid_permission`：每分钟可查询篇数必须是非负整数
- `invalid_limits`：无效的 RPM/TPM 限额
- `update_failed`：保存失败（查看 message）

排查建议：
1. 容量/队列信息缺失：检查 /api/queue/stats，确认 backend 字段与 Redis/MySQL 健康；
2. 编辑限额无效：检查返回的错误信息，确认值范围与数据类型；
3. tokens_per_req 修改无效：确认 /api/admin/tokens_per_req 返回的新值与 /api/queue/stats 的 effective_rate_per_min 是否更新；
4. i18n 文本未刷新：点击右上角“中/EN”语言切换按钮以强制刷新。

## 安全注意事项

- 管理员面板仅授权访问；必要时限制来源 IP；
- 管理操作均进行输入校验与最小权限原则；
- 重要配置变更（如 tokens_per_req、账户限额）建议保留审计记录；
- 建议通过 HTTPS 提供面板接入。

---

更多部署与运行时说明，请参见 `docs/DEPLOYMENT.md`。已移除历史的“共享开关 / 多模式”相关描述；如需回滚旧版本，请在旧分支中恢复对应端点与配置键。

## 进度显示与会话隔离（新增说明）

自 Stage4 起，进度按“会话”隔离：会话键 = (uid, query_index)。

- 内存侧：使用隔离进度桶 progress_map[(uid, query_index)] 记录 processed、最近耗时窗口 times、total 等；
- DB 校正：进度监控线程会定期调用 compute_query_progress(table, query_index) 修正 total/processed，避免重启或回滚导致的偏差；
- 起止时间：以 query_log.start_time 为准（UTC-YYYY-MM-DD HH:MM:SS），end_time 在全部完成后由 finalize_query_if_done 写入；
- 监控显示：只显示当前聚焦 (data.current_uid, data.current_query_index) 的进度；
- 完成处理：当 finalize_query_if_done 检测到查询完成时，会打印一次最终统计并释放对应的进度桶（内存）。

对 Prompt/返回值的影响：
- 模型提示与返回 JSON 中新增并强制回显两个字段：uid、query_index；
- 单元测试模式（unit_test_mode=true）下，模拟路径也会回显 uid、query_index，保持与真实路径一致；
- 工作线程在收到与期望不一致的 uid/query_index 时，视为“会话标识不一致”错误并回滚该任务，以防串号。

## 运维排查（Redis 观测指令）

以下 redis-cli 指令用于快速观测聚合键状态（需具备到 Redis 的网络访问与认证权限）。

基础容量相关键：

```bash
redis-cli GET apw:tokens_per_req              # 单篇文献 token 消耗
redis-cli GET apw:api_tpm_total               # 所有激活账号 TPM 总和（由调度器计算）
redis-cli GET apw:perm_sum_active             # active_uids 内所有用户权限和
redis-cli GET apw:max_capacity_per_min        # 系统最大容量（篇/分钟）
redis-cli GET apw:occupied_capacity_per_min   # 已占用容量（篇/分钟）
redis-cli GET apw:remaining_capacity_per_min  # 剩余容量（篇/分钟）
redis-cli GET apw:running_tasks_count         # 正在执行中的任务数
redis-cli GET apw:running_perm_sum            # 正在执行中的任务对应 permission 之和
redis-cli SMEMBERS apw:active_uids            # 当前活跃用户 UID 集合
redis-cli GET apw:uid:perm:<uid>              # 某个 uid 的权限值（替换 <uid>）
```

解释与常见情形：
- max_capacity = Σ(tpm_limit_active) / tokens_per_req（仅统计启用的账号）
- occupied_capacity = running_perm_sum（运行中任务的 permission 直接求和，不再做平均或乘以 tokens）
- remaining_capacity = max_capacity - occupied_capacity（若 <0 归零）
- 若 tokens_per_req 或 tpm 总和为 0 → max_capacity=0（worker 将等待）。
- active_uids 长时间不减少：检查是否有查询未正确 finalize；必要时使用维护脚本清理活跃 UID。

门控等待日志（示例，新的 occupied 语义）：
```
[gate-wait-123] head_task=987 (expected>=remaining) | src: perm(uid)=60, running_tasks=2, avg_perm_running=30.00, api_tpm_total=24000, tpr=400, max=60.0000, occupied=45.0000, remaining=15.0000, expected=60.0000
```
说明：
- expected_used_capacity = permission（队头任务所属用户的 permission，不再乘 tokens_per_req）
- occupied = Σ(运行中任务的 permission) = running_perm_sum
- remaining = max - occupied
- 当 `permission < remaining` 时放行，否则持续输出 gate-wait 日志直至 remaining 增加或 permission 下调。

排查步骤建议：
1. max_capacity 为 0：检查 tokens_per_req 与各激活账号的 tpm_limit 是否均为 0 或调度器未刷新。
2. 某用户一直等待：检查 remaining 是否长期低于该用户 permission（可能系统总体 permission 设置偏高或账号 TPM 不足）。
3. api_tpm_total 异常偏低：检查调度器是否正常运行及账户是否被禁用（is_active=false）。
4. running_perm_sum 不回落：确认任务结束时是否调用了 `decr_running_stats(permission)`；必要时人工重置 Redis 键。
5. remaining 长期为 0：检查是否 max=occupied（系统满载）或 max 计算因 tokens_per_req 设置过大被压缩。
