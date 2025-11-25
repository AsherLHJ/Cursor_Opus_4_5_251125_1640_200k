"""Redis维护脚本：清理陈旧 active_uids

使用场景：
  - 某些 uid 已经没有任何进行中的查询，但仍残留在 apw:active_uids 集合中，导致 perm_sum_active 过大、effective_capacity 异常偏低。

策略：
  1. 读取 active_uids 集合
  2. 对每个 uid 查询 MySQL 中是否仍有未完成(end_time IS NULL)的 query_log
  3. 若无未完成查询：
       - 从集合移除该 uid
       - perm_sum_active 减去其权限值
       - 删除 apw:uid:perm:{uid}
  4. 最后重新计算并写入 effective_capacity

运行：
  python scripts/redis_cleanup_active_uids.py

可选参数：
  --dry  仅打印将清理的 UID，不执行实际删除

注意：
  - 需具备 Redis 与 MySQL 正常连通；
  - 建议在低峰期执行；
  - 若使用外部调度器已定期清理，可不手动运行。
"""
from __future__ import annotations
import argparse
from typing import List

import os
import sys

# 允许直接以脚本方式运行：将项目根目录加入 sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from lib.process import redis_aggregates as agg  # type: ignore
    from lib.load_data import db_reader  # type: ignore
except ModuleNotFoundError:
    print('[cleanup] ERROR: cannot import project modules (lib.*). Please run the script from project root.')
    raise


def list_active_uids() -> List[int]:
    try:
        import redis
    except Exception:
        return []
    r = agg._get_redis_client()  # type: ignore
    if not r:
        return []
    try:
        members = r.smembers("apw:active_uids") or []
        out = []
        for m in members:
            try:
                out.append(int(m))
            except Exception:
                pass
        return sorted(out)
    except Exception:
        return []


def has_active_queries(uid: int) -> bool:
    if int(uid) <= 0:
        return False
    conn = db_reader._get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM query_log WHERE uid=%s AND end_time IS NULL",
                (int(uid),)
            )
            (cnt,) = cursor.fetchone() or (0,)
            return int(cnt or 0) > 0
    finally:
        conn.close()


def cleanup(dry: bool = False):
    active = list_active_uids()
    if not active:
        print("[cleanup] No active_uids found or Redis unavailable.")
        return
    print(f"[cleanup] Found {len(active)} active_uids: {active}")
    removed = []
    for uid in active:
        if not has_active_queries(uid):
            print(f"[cleanup] Stale uid detected: {uid}")
            removed.append(uid)
            if not dry:
                agg.remove_active_uid(uid)
    if not removed:
        print("[cleanup] No stale uids to remove.")
    else:
        print(f"[cleanup] Removed {len(removed)} stale uids: {removed} (dry={dry})")
        if not dry:
            # 重新计算有效容量（若依赖调度器公式，可视情况调用 compute_and_set_effective_capacity）
            eff = agg.compute_and_set_effective_capacity()
            print(f"[cleanup] Recomputed effective_capacity={eff:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry', action='store_true', help='Dry run: only list stale uids')
    args = parser.parse_args()
    cleanup(dry=args.dry)


if __name__ == '__main__':
    main()
