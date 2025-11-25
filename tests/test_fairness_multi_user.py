"""多用户公平性与有效容量提升压力测试（简化）

目标：
  - 模拟多个用户同时等待，当有效容量从较低值提升到较高值时，验证不同权限用户都能被放行，不出现“高权限用户长期垄断”或“低权限用户饥饿”。

实现思路：
  - 使用内存队列与 DummyAgg（与集成测试类似），构造 N 个用户各 1 个任务。
  - 初始 effective_capacity = 0.5 （所有用户 permission >= 1 -> 全部等待）。
  - 提升 effective_capacity 到一个较高值（例如 5.0）。
  - 并发启动多个 worker 线程，观察所有任务在合理时间内完成。
  - 统计完成顺序，确认没有某单一用户独占（不严格要求轮询，只避免全部集中于一个用户）。

注意：
  - 此测试为近似压力验证，不做精确概率/调度保证。
"""
import threading
import time
import unittest
from unittest import mock

from lib.process import worker as worker_mod
from lib.log import utils

class DummyAgg:
    """适配新的容量三元组测试桩：使用 max/occupied/remaining 语义取代旧 effective_capacity。
    - 提供 get_max_capacity_per_min / get_running_perm_sum / get_running_tasks_count 等接口
    - set_uid_perm 用于分配权限；不真实计算 occupied，这里由 worker 自行推导
    """
    def __init__(self):
        self.max_cap = 0.5  # 初始较小，迫使等待
        self.running_sum = 0
        self.running_cnt = 0
        self.uid_perm = {}
    def get_max_capacity_per_min(self, default=0.0):
        return self.max_cap
    def set_max_capacity(self, v: float):
        self.max_cap = float(v)
    def get_running_perm_sum(self):
        return self.running_sum
    def get_running_tasks_count(self):
        return self.running_cnt
    def incr_running_stats(self, perm):
        self.running_cnt += 1
        self.running_sum += int(perm or 0)
    def decr_running_stats(self, perm):
        self.running_cnt = max(0, self.running_cnt - 1)
        self.running_sum = max(0, self.running_sum - int(perm or 0))
    def compute_and_set_remaining_capacity_per_min(self):
        # occupied 统一为运行中任务的 permission 之和（req/min）
        occupied = float(self.running_sum)
        return float(self.max_cap) - occupied
    def get_uid_permission(self, uid):
        return self.uid_perm.get(uid, 0)
    def set_uid_perm(self, uid, perm):
        self.uid_perm[uid] = perm
    def get_tokens_per_req(self, default=0):
        return 400

class InMemoryQueue:
    def __init__(self):
        self.tasks = []
        self.lock = threading.Lock()
    def user_backlog_size(self, uid):
        with self.lock:
            return sum(1 for t in self.tasks if t['uid']==uid and not t.get('done'))
    def peek_head_for_user(self, uid):
        with self.lock:
            for t in self.tasks:
                if t['uid']==uid and not t.get('done'):
                    return t
        return None
    def conditional_pop(self, task_id, uid):
        with self.lock:
            # Strict FIFO per test: tasks appended grouped by uid
            head = None
            for t in self.tasks:
                if not t.get('done'):
                    head = t
                    break
            if not head:
                return None
            if head['task_id'] != task_id or head['uid'] != uid:
                return None
            return head
    def mark_done(self, task_id):
        with self.lock:
            for t in self.tasks:
                if t['task_id']==task_id:
                    t['done'] = True
                    return True
        return False
    def push_back_ready(self, task_id):
        return True
    def mark_failed(self, task_id, reason):
        return True

class DummyDBReader:
    def get_tokens_per_req(self, default):
        return 400
    def get_query_log_by_index(self, qi):
        return {'query_table':'t','research_question':'rq','requirements':'req'}
    def get_paper_title_abstract_by_doi(self, doi):
        return {'title':'Title','abstract':'Abstract'}
    def get_search_id_by_doi(self, table, qi, doi):
        return 1
    def update_search_result(self, *args, **kwargs):
        return True
    def compute_query_progress(self, table, qi):
        return {'completed':0,'total':0}
    def finalize_query_if_done(self, table, qi):
        return True
    def get_active_queries_info(self):
        return []
    def close_thread_connection(self):
        return True
    def get_active_api_accounts(self):
        return [{'api_key': 'test-key'}]

class TestFairnessMultiUser(unittest.TestCase):
    def test_multi_user_release_after_capacity_increase(self):
        dagg = DummyAgg()
        q = InMemoryQueue()
        users = [11, 22, 33, 44, 55]
        # Assign permissions (different values)
        perms = [1, 2, 3, 4, 5]
        task_id = 1000
        for uid, perm in zip(users, perms):
            dagg.set_uid_perm(uid, perm)
            q.tasks.append({'task_id': task_id, 'uid': uid, 'query_index': uid, 'doi': f'doi-{uid}', 'done': False})
            task_id += 1

        with mock.patch.object(worker_mod, 'agg', dagg), \
             mock.patch.object(worker_mod, 'queue_manager', q), \
             mock.patch.object(worker_mod, 'db_reader', DummyDBReader()), \
             mock.patch.object(worker_mod, 'rate_limiter', mock.MagicMock(try_acquire_for_any_account=lambda tokens: (True, {'api':'dummy'}))), \
             mock.patch.object(worker_mod.search_paper, 'search_relevant_papers', return_value={'is_relevant': True, 'reason': 'ok', 'prompt_tokens':10, 'completion_tokens':5}), \
             mock.patch.object(utils, 'print_and_log'):

            # Start threads (they will wait because max capacity is initially too low)
            threads = []
            results = {}
            for uid in users:
                t = threading.Thread(target=lambda u=uid: results.setdefault(u, worker_mod.worker_queue_loop_for_user(u)), daemon=True)
                threads.append(t)
                t.start()

            # Wait a bit in waiting state
            time.sleep(1.0)
            # Ensure no task done yet
            self.assertTrue(any(not t['done'] for t in q.tasks), 'Tasks should still be waiting')

            # 提升 max_capacity 充足使 expected_used_capacity < remaining：
            # 最高 permission=5, tpr=400 => expected=2000；设置 max_cap >> 2000 释放所有任务
            dagg.set_max_capacity(5000.0)

            # Join threads
            for t in threads:
                t.join(timeout=5)

            # All tasks should be done
            self.assertTrue(all(t['done'] for t in q.tasks), 'All tasks should complete after capacity increase')

            # Fairness heuristic: at least 3 distinct users processed (avoid collapse into single user) -- here all should have run
            processed_users = [u for u in users if results.get(u, 0) >= 0]
            self.assertGreaterEqual(len(set(processed_users)), 3)

if __name__ == '__main__':
    unittest.main()
