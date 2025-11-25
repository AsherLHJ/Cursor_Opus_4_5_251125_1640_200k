"""
MySQL 版限流器（Stage2）：分钟粒度的 RPM/TPM 近似控制
- 账户列表来源：api_list（get_active_api_accounts）
- 已用计数：api_usage_minute（upsert_api_usage_minute / get_api_usage_minute）
- 设计目标：在不引入 Redis 的前提下，提供保守的速率限制，避免超限
- 失败/缺表时：退化为“总是允许”，以保证旧路径可用
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple
from datetime import datetime
import random

from ..load_data import db_reader


def _minute_floor(dt: Optional[datetime] = None) -> datetime:
    dt = dt or datetime.utcnow()
    return dt.replace(second=0, microsecond=0)


def calc_effective_capacity_per_min(tokens_per_req: int) -> Dict:
    """按账户聚合得到每分钟可处理的近似请求数（min(rpm_limit, tpm_limit/tokens_per_req)）。"""
    accounts = db_reader.get_active_api_accounts() or []
    eff_caps = []
    for a in accounts:
        try:
            rpm = int(a.get('rpm_limit') or 0)
        except Exception:
            rpm = 0
        try:
            tpm = int(a.get('tpm_limit') or 0)
        except Exception:
            tpm = 0
        if tokens_per_req <= 0:
            tokens_per_req = 400
        if rpm <= 0 and tpm <= 0:
            continue
        cap = min(rpm if rpm > 0 else 10**9, (tpm // max(tokens_per_req, 1)) if tpm > 0 else 10**9)
        eff_caps.append(max(cap, 0))
    total = sum(eff_caps) if eff_caps else 0
    return {"accounts": len(accounts), "effective_req_per_min": int(total)}


def try_acquire_for_any_account(tokens: int) -> Tuple[bool, Optional[Dict]]:
    """
    在任一可用账户上尝试获取一次请求额度：
    - 读取当前分钟的用量
    - 若 rpm/tpm 允许，则写回 used_req+1, used_tokens+tokens
    - 返回 (ok, account)
    失败或缺表：返回 (True, None) 表示放行但未选择账户（上层可继续 reserve 可用 key）。
    """
    try:
        accounts = db_reader.get_active_api_accounts() or []
        if not accounts:
            return True, None
        # 简单负载均衡：随机两选择余量大的
        minute_ts = _minute_floor()
        cand = random.sample(accounts, min(2, len(accounts)))
        picked = None
        best_slack = -1
        for a in cand:
            usage = db_reader.get_api_usage_minute(a.get('api_name') or str(a.get('api_index')), minute_ts)
            rpm = int(a.get('rpm_limit') or 0) or 30000
            tpm = int(a.get('tpm_limit') or 0) or 5000000
            used_req = int(usage.get('used_req') or 0)
            used_tok = int(usage.get('used_tokens') or 0)
            slack_req = max(0, rpm - used_req)
            slack_tok = max(0, tpm - used_tok)
            slack = min(slack_req, slack_tok // max(tokens, 1))
            if slack > best_slack:
                best_slack = slack
                picked = a
        if picked is None:
            picked = accounts[0]
        # 再做一次阈值判断
        usage = db_reader.get_api_usage_minute(picked.get('api_name') or str(picked.get('api_index')), minute_ts)
        rpm = int(picked.get('rpm_limit') or 0) or 30000
        tpm = int(picked.get('tpm_limit') or 0) or 5000000
        used_req = int(usage.get('used_req') or 0)
        used_tok = int(usage.get('used_tokens') or 0)
        if used_req + 1 > rpm or used_tok + tokens > tpm:
            return False, None
        db_reader.upsert_api_usage_minute(picked.get('api_name') or str(picked.get('api_index')), minute_ts, 1, int(tokens or 0))
        return True, picked
    except Exception:
        # 缺表或异常时放行
        return True, None
