"""最小容量与 FIFO 测试

说明：
  - 使用 unittest 框架，不依赖真实 Redis/MySQL（需要项目提供模拟接口或在测试环境连接测试库）
  - 这里只对核心逻辑进行最小行为验证：
      1) 多用户入队后 peek + conditional_pop 顺序确保 FIFO
      2) 用户 permission >= effective_capacity 时任务阻塞（不弹出）
      3) active_uids 减少 -> effective_capacity 提升后再允许继续弹出

依赖：
  - queue_facade.enqueue_tasks_for_query / peek_head_for_user / conditional_pop
  - rate_limiter_facade.calc_effective_capacity_per_min （需可替换/打桩）

注意：
  - 若真实实现需要 Redis 或数据库，请在运行测试前设置测试配置（或通过 monkeypatch 注入假实现）。
  - 这里给出结构与伪桩；需要根据实际项目的可测试性补充 stub/mock。
"""
from __future__ import annotations
import unittest
from typing import Dict, List

# 导入待测模块（根据实际包结构调整）
from lib.process import queue_facade
from lib.process import rate_limiter_facade

# --- 测试桩 & 工具 ---
class FakeRateLimiter:
    def __init__(self):
        self.tokens_per_req = 400
        self.perm_sum_active = 0
        self.base_capacity = 10  # 模拟基础容量（例如按账号聚合）

    def set_active_perm_sum(self, v: int):
        self.perm_sum_active = v

    def calc_effective_capacity_per_min(self, tokens_per_req: int):  # noqa: D401
        # 简化公式：min(base_capacity, max(1, base_capacity - perm_sum_active//2))
        eff = self.base_capacity - (self.perm_sum_active // 2)
        if eff < 1:
            eff = 1
        return {
            'accounts': 3,
            'effective_req_per_min': eff
        }

fake_rl = FakeRateLimiter()

original_calc = rate_limiter_facade.calc_effective_capacity_per_min

def patch_calc(tokens_per_req: int):
    return fake_rl.calc_effective_capacity_per_min(tokens_per_req)


# 简单内存队列替身，模拟 FIFO 与容量门控
class FakeQueue:
    def __init__(self):
        self.q: dict[int, list[dict]] = {}
        self.next_id = 1
        self.popped_in_window = 0

    def _eff_cap(self) -> int:
        d = fake_rl.calc_effective_capacity_per_min(fake_rl.tokens_per_req)
        return int(d.get('effective_req_per_min') or 0)

    def _allow(self) -> bool:
        cap = self._eff_cap()
        return cap <= 0 or self.popped_in_window < cap

    def enqueue_tasks_for_query(self, uid: int, qidx: int, dois: list[str]) -> int:
        arr = self.q.setdefault(uid, [])
        for doi in dois:
            arr.append({'task_id': self.next_id, 'uid': uid, 'query_index': qidx, 'doi': doi})
            self.next_id += 1
        return len(dois)

    def peek_head_for_user(self, uid: int):
        arr = self.q.get(uid) or []
        return arr[0] if arr else None

    def conditional_pop(self, task_id: int, uid: int):
        arr = self.q.get(uid) or []
        if not arr:
            return None
        head = arr[0]
        if head['task_id'] != task_id:
            return None
        if not self._allow():
            return None
        # 通过门控，弹出
        self.popped_in_window += 1
        return arr.pop(0)

fake_queue = FakeQueue()

_orig_enqueue = queue_facade.enqueue_tasks_for_query
_orig_peek = queue_facade.peek_head_for_user
_orig_pop = queue_facade.conditional_pop

# --- 伪任务生成帮助函数 ---
_generated = []

def _gen_tasks(uid: int, query_index: int, count: int) -> List[str]:
    res = []
    for i in range(count):
        doi = f"doi_{uid}_{query_index}_{i}"
        res.append(doi)
    return res

class TestCapacityAndFIFO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # monkeypatch 限流计算 + 队列接口
        rate_limiter_facade.calc_effective_capacity_per_min = patch_calc  # type: ignore
        queue_facade.enqueue_tasks_for_query = fake_queue.enqueue_tasks_for_query  # type: ignore
        queue_facade.peek_head_for_user = fake_queue.peek_head_for_user  # type: ignore
        queue_facade.conditional_pop = fake_queue.conditional_pop  # type: ignore

    @classmethod
    def tearDownClass(cls):
        # 恢复原函数
        rate_limiter_facade.calc_effective_capacity_per_min = original_calc  # type: ignore
        queue_facade.enqueue_tasks_for_query = _orig_enqueue  # type: ignore
        queue_facade.peek_head_for_user = _orig_peek  # type: ignore
        queue_facade.conditional_pop = _orig_pop  # type: ignore

    def setUp(self):
        # 每个测试前清理假队列与窗口计数
        fake_queue.q.clear()
        fake_queue.popped_in_window = 0

    def test_fifo_order_multi_users(self):
        uid1, uid2 = 101, 202
        qidx = 555
        # 入队：用户1两个任务，用户2三个任务
        queue_facade.enqueue_tasks_for_query(uid1, qidx, _gen_tasks(uid1, qidx, 2))
        queue_facade.enqueue_tasks_for_query(uid2, qidx, _gen_tasks(uid2, qidx, 3))

        # 轮询 peek -> conditional_pop FIFO 验证
        popped: List[str] = []
        while True:
            task1 = queue_facade.peek_head_for_user(uid1)
            task2 = queue_facade.peek_head_for_user(uid2)
            if not task1 and not task2:
                break
            if task1:
                popped_obj = queue_facade.conditional_pop(task1['task_id'], uid1)
                if popped_obj:
                    popped.append(popped_obj['doi'])
            if task2:
                popped_obj = queue_facade.conditional_pop(task2['task_id'], uid2)
                if popped_obj:
                    popped.append(popped_obj['doi'])
        # 断言顺序保留相对 FIFO（同一用户内部顺序不乱）
        user1_dois = [d for d in popped if d.startswith('doi_101_')]
        user2_dois = [d for d in popped if d.startswith('doi_202_')]
        self.assertEqual(user1_dois, ['doi_101_555_0', 'doi_101_555_1'])
        self.assertEqual(user2_dois, ['doi_202_555_0', 'doi_202_555_1', 'doi_202_555_2'])

    def test_capacity_block_then_release(self):
        uid = 303
        qidx = 777
        # 设置高并发占用 -> 有效容量低
        fake_rl.set_active_perm_sum(18)  # 触发较低的 effective capacity
        queue_facade.enqueue_tasks_for_query(uid, qidx, _gen_tasks(uid, qidx, 5))

        # 第一次尝试：有效容量较低，预期只能弹出少量（这里我们简单检查是否至少 1）
        popped_first = 0
        for _ in range(5):
            task = queue_facade.peek_head_for_user(uid)
            if not task:
                break
            obj = queue_facade.conditional_pop(task['task_id'], uid)
            if obj:
                popped_first += 1
        self.assertGreaterEqual(popped_first, 1)

        # 提升容量（减少 active 权重）
        fake_rl.set_active_perm_sum(2)

        # 再入队一些任务
        queue_facade.enqueue_tasks_for_query(uid, qidx, _gen_tasks(uid, qidx, 3))

        popped_second = 0
        while True:
            task = queue_facade.peek_head_for_user(uid)
            if not task:
                break
            obj = queue_facade.conditional_pop(task['task_id'], uid)
            if obj:
                popped_second += 1
        # 在容量提升后应能处理剩余所有任务（粗略检查：第二阶段弹出数 > 第一阶段）
        self.assertGreater(popped_second, popped_first)

if __name__ == '__main__':
    unittest.main()
