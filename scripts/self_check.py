"""轻量自检脚本

用途：
  - 调用后端 /api/queue/stats 与 /api/admin/capacity 接口
  - 校验关键字段存在与只读语义（不出现可写/切换关键字）
  - 打印聚合有效容量、账号数量与简单一致性检查结果

运行：
  python scripts/self_check.py --host 127.0.0.1 --port 8080
"""
from __future__ import annotations
import sys
import json
import argparse
import urllib.request
import urllib.error

READONLY_NEGATIVE_KEYWORDS = [
    'bind', 'assign', 'reserve', 'toggle', 'switch', 'promote', 'waiting'
]

REQUIRED_QUEUE_FIELDS = [
    'backlog', 'active_uids', 'effective_capacity_per_min', 'accounts'
]

REQUIRED_CAPACITY_FIELDS = [
    'accounts', 'tokens_per_req', 'effective_capacity_per_min'
]


def fetch_json(url: str, timeout: int = 5):
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        data = resp.read().decode('utf-8', errors='replace')
        return json.loads(data)


def check_readonly_semantics(payload: dict) -> list[str]:
    text_blob = json.dumps(payload, ensure_ascii=False).lower()
    hits = []
    for kw in READONLY_NEGATIVE_KEYWORDS:
        if kw in text_blob:
            hits.append(kw)
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()

    base = f"http://{args.host}:{args.port}"
    queue_url = base + '/api/queue/stats'
    cap_url = base + '/api/admin/capacity'

    ok = True

    print(f"[self-check] Fetching {queue_url}")
    try:
        queue_stats = fetch_json(queue_url)
    except Exception as e:
        print(f"[self-check] ERROR queue_stats fetch failed: {e}")
        return 1

    if not queue_stats.get('success'):  # type: ignore
        print("[self-check] queue_stats success flag missing or false")
        ok = False

    missing_queue = [f for f in REQUIRED_QUEUE_FIELDS if f not in queue_stats]
    if missing_queue:
        print(f"[self-check] MISSING queue fields: {missing_queue}")
        ok = False

    print(f"[self-check] backlog={queue_stats.get('backlog')} active_uids={len(queue_stats.get('active_uids', []))} effective_capacity_per_min={queue_stats.get('effective_capacity_per_min')} accounts={queue_stats.get('accounts')}")

    bad_kw_queue = check_readonly_semantics(queue_stats)
    if bad_kw_queue:
        print(f"[self-check] WARNING queue payload contains write-ish keywords: {bad_kw_queue}")
        ok = False

    print(f"[self-check] Fetching {cap_url}")
    try:
        cap_stats = fetch_json(cap_url)
    except Exception as e:
        print(f"[self-check] ERROR capacity fetch failed: {e}")
        return 1

    if not cap_stats.get('success'):  # type: ignore
        print("[self-check] capacity success flag missing or false")
        ok = False

    missing_cap = [f for f in REQUIRED_CAPACITY_FIELDS if f not in cap_stats]
    if missing_cap:
        print(f"[self-check] MISSING capacity fields: {missing_cap}")
        ok = False

    accounts = cap_stats.get('accounts', [])
    print(f"[self-check] capacity accounts={len(accounts)} tokens_per_req={cap_stats.get('tokens_per_req')} effective_capacity_per_min={cap_stats.get('effective_capacity_per_min')}")

    bad_kw_cap = check_readonly_semantics(cap_stats)
    if bad_kw_cap:
        print(f"[self-check] WARNING capacity payload contains write-ish keywords: {bad_kw_cap}")
        ok = False

    # Simple consistency heuristic: effective capacity should be >= number of active_uids (one paper/min each minimal) unless 0.
    try:
        eff_cap_q = int(queue_stats.get('effective_capacity_per_min') or 0)
        active_uids = len(queue_stats.get('active_uids', []))
        if eff_cap_q and eff_cap_q < active_uids:
            print(f"[self-check] WARNING effective_capacity_per_min({eff_cap_q}) < active_uids({active_uids})")
            ok = False
    except Exception:
        pass

    print("[self-check] RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
