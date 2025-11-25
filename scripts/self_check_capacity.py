"""轻量自检脚本：
调用 /api/queue/stats 与 /api/admin/capacity 验证只读字段语义。
运行方式（确保后端已启动本地 8080 端口）：
    python scripts/self_check_capacity.py
输出：
    每个端点的关键字段、语义校验结果、潜在异常提示。
"""
from __future__ import annotations
import json
import sys
import urllib.request
import urllib.error
from typing import Dict, Any

BASE = "http://127.0.0.1:8080"

EXPECTED_QUEUE_STATS_KEYS = {
    "success", "backlog", "active_uids", "user_capacity_sum", "effective_capacity_per_min",
    "accounts", "redis", "db"
}
EXPECTED_CAPACITY_KEYS = {
    "success", "accounts", "redis_enabled", "tokens_per_req", "effective_capacity_per_min"
}

READ_ONLY_FLAGS: set[str] = set()  # 已移除旧 flags 字段


def fetch_json(path: str) -> Dict[str, Any]:
    url = f"{BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}"}
    except Exception as e:
        return {"_error": str(e)}


def check_queue_stats(obj: Dict[str, Any]) -> None:
    print("[CHECK] /api/queue/stats")
    if "_error" in obj:
        print("  ERROR:", obj["_error"])
        return
    missing = EXPECTED_QUEUE_STATS_KEYS - set(obj.keys())
    if missing:
        print("  Missing keys:", sorted(missing))
    else:
        print("  Keys OK")
    # 简单语义打印（不再检查 flags）
    print(f"  backlog={obj.get('backlog')} effective_capacity_per_min={obj.get('effective_capacity_per_min')} accounts={obj.get('accounts')}")
    print(f"  redis={obj.get('redis')} db={obj.get('db')}")


def check_capacity(obj: Dict[str, Any]) -> None:
    print("[CHECK] /api/admin/capacity")
    if "_error" in obj:
        print("  ERROR:", obj["_error"])
        return
    missing = EXPECTED_CAPACITY_KEYS - set(obj.keys())
    if missing:
        print("  Missing keys:", sorted(missing))
    else:
        print("  Keys OK")
    accounts = obj.get("accounts", [])
    if not isinstance(accounts, list):
        print("  accounts 字段类型异常")
    else:
        # 抽样前 3 条
        for i, acc in enumerate(accounts[:3]):
            print(f"  sample[{i}] api_index={acc.get('api_index')} active={acc.get('is_active')} rpm={acc.get('rpm_limit')} tpm={acc.get('tpm_limit')} used_req={acc.get('used_req')} used_tokens={acc.get('used_tokens')}")
    print(f"  tokens_per_req={obj.get('tokens_per_req')} effective_capacity_per_min={obj.get('effective_capacity_per_min')} redis_enabled={obj.get('redis_enabled')}")


def main():
    qs = fetch_json("/api/queue/stats")
    cp = fetch_json("/api/admin/capacity")
    check_queue_stats(qs)
    print()
    check_capacity(cp)

    # 汇总结论（只读语义快速判断）
    if "_error" not in qs and "_error" not in cp:
        print("\n[SUMMARY] 两端点访问成功。若未出现 Missing keys 列表则语义校验通过。")
    else:
        print("\n[SUMMARY] 存在访问错误，请检查后端是否启动或端口/防火墙设置。")


if __name__ == "__main__":
    main()
